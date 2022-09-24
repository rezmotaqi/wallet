import uuid
from datetime import datetime

from fastapi import Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status
from bson import ObjectId as BaseObjectId
from starlette.responses import Response

from app.core import depends
from app.core.router import router
from app.schemas.base import ObjectId
from app.schemas.general import TicketInput
from app.schemas.users import User


@router.post('/ticket', status_code=status.HTTP_201_CREATED)
async def create_ticket(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: TicketInput
):
    """
    Client

    Create product guarantee
    """

    result = await db.tickets.update_one(
        {'_id': BaseObjectId(current_user.id)},
        {'$addToSet': {'tickets': {**data.dict(), 'created_at': datetime.now(), 'id': uuid.uuid4()}}},
        upsert=True
    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create guarantee."
        )

    return Response(status_code=status.HTTP_201_CREATED)


@router.get('/ticket', status_code=status.HTTP_200_OK)
async def get_user_ticket(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: TicketInput,
        ticket_id: ObjectId = None
):
    """
    Client

    Create product guarantee
    """
    if

    now = datetime.now()
    if ticket_id:



    result = await db.tickets.update_one(
        {'owner_id': BaseObjectId(current_user.id)},
        {'$setOnInsert': {'owner_id': BaseObjectId(current_user.id),'created_at': now, 'department': }}
        {'$addToSet': {'tickets': {**data.dict(), 'created_at': datetime.now(), 'id': uuid.uuid4()}}},
        upsert=True,

    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create ticket."
        )

    return Response(status_code=status.HTTP_201_CREATED)


