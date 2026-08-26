from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from promptlab.cli import main
from promptlab.evaluators import evaluate
from promptlab.models import CaseDefinition
from promptlab.providers import FixtureProvider, OpenAICompatibleProvider, ProviderError
from promptlab.redaction import redact
from promptlab.reports import compare_results, load_result, write_json, write_junit, write_markdown
from promptlab.runner import run_suite
from promptlab.suite import SuiteError, render_case, suite_digest, validate_suite


def suite(response: str = '{"category":"billing","priority":"normal"}'):
    return {
        "name": "contract",
        "provider": {"type": "fixture", "responses": {"case-1": response}},
        "defaults": {"temperature": 0},
        "cases": [{
            "id": "case-1", "prompt": "Classify {message}", "variables": {"message": "refund"},
            "expectations": [{"type": "json_path", "path": "category", "equals": "billing"}],
        }],
    }


class SuiteTests(unittest.TestCase):
    def test_validates_fixture_suite(self):
        validate_suite(suite())

    def test_rejects_duplicate_ids(self):
        data = suite()
        data["cases"].append(dict(data["cases"][0]))
        with self.assertRaisesRegex(SuiteError, "Duplicate"):
            validate_suite(data)

    def test_rejects_missing_fixture_response(self):
        data = suite()
        data["provider"]["responses"] = {}
        with self.assertRaisesRegex(SuiteError, "missing"):
            validate_suite(data)

    def test_strict_prompt_variables(self):
        case = suite()["cases"][0]
        case["variables"]["unused"] = "value"
        with self.assertRaisesRegex(SuiteError, "unused"):
            render_case(case)

    def test_rejects_malformed_expectation(self):
        data = suite()
        data["cases"][0]["expectations"] = [{"type": "contains"}]
        with self.assertRaisesRegex(SuiteError, "string value"):
            validate_suite(data)

    def test_digest_is_key_order_independent(self):
        first = {"b": 2, "a": 1}
        second = {"a": 1, "b": 2}
        self.assertEqual(suite_digest(first), suite_digest(second))


class EvaluatorTests(unittest.TestCase):
    def test_text_evaluators(self):
        self.assertTrue(evaluate("Hello World", {"type": "contains", "value": "world", "case_sensitive": False}).passed)
        self.assertTrue(evaluate("safe", {"type": "not_contains", "value": "password"}).passed)
        self.assertTrue(evaluate("done", {"type": "exact", "value": "done"}).passed)

    def test_regex_error_is_a_failed_check(self):
        result = evaluate("text", {"type": "regex", "pattern": "["})
        self.assertFalse(result.passed)
        self.assertIn("evaluation error", result.message)

    def test_json_path_supports_lists_and_types(self):
        response = '{"items":[{"score":4.5}]}'
        self.assertTrue(evaluate(response, {"type": "json_path", "path": "items.0.score", "value_type": "number"}).passed)

    def test_missing_json_path_fails(self):
        result = evaluate('{"ok":true}', {"type": "json_path", "path": "missing"})
        self.assertFalse(result.passed)


class RunnerTests(unittest.TestCase):
    def test_passing_suite(self):
        data = suite()
        result = run_suite(data, FixtureProvider(data["provider"]["responses"]))
        self.assertTrue(result.passed)
        self.assertEqual(result.summary, {"total": 1, "passed": 1, "failed": 0})

    def test_failed_assertion_does_not_abort_suite(self):
        data = suite('{"category":"sales"}')
        result = run_suite(data, FixtureProvider(data["provider"]["responses"]))
        self.assertFalse(result.passed)
        self.assertEqual(result.cases[0].error, None)

    def test_provider_error_becomes_case_failure(self):
        data = suite()
        result = run_suite(data, FixtureProvider({}))
        self.assertFalse(result.passed)
        self.assertIn("ProviderError", result.cases[0].error)

    def test_preserves_case_order_with_concurrency(self):
        data = suite()
        data["cases"].append({
            "id": "case-2", "prompt": "Say {value}", "variables": {"value": "yes"},
            "expectations": [{"type": "exact", "value": "yes"}],
        })
        provider = FixtureProvider({"case-1": '{"category":"billing"}', "case-2": "yes"})
        result = run_suite(data, provider, max_workers=2)
        self.assertEqual([case.id for case in result.cases], ["case-1", "case-2"])


