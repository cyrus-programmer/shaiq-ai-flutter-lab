# SLA Sentinel for n8n

SLA Sentinel is an importable support-intake workflow that turns an untrusted
webhook payload into a validated, privacy-conscious triage decision. It assigns
a deterministic severity, response deadline, recommended queue, and escalation
action, then returns a machine-readable acknowledgement to the caller.

It uses only n8n core nodes and requires no vendor credentials. The scoring
logic is intentionally deterministic so teams can audit why a ticket was
routed instead of trusting an opaque model classification.

## What it does

```text
POST /webhook/support-intake
  -> normalize and validate
  -> reject invalid payloads with HTTP 400
  -> redact email addresses, phone numbers, and card-like values from message
  -> score impact, topic, sentiment, customer tier, and affected users
  -> calculate an acknowledgement SLA
  -> route urgent tickets to on-call and others to support queues
  -> return HTTP 202 with reasons and safe preview
```

Urgent routing means `critical` or `high` severity. This reference workflow
returns a recommended action (`page_on_call` or `queue_for_support`); it does
not claim to send Slack, PagerDuty, email, or CRM updates. Those provider nodes
can be added after credentials and delivery requirements are known.

## Payload contract

Required:

```json
{
  "ticket_id": "T-1042",
  "subject": "Production checkout unavailable",
  "message": "Every payment attempt is failing for 300 customers"
}
```

Optional fields:

```json
{
  "customer_email": "owner@example.com",
  "customer_tier": "enterprise",
  "affected_users": 300,
  "channel": "api",
  "occurred_at": "2026-08-24T02:00:00.000Z"
}
```

Limits are enforced before triage: ticket IDs 1 to 100 characters, subjects 3
to 200 characters, messages 10 to 5,000 characters, valid email syntax, and an
integer `affected_users` from 0 to 1,000,000.

Example accepted response:

```json
{
  "accepted": true,
  "ticket_id": "T-1042",
  "severity": "critical",
  "score": 100,
  "route": "on_call",
  "action": "page_on_call",
  "sla_minutes": 15,
  "acknowledge_by": "2026-08-24T02:15:00.000Z",
  "reasons": ["service outage", "payment impact", "enterprise customer", "300 users affected"],
  "safe_preview": "Every payment attempt is failing for 300 customers"
}
```

## Run locally

The supplied Compose file pins the n8n `2.35.7` stable image released on
August 21, 2026. Docker was not available in the validation environment, so
container startup is documented but not claimed as executed.

```bash
cp .env.example .env
# Set a unique N8N_ENCRYPTION_KEY in .env
docker compose up -d
```

Open `http://localhost:5678`, create the owner account, then import
`workflows/sla-sentinel.json`. Publish the workflow and copy its production
Webhook URL from the Webhook node.

Test it:

```bash
curl -i -X POST http://localhost:5678/webhook/support-intake \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"T-1042","subject":"Checkout is down","message":"All customer payments are failing","customer_tier":"enterprise","affected_users":300}'
```

For an internet-facing deployment, terminate TLS at a trusted reverse proxy,
set the public `WEBHOOK_URL`, restrict inbound traffic, and add Webhook Header
Auth or JWT Auth credentials in n8n before publishing.

## Development and validation

Workflow Code node bodies live in `src/nodes/`. The builder embeds them into
the importable JSON, which prevents the tested logic and workflow copy from
drifting.

```bash
npm run build          # regenerate workflow JSON
npm test               # assert generated file + run all tests
```

The test harness uses Node's built-in runner and VM module, so there are no npm
dependencies to install. It executes the actual Code node source with n8n-like
inputs and validates:

- required field rejection and size limits;
- critical, high, medium, and low scoring fixtures;
- SLA deadlines and queue routing;
- privacy redaction;
- workflow node IDs, connections, response paths, and absence of credentials;
- exact agreement between source nodes and generated workflow JSON.

## Customisation

Edit keyword weights and SLA thresholds in `src/nodes/triage.js`, run
`npm run build`, then re-import the generated workflow. Provider delivery nodes
should be added after the `Prepare Urgent Response` or `Prepare Standard
Response` nodes. Keep the Respond to Webhook node on every exclusive path.

## Honest limitations

- The workflow JSON and all embedded business logic were statically validated
  and executed in a local harness, but the workflow was not imported into a
  running n8n instance because Docker/n8n was unavailable here.
- Scoring is English keyword-based. It is auditable but not semantic,
  multilingual, or a substitute for human incident review.
- It recommends delivery actions but performs no third-party notification.
- n8n execution records may contain the original webhook input. Retention is
  limited in the sample configuration, but regulated deployments need a formal
  data-handling policy and may need input removal after processing.
- The local Compose setup uses n8n's default SQLite storage. Multi-worker
  production deployments should use n8n's documented PostgreSQL and queue-mode
  architecture.

## References

- [n8n Webhook node documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [n8n environment-variable deployment guide](https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/deployment/)
- [n8n privacy and execution-pruning guidance](https://docs.n8n.io/privacy-and-security/what-you-can-do/)
- [n8n 2.35.7 release](https://github.com/n8n-io/n8n/releases/tag/n8n%402.35.7)
