"""
Portfolio endpoints and views.

Route: "/portfolio"
"""

import datetime
import os
from typing import Any, Optional

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from starlette import status

from app.config.settings import settings
from app.core import depends
from app.core.uploads import move_image_from_temp
from app.schemas.base import ObjectId
from app.schemas.general import OperationResponse, UserType, ConnectionStatus, PortfolioSection
from app.schemas.portfolio import (
    SkillSchemaIn,
    SkillSchemaOut,
    ExperienceSchemaOut,
    ExperienceListOut,
    WorkSampleSchemaOut,
    WorkSampleListOut,
    CertificationSchemaOut,
    CertificationListOut,
    SkillUpdateSchema,
    CompanyUserPortfolioAnonymousUserOut,
    NormalUserPortfolioAnonymousUserOut,
    CompanyUserPortfolioAuthenticatedUserOut,
    NormalUserPortfolioAuthenticatedUserOut,
    UserBasicInfo,
    ExperienceSchemaUpdate,
    ExperienceSchemaPartialUpdate,
    WorkSampleSchemaCreate,
    WorkSampleSchemaUpdate,
    WorkSampleSchemaPartialUpdate,
    CertificationSchemaCreate,
    CertificationSchemaUpdate,
    CertificationSchemaPartialUpdate,
    ExperienceSchemaCreate
)
from app.schemas.users import User

router = APIRouter()
"""
Route: /portfolio
"""


@router.post('/skills', response_model=SkillSchemaOut)
async def add_value_to_skill(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: SkillSchemaIn
) -> Any:
    """
    Add skill to skills array

    Authorization: Required
    """

    now = datetime.datetime.now()
    user = await db.users.find_one(
        {'_id': current_user.id},
        {
            'basic_info.first_name': 1,
            'basic_info.last_name': 1,
            'basic_info.avatar': 1,
            'basic_info.headline': 1,
            'username': 1
        }
    )
    if not User:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    user_basic_info: UserBasicInfo = UserBasicInfo.parse_obj(user)

    result = await db.skills.find_one_and_update(
        {
            'owner_id': current_user.id,
        },
        {
            '$addToSet': {'skills': data.skill},
            '$set': {
                'first_name': user.get('basic_info').get('first_name') if user.get('basic_info') else None,
                'last_name': user.get('basic_info').get('last_name') if user.get('basic_info') else None,
                'headline': user.get('basic_info').get('headline') if user.get('basic_info') else None,
                'avatar': user.get('basic_info').get('avatar') if user.get('basic_info') else None,
                'username': user.get('username'),
                'updated_at': now
            },
            '$setOnInsert': {
                'owner_id': current_user.id,
                'created_at': now
            }

        },
        upsert=True,
        projection={'skills': 1},
        return_document=ReturnDocument.AFTER
    )

    return SkillSchemaOut.parse_obj(result)


@router.put('/skills')
async def update_skills(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: SkillUpdateSchema
) -> Any:
    """
    Update all user skills, accepts array of skills, use this api if you want to prioritize skills

    Authorization: Required
    """

    now = datetime.datetime.now()
    user = await db.users.find_one(
        {'_id': current_user.id},
        {
            'basic_info.first_name': 1,
            'basic_info.last_name': 1,
            'basic_info.avatar': 1,
            'basic_info.headline': 1,
            'username': 1
        }
    )

    result = await db.skills.find_one_and_update(
        {
            'owner_id': current_user.id,
        },
        {
            '$set': {
                'first_name': user.get('basic_info').get('first_name') if user.get('basic_info') else None,
                'last_name': user.get('basic_info').get('last_name') if user.get('basic_info') else None,
                'headline': user.get('basic_info').get('headline') if user.get('basic_info') else None,
                'avatar': user.get('basic_info').get('avatar') if user.get('basic_info') else None,
                'username': user.get('username'),
                'updated_at': now,
                'skills': data.skills
            },
            '$setOnInsert': {
                'owner_id': current_user.id,
                'created_at': now
            }

        },
        upsert=True,
        projection={'skills'},
        return_document=ReturnDocument.AFTER
    )

    return SkillSchemaOut.parse_obj(result)


