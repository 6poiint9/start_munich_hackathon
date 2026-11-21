"""The one door to the LLM: provider, cache, retries and the call log.

Agents call `extract` and never know the provider. Each call writes one row
to `llm_calls`, so the cost per file and per customer is a query
(docs/skalierung.md N7). The cache key holds the workspace, the model and
the full input, so a changed prompt reads every file again.
"""

import base64
import hashlib
import json
import random
import sqlite3
import threading
import time
from typing import Any

import openai

from lineguard import clock
from lineguard import config
from lineguard import db

_RETRY_WAIT_SECONDS = (1.0, 4.0, 16.0)
_RETRY_STATUS = (408, 409, 429, 500, 502, 503, 504)


class LlmError(Exception):
    """The provider failed after all retries, or returned no JSON."""


class LlmClient:
    """Calls an OpenAI-compatible chat API and returns parsed JSON."""

    def __init__(self, api_key: str, base_url: str, model_fast: str, model_reasoning: str, max_parallel: int = 8, use_cache: bool = True):
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url,
                                     timeout=120.0, max_retries=0)
        self.model_fast = model_fast
        self.model_reasoning = model_reasoning
        self.use_cache = use_cache
        self._slots = threading.BoundedSemaphore(max_parallel)

    def extract(
        self,
        conn: sqlite3.Connection,
        ws: str,
        *,
        purpose: str,
        system: str,
        prompt: str,
        images: list[tuple[bytes, str]] | None = None,
        model: str | None = None,
        file_id: int | None = None,
    ) -> dict[str, Any]:
        """Sends one request and returns the JSON object of the answer.

        Args:
            images: Pairs of image bytes and MIME type for the vision model.

        Raises:
            LlmError: No valid JSON after all retries.
        """
        model = model or self.model_fast
        images = images or []
        key = _cache_key(ws, model, system, prompt, images)
        if self.use_cache:
            cached = conn.execute(
                "SELECT response FROM llm_cache WHERE workspace_id = ? "
                "AND cache_key = ?", (ws, key)).fetchone()
            if cached:
                _log(conn, ws, file_id, purpose, model, 0, 0, 0, True)
                return json.loads(cached["response"])
        started = time.monotonic()
        with self._slots:
            text, tokens_in, tokens_out = self._call(model, system, prompt, images)
        try:
            result = json.loads(text)
        except json.JSONDecodeError as error:
            raise LlmError(f"The model returned no JSON: {text[:200]}") from error
        if not isinstance(result, dict):
            raise LlmError("The model returned JSON that is not an object")
        elapsed_ms = int((time.monotonic() - started) * 1000)
        conn.execute(
            "INSERT OR REPLACE INTO llm_cache (workspace_id, cache_key, "
            "response, created_at) VALUES (?, ?, ?, ?)",
            (ws, key, json.dumps(result, ensure_ascii=False), clock.iso()))
        _log(conn, ws, file_id, purpose, model, tokens_in, tokens_out, elapsed_ms, False)
        return result

    def _call(self, model: str, system: str, prompt: str, images: list[tuple[bytes, str]]) -> tuple[str, int, int]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for data, mime in images:
            encoded = base64.b64encode(data).decode("ascii")
            content.append({"type": "image_url", "image_url": {
                "url": f"data:{mime};base64,{encoded}"}})
        last_error: Exception | None = None
        for wait in (*_RETRY_WAIT_SECONDS, None):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": content}],
                    response_format={"type": "json_object"},
                )
                usage = response.usage
                return (response.choices[0].message.content or "",
                        usage.prompt_tokens if usage else 0,
                        usage.completion_tokens if usage else 0)
            except openai.APIStatusError as error:
                if error.status_code not in _RETRY_STATUS:
                    raise LlmError(f"LLM answered HTTP {error.status_code}: {error.message}") from error
                last_error = error
            except openai.APIConnectionError as error:
                last_error = error
            if wait is not None:
                time.sleep(wait + random.uniform(0, wait / 2))
        raise LlmError(f"LLM failed after retries: {last_error}")


def _cache_key(ws: str, model: str, system: str, prompt: str, images: list[tuple[bytes, str]]) -> str:
    digest = hashlib.sha256()
    for part in (ws, model, system, prompt):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    for data, _ in images:
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def _log(conn: sqlite3.Connection, ws: str, file_id: int | None, purpose: str, model: str, tokens_in: int, tokens_out: int, elapsed_ms: int, cache_hit: bool) -> None:
    db.insert(conn, "llm_calls", ws, file_id=file_id, purpose=purpose,
              model=model, tokens_in=tokens_in, tokens_out=tokens_out,
              ms=elapsed_ms, cache_hit=cache_hit, created_at=clock.iso())


def from_env(use_cache: bool = True) -> LlmClient | None:
    """Builds the client from `.env`, or returns None without a key."""
    api_key = config.get("XAI_API_KEY")
    if not api_key:
        return None
    return LlmClient(
        api_key=api_key,
        base_url=config.get("XAI_BASE_URL", "https://api.x.ai/v1"),
        model_fast=config.get("LLM_MODEL_FAST", "grok-4.20-0309-non-reasoning"),
        model_reasoning=config.get("LLM_MODEL_REASONING", "grok-4.7"),
        max_parallel=config.get_int("LLM_MAX_PARALLEL", 8),
        use_cache=use_cache,
    )
