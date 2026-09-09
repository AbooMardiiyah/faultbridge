# FaultBridge — Intron Submission

FaultBridge is a code-switched voice agent that resolves Nigerian telco fault calls
from verified network and account state. Unresolved complaints become evidence for
candidate network incidents, closing the gap between customer support and the NOC.

This repository is the Sahara-first entry for the Intron CodeSwitch Africa
Challenge. A separate AssemblyAI-first repository will be created after this
submission is complete.

## Current vertical slice

The initial domain engine demonstrates the agentic loop without external API keys:

1. accept consent and pseudonymize the caller;
2. persist only a redacted transcript;
3. look up an exact active fault for the caller's cell;
4. otherwise inspect account state and recommend a grounded diagnostic;
5. verify whether the action worked;
6. escalate unresolved calls with a structured handoff;
7. cluster distinct complaints and propose a candidate incident at the threshold.

Run it with Python 3.11+:

```bash
make test
make demo
```

To run the API:

```bash
uv sync
make run
```

Then open `http://localhost:8000/docs`.

## Repository layout

- `src/faultbridge/domain/`: call state and deterministic orchestration policy.
- `src/faultbridge/services/`: SQLite persistence and PII protection.
- `src/faultbridge/tools/`: typed, auditable telco actions.
- `src/faultbridge/adapters/`: Sahara and future voice-provider boundaries.
- `data/`: clearly synthetic demo fixtures.
- `tests/`: policy, privacy, idempotency, and clustering tests.
- `docs/`: architecture and responsible-AI documentation.

## Data status

All committed subscribers, faults, accounts, and calls are synthetic. The project
does not commit caller audio, raw provider outputs, API credentials, phone numbers,
or unredacted transcripts.

