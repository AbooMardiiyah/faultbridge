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
`9f3f0cdc554c5dc961ae6d8b14338ec0568827065a67b39c72d18be050987aad`.
All caller and operator records are synthetic. Each scenario also has a
`controlled_asr_error` variant that removes diacritics, punctuation, and selected
speech cues. This is a declared stress transform, not output from a named ASR.

## Named-ASR Downstream Panel

The secondary panel freezes 24 distinct telco utterances, six per language pair.
It covers consent refusal, a verified fault, guided diagnosis, crowd-signal
discovery, missing account state, and PII removal. Sahara TTS produces one female
voice rendition per prompt. The same files then pass through Sahara, SBPN,
Faster-Whisper, and OmniASR before their actual hypotheses enter the agent runner.

This controlled synthetic-speech test complements the 400-clip natural-speech
ASR benchmark. Sahara TTS may favor Sahara ASR, so reports must disclose that
source-model limitation. Source text and generated audio carry SHA-256 provenance.
Failed or empty ASR outputs remain empty agent inputs.

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

Build the named-ASR panel in resumable batches. Generation uses 24 paid TTS
requests and the Sahara pass uses 24 paid ASR requests; local models add no API
cost:

```bash
make benchmark-agent-audio-prepare
make benchmark-agent-audio-generate AGENT_AUDIO_BATCH_SIZE=6
make benchmark-agent-audio-asr-sahara AGENT_AUDIO_BATCH_SIZE=6
make benchmark-agent-audio-asr-faster-whisper
make benchmark-agent-audio-asr-sbpn
make benchmark-agent-audio-asr-omni
make benchmark-agent-audio-attach
make benchmark-agent-audio-run AGENT_PROVIDER=openai AGENT_MODEL=gpt-4.1-mini
make benchmark-agent-audio-score
```

The agent summary reports overall and per-language pass rates, propagation loss,
capability retention, assertion accuracy, and critical failure rate per named ASR.

The runner appends completed scenario/variant/repetition records immediately and
resumes after interruption. It rejects a changed scenario hash, model, code
commit, or lockfile. `--overwrite` is required for a deliberately new run. Raw
traces remain ignored; the aggregate contains the result hash and provenance.

## Limits

Oracle validation proves that expected outcomes agree with the real policy and
database stack; it does not measure model quality. Final numbers remain empty
until a configured external model completes the runs. The controlled text stress
test does not replace the named-ASR panel, human-speech trials, or black-box
conversation testing.
