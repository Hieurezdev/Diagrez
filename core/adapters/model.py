import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Protocol

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

logger = logging.getLogger(__name__)


class LLMResponseError(RuntimeError):
    """The provider returned a response that cannot cross the JSON seam."""

    code = "INVALID_RESPONSE"


class LLMTransportError(RuntimeError):
    """A retryable provider transport failure after bounded recovery."""

    code = "TRANSPORT_ERROR"


class CompletionPort(Protocol):
    async def complete_json(self, *, system: str, user: str) -> dict[str, Any]: ...


class OpenAICompatibleCompletion:
    def __init__(self) -> None:
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("LLM_API_KEY is required")
        self._model = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-35B-A3B-GPTQ-Int4")
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL", "http://171.226.10.154:8080/v1"),
            timeout=float(os.getenv("LLM_TIMEOUT", "120")),
        )

    async def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        started_at = time.perf_counter()
        request: dict[str, Any] = {
            "model": self._model,
            "temperature": 0.2,
            "extra_body": {"thinking": False},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        logger.info("llm.request.start", extra={"model": self._model})
        max_attempts = _max_attempts()
        response = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.chat.completions.create(**request)
                break
            except Exception as exc:
                if not _is_retryable(exc) or attempt == max_attempts:
                    raise
                delay = min(8.0, 0.5 * (2 ** (attempt - 1)))
                logger.warning(
                    "llm.request.retry",
                    extra={
                        "model": self._model,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "delay_ms": round(delay * 1000),
                    },
                )
                await asyncio.sleep(delay)
        if response is None:
            raise LLMTransportError("LLM request did not produce a response")
        choice = response.choices[0]
        logger.info(
            "llm.request.complete",
            extra={
                "model": self._model,
                "finish_reason": choice.finish_reason,
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000),
            },
        )
        if choice.finish_reason == "length":
            raise RuntimeError(
                "LLM provider stopped the response at its configured length limit"
            )
        content = choice.message.content
        if not content:
            raise LLMResponseError("LLM returned an empty response")
        try:
            return parse_json_object(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"LLM returned invalid JSON: {exc.msg}") from exc


def parse_json_object(content: str) -> dict[str, Any]:
    """Parse JSON while tolerating common model wrappers around a JSON object."""
    normalized = content.strip()
    normalized = re.sub(
        r"^```(?:json)?\s*|\s*```$", "", normalized, flags=re.IGNORECASE
    )
    normalized = re.sub(
        r"<think>.*?</think>", "", normalized, flags=re.IGNORECASE | re.DOTALL
    ).strip()
    try:
        value = json.loads(normalized)
    except json.JSONDecodeError:
        start = normalized.find("{")
        if start < 0:
            raise
        decoder = json.JSONDecoder()
        value, _ = decoder.raw_decode(normalized[start:])
    if not isinstance(value, dict):
        raise json.JSONDecodeError("expected a JSON object", normalized, 0)
    return value


def _max_attempts() -> int:
    raw_value = os.getenv("LLM_MAX_RETRIES", "2")
    try:
        retries = int(raw_value)
    except ValueError as exc:
        raise ValueError("LLM_MAX_RETRIES must be an integer") from exc
    if retries < 0:
        raise ValueError("LLM_MAX_RETRIES must be non-negative")
    return retries + 1


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, asyncio.TimeoutError, OSError)):
        return True
    status_code = getattr(error, "status_code", None)
    return isinstance(status_code, int) and (status_code == 429 or status_code >= 500)
