"""Users endpoints and logics.

Route: "/users"
"""

import random
from datetime import datetime, timedelta
from typing import Any, Optional, List

from bson import ObjectId as BaseObjectId
from fastapi import (
    status,
    Depends,
    APIRouter,
    HTTPException,
    Response
)
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from starlette.responses import JSONResponse

from app.config.settings import settings
from app.core import depends
from app.core.authentication import get_password_hash, verify_password
from app.core.utils import check_passwords, specify_username_type
from app.schemas.base import DateOrderBy, ObjectId
from app.schemas.general import (
    OperationResponse,
    UsernameType,
    UserStatus,
    UserType,
    NotificationCategory,
    ConnectionStatus,
    Roles,
    FriendshipAction
)
from app.schemas.users import (
    User,
    UserSetPassword,
    UserChangePassword,
    SetUserType,
    UserCreate,
    UserListAdminOut,
    UserAdminOut,
    FriendListOutSchema,
    FriendOutSchema,
    FriendRequestOutSchema,
    FriendRequestListOutSchema,
    CompanyUserInfoAdminOut,
    NormalUserInfoAdminOut,
    NotificationListOut,
    NotificationSchema,
    FriendSuggestionsListOut,
    CompanyUserInfoUpdate,
    CompanyUserInfoPartialUpdate,
    NormalUserInfoUpdate,
    FriendsSchema,
    NormalUserInfoOut,
    CompanyUserInfoOut,
    ParseDatabaseResultContactInfo,
    NormalUserInfoPartialUpdate
)

router = APIRouter()

"""
Users endpoints and logics.
Route: "/users"
"""


@router.post("/admin", status_code=status.HTTP_201_CREATED, response_model=User)
async def admin_create_user(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user: UserCreate
) -> Any:
    """
    Admin

    Create new user,

    Authorization: Required.
    """
    now = datetime.now()
    data = user.dict(exclude={'password1', 'password2'})
    password1 = user.password1.get_secret_value()
    password2 = user.password2.get_secret_value()
    check_passwords(password_1=password1, password_2=password2)
    data["password"] = get_password_hash(password1)
    data["owner_id"] = current_user.id
    username_type = specify_username_type(username=user.username)
    # add empty contact_info
    data['contact_info'] = {}
    if username_type == UsernameType.EMAIL:
        data['contact_info']['email'] = user.username
    elif username_type == UsernameType.MOBILE:
        data['contact_info']['mobile'] = user.username
    else:
        data.pop('contact_info')

    try:
        data = {**data, 'updated_at': now, 'created_at': now}
        result = await db.users.insert_one(data)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Provided mobile or email is taken.')

    if not result.acknowledged:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=OperationResponse.UNSUCCESSFUL_CREATE)
    return User.parse_obj({**data, "username": user.username, "id": result.inserted_id})


@router.get("/admin", response_model=UserListAdminOut)
async def admin_user_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        search_field: Optional[str] = None,
        from_date: Optional[datetime] = datetime(2000, 1, 1, 0, 0, 0, 0),
        to_date: Optional[datetime] = None,
        sort: Optional[DateOrderBy] = "-created_at",
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        status_variable: Optional[UserStatus] = None,
        user_type: Optional[UserType] = None
) -> Any:
    """
    Admin

    Get all account with the given queries (offset, limit),
    search_filed can have values of (username, mobile, email, first_name, last_name, status, role, user_type),

    Authorization: Required.
    """
    if not to_date:
        to_date = datetime.now()
    query = {"created_at": {"$gte": from_date, "$lte": to_date}}
    if status_variable:
        query['status'] = status_variable
    if user_type:
        query['user_type'] = user_type
    query['_id'] = {'$ne': current_user.id}

    search = None
    if search_field:
        search = {
            "$or": [
                {"username": {'$regex': search_field}},
                {"basic_info.first_name": {'$regex': search_field}},
                {"basic_info.last_name": {'$regex': search_field}},
            ]
        }

        # search = {"$text": {"$search": search_field}}

    query = {**query, **search} if search else query

    sort = {sort: 1} if sort[0] != "-" else {sort[1:]: -1}
    users_result = await db.users.find(
        {"$query": query, "$orderby": sort},
        {
            'username': 1,
            'created_at': 1,
            'status': 1,
            'user_type': 1,
            'basic_info.avatar': 1,
            'basic_info.cover': 1,
            'basic_info.first_name': 1,
            'basic_info.last_name': 1,
            'basic_info.company_name': 1,
        }
    ).skip(offset * limit).to_list(length=limit)

    users = [
        UserAdminOut.parse_obj(
            {
                'id': document.get('_id'),
                'username': document.get('username'),
                'created_at': document.get('created_at'),
                'status': document.get('status'),
                'user_type': document.get('user_type'),
                'avatar': document.get('basic_info').get('avatar') if document.get('basic_info') else None,
                'cover': document.get('basic_info').get('cover') if document.get('basic_info') else None,
                'first_name': document.get('basic_info').get('first_name') if document.get('basic_info') else None,
                'last_name': document.get('basic_info').get('last_name') if document.get('basic_info') else None,
                'company_name': document.get('basic_info').get('company_name') if document.get('basic_info') else None
            }
        ) for document in users_result]
    users_count = await db.users.count_documents(query)
    return UserListAdminOut(count=users_count, users=users)


