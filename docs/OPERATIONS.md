# FaultBridge Operations

## Runtime Topology

The API, worker, and PostgreSQL run as separate processes. The API handles voice
turns and authoritative data ingestion. The worker claims queued actions with
`FOR UPDATE SKIP LOCKED` and sends idempotent requests to operator-owned webhooks.
PostgreSQL retains redacted call state, audit events, approved playbooks, tickets,
and unconfirmed candidate incidents.

Start the local stack with:

```bash
cp .env.example .env
make db-up
make migrate
make run
```

Run `make docker-up` to build the packaged API, apply migrations, start PostgreSQL,
and wait for both containers to become healthy. The caller and operations UIs are
served by the API container. Override `FAULTBRIDGE_PORT` or
`FAULTBRIDGE_DB_PORT` if either host port is occupied. Use `make docker-workers`
only after configuring operator webhook URLs and a token.

As of 14 September 2026 at 08:00 WAT, Intron requires an explicit language on
every ASR and TTS request. FaultBridge maps the selected language pair to Sahara's
required `use_language_asr_input` and `voice_language` parameters; requests to the
voice endpoints must also supply `voice_language` and `voice_accent` explicitly.

## Provider Selection

`STT_PROVIDER`, `TTS_PROVIDER`, and `AGENT_PROVIDER` select implementations at
composition time. The Intron submission uses `sahara`, `sahara`, and either
`openai` or `groq`. The domain engine, telco tools, and database do not import a
speech or language-model provider.

Raw-audio endpoints accept mono, little-endian PCM16 and return one base64 WAV item
per Sahara text chunk. Clients play those items sequentially.

## Authoritative Data

Incidents, accounts, and playbooks enter only through `/internal/*` endpoints
authenticated with `X-Internal-API-Key`. Incidents and approved playbooks require a
source system, upstream reference, and verification time. Missing data remains
unknown.

## Action Delivery

Compensation and callback requests begin in `queued` state. Configure
`COMPENSATION_WEBHOOK_URL`, `CALLBACK_WEBHOOK_URL`, and
`OPERATOR_WEBHOOK_TOKEN`, then run `make worker`. Each outbound request carries the
command UUID as `Idempotency-Key`. Provider errors are recorded and retried; a
command becomes completed only after a successful response.

## Privacy and Retention

PII is removed before transcripts cross the language-model boundary or enter
PostgreSQL. Run `make purge` daily to apply `TRANSCRIPT_RETENTION_DAYS`. The
authenticated `DELETE /internal/caller-data` endpoint removes sessions, tool
events, tickets, account state, and queued actions for a caller-derived pseudonym
while retaining anonymous aggregate incidents.

## Health and Review

Use `/health/live` for process health and `/health/ready` for database readiness.
The caller voice interface is available at `/`. The operations dashboard is
available at `/operations`; its data requests require the
internal API key, which remains in browser session storage.
