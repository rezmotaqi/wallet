"""Pydantic schema models related to users."""

from datetime import datetime
from typing import Optional, List, Union

from fastapi.security import OAuth2PasswordBearer
from pydantic import SecretStr, EmailStr, BaseModel, validator
from pydantic.fields import Field

from app.config.settings import settings
from app.schemas.base import Model, ObjectId, IranianMobilePhoneNumber, DateTime
from app.schemas.general import UserType, Gender, UserStatus, NotificationCategory, Roles, ConnectionStatus

oauth2_schema = OAuth2PasswordBearer(tokenUrl=settings.API_PATH + "/auth/login")


class BaseUserBasicInfoOut(Model):
    """Schema for returning Base basic info which is mutual between company and normal user. """

    province: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    headline: Optional[str] = Field(default=None, description="work field")
    about_me: Optional[str] = Field(default=None)
    avatar: Optional[str] = Field(default=None)
    cover: Optional[str] = Field(default=None)


class NormalUserBasicInfoOut(BaseUserBasicInfoOut):
    """Schema for returning normal user basic info. """
    gender: Optional[Gender] = Field(default=None)
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)


class CompanyUserBasicInfoOut(BaseUserBasicInfoOut):
    """
    Schema for returning company user basic info
    """
    company_name: Optional[str] = Field(default=None)


class SocialAccountsOut(BaseModel):
    """
    Schema for returning user social profile links or ids
    """
    network: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)


class ContactInfoOut(Model):
    """
    Schema for returning contact info
    """
    mobile: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    address: Optional[str] = Field(default=None)
    email: Optional[EmailStr] = Field(default=None)
    website: Optional[str] = Field(default=None)
    social_accounts: Optional[List[SocialAccountsOut]] = Field(default=[])


class BaseUserSchemaAdminOut(Model):
    """Base schema for returning user data to admin. """

    id: Optional[ObjectId] = Field()
    username: str = Field()
    role: Optional[List[str]] = Field()
    created_at: DateTime = Field()
    two_step: Optional[bool] = Field()
    contact_info: Optional[ContactInfoOut] = Field()
    owner_id: Optional[ObjectId] = Field()


class CompanyUserSchemaAdminOut(Model):
    """
    Schema for returning company user data to admin
    """

    id: Optional[ObjectId] = Field()
    username: str = Field()
    role: Optional[List[str]] = Field()
    created_at: DateTime = Field()
    two_step: Optional[bool] = Field()
    contact_info: Optional[ContactInfoOut] = Field()
    owner_id: Optional[ObjectId] = Field()
    basic_info: Optional[CompanyUserBasicInfoOut] = Field()


class NormalUserSchemaAdminOut(Model):
    """
    Schema for returning normal user data to admin
    """

    id: Optional[ObjectId] = Field()
    username: str = Field()
    role: Optional[List[str]] = Field()
    created_at: DateTime = Field()
    two_step: Optional[bool] = Field()
    contact_info: Optional[ContactInfoOut] = Field()
    owner_id: Optional[ObjectId] = Field()
    basic_info: Optional[NormalUserBasicInfoOut] = Field()


class NormalUserInfoAdminOut(Model):
    """
    Schema for returning user info to admin in user profile
    """

    id: ObjectId = Field()
    basic_info: Optional[NormalUserBasicInfoOut] = Field(NormalUserBasicInfoOut().dict)
    contact_info: Optional[ContactInfoOut] = Field(default_factory=ContactInfoOut().dict)
    status: Optional[str] = Field()
    user_type: Optional[UserType] = Field()
    username: str = Field()


class CompanyUserInfoAdminOut(Model):
    """
    Schema for returning user info to admin in user profile
    """

    id: ObjectId = Field()
    basic_info: Optional[CompanyUserBasicInfoOut] = Field(CompanyUserBasicInfoOut().dict)
    contact_info: Optional[ContactInfoOut] = Field(default_factory=ContactInfoOut().dict)
    status: Optional[str] = Field()
    user_type: Optional[UserType] = Field()
    username: str = Field()


class UserAdminOut(Model):
    """
    Schema for returning user data for admin in list. is used for both company and normal user
    """

    id: ObjectId = Field()
    username: str = Field()
    created_at: DateTime = Field()
    status: Optional[str] = Field()
    user_type: Union[str, None] = Field()
    avatar: Optional[str] = Field()
    cover: Optional[str] = Field()
    first_name: Optional[str] = Field(description="is used for normal user")
    last_name: Optional[str] = Field(description="is used for normal user")
    company_name: Optional[str] = Field(description="is used for company user")


