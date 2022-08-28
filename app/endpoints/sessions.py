"""
Sessions APIs
route: /sessions
"""

from datetime import datetime
from typing import List

from bson import ObjectId as BaseObjectId
from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core import depends
from app.core.events import check_and_calculate_time
from app.core.meetings import create_meeting
from app.core.utils import create_mongo_array_update
from app.schemas.base import ObjectId
from app.schemas.events import DiscountType, EventOperatorType
from app.schemas.meetings import MeetingProperty
from app.schemas.sessions import (
    SessionCreate,
    Session,
    SessionUpdate,
    SessionDataInEvent,
    SessionPartialUpdate,
    SessionFinancialSettingsOutput,
    SessionSettingInput
)
from app.schemas.users import User

router = APIRouter()


@router.post("", response_model=Session, status_code=status.HTTP_201_CREATED)
async def create_session(
        event_id: ObjectId,
        session: SessionCreate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Create session

    Authorization: required
    """

    event = await db.events.find_one(
        {
            "_id": event_id,
            "$or": [
                {"owner_id": BaseObjectId(current_user.id)},
                {
                    "operators": {"$elemMatch": {
                        "id": BaseObjectId(current_user.id),
                        "type": EventOperatorType.ADMIN
                    }}
                }
            ]
        },
        {"_id": 1, "sessions": 1, "owner_id": 1, "properties": 1, "starts_at": 1, "ends_at": 1}
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No event found with the given id"
        )

    if event.get("properties") and event.get("properties").get("session"):
        if not event.get("properties").get("session").get("active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This event cannot have stage"
            )
        if not event.get("properties").get("session").get("remaining_hours"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This event cannot have any more stage"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event cannot have stage"
        )

    if event.get("owner_id") and event.get("owner_id") != current_user.id and current_user.id not in list(
            map(lambda x: x.get("id"), event.get("operators"))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this event"
        )

    event_remaining_hours_change: int = await check_and_calculate_time(event, session, "session")

    now = datetime.now()
    session_data = {
        **session.dict(),
        "owner_id": current_user.id,
        "event_id": event_id,
        "created_at": now,
        "updated_at": now
    }

    session_result = await db.sessions.insert_one(session_data)

    if not session_result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create session"
        )

    session_data["id"] = session_result.inserted_id

    event_update = await db.events.find_one_and_update(
        {"_id": event_id},
        {
            "$set": {
                "sessions": [
                    *event.get("sessions"),
                    SessionDataInEvent.parse_obj(session_data).dict()
                ] if event.get("sessions") else [SessionDataInEvent.parse_obj(session_data).dict()]
            },
            "$inc": {"properties.session.remaining_hours": -event_remaining_hours_change}
        },
        projection={'properties.session.remaining_hours': 1}
    )
    remaining_hours = event_update.get('properties', {}).get('session', {}).get(
        'remaining_hours') - event_remaining_hours_change
    session_data = await create_meeting(db, session_data, MeetingProperty.sessions)

    return Session.parse_obj({**session_data, 'remaining_hours': remaining_hours})


@router.patch("/settings/{event_id}", response_model=SessionFinancialSettingsOutput)
async def session_financial_settings(
        event_id: ObjectId,
        session_setting: SessionSettingInput,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Update session settings

    Authorization: required
    """

    now = datetime.now()

    event_document = await db.events.find_one(
        {
            "_id": event_id,
            "$or": [
                {"owner_id": BaseObjectId(current_user.id)},
                {
                    "operators": {"$elemMatch": {
                        "id": BaseObjectId(current_user.id),
                        "type": EventOperatorType.ADMIN
                    }}
                }
            ],
            "properties.session.active": True
        },
        {
            "properties.session": 1
        }

    )
    if not event_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event not found"
        )

    data = {**session_setting.dict(exclude_unset=True), "updated_at": now}

    if session_setting.discount:
        discount = {
            **session_setting.dict().get('discount', {}),
            'event_id': event_id,
            'created_at': now,
            'updated_at': now,
            'owner_id': current_user.id,
            'type': DiscountType.SESSION.value,
        }
        insert_discount = await db.discounts.insert_one(discount)
        data['discount']['discount_id'] = insert_discount.inserted_id

    event_document = await db.events.find_one_and_update(
        {"_id": event_id},
        {
            "$set": {
                "properties.session.financial_settings": {
                    **data
                }
            }
        },
        return_document=ReturnDocument.AFTER
    )

    return event_document.get("properties").get("session").get("financial_settings")