@router.put("/admin/role/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_alter_role(
        *,
        role: List[Roles],
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId
) -> Any:
    """
    Admin

    Change user roles

    Authorization: Required
    """
    await db.users.update_one({"_id": user_id}, {"$set": {"role": role, "updated_at": datetime.now()}})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/admin/status/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_alter_status(
        *,
        status_variable: UserStatus,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId
) -> Any:
    """
    Admin

    Alter user status

    Authorization: Required
    """
    await db.users.update_one(
        {"_id": user_id}, {"$set": {"status": status_variable, "updated_at": datetime.now()}}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/admin/company_user/{user_id}", status_code=status.HTTP_200_OK)
async def admin_update_company_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId,
        request_info: CompanyUserInfoUpdate
) -> Any:
    """
    Admin

    Update a company user's  info

    Authorization: Required
    """

    now = datetime.now()
    info = request_info.dict()
    mobile = info.get('contact_info').get('mobile') if info.get('contact_info') else None
    email = info.get('contact_info').get('email') if info.get('contact_info') else None

    if mobile or email:
        or_query = []
        if mobile:
            or_query.append({'contact_info.mobile': mobile})
        if email:
            or_query.append({'contact_info.email': email})
        if or_query:
            result = await db.users.find_one(
                {'$or': or_query, '_id': {'$ne': user_id}},
                {'contact_info.mobile': 1, 'contact_info.email': 1}
            )
            if result:
                result = ParseDatabaseResultContactInfo.parse_obj(result)
                result = result.dict()
                if mobile:
                    if mobile == result.get('contact_info').get('mobile'):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided mobile is used.')
                if email == result.get('contact_info').get('email'):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided email is used.')

    info = {**info, 'updated_at': now}
    try:
        result = await db.users.update_one({"_id": user_id, "user_type": UserType.COMPANY}, {"$set": info})
    except DuplicateKeyError:
        return Response(status_code=status.HTTP_409_CONFLICT)
    if not result.acknowledged:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Could not update user.')

    return Response(status_code=status.HTTP_200_OK)


@router.patch("/admin/company_user/{user_id}", status_code=status.HTTP_200_OK)
async def admin_partial_update_company_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId,
        request_info: CompanyUserInfoPartialUpdate
) -> Any:
    """
    Admin

    Partial update a company user's info

    Authorization: Required
    """

    now = datetime.now()
    info = request_info.nested_dict(exclude_unset=True)
    mobile = info.get('contact_info').get('mobile') if info.get('contact_info') else None
    email = info.get('contact_info').get('email') if info.get('contact_info') else None

    if mobile or email:
        or_query = []
        if mobile:
            or_query.append({'contact_info.mobile': mobile})
        if email:
            or_query.append({'contact_info.email': email})
        if or_query:
            result = await db.users.find_one(
                {'$or': or_query, '_id': {'$ne': user_id}},
                {'contact_info.mobile': 1, 'contact_info.email': 1}
            )
            if result:
                result = ParseDatabaseResultContactInfo.parse_obj(result)
                result = result.dict()
                if mobile:
                    if mobile == result.get('contact_info').get('mobile'):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided mobile is used.')
                if email == result.get('contact_info').get('email'):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided email is used.')
    info = {**info, 'updated_at': now}
    try:
        result = await db.users.update_one({"_id": user_id, "user_type": UserType.COMPANY}, {"$set": info})
    except DuplicateKeyError:
        return Response(status_code=status.HTTP_409_CONFLICT)
    if not result.acknowledged:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Could not update user.')

    return Response(status_code=status.HTTP_200_OK)


