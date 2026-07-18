from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.db.mongo import get_db
from app.services.ai_service import AiService
from app.services.ai_chat_service import AiChatService
from app.services.ambulance_service import AmbulanceService
from app.services.auth_service import AuthService
from app.services.data_integration_service import DataIntegrationService
from app.services.government_service import GovernmentService
from app.services.hospital_service import HospitalService
from app.services.notification_service import NotificationService
from app.services.public_service import PublicService
from app.services.realtime_service import RealtimeService
from app.services.routing_service import RoutingService
from app.services.user_service import UserService
from app.services.weather_service import WeatherService

bearer_scheme = HTTPBearer(auto_error=False)

_ai_service = AiService()
_public_service = PublicService()
_hospital_service = HospitalService()
_government_service = GovernmentService()
_ambulance_service = AmbulanceService()
_notification_service = NotificationService()
_routing_service = RoutingService()
_weather_service = WeatherService()
_data_integration_service = DataIntegrationService(
    routing_service=_routing_service,
    weather_service=_weather_service,
)
_realtime_service = RealtimeService()
_user_service = UserService()


def get_current_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    token = credentials.credentials
    settings = get_settings()

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def require_roles(*allowed_roles: str):
    allowed = {role.lower() for role in allowed_roles}

    def dependency(payload: dict[str, Any] = Depends(get_current_token_payload)) -> dict[str, Any]:
        role = str(payload.get("role", "")).lower()
        if role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return payload

    return dependency


def get_auth_service(db=Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_user_service() -> UserService:
    return _user_service


def get_hospital_service() -> HospitalService:
    return _hospital_service


def get_government_service() -> GovernmentService:
    return _government_service


def get_ambulance_service() -> AmbulanceService:
    return _ambulance_service


def get_public_service() -> PublicService:
    return _public_service


def get_notification_service() -> NotificationService:
    return _notification_service


def get_ai_service() -> AiService:
    return _ai_service


def get_ai_chat_service(db=Depends(get_db)) -> AiChatService:
    return AiChatService(db)


def get_data_integration_service() -> DataIntegrationService:
    return _data_integration_service


def get_routing_service() -> RoutingService:
    return _routing_service


def get_weather_service() -> WeatherService:
    return _weather_service


def get_realtime_service() -> RealtimeService:
    return _realtime_service