class UserListAdminOut(Model):
    """Pydantic schema for user list for admin."""

    count: int = Field()
    users: List[UserAdminOut] = Field()


class PublicPortfolioPrivacySettingOut(Model):
    """
    Schema for returning portfolio privacy setting
    """
    experience: Optional[bool] = Field(default=False)
    skill: Optional[bool] = Field(default=False)
    work_sample: Optional[bool] = Field(default=False)
    certification: Optional[bool] = Field(default=False)


class NormalUserInfoOut(Model):

    """
    Schema for returning user info to admin in user profile
    """

    id: ObjectId = Field()
    username: str = Field()
    basic_info: Optional[NormalUserBasicInfoOut] = Field(default_factory=NormalUserBasicInfoOut().dict)
    contact_info: Optional[ContactInfoOut] = Field(default_factory=ContactInfoOut().dict)
    user_type: Optional[UserType] = Field(default=None)
    status: Optional[str] = Field(default=None)
    public_portfolio: Optional[PublicPortfolioPrivacySettingOut] = Field(
        default_factory=PublicPortfolioPrivacySettingOut().dict
    )
    password: bool = Field()


class CompanyUserInfoOut(Model):
    """
    Schema for returning user info to admin in user profile
    """
    id: ObjectId = Field()
    username: str = Field()
    basic_info: Optional[CompanyUserBasicInfoOut] = Field(default_factory=CompanyUserBasicInfoOut().dict)
    contact_info: Optional[ContactInfoOut] = Field(default_factory=ContactInfoOut().dict)
    user_type: Optional[UserType] = Field(default=None)
    status: Optional[str] = Field(default=None)
    public_portfolio: Optional[PublicPortfolioPrivacySettingOut] = Field(
        default_factory=PublicPortfolioPrivacySettingOut().dict
    )
    password: bool = Field()


class User(Model):
    """Pydantic output user."""

    id: Optional[ObjectId] = Field()
    username: str = Field()
    role: Optional[List[str]] = Field()
    two_step: Optional[bool] = Field()


class BaseUserBasicInfoIn(Model):
    """
    Schema for receiving base user basic info which is mutual between normal and company user.
    """
    province: Optional[str] = Field()
    country: Optional[str] = Field()
    headline: Optional[str] = Field(description="work_field")
    about_me: Optional[str] = Field()


class NormalUserBasicInfoIn(BaseUserBasicInfoIn):
    """Schema for receiving normal user basic info. specific data to normal user"""

    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    gender: Optional[Gender] = Field()


class CompanyUserBasicInfoIn(BaseUserBasicInfoIn):
    """
    Schema for receiving company user basic info. Specific data to company user
    """
    company_name: Optional[str] = Field()


class SocialAccounts(BaseModel):
    """
    Schema for user social profile links or ids
    """
    network: str = Field()
    id: str = Field()


class ContactInfoIn(Model):
    """
    Schema for user contact info
    """

    mobile: Optional[IranianMobilePhoneNumber] = Field()
    phone: Optional[str] = Field()
    address: Optional[str] = Field()
    website: Optional[str] = Field()
    email: Optional[EmailStr] = Field()
    social_accounts: Optional[List[SocialAccounts]] = Field()


class NormalUserInfoUpdate(Model):
    """
    Schema for updating all normal user data
    """

    basic_info: Optional[NormalUserBasicInfoIn] = Field()
    contact_info: Optional[ContactInfoIn] = Field()


class NormalUserInfoPartialUpdate(NormalUserInfoUpdate):
    """
    Schema for partial updating all normal user data
    """
    ...


class CompanyUserInfoUpdate(Model):
    """
    Schema for updating all company user data
    """

    basic_info: Optional[CompanyUserBasicInfoIn]
    contact_info: Optional[ContactInfoIn]


class CompanyUserInfoPartialUpdate(CompanyUserInfoUpdate):
    """
    Schema for partial updating all company user data
    """
    ...


class UserCreate(Model):
    """Schema for creating user by admin"""

    username: str = Field()
    password1: SecretStr = Field()
    password2: SecretStr = Field()
    role: Optional[List[Roles]] = Field(default=["user"])
    status: Optional[UserStatus] = Field(default='active')
    user_type: Optional[UserType] = Field()

    @validator('user_type')
    def user_type_validate(cls, v):
        if v == UserType.GUEST:
            raise ValueError('You can not create a user with guest user_type. ')
        return v


class UserChangePassword(Model):
    """Pydantic user change password schema."""

    current_password: SecretStr = Field()
    new_password: SecretStr = Field()
    new_password_confirm: SecretStr = Field()


class UserSetPassword(Model):
    """Pydantic user add password schema."""

    new_password: SecretStr = Field()
    new_password_confirm: SecretStr = Field()


