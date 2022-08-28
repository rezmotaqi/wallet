"""
Workshop rooms APIs
route: /workshops
"""

from datetime import datetime

from bson import ObjectId as BaseObjectId
from fastapi import APIRouter, Depends, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status

from app.core import depends
from app.core.events import check_access_to_event, check_and_calculate_time
from app.core.meetings import create_meeting
from app.core.uploads import move_image_from_temp
from app.core.utils import create_mongo_array_update, async_loop
from app.schemas.base import ObjectId
from app.schemas.events import DiscountType, EventOperatorType
from app.schemas.general import UserSchedule
from app.schemas.meetings import MeetingProperty
from app.schemas.users import User
from app.schemas.workshops import (
    WorkshopOut,
    WorkshopCreate,
    WorkshopDataInEvent,
    WorkshopUpdate,
    WorkshopListOut,
    WorkshopPartialUpdate,
    WorkshopFinancialSettingsInput,
    WorkshopFinancialSettingsOutput,
    WorkshopListClientOut,
    WorkShopUser,
    WorkShopFile,
    WorkshopExecutionData
)

router = APIRouter()


@router.post("", response_model=WorkshopOut, status_code=status.HTTP_201_CREATED)
async def create_workshop(
        event_id: ObjectId,
        workshop: WorkshopCreate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Create workshop

    Authorization: required
    """

    image_path, files = workshop.cover, workshop.files
    image_path = workshop.cover
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
        {"_id": 1, "workshops": 1, "owner_id": 1, 'properties': 1, 'starts_at': 1, 'ends_at': 1}
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No event found with the given id."
        )

    event_workshop_property = event.get("properties", {}).get("workshop", {})
    if event_workshop_property:
        if not event_workshop_property.get("active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This event cannot have workshop."
            )
        if not event_workshop_property.get("remaining_hours"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This event cannot have any more workshop."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event cannot have workshop."
        )

    event_remaining_hours_change: int = await check_and_calculate_time(event, workshop, "workshop")

    now = datetime.now()
    workshop = {
        **WorkshopCreate.parse_obj({**workshop.dict(exclude_unset=True, exclude_none=True)}).dict(),
        "owner_id": current_user.id,
        "event_id": event_id,
        "created_at": now,
        "updated_at": now,
        'participant_count': 0
    }

    workshop_result = await db.workshops.insert_one(workshop)

    if not workshop_result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create workshop."
        )

    workshop["id"] = workshop_result.inserted_id

    workshops = [
        *event.get("workshops"),
        WorkshopDataInEvent.parse_obj(workshop).dict()
    ] if event.get("workshops") else [WorkshopDataInEvent.parse_obj(workshop).dict()]

    event_update = await db.events.find_one_and_update(
        {"_id": event_id},
        {
            "$set": {"workshops": workshops},
            "$inc": {"properties.workshop.remaining_hours": -event_remaining_hours_change}
        },
        projection={'properties.workshop.remaining_hours': 1}
    )

    remaining_hours = event_update.get('properties', {}).get(
        'workshop', {}
    ).get('remaining_hours') - event_remaining_hours_change

    workshop = await create_meeting(db, workshop, MeetingProperty.workshops)

    if image_path:
        await move_image_from_temp(image_path)
    if files:
        await async_loop(move_image_from_temp, "path", files, True)

    return WorkshopOut.parse_obj(
        WorkshopOut.parse_obj({
            **workshop,
            'remaining_hours': remaining_hours,
            "id": workshop_result.inserted_id
        }).dict(exclude_unset=True, exclude_none=True)
    )


@router.get('', response_model=WorkshopListOut)
async def get_workshop_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId
):
    """
    User

    Get user event workshops

    Authorization: Required
    """

    event = await check_access_to_event(db, event_id, current_user, {'properties.workshop.remaining_hours': 1})
    remaining_hours = event.get('properties', {}).get(
        'workshop', {}
    ).get('remaining_hours')

    result = await db.workshops.find(
        {'event_id': event.get("_id")}
    ).to_list(length=None)
    result = result if result else []
    workshops = list(map(
        lambda x: WorkshopOut.parse_obj(
            WorkshopOut.parse_obj_id({
                **x,
                "remaining_hours": remaining_hours
            }).dict(exclude_none=True, exclude_unset=True)
        ),
        result
    ))
    return WorkshopListOut(count=len(result), workshops=workshops, remaining_hours=remaining_hours)


@router.patch("/settings/{workshop_id}", response_model=WorkshopFinancialSettingsOutput)
async def workshop_financial_settings(
        workshop_id: ObjectId,
        workshop_setting: WorkshopFinancialSettingsInput,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Update workshop settings

    Authorization: required
    """

    now = datetime.now()
    workshop = await db.workshops.find_one(
        {"_id": workshop_id},
        {'event_id': 1}
    )
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workshop found with the given id"
        )

    event_document = await db.events.find_one(
        {
            "_id": workshop.get('event_id'),
            "$or": [
                {"owner_id": BaseObjectId(current_user.id)},
                {
                    "operators": {"$elemMatch": {
                        "id": BaseObjectId(current_user.id),
                        "type": EventOperatorType.ADMIN
                    }}
                }
            ],
            "properties.workshop.active": True,
        },
        {'_id': 1}
    )
    if not event_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update event workshop settings"
        )

    data = {**workshop_setting.dict(exclude_unset=True), "updated_at": now}

    if workshop_setting.discount:
        discount = {
            **workshop_setting.dict().get('discount'),
            'event_id': workshop.get('event_id'),
            'created_at': now,
            'updated_at': now,
            'owner_id': current_user.id,
            'type': DiscountType.WORKSHOP.value,
            'workshop_id': workshop_id,
            'usage_count': 0

        } if workshop_setting.discount.use_count else {
            **workshop_setting.dict().get('discount'),
            'event_id': workshop.get('event_id'),
            'created_at': now,
            'updated_at': now,
            'owner_id': current_user.id,
            'type': DiscountType.WORKSHOP.value,
            'workshop_id': workshop_id,
        }

        insert_discount = await db.discounts.insert_one(discount)
        data['discount']['discount_id'] = insert_discount.inserted_id

    workshop_update = await db.workshops.update_one(
        {'_id': workshop_id},
        {"$set": {"financial_settings": data}},
    )

    event_update = await db.events.update_one(
        {"_id": workshop.get('event_id'), "workshops": {"$elemMatch": {'id': workshop_id}}},
        {"$set": {"updated_at": now, "workshops.$.financial_settings": data}}
    )

    if not workshop_update.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not update workshop."
        )
    if not event_update.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not update event."
        )

    return WorkshopFinancialSettingsOutput.parse_obj({**data, "updated_at": now})


