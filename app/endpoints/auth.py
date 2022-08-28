"""
Authentication endpoints and views.

Route: "/auth"
"""

import time
from datetime import timedelta, datetime
from typing import Any

import google.auth.transport
import requests
from aioredis.client import Redis
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Response, Path, Header
from google.oauth2 import id_token
from httpx_oauth.oauth2 import GetAccessTokenError
from jose import ExpiredSignatureError, JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import SecretStr
from pymongo.errors import DuplicateKeyError

from app.config.settings import settings
from app.core import depends
from app.core.authentication import (
    get_password_hash,
    generate_otp_token,
    create_token,
    decode_refresh_token,
    return_linkedin_client,
    google_oauth2flow, check_user_status
)
from app.core.utils import specify_username_type, check_passwords
from app.handlers.email import send_register_mail, send_login_mail
from app.handlers.kavenegarx import KavenegarX
from app.schemas.general import (
    Roles,
    OperationResponse,
    Token,
    UsernameType,
    UserType,
    UserStatus
)
from app.schemas.users import (
    User,
    UsernameLookupIn,
    RegisterDataIn,
    UserSignUpIn
)

router = APIRouter()

"""
Authentication endpoints and views.
Route: "/auth"
"""


@router.post("/login")
async def login_access_token(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        redis: Redis = Depends(depends.get_redis),
        kavenegarx: KavenegarX = Depends(depends.get_kavenegarx),
        user: User = Depends(depends.basic_authenticate)
) -> Any:
    """
    Generate or get if exists access token based on basic auth (login).
    if two_step is true for user, after validating password an otp token is sent to username and to
    get login token you must call the otp_login api with the otp that was sent to you
    !!! if two_step is true, authorize button in open api will not work correctly
    Authorization: Not Required
    """

    username_type = specify_username_type(user.username)
    if user.two_step:
        token = generate_otp_token()

        await redis.set(
            user.username,
            token,
            settings.SMS_OTP_TOKEN_EXPIRE_SECONDS if
            username_type == UsernameType.MOBILE else settings.EMAIL_OTP_TOKEN_EXPIRE_SECONDS
        )
        if username_type == UsernameType.MOBILE:
            if not settings.USE_SMS:
                return {'message': 'USE_SMS is false.'}

            try:
                await kavenegarx.lookup(
                    receptor=user.username,
                    token=token,
                    template=settings.KAVENEGAR_LOGIN_TEMPLATE
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Couldn't communicate with Kavenegar to send OTP token") from e

            return {'success': True, 'message': f'OTP is sent to {user.username}'}
        elif username_type == UsernameType.EMAIL:
            # TODO add background job for sending sms
            await send_login_mail([user.username], token)
            return {'success': True, 'message': f'OTP is sent to {user.username}'}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Username not of valid type for two_step.'
            )
    data = {
        "sub": str(user.id),
        "username": user.username,
        "scope": [*user.role, "authenticated"] if user.role else ["authenticated"],
        "iat": int(time.time())
    }
    access_token = create_token(
        data=data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    data["grant_type"] = "refresh"
    refresh_token = create_token(
        data=data,
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    try:
        await db.users.update_one(
            {"username": user.username},
            {"$set": {"last_login": datetime.now()}}
        )
    except Exception as e:
        print(e)
        HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User could not be updated.")
    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@router.post("/otp_login_send")
async def otp_login_send(
    db: AsyncIOMotorDatabase = Depends(depends.get_database),
    kavenegarx: KavenegarX = Depends(depends.get_kavenegarx),
    redis: Redis = Depends(depends.get_redis),
    username: str = Body(Ellipsis, embed=True)
    ) -> Any:
    """
    Call this api to login using mobile and otp, validates username and sends otp to mobile

    Authorization: Required
    """
    username_type = specify_username_type(username)
    user = await db.users.find_one({'username': username}, {"_id": 1, "status": 1})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No user found with the given mobile')

    check_user_status(user)
    token = generate_otp_token()

    if await redis.ttl(f"signup_{username}") > 30:
        time_left = await redis.ttl(f"signup_{username}")
        return Response(status_code=status.HTTP_200_OK, content=f"{time_left}")

    await redis.set(
        f"otp_login_{username}",
        token,
        settings.SMS_OTP_TOKEN_EXPIRE_SECONDS if username_type == UsernameType.MOBILE else
        settings.EMAIL_OTP_TOKEN_EXPIRE_SECONDS
    )

    if username_type == UsernameType.MOBILE:
        if not settings.USE_SMS:
            return {'message': 'USE_SMS is false. '}
        try:
            await kavenegarx.lookup(receptor=username, token=token, template=settings.KAVENEGAR_LOGIN_TEMPLATE)

            return {'success': True, 'message': f'OTP is sent to {username}'}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Couldn't communicate with Kavenegar to send OTP token"
            ) from e

    elif username_type == UsernameType.EMAIL:
        await send_login_mail([username], token)
        return {'success': True, 'message': f'OTP is sent to {username}'}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong type of username")


@router.post("/otp_login_verify")
async def otp_login_verify(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        redis: Redis = Depends(depends.get_redis),
        username: str = Body(..., embed=True),
        otp: SecretStr = Body(..., embed=True)
) -> Any:
    """
    Call this api to login using mobile and otp, takes username and otp, validates them, returns login token

    Authorization: Not required
    """

    username_type = specify_username_type(username)
    if username_type not in (UsernameType.MOBILE, UsernameType.EMAIL):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wrong type of username"
        )
    user = await db.users.find_one({"username": username}, {"_id": 1, "username": 1, "role": 1, "status": 1})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user found with the given mobile"
        )
    check_user_status(user)
    otp_token = await redis.get(f"otp_login_{username}")
    if not otp_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid otp token")
    await redis.delete(f"otp_login_{username}")
    otp_token = otp_token.decode()
    if otp.get_secret_value() != otp_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP token"
        )
    data = {
        "sub": str(user.get("_id")),
        "username": user.get("username"),
        "scope": [*user.get("role"), "authenticated"] if user.get("role") else ["authenticated"],
        "iat": int(time.time())
    }
    access_token = create_token(
        data=data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    data["grant_type"] = "refresh"
    refresh_token = create_token(
        data=data,
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    try:
        await db.users.update_one(
            {"username": user.username},
            {"$set": {"last_login": datetime.now()}}
        )
    except Exception as e:
        print(e)
        HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User could not be updated")
    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@router.get("/me", response_model=User)
async def get_current_user(user: User = Depends(depends.get_current_user)) -> Any:
    """
    Get the current user's information, also can be used to test access token.

    Authorization: Required
    """
    return user


@router.post("/otp_password_recover/{mobile}")
async def otp_password_recover(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        redis: Redis = Depends(depends.get_redis),
        kavenegarx: KavenegarX = Depends(depends.get_kavenegarx),
        mobile: str = Path(..., regex=settings.IRANIAN_MOBILE_REGEX)
):
    """
    1- checks if user with given username exists and has mobile number
    2- sends otp to mobile number
    """

    result = await db.users.find_one(
        {"$or": [{"username": mobile}, {"contact_info": mobile}]},
        {"username": 1, "status": 1}
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user found with the given mobile"
        )

    check_user_status(result)

    if await redis.ttl(f"signup_{mobile}") > 30:
        time_left = await redis.ttl(f"signup_{mobile}")
        return Response(status_code=status.HTTP_200_OK, content=f"{time_left}")

    token = generate_otp_token()
    await redis.set(f"otp_password_recover_{mobile}", token, settings.SMS_OTP_TOKEN_EXPIRE_SECONDS)
    if settings.USE_SMS:
        try:
            await kavenegarx.lookup(
                receptor=mobile,
                token=token,
                template=settings.KAVENEGAR_LOGIN_TEMPLATE
            )
        except:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Couldn't communicate with Kavenegar to send OTP token"
            )
    else:
        return {'message': 'USE_SMS is false'}
    return {"success": True}


@router.post("/otp_password_reset/{username}")
async def otp_password_reset(
    *,
    db: AsyncIOMotorDatabase = Depends(depends.get_database),
    redis: Redis = Depends(depends.get_redis),
    mobile: str = Path(Ellipsis, regex=settings.IRANIAN_MOBILE_REGEX),
    token: SecretStr = Body(Ellipsis, embed=True),
    password1: SecretStr = Body(Ellipsis, embed=True),
    password2: SecretStr = Body(Ellipsis, embed=True)
):
    """Verifies sent otp for password recovery, if username and otp are valid, returns token to client for next step,
    nextstep takes token and new password """
    result = await db.users.find_one({
        "$or": [{"username": mobile}, {"contact_info": mobile}]},
        {"username": 1, "password": 1, "status": 1}
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login")
    check_user_status(result)
    otp_token = await redis.get(f"otp_password_recover_{mobile}")
    if not otp_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid otp token")

    await redis.delete(f"otp_password_recover_{mobile}")
    otp_token = otp_token.decode()
    if token.get_secret_value() != otp_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP token")

    password1 = password1.get_secret_value()
    password2 = password2.get_secret_value()
    check_passwords(user=result, password_1=password1, password_2=password2)
    await db.users.find_one_and_update({"username": mobile}, {"$set": {"password": get_password_hash(password1)}})

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/activate_two_step/{value}")
async def activate_two_step(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        value: bool
):
    """Updates two_step"""
    await db.users.update_one(
        {"_id": current_user.id},
        {"$set": {"two_step": value, "updated_at": datetime.now()}}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/check_two_step")
async def check_two_step(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
):
    """Retrieves two_step value"""
    result = await db.users.find_one({"_id": current_user.id}, {"two_step": 1})
    two_step = result.get("two_step")
    if two_step is None:
        return {'message': 'two_step is not set'}
    return {"two_step": two_step}


@router.post("/lookup", status_code=status.HTTP_404_NOT_FOUND)
async def username_lookup(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        register_data: UsernameLookupIn
):
    """
    Check if given username is taken ==> status code = 409 or not taken ==> status code 200
    """
    if await db.users.find_one({"username": register_data.username, "role": {"$ne": "admin"}}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=OperationResponse.USERNAME_TAKEN)
    else:
        return Response(status_code=status.HTTP_200_OK, content=OperationResponse.USERNAME_AVAILABLE)


@router.post("/signup_send", status_code=status.HTTP_200_OK)
async def signup_send(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        redis: Redis = Depends(depends.get_redis),
        kavenegarx: KavenegarX = Depends(depends.get_kavenegarx),
        register_data: RegisterDataIn,
):
    """
    checks if there is otp for the given mobile or email in redis and if there is, deletes the otp,
    Sets new otp for mobile or email in redis,
    sends otp via sms or email
    """

    username = register_data.username
    username_type = specify_username_type(username)

    if await redis.ttl(f"signup_{username}") > 30:
        time_left = await redis.ttl(f"signup_{username}")
        return Response(status_code=status.HTTP_200_OK, content=f"{time_left}")

    if username_type == UsernameType.MOBILE:
        if await db.users.find_one({"username": username}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OperationResponse.USERNAME_TAKEN
            )
        token = generate_otp_token()
        await redis.set(f"signup_{username}", token, settings.SMS_OTP_TOKEN_EXPIRE_SECONDS)
        if settings.USE_SMS:
            try:
                await kavenegarx.lookup(
                    receptor=username,
                    token=token,
                    template=settings.KAVENEGAR_REGISTER_TEMPLATE
                )
            except:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Couldn't communicate with Kavenegar to send OTP token"
                )
            return {'success': True, 'message': f"OTP was sent to {username}"}
        return {"message": "USE_SMS is false"}

    elif username_type == UsernameType.EMAIL:
        if await db.users.find_one({"$or": [{"contact_info.email": username}, {"username": username}]}):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=OperationResponse.USERNAME_TAKEN)
        token = generate_otp_token()
        await redis.set(f"signup_{username}", token, settings.EMAIL_OTP_TOKEN_EXPIRE_SECONDS)
        # email sending module
        await send_register_mail([username], token)
        return {'success': True, 'message': f"OTP was sent to {username}"}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=OperationResponse.INVALID_USERNAME)


