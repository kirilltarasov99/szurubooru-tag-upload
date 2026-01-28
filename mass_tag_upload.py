import asyncio
import re
from PicImageSearch import Iqdb
from pathlib import Path
import click

iqdb = Iqdb()

@click.command()
@click.option('--path', type=str)
@click.option('--url', type=str)
@click.option('--key', type=str)

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


def main(**kwargs):
    folder = Path(kwargs['path']).resolve()
    paths_files = [p for p in folder.rglob("*") if p.is_file()]

    for image in paths_files:
        relative = image.relative_to(folder)
        folder_tags = list(relative.parent.parts)

        tags, rating, link = asyncio.run(find_image(image, 85))
        if not tags:
            tags = asyncio.run(tag_interrogate(image))
            tags.append('ai_generated')
        
        tags.extend(folder_tags)


if __name__ == "__main__":
    main()
