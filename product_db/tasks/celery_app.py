from celery import Celery
from celery.schedules import crontab

from product_db.config import settings

app = Celery(
    "product_db",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "product_db.tasks.process_input",
        "product_db.tasks.sync_mxik",
        "product_db.tasks.quality_stats",
        "product_db.tasks.learn",
    ],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Tashkent",
    enable_utc=True,
)

app.conf.beat_schedule = {
    "sync-mxik-nightly": {
        "task": "product_db.tasks.sync_mxik.sync_mxik",
        "schedule": crontab(hour=2, minute=0),
    },
    "quality-stats-daily": {
        "task": "product_db.tasks.quality_stats.collect_quality_stats",
        "schedule": crontab(hour=3, minute=0),
    },
    "batch-learn-hourly": {
        "task": "product_db.tasks.learn.batch_learn",
        "schedule": crontab(minute=0),  # каждый час
    },
}

