from typing import List, Optional

from pydantic import BaseModel, root_validator
from pydantic.fields import Field

from app.schemas.base import Model, ObjectId, DateTime
from app.schemas.general import EmploymentType, UserType
from app.schemas.users import NormalUserBasicInfoOut, CompanyUserBasicInfoOut, ContactInfoOut


class BasicInfo(BaseModel):
    """
    Pydantic schema related to basic_info
    """
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    avatar: Optional[str] = Field(default=None)
    headline: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)


class UserBasicInfo(BaseModel):
    """
    Pydantic schema related to user's basic_info
    """
    basic_info: Optional[BasicInfo] = Field(default_factory=BasicInfo().dict)


class SkillSchemaIn(Model):
    """
    Schema for adding value to user skills
    """
    skill: str = Field()


class SkillSchemaOut(Model):
    """
    Schema for returning skills
    """
    skills: Optional[List[str]] = Field(default=[])


class SkillUpdateSchema(Model):
    """
    Schema for updating all user skills
    """
    skills: List[str] = Field()


def validate_end_date(cls, values):
    """
    Validate on experience create and update, end_date and current_workplace
    """

    not_none_fields = {k for k, v in values.items() if v is not None}
    end_date_present = "end_date" in not_none_fields
    current_workplace_present = "current_workplace" in not_none_fields

    if end_date_present and current_workplace_present:
        if values.get('current_workplace') is True:
            raise ValueError("Can't have end_date and current_workplace=True at the same time. ")
    if not end_date_present and not current_workplace_present:
        raise ValueError("Provide either current_workplace or end_date. ")
    if current_workplace_present and values.get('current_workplace') is False and not end_date_present:
        raise ValueError("Can't have no end_date with current_workplace=False. ")

    return values


class ExperienceSchemaCreate(Model):
    """
    Schema for creating experience
    """

    title: str = Field()
    company_name: str = Field()
    description: Optional[str] = Field()
    employment_type: Optional[EmploymentType] = Field()
    start_date: DateTime = Field()
    end_date: Optional[DateTime] = Field()
    current_workplace: Optional[bool] = Field()
    location: Optional[str] = Field()
    logo: Optional[str] = Field()

    _end_date_validation = root_validator(allow_reuse=True)(
        validate_end_date
    )


class ExperienceSchemaUpdate(Model):
    """
    Schema for updating experience
    """

    title: str = Field()
    company_name: str = Field()
    start_date: DateTime = Field()
    employment_type: Optional[EmploymentType] = Field()
    location: Optional[str] = Field()
    end_date: Optional[DateTime] = Field()
    current_workplace: Optional[bool] = Field()
    description: Optional[str] = Field()
    logo: Optional[str] = Field()

    _end_date_validation = root_validator(allow_reuse=True)(
        validate_end_date
    )


class ExperienceSchemaPartialUpdate(Model):
    """
    Schema for partial updating experience
    """

    title: Optional[str] = Field()
    company_name: Optional[str] = Field()
    start_date: Optional[DateTime] = Field()
    employment_type: Optional[EmploymentType] = Field()
    location: Optional[str] = Field()
    end_date: Optional[DateTime] = Field()
    current_workplace: Optional[bool] = Field()
    description: Optional[str] = Field()
    logo: Optional[str] = Field()


class ExperienceSchemaOut(Model):
    """
    Schema for returning one experience data
    """

    id: ObjectId = Field()
    owner_id: ObjectId = Field()
    title: Optional[str] = Field()
    employment_type: Optional[EmploymentType] = Field()
    company_name: Optional[str] = Field()
    location: Optional[str] = Field()
    start_date: Optional[DateTime] = Field()
    end_date: Optional[DateTime] = Field()
    current_workplace: Optional[bool] = Field()
    description: Optional[str] = Field()
    logo: Optional[str] = Field()


class ExperienceListOut(Model):
    """
    Schema for returning list of experiences
    """
    experiences: List[ExperienceSchemaOut] = Field()
    count: int = Field()


class WorkSampleSchemaCreate(Model):
    """
    Schema for creating and updating work sample
    """

    title: str = Field()
    description: Optional[str] = Field()
    link: Optional[str] = Field()
    image: Optional[str] = Field()


class WorkSampleSchemaUpdate(Model):
    """
    Schema for creating and updating work sample
    """

    title: str = Field()
    description: Optional[str] = Field()
    link: Optional[str] = Field()
    image: Optional[str] = Field()


