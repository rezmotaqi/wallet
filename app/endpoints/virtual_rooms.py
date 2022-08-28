"""
Virtual rooms APIs
route: /virtual_rooms
"""

from datetime import datetime

from bson import ObjectId as BaseObjectId
from fastapi import APIRouter, Depends, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status

from app.core import depends
from app.core.meetings import create_meeting
from app.core.utils import create_mongo_array_update
from app.core.virtual_rooms import check_room_participants
from app.schemas.base import ObjectId
from app.schemas.general import EventOperatorType
from app.schemas.meetings import MeetingProperty
from app.schemas.users import User
from app.schemas.virtual_rooms import (
    VirtualRoom,
    VirtualRoomCreate,
    VirtualRoomUser,
    VirtualRoomDataInEvent,
    VirtualRoomPartialUpdate
)

router = APIRouter()


@router.post("", response_model=VirtualRoom, status_code=status.HTTP_201_CREATED)
async def create_room(
        event_id: ObjectId,
        room: VirtualRoomCreate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Create virtual room

    Authorization: required
    """

    event = await db.events.find_one(
        {"_id": event_id},
        {
            "_id": 1,
            "participants": 1,
            "operators": 1,
            "owner_id": 1,
            "properties": 1,
            "starts_at": 1,
            "ends_at": 1,
            "virtual_rooms": 1
        }
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No event found with the given id"
        )
    if not event.get("properties", {}).get("virtual_room", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event cannot have virtual room"
        )

    operator = await db.users.find_one(
        {"_id": BaseObjectId(current_user.id)},
        {
            '_id': 1,
            'basic_info': 1,
            'user_type': 1,
            'username': 1,
            'contact_info': 1
        }
    )
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    room_data = room.dict()
    participants = await check_room_participants(BaseObjectId(current_user.id), event, room_data.get("participants"))

    now = datetime.now()
    room_owner = VirtualRoomUser.parse_obj({
        **operator,
        "id": operator.get("_id"),
        "company_name": operator.get('basic_info', {}).get('company_name'),
        "first_name": operator.get('basic_info', {}).get('first_name'),
        "last_name": operator.get('basic_info', {}).get('last_name'),
        "avatar": operator.get('basic_info', {}).get('avatar'),
        "headline": operator.get('basic_info', {}).get('headline'),
        "website": operator.get('contact_info', {}).get('website')
    }).dict(exclude_unset=True, exclude_none=True)
    room_data = VirtualRoom.parse_obj({
        **room.dict(),
        "is_active": True,
        "event_id": event_id,
        "created_at": now,
        "updated_at": now,
        "owner": room_owner,
    }).dict(exclude_unset=True, exclude_none=True)
    if participants:
        room_data.update({"participants": participants})

    room_result = await db.virtual_rooms.insert_one(room_data)

    if not room_result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create virtual room"
        )

    room_data["id"] = room_result.inserted_id

    await db.events.update_one(
        {"_id": event_id},
        {
            "$set": {"virtual_rooms": [
                *event.get("virtual_rooms"),
                VirtualRoomDataInEvent.parse_obj(room_data).dict(exclude_unset=True, exclude_none=True)
            ] if event.get("virtual_rooms") else [
                VirtualRoomDataInEvent.parse_obj(room_data).dict(exclude_unset=True, exclude_none=True)]}
        }
    )

    room_data = await create_meeting(db, room_data, MeetingProperty.virtual_rooms)

    return VirtualRoom.parse_obj(room_data)


@router.get("/{room_id}", response_model=VirtualRoom)
async def get_room(
        room_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Get virtual room

    Authorization: required
    """

    room_result = await db.virtual_rooms.find_one({"_id": room_id})
    if not room_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No room found with the given id"
        )

    event = await db.events.find_one(
        {"_id": room_result.get("event_id")},
        {"_id": 1, "owner_id": 1, "operators": 1}
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No event found for this room"
        )

    event_operators_ids = list({
        event.get("owner_id"),
        *list(map(
            lambda x: x.get("id"),
            filter(
                lambda x: x.get("type") == EventOperatorType.ADMIN.value,
                event.get("operators", [])
            )
        ))
    })

    if BaseObjectId(current_user.id) not in event_operators_ids:
        if room_result.get("owner.id") != BaseObjectId(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this room"
            )

    return VirtualRoom.parse_obj({**room_result, "id": room_id})


@router.patch("/{room_id}", response_model=VirtualRoom)
async def partial_update_room(
        room_id: ObjectId,
        room_update: VirtualRoomPartialUpdate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Partial update virtual room

    Authorization: required
    """

    now = datetime.now()
    room_result = await db.virtual_rooms.find_one({"_id": room_id})
    if not room_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No room found with the given id"
        )

    event = await db.events.find_one(
        {"_id": room_result.get("event_id")},
        {"_id": 1, "owner_id": 1, "operators": 1, "participants": 1}
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No event found for this room"
        )

    event_operators_ids = list({
        event.get("owner_id"),
        *list(map(
            lambda x: x.get("id"),
            filter(
                lambda x: x.get("type") == EventOperatorType.ADMIN.value,
                event.get("operators", [])
            )
        ))
    })
    if BaseObjectId(current_user.id) not in event_operators_ids:
        if not room_result.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot update a disabled room"
            )
        if room_result.get("starts_at") < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot update a room after it's started"
            )
        if room_result.get("owner.id") != BaseObjectId(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this room"
            )
    room_update_dict = {**room_result, "id": room_id}
    if room_update.participants:
        room_update_dict.update({**room_update.dict(exclude_unset=True), "updated_at": now})
        participants = await check_room_participants(
            BaseObjectId(current_user.id),
            event,
            room_update_dict.get("participants", []),
            room_result.get("participants", [])
        )
        if participants:
            room_update_dict.update({"participants": participants})
        await db.virtual_rooms.update_one({"_id": room_id}, {"$set": room_update_dict})
        await db.events.update_one(
            {"_id": room_result.get("event_id"), 'virtual_rooms.id': room_id},
            {
                "$set": {**create_mongo_array_update(
                    "virtual_rooms",
                    VirtualRoomDataInEvent.parse_obj(room_update_dict).dict()
                )}
            }
        )
    return VirtualRoom.parse_obj(room_update_dict)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_virtual_room(
        room_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Delete virtual room

    Authorization: required
    """

    room_result = await db.virtual_rooms.find_one({"_id": room_id})
    if not room_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No room found with the given id"
        )
    event = await db.events.find_one(
        {"_id": room_result.get("event_id")},
        {"_id": 1, "owner_id": 1, "operators": 1}
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No event found for this room"
        )
    event_operators_ids = list({
        event.get("owner_id"),
        *list(map(
            lambda x: x.get("id"),
            filter(
                lambda x: x.get("type") == EventOperatorType.ADMIN.value,
                event.get("operators", [])
            )
        ))
    })
    if BaseObjectId(current_user.id) not in event_operators_ids:
        if room_result.get("owner.id") != BaseObjectId(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this room"
            )
    await db.virtual_rooms.delete_one({"_id": room_id})
    await db.events.update_one(
        {"_id": event.get("_id")},
        {
            "$pull": {"virtual_rooms": {"id": room_id}},
        }
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
