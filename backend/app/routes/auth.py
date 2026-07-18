from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.db.mongo import get_db
from app.schemas.user import LoginRequest, SignupRequest
from app.db.models import GovVerificationRequest
from app.services.collections import HOSPITALS, USERS
from app.services.repository import MongoRepository

router = APIRouter(tags=["auth"])


def _create_token(user_id: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


@router.post("/signup", status_code=201)
async def signup(payload: SignupRequest):
    db = get_db()
    user_repo = MongoRepository(db, USERS)
    hospital_repo = MongoRepository(db, HOSPITALS)

    role = payload.role.lower()

    existing = await user_repo.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_password = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    is_verified = role in ["public", "government"]

    user_doc: dict = {
        "name": payload.name,
        "email": payload.email,
        "password": hashed_password,
        "role": role,
        "location": payload.location,
        "phone": payload.phone,
        "isVerified": is_verified,
        "createdAt": datetime.utcnow(),
    }

    if role == "hospital":
        user_doc["hospitalProfile"] = {
            "regNumber": payload.regNumber or "",
            "type": payload.hospitalType or "General",
        }

    created = await user_repo.insert_one(user_doc)

    if role in ["hospital", "ambulance"]:
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
        await hospital_repo.insert_one(hospital_doc)
        return {"message": "Signup successful! Pending Government verification."}

    token = _create_token(created["_id"], role)
    return {
        "_id": created["_id"],
        "name": created["name"],
        "email": created["email"],
        "role": created["role"],
        "token": token,
    }


@router.post("/login")
async def login(payload: LoginRequest):
    db = get_db()
    user_repo = MongoRepository(db, USERS)

    user = await user_repo.find_one({"email": payload.email})
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    if not bcrypt.checkpw(payload.password.encode("utf-8"), user["password"].encode("utf-8")):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    if payload.role:
        if payload.role.lower() != user["role"].lower():
            raise HTTPException(
                status_code=400,
                detail=f"This email is registered as '{user['role'].upper()}', not '{payload.role.upper()}'. Please switch tabs.",
            )

    if user["role"] == "hospital" and not user.get("isVerified", False):
        raise HTTPException(status_code=403, detail="Account pending Government verification.")

    token = _create_token(user["_id"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["_id"],
            "name": user["name"],
            "role": user["role"],
            "location": user.get("location"),
        },
    }
