from celery import Celery

from app.core.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    celery_app = Celery(
        "lifelink",
        broker=settings.celery_broker_url or settings.redis_url,
        backend=settings.celery_result_backend or settings.redis_url,
        include=[
            "app.services.notifications.tasks",
            "app.services.ml_tasks",
            "app.services.gov_tasks",
            "app.services.system_tasks",
        ],
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    return celery_app


celery_app = create_celery_app()
