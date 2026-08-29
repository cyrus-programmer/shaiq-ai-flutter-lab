from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from toolsafe.audit import MemoryAuditSink, redact
from toolsafe.cli import main
from toolsafe.models import RuntimePolicy
from toolsafe.provider import OpenAICompatibleProvider, ProviderError, ScriptedProvider
from toolsafe.registry import Tool, ToolRegistry
from toolsafe.runtime import AgentRuntime
from toolsafe.schema import SchemaError, validate_object


SCHEMA = {"type": "object", "properties": {
    "value": {"type": "integer", "minimum": 1, "maximum": 10}},
    "required": ["value"], "additionalProperties": False}


def tool(handler=lambda args: args["value"] * 2, *, approval=False):
    return Tool("calculate", "Double a value", SCHEMA, handler, approval)


def runtime(responses, *, registered=None, policy=None, audit=None, approve=None):
    return AgentRuntime(ScriptedProvider(responses), ToolRegistry(registered or [tool()]),
                        policy=policy, audit=audit, approve=approve)


class SchemaTests(unittest.TestCase):
    def test_valid_object(self):
        self.assertEqual(validate_object({"value": 4}, SCHEMA), {"value": 4})

    def test_required_extra_type_and_range(self):
        for value, message in [({}, "missing"), ({"value": 2, "extra": 1}, "unexpected"),
                               ({"value": "2"}, "integer"), ({"value": 11}, "maximum")]:
            with self.subTest(value=value), self.assertRaisesRegex(SchemaError, message):
                validate_object(value, SCHEMA)

    def test_array_items(self):
        schema = {"type": "object", "properties": {"items": {
            "type": "array", "items": {"type": "string", "maxLength": 3}}},
            "required": ["items"], "additionalProperties": False}
        with self.assertRaisesRegex(SchemaError, "longer"):
            validate_object({"items": ["okay", "no"]}, schema)


class RuntimeTests(unittest.TestCase):
    def test_executes_valid_tool_and_finishes(self):
        result = runtime([{"type": "tool_call", "id": "1", "tool": "calculate",
                           "arguments": {"value": 4}},
                          {"type": "final", "answer": "The result is 8."}]).run("double four")
        self.assertEqual((result.status, result.answer, result.tool_calls),
                         ("completed", "The result is 8.", 1))

    def test_unknown_tool_is_not_executed(self):
        audit = MemoryAuditSink()
        result = runtime([{"type": "tool_call", "id": "1", "tool": "shell",
                           "arguments": {}}, {"type": "final", "answer": "Unavailable."}],
                         audit=audit).run("run shell")
        self.assertEqual(result.status, "completed")
        self.assertEqual(audit.events[0].kind, "tool_denied")

    def test_invalid_arguments_do_not_execute(self):
        calls = []
        audit = MemoryAuditSink()
        result = runtime([{"type": "tool_call", "id": "1", "tool": "calculate",
                           "arguments": {"value": 99}}, {"type": "final", "answer": "Invalid."}],
                         registered=[tool(lambda args: calls.append(args))], audit=audit).run("calculate")
        self.assertEqual(result.status, "completed")
        self.assertEqual(calls, [])
        self.assertEqual(audit.events[0].kind, "tool_invalid")

    def test_approval_defaults_to_denied(self):
        calls = []
        audit = MemoryAuditSink()
        runtime([{"type": "tool_call", "id": "1", "tool": "calculate",
                  "arguments": {"value": 2}}, {"type": "final", "answer": "Denied."}],
                registered=[tool(lambda args: calls.append(args), approval=True)],
                audit=audit).run("calculate")
        self.assertEqual(calls, [])
        self.assertEqual(audit.events[0].kind, "tool_denied")

    def test_explicit_approval_executes(self):
        calls = []
        runtime([{"type": "tool_call", "id": "1", "tool": "calculate",
                  "arguments": {"value": 2}}, {"type": "final", "answer": "Done."}],
                registered=[tool(lambda args: calls.append(args), approval=True)],
                approve=lambda item, args: True).run("calculate")
        self.assertEqual(calls, [{"value": 2}])

    def test_repeated_call_id_replays_without_execution(self):
        calls = []
        call = {"type": "tool_call", "id": "same", "tool": "calculate", "arguments": {"value": 2}}
        audit = MemoryAuditSink()
        result = runtime([call, call, {"type": "final", "answer": "Done."}],
                         registered=[tool(lambda args: calls.append(args))], audit=audit).run("calculate")
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(calls), 1)
        self.assertIn("tool_call_replayed", [event.kind for event in audit.events])

    def test_call_id_collision_with_new_arguments_is_denied(self):
        calls = []
        first = {"type": "tool_call", "id": "same", "tool": "calculate", "arguments": {"value": 2}}
        changed = {"type": "tool_call", "id": "same", "tool": "calculate", "arguments": {"value": 3}}
        audit = MemoryAuditSink()
        result = runtime([first, changed, {"type": "final", "answer": "Done."}],
                         registered=[tool(lambda args: calls.append(args))], audit=audit).run("calculate")
        self.assertEqual(result.status, "completed")
        self.assertEqual(calls, [{"value": 2}])
        self.assertEqual(audit.events[1].kind, "tool_denied")

    def test_approval_callback_exception_fails_closed(self):
        calls = []
        def broken_approval(item, args):
            raise RuntimeError("approval service unavailable")
        audit = MemoryAuditSink()
        runtime([{"type": "tool_call", "id": "1", "tool": "calculate",
                  "arguments": {"value": 2}}, {"type": "final", "answer": "Denied."}],
                registered=[tool(lambda args: calls.append(args), approval=True)],
                approve=broken_approval, audit=audit).run("calculate")
        self.assertEqual(calls, [])
        self.assertEqual(audit.events[0].kind, "tool_denied")

    def test_tool_exception_is_contained(self):
        def fail(args):
            raise RuntimeError("database password leaked")
        audit = MemoryAuditSink()
        result = runtime([{"type": "tool_call", "id": "1", "tool": "calculate",
                           "arguments": {"value": 2}}, {"type": "final", "answer": "Failed safely."}],
                         registered=[tool(fail)], audit=audit).run("calculate")
        self.assertEqual(result.status, "completed")
        self.assertEqual(audit.events[0].detail, "RuntimeError")

    def test_tool_call_limit(self):
        calls = [{"type": "tool_call", "id": str(i), "tool": "calculate",
                  "arguments": {"value": 2}} for i in range(3)]
        result = runtime(calls, policy=RuntimePolicy(max_steps=4, max_tool_calls=2)).run("calculate")
        self.assertEqual((result.status, result.tool_calls), ("limit_reached", 2))

    def test_step_limit(self):
        call = {"type": "tool_call", "id": "same", "tool": "calculate", "arguments": {"value": 2}}
        result = runtime([call, call], policy=RuntimePolicy(max_steps=2, max_tool_calls=2)).run("calculate")
        self.assertEqual(result.status, "limit_reached")

    def test_provider_and_protocol_errors(self):
        exhausted = AgentRuntime(ScriptedProvider([]), ToolRegistry([tool()])).run("hello")
        invalid = runtime([{"type": "unknown"}]).run("hello")
        self.assertEqual(exhausted.status, "provider_error")
        self.assertEqual(invalid.status, "protocol_error")

    def test_rejects_empty_or_oversized_messages(self):
        for message in ["", "x" * 10001]:
            with self.subTest(length=len(message)), self.assertRaises(ValueError):
                runtime([{"type": "final", "answer": "x"}]).run(message)