@router.put("/{session_id}", response_model=Session)
async def update_session(
        session_id: ObjectId,
        session: SessionUpdate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Update session

    Authorization: required
    """

    now = datetime.now()

    session_document = await db.sessions.find_one({"_id": session_id})
    if not session_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No session found with the given id"
        )

    event_document = await db.events.find_one(
        {
            "_id": session_document.get("event_id"),
            "$or": [
                {"owner_id": BaseObjectId(current_user.id)},
                {
                    "operators": {"$elemMatch": {
                        "id": BaseObjectId(current_user.id),
                        "type": EventOperatorType.ADMIN
                    }}
                }
            ]
        },
        {"properties": 1, "starts_at": 1, "ends_at": 1, "_id": 1, "sessions": 1}
    )
    if not event_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No events found for this Stage"
        )

    remaining_hours_change = 0
    if session.ends_at and session.starts_at:
        remaining_hours_change = await check_and_calculate_time(
            event_document,
            session,
            "session",
            (session_document.get("ends_at") - session_document.get("starts_at")).total_seconds()
        )

    session_update_document = {
        **session.dict(),
        "updated_at": now
    }

    await db.sessions.update_one(
        {"_id": session_id},
        {"$set": session_update_document}
    )

    session_result = {
        **session_document,
        "updated_at": now,
        "id": session_document.get("_id")
    }
    session_result.update(session.dict())

    update_query = {
        "$set": {**create_mongo_array_update("sessions", SessionDataInEvent.parse_obj(session_result).dict())},
        "$inc": {"properties.session.remaining_hours": -remaining_hours_change}
    }

    await db.events.update_one(
        {"_id": session_result.get("event_id"), 'sessions.id': session_id},
        update_query
    )

    await db.meetings.update_one(
        {"_id": session_document.get("meeting")},
        {"$set": {"starts_at": session_result.get("starts_at"), "ends_at": session_result.get("ends_at")}}
    )

    return Session.parse_obj(
        {
            **session_result,
            'remaining_hours': event_document.get("properties").get("session").get(
                "remaining_hours") - remaining_hours_change
        }
    )


@router.patch("/{session_id}", response_model=Session)
async def partial_update_session(
        session_id: ObjectId,
        session: SessionPartialUpdate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Partial update session

    Authorization: required
    """

    now = datetime.now()

    session_document = await db.sessions.find_one({"_id": session_id})
    if not session_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No session found with the given id"
        )

    event_document = await db.events.find_one(
        {
            "_id": session_document.get("event_id"),
            "$or": [
                {"owner_id": BaseObjectId(current_user.id)},
                {
                    "operators": {"$elemMatch": {
                        "id": BaseObjectId(current_user.id),
                        "type": EventOperatorType.ADMIN
                    }}
                }
            ]
        },
        {"properties": 1, "starts_at": 1, "ends_at": 1, "_id": 1, "sessions": 1}
    )
    if not event_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No events found for this Stage"
        )

    remaining_hours_change = 0
    if session.ends_at and session.starts_at:
        remaining_hours_change = await check_and_calculate_time(
            event_document,
            session,
            "session",
            (session_document.get("ends_at") - session_document.get("starts_at")).total_seconds()
        )

    session_update_document = {
        **session.dict(exclude_unset=True),
        "updated_at": now
    }

    await db.sessions.update_one(
        {"_id": session_id},
        {"$set": session_update_document}
    )

    session_result = {
        **session_document,
        "updated_at": now,
        "id": session_document.get("_id")
    }
    session_result.update(session.dict(exclude_unset=True))

    update_query = {
        "$set": {**create_mongo_array_update("sessions", SessionDataInEvent.parse_obj(session_result).dict())},
        "$inc": {"properties.session.remaining_hours": -remaining_hours_change}
    }

    await db.events.update_one(
        {"_id": session_result.get("event_id"), 'sessions.id': session_id},
        update_query
    )

    await db.meetings.update_one(
        {"_id": session_document.get("meeting")},
        {"$set": {"starts_at": session_result.get("starts_at"), "ends_at": session_result.get("ends_at")}}
    )

    return Session.parse_obj(
        {
            **session_result,
            'remaining_hours': event_document.get("properties").get("session").get(
                "remaining_hours") - remaining_hours_change
        }
    )


@router.get("", response_model=List[Session])
async def get_sessions_list(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Get event's sessions

    Authorization: required
    """

    event_result = await db.events.find_one(
        {"_id": event_id},
        {"_id": 1, "sessions": 1, "operators": 1, "owner_id": 1}
    )

    if not event_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No session found with the given id"
        )

    if event_result.get("owner_id") != current_user.id and current_user.id not in list(
            map(lambda x: x.get("id"), event_result.get("operators"))
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session"
        )

    return event_result.get("sessions") if event_result.get("sessions") else []


@router.get("/{session_id}", response_model=Session)
async def get_session(
        session_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Get session

    Authorization: required
    """

    session_result = await db.sessions.find_one({"_id": session_id})

    if not session_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No session found with the given id"
        )

    event = await db.events.find_one(
        {"_id": session_result.get("event_id")},
        {"_id": 1, "sessions": 1, "owner_id": 1, "operators": 1}
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No event found for this session"
        )

    if session_result.get("owner_id") != current_user.id and current_user.id not in list(
            map(lambda x: x.get("id"), event.get("operators"))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session"
        )

    return Session.parse_obj({**session_result, "id": session_id})


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
        session_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Delete session

    Authorization: required
    """

    session_result = await db.sessions.find_one_and_delete({
        "_id": session_id,
        "$or": [{"owner_id": current_user.id}, {"operators.id": current_user.id}]
    })

    if not session_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session not found."
        )

    await db.events.update_one(
        {"_id": session_result.get("event_id")},
        {
            "$pull": {"sessions": {"id": session_id}},
            "$inc": {
                "properties.session.remaining_hours": (
                        session_result.get("ends_at").hour - session_result.get("starts_at").hour
                )
            }
        }
    )

    await db.meetings.delete_one(
        {"_id": session_result.get("meeting")}
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/settings/discount", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_discount(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Delete session discount

    Authorization: required
    """

    await db.events.update_one(
        {"_id": event_id,  "$or": [
                {"owner_id": BaseObjectId(current_user.id)},
                {
                    "operators": {"$elemMatch": {
                        "id": BaseObjectId(current_user.id),
                        "type": EventOperatorType.ADMIN
                    }}
                }
            ]},
        {"$unset": {"properties.session.financial_settings.discount": None}}

    )

    await db.discounts.delete_one({'event_id': event_id, 'type': DiscountType.SESSION.value})

    return Response(status_code=status.HTTP_204_NO_CONTENT)
