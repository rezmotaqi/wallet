"""
Functions related to virtual rooms
"""

import json
from collections import Counter
from typing import List, Dict

from bson import ObjectId as BaseObjectId
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from iteration_utilities import unique_everseen

from app.schemas.virtual_rooms import VirtualRoomUser


async def check_room_participants(
        user_id: BaseObjectId,
        event: Dict,
        participants: List[VirtualRoomUser.dict] = None,
        old_participants: List[VirtualRoomUser.dict] = None
) -> List:
    """Check if given participants are allowed to join virtual room"""

    event_members = [*event.get("participants", []), *event.get("operators", []), {"id": event.get("owner_id")}]
    event_members_ids = list(map(lambda x: x.get("id"), event_members))

    if user_id not in event_members_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member in this event"
        )

    if participants:
        if old_participants and Counter(list(map(
                lambda x: json.dumps(jsonable_encoder(VirtualRoomUser.parse_obj(x))),
                old_participants
        ))) == Counter(list(map(lambda x: json.dumps(jsonable_encoder(VirtualRoomUser.parse_obj(x))), participants))):
            participants = old_participants
        else:
            if len(participants) != len(list(unique_everseen(participants))):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="There are duplicated members in participants list"
                )
            participants_ids = list(map(lambda x: x.get("id"), participants))
            event_members = list(unique_everseen(map(
                lambda x: {"id": x.get("id"), "username": x.get("username")},
                (filter(lambda x: x.get("id") in participants_ids, event_members))
            )))
            if len(participants) != len(event_members):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not find all given participants in event"
                )

    return participants
