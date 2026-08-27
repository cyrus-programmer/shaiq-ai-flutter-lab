# Lead Router for n8n

An importable, deterministic B2B lead-intake workflow for teams that need useful
qualification before adding CRM credentials. It validates untrusted webhook
payloads, enforces explicit contact consent, scores ICP fit, assigns qualified
leads consistently, and returns privacy-aware handoff data.

## What is actually implemented

- Strict validation for email, company, company size, budget, timestamp, and
  pain-point detail.
- Configurable target industries, countries, and sales owners through environment
  variables.
- Explainable 0–100 scoring with recorded point-by-point reasons.
- Three outcomes: `sales` (70+), `nurture` (40–69), and `rejected`.
- Consent override: a lead without contact consent cannot enter either follow-up
  route, regardless of score.
- Deterministic owner selection based on company name, avoiding random reassignment
  when a request is replayed.
- Masked email addresses in webhook responses.
- Source-controlled Code nodes and a builder that generates the importable n8n
  workflow, preventing visual-workflow drift.

The project deliberately does **not** claim CRM writes, enrichment, email delivery,
or AI-based intent detection. The output branches are clean extension points for
HubSpot, Salesforce, Airtable, Slack, or an approved email provider.

## Flow

```text
POST /lead-router
      |
normalize + validate
      | invalid ----------------------------> 422
      v
explainable ICP score
      | sales (>=70) -> stable owner --------> 200
      | nurture (40-69) ---------------------> 202
      ` rejected / no consent --------------> 422
```

## Run locally

Requirements: Node.js 20+ for validation; Docker for the optional n8n runtime.

```bash
npm test
cp .env.example .env
# Replace N8N_ENCRYPTION_KEY before continuing.
docker compose up -d
```

Open `http://localhost:5678`, import
`workflows/lead-router.json`, review the policy variables, and activate the
workflow. n8n will display the final test and production webhook URLs.

Send the included example after replacing `<webhook-url>`:

```bash
curl -sS -X POST '<webhook-url>' \
  -H 'content-type: application/json' \
  --data @samples/high-fit.json
```

Expected route for the default policy: `sales`, score `100`, with a masked email
and one configured owner. Owner selection can differ if `SALES_OWNERS` changes.

## Policy configuration

| Variable | Purpose | Example |
| --- | --- | --- |
| `TARGET_INDUSTRIES` | Comma-separated ICP industries | `healthcare,saas` |
| `TARGET_COUNTRIES` | Comma-separated ISO alpha-2 countries | `US,CA,GB` |
| `SALES_OWNERS` | Comma-separated owner identifiers | `alex@example.com,sam@example.com` |

Changing thresholds requires editing `src/nodes/score.js`, rebuilding, and running
the tests:

```bash
npm run build
npm test
```

## Validation and production notes

The test suite executes every Code node in a VM, covers validation and each route,
checks email masking and consent behavior, confirms stable owner assignment, and
verifies that the generated 12-node workflow embeds the source files exactly.

Before exposing this publicly, add edge authentication or gateway rate limiting,
persist an idempotency key in a database/CRM, configure n8n execution-data
retention, and complete a data-processing review. The sample uses no secrets and
stores no lead data outside normal n8n execution history.