@router.delete('/skills/{skill}')
async def delete_skill(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        skill: str
) -> Any:
    """
    Delete skill

    Authorization: Required
    """

    result = await db.skills.find_one_and_update(
        {'owner_id': current_user.id},
        {'$pull': {'skills': skill}},
        projection={'skills': 1},
        return_document=ReturnDocument.AFTER
    )

    return SkillSchemaOut.parse_obj(result)


@router.get('/skills', response_model=SkillSchemaOut)
async def get_skills(
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"]))
) -> Any:
    """
    Get user skills

    Authorization: Required
    """

    skills_response = await db.skills.find_one(
        {'owner_id': current_user.id},
        {'skills': 1}
    )

    if not skills_response:
        return SkillSchemaOut()
    return SkillSchemaOut.parse_obj(skills_response)


@router.post('/experiences')
async def add_experience(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: ExperienceSchemaCreate
):
    """
    Add experience

    Authorization: Required
    """

    if data.logo:
        data.logo = await move_image_from_temp(data.logo)

    data = {**data.dict(), 'owner_id': current_user.id, 'created_at': datetime.datetime.now()}
    result = await db.experiences.insert_one(
        data
    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not create experience'
        )

    return ExperienceSchemaOut.parse_obj({**data, 'id': result.inserted_id})


