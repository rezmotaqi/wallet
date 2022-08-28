"""
Posts endpoints and views.

Route: "/posts"
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Any, List

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Body, Response, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from starlette import status
from starlette.background import BackgroundTasks

from app.config.settings import settings
from app.core import depends
from app.core.posts import (
    increment_posts_hits,
    check_required_fields,
    POLL_POST_UPDATE_REQUIRED_FIELDS,
    POLL_POST_UPDATE_PERMITTED_FIELDS,
    ARTICLE_UPDATE_PERMITTED_FIELDS,
    ARTICLE_UPDATE_REQUIRED_FIELDS,
    TEXT_POST_UPDATE_PERMITTED_FIELDS,
    TEXT_POST_UPDATE_REQUIRED_FIELDS,
    IMAGE_POST_UPDATE_PERMITTED_FIELDS,
    IMAGE_POST_UPDATE_REQUIRED_FIELDS,
    VIDEO_POST_UPDATE_PERMITTED_FIELDS,
    VIDEO_POST_UPDATE_REQUIRED_FIELDS,
    POLL_POST_PARTIAL_UPDATE_PERMITTED_FIELDS,
    ARTICLE_PARTIAL_UPDATE_PERMITTED_FIELDS,
    TEXT_POST_PARTIAL_UPDATE_PERMITTED_FIELDS,
    IMAGE_POST_PARTIAL_UPDATE_PERMITTED_FIELDS,
    VIDEO_POST_PARTIAL_UPDATE_PERMITTED_FIELDS,
    remove_unnecessary_fields,
)
from app.core.uploads import move_image_from_temp
from app.schemas.base import ObjectId, DateOrderBy
from app.schemas.general import (
    ConnectionStatus,
    OperationResponse,
    NotificationCategory,
    UserType
)
from app.schemas.posts import (
    UserPostsOut,
    UserPostsCreate,
    UserPostsListOut,
    FeedUserOut,
    FeedUserListOut,
    Comment,
    UserPostsPartialUpdate,
    PostsStatus,
    PostsType,
    PollType,
    PostsPrivacySetting,
    CommentStatus,
    PostCategoryCreate,
    PostCategoryListOut,
    PostCategoryOut,
    PollStatus,
    UserPostUpdate,
    UserPostsListAdminOut,
    UserPostsAdminOut,
    UserAdminOut,
    UserNestedInPost,
    ReportCollection
)
from app.schemas.users import User

router = APIRouter()

"""
Posts endpoints

