"""
Functions related to products
"""
from typing import Dict, NoReturn

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status


async def validate_guarantees(db: AsyncIOMotorDatabase, guarantees: Dict) -> NoReturn:
    """
    Validate guarantees when adding to product
    """

    ids = [g['id'] for g in guarantees]

    found_guarantees = await db.guarantees.find({'_id': {'$in': ids}})
    if not found_guarantees or len(found_guarantees) != len(ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={'a': 1}
        )