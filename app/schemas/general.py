from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.config.settings import settings
from app.schemas.base import DateTime, Model, ObjectId


class UserType(str, Enum):
    """
    Main User Type is absolute value in DB, either Company OR Normal User
    """
    COMPANY = 'company_user'
    NORMAL = 'normal_user'
    GUEST = 'guest'


class Gender(str, Enum):
    """Schema for user gender validation."""

    MALE = 'MALE'
    FEMALE = 'FEMALE'
    OTHER = 'OTHER'


class PersonType(str, Enum):
    """Schema for user type."""

    REAL = "REAL"
    LEGAL = "LEGAL"


class Roles(str, Enum):
    """User Roles"""
    ADMIN = "admin"
    STAFF = "staff"
    USER = "user"


class UserStatus(str, Enum):
    """User Status"""

    ACTIVE = 'active'
    INACTIVE = 'inactive'
    BANNED = 'banned'
    DELETED = 'deleted'


class OperationResponse(str, Enum):
    SUCCESSFUL_UPDATE = 'Object was updated successfully.'
    SUCCESSFUL_CREATE = 'Object was created successfully.'
    UNSUCCESSFUL_CREATE = 'Object was not created successfully.'
    SUCCESSFUL_DELETE = 'Object was deleted successfully.'
    UNSUCCESSFUL_UPDATE = 'Object was not updated successfully.'
    USERNAME_TAKEN = 'Username is taken.'
    INVALID_USERNAME = f'Username is invalid, use {settings.EMAIL_REGEX} for email OR {settings.IRANIAN_MOBILE_REGEX}\
 for iranian mobile number.'
    USERNAME_AVAILABLE = 'Username is available'


class Token(BaseModel):
    """
    Authorization token schema
    """
    access_token: Optional[str]
    refresh_token: Optional[str]
    token_type: str
    is_new_user: Optional[bool] = Field()


class TokenData(BaseModel):
    """
    JWT-stored data schema
    """
    id: str
    username: str
    role: Optional[List[str]]
    grant_type: Optional[str]


class Credentials(BaseModel):
    """
    Basic-Auth credentials schema
    """
    username: str
    password: str


class OTPActions(str, Enum):
    """
    OTP response actions model
    """
    LOGIN = "login"
    REGISTER = "register"
    RECOVER_PASSWORD = "recover_password"


class OTPRequest(BaseModel):
    """
    OPT Request response schema
    """
    number: str = Field()
    action: OTPActions = Field()


class UsernameType(int, Enum):
    """
    Username types used by users to register and login
    """

    MOBILE = 1
    EMAIL = 2
    USERNAME = 3


class NotificationCategory(str, Enum):
    FRIENDSHIP = 'FRIENDSHIP'
    COMMENT = 'COMMENT'
    LIKE = 'LIKE'


class DiscountAmountType(str, Enum):
    AMOUNT = 'AMOUNT'
    PERCENTAGE = 'PERCENTAGE'


class TicketDepartment(str, Enum):
    SUPPORT = 'SUPPORT'
    TECH = 'TECH'
    CONTENT = 'CONTENT'
    FINANCE = 'FINANCE'


class TicketInput(Model):
    """
    Pydantic schema for creating ticket by client
    """

    title: str = Field()
    text: str = Field()
    department: TicketDepartment = Field()


class TicketOutput(Model):
    """
    Pydantic schema for returning ticket
    """

    id: str = Field()
    title: str = Field()
    text: str = Field()
    department: TicketDepartment = Field()

