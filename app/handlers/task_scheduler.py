"""Task scheduler class"""

from typing import NoReturn

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config.settings import settings
from app.handlers.mongo import MongoConnection


class AsyncSchedulerClass:
    """Async scheduler class to schedule when and how often to do a job"""
    _JOB_STORES = {
        'default': MongoDBJobStore(
            database=settings.MONGO_DATABASE,
            collection='background_jobs',
            host=MongoConnection.get_url()
        )
    }
    _SCHEDULER = AsyncIOScheduler(timezone="Asia/Tehran", jobstores=_JOB_STORES)

    def __init__(
            self,
            trigger=CronTrigger(day_of_week='*', timezone="Asia/Tehran", hour=12, minute=9)
    ):
        self.trigger = trigger

    def run(
            self,
            func,
            coalesce: bool = False,
            max_instances: int = 2,
            replace_existing: bool = True
    ) -> NoReturn:
        scheduler = self._SCHEDULER
        scheduler.add_job(
            func=func,
            trigger=self.trigger,
            coalesce=coalesce,
            max_instances=max_instances,
            replace_existing=replace_existing
        )
        scheduler.start()
