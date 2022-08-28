import requests
from fastapi import HTTPException
from starlette import status

from app.config.settings import settings


async def send_register_mail(email, otp):
    a = requests.post(
        settings.MAILGUN_DOMAIN,
        auth=("api", settings.MAILGUN_KEY),
        data={"from": settings.SENDER_EMAIL,
              "to": [email],
              "subject": "TNC Registration",
              "text": f"Your registration code is {otp}"}
    )

    if a.status_code != 200:
        #TODO add logging
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not available. "
        )


async def send_login_mail(email, otp):
    a = requests.post(
        settings.MAILGUN_DOMAIN,
        auth=("api", settings.MAILGUN_KEY),
        data={"from": settings.SENDER_EMAIL,
              "to": [email],
              "subject": "TNC Login",
              "text": f"Your login code is {otp}"}
    )
    if a.status_code != 200:
        # TODO add logging
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not available. "
        )


async def send_mail(email, subject=None, text=None):
    """
    Sends mail with provided subject and text
    """
    data = {
        "from": settings.SENDER_EMAIL,
        "to": [email],
        "subject": subject,
        "text": text
    }
    response = requests.post(
        settings.MAILGUN_DOMAIN,
        auth=("api", settings.MAILGUN_KEY), data=data
    )
    if response.status_code != 200:
        # TODO add logging
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not available. "
        )
