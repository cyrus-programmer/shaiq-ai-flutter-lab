from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .schema import validate_object


ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    requires_approval: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").isalnum():
            raise ValueError("tool name must be alphanumeric with optional underscores")
        validate_object({}, {**self.parameters, "required": []})

    def specification(self) -> dict[str, Any]:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters,
        }}


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specifications(self) -> list[dict[str, Any]]:
        return [tool.specification() for tool in self._tools.values()]
