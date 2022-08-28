"""
Module for meetings schemas
"""

from enum import Enum
from typing import Optional, List

from pydantic import root_validator, EmailStr
from pydantic.fields import Field

from app.core.utils import specify_username_type
from app.schemas.base import Model, ObjectId, DateTime
from app.schemas.events import EventOperatorType
from app.schemas.general import UserType, UsernameType


class MeetingRoles(str, Enum):
    """Schema for meeting roles"""

    moderator = "moderator"
    admin = "admin"
    speaker = "speaker"
    teacher = "teacher"
    room_owner = "room_owner"
    participant = "participant"


class MeetingError(str, Enum):
    """Schema for meeting errors"""

    time = "time"
    property_existence = "property_existence"
    subscription = "subscription"
    user_existence = "user_existence"


class MeetingPermissions(str, Enum):
    """Schema for meeting permissions"""

    chat = "chat"
    video = "video"
    microphone = "microphone"


class MeetingProperty(str, Enum):
    """Schema for meeting properties"""

    sessions = "sessions"
    workshops = "workshops"
    booths = "booths"
    virtual_rooms = "virtual_rooms"


class MeetingClient(Model):
    """Pydantic schema related to meeting client"""

    id: Optional[ObjectId] = Field()
    username: Optional[str] = Field()
    email: Optional[EmailStr] = Field()
    user_type: Optional[UserType] = Field()
    type: Optional[EventOperatorType] = Field()
    company_name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    linkedin: Optional[str] = Field()
    website: Optional[str] = Field()

    @root_validator()
    def set_email(cls, values):
        if specify_username_type(
                values.get("username", "") if values.get("username") is not None else ""
        ).value == UsernameType.EMAIL.value:
            values["email"] = values["username"]
        return values


class MeetingDetail(Model):
    """Pydantic schema related to meeting"""

    uuid: Optional[str] = Field()
    max_participants: Optional[int] = Field()
    event_id: Optional[ObjectId] = Field()
    property_id: Optional[ObjectId] = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()


class Permissions(Model):
    """Pydantic schema related to meeting"""

    access: bool = Field(default=False)
    meeting: MeetingDetail = Field(default_factory=MeetingDetail().dict)
    role: Optional[MeetingRoles] = Field()
    permissions: Optional[List[MeetingPermissions]] = Field(default=[])
    client: Optional[MeetingClient] = Field(default_factory=MeetingClient().dict)
    error: Optional[MeetingError] = Field()
