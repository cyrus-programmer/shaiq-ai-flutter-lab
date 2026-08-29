from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuntimePolicy:
    max_steps: int = 8
    max_tool_calls: int = 5

    def __post_init__(self) -> None:
        if not 1 <= self.max_steps <= 50:
            raise ValueError("max_steps must be between 1 and 50")
        if not 0 <= self.max_tool_calls <= self.max_steps:
            raise ValueError("max_tool_calls must be between 0 and max_steps")


@dataclass(frozen=True)
class AgentResult:
    status: str
    answer: str | None
    steps: int
    tool_calls: int
    error: str | None = None


@dataclass
class Conversation:
    messages: list[dict[str, Any]] = field(default_factory=list)

    def system(self, content: str) -> None:
        self.messages.append({"role": "system", "content": content})

    def user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def tool_call(self, call_id: str, name: str, arguments: dict[str, Any]) -> None:
        import json
        self.messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments, separators=(",", ":"))},
            }],
        })

    def tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        import json
        self.messages.append({
            "role": "tool", "tool_call_id": call_id,
            "content": json.dumps(result, separators=(",", ":"), ensure_ascii=False),
        })
