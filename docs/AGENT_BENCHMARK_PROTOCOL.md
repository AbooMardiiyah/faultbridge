# Executable Agent Benchmark Protocol

## Evaluation Question

This benchmark measures whether FaultBridge turns a code-switched complaint into
the correct grounded action, rather than only whether an LLM produces fluent text.
Every run executes the configured complaint-analysis model, deterministic policy,
PostgreSQL tools, audit events, and final-state assertions.

## Frozen Panel

`benchmark/telco_scenarios.json` contains 48 synthetic telco scenarios, balanced
at 12 per language pair. Each language covers consent refusal, known-fault paths
with and without compensation, verified playbooks, confirmed resolution, first
escalation, a crowd-signal threshold, barred and empty-balance accounts, missing
account state, safe fallback, and PII redaction before model or tool access.

The panel SHA-256 is
`d1a3c1508706e374ae6670ffbedb8e516c4dee0a0ca6f2770c687d28f2ff48a9`.
All caller and operator records are synthetic. Each scenario also has a
`controlled_asr_error` variant that removes diacritics, punctuation, and selected
speech cues. This is a declared stress transform, not output from a named ASR.

## Assertions and Metrics

Each run grades structured symptom and language extraction, exact tool order,
response claims, database effects, candidate-incident status, and absence of
source PII throughout the observed trace. Critical privacy and unconfirmed-
incident gates are scored separately.

Run every gold and stressed scenario three times. Report pass@1, pass@3, pass^3,
assertion pass rate, critical failure rate, and stressed-text capability retention
relative to gold. Add provider-specific propagation variants only when their
hypotheses were generated from matching scenario audio.

## Reproduction

Create the isolated local database and validate every policy oracle without
contacting an LLM:

```bash
make benchmark-agent-prepare
make benchmark-eval-db
make benchmark-agent-validate
```

Configure either `OPENAI_API_KEY` or `GROQ_API_KEY`, then execute and score:

```bash
make benchmark-agent-run AGENT_PROVIDER=openai AGENT_MODEL=gpt-4.1-mini
make benchmark-agent-score
```

The runner appends completed scenario/variant/repetition records immediately and
resumes after interruption. It rejects a changed scenario hash, model, code
commit, or lockfile. `--overwrite` is required for a deliberately new run. Raw
traces remain ignored; the aggregate contains the result hash and provenance.

## Limits

Oracle validation proves that expected outcomes agree with the real policy and
database stack; it does not measure model quality. Final numbers remain empty
until a configured external model completes the runs. The controlled text stress
test does not replace end-to-end audio trials or black-box conversation testing.
