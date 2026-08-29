# ToolSafe Agent Runtime

ToolSafe is a dependency-free Python runtime for AI systems that can call
application tools. It treats model output as untrusted input: every proposed call
must match an allowlisted tool, pass a strict argument schema, stay inside execution
limits, and satisfy any approval requirement before application code runs.

The included demo and full test suite use deterministic scripted model responses,
so the core behavior is reproducible without an API key. An OpenAI-compatible Chat
Completions adapter is included for deliberate live testing.

## What it demonstrates

- Explicit tool allowlisting and duplicate registration protection.
- JSON-schema-inspired validation for required fields, extra fields, types, enums,
  lengths, numeric ranges, arrays, and nested item types.
- Human approval callbacks for side-effecting tools; the safe default is denial.
- Bounded agent steps and tool calls to prevent unending model loops.
- Call-ID replay protection so repeated tool calls return a cached result.
- Containment of tool exceptions without exposing raw exception text to the model.
- Structured audit events with recursive token, secret, email, and phone redaction.
- Native OpenAI-compatible tool-call parsing, timeouts, and bounded retry for 429/5xx.
- Deterministic offline provider, CLI demo, Dockerfile, and CI validation.

ToolSafe does not make a tool safe by itself. The handler still needs authorization,
tenant isolation, transaction controls, least-privilege credentials, and business
validation. The runtime provides one enforceable boundary around model-proposed calls.

## Architecture

```text
user request
    |
Provider -> proposed tool call
    |          |
    |    allowlist + schema + limits + approval
    |          |
    |      ToolRegistry -> application handler
    |          |
    `--- tool result + redacted AuditSink
               |
           final answer
```

## Quick start

Python 3.10+ is the only local requirement:

```bash
make check
make demo
```

Expected demo behavior: `lookup_order` runs once for `ORD-100`, and the scripted
provider returns a grounded shipping answer. This demonstrates orchestration, not
live model reasoning or a real commerce integration.

## Register tools

```python
from toolsafe import AgentRuntime, ScriptedProvider, Tool, ToolRegistry

registry = ToolRegistry([Tool(
    name="lookup_order",
    description="Look up an order visible to the current user.",
    parameters={
        "type": "object",
        "properties": {"order_id": {"type": "string", "maxLength": 40}},
        "required": ["order_id"],
        "additionalProperties": False,
    },
    handler=lambda arguments: order_service.lookup(arguments["order_id"]),
)])
```

For any action with side effects, set `requires_approval=True` and supply a callback
that uses trusted application state. Approval is denied when no callback is supplied.

## Live provider

Copy `.env.example` values into your shell or secret manager, then construct:

```python
from toolsafe import OpenAICompatibleProvider

provider = OpenAICompatibleProvider.from_env()
```

The adapter sends native `tools` definitions to `/chat/completions`, parses the first
tool call, retries transient HTTP failures, and rejects malformed provider responses.
The adapter is tested against an in-process fake HTTP server. No paid endpoint was
called, so model quality, provider-specific compatibility, and token cost are not
claimed.

## Audit and privacy

`MemoryAuditSink` records tool decisions and results for demonstration. Replace it
with an append-only sink appropriate to your system. Redaction is defense in depth,
not a data-loss-prevention guarantee. Do not include credentials in tool arguments,
descriptions, prompts, or handler return values.

Audit event types include `tool_executed`, `tool_invalid`, `tool_denied`,
`tool_failed`, `tool_call_replayed`, `provider_error`, `protocol_error`,
`limit_reached`, and `completed`.

## Validation

```bash
python -m compileall -q src tests
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m toolsafe.cli run \
  --script examples/support-agent.json \
  --message "Where is order ORD-100?"
```

The tests execute valid and invalid calls, approval policy, replay protection,
exception containment, step and call limits, schema rules, recursive redaction, CLI
audit output, provider retry/authentication, final answers, and native tool-call parsing.

## Production checklist

- Authorize the current user and tenant again inside every handler.
- Separate read-only tools from financial, destructive, or communication actions.
- Require explicit approval for consequential actions and bind it to exact arguments.
- Use idempotency keys in the downstream system, not only the in-memory call cache.
- Persist audit events with access control, retention limits, and tamper evidence.
- Rate-limit requests and tool calls per user and tenant.
- Keep credentials in the handler environment and return the minimum necessary data.
- Add end-to-end tests against the exact model and provider used in production.

## Honest limitations

- The schema validator implements a documented practical subset, not full JSON Schema.
- Replay results live only for one `run`; distributed idempotency needs durable storage.
- Tools are synchronous. Long-running work should enqueue a job and return a job ID.
- The runtime executes one tool call at a time and uses the first provider tool call.
- It does not provide authentication, a web server, a database, a dashboard, or a
  human-approval user interface.
