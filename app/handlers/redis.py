"""
Redis client connections.
"""

import aioredis

from app.core.utils import singletonify
from app.config.settings import settings


@singletonify
class RedisConnection:
    """
    Redis client connections class.
    """
    __cli = None

    def get_client(self) -> aioredis.client.Redis:
        """
        Creates Redis client connection.
        """
        if self.__cli is None:
            # username = getattr(settings, "MONGO_USERNAME", None)
            # password = getattr(settings, "MONGO_PASSWORD", None)
            # if username and password:
            #     auth = f"{username}:{password}"
            # elif username:
            #     auth = username
            # else:
            #     auth = None
            address = f"{settings.REDIS_HOSTNAME}:{settings.REDIS_PORT}"
            # database_url = f"mongodb://{auth}@{address}" if auth else f"mongodb://{address}"
            # self.__cli = motor.motor_asyncio.AsyncIOMotorClient(
            #     database_url,
            #     serverSelectionTimeoutMS=6000,
            #     maxPoolSize=getattr(settings, "MONGO_POOL_SIZE", None)
            # )
            redis_url = f"redis://{address}"
            self.__cli = aioredis.from_url(redis_url)

        return self.__cli
