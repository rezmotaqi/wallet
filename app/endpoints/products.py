"""
Products apis
route: /products
"""
from datetime import datetime
from typing import Optional, List

from bson import ObjectId as BaseObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from starlette import status
from starlette.responses import Response

from app.core import depends
from app.core.products import validate_guarantees
from app.core.utils import serve_nested_to_root
from app.schemas.base import DateOrderBy, ObjectId
from app.schemas.products import (
    ProductInput,
    ProductListOutput,
    ProductOutput,
    ProductPartialUpdate,
    CartOutput,
    ProductGuaranteeInput,
    ProductGuaranteeListOutput,
    ProductGuaranteeOutput
)
from app.schemas.users import User

router = APIRouter()


@router.post('/guarantees', status_code=status.HTTP_201_CREATED)
async def create_guarantee(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        data: ProductGuaranteeInput

):
    """
    Admin

    Create product guarantee
    """
    now = datetime.now()
    data = {**data.dict(), 'created_at': now, 'updated_at': now, 'owner_id': BaseObjectId(current_user.id)}
    result = await db.guarantees.insert_one(data)
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create guarantee."
        )

    return Response(status_code=status.HTTP_201_CREATED)


@router.get('/guarantees', response_model=ProductGuaranteeListOutput)
async def get_list_of_guarantees(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
):
    """
    Admin

    Get list of guarantees
    """
    guarantees = await db.guarantees.find({}).skip(offset * limit).to_list(length=limit)
    if not guarantees:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create guarantee."
        )

    guarantees = list(map(lambda x: ProductGuaranteeOutput.parse_obj_id(x), guarantees))
    count = await db.gurantees.count_documents({})
    return ProductGuaranteeListOutput(count=count, guarantees=guarantees)


@router.post('/guarantees/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
async def add_guarantee_to_product(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        guarantee_id: ObjectId,
        product_id: ObjectId
):
    """
    Admin

    Add guarantee to product
    """

    guarantee = await db.guarantees.find_one({'_id': guarantee_id})
    if not guarantee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guarantee not found."
        )
    guarantee['id'] = guarantee_id
    guarantee.pop('_id')
    update_result = await db.products.update_one({'_id': product_id}, {'$addToSet': {'guarantees': guarantee}})
    if not update_result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not update product."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/cart', status_code=status.HTTP_204_NO_CONTENT)
async def add_product_to_cart(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        product_id: ObjectId,
        guarantee_id: Optional[ObjectId] = None
):
    """
    Client

    Add product to cart
    """

    query = {'_id': product_id}
    projection = {'english_name': 1, 'price': 1}

    if guarantee_id:
        query['guarantee.id'] = guarantee_id
        projection['guarantee.$'] = guarantee_id
    product = await db.products.find_one(query, projection)
    user_result = await db.users.update_one(
        {'_id': BaseObjectId(current_user.id)}, {'$addToSet': {'cart': product}}
    )
    if not user_result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not update cart."
        )


@router.get('/cart/{user_id}', response_model=CartOutput)
async def get_user_cart(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),


):
    """
    User

    Get user cart
    """

    cart = await db.users.find_one({'_id': BaseObjectId(current_user.id)}, {'cart': 1})
    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found."
        )
    return CartOutput.parse_obj(cart)


@router.post('', status_code=status.HTTP_201_CREATED)
async def create_product(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        data: ProductInput
):
    """
    Admin

    Create product
    """

    now = datetime.now()
    data = {**data.dict(), 'updated_at': now, 'created_at': now, 'owner_id': current_user.id}

    try:
        await db.products.insert_one(data)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create product."
        )

    return Response(status_code=status.HTTP_201_CREATED)


@router.get('', response_model=ProductListOutput)
async def get_list_of_products(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        search_field: Optional[str] = None,
        from_date: Optional[datetime] = datetime(2000, 1, 1, 0, 0, 0, 0),
        to_date: Optional[datetime] = None,
        sort: Optional[DateOrderBy] = "-created_at",
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
):
    """
    Admin and client

    Get list of products
    """
    if not to_date:
        to_date = datetime.now()
    query = {"created_at": {"$gte": from_date, "$lte": to_date}}
    search = None
    if search_field:
        search = {
            "$or": [
                {"english_name": {'$regex': search_field}},
                {"farsi_name": {'$regex': search_field}},
            ]
        }

    query = {**query, **search} if search else query
    sort = {sort: 1} if sort[0] != "-" else {sort[1:]: -1}

    products = await db.products.find(
        {"$query": query, "$orderby": sort}
    ).skip(offset * limit).to_list(length=limit)

    if not products:
        return ProductListOutput()

    products = list(map(lambda x: ProductOutput.parse_obj_id(x), products))
    count = await db.products.count_documents(query)
    return ProductListOutput(products=products, count=count)


