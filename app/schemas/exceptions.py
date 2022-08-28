"""
Pydantic schema models related to exceptions
"""

from typing import List, Dict, Union

from app.schemas.base import Model


class Message(Model):
    """
    Pydantic schema for exception handling
    """
    detail: Union[str, List, Dict]
