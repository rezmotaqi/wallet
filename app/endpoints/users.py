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
    UserStatus,
    UserType,
    Roles,
)
from app.schemas.users import (
    User,
    UserSetPassword,
    UserChangePassword,
    SetUserType,
    UserCreate,
    UserListAdminOut,
    UserAdminOut,

    UserInfoAdminOut,
    NotificationListOut,
    NotificationSchema,
    UserInfoUpdate,
    UserInfoOut,
    UserInfoPartialUpdate
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

    try:
        data = {**data, 'updated_at': now, 'created_at': now}
        result = await db.users.insert_one(data)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Provided username is taken.')

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


@router.put("/admin/user/{user_id}", status_code=status.HTTP_200_OK)
async def admin_update_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId,
        request_info: UserInfoUpdate
) -> Any:
    """
    Admin

    Update a user's info

    Authorization: Required
    """

    now = datetime.now()
    try:
        result = await db.users.update_one({"_id": user_id}, {"$set": {**request_info.dict(), 'updated_at': now}})
    except DuplicateKeyError:
        return Response(status_code=status.HTTP_409_CONFLICT)
    if not result.acknowledged:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Could not update user.')
    return Response(status_code=status.HTTP_200_OK)


@router.patch("/admin/user/{user_id}", status_code=status.HTTP_200_OK)
async def admin_partial_update_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId,
        request_info: UserInfoPartialUpdate
) -> Any:
    """
    Admin

    Partial Update a user's info

    Authorization: Required
    """

    now = datetime.now()
    try:
        result = await db.users.update_one(
            {"_id": user_id},
            {"$set": {**request_info.nested_dict(exclude_unset=True), 'updated_at': now}}
        )
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
        {'contact_info': 1, 'basic_info': 1, 'status': 1, 'username': 1, 'created_at': 1})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserInfoAdminOut.parse_obj({**user, 'id': user.get('_id')})


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

    response_class = UserInfoOut
    return response_class.parse_obj({**user, 'id': user.get('_id'), 'password': password})


@router.put("")
async def update_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        request_info: UserInfoUpdate
) -> Any:
    """
    User
    
    Edit  user  info

    Authorization: Required
    """

    try:
        result = await db.users.update_one({"_id": current_user.id},
                                           {"$set": {**request_info.dict(), 'updated_at': datetime.now()}})
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


@router.patch("")
async def partial_update_user_info(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        request_info: UserInfoPartialUpdate
) -> Any:
    """
    User

    Edit a normal user  info

    Authorization: Required
    """
    try:
        result = await db.users.update_one(
            {"_id": current_user.id},
            {"$set": {**request_info.dict(exclude_unset=True), 'updated_at': datetime.now()}}
        )
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

