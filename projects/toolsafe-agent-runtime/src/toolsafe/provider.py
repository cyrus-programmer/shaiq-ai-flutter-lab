from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Protocol


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]: ...


class ScriptedProvider:
    """Deterministic provider used by examples and CI."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]:
        if not self._responses:
            raise ProviderError("script has no response remaining")
        self.calls += 1
        return self._responses.pop(0)


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str, *, timeout: float = 20,
                 max_retries: int = 2, sleeper: Callable[[float], None] = time.sleep) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ProviderError("base URL must use http or https")
        if not api_key or not model or timeout <= 0 or not 0 <= max_retries <= 5:
            raise ProviderError("provider configuration is invalid")
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.timeout, self.max_retries, self.sleeper = timeout, max_retries, sleeper

    @classmethod
    def from_env(cls) -> "OpenAICompatibleProvider":
        required = ["TOOLSAFE_BASE_URL", "TOOLSAFE_API_KEY", "TOOLSAFE_MODEL"]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ProviderError(f"missing environment variables: {', '.join(missing)}")
        return cls(os.environ[required[0]], os.environ[required[1]], os.environ[required[2]],
                   timeout=float(os.getenv("TOOLSAFE_TIMEOUT_SECONDS", "20")),
                   max_retries=int(os.getenv("TOOLSAFE_MAX_RETRIES", "2")))

    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload = json.dumps({"model": self.model, "messages": messages, "tools": tools,
                              "tool_choice": "auto", "temperature": 0}).encode()
        request = urllib.request.Request(f"{self.base_url}/chat/completions", data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST")
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode())
                return self._parse(body)
            except urllib.error.HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == self.max_retries:
                    raise ProviderError(f"provider HTTP error {error.code}") from error
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                if attempt == self.max_retries:
                    raise ProviderError(f"provider request failed: {type(error).__name__}") from error
            self.sleeper(0.25 * (2 ** attempt))
        raise ProviderError("provider request failed")

    @staticmethod
    def _parse(body: Any) -> dict[str, Any]:
        try:
            message = body["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                call = tool_calls[0]
                return {"type": "tool_call", "id": call["id"],
                        "tool": call["function"]["name"],
                        "arguments": json.loads(call["function"]["arguments"])}
            content = message["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty content")
            return {"type": "final", "answer": content}
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ProviderError("provider response has an invalid tool-calling shape") from error
