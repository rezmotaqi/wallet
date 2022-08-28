"""
API Dependencies
"""

from typing import Generator, List, Any

import httpx
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config.settings import settings
from app.core.authentication import verify_password, decode_access_token, check_user_status
from app.handlers.kavenegarx import KavenegarX
from app.handlers.mongo import MongoConnection
from app.handlers.rate_limit import limiter
from app.handlers.redis import RedisConnection
from app.schemas.general import Credentials
from app.schemas.users import User
from app.schemas.users import oauth2_schema


async def get_database() -> AsyncIOMotorDatabase:
    """
    Returns mongodb database object.
    """
    conn = await MongoConnection()
    return await conn.get_database()


async def get_redis() -> Generator:
    """
    Returns redis client object.
    """
    conn = await RedisConnection()
    return conn.get_client()


async def get_http_client() -> Generator:
    """
    Returns httpx async client object.
    """
    async with httpx.AsyncClient() as client:
        yield client


def get_kavenegarx() -> Generator:
    """
    Returns KavenegarX client object.
    """

    if settings.USE_SMS is not False:
        if not getattr(settings, "KAVENEGAR_API_KEY", None):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OTP service is not available"
            )
        yield KavenegarX(api_key=settings.KAVENEGAR_API_KEY)
    else:
        yield


async def basic_authenticate(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncIOMotorDatabase = Depends(get_database),
) -> User:
    """
    Authorize using basic credentials (username and password) and returns user object.
    """
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    credentials = Credentials(username=form_data.username.lower(), password=form_data.password)
    user = await db.users.find_one(
        {
            "username": credentials.username
        },
        {'_id': 1, 'username': 1, 'role': 1, 'two_step': 1, 'password': 1, 'status': 1}
    )
    if not (user and verify_password(credentials.password, user.get('password'))):
        raise credential_exception

    check_user_status(user)

    return User.parse_obj({**user, "id": user.get("_id")})


def get_current_user(
        token: str = Depends(oauth2_schema)
) -> Any:
    """Return current user based on http connection/request object."""
    token_data = decode_access_token(token=token)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Login",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if (token_data.username or token_data.id) is None:
        raise credentials_exception
    return User.parse_obj({**token_data.dict()})


def get_current_user_or_anonymous_user(
        request: Request
) -> Any:
    """Return current user based on http connection/request object."""
    token = request.headers.get("Authorization")
    if token:
        token = token.split(" ")[1]
        token_data = decode_access_token(token=token)
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login",
            headers={"WWW-Authenticate": "Bearer"},
        )
        if (token_data.username or token_data.id) is None:
            raise credentials_exception
        return User.parse_obj({**token_data.dict()})
    return


@limiter.limit("1/3seconds")
def rate_limit_1_3sec(request: Request):
    return None


def permissions(
        permissions_list: List[str],
) -> Any:
    """Create permission checker dependency with the give permission list."""

    async def user_permission_checker(user: User = Depends(get_current_user)) -> User:
        """
        permission checker dependency
        """

        if user.role and "admin" in user.role:
            pass
        elif "authenticated" in permissions_list and "authenticated" not in user.role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login",
            )
        elif not set(permissions_list).issubset(set(user.role)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this endpoint",
            )
        return user

    return user_permission_checker