@router.put('/experiences/{experience_id}', response_model=ExperienceSchemaOut)
async def update_experience(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: ExperienceSchemaUpdate,
        experience_id: ObjectId
) -> Any:
    """
    Update experience

    Authorization: Required
    """

    if data.logo:
        data.logo = await move_image_from_temp(data.logo)

    data = data.dict()
    result = await db.experiences.update_one(
        {'_id': experience_id, 'owner_id': current_user.id},
        {'$set': {**data, 'updated_at': datetime.datetime.now()}}
    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not create experience'
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/experiences/{experience_id}', response_model=ExperienceSchemaOut)
async def partial_update_experience(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: ExperienceSchemaPartialUpdate,
        experience_id: ObjectId
) -> Any:
    """
    Partial update experience

    Authorization: Required
    """

    if data.logo:
        data.logo = await move_image_from_temp(data.logo)

    data = data.dict(exclude_unset=True)
    result = await db.experiences.update_one(
        {'_id': experience_id, 'owner_id': current_user.id},
        {'$set': {**data, 'updated_at': datetime.datetime.now()}}
    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not create experience'
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# TODO: add remove image function
@router.delete('/experiences/{experience_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_experience(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        experience_id: ObjectId
):
    """
    Delete experience

    Authorization: Required
    """

    remove_result = await db.experiences.delete_one(
        {'_id': experience_id, 'owner_id': current_user.id}
    )
    if not remove_result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not delete experience'
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/experiences', response_model=ExperienceListOut)
async def get_experiences_list(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20
) -> Any:
    """
    Get user experiences list

    Authorization: Required
    """

    experiences_response = await db.experiences.find(
        {'owner_id': current_user.id}
    ).skip(offset * limit).to_list(length=limit)
    experiences = list(map(
        lambda x: ExperienceSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        experiences_response
    ))
    experience_count = await db.experiences.count_documents({'owner_id': current_user.id})
    return ExperienceListOut(count=experience_count, experiences=experiences)


@router.get('/experiences/{experience_id}')
async def get_experience(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        experience_id: ObjectId
):
    """
    Get user's experience

    Authorization: Required
    """

    result = await db.experiences.find_one(
        {'_id': experience_id, 'owner_id': current_user.id}
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Experience nor found')
    return ExperienceSchemaOut.parse_obj({**result, 'id': experience_id, 'owner_id': current_user.id})


@router.post('/work_samples')
async def add_work_sample(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: WorkSampleSchemaCreate
):
    """
    Add work_sample

    Authorization: Required
    """

    if data.image:
        data.image = await move_image_from_temp(data.image)

    data = {**data.dict(), 'created_at': datetime.datetime.now(), 'owner_id': current_user.id}
    result = await db.work_samples.insert_one(data)

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not create work sample.'
        )

    return WorkSampleSchemaOut.parse_obj({**data, 'id': result.inserted_id})


@router.put('/work_samples/{work_sample_id}', response_model=WorkSampleSchemaOut)
async def update_work_sample(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: WorkSampleSchemaUpdate,
        work_sample_id: ObjectId
):
    """
    Update work sample

    Authorization: Required
    """

    if data.image:
        data.image = await move_image_from_temp(data.image)

    data = data.dict()
    result = await db.work_samples.update_one(
        {'_id': work_sample_id, 'owner_id': current_user.id},
        {'$set': data}
    )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not edit work sample.'
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/work_samples/{work_sample_id}', response_model=WorkSampleSchemaOut)
async def partial_update_work_sample(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: WorkSampleSchemaPartialUpdate,
        work_sample_id: ObjectId
):
    """
    Partial update work sample

    Authorization: Required
    """

    if data.image:
        data.image = await move_image_from_temp(data.image)

    data = data.dict(exclude_unset=True)
    result = await db.work_samples.update_one(
        {'_id': work_sample_id, 'owner_id': current_user.id},
        {'$set': data}
    )

    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not edit work sample.'
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete('/work_samples/{work_sample_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_sample(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        work_sample_id: ObjectId
):
    """
    Delete work sample

    Authorization: Required
    """

    result = await db.work_samples.delete_one({'_id': work_sample_id, 'owner_id': current_user.id})
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not delete work sample.')
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/work_samples', response_model=WorkSampleListOut)
async def get_work_samples(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20
) -> Any:
    """
    Get user work samples

    Authorization: Required
    """

    work_samples_response = await db.work_samples.find(
        {'owner_id': current_user.id}
    ).skip(offset * limit).to_list(length=limit)

    work_samples = list(map(
        lambda x: WorkSampleSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        work_samples_response
    ))

    work_samples_count = await db.work_samples.count_documents({'owner_id': current_user.id})

    return WorkSampleListOut(count=work_samples_count, work_samples=work_samples)


@router.get('/work_samples/{work_sample_id}')
async def get_work_sample(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        work_sample_id: ObjectId
):
    """
    Get one work sample

    Authorization: Required
    """

    result = await db.work_samples.find_one({'_id': work_sample_id, 'owner_id': current_user.id})

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Work sample not found.'
        )

    return WorkSampleSchemaOut.parse_obj({**result, 'id': work_sample_id, 'owner_id': current_user.id})


@router.post('/certifications')
async def add_certification(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: CertificationSchemaCreate
):
    """
    Add certification

    Authorization: Required
    """

    if data.image:
        data.image = await move_image_from_temp(data.image)

    data = {**data.dict(), 'created_at': datetime.datetime.now(), 'owner_id': current_user.id}
    result = await db.certifications.insert_one(data)
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not create certification.'
        )

    return CertificationSchemaOut.parse_obj({**data, 'id': result.inserted_id})


