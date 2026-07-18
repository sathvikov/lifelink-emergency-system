from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["gateway"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "v2",
    }


@router.get("/info")
async def info() -> dict:
    settings = get_settings()
    return {
        "app": settings.app_name,
        "environment": settings.app_env,
        "llm_provider": settings.llm_provider,
        "vector_store": "mongodb",
    }
