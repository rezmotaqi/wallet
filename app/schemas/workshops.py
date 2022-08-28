"""
Module for virtual rooms schemas
"""

from datetime import datetime
from typing import Optional, List

from pydantic import root_validator
from pydantic.fields import Field

from app.schemas.base import Model, ObjectId, DateTime
from app.schemas.general import DiscountAmountType, UserType, UserSchedule


class WorkShopFile(Model):
    path: str = Field()
    size: str = Field()
    description: Optional[str] = Field()
    name: Optional[str] = Field()


class WorkshopFileList(Model):
    """
    Pydantic schema for returning list of workshop files
    """
    files: List[WorkShopFile] = Field()
    count: int = Field()


class WorkShopUser(Model):
    id: ObjectId
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    username: Optional[str] = Field()
    headline: Optional[str] = Field()


class WorkshopParticipantList(Model):
    """
    Pydantic schema for returning list of workshop participants
    """
    participants: List[WorkShopUser] = Field()
    count: int = Field()


class WorkshopScheduleList(Model):
    """
    Pydantic schema for returning list of user schedules in workshop execution page
    """
    schedules: List[UserSchedule] = Field()
    count: int = Field()


class WorkshopExecutionData(Model):
    """
    Pydantic schema for returning workshop data in execution page
    """

    resource: WorkshopFileList = Field()
    participant: WorkshopParticipantList = Field()
    schedule: WorkshopScheduleList = Field()


class Teacher(Model):
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


class WorkshopDiscountOutput(Model):
    """Pydantic schema related to workshop discount"""

    name: Optional[str] = Field(default=None)
    amount: Optional[int] = Field(default=None)
    amount_type: Optional[DiscountAmountType] = Field(default=None)
    starts_at: Optional[DateTime] = Field(default=None)
    ends_at: Optional[DateTime] = Field(default=None)
    use_count: Optional[bool] = Field(default=None)
    count: Optional[int] = Field(default=None)


class WorkshopDiscountInput(WorkshopDiscountOutput):
    """Pydantic schema related to workshop discount"""

    name: str = Field()
    amount: int = Field()
    amount_type: DiscountAmountType = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    use_count: bool = Field()
    count: Optional[int] = Field()

    @root_validator()
    def validate_usage_limit(cls, values):
        if values.get('use_count') and values.get('count') is None:
            raise ValueError("Count must be set while use_count is true.")
        return values


class WorkshopFinancialSettingsInput(Model):
    """Pydantic schema for setting workshop financial data"""

    is_free: bool = Field()
    price: int = Field()
    discount: Optional[WorkshopDiscountInput] = Field()

    @root_validator()
    def validate_price(cls, values):
        if not values.get('is_free'):
            if not values.get('price') > 0:
                raise ValueError("Can not have a property that is not free but its price is not greater than 0.")
        else:
            if not values.get('price') == 0:
                raise ValueError("Can not have a property that is free but its price is not 0.")

        return values


class WorkshopFinancialSettingsOutput(Model):
    """Pydantic schema for returning workshop financial data"""

    is_free: Optional[bool] = Field(default=None)
    price: Optional[int] = Field(default=None)
    discount: Optional[WorkshopDiscountOutput] = Field(default_factory=WorkshopDiscountOutput().dict)


class WorkshopCreate(Model):
    name: str = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    operators: Optional[List[Teacher]] = Field(default=[])
    cover: Optional[str] = Field()
    certificate: bool = Field(default=False)
    files: Optional[List[WorkShopFile]] = Field(default=[])
    description: Optional[str] = Field()

    @root_validator()
    def validate_date(cls, values):
        if values.get('starts_at') >= values.get('ends_at'):
            raise ValueError("starts_at must be smaller than ends_at")
        return values


class WorkshopUpdate(Model):
    name: str = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    operators: Optional[List[Teacher]] = Field()
    cover: Optional[str] = Field()
    certificate: Optional[bool] = Field()
    files: Optional[List[WorkShopFile]] = Field()
    description: Optional[str] = Field()

    @root_validator()
    def validate_date(cls, values):
        if values.get('starts_at') >= values.get('ends_at'):
            raise ValueError("starts_at must be smaller than ends_at")
        return values


class WorkshopPartialUpdate(WorkshopUpdate):
    name: Optional[str] = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    operators: Optional[List[Teacher]] = Field()
    cover: Optional[str] = Field()
    certificate: Optional[bool] = Field()
    files: Optional[List[WorkShopFile]] = Field()
    description: Optional[str] = Field()

    @root_validator()
    def validate_date(cls, values):
        if values.get('starts_at') and values.get('ends_at'):
            if values.get('starts_at') >= values.get('ends_at'):
                raise ValueError("starts_at must be smaller than ends_at")
        return values


class WorkshopOut(Model):
    """
    Pydantic schema for returning workshop data
    """
    id: ObjectId = Field()
    event_id: Optional[ObjectId] = Field()
    owner_id: Optional[ObjectId] = Field()
    created_at: Optional[DateTime] = Field()
    updated_at: Optional[DateTime] = Field()
    name: str = Field()
    starts_at: DateTime = Field(default_factory=datetime.now)
    ends_at: DateTime = Field(default_factory=datetime.now)
    operators: Optional[List[Teacher]] = Field()
    cover: Optional[str] = Field()
    certificate: Optional[bool] = Field()
    files: Optional[List[WorkShopFile]] = Field(default=[])
    description: Optional[str] = Field()
    financial_settings: Optional[WorkshopFinancialSettingsOutput] = Field(
        default_factory=WorkshopFinancialSettingsOutput().dict
    )
    participant_count: Optional[int] = Field(default=0)
    remaining_hours: Optional[int] = Field()
    is_bought: Optional[bool] = Field()


class WorkshopListOut(Model):
    """
    Pydantic schema for returning workshops in list
    """
    workshops: List[WorkshopOut] = Field()
    count: int = Field()
    remaining_hours: Optional[int] = Field()


class WorkshopListClientOut(Model):
    """
    Schema for returning list of workshops in workshop page for client user
    """
    workshops: List[WorkshopOut] = Field()
    count: int = Field()


class WorkshopDataInEvent(Model):
    id: Optional[ObjectId] = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    operators: Optional[List[Teacher]] = Field()
    name: str = Field()
    cover: Optional[str] = Field()
    description: Optional[str] = Field()
    financial_settings: Optional[WorkshopFinancialSettingsInput] = Field()
    participant_count: Optional[int] = Field()

    @root_validator()
    def validate_date(cls, values):
        if values.get('starts_at') and values.get('ends_at'):
            if values.get('starts_at') >= values.get('ends_at'):
                raise ValueError("starts_at must be smaller than ends_at")
        return values


class WorkshopFinancialSettingPreviewOutput(Model):
    """
    Pydantic schema for returning workshop financial data in event preview page
    """
    is_free: bool = Field(default=True)
    price: int = Field(default=0)
    discount: Optional[WorkshopDiscountOutput] = Field(default_factory=WorkshopDiscountOutput().dict)


class WorkshopDataInEventPreviewOut(Model):
    id: Optional[ObjectId] = Field()
    name: Optional[str] = Field(default=None)
    cover: Optional[str] = Field(default=None)
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    description: Optional[str] = Field()
    operators: Optional[List[Teacher]] = Field()
    financial_settings: Optional[WorkshopFinancialSettingPreviewOutput] = Field()

