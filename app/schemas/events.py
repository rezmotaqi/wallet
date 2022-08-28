"""
Module for events schemas
"""

from enum import Enum
from typing import Optional, List, Dict

from pydantic import root_validator, EmailStr
from pydantic.fields import Field

from app.core.utils import specify_username_type
from app.schemas.base import Model, ObjectId, DateTime
from app.schemas.general import DiscountAmountType, UserType, EventOperatorType, UsernameType
from app.schemas.sessions import SessionFinancialSettingsOutput, SessionDataInEvent, SessionCostCalculation
from app.schemas.workshops import WorkshopFinancialSettingsOutput, WorkshopDataInEventPreviewOut, WorkshopOut


class EventPrivacy(str, Enum):
    PRIVATE = 'PRIVATE'
    PUBLIC = 'PUBLIC'


class DiscountType(str, Enum):
    CODE = 'CODE'
    CAMPAIGN = 'CAMPAIGN'
    SESSION = 'SESSION'
    WORKSHOP = 'WORKSHOP'


class InvoiceType(str, Enum):
    EVENT_CREATOR = 'EVENT_CREATOR'
    EVENT_PARTICIPANT = 'EVENT_PARTICIPANT'
    BOOTH_EXHIBITOR = 'BOOTH_EXHIBITOR'


class EventsSort(str, Enum):
    CREATED_AT = '-created_at'
    PARTICIPANTS_COUNT = '-participants_count'


class EventCategoriesCreate(Model):
    """
    Schema for creating event category
    """

    text: str = Field()


class EventCategoryOut(Model):
    """
    Schema for returning category in list
    """

    text: str = Field()


class EventCategoryListOut(Model):
    """
    Schema for returning list of categories
    """

    categories: List[EventCategoryOut] = Field()
    count: int = Field()


class EventPropertyCostDetailIn(Model):
    """
    Pydantic schema related to session and workshop cost and limit details
    """

    max_participants: int = Field(default=None)
    hours: int = Field(default=None)
    active: bool = Field(default=False)

    @root_validator(allow_reuse=True)
    def validate_max_participants(cls, values):
        if values.get('active') and values.get('max_participants') < 1:
            raise ValueError("Max participants must be greater than 0 when property is active.")
        if values.get('active') and values.get('hours') < 1:
            raise ValueError("Hours must be greater than 0 when property is active.")

        # TODO add validation to accept inactive property (active=false)
        # if not values.get('active'):
        #     raise ValueError("Property active field must be true in order to set data.")

        return values


class EventSessionCostDetailIn(EventPropertyCostDetailIn):
    """
    Pydantic schema related to session cost and limit details
    """
    ...


class EventVirtualRoomCostDetailIn(EventPropertyCostDetailIn):
    """
    Pydantic schema related to virtual room cost and limit details
    """
    ...


class EventSessionCostDetailOut(Model):
    """
    Pydantic schema related to session cost and limit details
    """

    max_participants: int = Field(default=None)
    hours: int = Field(default=None)
    remaining_hours: int = Field(default=None)
    active: bool = Field(default=False)
    financial_settings: Optional[SessionFinancialSettingsOutput] = Field(
        default_factory=SessionFinancialSettingsOutput().dict)


class EventVirtualRoomCostDetailOut(Model):
    """
    Pydantic schema related to virtual room cost and limit details
    """

    max_participants: int = Field(default=None)
    hours: int = Field(default=None)
    remaining_hours: int = Field(default=None)
    active: bool = Field(default=False)
    financial_settings: Optional[Dict] = Field(default={})


class EventWorkshopCostDetailOut(Model):
    """
    Pydantic schema related to session cost and limit details
    """

    max_participants: int = Field(default=None)
    hours: int = Field(default=None)
    remaining_hours: int = Field(default=None)
    active: bool = Field(default=False)
    financial_settings: Optional[WorkshopFinancialSettingsOutput] = Field(
        default_factory=WorkshopFinancialSettingsOutput().dict)


class EventPropertiesIn(Model):
    """
    Schema for event properties in event create schema
    """

    session: Optional[EventSessionCostDetailIn] = Field()
    workshop: Optional[EventPropertyCostDetailIn] = Field()
    virtual_room: Optional[bool] = Field(default=False)
    booth: Optional[bool] = Field(default=False)

    @root_validator(skip_on_failure=True, allow_reuse=True)
    def validate_necessary_properties(cls, values):
        session_active = values.get('session').active if values.get('session') else None
        workshop_active = values.get('workshop').active if values.get('workshop') else None
        if not session_active and not workshop_active:
            raise ValueError('At least one of session or workshop must be True')
        return values


