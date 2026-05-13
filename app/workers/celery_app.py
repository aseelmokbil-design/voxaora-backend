from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "voxaora",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Riyadh",
    enable_utc=True,
    task_soft_time_limit=60,
    task_time_limit=120,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