class RedactionTests(unittest.TestCase):
    def test_redacts_pii_tokens_and_custom_values(self):
        source = "a@b.com +1 (415) 555-0123 sk-test_123456789012 Bearer abcdefghijkl secret-value"
        result = redact(source, ["secret-value"])
        self.assertNotIn("a@b.com", result)
        self.assertNotIn("555-0123", result)
        self.assertNotIn("sk-test", result)
        self.assertNotIn("abcdefghijkl", result)
        self.assertNotIn("secret-value", result)


class ReportTests(unittest.TestCase):
    def test_writes_parseable_reports(self):
        data = suite()
        result = run_suite(data, FixtureProvider(data["provider"]["responses"]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(result, root / "result.json")
            write_markdown(result, root / "result.md")
            write_junit(result, root / "junit.xml")
            self.assertEqual(load_result(root / "result.json")["passed"], True)
            self.assertIn("**Status:** PASS", (root / "result.md").read_text())
            self.assertEqual(ET.parse(root / "junit.xml").getroot().attrib["failures"], "0")

    def test_comparison_detects_regression_missing_and_improvement(self):
        baseline = {"cases": [
            {"id": "a", "passed": True, "latency_ms": 10},
            {"id": "b", "passed": True, "latency_ms": 10},
            {"id": "c", "passed": False, "latency_ms": 10},
        ]}
        candidate = {"cases": [
            {"id": "a", "passed": False, "latency_ms": 11},
            {"id": "c", "passed": True, "latency_ms": 10},
            {"id": "d", "passed": True, "latency_ms": 1},
        ]}
        result = compare_results(baseline, candidate)
        self.assertFalse(result["passed"])
        self.assertEqual(result["regressed"], ["a"])
        self.assertEqual(result["missing"], ["b"])
        self.assertEqual(result["improved"], ["c"])
        self.assertEqual(result["added"], ["d"])

    def test_comparison_enforces_latency_threshold(self):
        baseline = {"cases": [{"id": "a", "passed": True, "latency_ms": 100}]}
        candidate = {"cases": [{"id": "a", "passed": True, "latency_ms": 130}]}
        result = compare_results(baseline, candidate, max_latency_increase_pct=20)
        self.assertEqual(result["latency_violations"], ["a"])
        self.assertFalse(result["passed"])

    def test_comparison_rejects_different_suites(self):
        with self.assertRaisesRegex(ValueError, "different suites"):
            compare_results({"suite": "a", "cases": []}, {"suite": "b", "cases": []})


class FakeHandler(BaseHTTPRequestHandler):
    attempts = 0
    authorization = ""

    def log_message(self, *args):
        pass

    def do_POST(self):
        type(self).attempts += 1
        type(self).authorization = self.headers.get("Authorization", "")
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        if type(self).attempts == 1:
            self.send_response(503)
            self.end_headers()
            return
        body = json.dumps({
            "model": payload["model"],
            "choices": [{"message": {"content": "provider response"}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        FakeHandler.attempts = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_compatible_provider_retries_and_records_usage(self):
        sleeps = []
        provider = OpenAICompatibleProvider(
            f"http://127.0.0.1:{self.server.server_port}/v1", "test-token", "test-model",
            max_retries=1, sleeper=sleeps.append,
        )
        case = CaseDefinition("id", "hello", {}, [], system="be concise")
        response = provider.complete(case)
        self.assertEqual(response.text, "provider response")
        self.assertEqual(response.input_tokens, 4)
        self.assertEqual(FakeHandler.attempts, 2)
        self.assertEqual(FakeHandler.authorization, "Bearer test-token")
        self.assertEqual(sleeps, [0.25])

    def test_environment_configuration_requires_all_values(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                OpenAICompatibleProvider.from_env()


class CliTests(unittest.TestCase):
    def test_validate_and_run_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "suite.json"
            path.write_text(json.dumps(suite()), encoding="utf-8")
            self.assertEqual(main(["validate", str(path)]), 0)
            self.assertEqual(main(["run", str(path)]), 0)

    def test_failed_gate_returns_two(self):
        data = suite('{"category":"wrong"}')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "suite.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(main(["run", str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