@router.put("/admin/normal_user/{user_id}", status_code=status.HTTP_200_OK)
async def admin_update_normal_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId,
        request_info: NormalUserInfoUpdate
) -> Any:
    """
    Admin

    Update a normal user's info

    Authorization: Required
    """

    now = datetime.now()
    info = request_info.dict()
    mobile = info.get('contact_info').get('mobile') if info.get('contact_info') else None
    email = info.get('contact_info').get('email') if info.get('contact_info') else None
    if mobile or email:
        or_query = []
        if mobile:
            or_query.append({'contact_info.mobile': mobile})
        if email:
            or_query.append({'contact_info.email': email})
        if or_query:
            result = await db.users.find_one(
                {'$or': or_query, '_id': {'$ne': user_id}},
                {'contact_info.mobile': 1, 'contact_info.email': 1}
            )
            if result:
                result = ParseDatabaseResultContactInfo.parse_obj(result)
                result = result.dict()
                if mobile:
                    if mobile == result.get('contact_info').get('mobile'):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided mobile is used.')
                if email == result.get('contact_info').get('email'):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided email is used.')
    info = {**info, 'updated_at': now}
    try:
        result = await db.users.update_one({"_id": user_id}, {"$set": info})
    except DuplicateKeyError:
        return Response(status_code=status.HTTP_409_CONFLICT)
    if not result.acknowledged:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Could not update user.')
    return Response(status_code=status.HTTP_200_OK)


@router.patch("/admin/normal_user/{user_id}", status_code=status.HTTP_200_OK)
async def admin_partial_update_normal_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId,
        request_info: NormalUserInfoPartialUpdate
) -> Any:
    """
    Admin

    Partial Update a normal user's info

    Authorization: Required
    """

    now = datetime.now()
    info = request_info.nested_dict(exclude_unset=True)
    mobile = info.get('contact_info').get('mobile') if info.get('contact_info') else None
    email = info.get('contact_info').get('email') if info.get('contact_info') else None
    if mobile or email:
        or_query = []
        if mobile:
            or_query.append({'contact_info.mobile': mobile})
        if email:
            or_query.append({'contact_info.email': email})
        if or_query:
            result = await db.users.find_one(
                {'$or': or_query, '_id': {'$ne': user_id}},
                {'contact_info.mobile': 1, 'contact_info.email': 1}
            )
            if result:
                result = ParseDatabaseResultContactInfo.parse_obj(result)
                result = result.dict()
                if mobile:
                    if mobile == result.get('contact_info').get('mobile'):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided mobile is used.')
                if email == result.get('contact_info').get('email'):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided email is used.')
    info = {**info, 'updated_at': now}
    try:
        result = await db.users.update_one({"_id": user_id}, {"$set": info})
    except DuplicateKeyError:
        return Response(status_code=status.HTTP_409_CONFLICT)
    if not result.acknowledged:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Could not update user.')
    return Response(status_code=status.HTTP_200_OK)