class EventPropertiesOut(Model):
    """
    Schema for event properties in event create schema
    """

    session: Optional[EventSessionCostDetailOut] = Field(default_factory=EventSessionCostDetailOut().dict)
    workshop: Optional[EventWorkshopCostDetailOut] = Field(default_factory=EventWorkshopCostDetailOut().dict)
    virtual_room: Optional[bool] = Field(default=False)
    booth: Optional[bool] = Field(default=False)


class EventCreateCostCalculation(Model):
    """
    Pydantic schema for calculating event cost
    """
    session: Optional[EventSessionCostDetailIn] = Field()
    workshop: Optional[EventPropertyCostDetailIn] = Field()


class EventCreateCostCalculationOut(Model):
    """
    Pydantic schema for returning cost calculation result
    """
    workshop_cost: int = Field(default=None)
    session_cost: int = Field(default=None)


class EventsCreate(Model):
    """
    Schema for creating events
    """

    name: str = Field()
    category: str = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    privacy: EventPrivacy = Field(default=EventPrivacy.PUBLIC.value)
    properties: EventPropertiesIn = Field()

    @root_validator(pre=True)
    def validate_date(cls, values):
        if values.get('starts_at') >= values.get('ends_at'):
            raise ValueError("starts_at must be smaller than ends_at.")
        return values


class EventCreateOut(Model):
    """
    Schema for returning created event
    """
    id: ObjectId = Field()
    name: Optional[str] = Field()
    category: Optional[str] = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    privacy: EventPrivacy = Field(default=EventPrivacy.PUBLIC.value)
    properties: EventPropertiesOut = Field(default_factory=EventPropertiesOut().dict)
    is_published: bool = Field()
    cover: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)


class EventOperatorCreate(Model):
    """
    Pydantic schema related to speaker or teacher used in schedule
    """

    username: Optional[str] = Field()
    user_type: Optional[UserType] = Field()
    company_name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    website: Optional[str] = Field()
    linkedin: Optional[str] = Field()


class EventOperator(Model):
    """
    Pydantic schema related to event operator
    """

    id: ObjectId = Field()
    username: Optional[str] = Field()
    email: Optional[EmailStr] = Field()
    user_type: Optional[UserType] = Field()
    type: Optional[EventOperatorType] = Field()
    company_name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    website: Optional[str] = Field()
    linkedin: Optional[str] = Field()

    @root_validator()
    def set_email(cls, values):
        if specify_username_type(
                values.get("username", "") if values.get("username") is not None else ""
        ).value == UsernameType.EMAIL.value:
            values["email"] = values["username"]
        return values


class EventOperatorInSchedule(Model):
    """
    Pydantic schema related to speaker or teacher used in schedule
    """

    id: ObjectId = Field()
    username: Optional[str] = Field()
    user_type: Optional[UserType] = Field()
    type: Optional[EventOperatorType] = Field(default=EventOperatorType.SPEAKER.value)
    company_name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    website: Optional[str] = Field()
    linkedin: Optional[str] = Field()


class EventScheduleDetails(Model):
    """
    Pydantic schema related to event schedule details
    """

    id: Optional[str] = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    operator: Optional[List[EventOperatorInSchedule]] = Field()
    description: Optional[str] = Field()


class EventSchedule(Model):
    """
    Pydantic schema related to event schedule
    """

    details: List[EventScheduleDetails] = Field()
    date: DateTime = Field()


class UserSchedule(Model):
    """Pydantic schema related to user schedule"""

    id: str = Field()
    date: Optional[DateTime] = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    operator: Optional[List[EventOperatorInSchedule]] = Field()
    description: Optional[str] = Field()


class EventSessionSpeakerInListOut(Model):
    """
    Schema for returning event stage speaker in list
    """

    id: ObjectId = Field()
    name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    username: EmailStr = Field()
    linkedin: Optional[str] = Field()
    website: Optional[str] = Field()


class Events(Model):
    """
    Pydantic schema related to events
    """

    id: ObjectId = Field()
    name: str = Field()
    category: str = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    privacy: EventPrivacy = Field(default=EventPrivacy.PUBLIC.value)
    properties: EventPropertiesOut = Field(default_factory=EventPropertiesOut().dict)
    is_published: bool = Field()
    cover: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    schedule: Optional[List[EventSchedule]] = Field(default=[])
    publish_ready: bool = Field(default=False)


class EventsOutInList(Model):
    """
    Schema for returning event in list
    """

    id: ObjectId = Field()
    name: str = Field()
    category: str = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    cover: Optional[str] = Field()
    is_published: Optional[bool] = Field()


class EventsOutList(Model):
    """
    Schema for list of events
    """

    count: int = Field()
    events: List[EventsOutInList] = Field()


