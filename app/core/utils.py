"""
General core modules and utils.
"""
import random
import re
import secrets
import socket
import string
from typing import Iterable, Any, Dict, NoReturn, Callable, List
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.config.settings import settings
from app.core.authentication import common_password_validator, verify_password
from app.core.uploads import move_image_from_temp
from app.schemas.general import UsernameType

SECRET_KEY_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"


def get_random_secret_key(
        length: int = 50,
        allowed_chars: Iterable = SECRET_KEY_CHARS) -> str:
    """
    Return a 50 character random string usable as a SECRET_KEY setting value.
    """
    return ''.join(secrets.choice(allowed_chars) for i in range(length))


def singletonify(class_) -> Any:
    """
    Python Singleton design pattern to check instances.
    """

    class Singleton(class_):
        """
        Singleton instances class.
        """
        _instance = None
        _sealed = False

        async def __new__(cls, *args, **kwargs):
            if Singleton._instance is None:
                Singleton._instance = super(Singleton, cls).__new__(
                    cls, *args, **kwargs
                )
                Singleton._instance._sealed = False
            return Singleton._instance

        async def __init__(self, *args, **kwargs):
            if self._sealed:
                return
            await super().__init__(*args, **kwargs)
            self._sealed = True

    Singleton.__name__ = class_.__name__
    return Singleton


def check_passwords(user = None, password_1=None, password_2=None):
    """
    checks passwords strength and checks if they are the same
    """
    if user:
        if user.get('password'):
            if verify_password(password_1, user.get('password')):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New password cannot be the same as old one"
                )

    if password_1 != password_2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords does not match"
        )
    common_password_validator(password_1)
    if not re.search(settings.PASSWORD_REGEX, password_1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password is not valid, use this regex instead : {settings.PASSWORD_REGEX}"
        )


def has_internet(host="8.8.8.8", port=53, timeout=3):
    """Check internet connection."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        print(ex)
        return False

# figure out username_type to insert data in relevant files
def specify_username_type(username: str) -> Any:

    email_regex = settings.EMAIL_REGEX
    mobile_regex = settings.IRANIAN_MOBILE_REGEX
    if re.match(email_regex, username):
        return UsernameType.EMAIL
    elif re.match(mobile_regex, username):
        return UsernameType.MOBILE
    else:
        return UsernameType.USERNAME


def check_datetime_aware(d):
    """
    Checks if datetime object is aware(with timezone) or naive(without timezone)
    returns true if it's aware
    """

    return d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None


def convert_naive_to_aware(dt):
    """
    Converts naive datetime to aware datetime based on timezone value in env
    """

    dt = dt.replace(tzinfo=ZoneInfo(settings.TIMEZONE))
    return dt


def create_mongo_array_update(key: str, data: Dict) -> Dict:
    return_data = {}
    for k, v in data.items():
        return_data[f"{key}.$.{k}"] = v
    return return_data


async def serve_nested_to_root(incoming_info_dict: Dict) -> Dict:
    """Serving nested information"""

    returning_info_dict = {}
    for field, value in incoming_info_dict.items():
        if type(value) is dict:
            for (nested_field, nested_value) in value.items():
                returning_info_dict.update({f'{field}.{nested_field}': nested_value})
        else:
            returning_info_dict.update({f'{field}': value})
    return returning_info_dict


async def async_loop(
        function: Callable = move_image_from_temp,
        item: str = "logo",
        iterable: List[Any] = None,
        to_dict: bool = False
) -> NoReturn:
    if iterable:
        if to_dict:
            iterable = list(map(lambda x: x.__class__.dict(x), iterable))
        for obj in iterable:
            await function(obj.get(item))


def generate_password(length: int) -> str:
    """Password generator"""

    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for i in range(length))
