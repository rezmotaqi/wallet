"""
Pydantic schemas Posts
"""

import uuid
from enum import Enum
from typing import Optional, List

from pydantic import validator, root_validator
from pydantic.fields import Field

from app.schemas.base import Model, ObjectId, DateTime
from app.schemas.general import UserType


class PostsType(str, Enum):
    POLL_POST = 'POLL_POST'
    ARTICLE = 'ARTICLE'
    TEXT_POST = 'TEXT_POST'
    VIDEO_POST = 'VIDEO_POST'
    IMAGE_POST = 'IMAGE_POST'


class PostsPrivacySetting(str, Enum):
    PRIVATE = 'PRIVATE'
    PUBLIC = 'PUBLIC'
    ONLY_ME = 'ONLY_ME'


class PollStatus(str, Enum):
    OPEN = 'OPEN'
    CLOSED = 'CLOSED'


class PollType(str, Enum):
    SINGLE = 'SINGLE'
    MULTI = 'MULTI'


class CommentStatus(str, Enum):
    """
    schema for comment status
    """

    ACCEPTED = 'ACCEPTED'
    PENDING = 'PENDING'
    DECLINED = 'DECLINED'
    REPORTED = 'REPORTED'


class ReportCollection(str, Enum):
    POST = 'posts'
    COMMENT = 'comments'


class CommentOrderBy(str, Enum):
    """
    schema for comment ordering
    """

    CREATED_AT = 'created_at'
    _CREATED_AT = '-created_at'


class PostsStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    DELETED = 'DELETED'
    REPORTED = 'REPORTED'


class CommentUser(Model):
    """
    Pydantic schema for comment's user
    """

    id: Optional[ObjectId] = Field()
    username: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    company_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    user_type: Optional[UserType] = Field()


class Comment(Model):
    """
    Pydantic schema for comment
    """

    id: Optional[ObjectId] = Field()
    parent: Optional[List[ObjectId]] = Field()
    post_id: Optional[ObjectId] = Field()
    user: CommentUser = Field()
    created_at: DateTime = Field()
    text: str = Field()
    status: CommentStatus = Field(default=CommentStatus.ACCEPTED.value)
    reply_count: Optional[int] = Field(default=0)


class PollChoicesIn(Model):
    text: str = Field()


class PostCategoryCreate(Model):
    """
    Schema for creating article category by admin
    """
    name: str = Field()


class PostCategoryOut(Model):
    """
    Schema for returning category to user
    """
    id: ObjectId = Field()
    name: str = Field()


class PostCategoryListOut(Model):
    """
    Schema for returning category list to user
    """
    count: int = Field()
    category_list: List[PostCategoryOut] = Field()


class UserPostsCreate(Model):
    """
    Schema for creating post by user
    """

    title: Optional[str] = Field()
    url: str = Field()
    page_title: str = Field()


    privacy: PostsPrivacySetting = Field()
    post_type: PostsType = Field()
    body: Optional[str] = Field()
    category: Optional[str] = Field()
    tags: Optional[List[str]] = Field()

    images: Optional[List[str]] = Field()



class UserPostUpdate(Model):
    """
    Schema for updating article post
    """

    category: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    title: Optional[str] = Field()

    body: str = Field()
    privacy: PostsPrivacySetting = Field()

    images: Optional[List[str]] = Field()
    video: Optional[str] = Field()

    poll_status: Optional[PollStatus] = Field()


class UserPostsPartialUpdate(Model):
    """
    Schema for partial updating post by user
    """

    category: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    title: Optional[str] = Field()

    body: Optional[str] = Field()
    privacy: Optional[PostsPrivacySetting] = Field()

    images: Optional[List[str]] = Field()
    video: Optional[str] = Field()

    poll_status: Optional[PollStatus] = Field()


class PollChoicesOut(Model):
    """
    Schema for returning poll choice
    """

    text: str = Field()
    choice_id: Optional[uuid.UUID] = Field()
    vote_count: Optional[int] = Field()


