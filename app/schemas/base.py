"""Base models using pydandic."""

import re
from datetime import datetime
from enum import Enum
from typing import Union, Dict, Any, AbstractSet, Mapping, Optional

import pytz
from bson import ObjectId as BaseObjectId
from bson.errors import InvalidId
from persian_tools import national_id
from pydantic import ValidationError
from pydantic.class_validators import ROOT_KEY
from pydantic.error_wrappers import ErrorWrapper
from pydantic.main import BaseModel, BaseConfig


class NotNone(str):
    """Creating a NotNone class for pydantic models."""

    @classmethod
    def validate(cls, value):
        """Validate given value to check if is None."""
        if value is not None:
            return value
        else:
            raise ValueError("None value is not allowed")

    @classmethod
    def __get_validators__(cls):
        yield cls.validate


class ObjectId(str):
    """Creating a ObjectId class for pydantic models."""

    @classmethod
    def validate(cls, value):
        """Validate given str value to check if good for being ObjectId."""
        try:
            return BaseObjectId(str(value))
        except InvalidId as e:
            raise ValueError("Not a valid ObjectId") from e

    @classmethod
    def __get_validators__(cls):
        yield cls.validate


class DateTime(datetime):
    """Datetime class for pydantic models"""

    @staticmethod
    def remove_timezone(value: datetime) -> datetime:
        return datetime.fromisoformat(value.isoformat()[:-6])

    def __new__(cls, value: Optional[Union[int, str, datetime]] = None, *args, **kwargs):
        if args or kwargs:
            if kwargs.get("year"):
                return_object = datetime.__new__(datetime, *args, **kwargs)
            else:
                return_object = datetime.__new__(datetime, value, *args, **kwargs)
        else:
            return_object = cls.validate(value)
        if return_object.tzinfo:
            return_object = cls.remove_timezone(return_object.astimezone(pytz.UTC))
        return return_object

    @classmethod
    def validate(cls, value) -> datetime:
        """Validate given str value to cast to datetime object."""
        return_object = value
        if not isinstance(value, datetime):
            try:
                return_object = datetime.fromisoformat(value)
            except ValueError:
                try:
                    return_object = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
                except:
                    raise ValueError("Invalid datetime format")
            except:
                raise ValueError("Invalid datetime format")
        if return_object.tzinfo:
            return_object = cls.remove_timezone(return_object.astimezone(pytz.UTC))
        return return_object

    @classmethod
    def __get_validators__(cls):
        yield cls.validate


def iso_format(value: datetime) -> str:
    """convert datetime to iso format with utc tz"""
    return f"{value.isoformat()}+00:00"


class NationalID(str):
    """Validate Iranian national id."""

    @classmethod
    def validate(cls, value):
        """Validate method is here."""
        if not national_id.validate(value):
            raise ValueError("Not a valid national id!")
        return value

    @classmethod
    def __get_validators__(cls):
        yield cls.validate


class IranianMobilePhoneNumber(str):
    """Validate Iranian mobile mobile number """

    @classmethod
    def validate(cls, value):
        r = re.search('^98[0-9]{10}$', value)
        if r is None:
            raise ValueError('Not a valid mobile number')
        return value

    @classmethod
    def __get_validators__(cls):
        yield cls.validate


class Model(BaseModel):
    """Inherited model from pydantic basemodel for custom validations."""

    class Config(BaseConfig):
        """Convert datetime and ObjectId to json readable values."""

        json_encoders = {
            datetime: iso_format,
            BaseObjectId: str,
        }

    def nested_dict(
            self,
            *,
            include: Union[AbstractSet[Union[int, str]], Mapping[Union[int, str], Any]] = None,
            exclude: Union[AbstractSet[Union[int, str]], Mapping[Union[int, str], Any]] = None,
            by_alias: bool = False,
            skip_defaults: bool = None,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a dictionary representation of the model, optionally specifying which fields to include or exclude.
        Returning each nested key as separated key values.
        """
        data = self.dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none
        )
        nested_dict = {}
        for field, value in data.items():
            if type(value) is dict:
                for (nested_field, nested_value) in value.items():
                    nested_dict.update({f'{field}.{nested_field}': nested_value})
            else:
                nested_dict.update({f'{field}': value})
        return nested_dict

    @classmethod
    def parse_obj_id(cls, obj: Any):
        obj = cls._enforce_dict_if_root(obj)
        if not isinstance(obj, dict):
            try:
                obj = dict(obj)
            except (TypeError, ValueError) as e:
                exc = TypeError(f'{cls.__name__} expected dict not {obj.__class__.__name__}')
                raise ValidationError([ErrorWrapper(exc, loc=ROOT_KEY)], cls) from e
        obj = {**obj, "id": obj.get("_id")}
        return cls(**obj)

    @classmethod
    def get_field_names(cls, alias=False):
        return list(cls.schema(alias).get("properties").keys())


class DateOrderBy(str, Enum):
    """Schema for patient order-by."""

    created_at = 'created_at'
    _created_at = '-created_at'


class CurrencyType(str, Enum):
    """Type of currency for payment."""

    IRR = 'ریال'
    USD = 'دلار امریکا'
    EUR = 'یورو'
    GBP = 'پوند'
    JPY = 'ین'
    CAD = 'دلار کانادا'