@router.post("/signup_verify", status_code=status.HTTP_200_OK)
async def signup_verify(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        redis: Redis = Depends(depends.get_redis),
        register_data: UserSignUpIn
):
    """
    verify second step otp and
    if otp is valid return third step otp for sending password and user creation
    """

    username = register_data.username
    otp = register_data.token.get_secret_value()

    redis_otp = await redis.get(f"signup_{username}")
    if not redis_otp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No OTP token requested for this username or token is out-dated!"
        )
    redis_otp = redis_otp.decode()
    if otp != redis_otp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The token is invalid!"
        )
    await redis.delete(f"signup_{username}")

    now = datetime.now()
    user = {
        "username": username,
        "contact_info": {
            f"{'mobile' if specify_username_type(username) == UsernameType.MOBILE else 'email'}": username
        },
        "created_at": now,
        "updated_at": now,
        "status": UserStatus.ACTIVE.value,
        "user_type": UserType.GUEST.value
    }

    if register_data.password1 or specify_username_type(username) == UsernameType.EMAIL:
        check_passwords(
            password_1=register_data.password1.get_secret_value(),
            password_2=register_data.password2.get_secret_value()
        )
        user["password"] = get_password_hash(register_data.password1.get_secret_value())

    result = await db.users.insert_one(user)
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not register user"
        )

    data = {
        "sub": str(result.inserted_id),
        "username": username,
        "scope": [*user.get("role"), "authenticated"] if user.get("role") else ["authenticated"],
        "iat": int(time.time())
    }
    access_token = create_token(
        data=data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    data["grant_type"] = "refresh"
    refresh_token = create_token(
        data=data,
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    try:
        await db.users.update_one(
            {"username": username},
            {"$set": {"last_login": datetime.now()}}
        )
    except Exception as e:
        print(e)
        HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User could not be updated")
    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer", is_new_user=True)


# TODO insecure transport in env is just for local tests, in production must be commented
@router.get('/googleauthurl')
async def google_login():
    """
    Get google auth url
    """
    flow = await google_oauth2flow()
    auth_url, state = flow.authorization_url()
    return {
        # TODO check states be equal on front
        "link": auth_url,
        # state must be same as the state that will be received in /callback
        "state": state
    }


@router.get('/googlecallback')
async def google_callback(
        request: Request,
        db: AsyncIOMotorDatabase = Depends(depends.get_database)
):
    """
    After authenticating to google, google calls this endpoint,
    validates google access token,
    checks if provided email exists in database
    if it exists and has logged in before with Google, returns access token
    if it does not exist makes user with basic roles and permissions, also makes a record of all
    data sent from Google in google_auth collection
    """

    flow = await google_oauth2flow()
    datetime_variable = datetime.now()
    flow.fetch_token(authorization_response=str(request.url))
    credentials = flow.credentials
    request_session = request.session
    # cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=request_session)
    id_info = id_token.verify_oauth2_token(
        credentials.id_token,
        token_request,
        settings.GOOGLE_CLIENT_ID)
    username = id_info.get('email')
    user = await db.users.find_one(
        {"username": username, "social": {"google": True}}
    )
    if user:
        data = {
            "sub": str(user.get("_id")),
            "username": user.get("username"),
            "scope": [*user.get("role"), "authenticated"] if user.get("role") else ["authenticated"],
            "iat": int(time.time())
        }
        access_token = create_token(
            data=data,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        data["grant_type"] = "refresh"
        refresh_token = create_token(
            data=data,
            expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        )
        try:
            await db.users.update_one(
                {"username": username}, {"$set": {"last_login": datetime_variable}})
        except Exception as e:
            print(e)
            HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User count not be updated."
            )
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            is_new_user=False
        )

    else:
        try:
            user_insert_response = await db.users.insert_one(
                {
                    "username": username,
                    "basic_info": {
                        "first_name": id_info.get('given_name'),
                        "last_name": id_info.get('family_name'),
                    },
                    "contact_info": {
                        "email": username,
                    },
                    "role": [
                        Roles.USER
                    ],
                    "created_at": datetime_variable,
                    "updated_at": datetime_variable,
                    "status": UserStatus.ACTIVE,
                    "social": {
                        "google": True
                    },
                    "user_type": UserType.NORMAL
                }
            )
            id_info['user_id'] = user_insert_response.inserted_id
            google_auth_insert_response = await db.google_auth.insert_one(id_info)
            data = {
                "sub": str(user_insert_response.inserted_id),
                "username": username,
                "scope": [Roles.USER, "authenticated"],
                "iat": int(time.time())
            }
            access_token = create_token(
                data=data,
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            data["grant_type"] = "refresh"
            refresh_token = create_token(
                data=data,
                expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
            )
            return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer", is_new_user=True)
        except DuplicateKeyError as e:
            raise HTTPException(status_code=status.HTTP_226_IM_USED, detail="Provided username is taken.") from e
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail='Could not get data from google') from e


@router.get('/linkedinauthurl')
async def get_linkedin_auth_url():
    """
    Get linkedin auth url
    """
    linkedin_client = await return_linkedin_client()

    auth_url = await linkedin_client.get_authorization_url(
        redirect_uri=settings.LINKEDIN_CALLBACK_URL, scope=settings.LINKEDIN_SCOPES)
    return {'url': auth_url}


@router.get('/linkedincallback', )
async def linkedin_login_callback(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        code: str
):
    """
    LinkedIn callback,
    if user with given email exists and account has social: {linkedin: True} then returns jwt
    else creates user and returns jwt
    """
    linkedin_client = await return_linkedin_client()


    small_avatar_link = None
    datetime_variable = datetime.now()

    try:
        access = await linkedin_client.get_access_token(
            code,
            settings.LINKEDIN_CALLBACK_URL
        )
    except GetAccessTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code verifier does not match authorization code. Or authorization code expired."
        ) from e

    token = access['access_token']
    linkedin_id, email = await linkedin_client.get_id_email(token)
    headers = {
        "Authorization": f"Bearer {token}"
    }
    info_url = settings.LINKEDIN_BASIC_INFO_URL
    info_response = requests.get(url=info_url, headers=headers)
    picture_url = settings.LINKEDIN_PICTURE_URL
    picture_response = requests.get(url=picture_url, headers=headers)
    info_data = info_response.json()
    picture_data = picture_response.json()
    username = email

    user = await db.users.find_one(
        {"username": username, "social": {"linkedin": True}})
    if user:
        data = {
            "sub": str(user.get("_id")),
            "username": user.get("username"),
            "scope": [*user.get("role"), "authenticated"] if user.get("role") else ["authenticated"],
            "iat": int(time.time())
        }
        access_token = create_token(
            data=data,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        data["grant_type"] = "refresh"
        refresh_token = create_token(
            data=data,
            expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        )
        try:
            await db.users.update_one(
                {"username": username}, {"$set": {"last_login": datetime_variable}})
        except Exception as e:
            HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User count not be updated. ")
        return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer", is_new_user=False)

    else:
        try:
            small_avatar_link = picture_data.get('profilePicture').get('displayImage~').get('elements')[0] \
                .get('identifiers')[0].get('identifier')
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail='Could not get data from linkedin') from e

        try:
            user_insert_response = await db.users.insert_one(
                {
                    "username": username,
                    "basic_info": {
                        "first_name": info_data.get('localizedFirstName'),
                        "last_name": info_data.get('localizedLastName'),
                        "avatar": small_avatar_link
                    },
                    "contact_info": {
                        "email": username
                    },
                    "role": [
                        Roles.USER
                    ],
                    "created_at": datetime_variable,
                    "updated_at": datetime_variable,
                    "status": UserStatus.ACTIVE,
                    "social": {
                        "linkedin": True
                    },
                    "user_type": UserType.NORMAL
                })
            picture_data['user_id'] = user_insert_response.inserted_id
            linkedin_auth_insert_response = await db.linkedin_auth.insert_one(picture_data)
            data = {
                "sub": str(user_insert_response.inserted_id),
                "username": username,
                "scope": [Roles.USER, "authenticated"],
                "iat": int(time.time())
            }
            access_token = create_token(
                data=data,
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            data["grant_type"] = "refresh"
            refresh_token = create_token(
                data=data,
                expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
            )
            return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer", is_new_user=True)
        except DuplicateKeyError as e:
            raise HTTPException(status_code=status.HTTP_226_IM_USED, detail="Provided username is taken.") from e


@router.get("/refresh", response_model=Token)
async def refresh_access_token(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        authorization: str = Header(None),
) -> Any:
    """
    Get the current user's information, also can be used to test access token.

    Authorization: Required
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Login",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_type, token = authorization.split(" ")
        if token_type.lower() != "bearer":
            raise credentials_exception
        token_data = decode_refresh_token(
            token=token,
            secret_key=settings.SECRET_KEY,
            algorithm=settings.REFRESH_TOKEN_ALGORITHM
        )
        if token_data and token_data.grant_type != "refresh":
            raise credentials_exception
        user = await db.users.find_one({
            "username": token_data.username,
            "status": UserStatus.ACTIVE
        }, {"username": 1, "role": 1, "_id": 1})
        if not user:
            raise credentials_exception
        access_token = create_token(
            data={
                "sub": str(user.get("_id")),
                "username": user.get("username"),
                "scope": [*user.get("role"), "authenticated"]
                if user.get("role") else ["authenticated"],
                "iat": int(time.time())
            },
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            algorithm=settings.ACCESS_TOKEN_ALGORITHM,
            secret_key=settings.SECRET_KEY
        )
        return Token(access_token=access_token, token_type="bearer")
    except ExpiredSignatureError as e:
        raise credentials_exception from e
    except JWTError as e:
        raise credentials_exception from e
