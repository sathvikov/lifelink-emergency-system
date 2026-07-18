from app.core.celery_app import celery_app
from app.services.notifications.sendgrid_client import send_email


@celery_app.task(name="notifications.send_email")
def send_email_task(to_email: str, subject: str, html_content: str) -> dict:
    return send_email(to_email, subject, html_content)
