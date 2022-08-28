"""
Workshop rooms APIs
route: /booths
"""

from datetime import datetime
from typing import List

from bson import ObjectId as BaseObjectId
from fastapi import APIRouter, Depends, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status

from app.core import depends
from app.core.booths import find_or_create_exhibitor
from app.core.events import generate_uuid, check_access_to_event
from app.handlers.email import send_mail
from app.schemas.base import ObjectId
from app.schemas.booths import (
    BoothRequestInput,
    BoothRequestStatus,
    BoothRequestListOutput,
    BoothRequestOutput,
    BoothRequestAction,
    BoothStatus,
    BoothPartialUpdate, BoothOutput
)
from app.schemas.events import InvoiceType
from app.schemas.general import EventOperatorType, Roles
from app.schemas.users import User

router = APIRouter()


@router.post("/admin/{event_id}", status_code=status.HTTP_201_CREATED)
async def create_booth(
        event_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.get_current_user)
):
    """
    Client user

    Request booth from event owner, if user is authenticated, form data will not be used and user profile data will be
    used

    Authorization: required
    """
    now = datetime.now()

    event = await check_access_to_event(db, event_id, current_user, only_owner=True)

    user = await db.users.find_one({'_id': BaseObjectId(current_user.id)}, {'basic_info': 1, 'contact_info': 1})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    data = {
        'first_name': user.get('basic_info', {}).get('first_name'),
        'last_name': user.get('basic_info', {}).get('last_name'),
        'headline': user.get('basic_info', {}).get('headline'),
        'email': user.get('contact_info', {}).get('email'),
        'phone': user.get('contact_info', {}).get('phone'),
        'created_at': now,
        'updated_at': now,
        'status': BoothRequestStatus.PENDING.value,
        'id': generate_uuid()
    }

    booth = {
        'event_id': event_id,
        'event_name': event.get('name'),
        'status': BoothStatus.ACTIVE.value,
        'exhibitor': data,
        'created_at': now,
        'updated_at': now,
    }

    booth = await db.booths.insert_one(booth)

    await db.events.update_one(
        {'_id': event_id},
        {'$push': {'booth_requests': {**data, "booth_id": booth.inserted_id}}}
    )

    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/request/{event_id}", status_code=status.HTTP_201_CREATED)
async def request_booth(
        event_id: ObjectId,
        booth_request: BoothRequestInput,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.get_current_user_or_anonymous_user)
):
    """
    Client user

    Request booth from event owner, if user is authenticated, form data will not be used and user profile data will be
    used

    Authorization: required
    """
    now = datetime.now()

    event = await db.events.find_one(
        {
            '_id': event_id,
            'is_published': True,
            '$and': [{'starts_at': {'$lt': now}}, {'ends_at': {'$gt': now}}],
            'properties.booth': True
        },
        {'_id': 1}
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event not found."
        )

    if current_user:
        user = await db.users.find_one({'_id': BaseObjectId(current_user.id)}, {'basic_info': 1, 'contact_info': 1})

        data = {
            'first_name': user.get('basic_info', {}).get('first_name'),
            'last_name': user.get('basic_info', {}).get('last_name'),
            'headline': user.get('basic_info', {}).get('headline'),
            'email': user.get('contact_info', {}).get('email'),
            'phone': user.get('contact_info', {}).get('phone'),
            'created_at': now,
            'updated_at': now,
            'status': BoothRequestStatus.PENDING.value,
            'id': generate_uuid()
        }

        await db.events.update_one(
            {'_id': event_id},
            {'$push': {'booth_requests': data}}
        )

        return Response(status_code=status.HTTP_201_CREATED)

    data = {
        **booth_request.dict(),
        'created_at': now,
        'updated_at': now,
        'status': BoothRequestStatus.PENDING.value,
        'id': generate_uuid()
    }

    await db.events.update_one(
        {'_id': event_id},
        {'$push': {'booth_requests': data}}
    )

    return Response(status_code=status.HTTP_201_CREATED)


@router.get('/request/{event_id}', response_model=BoothRequestListOutput)
async def get_booth_request(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId
):
    """
    User

    Get user event booth requests

    Authorization: Required
    """

    event_document = await check_access_to_event(db, event_id, current_user, {'booth_requests': 1})
    booth_requests = event_document.get('booth_requests')
    if not booth_requests:
        return BoothRequestListOutput()

    booth_requests = list(map(lambda x: BoothRequestOutput.parse_obj(x), booth_requests))
    return BoothRequestListOutput(booth_requests=booth_requests, count=len(booth_requests))


