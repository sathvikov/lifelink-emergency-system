from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import bcrypt
from bson import ObjectId
from fastapi import HTTPException

from app.core.rbac import AMBULANCE_SUBROLES, GOVERNMENT_SUBROLES, HOSPITAL_SUBROLES, PORTAL_ROLES, AuthContext
from app.core.security import create_access_token
from app.schemas.portal_auth import PortalLoginRequest, PortalSignupRequest
from app.services.collections import HOSPITALS, USERS
from app.services.repository import MongoRepository
from app.db.models import GovVerificationRequest
from app.db.mongo import get_db


class AuthService:
    def __init__(self, db):
        self.user_repo = MongoRepository(db, USERS)
        self.hospital_repo = MongoRepository(db, HOSPITALS)

    @staticmethod
    def list_portals() -> dict:
        return {
            "roles": sorted(PORTAL_ROLES),
            "hospital_sub_roles": sorted(HOSPITAL_SUBROLES),
            "government_sub_roles": sorted(GOVERNMENT_SUBROLES),
            "ambulance_sub_roles": sorted(AMBULANCE_SUBROLES),
        }

    @staticmethod
    def _normalize_role(role: str) -> str:
        return role.strip().lower()

    async def signup(self, payload: PortalSignupRequest) -> dict:
        role = self._normalize_role(payload.role)
        if role not in PORTAL_ROLES:
            raise HTTPException(status_code=400, detail="Unsupported role")

        if payload.subRole:
            if role == "hospital" and payload.subRole not in HOSPITAL_SUBROLES:
                raise HTTPException(status_code=400, detail="Unsupported hospital sub-role")
            if role == "government" and payload.subRole not in GOVERNMENT_SUBROLES:
                raise HTTPException(status_code=400, detail="Unsupported government sub-role")
            if role == "ambulance" and payload.subRole not in AMBULANCE_SUBROLES:
                raise HTTPException(status_code=400, detail="Unsupported ambulance sub-role")

        existing = await self.user_repo.find_one({"email": payload.email})
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        hashed_password = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        is_verified = role in ["public", "government"]

        user_doc: dict = {
            "name": payload.name,
            "email": payload.email,
            "password": hashed_password,
            "role": role,
            "subRole": payload.subRole,
            "location": payload.location,
            "phone": payload.phone,
            "isVerified": is_verified,
            "createdAt": datetime.utcnow(),
        }

        if role == "hospital":
            user_doc["hospitalProfile"] = {
                "regNumber": payload.regNumber or "",
                "type": payload.hospitalType or "General",
                "departmentRole": payload.departmentRole or payload.subRole,
            }

        if role == "government":
            user_doc["governmentProfile"] = {
                "level": payload.governmentLevel or payload.subRole,
            }

        if role == "ambulance":
            user_doc["ambulanceProfile"] = {
                "base": payload.ambulanceBase,
                "vehicleId": payload.vehicleId,
            }

        created = await self.user_repo.insert_one(user_doc)

        if role in ["hospital", "ambulance"]:
            db = get_db()
            async with db() as session:
                session.add(
                    GovVerificationRequest(
                        id=uuid4().hex,
                        entity_type=role,
                        entity_id=str(created["_id"]),
                        status="pending",
                        notes=f"{role.title()} signup pending verification",
                        requested_by=str(created["_id"]),
                        reviewed_by=None,
                        reviewed_at=None,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
                await session.commit()

        if role == "hospital":
            hospital_doc = {
                "user": created["_id"],
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
            await self.hospital_repo.insert_one(hospital_doc)
            return {"message": "Signup successful! Pending Government verification."}

        claims = {"role": role, "sub_role": payload.subRole}
        token = create_access_token(str(created["_id"]), claims=claims)

        return {
            "token": token,
            "user": {
                "id": created["_id"],
                "name": created["name"],
                "email": created["email"],
                "role": created["role"],
                "subRole": created.get("subRole"),
            },
        }

    async def login(self, payload: PortalLoginRequest) -> dict:
        role = self._normalize_role(payload.role)
        if role == "hospital" and payload.hospitalId:
            user = await self.user_repo.find_one({"hospitalProfile.regNumber": payload.hospitalId})
        elif role == "hospital" and not payload.hospitalId:
            raise HTTPException(status_code=400, detail="Hospital ID is required")
        elif payload.email:
            user = await self.user_repo.find_one({"email": payload.email})
        else:
            user = None

        if not user:
            raise HTTPException(status_code=400, detail="User not found")

        if not bcrypt.checkpw(payload.password.encode("utf-8"), user["password"].encode("utf-8")):
            raise HTTPException(status_code=400, detail="Invalid credentials")

        if role != user.get("role"):
            raise HTTPException(status_code=400, detail="Role mismatch")

        if role == "hospital" and not user.get("isVerified", False):
            raise HTTPException(status_code=403, detail="Account pending Government verification")
        if role == "ambulance" and not user.get("isVerified", False):
            raise HTTPException(status_code=403, detail="Awaiting Government Verification")

        claims = {"role": user.get("role"), "sub_role": user.get("subRole")}
        token = create_access_token(str(user["_id"]), claims=claims)

        return {
            "token": token,
            "user": {
                "id": user["_id"],
                "name": user["name"],
                "role": user["role"],
                "subRole": user.get("subRole"),
                "location": user.get("location"),
            },
        }

    async def select_role(self, sub_role: str, ctx: AuthContext) -> dict:
        if ctx.role == "hospital" and sub_role not in HOSPITAL_SUBROLES:
            raise HTTPException(status_code=400, detail="Unsupported hospital sub-role")
        if ctx.role == "government" and sub_role not in GOVERNMENT_SUBROLES:
            raise HTTPException(status_code=400, detail="Unsupported government sub-role")
        if ctx.role == "ambulance" and sub_role not in AMBULANCE_SUBROLES:
            raise HTTPException(status_code=400, detail="Unsupported ambulance sub-role")

        try:
            user_id = ObjectId(ctx.user_id)
        except Exception:
            user_id = ctx.user_id

        updated = await self.user_repo.update_one({"_id": user_id}, {"$set": {"subRole": sub_role}}, return_new=True)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")

        claims = {"role": ctx.role, "sub_role": sub_role}
        token = create_access_token(str(updated["_id"]), claims=claims)

        return {
            "token": token,
            "user": {
                "id": updated["_id"],
                "name": updated.get("name"),
                "role": updated.get("role"),
                "subRole": updated.get("subRole"),
                "location": updated.get("location"),
            },
        }
