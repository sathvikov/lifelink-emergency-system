import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("lifelink.notifications")


def send_email(to_email: str, subject: str, html_content: str) -> dict:
    settings = get_settings()
    if not settings.sendgrid_api_key or not settings.sendgrid_from_email:
        logger.warning("SendGrid not configured; skipping email to %s", to_email)
        return {"status": "skipped", "reason": "sendgrid_not_configured"}

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": settings.sendgrid_from_email},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_content}],
    }

    headers = {
        "Authorization": f"Bearer {settings.sendgrid_api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=10) as client:
        response = client.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers)

    if response.status_code >= 400:
        logger.error("SendGrid error: %s", response.text)
        return {"status": "error", "detail": response.text}

    return {"status": "sent"}
