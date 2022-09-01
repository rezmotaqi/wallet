"""
Products apis
route: /products
"""
from datetime import datetime
from typing import Optional, List

from bson import ObjectId as BaseObjectId
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from starlette import status
from starlette.responses import Response

from app.core import depends
from app.core.utils import serve_nested_to_root
from app.schemas.base import DateOrderBy, ObjectId
from app.schemas.products import ProductInput, ProductListOutput, ProductOutput, ProductPartialUpdate, CartOutput
from app.schemas.users import User

router = APIRouter()


@router.post('/cart', status_code=status.HTTP_204_NO_CONTENT)
async def modify_cart(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        product_ids: List[ObjectId]
):
    """
    Client

    Modify cart, products in carts are updated based on provided list of product ids
    """

    now = datetime.now()

    products = await db.products.find(
        {'_id': {'$in': product_ids}}
    ).to_list(length=None)

    if not products:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Products were not found."
        )

    # check if all of the provided product ids are found
    found_product_ids = [product['_id'] for product in products]
    invalid_product_ids = []
    for i in product_ids:
        if i not in found_product_ids:
            invalid_product_ids.append(i)

    if invalid_product_ids:
        return Response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=invalid_product_ids
        )

    result = await db.carts.update_one(
        {'owner_id': BaseObjectId(current_user.id)},
        {
            '$setOnInsert': {
                'owner_id': current_user.id,
                'created_at': now
            },
            '$set': {
                'items': products,
                'updated_at': now
            }
        },
        upsert=True,
    )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Basket was not updated successfully"
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/cart/{user_id}', response_model=CartOutput)
async def get_cart(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        user_id: ObjectId,

):
    """
    Admin and client

    Get single product
    """

    cart = await db.carts.find_one({'owner_id': BaseObjectId(current_user.id)})
    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found."
        )

    return CartOutput.parse_obj(cart)


@router.post('', status_code=status.HTTP_201_CREATED)
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
async def get(
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
async def partial_update(
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
async def delete(
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