Route: /posts
"""


@router.post('')
async def create_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: UserPostsCreate
):
    """
    User

    Create post

    Authorization: Required
    """

    if data.post_type == PostsType.IMAGE_POST.value and not data.images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Images are not sent. "
        )

    now = datetime.now()
    user_result = await db.users.find_one(
        {"_id": current_user.id},
        {
            "_id": 1,
            "username": 1,
            "user_type": 1,
            "basic_info.first_name": 1,
            "basic_info.last_name": 1,
            "basic_info.avatar": 1,
            "basic_info.cover": 1,
            "basic_info.headline": 1,
            "basic_info.company_name": 1
        }
    )
    if not user_result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login"
        )

    user = {
        'id': user_result.get('_id'),
        'avatar': user_result.get('basic_info').get('avatar') if user_result.get('basic_info') else None,
        'cover': user_result.get('basic_info').get('cover') if user_result.get('basic_info') else None,
        'headline': user_result.get('basic_info').get('headline') if user_result.get('basic_info') else None,
        'username': user_result.get('username'),
        'user_type': user_result.get('user_type')
    }

    if user_result.get('user_type') == UserType.NORMAL.value:
        user = {
            **user,
            'first_name': user_result.get('basic_info').get('first_name') if user_result.get('basic_info') else None,
            'last_name': user_result.get('basic_info').get('last_name') if user_result.get('basic_info') else None,
        }
    elif user_result.get('user_type') == UserType.COMPANY.value:
        user = {
            **user,
            'company_name': user_result.get('basic_info').get('company_name') if user_result.get(
                'basic_info') else None,
        }

    extra_data = {
        'created_at': now,
        'updated_at': now,
        'owner_id': current_user.id,
        'status': PostsStatus.ACTIVE.value,
        'user': user,
        'hits': 0,
        'like_count': 0
    }
    data = data.dict(exclude_unset=True)
    if data.get('post_type') == PostsType.POLL_POST:
        for choice in data.get('poll_choices'):
            choice['choice_id'] = str(uuid.uuid4())
            choice['votes'] = []
            choice['vote_count'] = 0

        data['poll_status'] = PollStatus.OPEN
        data['poll_vote_count'] = 0

    data = {**data, **extra_data}

    result = await db.posts.insert_one(data)
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create post. "
        )

    if data.get("post_type") == PostsType.IMAGE_POST.value:
        for path in data.get("images"):
            await move_image_from_temp(path)

    return FeedUserOut.parse_obj({**data, 'id': result.inserted_id})


@router.get('', response_model=UserPostsListOut, response_model_exclude_none=True)
async def get_post_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
) -> UserPostsListOut:
    """
    User

    Get user posts for user

    Authorization: Required
    """
    result = await db.posts.find(
        {'owner_id': current_user.id},
        {
            'owner_id': 1,
            'title': 1,
            'tags': 1,
            'body': 1,
            'post_type': 1,
            'privacy': 1,
            'created_at': 1,
            'updated_at': 1,
            'status': 1,
            'hits': 1,
            'like_count': 1,
            'poll_choices': 1,
            'poll_expiration': 1,
            'poll_status': 1,
            'poll_type': 1,
            'poll_vote_count': 1,
            'images': 1,
            'video': 1,
            'category': 1
        }
    ).skip(offset * limit).to_list(length=limit)
    posts = list(map(lambda x: (UserPostsOut.parse_obj({**x, 'id': x.get('_id')})), result))
    count = await db.posts.count_documents({'owner_id': current_user.id})
    return UserPostsListOut(count=count, posts=posts)


@router.post('/vote/{post_id}')
async def vote_on_poll_post(
    db: AsyncIOMotorDatabase = Depends(depends.get_database),
    current_user: User = Depends(depends.permissions(["authenticated"])),
    post_id: ObjectId = Query(Ellipsis),
    new_choice_ids: List[str] = Body(Ellipsis, embed=True)
):
    """
    User

    Vote on poll_post with choice_id, if poll_type is MULTI, user can vote multiple choices, if its SINGLE, user
    can only vote one choice and the previous choice will be deleted if this api is called.

    Authorization: Required
    """
    if not new_choice_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No new choice_id is provided.")

    vote_result = await db.posts.find_one(
        {'_id': post_id, 'post_type': PostsType.POLL_POST},
        {'poll_choices': 1, 'poll_vote_count': 1, 'poll_type': 1, 'poll_expiration': 1}
    )

    if not vote_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poll not found")

    if vote_result.get('poll_expiration') < datetime.now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Poll has expired")

    poll_choices = vote_result.get('poll_choices')
    poll_vote_count = vote_result.get('poll_vote_count')
    if vote_result.get('poll_type') == PollType.SINGLE:
        if len(new_choice_ids) > 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="poll_type = single only accepts one choice_id.")

        for index, item in enumerate(poll_choices):
            if current_user.id in item.get('votes'):
                poll_choices[index].get('votes').remove(current_user.id)
                poll_choices[index]['vote_count'] -= 1
                poll_vote_count -= 1
            if str(item.get('choice_id')) == new_choice_ids[0]:
                poll_choices[index]['votes'].append(current_user.id)
                poll_choices[index]['vote_count'] += 1
                poll_vote_count += 1
    elif vote_result.get('poll_type') == PollType.MULTI:
        for index, item in enumerate(poll_choices):
            if current_user.id in item.get('votes'):
                poll_choices[index].get('votes').remove(current_user.id)
                poll_choices[index]['vote_count'] -= 1
                poll_vote_count -= 1
            if str(item.get('choice_id')) in new_choice_ids:
                poll_choices[index]['votes'].append(current_user.id)
                poll_choices[index]['vote_count'] += 1
                poll_vote_count += 1
    post = await db.posts.find_one_and_update(
        {'_id': post_id},
        {'$set': {'poll_choices': poll_choices, 'poll_vote_count': poll_vote_count}},
        return_document=ReturnDocument.AFTER,
        projection={
            'owner_id': 1,
            'body': 1,
            'post_type': 1,
            'privacy': 1,
            'created_at': 1,
            'hits': 1,
            'like_count': 1,
            'poll_choices': 1,
            'poll_expiration': 1,
            'poll_status': 1,
            'poll_type': 1,
            'poll_vote_count': 1, 
            'user': 1,
            'comment': 1,
            'comments_count': 1,
            'likes': 1,
            'reports': 1
        })

    if post.get('post_type') == PostsType.POLL_POST:
        for j, choice in enumerate(post.get('poll_choices')):
            if current_user.id in choice.get('votes'):
                post['poll_choices'][j].pop('votes')
                post['poll_choices'][j] = {**choice, 'voted': True}
            else:
                post['poll_choices'][j].pop('votes')
                post['poll_choices'][j] = {**choice, 'voted': False}
    post = {
        **post,
        'is_liked': current_user.id in (post.get("likes") or []),
        'is_reported': current_user.id in (post.get('reports') or []),
        'comment': [post.get("comment")] if post.get("comment") else [],
    }

    return FeedUserOut.parse_obj({**post, 'id': post.get('_id')})


@router.get('/feed', response_model=FeedUserListOut)
async def get_feed(
        *, db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        background_task: BackgroundTasks, offset: Optional[int] = 0,
        limit: Optional[int] = 20
) -> FeedUserListOut:
    """
    User

    Get user feed

    Authorization: Required
    """
    friends_raw_result = await db.friends.find({
        '$or': [{'requested_id': current_user.id}, {'requester_id': current_user.id}],
        'status': ConnectionStatus.CONNECTED}).to_list(length=None)

    friends_list = []
    if friends_raw_result:
        for friend in friends_raw_result:
            if friend.get('requester_id') == current_user.id:
                friends_list.append(friend.get('requested_id'))
            elif friend.get('requested_id') == current_user.id:
                friends_list.append(friend.get('requester_id'))
    result = await db.posts.find(
        {'$query': {'$or':
            [{'privacy': PostsPrivacySetting.PUBLIC},
             {'owner_id': {"$in": friends_list}, 'privacy': PostsPrivacySetting.PRIVATE},
             {'privacy': PostsPrivacySetting.ONLY_ME,'owner_id': current_user.id},
             {'privacy': PostsPrivacySetting.PRIVATE, 'owner_id': current_user.id}]},
         '$orderby': {'created_at': -1}},
        {'user': 1, 'comment': 1, 'comments_count': 1, 'owner_id': 1, 'title': 1, 'tags': 1, 'body': 1, 'post_type': 1,
         'privacy': 1, 'created_at': 1, 'updated_at': 1, 'hits': 1, 'like_count': 1, 'likes': 1,
         'status': 1, 'poll_choices': 1, 'poll_expiration': 1, 'poll_status': 1, 'poll_type': 1,
         'poll_vote_count': 1, 'video': 1, 'images': 1, 'category': 1}
        ).skip(offset * limit).to_list(length=limit)

    for i, post in enumerate(result):
        if post.get('post_type') == PostsType.POLL_POST:
            for j, choice in enumerate(post.get('poll_choices')):
                if current_user.id in choice.get('votes'):
                    result[i]['poll_choices'][j].pop('votes')
                    result[i]['poll_choices'][j] = {**choice, 'voted': True}
                else:
                    result[i]['poll_choices'][j].pop('votes')
                    result[i]['poll_choices'][j] = {**choice, 'voted': False}
    posts = list(map(lambda x: FeedUserOut.parse_obj(
        {**x, 'poll_vote_count': x.get("poll_vote_count"),
         'comment': [x.get("comment")] if x.get("comment") else [],
         'id': x.get('_id'), 'is_liked': current_user.id in x.get('likes'),
         'is_reported': current_user.id in x.get('reports')}
        ),
        map(lambda x: {**x, "likes": x.get('likes') or [], "reports": x.get('reports') or []}, result))
    )

    object_ids = list(map(lambda x: x.get('_id'), result))
    background_task.add_task(increment_posts_hits, db, object_ids)
    count = await db.posts.count_documents(
        {'$or': [
            {'privacy': PostsPrivacySetting.PUBLIC},
            {'owner_id': {"$in": friends_list}, 'privacy': PostsPrivacySetting.PRIVATE},
            {'privacy': PostsPrivacySetting.ONLY_ME, 'owner_id': current_user.id},
            {'privacy': PostsPrivacySetting.PRIVATE, 'owner_id': current_user.id}]})

    return FeedUserListOut(count=count, posts=posts)


@router.get('/get_one_feed/{post_id}')
async def get_one_post_feed(
        *, db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        post_id: ObjectId
):
    """
    User

    Get one post that is in user's feed

    Authorization: Required
    """
    friends_raw_result = await db.friends.find(
        {'$or': [{'requested_id': current_user.id}, {'requester_id': current_user.id}],
         'status': ConnectionStatus.CONNECTED}
    ).to_list(length=None)

    friends_list = []
    if friends_raw_result:
        for friend in friends_raw_result:
            if friend.get('requester_id') == current_user.id:
                friends_list.append(friend.get('requested_id'))
            elif friend.get('requested_id') == current_user.id:
                friends_list.append(friend.get('requester_id'))
    result = await db.posts.find_one(
        {'$query': {
            '$or': [
                {'_id': post_id, 'privacy': PostsPrivacySetting.PUBLIC},
                {'_id': post_id, 'owner_id': {"$in": friends_list}, 'privacy': PostsPrivacySetting.PRIVATE},
                {'_id': post_id, 'privacy': PostsPrivacySetting.ONLY_ME, 'owner_id': current_user.id},
                {'_id': post_id, 'privacy': PostsPrivacySetting.PRIVATE, 'owner_id': current_user.id}
            ]}, '$orderby': {'created_at': -1}
         },
        {'user': 1, 'comment': 1, 'comments_count': 1, 'owner_id': 1, 'title': 1, 'tags': 1, 'body': 1, 'post_type': 1,
         'privacy': 1, 'created_at': 1, 'updated_at': 1, 'hits': 1, 'like_count': 1, 'likes': 1, 'status': 1,
         'poll_choices': 1, 'poll_expiration': 1, 'poll_status': 1, 'poll_type': 1, 'poll_vote_count': 1, 'video': 1,
         'images': 1, 'category': 1}
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="You do not have access to this post.")

    if result.get('post_type') == PostsType.POLL_POST:
        for j, choice in enumerate(result.get('poll_choices')):
            if current_user.id in choice.get('votes'):
                result['poll_choices'][j].pop('votes')
                result['poll_choices'][j] = {**choice, 'voted': True}
            else:
                result['poll_choices'][j].pop('votes')
                result['poll_choices'][j] = {**choice, 'voted': False}
    result = {**result, "likes": result.get('likes') or [], "reports": result.get('reports') or []}
    return FeedUserOut.parse_obj(
        {**result, 'poll_vote_count': result.get("poll_vote_count"),
         'comment': [result.get("comment")] if result.get("comment") else [],
         'id': result.get('_id'),
         'is_liked': current_user.id in result.get('likes'),
         'is_reported': current_user.id in result.get('reports')}
    )


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


@router.post('/report/{entity_id}', status_code=status.HTTP_200_OK)
async def report_post_or_comment(
        *, db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        entity_id: ObjectId,
        collection: ReportCollection,
):
    """
    Report post or comment
    """

    result = await db[collection].update_one(
        {'_id': entity_id, 'reports': {'$ne': current_user.id}},
        {
            '$addToSet': {'reports': current_user.id},
            '$set': {'status': PostsStatus.REPORTED.value}
        }
    )

    if result and result.matched_count > 0:
        await db[collection].update_one({'_id': entity_id}, {'$inc': {'report_count': 1}})

    return {'message': "Successfully reported."}


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


@router.delete('/admin')
async def admin_delete_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        post_ids: List[ObjectId]
) -> Response:
    """
    Admin

    Delete post

    Authorization: Required
    """

    posts = await db.posts.find({'_id': {'$in': post_ids}}, {'image': 1, 'video': 1}).to_list(length=None)

    for post in posts:
        if post.get('image'):
            if post.get('image'):
                try:
                    image_list = post.get('images')
                    for image in image_list:
                        path = os.path.join(settings.MEDIA_DIR, image)
                        await aiofiles.os.remove(path)
                except Exception as e:
                    print(e)
                    # TODO add logging

        elif post.get('video'):
            if post.get('video'):
                try:
                    video_path = post.get('video')
                    path = os.path.join(settings.MEDIA_DIR, video_path)
                    await aiofiles.os.remove(path)
                except Exception as e:
                    print(e)
                    # TODO add logging

    result = await db.posts.delete_many({'_id': {'$in': post_ids}})
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not delete objects. "
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/admin', response_model=UserPostsListAdminOut)
async def admin_get_post_list(
    *, db: AsyncIOMotorDatabase = Depends(depends.get_database),
    current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
    search_field: Optional[str] = None,
    from_date: Optional[datetime] = datetime(2000, 1, 1, 0, 0, 0, 0),
    to_date: Optional[datetime] = None, sort: Optional[DateOrderBy] = "-created_at",
    post_status: Optional[PostsStatus] = None, post_type: Optional[PostsType] = None,
    user_id: Optional[ObjectId] = None, offset: Optional[int] = 0,
    limit: Optional[int] = 20
) -> UserPostsListAdminOut:
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
    if post_type:
        query['post_type'] = post_type
    if user_id:
        query['owner_id'] = user_id
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

    posts = list(map(lambda x: UserPostsAdminOut.parse_obj_id({**x, 'user': UserAdminOut.parse_obj(x.get('user'))}), result))
    count = await db.posts.count_documents(query)
    return UserPostsListAdminOut(count=count, posts=posts)


@router.get('/admin/comments', response_model=List[Comment])
async def admin_get_post_comments(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        post_id: Optional[ObjectId] = Query(None),
        parent: Optional[ObjectId] = Query(None),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20
) -> Any:
    """
    Admin

    Get comment

    Authorization: Required
    """

    # query = {"status": CommentStatus.PENDING.value}
    query = {}
    if post_id:
        query["post_id"] = post_id
    if parent:
        query["parent"] = {"$in": [parent]}
    comments = await db.comments.find(
        {"$query": query, "$orderby": {"created_at": 1}}
    ).skip(offset * limit).to_list(length=limit)
    comments = list(map(lambda x: Comment.parse_obj({**x, "id": x.get("_id")}), comments))
    return comments


@router.patch('/admin/comments')
async def admin_partial_update_comments_batch(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        comment_ids: List[ObjectId] = Query(..., alias="comment_ids[]"),
        comment_status: CommentStatus = Query(..., alias="status")
) -> Any:
    """
    Admin

    Edit comment

    Authorization: Required
    """

    await db.comments.update_many(
        {"_id": {"$in": comment_ids}},
        {"$set": {"updated_at": datetime.now(), "status": comment_status}}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/comments')
async def partial_update_post_comment(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        comment_id: ObjectId,
        text: str = Body(..., embed=True, alias="comment")
) -> Any:
    """
    User

    Edit comment

    Authorization: Required
    """

    result = await db.comments.find_one_and_update(
        {"_id": comment_id, "user.id": current_user.id},
        {"$set": {"text": text, "updated_at": datetime.now(), "status": CommentStatus.PENDING.value}}
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update comment"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete('/comments')
async def delete_post_comments(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        comment_id: ObjectId
) -> Any:
    """
    User

    Delete comment

    Authorization: Required
    """

    result = await db.comments.find_one({"_id": comment_id, "user.id": current_user.id},
                                        {"_id": 1, "user": 1, "post_id": 1})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No comment found with the given id"
        )
    if result.get("user").get("id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete this comment"
        )
    delete_result = await db.comments.delete_many({"$or": [{"_id": comment_id}, {"parent": {"$in": [comment_id]}}]})
    await db.posts.update_one(
        {"_id": result.get("post_id")},
        {"$inc": {"comments_count": -1 * delete_result.deleted_count}}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/comments/{post_id}', response_model=Comment)
async def add_comment_to_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        post_id: ObjectId,
        comment: str = Body(..., embed=True),
        parent: Optional[ObjectId] = Query(None)
) -> Any:
    """
    User

    Add comment

    Authorization: Required
    """

    post = await db.posts.find_one({"_id": post_id}, {"_id": 1, 'owner_id': 1, "comment": 1, 'images': 1})
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No post found with the given id"
        )

    if parent:
        parent = await db.comments.find_one({"_id": parent}, {"_id": 1, "parent": 1, "user": 1})
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No comment found with the given id"
            )

    parents_array = None
    if parent:
        parents_array = [*(parent.get("parent") if parent.get("parent") else []), parent.get("_id")]

    user = await db.users.find_one({"_id": current_user.id}, {"basic_info": 1, "username": 1, "_id": 1})
    now = datetime.now()
    comment = {
        "parent": parents_array,
        "post_id": post_id,
        "text": comment,
        "user": {
            "id": user.get("_id"),
            "username": user.get("username"),
            "first_name": user.get("basic_info").get("first_name") if user.get("basic_info") else None,
            "last_name": user.get("basic_info").get("last_name") if user.get("basic_info") else None,
            "avatar": user.get("basic_info").get("avatar") if user.get("basic_info") else None
        },
        "created_at": now,
        "status": CommentStatus.ACCEPTED.value
    }
    result = await db.comments.insert_one(comment)
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not insert comment"
        )

    if parents_array:
        inc_reply_count = await db.comments.update_one(
            {'_id': parents_array[-1]}, {'$inc': {'reply_count': 1}}
        )

    # comment notifications
    notifications = [{
        'owner_id': post.get("owner_id"),
        'category': NotificationCategory.COMMENT,
        'extra_data': {
            "post_id": post.get('_id'),
            "comment_id": result.inserted_id,
            "user": comment.get("user"),
            "comment_text": comment.get('text'),
            "post_images": post.get('images')

        },
        'actionable': True,
        'created_at': now,
        'seen': False
    }]
    if parent:
        notifications.append(
            {
                'owner_id': parent.get("user").get("id"),
                'category': NotificationCategory.COMMENT,
                'extra_data': {
                    "comment_id": result.inserted_id,
                    "user": parent.get("user"),
                    "comment_text": comment.get('text')

                },
                'actionable': True,
                'created_at': now,
                'seen': False
            }
        )
    notification_result = await db.notifications.insert_many(notifications)
    if not notification_result.acknowledged:
        return {'message': 'Could not create notification'}
    comment = Comment.parse_obj({**comment, "id": result.inserted_id}).dict()
    await db.posts.update_one(
        {"_id": post_id},
        {"$set": {"comment": comment} if not post.get("comment") else {}, "$inc": {"comments_count": 1}}
    )
    return comment


@router.get('/comments/{post_id}', response_model=List[Comment])
async def get_post_comments(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        post_id: ObjectId,
        parent: Optional[ObjectId] = Query(None),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20
) -> Any:
    """
    User

    Get comment

    Authorization: Required
    """

    query = {"post_id": post_id, "status": {"$ne": CommentStatus.DECLINED.value}, "parent": None}
    if parent:
        query["parent"] = {"$in": [parent]}
    comments = await db.comments.find(
        {"$query": query, "$orderby": {"created_at": 1}}
    ).skip(offset * limit).to_list(length=limit)
    comments = list(map(lambda x: Comment.parse_obj({**x, "id": x.get("_id")}), comments))
    return comments


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


@router.delete('/admin/comments/{comment_id}')
async def admin_delete_post_comments(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        comment_id: ObjectId
) -> Any:
    """
    Admin

    Delete comment

    Authorization: Required
    """

    result = await db.comments.find_one({"_id": comment_id}, {"_id": 1, "user": 1, "post_id": 1})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No comment found with the given id"
        )

    delete_result = await db.comments.delete_many({"$or": [{"_id": comment_id}, {"parent": {"$in": [comment_id]}}]})

    result = await db.posts.update_one(
        {"_id": result.get("post_id")},
        {"$inc": {"comments_count": -1 * delete_result.deleted_count}}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/admin/{post_id}', response_model=UserPostsOut)
async def admin_get_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        post_id: ObjectId,
) -> UserPostsOut:
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
    return UserPostsOut.parse_obj(
        {**result, 'id': post_id}
    )


@router.get('/{post_id}', response_model=UserPostsOut)
async def get_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        post_id: ObjectId
) -> UserPostsOut:
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
    return UserPostsOut.parse_obj(
        {**result, 'id': post_id}
    )


@router.put('/{post_id}')
async def update_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: UserPostUpdate,
        post_id: ObjectId
):
    """
    User

    Update post

    Authorization: Required
    """

    now = datetime.now()
    images = data.images
    data = data.dict(exclude_defaults=True)

    post = await db.posts.find_one({'_id': post_id, 'owner_id': current_user.id}, {'post_type': 1})
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found. "
        )
    post_type = post.get('post_type')
    if post_type == PostsType.POLL_POST:
        await check_required_fields(
            data, required_fields=POLL_POST_UPDATE_REQUIRED_FIELDS
        )
        data = await remove_unnecessary_fields(
            permitted_fields=POLL_POST_UPDATE_PERMITTED_FIELDS, request_data=data
        )
    elif post_type == PostsType.ARTICLE:
        await check_required_fields(
            data, required_fields=ARTICLE_UPDATE_REQUIRED_FIELDS
        )
        data = await remove_unnecessary_fields(
            permitted_fields=ARTICLE_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    elif post_type == PostsType.TEXT_POST:
        await check_required_fields(
            data, required_fields=TEXT_POST_UPDATE_REQUIRED_FIELDS
        )
        data = await remove_unnecessary_fields(
            permitted_fields=TEXT_POST_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    elif post_type == PostsType.IMAGE_POST:
        await check_required_fields(
            data, required_fields=IMAGE_POST_UPDATE_REQUIRED_FIELDS
        )
        data = await remove_unnecessary_fields(
            permitted_fields=IMAGE_POST_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    elif post_type == PostsType.VIDEO_POST:
        await check_required_fields(
            data, required_fields=VIDEO_POST_UPDATE_REQUIRED_FIELDS
        )
        data = await remove_unnecessary_fields(
            permitted_fields=VIDEO_POST_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    else:
        assert "Invalid PostType"

    data = {**data, 'updated_at': now} if data else {'updated_at': now}

    result = await db.posts.find_one_and_update(
        {'_id': post_id, 'owner_id': current_user.id}, {'$set': data},
        return_document=ReturnDocument.AFTER,
        projection=
        {
            'user',
            'owner_id',
            'title',
            'tags',
            'body',
            'post_type',
            'privacy',
            'created_at',
            'status',
            'hits',
            'like_count',
            'poll_choices',
            'poll_expiration',
            'poll_status',
            'poll_type',
            'poll_vote_count',
            'images',
            'video',
            'category'
        },
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=OperationResponse.UNSUCCESSFUL_UPDATE
        )

    if post_type == PostsType.IMAGE_POST.value and images:
        for path in images:
            await move_image_from_temp(path)

    return UserPostsOut.parse_obj_id({**result, 'user': UserNestedInPost.parse_obj(result.get('user'))})


@router.patch('/{post_id}')
async def partial_update_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: UserPostsPartialUpdate,
        post_id: ObjectId
):
    """
    User

    Partial Update post

    Authorization: Required
    """

    now = datetime.now()
    images = data.images
    data = data.dict(exclude_unset=True)

    post = await db.posts.find_one({'_id': post_id, 'owner_id': current_user.id}, {'post_type': 1})
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found. "
        )
    post_type = post.get('post_type')
    if post_type == PostsType.POLL_POST:
        data = await remove_unnecessary_fields(
            permitted_fields=POLL_POST_PARTIAL_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    elif post_type == PostsType.ARTICLE:
        data = await remove_unnecessary_fields(
            permitted_fields=ARTICLE_PARTIAL_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    elif post_type == PostsType.TEXT_POST:
        data = await remove_unnecessary_fields(
            permitted_fields=TEXT_POST_PARTIAL_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    elif post_type == PostsType.IMAGE_POST:
        data = await remove_unnecessary_fields(
            permitted_fields=IMAGE_POST_PARTIAL_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    elif post_type == PostsType.VIDEO_POST:
        data = await remove_unnecessary_fields(
            permitted_fields=VIDEO_POST_PARTIAL_UPDATE_PERMITTED_FIELDS, request_data=data
        )

    else:
        assert "Invalid PostType"

    data = {**data, 'updated_at': now}
    result = await db.posts.find_one_and_update(
        {'_id': post_id, 'owner_id': current_user.id},
        {'$set': data},
        projection=
        {
            'user',
            'owner_id',
            'title',
            'tags',
            'body',
            'post_type',
            'privacy',
            'created_at',
            'status',
            'hits',
            'like_count',
            'poll_choices',
            'poll_expiration',
            'poll_status',
            'poll_type',
            'poll_vote_count',
            'images',
            'video',
            'category'
        },
        return_document=ReturnDocument.AFTER
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=OperationResponse.UNSUCCESSFUL_UPDATE
        )

    if post_type == PostsType.IMAGE_POST.value and images:
        for path in images:
            await move_image_from_temp(path)

    return UserPostsOut.parse_obj_id({**result, 'user': UserNestedInPost.parse_obj(result.get('user'))})


@router.delete('/{post_id}')
async def delete_post(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        post_id: ObjectId
) -> Response:
    """
    User

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

    if result.get('video'):
        try:
            video_path = result.get('video')
            path = os.path.join(settings.MEDIA_DIR, video_path)
            await aiofiles.os.remove(path)
        except Exception as e:
            print(e)
            # TODO log that file has not been deleted

    return Response(status_code=status.HTTP_204_NO_CONTENT)