@router.patch('/request/{event_id}/{request_id}')
async def perform_action_booth_request(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        event_id: ObjectId,
        request_id: str,
        action: BoothRequestAction
):
    """
    User

    Accept or deny booth request,

    If request is accepted, user is either found in users collection or inserted

    Authorization: Required
    """

    event_document = await check_access_to_event(
        db,
        event_id,
        current_user,
        {'booth_requests': 1, 'name': 1}
    )
    booth_requests = event_document.get('booth_requests')
    if not booth_requests:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event does not have booth requests."
        )

    booth_request = None
    for request in booth_requests:
        if request['id'] == request_id:
            booth_request = request
            request['status'] = BoothRequestStatus.ACCEPTED.value if \
                action == BoothRequestAction.ACCEPT.value else BoothRequestStatus.REJECTED.value
            break

    if action == BoothRequestAction.ACCEPT:
        now = datetime.now()
        # create user for requester user or find existing user
        user_id, found, user_password = await find_or_create_exhibitor(db, booth_request)

        # create inactive booth, booth will be activated when exhibitor's purchase has been verified
        exhibitor = {
            'id': user_id,
            'email': booth_request.get('email'),
            'phone': booth_request.get('phone'),
            'headline': booth_request.get('headline')
        }

        if booth_request.get('company_name'):
            exhibitor['company_name'] = booth_request.get('company_name')
        else:
            exhibitor |= {'first_name': booth_request.get('first_name'), 'last_name': booth_request.get('last_name')}


        booth = {
            'event_id': event_id,
            'event_name': event_document.get('name'),
            'status': BoothStatus.INACTIVE.value,
            'exhibitor': exhibitor,
            'created_at': now,
            'updated_at': now,
            'request_id': request_id
        }

        booth = await db.booths.insert_one(booth)

        for request in booth_requests:
            if request['id'] == request_id:
                request['booth_id'] = booth.inserted_id

        # update booth request status in event
        event_update_result = await db.events.update_one({'_id': event_id},
                                                         {'$set': {'booth_requests': booth_requests}})

        # TODO send mail, containing link to login page and then booth config page
        # TODO for testing purposes for new user password is generated and set to db and its also returned in response
        # await send_mail(
        #     email=exhibitor.get('email'),
        #     subject="Booth request",
        #     text=f"Your booth request has been approved. Follow the provided link to config your booth. "
        #          f"booth id is {booth.inserted_id}. user password is {user_password}"
        # )

        return {'found': f"{found}", 'user_password': f"{user_password}"}

    elif action == BoothRequestAction.REJECT:

        # update booth request status in event
        event_update_result = await db.events.update_one({'_id': event_id},
                                                         {'$set': {'booth_requests': booth_requests}})

        # TODO send mail, containing link to login page and then booth config page
        await send_mail(
            email=booth_request.get('email'),
            subject="Booth request",
            text=f"Your booth request has been denied. event id is {event_id}"
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/buy/{booth_id}")
async def buy_booth(
        booth_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Pay for requested and accepted booth to activate the booth

    Authorization: Required
    """

    now = datetime.now()
    booth = await db.booths.find_one(
        {'_id': booth_id, 'exhibitor.id': BaseObjectId(current_user.id)},
        {'_id': 1, 'event_id': 1, 'exhibitor': 1}
    )

    if not booth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booth not found."
        )

    event = await db.events.find_one(
        {
            '_id': booth.get('event_id'),
            'is_published': True,
            '$and': [{'starts_at': {'$lt': now}}, {'ends_at': {'$gt': now}}],
            'properties.booth': True
        },
        {'_id': 1, 'name': 1, 'owner_id': 1}
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event."
        )

    # check if current user is system admin
    is_system_admin = Roles.ADMIN.value in current_user.role
    # check if current user owns the event
    is_event_owner = current_user.id == event.get('owner_id')
    # check if current user is event admin
    is_event_admin = current_user.id in event.get('admins') if event.get('admins') else False
    if any([is_system_admin, is_event_owner, is_event_admin]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin user can not buy booth")

    invoices = await db.invoices.find({
        'type': InvoiceType.BOOTH_EXHIBITOR.value,
        'event_id': event.get('_id'),
        'is_paid': True,
        'owner.id': BaseObjectId(current_user.id)
    }).to_list(length=None)

    if invoices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has already bought provided booth"
        )

    invoice = {
        'type': InvoiceType.BOOTH_EXHIBITOR.value,
        'created_at': now,
        'updated_at': now,
        'owner': booth.get('exhibitor'),
        'event_id': booth.get('event_id'),
        # is_paid is temporary true for testing purposes
        'is_paid': True,
        'event_name': event.get('name'),
        # TODO calculate booth cost
        # sample data
        'total_cost': 200000
    }
    invoice_insert_result = await db.invoices.insert_one(invoice)

    # TODO call the ipg with invoice id to return link
    invoice_id = invoice_insert_result.inserted_id

    # temporary update booth here for testing purposes
    booth_update_result = await db.booths.update_one({'_id': booth_id}, {'$set': {'status': BoothStatus.ACTIVE.value}})

    # temporary update event here for testing purposes
    operator = {
        **booth.get('exhibitor'),
        'username': booth.get('exhibitor').get('email'),
        'type': EventOperatorType.EXHIBITOR.value,
        'booth_id': booth_id
    }
    event_update_result = await db.events.update_one(
        {'_id': event.get('_id')},
        {'$addToSet': {'operators': operator}})

    return {'invoice_id': str(invoice_id)}


@router.post("/verify/{booth_id}")
async def verify_buy_booth(
        booth_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database)
):
    """
    IPG callback

    Verify purchase ipg

    Authorization: Not Required
    """

    # verify purchase

    # update booth => status = ACTIVE

    # redirect to appropriate success or failure front page

    return


@router.get('/exhibitor/{booth_id}', response_model=BoothOutput)
async def exhibitor_get_booth(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        booth_id: ObjectId
):
    """
    Exhibitor User

    Get booth data for exhibitor

    Authorization: Required
    """

    now = datetime.now()

    booth = await db.booths.find_one(
        {
            '_id': BaseObjectId(booth_id),
            'exhibitor.id': BaseObjectId(current_user.id),
            'status': BoothStatus.ACTIVE.value
        }
    )

    if not booth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booth not found."
        )

    event_document = await db.events.find_one(
        {'_id': booth.get('event_id'), 'ends_at': {'$gt': now}, 'starts_at': {'$lt': now}},
        {'operators': 1}
    )

    if not event_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event not found."
        )

    for operator in event_document.get('operators'):
        if operator['booth_id'] == booth_id and operator['id'] == current_user.id:
            break
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User does not have access to this booth.")

    return BoothOutput.parse_obj_id(booth)


@router.get('/{booth_id}', response_model=BoothOutput)
async def get_booth(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        booth_id: ObjectId
):
    """
    User

    Get booth data for booth page

    Authorization: Required
    """

    booth = await db.booths.find_one(
        {
            '_id': BaseObjectId(booth_id),
            'status': BoothStatus.ACTIVE.value
        }
    )

    if not booth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booth not found."
        )

    return BoothOutput.parse_obj_id(booth)


@router.patch('/{booth_id}', status_code=status.HTTP_204_NO_CONTENT)
async def partial_update_booth(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        booth_id: ObjectId,
        data: BoothPartialUpdate
):
    """
    User

    Partial Update booth data for exhibitor

    Authorization: Required
    """
    now = datetime.now()

    booth = await db.booths.find_one(
        {'_id': BaseObjectId(booth_id), 'exhibitor.id': BaseObjectId(current_user.id),
         'status': BoothStatus.ACTIVE.value}
    )

    if not booth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booth not found."
        )

    event_document = await db.events.find_one(
        {'_id': booth.get('event_id'), 'ends_at': {'$gt': now}, 'starts_at': {'$lt': now}},
        {'operators': 1}
    )

    if not event_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event not found."
        )

    for operator in event_document.get('operators'):
        if operator['booth_id'] == booth_id and operator['id'] == current_user.id:
            break
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User does not have access to this booth.")

    booth_update_result = await db.booths.update_one(
        {'_id': BaseObjectId(booth_id)},
        {'$set': data.dict(exclude_unset=True)}
    )

    return Response(status_code=status.HTTP_200_OK)


@router.get('/client', response_model=List[BoothOutput])
async def get_client_booths(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    User

    Get booths that client has joined

    Authorization: Required
    """

    booths = await db.booths.find({'exhibitor.id': BaseObjectId(current_user.id)}).to_list(length=None)
    return list(map(lambda x: BoothOutput.parse_obj_id(x), booths or []))


@router.get('', response_model=List[BoothOutput])
async def get_event_booths(
    event_id: ObjectId,
    db: AsyncIOMotorDatabase = Depends(depends.get_database),
    current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Admin

    Get events booths datas

    Authorization: Required
    """
    event = await check_access_to_event(db, event_id, current_user, {"booth_requests": 1})

    if booth_ids := list(filter(lambda x: x, map(lambda x: x.get("booth_id"), event.get("booth_requests", [])))):
        booths = await db.booths.find({"_id": {"$in": booth_ids}}).to_list(length=None)
        return list(map(lambda x: BoothOutput.parse_obj_id(x), booths or []))

    return []
