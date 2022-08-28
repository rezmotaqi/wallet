"""
A server-side application that provides centralized authentication and user management coreapi nodes.
"""

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config.settings import settings
from app.core.router import router
from app.events.startups import initialize_project

# ASGI app object
app = FastAPI(
    debug=settings.DEBUG,
    title=settings.PROJECT_NAME,
    # root_path=settings.ROOT_PATH,
    # docs_url=f'/{settings.API_PATH}/docs',
    # redoc_url=f'/{settings.API_PATH}/redoc',
    openapi_url=f"{settings.API_PATH}/openapi.json",
)

# serve media files
# app.mount("/media", StaticFiles(directory="media"), name="media")
# Routing API endpoints
app.include_router(router, prefix=settings.API_PATH)


# Add middlewares to the app
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# TODO "*" cors policy is for development phase
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Add events
app.add_event_handler("startup", initialize_project)