class EventSessionSpeaker(Model):
    """
    Schema for creating event stage speaker
    """

    id: ObjectId = Field()
    username: Optional[str] = Field()
    name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    linkedin: Optional[str] = Field()
    website: Optional[str] = Field()


class EventSessionSpeakerPartialUpdate(Model):
    """
    Schema for partial updating event session
    """

    name: Optional[str] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    username: Optional[EmailStr] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()
    linkedin: Optional[str] = Field()
    website: Optional[str] = Field()


class EventSessionSpeakerListOut(Model):
    """
    Schema for returning list of event speakers
    """

    speakers: List[EventSessionSpeakerInListOut] = Field()
    count: int = Field()


class EventOperatorListOut(Model):
    """
    Schema for returning list of event operator
    """

    operators: List[EventOperator] = Field(default=[])
    count: int = Field(default=0)


class EventParticipant(Model):
    """
    Schema for users that register in event
    """

    id: ObjectId = Field()
    username: Optional[str] = Field()
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


class EventSponsor(Model):
    """
    Schema for adding and updating event sponsor in event
    """

    id: Optional[str] = Field(default=None)
    name: str = Field()
    website: str = Field()
    logo: str = Field()


class EventSponsorOut(Model):
    """
    Schema for returning event sponsor in event
    """
    id: str = Field()
    name: str = Field()
    website: str = Field()
    logo: str = Field()


class EventSponsorsInList(Model):
    sponsors: List[EventSponsorOut] = Field()
    count: int = Field()


class EventHost(Model):
    """
    Schema for event host
    """

    name: str = Field()
    logo: Optional[str] = Field()


class EventUpdate(Model):
    """
    Schema for updating event data
    """

    name: Optional[str] = Field()
    category: Optional[str] = Field()
    privacy: Optional[EventPrivacy] = Field()
    description: Optional[str] = Field()
    cover: Optional[str] = Field()
    sponsors: Optional[List[EventSponsor]] = Field()
    hosts: Optional[List[EventHost]] = Field()
    is_published: Optional[bool] = Field()
    schedule: Optional[List[EventSchedule]] = Field()


class EventCreatorDataInPreview(Model):
    id: ObjectId = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()


class ParticipantInListOut(Model):
    """
    Schema for returning participant in list
    """
    id: ObjectId = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    name: Optional[str] = Field()
    headline: Optional[str] = Field()
    avatar: Optional[str] = Field()


class EventPreviewBaseOut(Model):
    """
    Schema for returning general event data in preview page
    """

    id: ObjectId = Field()
    description: Optional[str] = Field()
    cover: Optional[str] = Field()
    sponsors: Optional[List[EventSponsorOut]] = Field(default=[])
    hosts: Optional[List[EventHost]] = Field(default=[])
    name: str = Field()
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    properties: EventPropertiesOut = Field()
    sessions: Optional[List[SessionDataInEvent]] = Field()
    speakers: Optional[List[EventSessionSpeakerInListOut]] = Field(default=[])
    schedule: Optional[List[EventSchedule]] = Field(default=[])
    workshops: Optional[List[WorkshopDataInEventPreviewOut]] = Field()
    creator: Optional[EventCreatorDataInPreview] = Field()
    participants: List[ParticipantInListOut] = Field(default=[])


class EventPreviewOut(EventPreviewBaseOut):
    """
    Schema for returning general event data in preview page
    """
    is_bought: bool = Field()
    is_bookmarked: bool = Field()


class EventPreviewAnonymousOut(EventPreviewBaseOut):
    """
    Schema for returning general event data in preview page
    """
    is_bought: bool = Field(default=False)
    is_bookmarked: bool = Field(default=False)


class EventPreviewAnonymousListOut(Model):
    """
    Schema for returning list of Event previews for explore page
    """

    events: List[EventPreviewAnonymousOut] = Field()
    count: int = Field()


class EventPreviewListOut(Model):
    """
    Schema for returning list of Event previews for explore page
    """

    events: List[EventPreviewOut] = Field()
    count: int = Field()


class DiscountCreate(Model):
    """
    Schema for creating discount for event
    """

    starts_at: Optional[DateTime] = Field(default=None)
    ends_at: Optional[DateTime] = Field(default=None)
    amount: Optional[int] = Field(default=None)
    amount_type: DiscountAmountType = Field(default=DiscountAmountType.AMOUNT)
    count: Optional[int] = Field(default=None)
    name: str = Field()
    use_count: bool = Field()
    use_date_interval: bool = Field()
    type: DiscountType = Field()
    code: Optional[str] = Field(default=None)

    @root_validator()
    def validate_date(cls, values):

        if values.get('use_count'):
            if values.get('count') < 1:
                raise ValueError("use_count is true but count is not greater than 0. ")

        if values.get('type') == DiscountType.CODE.value and not values.get('code'):
            raise ValueError("Provide code when discount type is CODE. ")

        if values.get('type') == DiscountType.CAMPAIGN.value and values.get('code'):
            raise ValueError("Do not send code when type is CAMPAIGN. ")

        if values.get('use_date_interval'):
            if not values.get('starts_at') or not values.get('ends_at'):
                return ValueError("Provide starts_at and ends_at when use_date_interval is true. ")
            if values.get('starts_at') > values.get('ends_at'):
                raise ValueError("starts_at must be smaller than ends_at. ")

        return values