@router.put("/admin/password/{user_id}")
async def admin_change_password(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        password: UserSetPassword,
        user_id: ObjectId
):
    """
    Admin

    Change user password

    Authorization: Required
    """
    user = await db.users.find_one({'_id': user_id}, {'password': 1})
    check_passwords(
        user=user,
        password_1=password.new_password.get_secret_value(),
        password_2=password.new_password_confirm.get_secret_value())
    result = await db.users.find_one_and_update(
        {"_id": user_id},
        {"$set": {
            "password": get_password_hash(password.new_password.get_secret_value()),
            "updated_at": datetime.now()
        }}
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not update password. ")
    return {"message": "Password changed successfully"}


@router.get("/admin/{user_id}")
async def admin_get_user(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId
) -> Any:
    """
    Admin

    Get user by user_id

    Authorization: Required.
    """
    user = await db.users.find_one(
        {"_id": user_id},
        {'contact_info': 1, 'basic_info': 1, 'status': 1, 'user_type': 1, 'username': 1, 'created_at': 1})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    response_class = NormalUserInfoAdminOut if user.get("user_type") == UserType.NORMAL else CompanyUserInfoAdminOut
    return response_class.parse_obj({**user, 'id': user.get('_id')})


@router.delete("/admin/{user_id}")
async def admin_delete_user(
        user_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"]))
) -> Any:
    """
    Admin

    Delete user,

    Authorization: Required.
    """
    result = await db.users.delete_one({"_id": user_id})
    if not result.acknowledged:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User could not be deleted")

    await db.skills.delete_one({"owner_id": user_id})
    await db.events.delete_one({"owner_id": user_id})
    await db.posts.delete_one({"owner_id": user_id})
    await db.friends.delete_one({"$or": [{'requested_id': user_id}, {'requested_id': user_id}]})

    # TODO add other places that user data

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/me')
async def get_current_user_information(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
) -> Any:
    """
    Get current user's information

    Authorization: Required
    """

    user = await db.users.find_one(
        {"_id": current_user.id},
        {
            'contact_info': 1,
            'basic_info': 1,
            'status': 1,
            'username': 1,
            'created_at': 1,
            'user_type': 1,
            'public_portfolio': 1,
            'password': 1
        }
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    password = False
    if user.get('password'):
        password = True

    response_class = NormalUserInfoOut if user.get("user_type") == UserType.NORMAL else CompanyUserInfoOut
    return response_class.parse_obj({**user, 'id': user.get('_id'), 'password': password})


@router.put("/normal_user")
async def update_normal_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        request_info: NormalUserInfoUpdate
) -> Any:
    """
    Edit a normal user  info

    Authorization: Required
    """
    info = request_info.dict()
    mobile = info.get('contact_info').get('mobile') if info.get('contact_info') else None
    email = info.get('contact_info').get('email') if info.get('contact_info') else None
    or_query = []
    if mobile:
        or_query.append({'contact_info.mobile': mobile})
    if email:
        or_query.append({'contact_info.email': email})
    if or_query:
        result = await db.users.find_one(
            {'$or': or_query, '_id': {'$ne': current_user.id}},
            {'contact_info.mobile': 1, 'contact_info.email': 1}
        )
        if result:
            result = ParseDatabaseResultContactInfo.parse_obj(result)
            result = result.dict()
            if mobile:
                if mobile == result.get('contact_info').get('mobile'):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided mobile is used.')
            if email == result.get('contact_info').get('email'):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided email is used.')
    info = {**info, 'updated_at': datetime.now()}

    try:
        result = await db.users.update_one({"_id": current_user.id}, {"$set": info})
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provided mobile or email is taken. "
        )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/normal_user")
async def partial_update_normal_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        request_info: NormalUserInfoPartialUpdate
) -> Any:
    """
    User

    Edit a normal user  info

    Authorization: Required
    """

    info = request_info.nested_dict(exclude_unset=True)
    mobile = info.get('contact_info.mobile')
    email = info.get('contact_info.email')
    or_query = []
    if mobile:
        or_query.append({'contact_info.mobile': mobile})
    if email:
        or_query.append({'contact_info.email': email})
    if or_query:
        result = await db.users.find_one(
            {'$or': or_query, '_id': {'$ne': current_user.id}},
            {'contact_info.mobile': 1, 'contact_info.email': 1}
        )
        if result:
            result = ParseDatabaseResultContactInfo.parse_obj(result)
            result = result.dict()
            if mobile:
                if mobile == result.get('contact_info').get('mobile'):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided mobile is used.')
            if email == result.get('contact_info').get('email'):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided email is used.')

    info = {**info, 'updated_at': datetime.now()}

    try:
        result = await db.users.update_one({"_id": current_user.id}, {"$set": info})
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provided mobile or email is taken. "
        )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return {'message': "Successfully updated."}


