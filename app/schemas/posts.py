"""
Pydantic schemas Posts
"""

import uuid
from enum import Enum
from typing import Optional, List

from pydantic import validator, root_validator
from pydantic.fields import Field

from app.schemas.base import Model, ObjectId, DateTime


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


class RelatedPostDataInPost(Model):
    """
    Pydantic schema for storing related post data in post
    """
    post_id: ObjectId = Field()
    text: str = Field()


class RelatedProductDataInPost(Model):
    """
    Pydantic schema for storing related post data in post
    """
    product_id: ObjectId = Field()
    text: str = Field()


class AuthorInPost(Model):
    """
    Schema for nested user object in post
    """

    id: ObjectId = Field()
    username: str = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()


class PostsCreate(Model):
    """
    Schema for creating post by user
    """

    title: Optional[str] = Field()
    url: str = Field()
    page_title: str = Field()
    publish_date: DateTime = Field()
    author: Optional[AuthorInPost] = Field()
    reading_estimate: Optional[int] = Field()
    summary: Optional[str] = Field()
    text: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    image: Optional[str] = Field()
    related_posts: Optional[List[RelatedPostDataInPost]] = Field()
    related_products: Optional[List[RelatedProductDataInPost]] = Field()
    category: Optional[str] = Field()
    seo_text: Optional[str] = Field()
    keywords: Optional[List[str]] = Field()
    source_title: Optional[str] = Field()
    source_url: Optional[str] = Field()


class PostsUpdate(Model):
    """
    Schema for updating post
    """

    title: Optional[str] = Field()
    url: str = Field()
    page_title: str = Field()
    publish_date: DateTime = Field()
    author: Optional[AuthorInPost] = Field()
    reading_estimate: Optional[int] = Field()
    summary: Optional[str] = Field()
    text: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    image: Optional[str] = Field()
    related_posts: Optional[List[RelatedPostDataInPost]] = Field()
    related_products: Optional[List[RelatedProductDataInPost]] = Field()
    category: Optional[str] = Field()
    seo_text: Optional[str] = Field()
    keywords: Optional[List[str]] = Field()
    source_title: Optional[str] = Field()
    source_url: Optional[str] = Field()


class PostsPartialUpdate(Model):
    """
    Schema for partial updating post by user
    """

    title: Optional[str] = Field()
    url: Optional[str] = Field()
    page_title: Optional[str] = Field()
    publish_date: Optional[DateTime] = Field()
    author: Optional[AuthorInPost] = Field()
    reading_estimate: Optional[int] = Field()
    summary: Optional[str] = Field()
    text: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    image: Optional[str] = Field()
    related_posts: Optional[List[RelatedPostDataInPost]] = Field()
    related_products: Optional[List[RelatedProductDataInPost]] = Field()
    category: Optional[str] = Field()
    seo_text: Optional[str] = Field()
    keywords: Optional[List[str]] = Field()
    source_title: Optional[str] = Field()
    source_url: Optional[str] = Field()


class PostsOut(Model):
    """
    Schema for returning  post data to user
    """

    title: Optional[str] = Field()
    url: Optional[str] = Field()
    page_title: Optional[str] = Field()
    publish_date: Optional[DateTime] = Field()
    author: Optional[AuthorInPost] = Field()
    reading_estimate: Optional[int] = Field()
    summary: Optional[str] = Field()
    text: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    image: Optional[str] = Field()
    related_posts: Optional[List[RelatedPostDataInPost]] = Field()
    related_products: Optional[List[RelatedProductDataInPost]] = Field()
    category: Optional[str] = Field()
    seo_text: Optional[str] = Field()
    keywords: Optional[List[str]] = Field()
    source_title: Optional[str] = Field()
    source_url: Optional[str] = Field()


class PostsListOut(Model):
    """
    Schema for returning list of posts and s
    """
    count: int = Field()
    posts: List[PostsOut] = Field()


class PostsAdminOut(Model):
    """
    Schema for returning  post data to user
    """

    id: ObjectId = Field()
    title: Optional[str] = Field()
    url: Optional[str] = Field()
    page_title: Optional[str] = Field()
    publish_date: Optional[DateTime] = Field()
    author: Optional[AuthorInPost] = Field()
    reading_estimate: Optional[int] = Field()
    summary: Optional[str] = Field()
    text: Optional[str] = Field()
    tags: Optional[List[str]] = Field()
    image: Optional[str] = Field()
    related_posts: Optional[List[RelatedPostDataInPost]] = Field()
    related_products: Optional[List[RelatedProductDataInPost]] = Field()
    category: Optional[str] = Field()
    seo_text: Optional[str] = Field()
    keywords: Optional[List[str]] = Field()
    source_title: Optional[str] = Field()
    source_url: Optional[str] = Field()
    owner_id: ObjectId = Field()
    created_at: DateTime = Field()
    updated_at: DateTime = Field()
    status: Optional[PostsStatus] = Field()
    hits: Optional[int] = Field()
    like_count: Optional[int] = Field()


class PostsListAdminOut(Model):
    """
    Schema for returning list of posts and s
    """
    count: int = Field()
    posts: List[UserPostsAdminOut] = Field()

