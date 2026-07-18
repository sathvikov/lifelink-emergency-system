from __future__ import annotations

from app.services.ml_runner import run_ml_model


class AiService:
    async def run_prediction(self, command: str, payload: dict, script: str = "ai_ml.py"):
        return await run_ml_model(command, payload, script)