@router.put("/company_user")
async def update_company_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        request_info: CompanyUserInfoUpdate
) -> Any:
    """
    User

    Edit a company user  info

    Authorization: Required
    """
    info = request_info.dict()
    mobile = info.get('contact_info').get('mobile') if info.get('contact_info') else None
    email = info.get('contact_info').get('email') if info.get('contact_info') else None
    or_query = []
    if mobile:
        or_query.append({'contact_info.mobile': mobile})
    if email:
        or_query.append({'contact_info.email': email})
    if or_query:
        result = await db.users.find_one(
            {'$or': or_query, '_id': {'$ne': current_user.id}},
            {'contact_info.mobile': 1, 'contact_info.email': 1}
        )
        if result:
            result = ParseDatabaseResultContactInfo.parse_obj(result)
            result = result.dict()
            if mobile:
                if mobile == result.get('contact_info').get('mobile'):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided mobile is used.')
            if email == result.get('contact_info').get('email'):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided email is used.')
    info = {**info, 'updated_at': datetime.now()}

    try:
        result = await db.users.update_one({"_id": current_user.id}, {"$set": info})
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provided mobile or email is taken. "
        )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/company_user")
async def partial_update_company_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        request_info: CompanyUserInfoPartialUpdate
) -> Any:
    """
    User

    Edit a company user info

    Authorization: Required
    """
    now = datetime.now()
    info = request_info.nested_dict(exclude_unset=True)
    mobile = info.get('contact_info.mobile')
    email = info.get('contact_info.email')
    or_query = []
    if or_query:
        if mobile:
            or_query.append({'contact_info.mobile': mobile})
        if email:
            or_query.append({'contact_info.email': email})
        if or_query:
            result = await db.users.find_one(
                {'$or': or_query, '_id': {'$ne': current_user.id}},
                {'contact_info.mobile': 1, 'contact_info.email': 1}
            )
            if result:
                result = ParseDatabaseResultContactInfo.parse_obj(result)
                result = result.dict()
                if mobile:
                    if mobile == result.get('contact_info').get('mobile'):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided mobile is used.')
                if email == result.get('contact_info').get('email'):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Provided email is used.')

    info = {**info, 'updated_at': now}

    try:
        result = await db.users.update_one({"_id": current_user.id}, {"$set": info})
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provided mobile or email is taken. "
        )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return {'message': "Successfully updated."}


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_user(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
) -> Any:
    """
    User

    Delete current user.

    Authorization: Required.
    """

    result = await db.users.update_one({"_id": current_user.id}, {'$set': {'status': UserStatus.DELETED}})
    if not result.acknowledged:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="User could not be deleted")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/password")