@router.delete("/settings/discount/{event_id}/{workshop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workshop_discount(
        workshop_id: ObjectId,
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Delete workshop discount

    Authorization: required
    """

    event_update = await db.events.update_one(
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

    if event_update.matched_count < 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found. "
        )

    if not event_update.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not update event. "
        )

    await db.workshops.update_one(
        {'_id': workshop_id},
        {"$unset": {"financial_settings.discount": None}}
    )

    await db.discounts.delete_one(
        {'workshop_id': workshop_id, 'event_id': event_id, 'type': DiscountType.WORKSHOP.value}
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/execution/{workshop_id}", response_model=WorkshopExecutionData)
async def get_workshop_execution_data(
        workshop_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Get workshop execution page data

    Authorization: required
    """

    workshop_document = await db.workshops.find_one(
        {"_id": workshop_id},
        {"event_id": 1, 'files': 1}
    )
    if not workshop_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workshop found with the given id"
        )

    ws_invoices = await db.invoices.find(
        {
            'event_id': BaseObjectId(workshop_document.get('event_id')),
            '$or': [{'is_free': True}, {'is_paid': True}],
            'workshop_ids': BaseObjectId(workshop_id)
        },
        {'owner': 1}
    ).to_list(None)
    participants = list(map(lambda x: WorkShopUser.parse_obj(x.get('owner')), ws_invoices))

    user_document = await db.users.find_one({'_id': BaseObjectId(current_user.id)}, {'schedules': 1})
    if not user_document.get('schedules', []):
        user_document['schedules'] = []
    schedules = list(map(lambda x: UserSchedule.parse_obj(x), user_document.get('schedules')))

    resources = list(map(lambda x: WorkShopFile.parse_obj(x), workshop_document.get('files')))

    resource = {
        'resource': {'files': resources, 'count': len(resources)},
        'schedule': {'schedules': schedules, 'count': len(schedules)},
        'participant': {'participants': participants, 'count': len(participants)},

    }

    return WorkshopExecutionData.parse_obj(resource)


