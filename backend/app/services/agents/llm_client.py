from app.services.llm_service import generate_response


def generate_text(prompt: str, system_prompt: str | None = None, mode: str = "analysis") -> str:
    return generate_response(prompt=prompt, system_prompt=system_prompt, mode=mode)
