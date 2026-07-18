from app.core.config import get_settings
from groq import Groq

settings = get_settings()
client = Groq(api_key=settings.groq_api_key, base_url=settings.groq_base_url, timeout=10)

candidates = [
    'llama3-8b',
    'llama3-8b-4096',
    'llama3-16b-8192',
    'llama3-70b',
    'llama3-70b-8192',
    'llama3-8b-8192',
]

for model in candidates:
    try:
        print('testing model:', model)
        completion = client.chat.completions.create(
            model=model,
            messages=[{'role': 'system', 'content': 'You are a test assistant.'}, {'role': 'user', 'content': 'Hello.'}],
            temperature=0.2,
            top_p=0.9,
            max_tokens=20,
        )
        print('  ok', completion.choices[0].message.content if completion.choices else 'no choice')
        break
    except Exception as exc:
        print('  failed', model, type(exc).__name__, exc)