@router.get('/client/{event_id}', response_model=WorkshopListClientOut)
async def get_event_workshop_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
):
    """
    User

    Get event workshops for clients or admins

    Authorization: Required
    """

    event = await db.events.find_one({'_id': BaseObjectId(event_id)}, {'workshops': 1, 'operators': 1, 'owner_id': 1})

    event_invoices = await db.invoices.find(
        {
            'event_id': BaseObjectId(event_id),
            'owner.id': BaseObjectId(current_user.id),
            '$or': [{'is_paid': True}, {'is_free': True}]
        }
    ).to_list(length=None)

    event_operators = list({
        event.get("owner_id"),
        *list(map(
            lambda x: x.get("id"),
            filter(
                lambda x: x.get("type") == EventOperatorType.ADMIN.value or x.get(
                    "type") == EventOperatorType.TEACHER.value, event.get("operators", [])
            )
        ))
    })

    bought_ws_ids = []

    if event_invoices:
        for invoice in event_invoices:
            if invoice.get('workshop_ids'):
                bought_ws_ids = [*bought_ws_ids, *invoice.get('workshop_ids')]
            continue

    elif current_user.id in event_operators:
        workshops = event.get('workshops', [])
        for workshop in workshops:
            workshop['is_bought'] = True

        return WorkshopListClientOut(count=len(workshops), workshops=workshops)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have access to event."
        )

    workshops = event.get('workshops', [])
    for workshop in workshops:
        for invoice in event_invoices:
            if invoice.get('workshops'):
                for ws in invoice.get('workshops'):
                    if ws.get('id') == workshop.get('id'):
                        workshop['is_bought'] = True
                    else:
                        workshop['is_bought'] = False
            continue

    return WorkshopListClientOut(count=len(workshops), workshops=workshops)


