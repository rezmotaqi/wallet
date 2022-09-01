"""Routing core modules and utilities."""

from fastapi import APIRouter

from app.endpoints import (
    uploads,
    users,
    auth,
    posts,
    products
)

router = APIRouter()


router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)


router.include_router(
    uploads.router,
    prefix="/uploads",
    tags=["uploads"]
)


router.include_router(
    posts.router,
    prefix="/posts",
    tags=["posts"]
)

router.include_router(
    products.router,
    prefix="/products",
    tags=["products"]
)
