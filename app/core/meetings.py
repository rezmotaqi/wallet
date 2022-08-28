"""
Functions for meetings
"""

import datetime
import uuid

from bson import ObjectId as BaseObjectId

from app.schemas.meetings import MeetingProperty, MeetingDetail


async def create_meeting(db, property_data, property_option: MeetingProperty):
    """
    Create meeting and add it to the current property
    """

    now = datetime.datetime.now()
    meeting = MeetingDetail(
        uuid=str(uuid.uuid4()),
        event_id=property_data.get("event_id"),
        property_id=property_data.get("id"),
        starts_at=property_data.get("starts_at"),
        ends_at=property_data.get("ends_at"),
    ).dict()

    meeting = {
        **meeting,
        "created_at": now,
        "updated_at": now
    }

    meeting_result = await db.meetings.insert_one(meeting)
    await db[property_option.value].update_one(
        {"_id": BaseObjectId(property_data.get("id"))},
        {"$set": {"meeting": meeting_result.inserted_id}}
    )

    return {**property_data, "meeting": meeting_result.inserted_id}
