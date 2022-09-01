"""The main endpoint of this platform."""

from datetime import datetime
from typing import NoReturn

from pymongo import ASCENDING, TEXT, DESCENDING

from app.config.settings import settings
from app.core.authentication import get_password_hash
from app.core.depends import get_database
from app.schemas.general import UserStatus


async def initialize_project() -> NoReturn:
    db = await get_database()

    # Put your mongo indexes here

    await db.users.create_index(
        [("username", ASCENDING)], name="username", unique=True, background=True
    )

    # await db.post_categories.create_index(
    #     [("name", ASCENDING)], name="post_categories", unique=True, background=True
    # )

    # await db.discounts.create_index(
    #     [("code", ASCENDING)], name="discount_code", unique=True, background=True
    # )

    # await db.discounts.create_index(
    #     [("code", ASCENDING)],
    #     name="discount_code",
    #     partialFilterExpression=
    #     {"code": {"$type": [
    #         "double",
    #         "string",
    #         "object",
    #         "array",
    #         "binData",
    #         "undefined",
    #         "objectId",
    #         "bool",
    #         "date",
    #         "regex",
    #         "dbPointer",
    #         "javascript",
    #         "symbol",
    #         "javascriptWithScope",
    #         "int",
    #         "timestamp",
    #         "long",
    #         "decimal",
    #         "minKey",
    #         "maxKey"
    #     ]}},
    #     background=True,
    #     unique=True
    # )

    # await db.users.create_index(
    #     [("contact_info.mobile", ASCENDING)],
    #     name="contact_info.mobile",
    #     partialFilterExpression=
    #     {"contact_info.mobile": {"$type": [
    #         "double",
    #         "string",
    #         "object",
    #         "array",
    #         "binData",
    #         "undefined",
    #         "objectId",
    #         "bool",
    #         "date",
    #         "regex",
    #         "dbPointer",
    #         "javascript",
    #         "symbol",
    #         "javascriptWithScope",
    #         "int",
    #         "timestamp",
    #         "long",
    #         "decimal",
    #         "minKey",
    #         "maxKey"
    #     ]}},
    #     background=True,
    #     unique=True
    # )
    #
    # await db.users.create_index(
    #     [("contact_info.email", ASCENDING)],
    #     name="contact_info.email",
    #     partialFilterExpression=
    #     {"contact_info.email": {"$type": [
    #         "double",
    #         "string",
    #         "object",
    #         "array",
    #         "binData",
    #         "undefined",
    #         "objectId",
    #         "bool",
    #         "date",
    #         "regex",
    #         "dbPointer",
    #         "javascript",
    #         "symbol",
    #         "javascriptWithScope",
    #         "int",
    #         "timestamp",
    #         "long",
    #         "decimal",
    #         "minKey",
    #         "maxKey"
    #     ]}},
    #     background=True,
    #     unique=True
    # )

    await db.users.create_index(
        [
            ("username", TEXT),
            ("basic_info.last_name", TEXT),
            ("basic_info.first_name", TEXT)

        ], name="text", background=True)

    await db.posts.create_index([("created_at", DESCENDING)], name="created_at", background=True)

    # check if root user exists and if not, insert it
    await db.users.update_one(
        {"username": settings.ROOT_USER},
        {
            "$set": {
                "role": ["admin"],
                "username": settings.ROOT_USER,
                "password": get_password_hash(settings.ROOT_PASSWORD),
                "updated_at": datetime.now(),
                "created_at": datetime.now(),
                "status": UserStatus.ACTIVE
            }
        },
        upsert=True
    )
