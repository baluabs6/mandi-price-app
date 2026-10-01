"""Thin wrapper around the Anthropic Messages API.

Deliberately uses `requests` instead of the `anthropic` SDK to avoid
pulling in an extra dependency for a single call site. Requires
ANTHROPIC_API_KEY to be set (see config.ASSISTANT_ENABLED) — callers
check that flag and degrade to a plain database answer instead of
crashing when no key is configured, so this is safe to ship even before
a key is provisioned.

Two entry points:
  * complete()            – single-turn text completion.
  * complete_with_tools() – multi-turn conversation where the model may
                            call server-side tools (our own DB queries)
                            before answering.
"""
import json
import logging

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
REQUEST_TIMEOUT_SECONDS = 20


class LLMError(Exception):
    pass


def _post(payload: dict, api_key: str) -> dict:
    """POST one request to the Messages API and return the parsed JSON.
    Raises LLMError on any transport / HTTP / parsing failure."""
    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.exception("LLM call failed")
        raise LLMError(str(exc)) from exc
    except ValueError as exc:
        logger.exception("LLM returned invalid JSON")
        raise LLMError("Unexpected response from LLM provider") from exc


def _text_of(content_blocks) -> str:
    return "\n".join(
        b["text"] for b in (content_blocks or []) if b.get("type") == "text"
    ).strip()


def complete(system_prompt: str, user_prompt: str, api_key: str, model: str, max_tokens: int = 500) -> str:
    """Single-turn completion. Returns plain text, raises LLMError on
    any failure so callers can degrade gracefully instead of crashing
    the request."""
    data = _post(
        {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        api_key,
    )
    try:
        return _text_of(data.get("content"))
    except (KeyError, TypeError) as exc:
        logger.exception("Unexpected LLM response shape")
        raise LLMError("Unexpected response from LLM provider") from exc


def complete_with_tools(
    system_prompt: str,
    messages: list,
    tools: list,
    execute_tool,
    api_key: str,
    model: str,
    max_tokens: int = 600,
    max_rounds: int = 4,
) -> str:
    """Run a tool-use loop.

    `messages` is the conversation so far (alternating user/assistant,
    ending with a user turn). `execute_tool(name, input_dict)` must return
    a JSON-serialisable dict and must never raise — tool failures should
    be reported to the model as {"error": "..."} so it can say so plainly.

    Raises LLMError if the API fails or the model never produces a final
    answer within `max_rounds` round-trips.
    """
    convo = list(messages)
    for _ in range(max_rounds):
        data = _post(
            {
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "tools": tools,
                "messages": convo,
            },
            api_key,
        )
        content = data.get("content") or []

        if data.get("stop_reason") != "tool_use":
            text = _text_of(content)
            if not text:
                raise LLMError("LLM returned an empty answer")
            return text

        convo.append({"role": "assistant", "content": content})
        tool_results = []
        for block in content:
            if block.get("type") != "tool_use":
                continue
            result = execute_tool(block.get("name", ""), block.get("input") or {})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result, default=str),
                }
            )
        if not tool_results:
            raise LLMError("stop_reason was tool_use but no tool calls were found")
        convo.append({"role": "user", "content": tool_results})

    raise LLMError("Tool-use loop did not finish within the allowed number of rounds")