class DiscountUpdate(Model):
    """
    Schema for discount update
    """

    name: str = Field()
    starts_at: Optional[DateTime] = Field(default=None)
    ends_at: Optional[DateTime] = Field(default=None)
    amount: Optional[int] = Field(default=None)
    count: Optional[int] = Field(default=None)
    use_count: bool = Field()
    use_date_interval: bool = Field()


class DiscountPartialUpdate(Model):
    """
    Schema for discount partial update
    """

    name: str = Field()
    starts_at: Optional[DateTime] = Field()
    ends_at: Optional[DateTime] = Field()
    amount: Optional[int] = Field()
    count: Optional[int] = Field()
    use_count: Optional[bool] = Field()
    use_date_interval: Optional[bool] = Field()


class DiscountInListOut(Model):
    """
    Schema for returning discount in list
    """
    name: Optional[str] = Field(default=None)
    used_count: Optional[int] = Field(default=None)
    starts_at: Optional[DateTime] = Field(default=None)
    ends_at: Optional[DateTime] = Field(default=None)
    amount: Optional[int] = Field(default=None)
    amount_type: DiscountAmountType = Field(default=DiscountAmountType.AMOUNT)
    count: Optional[int] = Field(default=None)
    use_amount: Optional[bool] = Field(default=False)
    use_percent: Optional[bool] = Field(default=False)
    use_count: Optional[bool] = Field(default=False)
    use_date_interval: Optional[bool] = Field(default=False)
    code: Optional[str] = Field(default=None)


class DiscountListOut(Model):
    """
    Schema for returning list of discount
    """
    discounts: List[DiscountInListOut] = Field(default_factory=DiscountInListOut().dict)
    count: int = Field(default=0)


class AdminParticipantInListOut(Model):
    """
    Schema for returning participant in list
    """

    id: Optional[ObjectId] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    company_name: Optional[str] = Field()
    user_type: Optional[UserType] = Field()
    headline: Optional[str] = Field()
    avatar: Optional[str] = Field()
    stage: Optional[bool] = Field(default=False)
    stage_object: Optional[SessionCostCalculation] = Field(default={})
    workshop: Optional[bool] = Field(default=False)
    workshop_objects: Optional[List[WorkshopOut]] = Field(default=[])
    total_cost: Optional[int] = Field(default=0)
    payment_status: Optional[bool] = Field(default=False)
    register_date: Optional[DateTime] = Field()


class ParticipantListOut(Model):
    """
    Schema for returning participant list
    """

    participants: List[ParticipantInListOut] = Field()


class AdminParticipantListOut(Model):
    """
    Schema for returning participant list
    """

    count: Optional[int] = Field(default=0)
    participants: Optional[List[AdminParticipantInListOut]] = Field(default=[])


class AddAdminToEvent(Model):
    """
    Schema for adding admin to event
    """

    email: EmailStr = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()


class EventAdminInListOut(Model):
    """
    Schema for returning event admin in list
    """

    username: EmailStr = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()


class EventAdminListOut(Model):
    """
    Schema for returning list of admins
    """

    admins: List[EventAdminInListOut] = Field()
    count: int = Field()


class EventCreatorDataInBookmark(Model):
    id: ObjectId = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()


class AddEventBookmark(Model):
    """
    Pydantic schema for adding event to user's bookmark events
    """

    id: ObjectId = Field()
    name: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    properties: EventPropertiesIn = Field()
    cover: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    creator: Optional[EventCreatorDataInBookmark] = Field()


class EventBookmarkOutInList(Model):
    """
    Pydantic schema for returning event bookmark in list
    """

    id: ObjectId = Field()
    name: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)
    starts_at: DateTime = Field()
    ends_at: DateTime = Field()
    properties: EventPropertiesIn = Field()
    cover: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    creator: Optional[EventCreatorDataInBookmark] = Field()


class EventBookmarkListOut(Model):
    """
    Schema for returning list of admins
    """

    events: List[EventBookmarkOutInList] = Field(default=[])
    count: int = Field(default=0)
