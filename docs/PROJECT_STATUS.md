# Project Status

Updated 10 September 2026. This file records durable working context for future
sessions; the Git history remains the authoritative implementation record.

## Completed

- Provider-neutral voice pipeline with Sahara streaming STT and TTS adapters.
- PostgreSQL persistence, migrations, verified incident/account/playbook inputs,
  PII redaction, pseudonymous callers, retention, and deletion.
- Three-tier orchestration: known-fault handling, guided diagnosis with outcome
  verification, and escalation with crowd-signal candidate incidents.
- Durable compensation and callback queues, workers, and operator webhooks.
- Industry-oriented ASR, robustness, privacy, routing, and agent evaluation tools.
- Responsive caller and operations interfaces using real protected API endpoints.
- Operations call inspector for redacted transcripts, grounded answers, and
  operator-readable timelines built from persisted tool events.

## External dependencies

- AfriSwitch access is pending. `HF_TOKEN` is configured locally, but preparation
  cannot begin until the dataset owner approves the account.
- AssemblyAI credentials are still needed for the required third-model benchmark.
- `SAHARA_VOICEBOT_WORKFLOW_ID` is needed only if the demo uses an outbound Sahara
  Conversation Call; the browser microphone flow does not require it.
- The submission portal access code and final YouTube upload remain user-owned.

## Active sequence

1. Test the caller and operations interfaces with live services when hardware is
   available.
2. Build the benchmark report renderer and five-minute demo/submission package.
3. On AfriSwitch approval, freeze the sample manifest, run three providers, score
   results, generate the three-page report, and derive routing recommendations.

Do not start Docker, PostgreSQL, the API, workers, or a frontend server in the
background until the user explicitly resumes live testing.
