"""
Module for virtual rooms schemas
"""

from enum import Enum
from typing import Optional, List

from pydantic import root_validator, EmailStr
from pydantic.fields import Field

from app.schemas.base import Model, DateTime, IranianMobilePhoneNumber, ObjectId


class BoothRequestStatus(str, Enum):
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    REJECTED = 'REJECTED'


class BoothRequestAction(str, Enum):
    ACCEPT = 'ACCEPT'
    REJECT = 'REJECT'


class BoothStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'
    SUSPENDED = 'SUSPENDED'


class BoothFile(Model):
    path: str = Field()
    size: str = Field()
    description: Optional[str] = Field()
    name: Optional[str] = Field()


class Exhibitor(Model):
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    company_name: Optional[str] = Field()
    email: EmailStr = Field()
    phone: IranianMobilePhoneNumber = Field()
    headline: str = Field()


class BoothPartialUpdate(Model):
    name: Optional[str] = Field()
    cover: Optional[str] = Field()
    files: Optional[List[BoothFile]] = Field()
    description: Optional[str] = Field()


class BoothOutput(Model):
    """
    Pydantic schema for returning booth data to exhibitor in dashboard
    """
    id: ObjectId = Field()
    name: Optional[str] = Field()
    cover: Optional[str] = Field()
    files: Optional[List[BoothFile]] = Field()
    description: Optional[str] = Field()


class BoothRequestInput(Model):
    """
    Pydantic schema for requesting booth
    """
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    company_name: Optional[str] = Field()
    email: EmailStr = Field()
    phone: Optional[IranianMobilePhoneNumber] = Field()
    headline: str = Field()

    @root_validator()
    def validate_names(cls, values):
        """Validate at least one of first_name and last_name or company_name exists"""
        if not (values.get('first_name') and values.get('last_name')) and not values.get('company_name'):
            raise ValueError("Provide either first_name, last_name or company_name")
        return values


class BoothRequestOutput(Model):
    """
    Pydantic schema for returning booth request
    """
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    company_name: Optional[str] = Field()
    email: EmailStr = Field()
    phone: IranianMobilePhoneNumber = Field()
    headline: str = Field()
    created_at: DateTime = Field()
    status: BoothRequestStatus = Field()
    id: str = Field()


class BoothRequestListOutput(Model):
    """
    Pydantic schema for returning list of booth requests
    """

    booth_requests: List[BoothRequestOutput] = Field(default=[])
    count: int = Field(default=0)
