import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId as BaseObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status

from app.core.utils import convert_naive_to_aware, specify_username_type
from app.schemas.base import ObjectId
from app.schemas.events import DiscountType, EventOperatorType, EventOperator
from app.schemas.general import DiscountAmountType, UserType, UserStatus, UsernameType
from app.schemas.users import User


def generate_uuid():
    return str(uuid.uuid4())


async def validate_create_code_discount(event, discount) -> (bool, Any):
    """
    Validates request data for creating discount
    """

    properties = event.get('properties') if event.get('properties') else None
    if not properties:
        return False, "Event configuration is not complete and can not create discount. "

    session = properties.get('session')
    workshop = properties.get('workshop')
    if not session and not workshop:
        if not properties:
            return False, "Event configuration is not complete and can not create discount. "
    if not session.get('active') and not workshop.get('active'):
        assert "Invalid event with inactive session and workshop is created. "

    # TODO validate free event from stage and workshop config data when its implemented

    if discount.get('use_count') is True:
        # validate discount count and sum of session and workshop max_participant
        if session.get('max_participants') + session.get('max_participants') < discount.get('count'):
            error = "discount count can not be greater than the sum of event properties max_participants"
            return False, error

    # validate discount datetime interval with event datetime interval
    # convert datetime values that are queried from
    event['starts_at'] = convert_naive_to_aware(event.get('starts_at'))
    event['ends_at'] = convert_naive_to_aware(event.get('ends_at'))
    discount['starts_at'] = convert_naive_to_aware(discount.get('starts_at'))
    discount['ends_at'] = convert_naive_to_aware(discount.get('ends_at'))
    if event.get('starts_at') > discount.get('starts_at') or event.get('ends_at') < discount.get('ends_at'):
        error = "discount datetime interval must be a subset of event datetime interval."
        return False, error

    return True, None


async def calculate_session_cost(
        session: Dict
) -> Dict:
    """
    Check if session discount is valid and calculate session cost,
    return response = {cost: int, applied_discount: bool, increase_usage_count: bool}
    if discount is applied, applied_discount is True else if False
    """

    # if session is not free
    # if discount exists and has not expired
    # if discount use_count is true
    # if count > usage_count ==> decrease cost by discount amount and return applied_discount as True

    now = datetime.now()

    response = {"cost": 0, "applied_discount": False, "increase_usage_count": False}

    fs = session.get('financial_settings')

    if not fs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event"
        )

    ds = fs.get('discount') if fs.get('discount') else None

    if not fs.get('is_free'):
        response["cost"] = fs.get('price')
        if ds:
            if ds.get('starts_at') < now < ds.get('ends_at'):
                if ds.get('use_count'):
                    if ds.get('usage_count'):
                        if ds.get('usage_count') < ds.get('count'):
                            response["increase_usage_count"] = True
                        else:
                            return response
                    else:
                        response["increase_usage_count"] = True

                if ds.get('amount_type') == DiscountAmountType.AMOUNT:
                    response["cost"] = response.get("cost") - ds.get('amount')
                    response["applied_discount"] = True
                    return response
                elif ds.get('amount_type') == DiscountAmountType.PERCENTAGE:
                    response["cost"] = response.get("cost") - ds.get('amount') * 100 * response.get("cost")
                    response["applied_discount"] = True
                    return response

                else:
                    assert "invalid DiscountAmountType"

    return response


async def calculate_workshops_invoice_data(
        workshops: List
) -> (List[Dict], int, List[ObjectId], List[ObjectId], List[ObjectId]):
    """
    Check if workshop discount is valid and calculate workshop cost,
    return response = (
    [{workshop_id: ObjectId, price: int, cost: int, applied_discount: bool, increase_usage_count: bool}],
    total_workshop_cost: int,
    calculated_workshop_ids: List[ObjectId],
    increase_usage_discounts_ids: List[ObjectId]
    increase_usage_ws_ids: List[ObjectId]
    )
    if discount is applied, applied_discount is True,
    if use_cant is True and valid, increase_usage_count will be True
    """

    # if session is not free
    # if discount exists and has not expired
    # if discount use_count is true
    # if count > usage_count ==> decrease cost by discount amount and return applied_discount as True

    now = datetime.now()
    response = []

    increase_usage_discounts_ids = []
    increase_usage_ws_ids = []

    total_cost = 0
    ws_ids = []

    # ws is abbreviation for workshop and fs is abbreviation for financial_settings and ds is abbreviation for discount

    for ws in workshops:
        print(ws)
        ws_invoice = {
            **ws,
            "cost": 0,
            "applied_discount": False,
            "increase_usage_count": False,
            "price": ws.get('financial_settings', {}).get('price')
        }

        fs = ws.get('financial_settings')

        if not fs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid event."
            )

        ds = fs.get('discount') or None

        if not fs.get('is_free'):
            ws_invoice["cost"] = fs.get('price')

            if ds and ds.get('starts_at') < now < ds.get('ends_at'):
                if ds.get('use_count'):
                    if ds.get('usage_count'):
                        if ds.get('usage_count') < ds.get('count'):
                            ws_invoice["increase_usage_count"] = True
                            increase_usage_ws_ids.append(ws.get('id'))
                            increase_usage_discounts_ids.append(ds.get('discount_id'))
                        else:
                            response.append(ws_invoice)
                            total_cost = total_cost + ws_invoice.get('cost')
                            ws_ids.append(ws.get('id'))
                            continue
                    else:
                        increase_usage_discounts_ids.append(ds.get('discount_id'))
                        increase_usage_ws_ids.append(ws.get('id'))
                        ws_invoice["increase_usage_count"] = True

                if ds.get('amount_type') == DiscountAmountType.AMOUNT:
                    ws_invoice["cost"] = ws_invoice.get("cost") - ds.get('amount')
                    ws_invoice["applied_discount"] = True
                    response.append(ws_invoice)
                    total_cost = total_cost + ws_invoice.get('cost')

                    ws_ids.append(ws.get('id'))
                    continue

                elif ds.get('amount_type') == DiscountAmountType.PERCENTAGE:
                    ws_invoice["cost"] = ws_invoice.get("cost") - (ds.get('amount') * 100 * ws_invoice.get("cost"))
                    ws_invoice["applied_discount"] = True
                    response.append(ws_invoice)
                    total_cost = total_cost + ws_invoice.get('cost')

                    ws_ids.append(ws.get('id'))
                    continue
                else:
                    assert "invalid DiscountAmountType"

        response.append(ws_invoice)
        ws_ids.append(ws.get('id'))

    return response, total_cost, ws_ids, increase_usage_discounts_ids, increase_usage_ws_ids


