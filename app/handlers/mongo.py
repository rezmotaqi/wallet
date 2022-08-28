"""
Mongodb database and client connections.
"""
import motor.motor_asyncio

from app.core.utils import singletonify
from app.config.settings import settings


@singletonify
class MongoConnection:
    """
    Mongodb database and client connections class.
    """
    __cli = None
    __db = None

    async def get_client(self) -> motor.motor_asyncio.AsyncIOMotorClient:
        """
        Creates Mongodb client connection.
        """
        if self.__cli is None:
            username = getattr(settings, "MONGO_USERNAME", None)
            password = getattr(settings, "MONGO_PASSWORD", None)
            if username and password:
                auth = f"{username}:{password}"
            elif username:
                auth = username
            else:
                auth = None
            address = f"{settings.MONGO_HOSTNAME}:{settings.MONGO_PORT}"
            database_url = f"mongodb://{auth}@{address}" if auth else f"mongodb://{address}"
            self.__cli = motor.motor_asyncio.AsyncIOMotorClient(
                database_url,
                serverSelectionTimeoutMS=6000,
                maxPoolSize=getattr(settings, "MONGO_POOL_SIZE", None)
            )
        return self.__cli

    async def get_database(self) -> motor.motor_asyncio.AsyncIOMotorDatabase:
        """
        Creates and gets database connection.
        """
        if self.__db is None:
            await self.get_client()
            self.__db = self.__cli.get_database(settings.MONGO_DATABASE)
        return self.__db
