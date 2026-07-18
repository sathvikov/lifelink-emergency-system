from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import HTTPException, status

PORTAL_ROLES = {
    "public",
    "hospital",
    "ambulance",
    "government",
}

HOSPITAL_SUBROLES = {
    "ceo",
    "finance",
    "emergency",
    "opd",
    "icu",
    "radiology",
    "ot",
}

GOVERNMENT_SUBROLES = {
    "national_admin",
    "state_admin",
    "district_admin",
    "supervisory_authority",
}

AMBULANCE_SUBROLES = {
    "crew",
    "dispatcher",
}

BASE_SCOPES = {
    "public": {
        "dashboard:read",
        "emergency:trigger",
        "alerts:read",
        "ai:ask",
        "profile:write",
    },
    "hospital": {
        "dashboard:read",
        "hospital:read",
        "hospital:write",
        "patients:read",
        "patients:write",
        "resources:read",
        "resources:write",
        "alerts:read",
        "analytics:read",
        "ai:ask",
    },
    "ambulance": {
        "dashboard:read",
        "ambulance:read",
        "ambulance:write",
        "routes:read",
        "routes:write",
        "patients:read",
        "ai:ask",
    },
    "government": {
        "dashboard:read",
        "gov:read",
        "gov:write",
        "analytics:read",
        "policy:write",
        "resources:read",
        "ai:ask",
    },
}

HOSPITAL_SCOPES = {
    "ceo": {"hospital:admin", "finance:read", "finance:write"},
    "finance": {"finance:read", "finance:write"},
    "emergency": {"emergency:control", "ambulance:dispatch"},
    "opd": {"patients:read", "patients:write"},
    "icu": {"patients:read", "patients:write"},
    "radiology": {"imaging:read", "imaging:write"},
    "ot": {"surgery:read", "surgery:write"},
}

GOVERNMENT_SCOPES = {
    "national_admin": {"gov:admin", "policy:write"},
    "state_admin": {"gov:admin"},
    "district_admin": {"gov:ops"},
    "supervisory_authority": {"hospital:oversight"},
}

AMBULANCE_SCOPES = {
    "crew": {"ambulance:operations"},
    "dispatcher": {"ambulance:dispatch"},
}


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    sub_role: str | None
    scopes: set[str]


def resolve_scopes(role: str, sub_role: str | None = None) -> set[str]:
    base = set(BASE_SCOPES.get(role, set()))
    if role == "hospital" and sub_role in HOSPITAL_SCOPES:
        base |= HOSPITAL_SCOPES[sub_role]
    if role == "government" and sub_role in GOVERNMENT_SCOPES:
        base |= GOVERNMENT_SCOPES[sub_role]
    if role == "ambulance" and sub_role in AMBULANCE_SCOPES:
        base |= AMBULANCE_SCOPES[sub_role]
    return base


def ensure_roles(role: str, allowed: Iterable[str]) -> None:
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for this role",
        )


def ensure_scopes(scopes: set[str], required: Iterable[str]) -> None:
    missing = [scope for scope in required if scope not in scopes]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scopes: {', '.join(missing)}",
        )
