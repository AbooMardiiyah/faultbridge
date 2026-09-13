# FaultBridge — Intron Submission

FaultBridge is a code-switched voice agent that resolves Nigerian telco fault calls
from verified network and account state. Unresolved complaints become evidence for
candidate network incidents, closing the gap between customer support and the NOC.

This repository is the Sahara-first entry for the Intron CodeSwitch Africa
Challenge. A separate AssemblyAI-first repository will be created after this
submission is complete.

## Implemented System

FaultBridge composes a provider-independent voice pipeline around a constrained
agentic loop:

1. transcribe PCM16 audio through the selected STT adapter;
2. redact PII before structured LLM analysis;
3. accept consent and pseudonymize the caller;
4. look up an exact active fault for the caller's cell;
5. otherwise inspect account state and retrieve an approved diagnostic playbook;
6. synthesize the grounded response through the selected TTS adapter;
7. verify the outcome, escalate unresolved calls, and cluster distinct complaints;
8. queue callbacks and compensation for idempotent operator delivery.

Run it with Python 3.11+, Docker, and `uv`:

```bash
cp .env.example .env
make install
make db-up
make migrate
make test
make run
```

To run the packaged API, migrations, and PostgreSQL entirely through Docker:

```bash
make docker-up       # build and wait for the API and database to become healthy
make docker-status   # show container health and published ports
make docker-logs     # follow API and database logs
make docker-down     # stop the complete stack
```

The web interfaces are served by the API container, so no separate frontend
process is required. Docker publishes them at `http://localhost:8010/`; `make run`
uses port `8000`. Start delivery workers only after configuring operator webhooks
with `make docker-workers`. Live provider endpoints remain unavailable until their
credentials are present; the rest of the service starts without them.

## Repository layout

- `src/faultbridge/domain/`: call state and deterministic orchestration policy.
- `src/faultbridge/services/`: PostgreSQL persistence and PII protection.
- `src/faultbridge/tools/`: typed, auditable telco actions.
- `src/faultbridge/adapters/`: Sahara and future voice-provider boundaries.
- `migrations/`: versioned PostgreSQL schema.
- `tests/`: policy, privacy, idempotency, and clustering tests.
- `eval/`: frozen-manifest ASR scoring and executable agent-state evaluation.
- `docs/`: architecture and responsible-AI documentation.
- `src/faultbridge/static/`: responsive caller and operations interfaces.

## Data status

The runtime contains no committed subscriber, fault, account, or call records.
Authoritative incidents and account state enter through protected internal API
endpoints with source provenance and verification timestamps. Clearly labelled,
synthetic scenarios are committed under `benchmark/` for reproducible evaluation.
The project does not commit real caller audio, raw provider outputs, credentials,
real phone numbers, or unredacted production transcripts.

## Operational data boundary

`PUT /internal/network-incidents/{incident_id}` accepts verified fault updates from
a telco NOC, assurance platform, or authorized operations console.
`PUT /internal/accounts` accepts verified account state from a CRM or billing
adapter. Both endpoints require `X-Internal-API-Key`. Missing upstream data remains
unknown; the agent does not manufacture a fault, balance, or compensation status.

## Sahara adapter

`SaharaStreamingSTT` and `SaharaStreamingTTS` implement the official WebSocket
contracts. `SaharaSynchronousTTS` supplies the resumable benchmark transport, and
`SaharaConversationCall` starts active outbound conversation workflows. Every
speech request sends an explicit language selection. The browser maps Pidgin to
`pcm`, Hausa to `ha`, Igbo to `ig`, and Yoruba to `yo`; missing language metadata
is rejected before a provider call.

See [Operations](docs/OPERATIONS.md) for provider selection, deployment, action
delivery, privacy controls, and health checks. The
[experience design guide](docs/EXPERIENCE_DESIGN.md) records the UI rationale and
manual review checklist. The
[voice benchmark research](docs/VOICE_BENCHMARK_RESEARCH.md) defines the
industry-grounded evaluation protocol. The dedicated
[TTS benchmark protocol](docs/TTS_BENCHMARK_PROTOCOL.md) defines hallucination,
transcript loss, segment loss, accuracy, and the native-listener audit;
the [completed automatic TTS report](docs/TTS_BENCHMARK_REPORT.md) records the
200-output, three-judge results; the [privacy report](docs/PRIVACY_BENCHMARK_REPORT.md)
records the deterministic PII scorecard; the
[agent benchmark protocol](docs/AGENT_BENCHMARK_PROTOCOL.md) defines the 48
executable scenarios and 24-utterance named-ASR propagation panel; and
[`eval/README.md`](eval/README.md) contains the reproducible commands.
