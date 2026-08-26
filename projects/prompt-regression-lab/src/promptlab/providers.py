from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request

from .models import CaseDefinition, ProviderResponse


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    provider_type: str

    def complete(self, case: CaseDefinition) -> ProviderResponse: ...


@dataclass(frozen=True)
class FixtureProvider:
    responses: dict[str, str]
    provider_type: str = "fixture"

    def complete(self, case: CaseDefinition) -> ProviderResponse:
        started = time.perf_counter()
        if case.id not in self.responses:
            raise ProviderError(f"No fixture response for case {case.id}")
        response = self.responses[case.id]
        if not isinstance(response, str):
            raise ProviderError(f"Fixture response for {case.id} must be a string")
        return ProviderResponse(response, (time.perf_counter() - started) * 1000, model="fixture")


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 20.0
    max_retries: int = 2
    sleeper: object = time.sleep
    provider_type: str = "openai_compatible"

    @classmethod
    def from_env(cls) -> "OpenAICompatibleProvider":
        base_url = os.getenv("PROMPTLAB_BASE_URL", "").strip()
        api_key = os.getenv("PROMPTLAB_API_KEY", "").strip()
        model = os.getenv("PROMPTLAB_MODEL", "").strip()
        if not all((base_url, api_key, model)):
            raise ProviderError("PROMPTLAB_BASE_URL, PROMPTLAB_API_KEY, and PROMPTLAB_MODEL are required")
        retries = int(os.getenv("PROMPTLAB_MAX_RETRIES", "2"))
        if not 0 <= retries <= 5:
            raise ProviderError("PROMPTLAB_MAX_RETRIES must be between 0 and 5")
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=float(os.getenv("PROMPTLAB_TIMEOUT_SECONDS", "20")),
            max_retries=retries,
        )

    def complete(self, case: CaseDefinition) -> ProviderResponse:
        messages = []
        if case.system:
            messages.append({"role": "system", "content": case.system})
        messages.append({"role": "user", "content": case.prompt})
        payload = {"model": self.model, "messages": messages, "temperature": case.temperature}
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            req = request.Request(
                f"{self.base_url.rstrip('/')}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                text = parsed["choices"][0]["message"]["content"]
                usage = parsed.get("usage", {})
                return ProviderResponse(
                    text=text,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    input_tokens=usage.get("prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                    model=parsed.get("model", self.model),
                )
            except error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.max_retries:
                    break
            except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
            self.sleeper(0.25 * (2**attempt))  # type: ignore[operator]
        raise ProviderError(f"Provider request failed after {self.max_retries + 1} attempt(s): {type(last_error).__name__}")


def build_provider(config: dict) -> Provider:
    if config["type"] == "fixture":
        return FixtureProvider(config["responses"])
    if config["type"] == "openai_compatible":
        return OpenAICompatibleProvider.from_env()
    raise ProviderError(f"Unsupported provider: {config['type']}")

