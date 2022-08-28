"""
Events APIs
route: /events
"""
from datetime import datetime
from typing import Optional, List, Dict

from bson import ObjectId as BaseObjectId
from fastapi import APIRouter, Depends, HTTPException, Response, Body
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateMany, UpdateOne
from pymongo.errors import DuplicateKeyError
from starlette import status
from starlette.responses import JSONResponse

from app.core import depends
from app.core.accountant import calculate_event_price
from app.core.events import (
    generate_uuid,
    validate_create_code_discount,
    calculate_session_cost,
    check_event_publish_ready,
    calculate_workshops_invoice_data, validate_invoice_discount, validate_total_cost_discount, check_access_to_event,
    get_or_create_event_operator
)
from app.core.uploads import move_image_from_temp
from app.core.utils import create_mongo_array_update, async_loop
from app.schemas.base import ObjectId
from app.schemas.events import (
    EventsCreate,
    EventCategoriesCreate,
    EventsOutInList,
    EventsOutList,
    EventUpdate,
    EventCategoryOut,
    EventCategoryListOut,
    EventPrivacy,
    DiscountCreate,
    DiscountInListOut,
    DiscountListOut,
    DiscountPartialUpdate,
    EventPreviewAnonymousOut,
    EventPreviewAnonymousListOut,
    EventPreviewOut,
    EventPreviewListOut,
    ParticipantInListOut,
    ParticipantListOut,
    EventSessionSpeakerInListOut,
    EventOperatorType,
    Events,
    EventSponsorsInList,
    EventSessionSpeakerPartialUpdate,
    EventCreateOut,
    EventCreateCostCalculationOut,
    EventCreateCostCalculation,
    EventSponsorOut,
    EventsSort,
    EventCreatorDataInPreview,
    InvoiceType,
    UserSchedule,
    EventOperatorListOut,
    EventOperator,
    EventOperatorCreate,
    EventParticipant,
    AddEventBookmark,
    EventBookmarkListOut,
    EventBookmarkOutInList,
    AdminParticipantListOut,
    DiscountType
)
from app.schemas.general import ConnectionStatus, Roles
from app.schemas.users import User

router = APIRouter()


@router.post('/category')
async def admin_create_event_category(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        data: EventCategoriesCreate
):
    """
    Admin

    Create event category

    Authorization: required
    """

    now = datetime.now()
    data = {**data.dict(), 'created_at': now, 'updated_at': now}
    result = await db.event_categories.insert_one(data)

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create event category. "
        )

    return Response(status_code=status.HTTP_201_CREATED)


@router.get('/category')
async def get_category_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
):
    """
    User

    Get event categories

    Authorization: Required
    """
    result = await db.event_categories.find(
    ).skip(offset * limit).to_list(length=limit)
    categories = list(map(lambda x: (EventCategoryOut.parse_obj_id({**x})), result))
    count = await db.event_categories.count_documents({})
    return EventCategoryListOut(count=count, categories=categories)


@router.post('/cost', response_model=EventCreateCostCalculationOut)
async def calculate_event_cost(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: EventCreateCostCalculation
):
    """
    User

    Calculate event cost based on selected properties

    Authorization: Required
    """

    data = data.dict()
    session_max = data.get('session').get('max_participants') if data.get('session') else 0
    session_hours = data.get('session').get('hours') if data.get('session') else 0
    workshop_max = data.get('workshop').get('max_participants') if data.get('workshop') else 0
    workshop_hours = data.get('workshop').get('hours') if data.get('workshop') else 0

    calculation_result = await calculate_event_price(
        session_participants=session_max,
        session_hours=session_hours,
        workshop_hours=workshop_max,
        workshop_participants=workshop_hours
    )

    return EventCreateCostCalculationOut.parse_obj(calculation_result)


@router.get("/client")
async def get_my_events(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
):
    """
    User

    Get user participated(registered) events

    Authorization: Required
    """

    invoices = await db.invoices.find(
        {'owner.id': BaseObjectId(current_user.id), '$or': [{'is_free': True}, {'is_paid': True}]},
        {'event_id': 1}
    ).to_list(length=None)

    events_ids = list(set(list(map(lambda x: x.get("event_id"), invoices or []))))

    events = await db.events.find(
        {'_id': {'$in': events_ids}},
        {
            'name': 1,
            'category': 1,
            'starts_at': 1,
            'ends_at': 1,
            'cover': 1,
            'is_published': 1
        }
    ).skip(offset * limit).to_list(length=limit)

    events = list(map(lambda x: (EventsOutInList.parse_obj({**x, 'id': x.get('_id')})), events))
    return EventsOutList(count=len(events_ids), events=events)


@router.get('/client/explore')
async def get_events_explore(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.get_current_user_or_anonymous_user),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        sort: EventsSort = EventsSort.CREATED_AT.value
):
    """
    Anonymous  and Authenticated User

    Get Published events

    Authorization: Not required
    """

    now = datetime.now()
    sort = {sort: 1} if sort[0] != "-" else {sort[1:]: -1}

    result = await db.events.find(
        {
            "$query": {'is_published': True, 'ends_at': {'$gt': now}},
            "$orderby": sort
        },
        {
            '_id': 1,
            'description': 1,
            'cover': 1,
            'sponsors': 1,
            'host': 1,
            'is_bought': 1,
            'name': 1,
            'starts_at': 1,
            'ends_at': 1,
            'properties': 1,
            'sessions': 1,
            'workshops': 1,
            'creator': 1,
            'participants': 1
        }
    ).skip(offset * limit).to_list(length=limit)

    count = await db.events.count_documents({'is_published': True, 'ends_at': {'$gt': now}})

    if current_user:
        invoices = await db.invoices.find(
            {'$or': [{'is_free': True}, {'is_paid': True}], 'owner.id': BaseObjectId(current_user.id)},
            {'event_id': 1, '_id': 0}
        ).to_list(length=None)

        invoices = list(map(lambda x: x.get('event_id'), invoices))

        bookmarks_document = await db.event_bookmarks.find_one(
            {'owner_id': BaseObjectId(current_user.id)},
            {'bookmarks': 1, '_id': 0}
        )
        bookmarks = bookmarks_document.get('bookmarks') if bookmarks_document else []
        bookmarks = list(map(lambda x: x.get('id'), bookmarks))
        events = list(map(
            lambda x: (EventPreviewOut.parse_obj_id(
                {
                    **x,
                    'is_bought': True if x.get('_id') in invoices else False,
                    'is_bookmarked': True if x.get('_id') in bookmarks else False
                })),
            result
        ))
        return EventPreviewListOut(count=count, events=events)

    else:
        events = list(map(lambda x: (EventPreviewAnonymousOut.parse_obj_id({**x})), result))
        return EventPreviewAnonymousListOut(count=count, events=events)


