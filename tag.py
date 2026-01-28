from PicImageSearch import Iqdb
import asyncio
import re

iqdb = Iqdb()


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


if __name__ == "__main__":
    tags, rating, link = asyncio.run(find_image('0c11e9702d96d2c40401fbd9c8d5e7f9.jpg', 85))
    if not tags:
        tags = asyncio.run(tag_interrogate('0c11e9702d96d2c40401fbd9c8d5e7f9.jpg'))
    