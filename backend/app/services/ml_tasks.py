from __future__ import annotations

import asyncio
from typing import Any

from app.core.celery_app import celery_app
from app.services.ml_runner import run_ml_model


@celery_app.task(name="ml.run_model")
def run_model_task(command: str, payload: Any = None) -> dict:
    return asyncio.run(run_ml_model(command, payload, "ai_ml.py"))
