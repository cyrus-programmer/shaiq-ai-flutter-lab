from __future__ import annotations

from typing import Any, Callable

from .audit import AuditEvent, AuditSink, MemoryAuditSink
from .models import AgentResult, Conversation, RuntimePolicy
from .provider import Provider, ProviderError
from .registry import Tool, ToolRegistry
from .schema import SchemaError, validate_object


ApprovalCallback = Callable[[Tool, dict[str, Any]], bool]


class AgentRuntime:
    def __init__(self, provider: Provider, registry: ToolRegistry, *,
                 policy: RuntimePolicy | None = None, audit: AuditSink | None = None,
                 approve: ApprovalCallback | None = None) -> None:
        self.provider = provider
        self.registry = registry
        self.policy = policy or RuntimePolicy()
        self.audit = audit or MemoryAuditSink()
        self.approve = approve or (lambda tool, arguments: False)

    def run(self, message: str, *, system: str = "Use only the supplied tools. Never invent results.") -> AgentResult:
        if not isinstance(message, str) or not message.strip() or len(message) > 10_000:
            raise ValueError("message must contain 1 to 10000 characters")
        conversation = Conversation()
        conversation.system(system)
        conversation.user(message.strip())
        cache: dict[str, tuple[str, Any, dict[str, Any]]] = {}
        tool_calls = 0

        for step in range(1, self.policy.max_steps + 1):
            try:
                response = self.provider.complete(conversation.messages, self.registry.specifications())
            except ProviderError as error:
                self.audit.record(AuditEvent.create("provider_error", detail=str(error)))
                return AgentResult("provider_error", None, step, tool_calls, str(error))

            if not isinstance(response, dict) or response.get("type") not in {"tool_call", "final"}:
                self.audit.record(AuditEvent.create("protocol_error", detail="invalid response type"))
                return AgentResult("protocol_error", None, step, tool_calls, "invalid provider response")
            if response["type"] == "final":
                answer = response.get("answer")
                if not isinstance(answer, str) or not answer.strip():
                    return AgentResult("protocol_error", None, step, tool_calls, "empty final answer")
                self.audit.record(AuditEvent.create("completed", detail={"steps": step, "tool_calls": tool_calls}))
                return AgentResult("completed", answer.strip(), step, tool_calls)

            call_id, name, arguments = response.get("id"), response.get("tool"), response.get("arguments")
            if not isinstance(call_id, str) or not call_id or not isinstance(name, str):
                return AgentResult("protocol_error", None, step, tool_calls, "invalid tool-call identity")
            if call_id in cache:
                cached_name, cached_arguments, cached_result = cache[call_id]
                conversation.tool_call(call_id, name, arguments if isinstance(arguments, dict) else {})
                if name != cached_name or arguments != cached_arguments:
                    result = {"ok": False, "error": "call ID reused with a different request"}
                    conversation.tool_result(call_id, result)
                    self.audit.record(AuditEvent.create("tool_denied", call_id=call_id, tool=name,
                                                        detail="call ID collision"))
                else:
                    conversation.tool_result(call_id, cached_result)
                    self.audit.record(AuditEvent.create("tool_call_replayed", call_id=call_id, tool=name))
                continue
            tool_calls += 1
            if tool_calls > self.policy.max_tool_calls:
                self.audit.record(AuditEvent.create("limit_reached", call_id=call_id, tool=name))
                return AgentResult("limit_reached", None, step, tool_calls - 1, "maximum tool calls reached")

            result = self._execute(call_id, name, arguments)
            cache[call_id] = (name, arguments, result)
            conversation.tool_call(call_id, name, arguments if isinstance(arguments, dict) else {})
            conversation.tool_result(call_id, result)

        self.audit.record(AuditEvent.create("limit_reached", detail="maximum steps reached"))
        return AgentResult("limit_reached", None, self.policy.max_steps, tool_calls, "maximum steps reached")

    def _execute(self, call_id: str, name: str, arguments: Any) -> dict[str, Any]:
        tool = self.registry.get(name)
        if tool is None:
            result = {"ok": False, "error": "tool is not allowed"}
            self.audit.record(AuditEvent.create("tool_denied", call_id=call_id, tool=name, detail=result))
            return result
        try:
            validated = validate_object(arguments, tool.parameters)
        except SchemaError as error:
            result = {"ok": False, "error": str(error)}
            self.audit.record(AuditEvent.create("tool_invalid", call_id=call_id, tool=name,
                                                detail={"arguments": arguments, "error": str(error)}))
            return result
        if tool.requires_approval:
            try:
                approved = self.approve(tool, validated)
            except Exception:
                approved = False
            if not approved:
                result = {"ok": False, "error": "approval required"}
                self.audit.record(AuditEvent.create("tool_denied", call_id=call_id, tool=name,
                                                    detail={"arguments": validated, "reason": "approval required"}))
                return result
        try:
            output = tool.handler(validated)
            result = {"ok": True, "result": output}
            self.audit.record(AuditEvent.create("tool_executed", call_id=call_id, tool=name,
                                                detail={"arguments": validated, "result": output}))
            return result
        except Exception as error:
            result = {"ok": False, "error": "tool execution failed"}
            self.audit.record(AuditEvent.create("tool_failed", call_id=call_id, tool=name,
                                                detail=type(error).__name__))
            return result
