# Shaiq AI + Flutter Lab

Production-minded reference projects for AI systems, workflow automation, and
Flutter applications. Each project is self-contained, documented, and includes
repeatable validation instead of relying on screenshots or unverified claims.

## Projects

| Project | Category | What it demonstrates |
| --- | --- | --- |
| [CiteGuard RAG API](projects/citeguard-rag-api) | AI / backend | Grounded retrieval, citations, abstention, PII redaction, injection defence, optional LLM generation, and a dependency-free HTTP API |
| [SLA Sentinel](projects/n8n-sla-sentinel) | n8n automation | Validated support intake, deterministic priority scoring, PII-safe summaries, SLA calculation, native routing, and reproducible workflow tests |
| [Resilient Feature Kit](projects/flutter-resilient-feature-kit) | Flutter package | Stale-while-revalidate caching, bounded retries, request coalescing, optimistic updates, lifecycle safety, and reusable state widgets |
| [Prompt Regression Lab](projects/prompt-regression-lab) | AI evaluation | Fixture-backed prompt tests, OpenAI-compatible replay, deterministic assertions, redacted reports, baseline comparison, and CI release gates |
| [Lead Router](projects/n8n-lead-router) | n8n automation | Validated B2B intake, consent enforcement, explainable ICP scoring, stable ownership, privacy-aware responses, and tested route generation |
| [Flutter Auth Session Kit](projects/flutter-auth-session-kit) | Flutter package | Session restore, single-flight refresh, logout race protection, typed failures, authorized-call retry, and pluggable secure storage/backend boundaries |

## Engineering principles

- Secrets stay in environment variables and `.env.example` files.
- Core behaviour works locally without paid services.
- External integrations are clearly separated from verified offline behaviour.
- Tests cover retrieval, safety, grounding, and API contracts.

## Licence

MIT
