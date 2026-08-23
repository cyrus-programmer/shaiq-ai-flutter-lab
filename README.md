# Shaiq AI + Flutter Lab

Production-minded reference projects for AI systems, workflow automation, and
Flutter applications. Each project is self-contained, documented, and includes
repeatable validation instead of relying on screenshots or unverified claims.

## Projects

| Project | Category | What it demonstrates |
| --- | --- | --- |
| [CiteGuard RAG API](projects/citeguard-rag-api) | AI / backend | Grounded retrieval, citations, abstention, PII redaction, injection defence, optional LLM generation, and a dependency-free HTTP API |

## Engineering principles

- Secrets stay in environment variables and `.env.example` files.
- Core behaviour works locally without paid services.
- External integrations are clearly separated from verified offline behaviour.
- Tests cover retrieval, safety, grounding, and API contracts.

## Licence

MIT
