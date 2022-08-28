"""
Authentication core modules and utilities.
"""

import gzip
import secrets
from datetime import datetime, timedelta
from typing import Optional, NoReturn

from fastapi import HTTPException, status
from google_auth_oauthlib.flow import Flow
from httpx_oauth.clients.linkedin import LinkedInOAuth2
from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext
from starlette.datastructures import Secret

from app.config.settings import settings
from app.schemas.general import TokenData, UserStatus


def create_token(
        data: dict,
        expires_delta: Optional[timedelta] = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        algorithm: str = settings.ACCESS_TOKEN_ALGORITHM,
        secret_key: Secret = settings.SECRET_KEY
) -> str:
    """Generate a jwt based on data and expires delta time."""
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + expires_delta})
    encoded_jwt = jwt.encode(to_encode, str(secret_key), algorithm=algorithm)
    return encoded_jwt


def decode_access_token(
        token: str,
        secret_key: Secret = settings.SECRET_KEY,
        algorithm: str = settings.ACCESS_TOKEN_ALGORITHM
) -> TokenData:
    """Decode generated token."""
    login_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Login",
        headers={"WWW-Authenticate": "Bearer"},
    )
    refresh_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, str(secret_key), algorithms=[algorithm])
    except ExpiredSignatureError:
        raise refresh_credentials_exception
    except JWTError:
        raise login_credentials_exception  # pylint: disable=raise-missing-from
    if payload.get("exp") < int(datetime.utcnow().timestamp()):
        raise login_credentials_exception  # pylint: disable=raise-missing-from
    return TokenData(
        id=payload.get("sub"),
        username=payload.get("username"),
        role=payload.get("scope")
    )


def decode_refresh_token(
        token: str,
        secret_key: Secret = settings.SECRET_KEY,
        algorithm: str = settings.REFRESH_TOKEN_ALGORITHM
) -> TokenData:
    """Decode generated token."""
    login_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Login",
        headers={"WWW-Authenticate": "Bearer"},
    )
    refresh_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Login",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, str(secret_key), algorithms=[algorithm])
    except ExpiredSignatureError:
        raise refresh_credentials_exception
    except JWTError:
        raise login_credentials_exception  # pylint: disable=raise-missing-from
    if payload.get("exp") < int(datetime.utcnow().timestamp()):
        raise login_credentials_exception  # pylint: disable=raise-missing-from
    return TokenData(
        id=payload.get("sub"),
        username=payload.get("username"),
        role=payload.get("scope"),
        grant_type=payload.get("grant_type")
    )


pwd_context = CryptContext(schemes=settings.PASSWD_SCHEMES, deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify plain password is match with hashed password.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Generate a salted hashed password from plain password based on context.
    """
    return pwd_context.hash(password)


def generate_otp_token():
    """
    Generates a 5-digits numeral token, that used for OTP
    """
    return str(int(secrets.token_hex(2), 16)).zfill(6)


def generate_complicated_otp_token():
    return str((secrets.token_hex()))


def common_password_validator(password) -> NoReturn:
    password_list_path = settings.BASE_DIR + \
                         "/app/resources/common-passwords.txt.gz"
    try:
        with gzip.open(password_list_path, 'rt', encoding='utf-8') as f:
            common_passwords = {x.strip() for x in f}
    except OSError:
        with open(password_list_path) as f:
            common_passwords = {x.strip() for x in f}
    if password.lower().strip() in common_passwords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your password can’t be a commonly used password."
        )


async def google_oauth2flow():
    flow = Flow.from_client_secrets_file(client_secrets_file=settings.GOOGLE_CLIENT_SECRETS_JSON,
                                         scopes=settings.GOOGLE_SCOPES,
                                         redirect_uri=settings.GOOGLE_CALLBACK_URL)
    return flow


async def return_linkedin_client():
    linkedin_client = LinkedInOAuth2(settings.LINKEDIN_CLIENT_ID.strip('"'), settings.LINKEDIN_CLIENT_SECRET.strip('"'))
    return linkedin_client


def check_user_status(user: dict, user_status: Optional[str] = UserStatus.ACTIVE.value) -> NoReturn:
    if user.get("status") != user_status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this endpoint"
        )
