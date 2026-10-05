"""
LLM client abstraction. Default provider is Ollama (fully local, $0, no API key).
An optional free-tier Groq fallback can be enabled via LLM_PROVIDER=groq in .env —
useful on machines too weak to run local models well. The rest of the app never
talks to a provider directly, only through generate()/generate_stream(), so
swapping/adding providers later (OpenAI, Anthropic, Gemini) means editing only
this file.
"""
import base64
from typing import Iterator
from app.config import settings

import ollama as ollama_lib


def _ollama_client():
    return ollama_lib.Client(host=settings.OLLAMA_BASE_URL)


def generate_stream(system_prompt: str, user_prompt: str, image_paths: list[str] | None = None) -> Iterator[str]:
    """Yields response text chunks as they're generated (for streaming to the UI)."""
    if settings.LLM_PROVIDER == "groq":
        yield from _groq_stream(system_prompt, user_prompt)
        return

    messages = [{"role": "system", "content": system_prompt}]
    user_msg = {"role": "user", "content": user_prompt}

    if image_paths:
        # Use the vision model + attach images as base64 for diagram/screenshot questions
        user_msg["images"] = [_encode_image(p) for p in image_paths]
        model = settings.OLLAMA_VISION_MODEL
    else:
        model = settings.OLLAMA_MODEL

    messages.append(user_msg)

    client = _ollama_client()
    try:
        for part in client.chat(model=model, messages=messages, stream=True):
            token = part.get("message", {}).get("content", "")
            if token:
                yield token
    except Exception as e:
        yield (
            f"\n\n⚠️ Could not reach the local Ollama model ('{model}'). "
            f"Make sure Ollama is running (`ollama serve`) and the model is pulled "
            f"(`ollama pull {model}`). Details: {e}"
        )


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _groq_stream(system_prompt: str, user_prompt: str) -> Iterator[str]:
    if not settings.GROQ_API_KEY:
        yield "⚠️ LLM_PROVIDER is set to 'groq' but GROQ_API_KEY is empty in .env."
        return
    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)
    stream = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