async def check_password(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """
    Check if user has set password

    Authorization: Required
    """

    result = await db.users.find_one({'_id': current_user.id}, {'_id': 1, 'password': 1})
    if result:
        if result.get('password'):
            return Response(status_code=status.HTTP_200_OK, content="Password found.")
    return Response(status_code=status.HTTP_404_NOT_FOUND, content="Password not found.")


@router.post("/password")
async def set_password(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        password: UserSetPassword
) -> Any:
    """
    IF User has not set a password yet, they can Set new password with this api

    Authorization: Required
    """

    result = await db.users.find_one({"username": current_user.username}, {"_id": 1, "username": 1, "password": 1})
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if result.get('password'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a password, user change password API instead"
        )
    check_passwords(
        user=result,
        password_1=password.new_password.get_secret_value(),
        password_2=password.new_password_confirm.get_secret_value())
    result = await db.users.find_one_and_update(
        {"username": current_user.username},
        {"$set": {
            "password": get_password_hash(password.new_password.get_secret_value()),
            "updated_at": datetime.now()}}
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not update password")
    return {"message": "password added successfully"}


@router.patch("/password", status_code=status.HTTP_200_OK)
async def change_password(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        password: UserChangePassword
) -> Any:
    """
    User

    Change current user's password.

    Authorization: Required
    """

    result = await db.users.find_one({"username": current_user.username}, {"_id": 1, "username": 1, "password": 1})
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not result.get('password'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has not set password. "
        )
    user_current_password = result['password']
    if not verify_password(password.current_password.get_secret_value(), user_current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current entered password is wrong"
        )
    check_passwords(
        user=result,
        password_1=password.new_password.get_secret_value(),
        password_2=password.new_password_confirm.get_secret_value()
    )
    result = await db.users.find_one_and_update(
        {"username": current_user.username},
        {"$set": {
            "password": get_password_hash(password.new_password.get_secret_value()),
            "updated_at": datetime.now()}}
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not update password")
    return {"message": "Password changed successfully"}


@router.post("/type", status_code=status.HTTP_200_OK)
async def set_user_type(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: SetUserType
) -> Any:
    """
    User

    Set user type, only works first time (new user has guest as value for user_type)

    Authorization: Required
    """
    result = await db.users.update_one(
        {
            "_id": current_user.id,
            "user_type": {'$eq': UserType.GUEST.value}
        },
        {"$set": {"user_type": data.user_type, "updated_at": datetime.now()}}
    )

    if result.raw_result.get('nModified') == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=OperationResponse.UNSUCCESSFUL_UPDATE
        )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=OperationResponse.UNSUCCESSFUL_UPDATE)
    response = {"message": OperationResponse.SUCCESSFUL_UPDATE}
    return response


@router.post('/friends/action/{user_id}', status_code=status.HTTP_200_OK)
async def perform_friendship_action(
        user_id: ObjectId,
        action: FriendshipAction,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """
    Perform Friendship action (send_request, accept_request, deny_request, delete_friend)

    Authorization: Required
    """

    now = datetime.now()

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can not do operation on self user"
        )

    if action == FriendshipAction.DENY:
        await db.friends.delete_one({
            'requester_id': user_id,
            'requested_id': BaseObjectId(current_user.id),
            'status': ConnectionStatus.PENDING
        })

        await db.notifications.delete_one(
            {
                'owner_id': BaseObjectId(current_user.id),
                'extra_data.user.id': BaseObjectId(user_id),
                'category': NotificationCategory.FRIENDSHIP.value
            })

    elif action == FriendshipAction.DELETE:
        await db.friends.delete_one({
            '$or': [
                {'requester_id': user_id, 'requested_id': BaseObjectId(current_user.id)},
                {'requested_id': user_id, 'requester_id': BaseObjectId(current_user.id)}
            ],
            'status': ConnectionStatus.CONNECTED
        })

    elif action == FriendshipAction.REQUEST:

        requester_id = current_user.id
        requested_id = user_id
        users_id = [requester_id, requested_id]
        users = await db.users.find(
            {'_id': {'$in': users_id}},
            {
                'basic_info.first_name': 1,
                'basic_info.last_name': 1,
                'basic_info.avatar': 1,
                'basic_info.headline': 1
            }
        ).to_list(length=None)
        if not users or len(users) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Users not found. "
            )

        requester_user = None
        requested_user = None
        for i, user in enumerate(users):

            if user['_id'] == requester_id:
                requester_user = users[i]
            if user['_id'] == requested_id:
                requested_user = users[i]

        requester_user = {**requester_user, 'id': requester_user.get('_id')}
        requested_user = {**requested_user, 'id': requested_user.get('_id')}

        friend_request = {
            'requester_user': requester_user,
            'requested_user': requested_user,
        }
        friend_request = FriendsSchema.parse_obj(friend_request)

        request_result = await db.friends.find_one(
            {
                '$or': [
                    {'requester_id': user_id, 'requested_id': current_user.id},
                    {'requested_id': user_id, 'requester_id': current_user.id}
                ]
            },
            {'status': 1, 'updated_at': 1, 'requested_user': 1, 'requester_user': 1}
        )

        if request_result:

            if request_result.get('status') == ConnectionStatus.CONNECTED:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={'message': "You are already connected to this user. "}
                )

            # current user role in friend request (requester or requested)
            user_is_requester = True if current_user.id == request_result.get('requester_user').get('id') else False

            # check if user request has been rejected and FRIEND_REQUEST_AGAIN_AFTER_DAYS has passed after request time
            if user_is_requester and request_result.get('status') == ConnectionStatus.REJECTED.value and \
                    now - request_result.get('updated_at') < timedelta(days=settings.FRIEND_REQUEST_AGAIN_AFTER_DAYS):
                request_again_in = request_result.get('updated_at') + timedelta(
                    days=settings.FRIEND_REQUEST_AGAIN_AFTER_DAYS)

                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "request_after": str(request_again_in),
                        "message": f"You can request again after {request_again_in}. "
                    }
                )
            # check if other user has requested current user before and request status is pending
            elif not user_is_requester and request_result.get('status') == ConnectionStatus.PENDING:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={'message': "The other user has already requested you. "}
                )

            elif user_is_requester and request_result.get('status') == ConnectionStatus.PENDING:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={'message': "You have already requested this user. "}
                )

        insert_result = await db.friends.update_one(
            {
                'requester_id': requester_id, 'requested_id': requested_id
            },
            {'$set': friend_request.dict()},
            upsert=True
        )
        if not insert_result:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=OperationResponse.UNSUCCESSFUL_CREATE
            )

        notification = {
            'owner_id': requested_id,
            'created_at': now,
            'seen': False,
            'category': NotificationCategory.FRIENDSHIP,
            'actionable': True,
            'extra_data': {
                'user': {
                    'id': requester_id,
                    'avatar': friend_request.requester_user.basic_info.avatar,
                    'first_name': friend_request.requester_user.basic_info.first_name,
                    'last_name': friend_request.requester_user.basic_info.last_name
                }
            }}

        notification_result = await db.notifications.update_one(
            {
                'owner_id': requested_id,
                'category': NotificationCategory.FRIENDSHIP,
                'extra_data.requester_id': requester_id
            },
            {'$set': notification}, upsert=True)
        if not notification_result.acknowledged:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not create notification"
            )

    elif action == FriendshipAction.ACCEPT:
        result = await db.friends.update_one(
            {'requester_id': user_id, 'requested_id': current_user.id, 'status': ConnectionStatus.PENDING},
            {'$set': {'status': ConnectionStatus.CONNECTED, 'updated_at': now}}
        )
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found"
            )

        await db.notifications.delete_one(
            {
                'owner_id': BaseObjectId(current_user.id),
                'extra_data.user.id': BaseObjectId(user_id),
                'category': NotificationCategory.FRIENDSHIP.value
            })

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/friend_requests', status_code=status.HTTP_200_OK)
async def my_friend_requests(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20
):
    """
    Get list of friend requests

    Authorization: Required
    """

    requests_result = await db.friends.find(
        {'requested_id': current_user.id, 'status': ConnectionStatus.PENDING},
        {
            'requester_id': 1,
            'requester_user': 1,
            'created_at': 1
        }
    ).skip(offset * limit).to_list(length=limit)
    if not requests_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have no requests. "
        )
    count = await db.friends.count_documents({'requested_id': current_user.id, 'status': ConnectionStatus.PENDING})
    requests = list(map(
        lambda x: FriendRequestOutSchema.parse_obj(
            {
                'id': x.get('requester_id'),
                'created_at': x.get('created_at'),
                'first_name': x.get('requester_user').get('basic_info').get('first_name'),
                'last_name': x.get('requester_user').get('basic_info').get('last_name'),
                'avatar': x.get('requester_user').get('basic_info').get('avatar'),
                'headline': x.get('requester_user').get('basic_info').get('headline')
            }
        ), requests_result
    ))
    return FriendRequestListOutSchema(requests=requests, count=count)


