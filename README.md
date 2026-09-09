# FaultBridge — Intron Submission

FaultBridge is a code-switched voice agent that resolves Nigerian telco fault calls
from verified network and account state. Unresolved complaints become evidence for
candidate network incidents, closing the gap between customer support and the NOC.

This repository is the Sahara-first entry for the Intron CodeSwitch Africa
Challenge. A separate AssemblyAI-first repository will be created after this
submission is complete.

## Current vertical slice

The domain engine implements the agentic loop independently of voice-provider keys:

1. accept consent and pseudonymize the caller;
2. persist only a redacted transcript;
3. look up an exact active fault for the caller's cell;
4. otherwise inspect account state and recommend a grounded diagnostic;
5. verify whether the action worked;
6. escalate unresolved calls with a structured handoff;
7. cluster distinct complaints and propose a candidate incident at the threshold.

Run it with Python 3.11+, Docker, and `uv`:

```bash
cp .env.example .env
make install
make db-up
make migrate
make test
make run
```

Then open `http://localhost:8000/docs`.

## Repository layout

- `src/faultbridge/domain/`: call state and deterministic orchestration policy.
- `src/faultbridge/services/`: PostgreSQL persistence and PII protection.
- `src/faultbridge/tools/`: typed, auditable telco actions.
- `src/faultbridge/adapters/`: Sahara and future voice-provider boundaries.
- `migrations/`: versioned PostgreSQL schema.
- `tests/`: policy, privacy, idempotency, and clustering tests.
- `docs/`: architecture and responsible-AI documentation.

## Data status

The runtime contains no committed subscriber, fault, account, or call records.
Authoritative incidents and account state enter through protected internal API
endpoints with source provenance and verification timestamps. Synthetic scenarios
exist only inside the test suite. The project does not commit caller audio, raw
provider outputs, credentials, phone numbers, or unredacted transcripts.

## Operational data boundary

`PUT /internal/network-incidents/{incident_id}` accepts verified fault updates from
a telco NOC, assurance platform, or authorized operations console.
`PUT /internal/accounts` accepts verified account state from a CRM or billing
adapter. Both endpoints require `X-Internal-API-Key`. Missing upstream data remains
unknown; the agent does not manufacture a fault, balance, or compensation status.

## Sahara adapter

`SaharaStreamingSTT` implements the official PCM16 WebSocket contract and maps all
four submission language pairs to Sahara language codes. It has not been exercised
against the live service because no API key is stored in this repository. Live
validation is the next integration checkpoint.
