# Architecture Decisions

This record explains the choices that shape the Intron submission.

## Sahara Is the Default Speech Path

Sahara is the sponsor platform and achieved the best aggregate WER in the frozen
four-model panel. Every ASR and TTS request sends an explicit language value.
An evidence-gated router exists, but multi-provider routing stays disabled because
no alternative met the paired accuracy, latency, and downstream safety gates for
all four language pairs.

## Models Sit Behind Interfaces

Speech recognition, text generation, speech synthesis, and telephony implement
separate protocols. The current stack uses Sahara and Together, while the domain
engine imports neither provider. A provider can be replaced without changing
fault policy, persistence, or tool permissions.

## The LLM Cannot Execute Tools Directly

The LLM converts a redacted transcript into a constrained complaint schema.
Deterministic code owns consent, state transitions, tool access, compensation,
callback scheduling, clustering thresholds, and terminal outcomes. This keeps a
model wording error from becoming an unauthorized operational action.

## PostgreSQL Stores Operational Truth

PostgreSQL was selected over SQLite because the product needs concurrent API and
worker access, durable command queues, row locking, JSON audit events, and
idempotency constraints. The same schema supports local Docker and Railway.

## Verified Faults Use Exact Queries

An outage answer requires an active, verified record for the exact cell. Vector
search and Qdrant were excluded from this decision path because semantic
similarity is not proof of a network fault. Approved troubleshooting playbooks
also use versioned relational records with provenance. Semantic retrieval can be
added later for discovery, but it cannot promote a suggestion into a fact.

## Resolution Has Three Controlled Tiers

A known fault produces a grounded answer and eligible queued actions. An unknown
fault uses account state and an approved playbook, then asks the caller to verify
the result. A failed verification creates a safe handoff and complaint signal.
Three distinct callers can propose an unconfirmed incident for NOC review.

## Privacy Precedes External Reasoning

Consent is checked before speech or model processing. Caller identifiers are
pseudonymized, and transcripts are redacted before the LLM, database, logs, tools,
or UI. Raw audio is processed in memory and is not retained.

## The Demo Uses Production Boundaries

`make demo-seed` sends labelled synthetic NOC and CRM records through the
authenticated ingestion API. The browser then makes a real Sahara STT request,
runs the real LLM, policy engine, PostgreSQL tools, and Sahara TTS. No response
fixture or mocked tool result appears in the recorded flow.
