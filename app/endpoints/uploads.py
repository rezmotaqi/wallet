"""
Uploads endpoints and views.

Route: "/uploads"
"""

import os
import uuid
from tempfile import NamedTemporaryFile
from typing import Any, Union, IO

import aiofiles
import aiofiles.os
import magic
from fastapi import (
    File,
    status,
    Depends,
    APIRouter,
    UploadFile,
    HTTPException,
    Response,
    Query
)
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.config.settings import settings
from app.core import depends
from app.core.uploads import get_magic_bytes
from app.schemas.base import ObjectId
from app.schemas.exceptions import Message
from app.schemas.uploads import Upload, ImageType, PortfolioImageType, UploadImage
from app.schemas.users import User, UserAvatarOut, UserCoverOut

router = APIRouter()


@router.post('/images', response_model=UploadImage)
async def upload_images(
        image_type: PortfolioImageType = Query(..., alias="collection"),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        files: list[UploadFile] = File(..., max_items=20, alias="files[]"),
) -> Any:
    """
    User
    Authorization: Required
    """

    accepted_list, error_list, paths = [], [], []
    for file in files:
        magic_bytes = await get_magic_bytes(file)
        if (file.content_type not in settings.ALLOWED_IMAGE_TYPES) or \
                (file.content_type != magic.from_buffer(magic_bytes, mime=True)):
            error_list.append(file.filename)
        else:
            accepted_list.append(file)

    temp_dir = "tmp"

    if not os.path.exists(f"{settings.MEDIA_DIR}{temp_dir}/{image_type}/{current_user.id}/images"):
        os.makedirs(f"{settings.MEDIA_DIR}{temp_dir}/{image_type}/{current_user.id}/images")

    if not os.path.exists(f"{settings.MEDIA_DIR}{image_type}/{current_user.id}/images"):
        os.makedirs(f"{settings.MEDIA_DIR}{image_type}/{current_user.id}/images")

    for file in accepted_list:

        file_format = file.filename.split(".")[-1]
        file_format = "jpeg" if file_format == "jpg" else file_format
        file.filename = f"{uuid.uuid4()}.{file_format}"
        file_path = f"{settings.MEDIA_DIR}{temp_dir}/{image_type}/{current_user.id}/images/{file.filename}"

        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            if len(content) > 3 * (10 ** 6):
                error_list.append(file.filename)
            else:
                await out_file.write(content)

        paths.append(f"{image_type}/{current_user.id}/images/{file.filename}")

    if error_list:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"images": paths, "status": False, "message": f"{error_list} these images failed to be uploaded"}
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"images": paths, "status": True, "message": "Images uploaded successfully"}
    )


@router.post("", responses={400: {"model": Message}})
async def upload_user_image(
        *,
        file: UploadFile = File(...),
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        user: User = Depends(depends.permissions(["authenticated"])),
        image_type: ImageType
) -> Any:
    """
    Uploads new avatar or cover image and creates image thumbnails.

    Authorization: Required
    """

    magic_bytes = await get_magic_bytes(file)
    if (file.content_type not in settings.ALLOWED_IMAGE_TYPES) or \
            (file.content_type != magic.from_buffer(magic_bytes, mime=True)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{file.content_type} is not a valid image type"
        )

    if not os.path.exists(f"{settings.MEDIA_DIR}{image_type}/{user.id}"):
        os.makedirs(f"{settings.MEDIA_DIR}{image_type}/{user.id}")

    file_format = file.filename.split(".")[-1]
    file.filename = f"{image_type}.{file_format}"

    processed_path = f"{image_type}/{user.id}/{file.filename}"
    file_path = f"{settings.MEDIA_DIR}{processed_path}"

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    await db.users.update_one(
        {"_id": user.id},
        {"$set": {f"basic_info.{image_type}": processed_path}}
    )
    return Upload(filename=processed_path)


@router.get("", response_model=Union[UserAvatarOut, UserCoverOut], responses={404: {"model": Message}})
async def get_user_image(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        user: User = Depends(depends.permissions(["authenticated"])),
        image_type: ImageType
) -> Any:
    """
    Get user avatar or cover.

    Authorization: Required
    """
    result = await db.users.find_one({"username": user.username}, {"basic_info": 1})
    image = result.get("basic_info").get(f"{image_type}") if result.get("basic_info") else ""
    return {f"{image_type}": image}


