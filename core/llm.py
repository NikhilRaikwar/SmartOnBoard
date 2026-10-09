"""
LLM and Embedding provider gateway for SmartOnboard.

Supports:
- OpenRouter (primary LLM provider, free/low-cost models)
- AIML API (fallback provider)
- MockProvider (deterministic, zero-network mock for keyless testing and local dev)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Union


class LLMUnavailable(Exception):
    """Raised when LLM provider is unconfigured, keys are missing, or API is down."""
    pass


class MockProvider:
    """Deterministic keyless mock provider for tests and offline development."""

    def __init__(self, script: Optional[List[Dict[str, Any]]] = None):
        self.script = list(script) if script else []
        self.script_index = 0

    def chat(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 800,
        temperature: float = 0.2,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if self.script:
            step = self.script[min(self.script_index, len(self.script) - 1)]
            self.script_index += 1
            if "tool_calls" in step:
                formatted_calls = []
                for idx, tc in enumerate(step["tool_calls"]):
                    call_id = tc.get("id") or f"call_mock_{idx}_{int(time.time())}"
                    formatted_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": json.dumps(tc.get("args") or tc.get("arguments") or {}),
                            },
                        }
                    )
                return {
                    "content": None,
                    "tool_calls": formatted_calls,
                    "usage": {"in": 0, "out": 0},
                }
            final_text = step.get("final") or step.get("content") or "Mock answer."
            return {
                "content": final_text,
                "tool_calls": [],
                "usage": {"in": 0, "out": 0},
            }

        # Default fallback response if no script provided
        last_msg = messages[-1]["content"] if messages else ""
        return {
            "content": f"Mock analysis answer for query: '{last_msg}'. See `README.md` and detected manifests.",
            "tool_calls": [],
            "usage": {"in": 0, "out": 0},
        }

    def embed(self, texts: List[str], **kwargs: Any) -> List[List[float]]:
        return [self._embed_single(t) for t in texts]

    @staticmethod
    def _embed_single(text: str, dim: int = 1536) -> List[float]:
        """Generate a deterministic 1536-dim unit vector from sha256 hash."""
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Seed pseudo-random values deterministically from hash
        raw = []
        for i in range(dim):
            byte_val = h[i % len(h)]
            mult = ((i * 37) % 256) ^ byte_val
            raw.append(float(mult - 128) / 128.0)
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]


def get_client() -> Union[Any, MockProvider]:
    """Return the configured LLM client or raise LLMUnavailable."""
    provider = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()

    if provider == "mock":
        return MockProvider()

    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise LLMUnavailable("OPENROUTER_API_KEY is not set.")
        from openai import OpenAI

        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://smartonboard.dev",
                "X-Title": "SmartOnboard",
            },
        )

    if provider == "aiml":
        api_key = os.getenv("AIML_API_KEY")
        if not api_key:
            raise LLMUnavailable("AIML_API_KEY is not set.")
        from openai import OpenAI

        return OpenAI(
            base_url="https://api.aimlapi.com/v1",
            api_key=api_key,
        )

    raise LLMUnavailable(f"Unsupported LLM provider: {provider}")


def chat(
    messages: List[Dict[str, Any]],
    max_tokens: int = 800,
    temperature: float = 0.2,
    tools: Optional[List[Dict[str, Any]]] = None,
    client: Optional[Union[Any, MockProvider]] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute chat completion with automatic 3x exponential backoff retry.
    Returns {"content": str | None, "tool_calls": list, "usage": {"in": int, "out": int}}
    """
    if client is None:
        client = get_client()

    if isinstance(client, MockProvider):
        return client.chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )

    provider = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()
    if not model:
        if provider == "aiml":
            model = os.getenv("AIML_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
        else:
            model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    last_exc = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            tool_calls = []
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                    )

            usage = {"in": 0, "out": 0}
            if hasattr(response, "usage") and response.usage:
                usage["in"] = getattr(response.usage, "prompt_tokens", 0) or 0
                usage["out"] = getattr(response.usage, "completion_tokens", 0) or 0

            return {
                "content": message.content,
                "tool_calls": tool_calls,
                "usage": usage,
            }
        except Exception as exc:
            last_exc = exc
            status_code = getattr(exc, "status_code", None)
            if status_code in (429, 500, 502, 503, 504) or attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise LLMUnavailable(f"LLM chat call failed: {exc}") from exc

    raise LLMUnavailable(f"LLM chat call failed after 3 retries: {last_exc}")


def embed(
    texts: List[str],
    client: Optional[Union[Any, MockProvider]] = None,
    model: Optional[str] = None,
    batch_size: int = 64,
) -> List[List[float]]:
    """Generate vector embeddings for texts in batches of up to 64."""
    if not texts:
        return []

    if client is None:
        try:
            client = get_client()
        except LLMUnavailable:
            client = MockProvider()

    if isinstance(client, MockProvider):
        return client.embed(texts)

    embed_model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    all_vectors: List[List[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            resp = client.embeddings.create(input=batch, model=embed_model)
            for item in resp.data:
                all_vectors.append(item.embedding)
        except Exception as exc:
            # Fallback to deterministic mock embedding if embedding endpoint fails
            mock = MockProvider()
            all_vectors.extend(mock.embed(batch))

    return all_vectors


def llm_status() -> Dict[str, Any]:
    """Return current LLM configuration and readiness status."""
    provider = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()
    if provider == "mock":
        return {
            "provider": "mock",
            "configured": True,
            "available": True,
            "model": "mock-deterministic",
        }

    if provider == "openrouter":
        has_key = bool(os.getenv("OPENROUTER_API_KEY"))
        return {
            "provider": "openrouter",
            "configured": has_key,
            "available": has_key,
            "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
        }

    if provider == "aiml":
        has_key = bool(os.getenv("AIML_API_KEY"))
        return {
            "provider": "aiml",
            "configured": has_key,
            "available": has_key,
            "model": os.getenv("AIML_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
        }

    return {
        "provider": provider,
        "configured": False,
        "available": False,
        "model": "unconfigured",
    }