async def check_event_publish_ready(event: Dict) -> bool:
    """
    Validates event required fields to be published
    """

    # check session requirements

    if event:
        if event.get('properties').get('session') and event.get('properties').get('session').get('active'):
            # check if at least one session is created
            if event.get('properties').get('session').get('hours') == event.get(
                    'properties').get('session').get('remaining_hours'):
                return False
            # check if financial settings are set
            if not event.get('properties').get('session').get('financial_settings'):
                return False
            # check if session is free or is not free and price is set
            if event.get('properties').get('session').get('financial_settings').get('is_free'):
                pass
            else:
                if not event.get('properties').get('session').get('financial_settings').get('price'):
                    return False
                pass
        else:
            pass

        # check workshop requirements

        if event.get('properties').get('workshop') and event.get('properties').get('workshop').get('active'):
            # check if at least one workshop is created
            if event.get('properties').get('workshop').get('hours') == event.get(
                    'properties').get('workshop').get('remaining_hours'):
                return False
            # check if financial settings are set and if so, check if workshop is free or price is set
            for ws in event.get('workshops'):
                if not ws.get('financial_settings'):
                    return False
                else:
                    if ws.get('financial_settings').get('is_free'):
                        pass
                    else:
                        if not ws.get('financial_settings').get('price'):
                            return False
        else:
            pass

        return True
    return False


async def validate_invoice_discount(db: AsyncIOMotorDatabase, discount_code: str, invoice: Dict) -> Dict:
    """
    Validates and applies discount and returns invoice
    """

    now = datetime.now()
    # ds is abbreviation for discount
    ds = await db.discounts.find_one(
        {
            'code': discount_code,
            'type': DiscountType.CAMPAIGN.value,
            'event_id': invoice.get('event_id')
        },
        {
            '_id': 1,
            'starts_at': 1,
            'ends_at': 1,
            'use_count': 1,
            'usage_count': 1,
            'amount': 1,
            'amount_type': 1
        }
    )

    if not ds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount not found for the given discount code."
        )

    # validate discount
    if ds.get('starts_at') < now < ds.get('ends_at'):
        if ds.get('use_count'):
            if ds.get('use_count') < ds.get('usage_count'):
                await db.discounts.update_one({'_id': ds.get('_id')}, {'$inc': {'usage_count': 1}})
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Discount is expired."
                )

        if ds.get('amount_type') == DiscountAmountType.AMOUNT:
            invoice = {
                **invoice,
                'discount': ds,
                'total_cost': invoice.get('total_cost') - ds.get('amount') if invoice.get('total_cost') - ds.get(
                    'amount') >= 0 else 0
            }
        elif ds.get('amount_type') == DiscountAmountType.PERCENTAGE:
            invoice = {
                **invoice,
                'discount': ds,
                'total_cost': invoice.get('total_cost') - (ds.get('amount') * 100 * invoice.get(
                    'total_cost')) if invoice.get('total_cost') - (ds.get('amount') * 100 * invoice.get(
                    'total_cost')) >= 0 else 0
            }
        assert "Invalid discount amount_type"

        return invoice

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Discount is expired."
    )


