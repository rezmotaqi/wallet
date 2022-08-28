"""
Functions for posts
"""

from fastapi import HTTPException
from starlette import status

from app.schemas.posts import PostsType


async def increment_posts_hits(db, object_ids):
    """
    Increase post hits (number of times that post has benn viewed)
    """

    hits_update_result = await db.posts.update_many(
        {'_id': {'$in': object_ids}},
        {'$inc': {'hits': 1}}
    )

    if not hits_update_result.acknowledged:
        # TODO add logging mechanism
        pass


async def check_required_fields(data, required_fields=None):
    """
    Checks if required fields are present in data and if not raises HTTP exception
    """

    if required_fields:
        required_fields_not_provided = all(field not in data.keys() for field in required_fields)
        if required_fields_not_provided:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid fields. Required fields not provided! required_fields={required_fields}."
            )


async def remove_unnecessary_fields(permitted_fields, request_data):
    """
    Check request data and if there are any keys other than fields that are given in permitted_fields, it deletes those
    fields and returns cleaned data
    """
    returning_request_data = request_data.copy()
    for field in request_data.keys():
        if field not in permitted_fields:
            returning_request_data.pop(field)
    return returning_request_data


"""
Static values for post modules
"""

POLL_POST_UPDATE_PERMITTED_FIELDS = ["privacy", "poll_status"]
POLL_POST_UPDATE_REQUIRED_FIELDS = ["privacy", "poll_status"]
POLL_POST_PARTIAL_UPDATE_PERMITTED_FIELDS = ["privacy", "poll_status"]

ARTICLE_UPDATE_PERMITTED_FIELDS = ["title", "body", "category", "privacy", "images", "video", "tags"]
ARTICLE_UPDATE_REQUIRED_FIELDS = ["title", "body", "category", "privacy", "category"]
ARTICLE_PARTIAL_UPDATE_PERMITTED_FIELDS = ["title", "body", "category", "privacy", "images", "video", "tags"]

TEXT_POST_UPDATE_PERMITTED_FIELDS = ["body", "privacy"]
TEXT_POST_UPDATE_REQUIRED_FIELDS = ["body", "privacy"]
TEXT_POST_PARTIAL_UPDATE_PERMITTED_FIELDS = ["body", "privacy"]

IMAGE_POST_UPDATE_PERMITTED_FIELDS = ["body", "images", "privacy"]
IMAGE_POST_UPDATE_REQUIRED_FIELDS = ["images", "privacy"]
IMAGE_POST_PARTIAL_UPDATE_PERMITTED_FIELDS = ["body", "images", "privacy"]

VIDEO_POST_UPDATE_PERMITTED_FIELDS = ["body", "video", "privacy"]
VIDEO_POST_UPDATE_REQUIRED_FIELDS = ["video", "privacy"]
VIDEO_POST_PARTIAL_UPDATE_PERMITTED_FIELDS = ["body", "video", "privacy"]