@router.post("")
async def create_event(
        data: EventsCreate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Create event

    Authorization: required
    """

    now = datetime.now()

    event_owner = await db.users.find_one(
        {'_id': BaseObjectId(current_user.id)},
        {'basic_info': 1, '_id': 1}
    )

    if not event_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found."
        )

    creator = EventCreatorDataInPreview.parse_obj(
        {
            'id': event_owner.get('_id'),
            'first_name': event_owner.get('basic_info', {}).get('first_name'),
            'last_name': event_owner.get('basic_info', {}).get('last_name'),
            'avatar': event_owner.get('basic_info', {}).get('avatar')
        }
    )

    data = {
        **data.dict(exclude_unset=True),
        'created_at': now,
        'updated_at': now,
        'owner_id': current_user.id,
        'is_published': False,
        'creator': creator.dict()
    }

    if data.get("properties"):
        if data.get("properties").get("session"):
            data["properties"]["session"]["hours"] = data["properties"]["session"]["hours"] * 3600
            data["properties"]["session"]["remaining_hours"] = data["properties"]["session"]["hours"]

        if data.get("properties").get("workshop"):
            data["properties"]["workshop"]["hours"] = data["properties"]["workshop"]["hours"] * 3600
            data["properties"]["workshop"]["remaining_hours"] = data["properties"]["workshop"]["hours"]

    result = await db.events.insert_one(data)

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create event"
        )

    return EventCreateOut.parse_obj_id(data)


@router.get("")
async def get_event_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
):
    """
    User

    Get user events

    Authorization: Required
    """
    result = await db.events.find(
        {'owner_id': current_user.id},
        {
            'name': 1,
            'category': 1,
            'starts_at': 1,
            'ends_at': 1,
            'cover': 1,
            'is_published': 1

        }
    ).skip(offset * limit).to_list(length=limit)
    events = list(map(lambda x: (EventsOutInList.parse_obj({**x, 'id': x.get('_id'), })), result))
    count = await db.events.count_documents({'owner_id': current_user.id})
    return EventsOutList(count=count, events=events)


@router.get('/client/{event_id}')
async def pre_initialize(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId
):
    """
    User

    Check if user has access to event

    1-User is system admin,
    2-User owns the event,
    3-User is event admin,

    If none of the above conditions are true then all the following conditions must be true:
        1-User has bought ticket,
        2-Whether or not event is finished,
        3-Whether or not event has started,
        4-Whether or not event is published

    Authorization: Required
    """
    now = datetime.now()
    result = await db.events.find_one({'_id': event_id}, {'starts_at': 1, 'ends_at': 1, 'privacy': 1, 'owner_id': 1, 'admins': 1, 'is_published': 1})

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event does not exist. ")

    is_system_admin = Roles.ADMIN.value in current_user.role
    is_event_owner = current_user.id == result.get('owner_id')
    is_event_admin = current_user.id in result.get('admins') if result.get('admins') else []

    if any([is_system_admin, is_event_owner, is_event_admin]):
        return {'has_access': True}
    if result.get('starts_at') > now or result.get('ends_at') < now or not result.get('is_published'):
        return {'has_access': False}
    if result.get('privacy') == EventPrivacy.PRIVATE:
        result = await db.friends.find_one(
            {'$or': [
                {'requested_id': current_user.id, 'requester_id': result.get('owner_id')},
                {'requester_id': current_user.id, 'requested_id': result.get('owner_id')}
            ],
             'status': ConnectionStatus.CONNECTED.value},
            {'_id': 1}
        )

        if not result:
            return {'has_access': False}
    result = await db.invoices.find_one(
        {'$or': [
            {'is_paid': True},
            {'is_free': True}
        ],
         'owner.id': current_user.id,
         'event_id': event_id
         }
    )

    return {'has_access': True} if result else {'has_access': False}


@router.post('/discount/{event_id}/{discount_code}', response_model=bool)
async def check_discount_code_availability(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        discount_code: str
):
    discount_code = await db.discounts.find_one({
        "event_id": event_id, "code": discount_code
    })
    return bool(discount_code)


@router.post('/discount/{event_id}')
async def create_discount(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: DiscountCreate,
        event_id: ObjectId
):
    """
    User

    Create event discount

    Authorization: required
    """

    now = datetime.now()
    data = {
        **data.dict(),
        'created_at': now,
        'updated_at': now,
        'event_id': event_id,
        'owner_id': current_user.id,
        'usage_count': 0
    }

    # validate discount with event data `
    event = await db.events.find_one(
        {'_id': event_id, 'owner_id': current_user.id},
        {'properties': 1, 'starts_at': 1, 'ends_at': 1}
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found. "
        )

    (is_valid, error) = await validate_create_code_discount(event=event, discount=data)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    try:
        discount_result = await db.discounts.insert_one(data)
    except DuplicateKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount code is already used.") from e


    return Response(status_code=status.HTTP_201_CREATED)


@router.get('/discount/{event_id}')
async def get_discount_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId
):
    """
    User

    Get user event discounts

    Authorization: Required
    """

    result = await db.discounts.find(
        {'event_id': event_id, 'owner_id': BaseObjectId(current_user.id)}
    ).to_list(length=None)
    result = result if result else []
    discounts = list(map(
        lambda x: DiscountInListOut.parse_obj(x),
        filter(lambda x: x.get("type") == DiscountType.CODE.value, result)))
    count = await db.discounts.count_documents(
        {'event_id': event_id, 'owner_id': BaseObjectId(current_user.id), 'type': DiscountType.CODE.value}
    )
    return DiscountListOut(count=count, discounts=discounts)


@router.delete('/discount/{event_id}/{discount_code}')
async def delete_event_discount(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        discount_code: str
) -> Response:
    """
    User

    Delete user event discount

    Authorization: Required
    """

    result = await db.discounts.delete_one(
        {'event_id': event_id, 'owner_id': current_user.id, 'code': discount_code}
    )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not delete discount. "
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/discount/{event_id}/{discount_code}')
async def partial_update_discount(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        data: DiscountPartialUpdate,
        discount_code: str
) -> Response:
    """
    User

    Partial Update event discount

    Authorization: Required
    """

    result = await db.discounts.update_one(
        {'event_id': event_id, 'owner_id': current_user.id, 'code': discount_code},
        {"$set": data.dict(exclude_unset=True)}
    )

    if result.matched_count < 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found. "
        )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not update event. "
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/client/register/{event_id}')
async def register_in_event(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        session: Optional[bool] = Body(default=False),
        workshops: Optional[List[ObjectId]] = Body(default=[]),
        discount_code: Optional[str] = Body(default=None)
):
    """
    User

    initiates event registration:

    1- creates invoice with paid=False and appropriate access to event properties
    2- calls ipg and returns ipg link

    Authorization: Required
    """

    if not session and not workshops:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must at least buy one property."
        )

    now = datetime.now()
    user = await db.users.find_one(
        {'_id': current_user.id},
        {
            '_id': 1,
            'basic_info': 1,
            'user_type': 1,
            'username': 1,
            'contact_info': 1
        }
    )

    user = EventParticipant.parse_obj({
        **user,
        "id": user.get("_id"),
        "company_name": user.get('basic_info', {}).get('company_name'),
        "first_name": user.get('basic_info', {}).get('first_name'),
        "last_name": user.get('basic_info', {}).get('last_name'),
        "avatar": user.get('basic_info', {}).get('avatar'),
        "headline": user.get('basic_info', {}).get('headline'),
        "website": user.get('contact_info', {}).get('website')
    }).dict(exclude_none=True, exclude_unset=True)

    event = await db.events.find_one(
        {'_id': event_id},
        {
            'starts_at': 1,
            'ends_at': 1,
            'privacy': 1,
            'owner_id': 1,
            'admins': 1,
            'is_published': 1,
            'ticket': 1,
            'sessions': 1,
            'workshops': 1,
            'properties': 1,
            'description': 1,
            'cover': 1,
            'name': 1
        }
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event does not exist. "
        )

    # check if current user is system admin
    is_system_admin = Roles.ADMIN.value in current_user.role
    # check if current user owns the event
    is_event_owner = current_user.id == event.get('owner_id')
    # check if current user is event admin
    is_event_admin = current_user.id in event.get('admins') if event.get('admins') else False
    if any([is_system_admin, is_event_owner, is_event_admin]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin user can not register in this event")

    # check if event has started and has not finished and is published
    if not event.get('starts_at') < now < event.get('ends_at') or not event.get('is_published'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event has not started or it is ended or it is not published yet. "
        )

    # check if private event is accessible by user
    if event.get('privacy') == EventPrivacy.PRIVATE:
        friends_result = await db.friends.find_one(
            {
                '$or': [
                    {
                        'requested_id': current_user.id,
                        'requester_id': event.get('owner_id')
                    },
                    {
                        'requester_id': current_user.id,
                        'requested_id': event.get('owner_id')
                    }],
                'status': ConnectionStatus.CONNECTED.value
            },
            {'_id': 1}
        )
        if not friends_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You don not have access to this event. "
            )

    # check if event has session and provided workshop

    if session and not event.get('properties').get('session', {}).get('active'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided event does not have session."
        )

    if workshops and not event.get('properties').get('workshop', {}).get('active'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided event does not have workshop."
        )

    buying_ws = []
    available_ws_ids = []
    if workshops:
        for buying_ws_id in workshops:
            for ws in event.get('workshops'):
                if BaseObjectId(ws.get('id')) == BaseObjectId(buying_ws_id):
                    buying_ws.append(ws)
                    available_ws_ids.append(ws.get('id'))

    for ws_id in workshops:
        if ws_id not in available_ws_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workshop with {ws_id} as id, does not exist."
            )

    # check if any workshops are bought or session is bought
    # get all invoices for this user and event (for both free and not free events, invoice is created)
    invoice_list = await db.invoices.find(
        {'$or': [{'is_paid': True}, {'is_free': True}], 'owner.id': current_user.id, 'event_id': event_id}
    ).to_list(length=None)

    bought_ws = []
    bought_session = False

    if invoice_list:
        for buying_ws_id in workshops:
            for invoice in invoice_list:
                if invoice.get('session') and session:
                    bought_session = True
                if invoice.get('workshops'):
                    if buying_ws_id in list(map(lambda x: x.get('id'), invoice.get('workshops'))):
                        bought_ws.append(str(buying_ws_id))
                else:
                    continue
    else:
        pass

    bought_properties = {
        'workshops': bought_ws,
        'session': bought_session
    }

    if bought_ws or bought_session:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=
            {
                'bought_property': bought_properties,
                'message': "User has already bought the provided properties."
            }

        )

    # create and complete invoice

    invoice = {
        'type': InvoiceType.EVENT_PARTICIPANT.value,
        'created_at': now,
        'updated_at': now,
        'owner': user,
        'event_id': event_id,
        'is_paid': True,
        'is_free': False,
        'event_name': event.get('name'),
        'event_cover': event.get('cover'),
        'event_description': event.get('description'),
        'total_cost': 0
    }

    event_update_query = {
        '$addToSet': {'participants': user}
    }

    applied_discounts_ids = []

    if session:
        session_calculation_response: Dict = await calculate_session_cost(
            event.get('properties').get('session')
        )
        session = {
            **session_calculation_response,
            "price": event.get('properties').get('session').get('financial_settings').get('price')
        }
        if session.get('applied_discount'):
            session['discount_id'] = event.get('properties').get('session').get('financial_settings').get(
                'discount').get('discount_id')

        increase_dict = {}
        if session.get('increase_usage_count'):
            increase_dict.update({'properties.session.financial_settings.discount.usage_count': 1})

            # add discount id to applied_discounts_ids to use to update discounts collection
            applied_discounts_ids.append(session.get('discount_id'))

        invoice = {**invoice, 'session': session, 'total_cost': session.get('cost')}
        increase_dict.update({'properties.session.participant_count': 1})

        if increase_dict:
            event_update_query.update({"$inc": increase_dict})

    calculated_ws_ids = []
    inc_usage_ws_ids = []
    if buying_ws:
        # below variables are returned as List[Dict], int, List[ObjectId], List[ObjectId], List[ObjectId]
        ws_calculation_response, total_ws_cost, calculated_ws_ids, discount_ids, inc_usage_ws_ids = \
            await calculate_workshops_invoice_data(buying_ws)

        applied_discounts_ids = [*applied_discounts_ids, *discount_ids]

        invoice = {
            **invoice,
            'workshops': ws_calculation_response,
            'total_cost': invoice.get('total_cost', 0) + total_ws_cost,
            'workshop_ids': calculated_ws_ids
        }

        # increase participant_count for every work shop to update event document
        # increase usage_count for workshops that discount has been used for them
        updated_workshops = event.get('workshops')
        for ws in updated_workshops:
            if ws.get('id') in calculated_ws_ids:
                ws['participant_count'] += 1
            if ws.get('id') in inc_usage_ws_ids:
                ws['financial_settings']['discount']['usage_count'] += 1

        event_update_query.update({'$set': {'workshops': updated_workshops}})

    # calculate code discount if provided
    if discount_code:
        invoice = await validate_invoice_discount(db, discount_code, invoice)

    invoice_is_free = invoice.get('total_cost') == 0
    invoice = {**invoice, 'is_free': invoice_is_free}

    await db.invoices.insert_one(invoice)

    # if invoice_is_free:
    await db.events.update_one(
        {'_id': event_id},
        event_update_query
    )

    await db.discounts.update_many(
        {'_id': {'$in': applied_discounts_ids}},
        {'$inc': {'usage_count': 1}}
    )

    await db.workshops.bulk_write([
        UpdateMany({'_id': {'$in': calculated_ws_ids}}, {'$inc': {'participant_count': 1}}),
        UpdateMany({'_id': {'$in': inc_usage_ws_ids}}, {'$inc': {'financial_settings.discount.usage_count': 1}})
    ])
    return Response(status_code=status.HTTP_200_OK, content="User is successfully registered in event.")

    # else:
    # TODO save all the calculated data in another collection and use that data to do update after verification

    # invoice_id = invoice_result.inserted_id
    # ipg_link = None
    # return Response(status_code=status.HTTP_200_OK, content=f" redirect to ipg link {ipg_link}")


@router.post('/client/verify/{invoice_id}')
async def verify_payment():
    """
    IPG

    call ipg to verify incoming data,
    update database,
    redirect to specific route after
    """

    # TODO increase max_participant of event and used discount
    pass


@router.get('/client/preview/{event_id}')
async def get_event_preview(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.get_current_user_or_anonymous_user),
        event_id: ObjectId
):
    """
    Anonymous and Authenticated User

    Return event preview page data

    Authorization: Not required
    """

    event = await db.events.find_one(
        {'_id': event_id},
        {
            '_id': 1,
            'starts_at': 1,
            'ends_at': 1,
            'properties': 1,
            'name': 1,
            'host': 1,
            'sponsors': 1,
            'cover': 1,
            'description': 1,
            'operators': 1,
            'schedule': 1,
            'hosts': 1,
            'workshops': 1,
            'sessions': 1,
            'owner_id': 1,
            'participants': 1
        }
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event was not found. "
        )

    event_owner = await db.users.find_one(
        {'_id': event.get('owner_id')},
        {'basic_info': 1, '_id': 1}
    )
    creator = EventCreatorDataInPreview.parse_obj(
        {
            'id': event_owner.get('_id'),
            'first_name': event_owner.get('basic_info', {}).get('first_name'),
            'last_name': event_owner.get('basic_info', {}).get('last_name'),
            'avatar': event_owner.get('basic_info', {}).get('avatar')
        }
    )

    event['speakers'] = list(map(
        lambda x: EventSessionSpeakerInListOut.parse_obj({**x, 'id': x.get('id')}),
        filter(lambda x: x.get('type') == EventOperatorType.SPEAKER.value, event.get('operators', []))
    ))

    event['creator'] = creator

    if current_user:
        invoice = await db.invoices.find(
            {'$or': [{'is_free': True}, {'is_paid': True}], 'owner.id': current_user.id, 'event_id': event_id}, {'_id'}
        ).to_list(length=None)
        is_bought = True if invoice or (
                BaseObjectId(current_user.id) == event.get('owner_id') or BaseObjectId(current_user.id) in
                event.get('operators', [])
        ) else False

        bookmarks_document = await db.event_bookmarks.find_one(
            {'owner_id': BaseObjectId(current_user.id)},
            {'bookmarks': 1, '_id': 0}
        )
        bookmarks = bookmarks_document.get('bookmarks') if bookmarks_document else []
        is_bookmarked = event_id in list(map(lambda x: x.get('id'), bookmarks))

        return EventPreviewOut.parse_obj(
            EventPreviewOut.parse_obj_id(
                {
                    **event,
                    'is_bought': is_bought,
                    'is_bookmarked': is_bookmarked
                }).dict(exclude_none=True)
        )
    else:
        return EventPreviewAnonymousOut.parse_obj(
            EventPreviewAnonymousOut.parse_obj_id(event).dict(exclude_none=True)
        )


@router.delete('/{event_id}')
async def delete_event(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId
) -> Response:
    """
    User

    Delete user event

    Authorization: Required
    """

    result = await db.events.find_one_and_delete({'_id': event_id, 'owner_id': BaseObjectId(current_user.id)})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not delete event"
        )
    await db.sessions.delete_many({"event_id": result.get("_id")})
    await db.workshops.delete_many({"event_id": result.get("_id")})

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put('/{event_id}')
async def update_event(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        data: EventUpdate

) -> Response:
    """
    User

    Update event

    Authorization: Required
    """

    if data.is_published:
        event_document = await db.events.find_one(
            {
                '_id': event_id,
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
            {'properties': 1, 'workshops': 1}
        )

        if not await check_event_publish_ready(event_document):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event settings are not complete."
            )

    if data.sponsors:
        await async_loop(move_image_from_temp, "logo", data.sponsors, True)
    if data.hosts:
        await async_loop(move_image_from_temp, "logo", data.hosts, True)
    if data.cover:
        await move_image_from_temp(data.cover)

    data = {**data.dict(), 'updated_at': datetime.now()}
    if data.get("schedule"):
        data["schedule"] = list(map(
            lambda x: {
                **x,
                "details": list(map(lambda y: {**y, "id": y.get("id", generate_uuid())}, x.get("details", [])))
            },
            data.get("schedule")
        ))
    if data.get('sponsors'):
        data["sponsors"] = list(map(lambda x: {**x, "id": x.get("id", generate_uuid())}, data.get("sponsors")))

    result = await db.events.update_one(
        {
            '_id': event_id,
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
        {"$set": data}
    )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not delete event. "
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/{event_id}')
async def partial_update_event(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        data: EventUpdate
) -> Response:
    """
    User

    Partial Update event

    Authorization: Required
    """

    if data.is_published:
        event_document = await db.events.find_one(
            {
                '_id': event_id,
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
            {'properties': 1, 'workshops': 1}
        )

        if not await check_event_publish_ready(event_document):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event settings are not complete."
            )

    if data.sponsors:
        await async_loop(move_image_from_temp, "logo", data.sponsors, True)
    if data.hosts:
        await async_loop(move_image_from_temp, "logo", data.hosts, True)
    if data.cover:
        await move_image_from_temp(data.cover)

    data = {**data.dict(exclude_none=True), 'updated_at': datetime.now()}
    if data.get("schedule"):
        data["schedule"] = list(map(
            lambda x: {
                **x,
                "details": list(map(lambda y: {**y, "id": y.get("id", generate_uuid())}, x.get("details", [])))
            },
            data.get("schedule")
        ))
    if data.get('sponsors'):
        data["sponsors"] = list(map(lambda x: {**x, "id": x.get("id", generate_uuid())}, data.get("sponsors")))

    result = await db.events.update_one(
        {
            '_id': event_id,
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
        {"$set": data}
    )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not delete event. "
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/participants/{event_id}', response_model=AdminParticipantListOut)
async def get_event_participants(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20
):
    """
    User

    Get event participants

    Authorization: Not required
    """

    event = await check_access_to_event(db, event_id, current_user)

    event_invoices = db.invoices.aggregate([
        {
            '$match': {"event_id": event_id, '$or': [{'is_paid': True}, {'is_free': True}]}
        },
        {
            '$group': {
                '_id': "$owner.id",
                'total_cost': {'$sum': '$total_cost'},
                'stage_object': {"$mergeObjects": "$session"},
                'workshop_objects': {"$push": {"$concatArrays": "$workshops"}},
                'register_date': {"$min": "$created_at"}
            }
        },
        {
            "$facet": {
                "participants": [
                    {
                        "$lookup": {
                            "from": "users",
                            "localField": "_id",
                            "foreignField": "_id",
                            "pipeline": [
                                {
                                    "$project": {
                                        "id": "$_id",
                                        "first_name": "$basic_info.first_name",
                                        "last_name": "$basic_info.last_name",
                                        "company_name": "$basic_info.company_name",
                                        "user_type": "$user_type",
                                        "headline": "$basic_info.headline",
                                        "avatar": "$basic_info.avatar"
                                    }
                                }
                            ],
                            "as": "owner"
                        }
                    },
                    {
                        "$replaceRoot": {"newRoot": {"$mergeObjects": [{"$arrayElemAt": ["$owner", 0]}, "$$ROOT"]}}
                    },
                    {
                        "$set": {
                            "workshop_objects": {
                                "$filter": {
                                    "input": {
                                        "$reduce": {
                                            "input": "$workshop_objects",
                                            "initialValue": [],
                                            "in": {"$concatArrays": ["$$value", "$$this"]}
                                        }
                                    },
                                    "cond": {"$ne": ["$$this", "None"]}
                                }
                            }
                        }
                    },
                    {
                        "$set": {
                            "stage": {
                                "$cond": {
                                    "if": {"$ne": ["$stage_object", None]},
                                    "then": True,
                                    "else": False
                                }
                            },
                            "workshop": {
                                "$cond": {
                                    "if": {"$ne": ["$workshop_objects", None]},
                                    "then": True,
                                    "else": False
                                }
                            }
                        }
                    },
                    {
                        "$skip": offset * limit
                    },
                    {
                        "$limit": limit
                    }
                ],
                "count": [
                    {
                        "$count": 'count'
                    }
                ]
            }
        }
    ])

    event_invoices = [invoice async for invoice in event_invoices]
    if event_invoices[0].get("participants"):
        return AdminParticipantListOut(
            count=event_invoices[0].get("count")[0].get("count"),
            participants=event_invoices[0].get("participants")
        )
    return AdminParticipantListOut()


@router.get('/client/participants/{event_id}')
async def get_event_participants_client(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        event_id: ObjectId
):
    """
    Anonymous User

    Get event participants

    Authorization: Not required
    """

    now = datetime.now()
    result = await db.events.find_one(
        {'is_published': True, 'ends_at': {'$gt': now}, '_id': event_id},
        {'participants': {'$slice': -20}}
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found. "
        )

    return ParticipantListOut(participants=list(map(
        lambda x: ParticipantInListOut.parse_obj(x), result.get('participants', [])
    )))


@router.post('/schedule/{event_id}', response_model=List[UserSchedule])
async def add_schedule(
        event_id: ObjectId,
        data: Optional[List[UserSchedule]] = Body([]),
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """
    User

    Add schedule for event

    Authorization: Required
    """

    data = list(map(lambda x: {**x.dict(), "event_id": event_id}, data))

    event = await db.events.find_one(
        {
            '_id': event_id,
        },
        {'_id': 1}
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event was not found."
        )

    users_requests = [
        UpdateOne(
            {'_id': BaseObjectId(current_user.id)},
            {'$pull': {"schedules": {"event_id": event_id}}}
        )
    ]
    if data:
        users_requests.append(
            UpdateOne(
                {'_id': BaseObjectId(current_user.id)},
                {'$addToSet': {'schedules': {"$each": data}}}
            )
        )
    await db.users.bulk_write(users_requests)

    return data


@router.get('/schedule/{event_id}', response_model=List[UserSchedule])
async def get_schedule(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """
    User

    Add schedule for event

    Authorization: Required
    """

    event = await db.events.find_one(
        {
            '_id': event_id,
        },
        {'_id': 1}
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event was not found."
        )

    user = await db.users.find_one(
        {"_id": BaseObjectId(current_user.id)},
        {"schedules": 1}
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User was not found."
        )

    return list(map(
        lambda x: UserSchedule.parse_obj(x),
        filter(lambda x: x.get("event_id") == event_id, user.get("schedules", []))
    ))


@router.post('/admin/{event_id}', response_model=EventOperator)
async def add_admin(
        event_id: ObjectId,
        data: EventOperatorCreate,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User
    
    Add admin for event
    
    Authorization: Required
    """

    event = await check_access_to_event(db, event_id, current_user, only_owner=True)

    image_path = data.avatar

    operator_user = await get_or_create_event_operator(
        db,
        EventOperatorType.ADMIN,
        data.dict(exclude_unset=True, exclude_none=True)
    )

    operator_exists = list(filter(
        lambda x: x.get("id") == operator_user.get("id") and operator_user.get(
            "type") == x.get("type"),
        event.get("operators", [])
    ))

    if operator_exists:
        await db.events.update_one(
            {
                '_id': event.get("_id"),
                "operators": {"$elemMatch": {
                    "id": operator_user.get("id"), "type": EventOperatorType.ADMIN
                }}
            },
            {'$set': {**create_mongo_array_update("operators", operator_user)}}
        )

    else:
        await db.events.update_one(
            {'_id': event.get("_id")},
            {'$addToSet': {'operators': operator_user}}
        )

    if image_path:
        await move_image_from_temp(image_path)

    return operator_user


@router.get('/admin/{event_id}', response_model=EventOperatorListOut)
async def get_admins(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
):
    """
    User

    Get event admins

    Authorization: Required
    """

    event = await check_access_to_event(db, event_id, current_user, only_owner=True)

    admins = list(map(
        lambda x: EventOperator.parse_obj(x),
        filter(lambda x: x.get("type") == EventOperatorType.ADMIN.value, event.get("operators", []))
    ))
    return EventOperatorListOut(operators=admins, count=len(admins))


@router.delete('/admin/{event_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin(
        event_id: ObjectId,
        operator_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Delete event admins

    Authorization: Required
    """

    event = await check_access_to_event(db, event_id, current_user, only_owner=True)
    await db.events.update_one(
        {
            '_id': event.get("_id")
        },
        {
            '$pull': {'operators': {
                "id": operator_id,
                "type": EventOperatorType.ADMIN
            }}
        }
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/speaker/{event_id}', response_model=EventOperator)
async def create_speaker(
        data: EventOperatorCreate,
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Create session speaker

    Authorization: Required
    """

    event = await check_access_to_event(db, event_id, current_user)

    image_path = data.avatar

    operator_user = await get_or_create_event_operator(
        db,
        EventOperatorType.SPEAKER,
        data.dict(exclude_unset=True, exclude_none=True)
    )

    operator_exists = list(filter(
        lambda x: x.get("id") == operator_user.get("id") and operator_user.get(
            "type") == x.get("type"),
        event.get("operators", [])
    ))

    if operator_exists:
        await db.events.update_one(
            {
                '_id': event.get("_id"),
                "operators": {"$elemMatch": {
                    "id": operator_user.get("id"), "type": EventOperatorType.SPEAKER
                }}
            },
            {'$set': {**create_mongo_array_update("operators", operator_user)}}
        )
        await db.sessions.update_many(
            {
                'event_id': event.get("_id"),
                "speakers": {"$elemMatch": {
                    "id": operator_user.get("id")
                }}
            },
            {'$set': {**create_mongo_array_update("speakers", operator_user)}}
        )
    else:
        await db.events.update_one(
            {'_id': event.get("_id")},
            {'$addToSet': {'operators': operator_user}}
        )

    if image_path:
        await move_image_from_temp(image_path)

    return operator_user


@router.get('/client/speaker/{event_id}', response_model=EventOperatorListOut)
async def get_speakers(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.get_current_user_or_anonymous_user),
        event_id: ObjectId
):
    """
    User

    Get list of speakers of event

    Authorization: Not required
    """

    event = await db.events.find_one({'_id': event_id}, {'privacy': 1, 'operators': 1, 'owner_id': 1})

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found. "
        )

    if event.get('privacy') == EventPrivacy.PRIVATE.value:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You do not have access to this event. "
            )
        admins = list(map(
            lambda x: x.get("id"),
            filter(lambda x: x.get("type") == EventOperatorType.ADMIN.value, event.get("operators", []))
        ))
        if BaseObjectId(current_user.id) != event.get('owner_id') and BaseObjectId(current_user.id) not in admins:
            result = await db.friends.find_one(
                {
                    '$or': [
                        {
                            'requested_id': BaseObjectId(current_user.id),
                            'requester_id': event.get('owner_id')
                        },
                        {
                            'requester_id': BaseObjectId(current_user.id),
                            'requested_id': event.get('owner_id')
                        }
                    ],
                    'status': ConnectionStatus.CONNECTED.value
                },
                {'_id': 1}
            )
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You don not have access to this event. "
                )

    operators = list(map(
        lambda x: EventOperator.parse_obj(x),
        filter(lambda x: x.get("type") == EventOperatorType.SPEAKER.value, event.get("operators", []))
    ))
    return EventOperatorListOut(operators=operators, count=len(operators))


