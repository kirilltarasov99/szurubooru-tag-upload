import requests
import asyncio
import base64
import os
import time
import json
import logging

from typing import Final
from pathlib import Path
from celery import Celery

BOORU_API_URL: Final = os.environ.get("BOORU_API_URL")
USERNAME: Final = os.environ.get("BOORU_USERNAME")
LOGIN_TOKEN: Final = os.environ.get("BOORU_TOKEN")

logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO").upper(), # Set log level via env var
    format='%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s',
    handlers=[logging.StreamHandler()] # Explicitly use StreamHandler
)

celery_client = Celery(
    'tagger',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    )


def btoa(txt: str):
    return base64.b64encode(txt.encode()).decode()

def tagger_task_send(image_path):
    try:
        task = celery_client.send_task("tagger.tag", args=[image_path])
        return task.id
    
    except Exception:
        return
        # log exception and move on


def get_task_status(task_id):
    task = celery_client.AsyncResult(task_id)
    if task.state == 'PENDING':
        return {
            "task_id": task_id,
            "status": "pending"
        }
    
    elif task.state == 'SUCCESS':
        return {
            "task_id": task_id,
            "status": "success",
            "output": task.result["output"],
            "tags": task.result["tags"],
            "safety": task.result["safety"],
            "source": task.result["source"]
        }
        
    else:
        return {
            "task_id": task_id,
            "status": "failed"
        }


async def upload(file, tags, safety, source):
    session = requests.Session()
    session.headers = {
        "Accept": "application/json",
        "Authorization": "Token " + btoa("{USERNAME}:{LOGIN_TOKEN}"),
    }
    with open(file, "rb") as uploadfile:
        temporary_data = session.post(
            f"{BOORU_API_URL.rstrip('/')}/uploads", files={"content": uploadfile}
        ).json()
        file_token = temporary_data["token"]

        try:
            post_data = session.post(
                f"{BOORU_API_URL}/posts",
                json={"contentToken": file_token, "safety": safety, "tags": tags, "source": source},
                headers={"Content-Type": "application/json"},
            )
            
            return post_data.json()

        except requests.exceptions.HTTPError as e:
            try:
                error_details = post_data.json()
                print("Szurubooru API error:", error_details)
            except json.JSONDecodeError:
                print("Response body:", post_data.text)
            raise


def main(path):
    folder = Path(path).resolve()
    paths_files = [p for p in folder.rglob("*") if p.is_file()]

    for image in paths_files:
        task_id = tagger_task_send(image)
        while True:
            status = get_task_status(task_id)
            if status["status"] == "pending":
                time.sleep(0.1)
            elif status["status"] == "failed":
                # log problem
                continue

            else:
                tags = status["tags"]
                safety = status["safety"]
                source = status["source"]

                break
            
        logger.info(f"pass {image}")
        asyncio.run(upload(image, tags, safety, source))


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    path = "/app/data"
    main(path)