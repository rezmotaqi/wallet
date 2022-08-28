"""
Meetings APIs
route: /meetings
"""

import datetime
from itertools import chain
from typing import Optional

from bson import ObjectId as BaseObjectId
from fastapi import APIRouter, Depends, Path, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core import depends
from app.schemas.base import ObjectId
from app.schemas.events import EventOperatorType
from app.schemas.general import UserType
from app.schemas.meetings import MeetingProperty, Permissions, MeetingDetail, MeetingRoles, MeetingClient, MeetingError
from app.schemas.sessions import StageSpeaker
from app.schemas.users import User
from app.schemas.virtual_rooms import VirtualRoomUser
from app.schemas.workshops import Teacher

router = APIRouter()


@router.get("/{property_id}", response_model=Permissions)
async def get_meeting_permissions(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        property_id: ObjectId = Path(...),
        property_option: MeetingProperty = Query(..., alias="property"),
        current_user: Optional[User] = Depends(depends.permissions(["authenticated"]))
):
    """
    Get meeting permissions

    Authorization: required
    """

    meeting_client = None
    permissions = Permissions(access=False)

    property_result = await db[property_option].find_one({"_id": property_id})
    if property_result:
        meeting_result = await db.meetings.find_one({"_id": property_result.get("meeting")})
        if meeting_result:
            event = await db.events.find_one({"_id": meeting_result.get("event_id")})
            if event:
                permissions.meeting = MeetingDetail.parse_obj(meeting_result)
                if property_option == MeetingProperty.virtual_rooms:
                    virtual_room = list(filter(lambda x: x.get("id") == property_id, event.get("virtual_rooms", [])))
                    if virtual_room:
                        permissions.meeting.max_participants = virtual_room[0].get("maximum_clients")
                else:
                    permissions.meeting.max_participants = event.get("properties", {}).get(
                        property_option.value[:-1], {}
                    ).get("max_participants")

                now = datetime.datetime.now()
                if permissions.meeting.starts_at > now or permissions.meeting.ends_at < now:
                    permissions.access = False
                    permissions.error = MeetingError.time
                else:
                    operators_ids = list(map(
                        lambda x: x.get("id"),
                        filter(
                            lambda x: x.get("id") == BaseObjectId(current_user.id),
                            event.get("operators", [])
                        )
                    ))
                    if BaseObjectId(current_user.id) in [*operators_ids, event.get("owner_id")]:
                        operators = list(filter(
                            lambda x: x.get("id") == BaseObjectId(current_user.id) and x.get(
                                "type") == EventOperatorType.ADMIN.value,
                            event.get("operators", [])
                        ))
                        if operators or BaseObjectId(current_user.id) == event.get("owner_id"):
                            if operators:
                                operator = operators[0]
                                permissions.role = MeetingRoles.admin.value
                                meeting_client = MeetingClient.parse_obj(operator)
                                permissions.access = True
                            elif BaseObjectId(current_user.id) == event.get("owner_id"):
                                permissions.role = MeetingRoles.moderator.value
                                permissions.access = True

                        elif property_option == MeetingProperty.sessions:
                            session = list(filter(lambda x: x.get("id") == property_id, event.get("sessions", [])))
                            if session:
                                session = session[0]

                                speakers = list(map(
                                    lambda x: StageSpeaker.parse_obj(x).dict(),
                                    filter(
                                        lambda x: x.get("id") == BaseObjectId(current_user.id),
                                        session.get("speakers", [])
                                    )
                                ))
                                if speakers:
                                    speaker = speakers[0]
                                    permissions.role = MeetingRoles.speaker.value
                                    meeting_client = MeetingClient.parse_obj(speaker)
                                    permissions.access = True

                        elif property_option == MeetingProperty.workshops:
                            workshop = list(filter(lambda x: x.get("id") == property_id, event.get("workshops", [])))
                            if workshop:
                                workshop = workshop[0]

                                teachers = list(map(
                                    lambda x: Teacher.parse_obj(x).dict(),
                                    filter(
                                        lambda x: x.get("id") == BaseObjectId(current_user.id),
                                        workshop.get("operators", [])
                                    )
                                ))
                                if teachers:
                                    teacher = teachers[0]
                                    permissions.role = MeetingRoles.teacher.value
                                    meeting_client = MeetingClient.parse_obj(teacher)
                                    permissions.access = True

                    elif property_option == MeetingProperty.virtual_rooms:
                        virtual_room = list(filter(
                            lambda x: x.get("id") == property_id,
                            event.get("virtual_rooms", [])
                        ))
                        if virtual_room:
                            virtual_room = virtual_room[0]

                            if BaseObjectId(current_user.id) == virtual_room.get("owner", {}).get("id"):
                                permissions.role = MeetingRoles.room_owner.value
                                meeting_client = MeetingClient.parse_obj(virtual_room.get("owner", {}))
                                permissions.access = True

                            else:
                                participant = list(map(
                                    lambda x: VirtualRoomUser.parse_obj(x).dict(),
                                    filter(
                                        lambda x: x.get("id") == BaseObjectId(current_user.id),
                                        virtual_room.get("participants", [])
                                    )
                                ))
                                if participant:
                                    participant = participant[0]
                                    permissions.role = MeetingRoles.participant.value
                                    meeting_client = MeetingClient.parse_obj(participant)
                                    permissions.access = True

                    else:
                        invoices = await db.invoices.find(
                            {'owner.id': BaseObjectId(current_user.id),
                             '$or': [{'is_free': True}, {'is_paid': True}]}
                        ).to_list(length=None)
                        invoices = list(filter(
                            lambda x: x.get("event_id") == event.get("_id"),
                            invoices if invoices else []
                        ))
                        if invoices:
                            if property_option == MeetingProperty.sessions:
                                invoices = list(map(
                                    lambda x: x,
                                    map(lambda x: x.get("session"), filter(lambda x: x.get("session"), invoices))
                                ))
                                if invoices:
                                    permissions.access = True
                                    permissions.role = MeetingRoles.participant.value

                            elif property_option == MeetingProperty.workshops:
                                invoices = list(filter(
                                    lambda x: x.get("id") == property_id,
                                    list(chain.from_iterable(map(
                                        lambda x: x.get("workshops"),
                                        filter(lambda x: x.get("workshops"), invoices)
                                    )))
                                ))
                                if invoices:
                                    permissions.access = True
                                    permissions.role = MeetingRoles.participant.value

                            if permissions.access is True:
                                participants = list(filter(
                                    lambda x: x.get("id") == BaseObjectId(current_user.id),
                                    event.get("participants", [])
                                ))
                                if participants:
                                    meeting_client = MeetingClient.parse_obj(participants[0])
            else:
                permissions.error = MeetingError.property_existence
        else:
            permissions.error = MeetingError.property_existence
    else:
        permissions.error = MeetingError.property_existence

    if permissions.access:
        if not meeting_client:
            user = await db.users.find_one(
                {"_id": BaseObjectId(current_user.id)},
                {
                    '_id': 1,
                    'basic_info': 1,
                    'user_type': 1,
                    'username': 1,
                    'contact_info': 1
                }
            )
            if user:
                if user.get('user_type') in (UserType.NORMAL.value, UserType.COMPANY.value):
                    meeting_client = MeetingClient.parse_obj({
                        **user,
                        "id": user.get("_id"),
                        "company_name": user.get('basic_info', {}).get('company_name'),
                        "first_name": user.get('basic_info', {}).get('first_name'),
                        "last_name": user.get('basic_info', {}).get('last_name'),
                        "avatar": user.get('basic_info', {}).get('avatar'),
                        "headline": user.get('basic_info', {}).get('headline'),
                        "website": user.get('contact_info', {}).get('website')
                    })
                else:
                    permissions.access = False
                    permissions.error = MeetingError.user_existence
            else:
                permissions.access = False
                permissions.error = MeetingError.user_existence
        permissions.client = meeting_client

    return permissions
