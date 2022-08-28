"""Routing core modules and utilities."""

from fastapi import APIRouter

from app.endpoints import (
    uploads,
    portfolio,
    websockets,
    users,
    auth,
    posts,
    events,
    sessions,
    meetings,
    virtual_rooms,
    workshops,
    booths
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
    websockets.router,
    prefix="/ws",
    tags=["websockets"]
)

router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["portfolio"]
)


router.include_router(
    posts.router,
    prefix="/posts",
    tags=["posts"]
)

router.include_router(
    events.router,
    prefix="/events",
    tags=["events"]
)

router.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["sessions"]
)

router.include_router(
    meetings.router,
    prefix="/meetings",
    tags=["meetings"]
)

router.include_router(
    virtual_rooms.router,
    prefix="/virtual_rooms",
    tags=["virtual_rooms"]
)

router.include_router(
    workshops.router,
    prefix="/workshops",
    tags=["workshops"]
)

router.include_router(
    booths.router,
    prefix="/booths",
    tags=["booths"]
)