class PollChoicesOutFeed(Model):
    """
    Schema for returning poll choice
    """

    text: str = Field()
    choice_id: Optional[uuid.UUID] = Field()
    vote_count: Optional[int] = Field()
    voted: bool = Field(default=False)


class UserNestedInPost(Model):
    """
    Schema for nested user object in admin
    """

    id: ObjectId = Field()
    username: str = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()


class UserPostsOut(Model):
    """
    Schema for returning  post data to user
    """

    id: ObjectId = Field()
    owner_id: ObjectId = Field()
    title: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    body: Optional[str] = Field()
    post_type: Optional[PostsType] = Field()
    privacy: Optional[PostsPrivacySetting] = Field()
    created_at: DateTime = Field()
    status: Optional[PostsStatus] = Field()
    hits: Optional[int] = Field()
    like_count: Optional[int] = Field()
    poll_choices: Optional[List[PollChoicesOut]] = Field()
    poll_expiration: Optional[DateTime] = Field()
    poll_status: Optional[PollStatus] = Field()
    poll_type: Optional[PollType] = Field()
    poll_vote_count: Optional[int] = Field()
    images: Optional[List[str]] = Field()
    video: Optional[str] = Field()
    category: Optional[str] = Field()
    user: Optional[UserNestedInPost] = Field()


class UserPostsListOut(Model):
    """
    Schema for returning list of posts and s
    """
    count: int = Field()
    posts: List[UserPostsOut] = Field()


class UserAdminOut(UserNestedInPost):
    """
    Schema for returning user data nested in post object to admin
    """
    pass


class UserPostsAdminOut(Model):
    """
    Schema for returning  post data to user
    """

    id: ObjectId = Field()
    owner_id: ObjectId = Field()
    title: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    body: Optional[str] = Field()
    post_type: Optional[PostsType] = Field()
    privacy: Optional[PostsPrivacySetting] = Field()
    created_at: DateTime = Field()
    status: Optional[PostsStatus] = Field()
    hits: Optional[int] = Field()
    like_count: Optional[int] = Field()
    comments_count: Optional[int] = Field()
    poll_choices: Optional[List[PollChoicesOut]] = Field()
    poll_expiration: Optional[DateTime] = Field()
    poll_status: Optional[PollStatus] = Field()
    poll_type: Optional[PollType] = Field()
    poll_vote_count: Optional[int] = Field()
    images: Optional[List[str]] = Field()
    video: Optional[str] = Field()
    category: Optional[str] = Field()
    user: UserAdminOut = Field()


class UserPostsListAdminOut(Model):
    """
    Schema for returning list of posts and s
    """
    count: int = Field()
    posts: List[UserPostsAdminOut] = Field()


class FeedUser(CommentUser):
    """
    Pydantic schema for feed's user
    """

    headline: Optional[str] = Field()


class FeedUserOut(Model):
    """
    Schema for returning  post data to user
    """

    id: ObjectId = Field()
    user: Optional[FeedUser] = Field()
    comment: Optional[List[Comment]] = Field(default=[])
    comments_count: Optional[int] = Field(default=0)
    owner_id: ObjectId = Field()
    title: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    body: Optional[str] = Field()
    post_type: PostsType = Field()
    privacy: PostsPrivacySetting = Field()
    created_at: DateTime = Field()
    hits: Optional[int] = Field(default=0)
    like_count: Optional[int] = Field(default=0)
    is_liked: Optional[bool] = Field(default=False)
    is_reported: Optional[bool] = Field(default=False)
    poll_choices: Optional[List[PollChoicesOutFeed]] = Field()
    poll_expiration: Optional[DateTime] = Field()
    poll_status: Optional[PollStatus] = Field()
    poll_type: Optional[PollType] = Field()
    poll_vote_count: Optional[int] = Field()
    video: Optional[str] = Field()
    images: Optional[List[str]] = Field()
    category: Optional[str] = Field()


class FeedUserListOut(Model):
    """
    Schema for returning list of posts and s
    """
    count: int = Field()
    posts: List[FeedUserOut] = Field()