class UserAvatarOut(Model):
    """Pydantic model for user avatar url"""
    avatar: str = Field()


class UserCoverOut(Model):
    """Pydantic model for user avatar url"""
    cover: str = Field()


class UserCompanyLogoOut(Model):
    """Pydantic model for user avatar url"""
    logo: str = Field()


class UsernameLookupIn(Model):
    """
    Pydantic model for checking if username exists
    """
    username: str = Field()


class RegisterDataIn(Model):
    """
    Pydantic model for first step of signup
    """
    username: str = Field()


class UserSignUpIn(Model):
    """
    Pydantic model for getting password from new user
    """

    username: str = Field()
    two_step: Optional[bool] = Field(default=True)
    password1: Optional[SecretStr] = Field()
    password2: Optional[SecretStr] = Field()
    token: SecretStr = Field()


class UserSignUpOut(Model):
    """
    Schema for returning user data after registration
    """
    updated_at: DateTime = Field()
    created_at: DateTime = Field()
    status: Optional[UserStatus] = Field(default='active')
    role: Optional[List[str]] = Field(default=[])
    username: str = Field()
    two_step: Optional[bool] = Field()
    set_password: Optional[bool] = Field()


class SetUserType(Model):
    """
    Schema for updating user type
    """
    user_type: UserType = Field()


class FriendRequestBasicInfo(Model):
    """
    Schema for adding basic user info in friend request
    """

    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()


class RequesterUser(Model):
    """
    Schema for
    """
    id: ObjectId = Field()
    basic_info: FriendRequestBasicInfo = Field()


class RequestedUser(Model):
    """
    Schema for
    """
    id: ObjectId = Field()
    basic_info: FriendRequestBasicInfo = Field()


class FriendsSchema(Model):
    """
    Schema for creating friend relationship between two users, is used when user requests another user
    """
    created_at: DateTime = Field(default_factory=datetime.now)
    updated_at: DateTime = Field(default_factory=datetime.now)
    status: Optional[ConnectionStatus] = Field(default='PENDING')
    requester_user: RequesterUser = Field()
    requested_user: RequestedUser = Field()


class AddFriend(Model):
    """
    Schema for sending friend request
    """
    request_to_id: ObjectId = Field()


class AcceptFriend(Model):
    """
    Schema for accepting friend request
    """
    requester_id: ObjectId = Field()


class DenyFriend(Model):
    """
    Schema for denying friend request
    """
    requester_id: ObjectId = Field()


class DeleteFriend(Model):
    """
    Schema for deleting friend
    """
    friend_id: ObjectId = Field()


class FriendOutSchema(Model):
    """
    Schema for returning one friend
    """

    id: ObjectId = Field()
    created_at: Optional[DateTime] = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    cover: Optional[str] = Field()
    headline: Optional[str] = Field()


class FriendListOutSchema(Model):
    """
    Schema for returning list of friends
    """

    count: int = Field(default=0)
    friends: Optional[List[FriendOutSchema]] = Field(default=[])


class FriendRequestOutSchema(Model):
    """
    Schema for returning one friend request
    """
    id: ObjectId = Field()
    created_at: DateTime = Field()
    first_name: Optional[str] = Field()
    last_name: Optional[str] = Field()
    avatar: Optional[str] = Field()
    headline: Optional[str] = Field()


class FriendRequestListOutSchema(Model):
    """
    Schema for returning list of friend requests
    """
    count: int = Field()
    requests: List[FriendOutSchema] = Field()


class NotificationSchema(Model):
    """
    General schema for notifications system
    Notifications are added to this schema by internal background jobs
    """

    id: Optional[ObjectId] = Field()
    owner_id: ObjectId = Field()
    text: Optional[str] = Field()
    created_at: DateTime = Field(default_factory=datetime.now)
    seen: bool = Field(default=False)
    actionable: bool = Field()
    category: NotificationCategory = Field()
    extra_data: Optional[dict] = Field()


class NotificationListOut(Model):
    """
    Schema for returning list of notifications
    """
    notifications: List[NotificationSchema]
    count: int = Field()


class FriendsSuggestionOut(Model):
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    owner_id: Optional[ObjectId] = Field(default=None)
    avatar: Optional[str] = Field(default=None)
    headline: Optional[str] = Field(default=None)


class FriendSuggestionsListOut(Model):
    count: Optional[int] = Field(default=None)
    users: Optional[List[FriendsSuggestionOut]] = Field(FriendsSuggestionOut().dict)


class ParseDatabaseResultContactInfo(Model):
    contact_info: Optional[ContactInfoOut] = Field()
