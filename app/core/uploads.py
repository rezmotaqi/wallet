"""
Functions for uploads
"""

import os
from typing import Dict, Tuple, Any

import aiofiles.os
from PIL import Image
from fastapi import UploadFile

from app.config.settings import settings


def create_thumbnail(path: str, size: Dict[str, Tuple[int, int]]) -> Any:
    """
    creates a thumbnail from the given image path and saves it
    """
    if not os.path.exists(f"{settings.MEDIA_DIR}{list(size.keys())[0]}/{path.split('/')[0]}/"):
        os.makedirs(f"{settings.MEDIA_DIR}{list(size.keys())[0]}/{path.split('/')[0]}/")
    try:
        image = Image.open(f"{settings.MEDIA_DIR}/{path.split('/')[0]}/{path.split('/')[1]}")
        # file_format = path.split(".")[-1]
        new_path = f"{settings.MEDIA_DIR}{list(size.keys())[0]}/{path.split('/')[0]}/{path.split('/')[1]}"
        image.thumbnail(list(size.values())[0])

        # thumb_io = BytesIO()
        image.save(new_path)
        # thumb_io.seek(0)

        # async with aiofiles.open(new_path, 'wb') as out_file:
        #     content = thumb_io.read()
        #     await out_file.write(content)
        # thumb_io.close()

    except IOError:
        pass


async def get_magic_bytes(file: UploadFile) -> Any:
    """
    returns the first 32 bits of the current file and sets file cursor at 0 position
    """
    magic_bytes = await file.read(4096)
    await file.seek(0)
    return magic_bytes


async def move_image_from_temp(image_path: str):
    old_path = f"{settings.MEDIA_DIR}tmp/{image_path}"
    new_path = f"{settings.MEDIA_DIR}{image_path}"
    try:
        await aiofiles.os.replace(old_path, new_path)
        return image_path
    except Exception as e:
        print(e)
        return image_path
