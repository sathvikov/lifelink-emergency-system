from __future__ import annotations

from app.services.notifications.sendgrid_client import send_email


class NotificationService:
    def send_email(self, to_email: str, subject: str, html: str) -> dict:
        return send_email(to_email, subject, html)