@router.get('/friends', response_model=FriendListOutSchema)
async def my_friends(
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Get list of friends

    Authorization: Required
    """

    friends_raw_result = await db.friends.find(
        {
            '$or': [{'requested_id': current_user.id}, {'requester_id': current_user.id}],
            'status': ConnectionStatus.CONNECTED
        }
    ).skip(offset * limit).to_list(length=limit)
    if not friends_raw_result:
        return FriendListOutSchema()

    friends_ids = list(map(
        lambda x: x.get("requested_id") if x.get(
            'requester_id'
        ) == BaseObjectId(current_user.id) else x.get("requester_id"),
        friends_raw_result
    ))

    friends_details = await db.users.find(
        {"_id": {"$in": friends_ids}},
        {'_id': 1, 'basic_info': 1}
    ).to_list(length=None)

    friends = list(map(
        lambda x: FriendOutSchema.parse_obj({
            "id": x.get("_id"),
            "first_name": x.get('basic_info', {}).get('first_name'),
            "last_name": x.get('basic_info', {}).get('last_name'),
            "avatar": x.get('basic_info', {}).get('avatar'),
            "cover": x.get('basic_info', {}).get('cover'),
            "headline": x.get('basic_info', {}).get('headline')
        }),
        friends_details if friends_details else []
    ))

    return FriendListOutSchema(friends=friends, count=len(friends_details))


@router.get('/notifications')
async def get_notifications(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        seen: Optional[bool] = None
):
    """
    Get user notifications

    Authorization: Required
    """
    query = {'owner_id': current_user.id}

    if seen is not None:
        query['seen'] = seen

    count = await db.notifications.count_documents(query)

    notifications_response = await db.notifications.find({
        '$query': query,
        '$orderby': {'created_at': -1}
    }).skip(offset * limit).to_list(length=limit)
    notifications = list(map(
        lambda notif: NotificationSchema.parse_obj({**notif, 'id': notif.get('_id')}),
        notifications_response
    ))
    return NotificationListOut(notifications=notifications, count=count)


@router.post('/notifications')
async def seen_notifications(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        notifications: List[ObjectId]
):
    """
    Update user's notifications to seen status

    Authorization: Required
    """
    result = await db.notifications.update_many(
        {'_id': {'$in': notifications}, 'owner_id': current_user.id},
        {'$set': {'seen': True}}
    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not update objects.')
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/friend_suggestions')
async def get_friend_suggestions(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
):
    """
    Get friend suggestions based on mutual skills

    # if current user has skills => get random skill from 0 to 5 index from skill values (skills values can be empty)

    # OR if current user does not have skill => get 10 random docs from skills (other users must have set skills)

    Authorization: Required
    """

    skills_result = await db.skills.find_one(
        {'owner_id': current_user.id},
        {'skills': 1}
    )

    connections_result = await db.friends.find(
        {'$or': [{'requester_id': current_user.id}, {'requested_id': current_user.id}]}
    ).to_list(length=None)

    connections_ids = []
    if connections_result:
        for friend in connections_result:
            if friend.get('requester_id') == current_user.id:
                connections_ids.append(friend.get('requested_id'))
            elif friend.get('requested_id') == current_user.id:
                connections_ids.append(friend.get('requester_id'))

    if skills_result and skills_result.get('skills'):
        skills = skills_result.get('skills')
        # if user has more than 5 skills, random index is generated from 0 to 5
        random_index = random.randint(0, len(skills)) if len(skills) <= 5 else random.randint(0, 5)
        random_skill = skills[random_index - 1]

        result = await db.skills.find(
            {'skills': random_skill,
             '$and': [
                 {'owner_id': {'$nin': connections_ids}},
                 {'owner_id': {'$ne': current_user.id}}
             ]
             },
            {'owner_id': 1, 'avatar': 1, 'first_name': 1, 'last_name': 1, 'headline': 1, '_id': 0}
        ).to_list(length=10)
        count = len(result)
        return FriendSuggestionsListOut(users=result, count=count)

    else:

        pipeline = [
            {'$match': {'$and': [
                {'owner_id': {'$nin': connections_ids}},
                {'owner_id': {'$ne': current_user.id}},
            ]}},
            {'$project': {'owner_id': 1, 'avatar': 1, 'first_name': 1, 'last_name': 1, 'headline': 1, '_id': 0}},
            {'$sample': {'size': 10}},
        ]

        result = [document async for document in db.skills.aggregate(pipeline)]

        count = len(result)

        return FriendSuggestionsListOut(users=result, count=count)


@router.get('/admin/friends/{user_id}')
async def get_user_friends(
        user_id: ObjectId,
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"]))
):
    """
    Admin

    Get user friends

    Authorization: Required
    """

    friends_raw_result = await db.friends.find(
        {
            '$or': [{'requested_id': user_id}, {'requester_id': user_id}],
            'status': ConnectionStatus.CONNECTED
        }
    ).skip(offset * limit).to_list(length=limit)
    if not friends_raw_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User has no friends"
        )

    friends_ids = list(map(
        lambda x: x.get("requested_id") if x.get(
            'requester_id'
        ) == BaseObjectId(current_user.id) else x.get("requester_id"),
        friends_raw_result
    ))

    friends_details = await db.users.find(
        {"_id": {"$in": friends_ids}},
        {'_id': 1, 'basic_info': 1}
    ).to_list(length=None)

    friends = list(map(
        lambda x: FriendOutSchema.parse_obj({
            "id": x.get("_id"),
            "first_name": x.get('basic_info', {}).get('first_name'),
            "last_name": x.get('basic_info', {}).get('last_name'),
            "avatar": x.get('basic_info', {}).get('avatar'),
            "cover": x.get('basic_info', {}).get('cover'),
            "headline": x.get('basic_info', {}).get('headline')
        }),
        friends_details if friends_details else []
    ))

    return FriendListOutSchema(friends=friends, count=len(friends_details))
