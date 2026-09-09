# Responsible AI Note

FaultBridge processes voice complaints only after a clear recording and automated
processing disclosure. If consent is declined, automated processing stops and the
caller is offered a human handoff path.

The application pseudonymizes caller identifiers before storage and redacts phone
numbers, email addresses, account identifiers, and long numeric identifiers before
transcripts reach an external language model, logs, tool traces, escalation
summaries, or benchmark artifacts. Raw audio is handled in memory and is not
persisted. Redacted call sessions use configurable retention, and an authenticated
deletion operation removes caller-linked records.

Network faults are confirmed only from authoritative structured records. Complaint
clusters create **unconfirmed candidate incidents** for NOC review; they are never
presented as verified outages. Distinct-caller thresholds reduce duplicate and
coordinated reports. Compensation requests are policy-gated and written as durable,
idempotent commands; the agent reports them as queued until a billing connector
confirms completion.

Benchmark results are reported separately by language pair, model, natural or
synthetic source, and noise condition. Synthetic speech is disclosed. Known
limitations, spelling variation, sample counts, and failure cases are reported so
aggregate accuracy does not hide unequal performance.