class AuditTests(unittest.TestCase):
    def test_recursive_redaction(self):
        result = redact({"token": "secret", "body": "a@b.com +1 415 555 0123 sk-test_12345678"})
        self.assertEqual(result["token"], "[REDACTED]")
        self.assertNotIn("a@b.com", result["body"])
        self.assertNotIn("555", result["body"])
        self.assertNotIn("sk-test", result["body"])


class FakeHandler(BaseHTTPRequestHandler):
    attempts = 0
    authorization = ""
    payload = None
    response_message = {"content": "Done."}

    def log_message(self, *args):
        pass

    def do_POST(self):
        type(self).attempts += 1
        type(self).authorization = self.headers.get("Authorization", "")
        length = int(self.headers["Content-Length"])
        type(self).payload = json.loads(self.rfile.read(length))
        if type(self).attempts == 1:
            self.send_response(503)
            self.end_headers()
            return
        body = json.dumps({"choices": [{"message": type(self).response_message}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        FakeHandler.attempts = 0
        FakeHandler.response_message = {"content": "Done."}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def provider(self):
        return OpenAICompatibleProvider(f"http://127.0.0.1:{self.server.server_port}/v1",
                                        "test-key", "test-model", max_retries=1, sleeper=lambda _: None)

    def test_retries_and_parses_final(self):
        result = self.provider().complete([{"role": "user", "content": "hi"}], [])
        self.assertEqual(result, {"type": "final", "answer": "Done."})
        self.assertEqual(FakeHandler.attempts, 2)
        self.assertEqual(FakeHandler.authorization, "Bearer test-key")
        self.assertEqual(FakeHandler.payload["model"], "test-model")

    def test_parses_native_tool_call(self):
        FakeHandler.response_message = {"content": None, "tool_calls": [{"id": "call-1",
            "function": {"name": "calculate", "arguments": "{\"value\":3}"}}]}
        result = self.provider().complete([], [])
        self.assertEqual(result["arguments"], {"value": 3})

    def test_environment_requires_all_values(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ProviderError):
            OpenAICompatibleProvider.from_env()


class CliTests(unittest.TestCase):
    def test_demo_script_and_audit(self):
        script = {"responses": [{"type": "final", "answer": "Safe answer."}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "script.json"; audit = root / "audit.json"
            source.write_text(json.dumps(script), encoding="utf-8")
            self.assertEqual(main(["run", "--script", str(source), "--message", "hello",
                                   "--audit", str(audit)]), 0)
            self.assertEqual(json.loads(audit.read_text())[0]["kind"], "completed")


if __name__ == "__main__":
    unittest.main()