@router.patch('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
async def partial_update_product(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        product_id: ObjectId,
        data: ProductPartialUpdate

):
    """
    Admin

    Partial update product
    """
    data = await serve_nested_to_root(data.dict(exclude_unset=True))
    if data.get('guarantees'):
        await validate_guarantees(db, data.get('guarantees'))

    result = await db.products.update_one({'_id': product_id}, {'$set': {**data, 'updated_at': datetime.now()}})

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product was not updated successfully."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/{product_id}', response_model=ProductOutput)
async def get_single_product(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        product_id: ObjectId,

):
    """
    Admin and client

    Get single product
    """

    product = await db.products.find_one({'_id': product_id})
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found."
        )

    return ProductOutput.parse_obj_id(product)


@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        product_id: ObjectId,

):
    """
    Admin

    Delete product
    """

    result = await db.products.delete_one({'_id': product_id})
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not delete product."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# import sys
# from datetime import datetime
#
# import requests
# from django.shortcuts import re   nder
# from django.http import HttpResponse
# from django.shortcuts import redirect
# from zeep import Client
#
# from django.conf import settings
#
# from panel.models import Order
# from sms.utils import send_order_notif_sms, send_order_notif_sms_to_customer
#
# MERCHANT = '67b4ca7f-e25f-4d39-bfb8-cdd4f39377f4'
#
# if not settings.TEST:
#     client = Client('https://www.zarinpal.com/pg/services/WebGate/wsdl')
#
#
# def send_request(request, orderpk):
#     thisorder = Order.objects.get(pk=orderpk)
#
#     description = str(thisorder.order_id)  # "توضیحات مربوط به تراکنش را در این قسمت وارد کنید"
#     email = thisorder.customer.user.email
#     mobile = thisorder.customer.phone_number
#     CallbackURL = settings.WEBSITE_URL + '/zarinpal/verify/' + str(
#         thisorder.pk)  # Important: need to edit for real server.
#
#     amount = int(thisorder.final_price)
#     thisorder.date_ordered = datetime.now()
#     thisorder.payment_state = 'pending'
#     thisorder.decrease_product_counts()
#     thisorder.save()
#
#     result = client.service.PaymentRequest(MERCHANT, amount, description, email, mobile, CallbackURL)
#     if result.Status == 100:
#         return redirect('https://www.zarinpal.com/pg/StartPay/' + str(result.Authority))
#     else:
#         return HttpResponse('Error code: ' + str(result.Status))
#
#
# def verify(request, orderpk):
#     thisorder = Order.objects.get(pk=orderpk)
#
#     if request.GET.get('Status') == 'OK':
#         result = client.service.PaymentVerification(MERCHANT, request.GET['Authority'], thisorder.final_price)
#
#         print(result)
#
#         if result.Status == 100:
#             send_order_notif_sms(thisorder.order_id)
#             send_order_notif_sms_to_customer(thisorder.customer.phone_number, result.RefID)
#             thisorder.SaleReferenceId = result.RefID
#             thisorder.payment_state = 'paid'
#             thisorder.shipping_state = 'ordered'
#             thisorder.save()
#             try:
#                 thisorder.discount_code.used += 1
#                 thisorder.discount_code.save()
#             except Exception as e:
#                 # print(e)
#                 pass
#             context = {
#                 'success': True,
#                 'RefID': result.RefID
#             }
#             return render(request, 'store/transaction-return.html', context=context)
#
#         elif result.Status == 101:
#             return HttpResponse('Transaction submitted : ' + str(result.Status))
#
#         else:
#             thisorder.payment_state = 'failed'
#             thisorder.undecrease_product_counts()
#             thisorder.save()
#             context = {
#                 'success': False,
#             }
#             return render(request, 'store/transaction-return.html', context=context)
#     else:
#         thisorder.payment_state = 'failed'
#         thisorder.undecrease_product_counts()
#         thisorder.save()
#         context = {
#             'success': False,
#         }
#         return render(request, 'store/transaction-return.html', context=context)