@router.put('/certifications/{certification_id}', response_model=CertificationSchemaOut)
async def update_certification(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: CertificationSchemaUpdate,
        certification_id: ObjectId
):
    """
    Update certification

    Authorization: Required
    """

    if data.image:
        data.image = await move_image_from_temp(data.image)

    data = data.dict()
    result = await db.certifications.update_one(
        {'_id': certification_id, 'owner_id': current_user.id},
        {'$set': {**data, 'updated_at': datetime.datetime.now()}}
    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not edit certification.'
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/certifications/{certification_id}', response_model=CertificationSchemaOut)
async def partial_update_certification(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        data: CertificationSchemaPartialUpdate,
        certification_id: ObjectId
):
    """
    Partial Update certification

    Authorization: Required
    """

    if data.image:
        data.image = await move_image_from_temp(data.image)

    data = data.dict(exclude_unset=True)
    result = await db.certifications.update_one(
        {'_id': certification_id, 'owner_id': current_user.id},
        {'$set': {**data, 'updated_at': datetime.datetime.now()}}
    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not edit certification.'
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete('/certifications/{certification_id}')
async def delete_certification(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        certification_id: ObjectId
):
    """
    Delete work certification

    Authorization: Required
    """

    result = await db.certifications.delete_one({'_id': certification_id, 'owner_id': current_user.id})
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not delete certification.'
        )
    return result.raw_result


@router.get('/certifications', response_model=CertificationListOut)
async def get_certifications(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20
) -> Any:
    """
    Get user certifications

    Authorization: Required
    """

    certifications_response = await db.certifications.find(
        {'owner_id': current_user.id}
    ).skip(offset * limit).to_list(length=limit)

    certifications = list(map(
        lambda x: CertificationSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        certifications_response
    ))

    certifications_count = await db.certifications.count_documents({'owner_id': current_user.id})

    return CertificationListOut(count=certifications_count, certifications=certifications)


@router.get('/certifications/{certification_id}', response_model=CertificationSchemaOut)
async def get_certification(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        certification_id: ObjectId
):
    """
    Get one certification

    Authorization: Required
    """

    result = await db.certifications.find_one({'_id': certification_id, 'owner_id': current_user.id})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Certification not found.'
        )
    return CertificationSchemaOut.parse_obj({**result, 'id': certification_id, 'owner_id': current_user.id})


@router.put('/privacy/{section}/{public}')
async def set_portfolio_privacy(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        public: bool,
        section: PortfolioSection
):
    """
    Change portfolio privacy setting

    Authorization: Required
    """
    result = await db.users.update_one(
        {'_id': current_user.id},
        {'$set': {f'public_portfolio.{section}': public}}
    )
    if not result.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=OperationResponse.UNSUCCESSFUL_UPDATE
        )
    return Response(status_code=status.HTTP_200_OK)


@router.get('/anonymous/{user_id}')
async def get_portfolio_info_anonymous(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        user_id: ObjectId
):
    """
    Get basic information for portfolio

    Authorization: Not Required
    """

    user = await db.users.find_one(
        {'_id': user_id},
        {
            '_id': 1,
            'basic_info': 1,
            'contact_info.email': 1,
            'public_portfolio': 1,
            'user_type': 1
        }
    )
    if user.get('user_type') == UserType.GUEST:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='User has not set user_type.')
    if user.get('user_type') == UserType.NORMAL:
        return NormalUserPortfolioAnonymousUserOut.parse_obj({**user, 'id': user.get('_id')})
    elif user.get('user_type') == UserType.COMPANY:
        return CompanyUserPortfolioAnonymousUserOut.parse_obj({**user, 'id': user.get('_id')})


@router.get('/authenticated/{user_id}')
async def get_portfolio_info_authenticated(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated"])),
        user_id: ObjectId
):
    """
    Get basic information of portfolio for authenticated user

    field_descriptions:
    connection_status: 'CONNECTED','PENDING','NOT_CONNECTED'

    Authorization: Required
    """
    connection_status = None
    connection_status_result = await db.friends.find_one(
        {'$or': [
            {'requester_id': current_user.id, 'requested_id': user_id},
            {'requester_id': user_id, 'requested_id': current_user.id}
        ]},
        {'_id': 0, 'status': 1, 'requester_user': 1}
    )
    if not connection_status_result:
        connection_status = ConnectionStatus.NOT_CONNECTED
    else:
        connection_status = connection_status_result.get('status')

        if connection_status == ConnectionStatus.PENDING and connection_status_result.get(
                'requester_user').get('id') == current_user.id:
            connection_status = ConnectionStatus.IS_REQUESTED.value

    user = await db.users.find_one(
        {'_id': user_id},
        {
            '_id': 1,
            'basic_info': 1,
            'contact_info': 1,
            'public_portfolio': 1,
            'user_type': 1
        }
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. "
        )

    if user.get('user_type') == UserType.GUEST:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='User has not set user_type.')
    if user.get('user_type') == UserType.NORMAL:
        return NormalUserPortfolioAuthenticatedUserOut.parse_obj(
            {**user, 'id': user.get('_id'), 'connection_status': connection_status}
        )
    elif user.get('user_type') == UserType.COMPANY:
        return CompanyUserPortfolioAuthenticatedUserOut.parse_obj(
            {**user, 'id': user.get('_id'), 'connection_status': connection_status}
        )


