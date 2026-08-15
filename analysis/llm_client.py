"""
LLM client for Hermes/Featherless API calls.
Handles:
  - OpenAI-compatible chat completions via Featherless.ai
  - Filesystem caching (sha256 of prompt+content) to avoid re-spending tokens
  - JSON response parsing with fallback
"""

import hashlib
import json
import os
from pathlib import Path

import requests
from decouple import config

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FEATHERLESS_API_KEY = config("FEATHERLESS_API_KEY", default="")
FEATHERLESS_BASE_URL = config("FEATHERLESS_BASE_URL", default="https://api.featherless.ai/v1")
MODEL_NAME = config("MODEL_NAME", default="zai-org/GLM-5.2")

CACHE_DIR = Path(__file__).resolve().parent.parent / "responses"
CACHE_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def _cache_key(system_prompt: str, user_prompt: str) -> str:
    """Generate a deterministic SHA256 cache key from prompt content."""
    raw = system_prompt + "\n" + user_prompt
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _get_cached(key: str):
    """Return cached response content or None."""
    path = _cache_path(key)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return None


def _set_cached(key: str, content: str):
    """Persist response content to cache."""
    path = _cache_path(key)
    with open(path, "w") as f:
        json.dump({"content": content}, f)


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def chat_completion(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    temperature: float = 0.3,
    use_cache: bool = True,
) -> str:
    """
    Send a chat completion request to Featherless.ai.
    Returns the assistant message content as a string.

    Caching is enabled by default — repeated calls with the same
    prompt+content return instantly without hitting the API.
    """
    key = _cache_key(system_prompt, user_prompt)

    if use_cache:
        cached = _get_cached(key)
        if cached is not None:
            return cached["content"]

    if not FEATHERLESS_API_KEY:
        raise RuntimeError(
            "FEATHERLESS_API_KEY is not set. "
            "Add it to your .env file (see .env.example)."
        )

    response = requests.post(
        f"{FEATHERLESS_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=120,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    if use_cache:
        _set_cached(key, content)

    return content


# ---------------------------------------------------------------------------
# JSON parsing with fallback
# ---------------------------------------------------------------------------

def chat_completion_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    temperature: float = 0.3,
    use_cache: bool = True,
) -> dict:
    """
    Like chat_completion but parses the response as JSON.
    Strips markdown fences if present and falls back to
    returning a minimal error structure on parse failure.
    """
    raw = chat_completion(
        system_prompt, user_prompt, max_tokens, temperature, use_cache
    )

    # Strip markdown code fences if the model wrapped the JSON
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "parse_error": True,
            "raw_response": raw,
            "themes": [],
            "notable_flags": ["Failed to parse LLM response as JSON"],
        }