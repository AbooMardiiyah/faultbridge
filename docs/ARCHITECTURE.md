# Architecture

FaultBridge composes sponsor-specific voice providers around a shared telco domain
engine. Sahara supplies speech input and output by default in this repository. The
domain engine receives a redacted transcript plus verified call metadata and
returns a response, tool events, and an explicit terminal state.

```mermaid
flowchart LR
    A[Caller audio] --> B[Sahara voice adapter]
    B --> C[PII redaction]
    C --> L[Structured LLM analysis]
    L --> D[Constrained orchestrator]
    D --> E[Fault and account tools]
    D --> F[Diagnostic policy]
    D --> G[Ticket and callback tools]
    G --> H[Complaint signal store]
    H --> I[Candidate incident]
    E --> J[Auditable event ledger]
    F --> J
    G --> J
    D --> K[Sahara speech response]
```

The composition root selects four protocols: `SpeechToText`, `AgentModel`,
`TextToSpeech`, and `TelephonyTransport`. Provider adapters cannot access the
database or invoke telco actions. The LLM extracts a constrained symptom and
language pair; only the orchestrator can execute typed tools.

Authoritative operational facts use exact PostgreSQL queries. Approximate semantic
retrieval is not used to confirm an outage. Approved PostgreSQL playbooks supply
diagnostic instructions. Exact filters select a verified version, and every
customer-facing fact and state-changing action remains grounded in a typed tool
result.

The LLM extracts symptoms and language hints within a fixed schema. The
orchestrator enforces consent, required fields, valid state transitions,
idempotency, clustering thresholds, and terminal outcomes.

NOC and CRM systems publish verified state through authenticated internal API
boundaries. Every record carries a source system, source reference, and verification
time. Compensation and callbacks use durable, idempotent command tables so external
workers can execute them without losing work or duplicating actions.