@router.get('/certifications/pub/{user_id}', response_model=CertificationListOut)
async def get_public_certifications(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        user_id: ObjectId

) -> Any:
    """
    Get user public certifications

    Authorization: Not required
    """

    result = await db.users.find_one({'_id': user_id, 'public_portfolio.certification': True})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Not public.'
        )

    certifications_response = await db.certifications.find(
        {'owner_id': user_id}
    ).skip(offset * limit).to_list(length=limit)

    certifications = list(map(
        lambda x: CertificationSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        certifications_response
    ))

    certifications_count = await db.certifications.count_documents({'owner_id': user_id})

    return CertificationListOut(count=certifications_count, certifications=certifications)


@router.get('/work_samples/pub/{user_id}', response_model=WorkSampleListOut)
async def get_public_work_samples(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        user_id: ObjectId
) -> Any:
    """
    Get user public work samples

    Authorization: Not required
    """

    result = await db.users.find_one({'_id': user_id, 'public_portfolio.work_sample': True})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Not public.'
        )

    work_samples_response = await db.work_samples.find(
        {'owner_id': user_id}
    ).skip(offset * limit).to_list(length=limit)

    work_samples = list(map(
        lambda x: WorkSampleSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        work_samples_response
    ))

    work_samples_count = await db.work_samples.count_documents({'owner_id': user_id})

    return WorkSampleListOut(count=work_samples_count, work_samples=work_samples)


@router.get('/experiences/pub/{user_id}', response_model=ExperienceListOut)
async def get_public_experiences(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        user_id: ObjectId
) -> Any:
    """
    Get user public experiences

    Authorization: Not required
    """

    result = await db.users.find_one({'_id': user_id, 'public_portfolio.experience': True})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Not public.'
        )
    experiences_response = await db.experiences.find(
        {'owner_id': user_id}
    ).skip(offset * limit).to_list(length=limit)

    experiences = list(map(
        lambda x: ExperienceSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        experiences_response
    ))

    experience_count = await db.experiences.count_documents({'owner_id': user_id})

    return ExperienceListOut(count=experience_count, experiences=experiences)


@router.get('/skills/pub/{user_id}', response_model=SkillSchemaOut)
async def get_public_skills(
        user_id: ObjectId,
        db: AsyncIOMotorDatabase = Depends(depends.get_database)
) -> Any:
    """
    Get user public skills

    Authorization: Not required
    """

    result = await db.users.find_one({'_id': user_id, 'public_portfolio.skill': True})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Not public'
        )

    skills_response = await db.skills.find_one(
        {'owner_id': user_id},
        {'skills': 1}
    )
    if not skills_response:
        return SkillSchemaOut()

    return SkillSchemaOut.parse_obj(skills_response)


# admin endpoints

@router.delete('/admin/skills/{user_id}/{skill}')
async def admin_delete_skill(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        skill: str,
        user_id: ObjectId
) -> Any:
    """
    Admin

    Delete skill

    Authorization: Required
    """

    result = await db.skills.find_one_and_update(
        {'owner_id': user_id},
        {'$pull': {'skills': skill}},
        projection={'skills': 1},
        return_document=ReturnDocument.AFTER
    )

    return SkillSchemaOut.parse_obj(result)


