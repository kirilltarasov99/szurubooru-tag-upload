import asyncio
import re
import json
import base64
import click
import os
import requests
from typing import Final
from PicImageSearch import Iqdb
from pathlib import Path


iqdb = Iqdb()
iqdb_supported = [".jpg", ".jpeg", ".png", ".gif"]
wd14_supported = [".jpg", ".jpeg", ".png"]
animated = [".gif"]
API_URL: Final = os.environ.get("BOORU_API_URL")
USERNAME: Final = os.environ.get("BOORU_USERNAME")
LOGIN_TOKEN: Final = os.environ.get("BOORU_TOKEN")

def btoa(txt: str):
    return base64.b64encode(txt.encode()).decode()

async def find_image(filepath, similarity):
    results = await iqdb.search(file=filepath)
    best_result = results.raw[0]

    if best_result.similarity >= similarity:
        query = best_result.origin.html()
        tags = re.findall(r'Tags: (.*?)\"/>', query)[0].split(" ")
        rating = re.findall('Rating: .', query)[0][-1]
        link = re.findall(r'a href="//(.*?)\"', query)[0]
    
    else:
        tags = None
        rating = "q"
        link = None

    return tags, rating, link


async def tag_interrogate(filepath):
    command = "python"
    args = ["wd14-tagger-standalone/run.py", "--cpu", "--model", "wd-v1-4-swinv2-tagger.v3", "--file", filepath]

    process = await asyncio.create_subprocess_exec(
        command, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()
    tags = str(stdout)[2:-3].split(", ")
    tags = [tag.replace("\\", "") for tag in tags]
    tags = [tag.replace(" ", "_") for tag in tags]
    
    return tags


async def upload(file, tags, safety, source):
    session = requests.Session()
    session.headers = {
        "Accept": "application/json",
        "Authorization": "Token " + btoa("{USERNAME}:{LOGIN_TOKEN}"),
    }
    with open(file, "rb") as uploadfile:
        temporary_data = session.post(
            f"{API_URL.rstrip('/')}/uploads", files={"content": uploadfile}
        ).json()
        file_token = temporary_data["token"]

        try:
            post_data = session.post(
                f"{API_URL}/posts",
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
        finally:
            uploadfile.close()  # clean up file handle

@click.command()
@click.option('--path', type=str)

def main(**kwargs):
    folder = Path(kwargs['path']).resolve()
    paths_files = [p for p in folder.rglob("*") if p.is_file()]

    for image in paths_files:
        relative = image.relative_to(folder)
        folder_tags = list(relative.parent.parts)
        file_type = image.suffix

        if file_type in iqdb_supported:
            print("iqdb_check")
            tags, safety, source_link = asyncio.run(find_image(image, 85))
            if not tags and file_type in wd14_supported:
                print("wd14_check")
                tags = asyncio.run(tag_interrogate(image))
                tags.append('ai_generated')
                safety = "sketchy"
                source_link = None
            

            tags.extend(folder_tags)
        
        elif file_type not in iqdb_supported and file_type not in wd14_supported:
            continue

        else:
            tags = ["no_autotag"]
        print("pass")
        asyncio.run(upload(image, tags, safety, source_link))


if __name__ == "__main__":
    main()
