"""
Pydantic schema models related to uploads
"""

from enum import Enum
from typing import Optional, List

from pydantic import Field

from app.schemas.base import Model


class Upload(Model):
    """
    Pydantic output user
    """
    filename: str = Field()


class ImageType(str, Enum):
    AVATAR = "avatar"
    COVER = "cover"


class PortfolioImageType(str, Enum):
    COMPANY_LOGO = "experiences"
    WORK_SAMPLE = "work_samples"
    CERTIFICATION = "certifications"
    POST = "posts"


class EventImageType(str, Enum):
    WORKSHOPS = "workshops"
    WORK_SAMPLE = "work_samples"
    CERTIFICATION = "certifications"
    POST = "posts"


class UploadImage(Model):
    status: bool = Field()
    images: Optional[List[str]] = Field()
    message: str = Field()