@router.get("/{workshop_id}", response_model=WorkshopOut)
async def get_workshop(
        workshop_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Get workshop

    Authorization: required
    """

    workshop_result = await db.workshops.find_one({"_id": workshop_id})
    if not workshop_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workshop found with the given id"
        )

    event = await check_access_to_event(
        db,
        workshop_result.get("event_id"),
        current_user,
        {'properties.workshop.remaining_hours': 1}
    )
    remaining_hours = event.get('properties', {}).get(
        'workshop', {}
    ).get('remaining_hours')

    return WorkshopOut.parse_obj(
        WorkshopOut.parse_obj_id({
            **workshop_result,
            "remaining_hours": remaining_hours
        }).dict(exclude_unset=True, exclude_none=True)
    )


@router.delete("/{workshop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workshop(
        workshop_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Delete workshop room

    Authorization: required
    """

    workshop = await db.workshops.find_one({
        "_id": workshop_id
    })
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workshop found"
        )

    event_document = await db.events.find_one_and_update(
        {
            "_id": workshop.get("event_id"),
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
        {
            "$pull": {"workshops": {"id": workshop_id}},
            "$inc": {
                "properties.workshop.remaining_hours": (workshop.get("ends_at").hour - workshop.get("starts_at").hour)
            }
        },
        projection={"_id": 1}
    )
    if not event_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No event found for this workshop"
        )

    await db.workshops.delete_one({"_id": workshop_id})

    await db.meetings.delete_one(
        {"_id": workshop.get("meeting")}
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{workshop_id}", response_model=WorkshopOut)
async def update_workshop(
        workshop_id: ObjectId,
        workshop: WorkshopUpdate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Update workshop

    Authorization: required
    """

    workshop_document = await db.workshops.find_one({
        "_id": workshop_id
    })
    if not workshop_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workshop found with the given id"
        )

    event_document = await check_access_to_event(
        db,
        workshop_document.get("event_id"),
        current_user,
        {"_id": 1, "workshops": 1, 'starts_at': 1, 'ends_at': 1, 'properties': 1}
    )

    image_path, files = workshop.cover, workshop.files
    now = datetime.now()

    remaining_hours_change = 0
    if workshop.ends_at and workshop.starts_at:
        remaining_hours_change = await check_and_calculate_time(
            event_document,
            workshop,
            "workshop",
            (workshop_document.get("ends_at") - workshop_document.get("starts_at")).total_seconds()
        )

    await db.workshops.update_one(
        {"_id": workshop_id},
        {"$set": {
            **workshop.dict(),
            "updated_at": now
        }}
    )

    workshop_document.update({
        "updated_at": now,
        "id": workshop_document.get("_id"),
        **workshop.dict()
    })

    update_query = {
        "$set": {**create_mongo_array_update("workshops", WorkshopDataInEvent.parse_obj(workshop_document).dict())},
        "$inc": {"properties.workshop.remaining_hours": -remaining_hours_change}
    }

    await db.events.update_one(
        {"_id": workshop_document.get("event_id"), 'workshops.id': workshop_id},
        update_query
    )

    if image_path:
        await move_image_from_temp(image_path)
    if files:
        await async_loop(move_image_from_temp, "path", files, True)

    await db.meetings.update_one(
        {"_id": workshop_document.get("meeting")},
        {"$set": {"starts_at": workshop_document.get("starts_at"), "ends_at": workshop_document.get("ends_at")}}
    )

    return WorkshopOut.parse_obj(
        WorkshopOut.parse_obj({
            **workshop_document,
            'remaining_hours': event_document.get("properties").get("workshop").get(
                "remaining_hours") - remaining_hours_change
        }).dict(exclude_unset=True, exclude_none=True)
    )


@router.patch("/{workshop_id}", response_model=WorkshopOut)
async def partial_update_workshop(
        workshop_id: ObjectId,
        workshop: WorkshopPartialUpdate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Partial update workshop

    Authorization: required
    """

    workshop_document = await db.workshops.find_one({
        "_id": workshop_id
    })
    if not workshop_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workshop found with the given id"
        )

    event_document = await check_access_to_event(
        db,
        workshop_document.get("event_id"),
        current_user,
        {"_id": 1, "workshops": 1, 'starts_at': 1, 'ends_at': 1, 'properties': 1}
    )

    image_path, files = workshop.cover, workshop.files
    now = datetime.now()

    remaining_hours_change = 0
    if workshop.ends_at and workshop.starts_at:
        remaining_hours_change = await check_and_calculate_time(
            event_document,
            workshop,
            "workshop",
            (workshop_document.get("ends_at") - workshop_document.get("starts_at")).total_seconds()
        )

    await db.workshops.update_one(
        {"_id": workshop_id},
        {"$set": {
            **workshop.dict(exclude_unset=True),
            "updated_at": now
        }}
    )

    workshop_document.update({
        "updated_at": now,
        "id": workshop_document.get("_id"),
        **workshop.dict(exclude_unset=True)
    })

    update_query = {
        "$set": {**create_mongo_array_update("workshops", WorkshopDataInEvent.parse_obj(workshop_document).dict())},
        "$inc": {"properties.workshop.remaining_hours": -remaining_hours_change}
    }

    await db.events.update_one(
        {"_id": workshop_document.get("event_id"), 'workshops.id': workshop_id},
        update_query
    )

    if image_path:
        await move_image_from_temp(image_path)
    if files:
        await async_loop(move_image_from_temp, "path", files, True)

    await db.meetings.update_one(
        {"_id": workshop_document.get("meeting")},
        {"$set": {"starts_at": workshop_document.get("starts_at"), "ends_at": workshop_document.get("ends_at")}}
    )

    return WorkshopOut.parse_obj(
        WorkshopOut.parse_obj({
            **workshop_document,
            'remaining_hours': event_document.get("properties").get("workshop").get(
                "remaining_hours") - remaining_hours_change
        }).dict(exclude_unset=True, exclude_none=True)
    )
