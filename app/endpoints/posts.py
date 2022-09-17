"""
Posts endpoints and views.

Route: "/posts"
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Any, List

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from starlette import status
from starlette.background import BackgroundTasks

from app.config.settings import settings
from app.core import depends
from app.core.posts import (
    increment_posts_hits,
)
from app.core.uploads import move_image_from_temp
from app.schemas.base import ObjectId, DateOrderBy
from app.schemas.general import (
    OperationResponse,
    NotificationCategory,
)
from app.schemas.posts import (
    PostsStatus,
    PostCategoryCreate,
    PostCategoryListOut,
    PostCategoryOut,
    PostsCreate,
    PostsListOut,
    PostsOut,
    PostsAdminOut,
    PostsUpdate,
    PostsPartialUpdate,
    PostsListAdminOut,
    AuthorInPost
)
from app.schemas.users import User

router = APIRouter()

"""
Posts endpoints

Route: /posts
"""


@router.post('')
async def admin_create_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        data: PostsCreate
):
    """
    Admin

    Create post

    Authorization: Required
    """

    now = datetime.now()
    insert_result = await db.posts.insert_one(
        {**data.dict(), 'created_at': now, 'updated_at': now, 'owner_id': current_user.id}
    )
    if not insert_result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create post."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('', response_model=PostsListOut)
async def get_post_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
) -> PostsListOut:
    """
    User

    Get posts for user

    Authorization: Not required
    """
    result = await db.posts.find({}, {}).skip(offset * limit).to_list(length=limit)
    posts = list(map(lambda x: (PostsOut.parse_obj({**x, 'id': x.get('_id')})), result))
    count = await db.posts.count_documents({})
    return PostsListOut(count=count, posts=posts)


@router.post('/like/{post_id}')
async def like_or_dislike_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        post_id: ObjectId,
        action: bool
):
    """
    User

    Like or Dislike post, action=True ==> like & action=False ==> dislike

    Authorization: Required
    """
    result = None

    if action:

        user_result = await db.users.find_one(
            {'_id': current_user.id},
            {'basic_info.first_name': 1, 'basic_info.last_name': 1, 'basic_info.avatar': 1}
        )

        result = await db.posts.find_one_and_update(
            {'_id': post_id, 'likes': {'$ne': current_user.id}},
            {'$inc': {'like_count': 1}, '$addToSet': {'likes': current_user.id}},
            projection={'user': 1, 'body': 1, 'owner_id': 1}
        )

        if result:
            notification = {
                'owner_id': result.get('owner_id'),
                'category': NotificationCategory.LIKE.value,
                'extra_data': {
                    "user":
                        {
                            "first_name": user_result.get("basic_info").get('first_name')
                            if user_result.get("basic_info") else None,
                            "last_name": user_result.get("basic_info").get('last_name')
                            if user_result.get("basic_info") else None,
                            "avatar": user_result.get("basic_info").get('avatar')
                            if user_result.get("basic_info") else None
                        },
                    "post_text": result.get("body"),
                    "post_images": result.get('images'),
                    "post_id": result.get('_id')
                },
                'actionable': False,
                'created_at': datetime.now(),
                'seen': False
            }

            notif_result = await db.notifications.insert_one(notification)

    else:
        result = await db.posts.update_one(
            {'_id': post_id, 'likes': current_user.id},
            {'$inc': {'like_count': -1}, '$pull': {'likes': current_user.id}},
        )

    return Response(status_code=status.HTTP_200_OK)


@router.post('/admin/category')
async def create_post_category(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        data: PostCategoryCreate
):
    """
    Admin

    Create post category

    Authorization: Required
    """
    data = {**data.dict(), 'created_at': datetime.now(), 'admin_id': current_user.id}
    try:
        result = await db.post_categories.insert_one(data)
        if not result.acknowledged:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not create category. "
            )
    except DuplicateKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category already exists. "
        ) from e

    return Response(status_code=status.HTTP_201_CREATED)


@router.get('/admin', response_model=PostsListAdminOut)
async def admin_get_post_list(
    *, db: AsyncIOMotorDatabase = Depends(depends.get_database),
    current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
    search_field: Optional[str] = None,
    from_date: Optional[datetime] = datetime(2000, 1, 1, 0, 0, 0, 0),
    to_date: Optional[datetime] = None, sort: Optional[DateOrderBy] = "-created_at",
    post_status: Optional[PostsStatus] = None,
    limit: Optional[int] = 20,
    offset: Optional[int] = 0,

) -> PostsListAdminOut:
    """
    Admin

    Get list of posts, search_field searches in these fields: [username, post_body and post_title]

    Authorization: Required
    """
    if not to_date:
        to_date = datetime.now()
    query = {"created_at": {"$gte": from_date, "$lte": to_date}}
    if post_status:
        query['status'] = post_status

    if search_field:
        search = {
            "$or": [{"user.username": {'$regex': search_field}},
                    {"body": {'$regex': search_field}}, {"title": {'$regex': search_field}}]}

        query |= search
    sort = {sort: 1} if sort[0] != "-" else {sort[1:]: -1}
    result = await db.posts.find(
        {"$query": query, "$orderby": sort},
        {'owner_id': 1, 'title': 1, 'tags': 1, 'body': 1, 'post_type': 1, 'privacy': 1, 'created_at': 1,
         'status': 1, 'hits': 1, 'like_count': 1, 'comments_count': 1, 'poll_choices': 1,
         'poll_expiration': 1, 'poll_status': 1, 'poll_type': 1, 'poll_vote_count': 1,
         'images': 1, 'video': 1, 'category': 1, 'user': 1}
    ).skip(offset * limit).to_list(length=limit)

    posts = list(map(lambda x: PostsAdminOut.parse_obj_id({**x, 'user': AuthorInPost.parse_obj(x.get('user'))}), result))
    count = await db.posts.count_documents(query)
    return PostsListAdminOut(count=count, posts=posts)


@router.get('/categories', response_model=PostCategoryListOut)
async def get_category_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
) -> PostCategoryListOut:
    """
    User

    Get post categories

    Authorization: Required
    """
    result = await db.post_categories.find({}, {'name': 1}).skip(offset * limit).to_list(length=limit)
    category_list = list(map(lambda x: (PostCategoryOut.parse_obj_id({**x})), result))
    count = await db.post_categories.count_documents({})
    return PostCategoryListOut(count=count, category_list=category_list)


@router.get('/admin/{post_id}', response_model=PostsAdminOut)
async def admin_get_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        post_id: ObjectId,
) -> PostsAdminOut:
    """
    Admin

    Get post

    Authorization: Required
    """
    result = await db.posts.find_one({'_id': post_id})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found. "
        )
    return PostsAdminOut.parse_obj(
        {**result, 'id': post_id}
    )


@router.get('/{post_id}', response_model=PostsOut)
async def get_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        post_id: ObjectId,
        background_task: BackgroundTasks
) -> PostsOut:
    """
    User

    Get post

    Authorization: Required
    """
    result = await db.posts.find_one({'_id': post_id, 'owner_id': current_user.id})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )

    background_task.add_task(increment_posts_hits, db, [post_id])

    return PostsOut.parse_obj(
        {**result, 'id': post_id}
    )


@router.put('/{post_id}')
async def admin_update_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        data: PostsUpdate,
        post_id: ObjectId
):
    """
    Admin

    Update post

    Authorization: Required
    """

    now = datetime.now()
    data = data.dict(exclude_defaults=True)

    post = await db.posts.find_one({'_id': post_id, 'owner_id': current_user.id}, {'post_type': 1})
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found. "
        )

    data = {**data, 'updated_at': now} if data else {'updated_at': now}

    result = await db.posts.find_one_and_update(
        {'_id': post_id, 'owner_id': current_user.id}, {'$set': data},
        return_document=ReturnDocument.AFTER,
        projection=
        {},
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=OperationResponse.UNSUCCESSFUL_UPDATE
        )

    # TODO handle moving image

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/{post_id}')
async def admin_partial_update_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        data: PostsPartialUpdate,
        post_id: ObjectId
):
    """
    Admin

    Partial Update post

    Authorization: Required
    """

    now = datetime.now()
    data = data.dict(exclude_unset=True)

    post = await db.posts.find_one({'_id': post_id, 'owner_id': current_user.id}, {'post_type': 1})
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found. "
        )

    data = {**data, 'updated_at': now}
    result = await db.posts.find_one_and_update(
        {'_id': post_id, 'owner_id': current_user.id},
        {'$set': data},
        projection=
        {},
        return_document=ReturnDocument.AFTER
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=OperationResponse.UNSUCCESSFUL_UPDATE
        )

    # if post_type == PostsType.IMAGE_POST.value and images:
    #     for path in images:
    #         await move_image_from_temp(path)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete('/{post_id}')
async def admin_delete_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        post_id: ObjectId
) -> Response:
    """
    Admin

    Delete post

    Authorization: Required
    """

    result = await db.posts.find_one_and_delete({'_id': post_id, 'owner_id': current_user.id})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not delete object. "
        )

    if result.get('image'):
        try:
            image_list = result.get('images')
            for image in image_list:
                path = os.path.join(settings.MEDIA_DIR, image)
                await aiofiles.os.remove(path)
        except Exception as e:
            print(e)
            # TODO log that file has not been deleted

    return Response(status_code=status.HTTP_204_NO_CONTENT)