@router.delete('/speaker/{event_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_speaker(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        speaker_id: ObjectId
):
    """
    User

    Delete event speaker

    Authorization: Required
    """

    event = await check_access_to_event(db, event_id, current_user)

    await db.events.update_one(
        {
            '_id': event.get("_id")
        },
        {
            '$pull': {'operators': {
                "id": speaker_id,
                "type": EventOperatorType.SPEAKER
            }}
        }
    )
    await db.sessions.update_many(
        {"event_id": event.get("_id")},
        {
            '$pull': {'speakers': {
                "id": speaker_id
            }}
        }
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/teacher/{event_id}', response_model=EventOperator)
async def create_teacher(
        data: EventOperatorCreate,
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Create workshop teacher or update existing one

    Authorization: Required
    """

    event = await check_access_to_event(db, event_id, current_user)

    image_path = data.avatar

    operator_user = await get_or_create_event_operator(
        db,
        EventOperatorType.TEACHER,
        data.dict(exclude_unset=True, exclude_none=True)
    )

    operator_exists = list(filter(
        lambda x: x.get("id") == operator_user.get("id") and operator_user.get(
            "type") == x.get("type"),
        event.get("operators", [])
    ))

    if operator_exists:
        await db.events.update_one(
            {
                '_id': event.get("_id"),
                "operators": {"$elemMatch": {
                    "id": operator_user.get("id"), "type": EventOperatorType.TEACHER
                }}
            },
            {'$set': {**create_mongo_array_update("operators", operator_user)}}
        )
        await db.workshops.update_many(
            {
                'event_id': event.get("_id"),
                "operators": {"$elemMatch": {
                    "id": operator_user.get("id")
                }}
            },
            {'$set': {**create_mongo_array_update("operators", operator_user)}}
        )
    else:
        await db.events.update_one(
            {'_id': event.get("_id")},
            {'$addToSet': {'operators': operator_user}}
        )

    if image_path:
        await move_image_from_temp(image_path)

    return operator_user


@router.get('/client/teacher/{event_id}', response_model=EventOperatorListOut)
async def get_teachers(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.get_current_user_or_anonymous_user)
):
    """
    User

    Get list of teachers of event

    Authorization: Not required
    """

    event = await db.events.find_one({'_id': event_id}, {'privacy': 1, 'operators': 1, 'owner_id': 1})
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    if event.get('privacy') == EventPrivacy.PRIVATE.value:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You do not have access to this event"
            )
        admins = list(map(
            lambda x: x.get("id"),
            filter(lambda x: x.get("type") == EventOperatorType.ADMIN.value, event.get("operators"))
        ))
        if BaseObjectId(current_user.id) != event.get('owner_id') and BaseObjectId(current_user.id) not in admins:
            result = await db.friends.find_one(
                {
                    '$or': [
                        {
                            'requested_id': BaseObjectId(current_user.id),
                            'requester_id': event.get('owner_id')
                        },
                        {
                            'requester_id': BaseObjectId(current_user.id),
                            'requested_id': event.get('owner_id')
                        }
                    ],
                    'status': ConnectionStatus.CONNECTED.value
                },
                {'_id': 1}
            )
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You don not have access to this event"
                )

    operators = list(map(
        lambda x: EventOperator.parse_obj(x),
        filter(lambda x: x.get("type") == EventOperatorType.TEACHER.value, event.get("operators", []))
    ))
    return EventOperatorListOut(operators=operators, count=len(operators))


@router.delete('/teacher/{event_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_teacher(
        event_id: ObjectId,
        operator_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Delete event teacher

    Authorization: Required
    """

    event = await check_access_to_event(db, event_id, current_user)

    await db.events.update_one(
        {
            '_id': event.get("_id")
        },
        {
            '$pull': {'operators': {
                "id": operator_id,
                "type": EventOperatorType.TEACHER
            }}
        }
    )
    await db.workshops.update_many(
        {"event_id": event.get("_id")},
        {
            '$pull': {'operators': {
                "id": operator_id
            }}
        }
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/teacher/{event_id}')
async def partial_update_event_teacher(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        data: EventOperator,
        teacher_id: ObjectId
) -> Response:
    """
    User

    Partial Update event workshop teacher

    Authorization: Required
    """

    image_path = data.avatar
    data = {**data.dict(exclude_unset=True), 'type': EventOperatorType.TEACHER.value}
    result = await db.events.update_one(
        {
            '_id': event_id,
            'operators.id': teacher_id,
            "$or": [
                {"owner_id": BaseObjectId(current_user.id)},
                {
                    "operators": {"$elemMatch": {
                        "id": BaseObjectId(current_user.id),
                        "type": EventOperatorType.TEACHER.value
                    }}
                }
            ]
        },
        {"$set": {**create_mongo_array_update("operators", data)}}
    )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not update event. "
        )

    if image_path:
        await move_image_from_temp(image_path)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sponsor/{event_id}")
async def get_sponsors(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Get event sponsors

    Authorization: Required
    """

    event_result = await db.events.find_one(
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
        {"sponsors": 1}
    )
    if not event_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No events found with the given id"
        )

    event_result['sponsors'] = event_result['sponsors'] if 'sponsors' in event_result and event_result[
        'sponsors'] else []
    sponsors = list(map(lambda x: EventSponsorOut.parse_obj(x), event_result['sponsors']))
    return EventSponsorsInList(sponsors=sponsors, count=len(sponsors))


@router.patch('/speaker/{event_id}')
async def partial_update_event_speaker(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        data: EventSessionSpeakerPartialUpdate,
        speaker_id: ObjectId
) -> Response:
    """
    User

    Partial Update event session speaker

    Authorization: Required
    """

    image_path = data.avatar
    data = {**data.dict(exclude_unset=True), 'type': EventOperatorType.SPEAKER.value}
    result = await db.events.update_one(
        {
            '_id': event_id,
            'operators.id': speaker_id,
            "$or": [
                {"owner_id": BaseObjectId(current_user.id)},
                {
                    "operators": {"$elemMatch": {
                        "id": BaseObjectId(current_user.id),
                        "type": EventOperatorType.SPEAKER.value
                    }}
                }
            ]
        },
        {"$set": {**create_mongo_array_update("operators", data)}}
    )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not update event. "
        )

    if image_path:
        await move_image_from_temp(image_path)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/client/discount/{event_id}')
async def validate_discount(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        event_id: ObjectId,
        discount_code: str = Body(...)
):
    """
    Validate discount code and returns discount_type and discount_amount

    Authorization: Required
    """

    discount_data = await validate_total_cost_discount(
        db=db,
        discount_code=discount_code,
        event_id=event_id
    )

    return discount_data


@router.get('/bookmark', response_model=EventBookmarkListOut)
async def get_bookmarked_events(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))):
    """
    User

    Get user's bookmarked events

    Authorization: Required
    """

    bookmark_document = await db.event_bookmarks.find_one(
        {'owner_id': BaseObjectId(current_user.id)},
        {'bookmarks': 1}
    )

    if not bookmark_document:
        return EventBookmarkListOut()

    bookmark_document['bookmarks'] = [] if not bookmark_document.get('bookmarks') else bookmark_document.get(
        'bookmarks')
    bookmarked_events = list(map(lambda x: EventBookmarkOutInList.parse_obj(x), bookmark_document.get('bookmarks')))
    return EventBookmarkListOut(events=bookmarked_events, count=len(bookmarked_events))


@router.post('/bookmark/{event_id}', status_code=status.HTTP_204_NO_CONTENT)
async def add_bookmark_event(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId
):
    """
    User

    Add event to user's bookmarked events

    Authorization: Required
    """

    event = await db.events.find_one(
        {'_id': event_id},
        {
            'name': 1,
            'properties': 1,
            'starts_at': 1,
            'ends_at': 1,
            'category': 1,
            'creator': 1,
            'description': 1,
            'cover': 1
        }
    )

    bookmark = AddEventBookmark.parse_obj_id({**event}).dict()
    await db.event_bookmarks.update_one(
        {'owner_id': BaseObjectId(current_user.id)},
        {
            '$addToSet': {'bookmarks': bookmark},
            '$setOnInsert': {'owner_id': current_user.id}
        },
        upsert=True
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete('/bookmark/{event_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark_event(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId
):
    """
    User

    Delete bookmark from event bookmarks

    Authorization: Required
    """

    delete_response = await db.event_bookmarks.update_one(
        {'owner_id': BaseObjectId(current_user.id)},
        {
            '$pull': {'bookmarks': {'id': event_id}}
        })

    if delete_response.matched_count < 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found. "
        )

    if not delete_response.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not update bookmarks. "
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{event_id}", response_model=Events)
async def get_event(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Get event

    Authorization: Required
    """

    event_result = await db.events.find_one(
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
        {
            '_id': 1,
            'description': 1,
            'cover': 1,
            'sponsors': 1,
            'host': 1,
            'is_bought': 1,
            'name': 1,
            'starts_at': 1,
            'ends_at': 1,
            'properties': 1,
            'is_published': 1,
            'category': 1,
            'schedule': 1,
            'sessions': 1,
            'operators': 1,
            'workshops': 1
        }
    )
    if not event_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No events found with the given id"
        )

    speakers = list(map(
        lambda x: EventSessionSpeakerInListOut.parse_obj({**x, 'id': x.get('id')}),
        filter(
            lambda x: x.get('type') == EventOperatorType.SPEAKER.value,
            event_result.get('operators', [])
        )
    ))

    publish_ready = await check_event_publish_ready(event_result)
    if not event_result.get('schedule', []):
        event_result['schedule'] = []

    return Events.parse_obj(
        {
            **event_result,
            "id": event_result.get("_id"),
            "speakers": speakers,
            "publish_ready": publish_ready
        }
    )
