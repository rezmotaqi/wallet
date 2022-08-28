"""
Module for sessions schemas
"""

from datetime import datetime
from typing import Optional, List

from pydantic import root_validator
from pydantic.fields import Field

from app.schemas.base import Model, ObjectId, DateTime
from app.schemas.general import DiscountAmountType, UserType


class StageSpeaker(Model):
    """Pydantic schema related to session speaker"""

    id: ObjectId = Field()
    username: Optional[str] = Field()
    user_type: Optional[UserType] = Field()
    company_name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    linkedin: Optional[str] = Field()
    website: Optional[str] = Field()


class SessionDiscount(Model):
    """Pydantic schema related to session discount"""

    name: str = Field(default=None)
    amount: int = Field(default=None)
    amount_type: DiscountAmountType = Field(default=None)
    starts_at: DateTime = Field(default=None)
    ends_at: DateTime = Field(default=None)
    use_count: bool = Field(default=None)
    count: Optional[int] = Field(default=None)

    @root_validator()
    def validate_usage_limit(cls, values):
        if values.get('use_count') and values.get('count') is None:
            raise ValueError("Count must be set while use_count is true.")
        return values


class SessionSettingInput(Model):
    """Pydantic schema related to session settings"""

    is_free: bool = Field()
    price: int = Field()
    discount: Optional[SessionDiscount] = Field()

    @root_validator()
    def validate_price(cls, values):
        if not values.get('is_free'):
            if not values.get('price') > 0:
                raise ValueError("Can not have a property that is not free but its price is not greater than 0.")
        else:
            if not values.get('price') == 0:
                raise ValueError("Can not have a property that is free but its price is not 0.")
        return values


class SessionFinancialSettingsOutput(Model):
    """Pydantic schema related to session settings"""

    is_free: bool = Field(default=True)
    price: int = Field(default=0)
    discount: Optional[SessionDiscount] = Field(default_factory=SessionDiscount().dict)
    updated_at: DateTime = Field(default_factory=datetime.now)


class SessionCreate(Model):
    """Pydantic schema related to session create"""

    name: str = Field()
    starts_at: DateTime = Field(default_factory=datetime.now)
    ends_at: DateTime = Field(default_factory=datetime.now)
    speakers: Optional[List[StageSpeaker]] = Field()

    @root_validator()
    def validate_date(cls, values):
        if values.get('starts_at') >= values.get('ends_at'):
            raise ValueError("starts_at must be smaller than ends_at")
        return values


class Session(Model):
    """Pydantic schema related to session"""

    id: Optional[ObjectId] = Field()
    name: str = Field()
    event_id: Optional[ObjectId] = Field()
    owner_id: Optional[ObjectId] = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    created_at: Optional[DateTime] = Field()
    updated_at: Optional[DateTime] = Field()
    speakers: Optional[List[StageSpeaker]] = Field()
    remaining_hours: Optional[int] = Field()


class SessionDataInEvent(Model):
    """Pydantic schema related to session"""

    id: Optional[ObjectId] = Field()
    name: str = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    speakers: Optional[List[StageSpeaker]] = Field()

    @root_validator(skip_on_failure=True)
    def validate_date(cls, values):
        if values.get('starts_at') and values.get('ends_at'):
            if values.get('starts_at') >= values.get('ends_at'):
                raise ValueError("starts_at must be smaller than ends_at")
        return values


class SessionCostCalculation(Model):
    """Pydantic schema related to session cost calculation"""

    cost: Optional[int] = Field(default=0)
    price: Optional[int] = Field(default=0)
    applied_discount: Optional[bool] = Field(default=False)
    increase_usage_count: Optional[bool] = Field(default=False)


class SessionUpdate(SessionCreate):
    """Pydantic schema related to session update"""

    name: str = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    speakers: Optional[List[StageSpeaker]] = Field()

    @root_validator()
    def validate_date(cls, values):
        if values.get('starts_at') >= values.get('ends_at'):
            raise ValueError("starts_at must be smaller than ends_at")
        return values


class SessionPartialUpdate(SessionUpdate):
    """Pydantic schema related to session partial update"""

    name: Optional[str] = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()

    @root_validator()
    def validate_date(cls, values):
        if values.get('starts_at') and values.get('ends_at'):
            if values.get('starts_at') >= values.get('ends_at'):
                raise ValueError("starts_at must be smaller than ends_at")
        return values
