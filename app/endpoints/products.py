"""
Products apis
route: /products
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core import depends
from app.schemas.products import ProductInput
from app.schemas.users import User

router = APIRouter()


@router.post('')
async def create(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        data: ProductInput
):
    """
    Admin

    Create product
    """

    return


@router.get('')
async def get(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """

    """

    return


@router.patch('/{_id}')
async def partial_update(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """

    """

    return


@router.get('/{_id}')
async def get_single(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """

    """

    return


@router.delete('/{_id}')
async def delete(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """

    """

    return
