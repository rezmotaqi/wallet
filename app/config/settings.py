"""Configuration core modules and utilities."""
import os.path
import pathlib
import secrets
from pathlib import Path
from typing import Optional, List, Tuple, Dict

from pydantic import BaseSettings
from pydantic.main import BaseConfig


class Settings(BaseSettings):
    """Base settings model for usersapi."""

    PROJECT_NAME: str = "heisenberg_core"
    ROOT_USER: str = "root"
    ROOT_PASSWORD: str = "12345678"

    SMS_OTP_TOKEN_EXPIRE_SECONDS: int = 120
    EMAIL_OTP_TOKEN_EXPIRE_SECONDS: int = 7200
    # used for setting password_otp KEY in redis for third step user signup and the
    # key will be like username_PASSWORD_OTP_KEY_NAME
    PASSWORD_OTP_KEY_NAME = '_p'
    PASSWORD_RECOVER_OTP_KEY_NAME = 'rp'

    API_PATH: str = "/api"
    ROOT_PATH: str = "/api"

    BASE_DIR: str = str(Path(__file__).resolve().parent.parent.parent)
    MEDIA_DIR: str = "/media/"
    ALLOWED_IMAGE_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/svg+xml",
        "image/webp"
    ]

    ALLOWED_FILE_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/xml",
        "text/xml",
        "application/atom+xml",
        "text/xml",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]

    ALLOWED_VIDEO_TYPES: List[str] = ["video/mkv", "video/avi", "video/mp4", "video/x-matroska"]

    # TODO what is the right size of upload for video_post and article ??
    ARTICLE_VIDEO_MAX_LENGTH: int = 5000000000
    VIDEO_POST_MAX_LENGTH: int = 20000000

    ORIGINAL_IMAGE: bool = True
    IMAGE_THUMBNAIL_SMALL: Dict[str, Tuple[int, int]] = {"small": (64, 64)}
    IMAGE_THUMBNAIL_MEDIUM: Dict[str, Tuple[int, int]] = {"medium": (512, 512)}
    IMAGE_THUMBNAIL_LARGE: Dict[str, Tuple[int, int]] = {"large": (1024, 1024)}

    PASSWD_SCHEMES: List[str] = ["bcrypt"]
    SECRET_KEY: str = secrets.token_hex()
    DEBUG: bool = True

    PASSWORD_REGEX: str = r'^(?=.*[a-z])(?=.*\d).{8,30}$'

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 86400
    ACCESS_TOKEN_ALGORITHM: str = "HS256"
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 20160
    REFRESH_TOKEN_ALGORITHM: str = "HS256"

    EMAIL_REGEX: str = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    IRANIAN_MOBILE_REGEX: str = '^98[0-9]{10}$'

    MONGO_HOSTNAME: str = None
    MONGO_PORT: str = "27017"
    MONGO_USERNAME: Optional[str] = None
    MONGO_PASSWORD: Optional[str] = None
    MONGO_DATABASE: str = "heisenberg"

    REDIS_PORT: str = "6379"
    REDIS_HOSTNAME: str = "redis-heisenberg"
    REDIS_USERNAME: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DATABASE: Optional[str] = None

    KAVENEGAR_API_KEY: Optional[str] = None
    KAVENEGAR_REGISTER_TEMPLATE: str = "LoginNetAll"
    KAVENEGAR_LOGIN_TEMPLATE: str = "LoginNetAll"
    KAVENEGAR_RECOVER_PASSWORD_TEMPLATE: str = "LoginNetAll"
    KAVENEGAR_VERIFY: str = "LoginNetAll"
    KAVENEGAR_SEND_INVOICE: str = "LoginNetAll"

    # Tax & VAT
    # TAX: float = 1.09
    TAX_PERCENTAGE: float = 0.03
    VAT_PERCENTAGE: float = 0.06
    OTHER_TAX_PERCENTAGE: float = 0

    # Rate Limit
    RATE_LIMIT_TIMES: int = 1
    RATE_LIMIT_SECONDS: int = 2

    # Device info
    DEVICE_ID: Optional[int] = None
    DEVICE_KIND: Optional[str] = None
    DEVICE_SERIAL: Optional[int] = None

    # Seller info
    SELLER_NAME: Optional[str] = None
    SELLER_CITY: Optional[str] = None
    SELLER_PHONE: Optional[str] = None
    SELLER_ADDRESS: Optional[str] = None
    SELLER_PROVINCE: Optional[str] = None
    SELLER_POSTAL_CODE: Optional[str] = None
    SELLER_NATIONAL_CODE: Optional[str] = None
    SELLER_ECONOMIC_CODE: Optional[str] = None
    SELLER_REGISTER_NUMBER: Optional[str] = None

    RSA_PUBK: Optional[str] = None
    RSA_PRVK: Optional[str] = None

    USE_SMS: Optional[bool] = None
    MAILGUN_DOMAIN: Optional[str] = "https://api.eu.mailgun.net/v3/netall.live/messages"
    MAILGUN_KEY: Optional[str] = None

    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SENDER_EMAIL: Optional[str] = "register@netall.live"
    SMTP_SERVER_PASSWORD: Optional[str] = None

    # google social log in
    COOKIE_AUTHORIZATION_NAME: Optional[str] = None
    COOKIE_DOMAIN: Optional[str] = None
    PROTOCOL: Optional[str] = None
    FULL_HOST_NAME: Optional[str] = None
    PORT_NUMBER: Optional[str] = 8000
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_CLIENT_SECRETS_JSON: Optional[str] = os.path.join(
        pathlib.Path(__file__).parent.parent.parent,
        'client_secret',
        'client_secret.json'
    )
    GOOGLE_CALLBACK_URL: Optional[str] = None
    GOOGLE_SCOPES: Optional[list] = None
    # linked in social log in

    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_BASIC_INFO_URL: Optional[str] = None
    LINKEDIN_PICTURE_URL: Optional[str] = None
    LINKEDIN_CALLBACK_URL: Optional[str] = None
    LINKEDIN_SCOPES: Optional[list] = None

    API_LOCATION: Optional[str] = f"{PROTOCOL}{FULL_HOST_NAME}:{PORT_NUMBER}"
    SWAP_TOKEN_ENDPOINT: Optional[str] = "/swap_token"
    SUCCESS_ROUTE: Optional[str] = ""
    ERROR_ROUTE: Optional[str] = ""

    FRIEND_REQUEST_AGAIN_AFTER_DAYS: Optional[int] = 30

    TIMEZONE: Optional[str] = None

    # Events
    VIRTUAL_ROOM_MAXIMUM_CLIENTS: Optional[int] = 4

    class Config(BaseConfig):
        """config class for env setting."""

        fields = {
            'RSA_PUBK': {
                'env': 'RSA_PUBK'
            },
            'RSA_PRVK': {
                'env': 'RSA_PRVK'
            },
            'DEVICE_ID': {
                'env': 'DEVICE_ID'
            },
            'DEVICE_KIND': {
                'env': 'DEVICE_KIND'
            },
            'DEVICE_SERIAL': {
                'env': 'DEVICE_SERIAL'
            },
            'SELLER_NAME': {
                'env': 'SELLER_NAME'
            },
            'SELLER_CITY': {
                'env': 'SELLER_CITY'
            },
            'SELLER_PHONE': {
                'env': 'SELLER_PHONE'
            },
            'SELLER_ADDRESS': {
                'env': 'SELLER_ADDRESS'
            },
            'SELLER_PROVINCE': {
                'env': 'SELLER_PROVINCE'
            },
            'SELLER_POSTAL_CODE': {
                'env': 'SELLER_POSTAL_CODE'
            },
            'SELLER_NATIONAL_CODE': {
                'env': 'SELLER_NATIONAL_CODE'
            },
            'SELLER_ECONOMIC_CODE': {
                'env': 'SELLER_ECONOMIC_CODE'
            },
            'SELLER_REGISTER_NUMBER': {
                'env': 'SELLER_REGISTER_NUMBER'
            },
            'ROOT_USER': {
                'env': 'ROOT_USER'
            },
            'ROOT_PASSWORD': {
                'env': 'ROOT_PASSWORD'
            },
            'SECRET_KEY': {
                'env': 'SECRET_KEY'
            },
            'MONGO_HOSTNAME': {
                'env': 'MONGO_HOSTNAME'
            },
            'MONGO_PORT': {
                'env': 'MONGO_PORT'
            },
            'MONGO_USERNAME': {
                'env': 'MONGO_USERNAME'
            },
            'MONGO_PASSWORD': {
                'env': 'MONGO_PASSWORD'
            },
            'MONGO_DATABASE': {
                'env': 'MONGO_DATABASE'
            },
            'REDIS_HOSTNAME': {
                'env': 'REDIS_HOSTNAME'
            },
            'REDIS_PORT': {
                'env': 'REDIS_PORT'
            },
            'REDIS_USERNAME': {
                'env': 'REDIS_USERNAME'
            },
            'REDIS_PASSWORD': {
                'env': 'REDIS_PASSWORD'
            },
            'REDIS_DATABASE': {
                'env': 'REDIS_DATABASE'
            },
            'KAVENEGAR_API_KEY': {
                'env': 'KAVENEGAR_API_KEY'
            },
            'SMTP_SERVER': {
                'env': 'SMTP_SERVER'
            },
            'SMTP_PORT': {
                'env': 'SMTP_PORT'
            },
            'SMTP_SERVER_PASSWORD': {
                'env': 'SMTP_SERVER_PASSWORD'
            },
            'OAUTHLIB_INSECURE_TRANSPORT': {
                'env': 'OAUTHLIB_INSECURE_TRANSPORT'
            },
            'LINKEDIN_CLIENT_ID': {
                'env': 'LINKEDIN_CLIENT_ID'
            },
            'LINKEDIN_CLIENT_SECRET': {
                'env': 'LINKEDIN_CLIENT_SECRET'
            },
            'LINKEDIN_BASIC_INFO_URL': {
                'env': 'LINKEDIN_BASIC_INFO_URL'
            },
            'LINKEDIN_PICTURE_URL': {
                'env': 'LINKEDIN_PICTURE_URL'
            },
            'LINKEDIN_CALLBACK_URL': {
                'env': 'LINKEDIN_CALLBACK_URL'
            },
            'LINKEDIN_SCOPES': {
                'env': 'LINKEDIN_SCOPES'
            },
            'GOOGLE_COOKIE_AUTHORIZATION_NAME': {
                'env': 'GOOGLE_COOKIE_AUTHORIZATION_NAME'
            },
            'GOOGLE_PROTOCOL': {
                'env': 'GOOGLE_PROTOCOL'
            },
            'GOOGLE_FULL_HOST_NAME': {
                'env': 'GOOGLE_FULL_HOST_NAME'
            },
            'GOOGLE_PORT_NUMBER': {
                'env': 'GOOGLE_PORT_NUMBER'
            },
            'GOOGLE_CLIENT_ID': {
                'env': 'GOOGLE_CLIENT_ID'
            },
            'GOOGLE_CLIENT_SECRET': {
                'env': 'GOOGLE_CLIENT_SECRET'
            },
            'USE_SMS': {
                'env': 'USE_SMS'
            },
            'EMAIL_REGEX': {
                'env': 'EMAIL_REGEX'
            },
            'IRANIAN_MOBILE_REGEX': {
                'env': 'IRANIAN_MOBILE_REGEX'
            },
            'PASSWORD_REGEX': {
                'env': 'PASSWORD_REGEX'
            },
            'ACCESS_TOKEN_EXPIRE_MINUTES': {
                'env': 'ACCESS_TOKEN_EXPIRE_MINUTES'
            },
            'SMS_OTP_TOKEN_EXPIRE_SECONDS': {
                'env': 'SMS_OTP_TOKEN_EXPIRE_SECONDS'
            },
            'EMAIL_OTP_TOKEN_EXPIRE_SECONDS': {
                'env': 'EMAIL_OTP_TOKEN_EXPIRE_SECONDS'
            },
            'ACCESS_TOKEN_ALGORITHM': {
                'env': 'ACCESS_TOKEN_ALGORITHM'
            },
            'PASSWORD_OTP_KEY_NAME': {
                'env': 'PASSWORD_OTP_KEY_NAME'
            },
            'PASSWORD_RECOVER_OTP_KEY_NAME': {
                'env': 'PASSWORD_RECOVER_OTP_KEY_NAME'
            },
            'MAILGUN_KEY': {
                'env': 'MAILGUN_KEY'
            },
            'TIMEZONE': {
                'env': 'TIMEZONE'
            }

        }

        env_file = ".env"


settings = Settings()