async def validate_total_cost_discount(
        db,
        discount_code,
        event_id
) -> dict:
    """
    Validates and applies code discount and returns new cost
    """

    now = datetime.now()
    # ds is abbreviation for discount
    ds = await db.discounts.find_one(
        {
            'code': discount_code,
            'type': DiscountType.CODE.value,
            'event_id': event_id
        },
        {
            '_id': 1,
            'starts_at': 1,
            'ends_at': 1,
            'use_count': 1,
            'count': 1,
            'usage_count': 1,
            'amount': 1,
            'amount_type': 1
        }
    )

    if not ds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount not found for the given discount code."
        )

    # validate discount

    if not (ds.get('starts_at') < now < ds.get('ends_at')) or (
            ds.get('use_count') and not ds.get('count') > ds.get('usage_count')
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount is expired."
        )

    return {'amount_type': ds.get('amount_type'), 'amount': ds.get('amount')}


async def check_access_to_event(
        db: AsyncIOMotorDatabase,
        event_id: ObjectId,
        current_user: User,
        projection: Optional[Dict] = None,
        only_owner: bool = False
) -> Dict:
    """Check user access to event"""

    if projection is None:
        projection = {"_id": 1, "owner_id": 1, "operators": 1}
    else:
        projection = {"_id": 1, "owner_id": 1, "operators": 1, **projection}

    event = await db.events.find_one(
        {
            '_id': event_id
        },
        projection
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No event found with the given id"
        )

    if only_owner:
        if BaseObjectId(current_user.id) != event.get("owner_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this endpoint"
            )
    else:
        event_operators = list({
            event.get("owner_id"),
            *list(map(
                lambda x: x.get("id"),
                filter(
                    lambda x: x.get("type") == EventOperatorType.ADMIN.value,
                    event.get("operators", [])
                )
            ))
        })
        if BaseObjectId(current_user.id) not in event_operators:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this endpoint"
            )
    return event


async def get_or_create_event_operator(
        db: AsyncIOMotorDatabase,
        operator_type: EventOperatorType,
        data: Optional[Dict] = None
) -> Dict:
    if data is None:
        data = {}

    # TODO: Send email to teacher on publishing event PATCH event

    username = data.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Wrong type of username"
        )
    username_type = specify_username_type(username)
    find_user_query = {}
    if username_type == UsernameType.EMAIL:
        find_user_query = {"$or": [{"username": username}, {"contact_info.mobile": username}]}
    elif username_type == UsernameType.MOBILE:
        find_user_query = {"$or": [{"username": username}, {"contact_info.email": username}]}
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Wrong type of username"
        )

    now = datetime.now()
    user = await db.users.find_one(
        find_user_query,
        {
            '_id': 1,
            'basic_info': 1,
            'user_type': 1,
            'username': 1,
            'contact_info': 1
        }
    )
    if user:
        if user.get('user_type') not in (UserType.NORMAL.value, UserType.COMPANY.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provided user does not have correct user_type"
            )
        user = {
            **user,
            "id": user.get("_id"),
            "company_name": user.get('basic_info', {}).get('company_name'),
            "first_name": user.get('basic_info', {}).get('first_name'),
            "last_name": user.get('basic_info', {}).get('last_name'),
            "avatar": user.get('basic_info', {}).get('avatar'),
            "headline": user.get('basic_info', {}).get('headline'),
            "website": user.get('contact_info', {}).get('website'),
            "type": operator_type.value
        }

    else:
        user = {
            'username': data.get('username'),
            'created_at': now,
            'updated_at': now,
            'status': UserStatus.ACTIVE.value,
            'user_type': UserType.NORMAL.value,
            'basic_info': {
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name'),
                'avatar': data.get('avatar'),
                'headline': data.get('headline')
            },
            "contact_info": {
                "website": data.get("website")
            }
        }
        if username_type == UsernameType.EMAIL:
            user["contact_info"]["email"] = username
        else:
            user["contact_info"]["mobile"] = username
        user_result = await db.users.insert_one(user)
        user = {
            **user,
            "id": user_result.inserted_id,
            "company_name": user.get('basic_info', {}).get('company_name'),
            "first_name": user.get('basic_info', {}).get('first_name'),
            "last_name": user.get('basic_info', {}).get('last_name'),
            "avatar": user.get('basic_info', {}).get('avatar'),
            "headline": user.get('basic_info', {}).get('headline'),
            "website": user.get('contact_info', {}).get('website'),
            "type": operator_type.value
        }

    user.update(data)
    user = EventOperator.parse_obj(user).dict(exclude_none=True, exclude_unset=True)

    return user


async def check_and_calculate_time(event: Dict, property_object, property_name: str, plus_time: float = 0) -> int:
    """
    Check event remaining property time and calculate new one
    """

    try:
        if property_object.starts_at < event.get("starts_at") or property_object.ends_at > event.get("ends_at"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You cannot create {property_name} out of event duration"
            )
    except TypeError:
        if convert_naive_to_aware(
                property_object.starts_at
        ) < convert_naive_to_aware(event.get("starts_at")) or convert_naive_to_aware(
            property_object.ends_at
        ) > convert_naive_to_aware(event.get("ends_at")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You cannot create {property_name} out of event duration"
            )

    property_duration: float = (property_object.ends_at - property_object.starts_at).total_seconds()
    event = event.get("properties", {}).get(property_name, {})

    if property_duration > (event.get("remaining_hours", 0) + plus_time):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You do not have enough remaining time to run this {property_name}"
        )

    return round(property_duration - plus_time)