@router.get('/admin/skills/{user_id}', response_model=SkillSchemaOut)
async def admin_get_skills(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        user_id: ObjectId
) -> Any:
    """
    Admin

    Get user skills

    Authorization: Required
    """

    skills_response = await db.skills.find_one(
        {'owner_id': user_id},
        {'skills': 1}
    )

    return SkillSchemaOut.parse_obj(skills_response) if skills_response else Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete('/admin/experiences/{experience_id}')
async def admin_delete_experience(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        experience_id: ObjectId,

):
    """
    Admin

    Delete experience

    Authorization: Required
    """

    result = await db.experiences.find_one_and_delete(
        {'_id': experience_id}
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Experience not found. '
        )
    if result.get('logo'):
        try:
            logo_path = result.get('logo')
            path = os.path.join(settings.MEDIA_DIR, logo_path)
            await aiofiles.os.remove(path)
        except Exception as e:
            print(e)
            # TODO log that file has not been deleted
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/admin/experiences/{user_id}', response_model=ExperienceListOut)
async def admin_get_experiences(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        user_id: ObjectId
) -> Any:
    """
    Admin

    Get user experiences

    Authorization: Required
    """

    experiences_response = await db.experiences.find(
        {'owner_id': user_id}
    ).skip(offset * limit).to_list(length=limit)
    experiences = list(map(
        lambda x: ExperienceSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        experiences_response
    ))

    experience_count = await db.experiences.count_documents({'owner_id': user_id})

    return ExperienceListOut(count=experience_count, experiences=experiences)


@router.delete('/admin/work_samples/{work_sample_id}', status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_work_sample(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        work_sample_id: ObjectId,

):
    """
    Admin

    Delete work sample

    Authorization: Required
    """

    result = await db.work_samples.find_one_and_delete({'_id': work_sample_id})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not delete work sample.')
    if result.get('image'):
        try:
            image_path = result.get('image')
            path = os.path.join(settings.MEDIA_DIR, image_path)
            await aiofiles.os.remove(path)
        except Exception as e:
            print(e)
            # TODO log that file has not been deleted

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/admin/work_samples/{user_id}', response_model=WorkSampleListOut)
async def admin_get_work_samples(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        user_id: ObjectId

) -> Any:
    """
    Admin

    Get user work samples

    Authorization: Required
    """

    work_samples_response = await db.work_samples.find(
        {'owner_id': user_id}
    ).skip(offset * limit).to_list(length=limit)

    work_samples = list(map(
        lambda x: WorkSampleSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        work_samples_response
    ))

    work_samples_count = await db.work_samples.count_documents({'owner_id': user_id})

    return WorkSampleListOut(count=work_samples_count, work_samples=work_samples)


@router.delete('/admin/certifications/{certification_id}')
async def admin_delete_certification(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        certification_id: ObjectId,
):
    """
    Admin

    Delete work certification

    Authorization: Required
    """

    result = await db.certifications.find_one_and_delete({'_id': certification_id})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not delete certification.'
        )
    if result.get('image'):
        try:
            image_path = result.get('image')
            path = os.path.join(settings.MEDIA_DIR, image_path)
            await aiofiles.os.remove(path)
        except Exception as e:
            print(e)
            # TODO log that file has not been deleted

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/admin/certifications/{user_id}', response_model=CertificationListOut)
async def admin_get_certifications(
        *,
        db: AsyncIOMotorDatabase = Depends(depends.get_database),
        current_user: User = Depends(depends.permissions(["authenticated", "admin"])),
        offset: Optional[int] = 0,
        limit: Optional[int] = 20,
        user_id: ObjectId

) -> Any:
    """
    Admin

    Get user certifications

    Authorization: Required
    """

    certifications_response = await db.certifications.find(
        {'owner_id': user_id}
    ).skip(offset * limit).to_list(length=limit)

    certifications = list(map(
        lambda x: CertificationSchemaOut.parse_obj({**x, 'id': x.get('_id')}),
        certifications_response
    ))

    certifications_count = await db.certifications.count_documents({'owner_id': user_id})

    return CertificationListOut(count=certifications_count, certifications=certifications)