@router.delete("")
async def delete_user_image(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        image_type: ImageType
):
    """
    Delete avatar

    Authorization: Required
    """

    result = await db.users.find_one_and_update(
        {'_id': current_user.id},
        {'$unset': {f'basic_info.{image_type}': None}},
        projection={f'basic_info.{image_type}': 1},
        return_document=ReturnDocument.BEFORE
    )
    try:
        image_path = result.get('basic_info').get(image_type)
        path = os.path.join(settings.MEDIA_DIR, image_path)
        await aiofiles.os.remove(path)
    except Exception as e:
        print(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/admin/{user_id}")
async def admin_delete_user_image(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        image_type: ImageType,
        user_id: ObjectId
):
    """
    Admin

    Delete User cover or avatar

    Authorization: Required
    """

    result = await db.users.find_one_and_update(
        {'_id': user_id},
        {'$unset': {f'basic_info.{image_type}': None}},
        projection={f'basic_info.{image_type}': 1},
        return_document=ReturnDocument.BEFORE
    )
    try:
        image_path = result.get('basic_info').get(image_type)
        path = os.path.join(settings.MEDIA_DIR, image_path)
        await aiofiles.os.remove(path)
    except Exception as e:
        # TODO add logging
        print(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete('/portfolio')
async def delete_experience_company_logo(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        object_id: ObjectId,
        image_type: PortfolioImageType
):
    """
    Delete work experience image

    Authorization: Required
    """

    result = await db[image_type].find_one_and_update(
        {'_id': object_id, "owner_id": current_user.id},
        {'$unset': {"logo" if image_type == PortfolioImageType.COMPANY_LOGO else "image": None}},
        projection={"logo" if image_type == PortfolioImageType.COMPANY_LOGO else "image": 1},
        return_document=ReturnDocument.BEFORE
    )

    try:
        company_logo_path = result.get("logo" if image_type == PortfolioImageType.COMPANY_LOGO else "image")
        path = os.path.join(settings.MEDIA_DIR, company_logo_path)
        await aiofiles.os.remove(path)
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='File could not be deleted.'
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/post/video')
async def upload_video(
        user: User = Depends(depends.permissions(["authenticated"])),
        file: UploadFile = File(...)
):

    """
    Upload video for video_post or article
    """

    magic_bytes = await get_magic_bytes(file)
    if (file.content_type not in settings.ALLOWED_VIDEO_TYPES) or \
            (file.content_type != magic.from_buffer(magic_bytes, mime=True)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{file.content_type} is not a valid video type"
        )

    real_file_size = 0
    temp: IO = NamedTemporaryFile(delete=False)
    for chunk in file.file:
        real_file_size += len(chunk)
        if real_file_size > settings.ARTICLE_VIDEO_MAX_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is Too large"
            )
        temp.write(chunk)

    temp.close()
    await file.seek(0)

    if not os.path.exists(f"{settings.MEDIA_DIR}posts/{user.id}/videos"):
        os.makedirs(f"{settings.MEDIA_DIR}posts/{user.id}/videos")

    file_format = file.filename.split(".")[-1]
    file.filename = f"{uuid.uuid4()}.{file_format}"
    file_path = f"{settings.MEDIA_DIR}posts/{user.id}/videos/{file.filename}"

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    processed_path = f"posts/{user.id}/videos/{file.filename}"

    return Upload(filename=processed_path)


@router.post('/events/{event_id}', response_model=UploadImage)
async def upload_event_media(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        files: list[UploadFile] = File(..., max_items=20, alias="files[]")
):
    """
    Upload media for events
    """

    event_data = await db.events.find_one({"owner_id": current_user.id, "_id": event_id}, {"_id": 1})
    if not event_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not upload media on this event"
        )

    accepted_list, error_list, paths = [], [], []
    for file in files:
        magic_bytes = await get_magic_bytes(file)
        if (file.content_type not in settings.ALLOWED_IMAGE_TYPES and file.content_type not in
            settings.ALLOWED_FILE_TYPES) or (file.content_type != magic.from_buffer(magic_bytes, mime=True)):
            error_list.append(file.filename)
        else:
            accepted_list.append(file)

    temp_dir = "tmp"

    if not os.path.exists(f"{settings.MEDIA_DIR}{temp_dir}/events/{event_id}/{current_user.id}/files"):
        os.makedirs(f"{settings.MEDIA_DIR}{temp_dir}/events/{event_id}/{current_user.id}/files")

    if not os.path.exists(f"{settings.MEDIA_DIR}events/{event_id}/{current_user.id}/files"):
        os.makedirs(f"{settings.MEDIA_DIR}events/{event_id}/{current_user.id}/files")

    for file in accepted_list:

        file_format = file.filename.split(".")[-1]
        file_format = "jpeg" if file_format == "jpg" else file_format
        file.filename = f"{uuid.uuid4()}.{file_format}"
        file_path = f"{settings.MEDIA_DIR}{temp_dir}/events/{event_id}/{current_user.id}/files/{file.filename}"

        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            if len(content) > 10 * (10 ** 6):
                error_list.append(file.filename)
            else:
                await out_file.write(content)

        paths.append(f"events/{event_id}/{current_user.id}/files/{file.filename}")

    if error_list:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"images": paths, "status": False, "message": f"{error_list} these images failed to be uploaded"}
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"images": paths, "status": True, "message": "Images uploaded successfully"}
    )
