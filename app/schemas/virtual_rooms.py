"""
Module for virtual rooms schemas
"""

from datetime import datetime
from typing import Optional, List

from pydantic import EmailStr, root_validator
from pydantic.fields import Field

from app.config.settings import settings
from app.core.utils import specify_username_type
from app.schemas.base import Model, ObjectId, DateTime
from app.schemas.general import UserType, UsernameType


class VirtualRoomUser(Model):
    """Pydantic schema related to virtual rooms user"""

    id: ObjectId = Field()
    username: str = Field()
    email: Optional[EmailStr] = Field()
    user_type: Optional[UserType] = Field()
    company_name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    website: Optional[str] = Field()

    @root_validator()
    def set_email(cls, values):
        if specify_username_type(
                values.get("username", "") if values.get("username") is not None else ""
        ).value == UsernameType.EMAIL.value:
            values["email"] = values["username"]
        return values


class VirtualRoomCreate(Model):
    """Pydantic schema related to virtual rooms create"""

    maximum_clients: Optional[int] = Field(le=settings.VIRTUAL_ROOM_MAXIMUM_CLIENTS, gt=0)
    starts_at: Optional[DateTime] = Field(default_factory=datetime.now)
    ends_at: Optional[DateTime] = Field(default_factory=datetime.now)
    participants: Optional[List[VirtualRoomUser]] = Field(max_items=settings.VIRTUAL_ROOM_MAXIMUM_CLIENTS - 1)

    @root_validator()
    def validate_date(cls, values):
        if values.get('starts_at') >= values.get('ends_at'):
            raise ValueError("starts_at must be smaller than ends_at")
        return values


class VirtualRoom(Model):
    """Pydantic schema related to virtual rooms"""

    id: Optional[ObjectId] = Field()
    is_active: Optional[bool] = Field(default=False)
    event_id: ObjectId = Field()
    maximum_clients: int = Field(le=settings.VIRTUAL_ROOM_MAXIMUM_CLIENTS, gt=0)
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    created_at: DateTime = Field()
    updated_at: DateTime = Field()
    owner: VirtualRoomUser = Field()
    participants: Optional[List[VirtualRoomUser]] = Field(
        max_items=settings.VIRTUAL_ROOM_MAXIMUM_CLIENTS - 1,
        default=[]
    )


class VirtualRoomDataInEvent(Model):
    """Pydantic schema related to virtual rooms"""

    id: Optional[ObjectId] = Field()
    maximum_clients: Optional[int] = Field(le=settings.VIRTUAL_ROOM_MAXIMUM_CLIENTS, gt=0)
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    owner: Optional[VirtualRoomUser] = Field()
    participants: Optional[List[VirtualRoomUser]] = Field(max_items=settings.VIRTUAL_ROOM_MAXIMUM_CLIENTS - 1)

    @root_validator(skip_on_failure=True)
    def validate_date(cls, values):
        if values.get('starts_at') and values.get('ends_at'):
            if values.get('starts_at') >= values.get('ends_at'):
                raise ValueError("starts_at must be smaller than ends_at")
        return values


class VirtualRoomPartialUpdate(Model):
    """Pydantic schema related to virtual rooms partial update"""

    participants: Optional[List[VirtualRoomUser]] = Field(max_items=settings.VIRTUAL_ROOM_MAXIMUM_CLIENTS - 1)
