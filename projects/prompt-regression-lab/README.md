# Prompt Regression Lab

Prompt Regression Lab is a dependency-free evaluation runner for teams that
change prompts, model parameters, or providers and need a repeatable release
decision. It runs JSON test suites, evaluates every response with deterministic
assertions, emits machine-readable and human-readable reports, and compares a
candidate run with a checked-in baseline.

The included sample uses a replay fixture, so the complete pipeline works in CI
without an API key or network call. An OpenAI-compatible Chat Completions
adapter is included for deliberate live evaluation.

## Why this is useful

Manually trying a few prompts does not answer whether a change broke an older
case. Prompt Regression Lab treats AI behaviour like a versioned contract:

- strict prompt variables fail before a provider call;
- case IDs and fixture responses are deterministic;
- exact, contains, forbidden-text, regex, and JSON-path assertions are built in;
- provider failures become case failures instead of aborting the entire suite;
- captured prompts and outputs are redacted for common secrets and PII;
- JSON, Markdown, and JUnit XML reports support CI and review;
- baseline comparison detects pass-to-fail regressions and latency increases;
- exit codes make the result usable as a release gate.

This project does not use an LLM to grade another LLM. Deterministic evaluators
are less flexible but keep the demonstrated results auditable and reproducible.

## Quick start

Python 3.10+ is the only requirement:

```bash
cd projects/prompt-regression-lab
make check
make demo
```

Run a suite directly:

```bash
PYTHONPATH=src python -m promptlab.cli run examples/support-triage.json \
  --output reports/candidate.json \
  --markdown reports/candidate.md \
  --junit reports/junit.xml
```

Compare with a baseline and fail if any previously passing case regresses:

```bash
PYTHONPATH=src python -m promptlab.cli compare \
  examples/baseline.json reports/candidate.json \
  --max-regressions 0 \
  --max-latency-increase-pct 25
```

Exit codes are `0` for a passing gate, `1` for invalid configuration or runtime
errors, and `2` for completed evaluations or comparisons that fail their gate.

## Suite format

```json
{
  "name": "support-triage-contract",
  "provider": {
    "type": "fixture",
    "responses": {
      "refund": "{\"category\":\"billing\",\"priority\":\"normal\"}"
    }
  },
  "defaults": {
    "system": "Return compact JSON only.",
    "temperature": 0
  },
  "cases": [
    {
      "id": "refund",
      "prompt": "Classify: {message}",
      "variables": {"message": "Where is my refund?"},
      "expectations": [
        {"type": "json_path", "path": "category", "equals": "billing"},
        {"type": "not_contains", "value": "password", "case_sensitive": false}
      ]
    }
  ]
}
```

Supported expectations:

| Type | Required fields | Behaviour |
| --- | --- | --- |
| `exact` | `value` | Entire stripped output must match |
| `contains` | `value` | Output must contain text |
| `not_contains` | `value` | Output must not contain text |
| `regex` | `pattern` | Python regular expression must match |
| `json_path` | `path`, optional `equals` or `value_type` | Parse JSON and inspect a dotted path or list index |

`case_sensitive` defaults to `true` for text evaluators. JSON-path `value_type`
accepts `string`, `number`, `integer`, `boolean`, `object`, `array`, or `null`.

## Live OpenAI-compatible provider

Change the suite provider to:

```json
{"type": "openai_compatible"}
```

Then export the values from `.env.example` through your shell or secret
manager. The adapter calls `/chat/completions`, uses a bounded timeout, retries
HTTP 429 and 5xx responses with exponential backoff, and records provider token
usage when returned.

The adapter contract and retry behaviour are tested against an in-process fake
HTTP server. No real model endpoint or paid request was used, so this repository
does not claim model quality, token cost, or production-provider compatibility
beyond the documented request shape.

## Reports and privacy

By default, report prompts and outputs redact:

- email addresses and phone-like values;
- common API-key and bearer-token patterns;
- values supplied through `PROMPTLAB_REDACT_VALUES`, separated by commas.

Assertions run against the original response before report redaction. Redaction
is a safety convenience, not a complete data-loss-prevention system. Avoid
putting regulated data into evaluation fixtures or prompts.

## Baseline workflow

1. Run the existing prompt against the intended evaluation environment.
2. Review the report and commit the approved JSON as a baseline.
3. Run the candidate prompt or model using the same case IDs.
4. Compare candidate versus baseline in CI.
5. Investigate regressions before intentionally replacing the baseline.

The comparator reports added, missing, improved, regressed, and unchanged
cases. A missing previously passing case counts as a regression.

## Project layout

```text
src/promptlab/
  cli.py          command-line interface and exit codes
  evaluators.py   deterministic output assertions
  models.py       suite and result contracts
  providers.py    fixture and OpenAI-compatible adapters
  redaction.py    report-time secret and PII masking
  reports.py      JSON, Markdown, and JUnit output
  runner.py       bounded concurrent execution
  suite.py        strict suite parsing and prompt rendering
tests/            unit, integration, CLI, and fake-provider tests
examples/         offline suite and approved baseline
```

## Honest limitations

- Deterministic assertions cannot measure tone, nuanced correctness, or semantic
  similarity unless those requirements can be expressed as explicit contracts.
- Latency from fixture runs is synthetic and should not be compared with live
  provider latency. The sample baseline therefore omits a latency gate.
- Live model outputs are inherently variable even at temperature zero. Use
  multiple repetitions or statistical evaluators for high-stakes model changes.
- The runner stores reports on the local filesystem and has no dashboard,
  database, distributed queue, authentication, or hosted service.
- Token pricing changes over time, so cost is not guessed. Raw provider usage is
  recorded for the caller to price using an approved current rate card.
