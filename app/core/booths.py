"""
Functions related to booths
"""
from datetime import datetime

from app.core.authentication import get_password_hash
from app.core.utils import generate_password
from app.schemas.base import ObjectId
from app.schemas.general import UserStatus, UserType


async def find_or_create_exhibitor(db, booth_request) -> (ObjectId, bool, str):
    """
    Create or find exhibitor user in users collection based on email field
    """

    now = datetime.now()
    user = await db.users.find_one(
        {'username': booth_request.get('email')},
        {'_id': 1}
    )

    user_password = None
    found = True

    if not user:
        found = False
        user_password = generate_password(8)

        # TODO for testing purposes for new user password is generated and set to db and its also returned in response

        user = {
            'username': booth_request.get('email'),
            'created_at': now,
            'updated_at': now,
            'status': UserStatus.ACTIVE.value,
            'user_type': UserType.NORMAL.value,
            'basic_info': {
                'first_name': booth_request.get('first_name'),
                'last_name': booth_request.get('last_name'),
                'headline': booth_request.get('headline')
            },
            "password": get_password_hash(user_password)
        }

        user = await db.users.insert_one(user)
        user_id = user.inserted_id

    else:
        user_id = user.get('_id')

    return user_id, found, user_password