class WorkSampleSchemaPartialUpdate(Model):
    """
    Schema for creating and updating work sample
    """

    title: Optional[str] = Field()
    description: Optional[str] = Field()
    link: Optional[str] = Field()
    image: Optional[str] = Field()


class WorkSampleSchemaOut(Model):
    """
    Schema for returning one work sample data
    """

    id: ObjectId = Field()
    owner_id: ObjectId = Field()
    title: str = Field()
    description: Optional[str] = Field()
    link: Optional[str] = Field()
    image: Optional[str] = Field()
    created_at: Optional[DateTime] = Field()


class WorkSampleListOut(Model):
    """
    Schema for returning list of work samples
    """
    work_samples: List[WorkSampleSchemaOut] = Field()
    count: int = Field()


class CertificationSchemaCreate(Model):
    """
    Schema for creating and updating certification
    """

    title: str = Field()
    issuing_organization: str = Field()
    issuing_date: Optional[DateTime] = Field()
    expiration_date: Optional[DateTime] = Field()
    credential_id: Optional[str] = Field()
    credential_url: Optional[str] = Field()
    expires: Optional[bool] = Field()
    image: Optional[str] = Field()


class CertificationSchemaUpdate(Model):
    """
    Schema for creating and updating certification
    """
    title: str = Field()
    issuing_organization: str = Field()
    issuing_date: Optional[DateTime] = Field()
    expiration_date: Optional[DateTime] = Field()
    credential_id: Optional[str] = Field()
    credential_url: Optional[str] = Field()
    expires: Optional[bool] = Field()
    image: Optional[str] = Field()


class CertificationSchemaPartialUpdate(Model):
    """
    Schema for creating and updating certification
    """
    title: Optional[str] = Field()
    issuing_organization: Optional[str] = Field()
    issuing_date: Optional[DateTime] = Field()
    expiration_date: Optional[DateTime] = Field()
    credential_id: Optional[str] = Field()
    credential_url: Optional[str] = Field()
    expires: Optional[bool] = Field()
    image: Optional[str] = Field()


class CertificationSchemaOut(Model):
    """
    Schema for returning one certification data
    """

    id: ObjectId = Field()
    owner_id: ObjectId = Field()
    title: str = Field()
    issuing_organization: str = Field()
    issuing_date: Optional[DateTime] = Field()
    expiration_date: Optional[DateTime] = Field()
    credential_id: Optional[str] = Field()
    credential_url: Optional[str] = Field()
    expires: Optional[bool] = Field()
    image: Optional[str] = Field()


class CertificationListOut(Model):
    """
    Schema for returning list of certifications
    """
    certifications: List[CertificationSchemaOut] = Field()
    count: int = Field()


class PublicPortfolioPrivacySettingOut(Model):
    """
    Schema for returning portfolio privacy setting
    """
    experience: Optional[bool] = Field(default=False)
    skill: Optional[bool] = Field(default=False)
    work_sample: Optional[bool] = Field(default=False)
    certification: Optional[bool] = Field(default=False)


class BaseUserPortfolioOut(Model):
    """
    Schema for returning normal user portfolio to anonymous user.
    """
    id: ObjectId = Field()
    contact_info: Optional[ContactInfoOut] = Field()
    public_portfolio: Optional[PublicPortfolioPrivacySettingOut] = Field(
        default_factory=PublicPortfolioPrivacySettingOut().dict
    )


class NormalUserPortfolioAnonymousUserOut(BaseUserPortfolioOut):
    """
    Schema for returning normal user portfolio to anonymous user.
    """

    basic_info: Optional[NormalUserBasicInfoOut] = Field()


class CompanyUserPortfolioAnonymousUserOut(BaseUserPortfolioOut):
    """
    Schema for returning company user portfolio to anonymous user.
    """
    basic_info: Optional[CompanyUserBasicInfoOut] = Field()


class NormalUserPortfolioAuthenticatedUserOut(BaseUserPortfolioOut):
    """
    Schema for returning normal user portfolio to authenticated user.
    """

    basic_info: Optional[NormalUserBasicInfoOut] = Field()
    user_type: Optional[UserType] = Field()
    connection_status: str = Field()


class CompanyUserPortfolioAuthenticatedUserOut(BaseUserPortfolioOut):
    """
    Schema for returning company user portfolio to authenticated user.
    """

    basic_info: Optional[CompanyUserBasicInfoOut] = Field()
    user_type: Optional[UserType] = Field()
    connection_status: str = Field()
