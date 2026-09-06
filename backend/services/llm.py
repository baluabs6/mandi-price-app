"""Thin wrapper around the Anthropic Messages API.

Deliberately uses `requests` instead of the `anthropic` SDK to avoid
pulling in an extra dependency for a single call site. Requires
ANTHROPIC_API_KEY to be set (see config.ASSISTANT_ENABLED) — the
assistant routes check that flag and return a clear 503 instead of
crashing when no key is configured, so this is safe to ship even before
a key is provisioned.
"""
import logging

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class LLMError(Exception):
    pass


def complete(system_prompt: str, user_prompt: str, api_key: str, model: str, max_tokens: int = 500) -> str:
    """Single-turn completion. Returns plain text, raises LLMError on
    any failure so callers can degrade gracefully instead of crashing
    the request."""
    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks).strip()
    except requests.RequestException as exc:
        logger.exception("LLM call failed")
        raise LLMError(str(exc)) from exc
    except (KeyError, ValueError) as exc:
        logger.exception("Unexpected LLM response shape")
        raise LLMError("Unexpected response from LLM provider") from exc
