import asyncio
import re

from celery import Celery
from PicImageSearch import Iqdb
from pathlib import Path


iqdb = Iqdb()
iqdb_supported = [".jpg", ".jpeg", ".png", ".gif"]
wd14_supported = [".jpg", ".jpeg", ".png"]
animated = [".gif"]

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


celery_app = Celery(
    'tagger',
    broker='redis://gluetun:6379/0',
    backend='redis://gluetun:6379/0'
)

@celery_app.task
def tag(filepath: Path):
    folder_tags = [p.name for p in filepath.parents]
    file_type = filepath.suffix
    tags = list()
    safety = "sketchy"
    source = str()

    if file_type in iqdb_supported:
        print("iqdb_check")
        tags, safety, source = asyncio.run(find_image(filepath, 85))
        if not tags and file_type in wd14_supported:
            print("wd14_check")
            tags = asyncio.run(tag_interrogate(filepath))
            tags.append('ai_generated')

        tags.extend(folder_tags)

        return {
            "status": "processed",
            "output": f"Processed {filepath}",
            "tags": tags,
            "safety": safety,
            "source": source
        }
        
    elif file_type not in iqdb_supported and file_type not in wd14_supported:
        return {
            "status": "unsupported",
            "output": f"Unsupported file type: {filepath}",
            "tags": tags,
            "safety": safety,
            "source": source
        }

    else:
        tags = ["no_autotag"]
        return {
            "status": "untagged",
            "output": f"Could not tag {filepath}",
            "tags": tags,
            "safety": safety,
            "source": source
        }
