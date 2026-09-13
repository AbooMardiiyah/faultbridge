# FaultBridge Executable Voice-Agent Benchmark

## Full Capability Panel

The primary agent panel completed 288/288 strict passes over 48 scenarios, two
input variants, and three repetitions. Gold transcripts and controlled ASR-stress
texts both achieved 100% pass@1, pass@3, pass³, assertion accuracy, and voice
capability retention, with 0% critical safety failures. Together Llama 3.3 70B
structured-analysis latency was 1.20 seconds p50 and 2.25 seconds p95 for gold,
and 1.24 seconds p50 and 2.06 seconds p95 for stressed text.

The 48 scenarios contain 12 capabilities per language pair: consent refusal,
known faults with and without compensation, guided diagnosis, confirmed
resolution, first escalation, crowd-signal thresholds, barred and empty-balance
accounts, missing account state, safe fallback, and PII handling. The controlled
variant removes diacritics, punctuation, and selected speech cues. It is a stable
stress transform, not the output of a named ASR.

## Named-ASR Downstream Result

FaultBridge completed 360 executable runs over 24 synthetic telco scenarios:
four language pairs, five transcript variants, and three repetitions. Each run
used Together-hosted `meta-llama/Llama-3.3-70B-Instruct-Turbo`, the real
deterministic policy, PostgreSQL tools, audit events, and final database-state
checks.

| Transcript | Strict task success | Assertion pass rate | Critical failure rate | LLM p50 / p95 |
|---|---:|---:|---:|---:|
| Gold | 100.0% | 100.0% | 0.0% | 1.12 / 2.09 s |
| Sahara ASR | 100.0% | 100.0% | 0.0% | 1.09 / 1.96 s |
| SBPN | 95.8% | 99.2% | 0.0% | 1.08 / 1.74 s |
| OmniASR | 87.5% | 98.4% | 0.0% | 1.18 / 1.87 s |
| Faster-Whisper Turbo | 79.2% | 97.6% | 0.0% | 1.14 / 1.92 s |

Sahara retained 100% of the gold-transcript capability on this controlled panel.
SBPN retained 95.8%, OmniASR 87.5%, and Faster-Whisper 79.2%. All scenario and
provider cells were stable across the three repetitions: pass@1, pass@3, and
pass³ were identical.

## Language Results

Strict task success by language pair was:

| Language pair | Sahara | SBPN | OmniASR | Faster-Whisper |
|---|---:|---:|---:|---:|
| Hausa-English | 100.0% | 100.0% | 100.0% | 50.0% |
| Igbo-English | 100.0% | 100.0% | 83.3% | 83.3% |
| Pidgin-English | 100.0% | 100.0% | 83.3% | 100.0% |
| Yoruba-English | 100.0% | 83.3% | 83.3% | 83.3% |

The 27 failed runs belong to nine scenario/provider cells. In every case, the ASR
hypothesis lost a complaint symptom or language cue, changing diagnosis or
playbook selection. No run leaked declared PII, asserted an unconfirmed incident
as fact, or failed another critical safety gate.

## Method

The panel contains six distinct utterances per language: consent refusal, known
fault handling, guided diagnosis, crowd-threshold discovery, missing account
state, and PII removal. Sahara TTS generated one female-voice WAV per prompt.
Sahara, SBPN, OmniASR, and Faster-Whisper transcribed the same 24 files. Each real
hypothesis and the gold prompt then entered the agent three times.

Strict success requires every expected analysis value, exact tool trace, response
claim, database effect, and privacy check to pass. Failed and empty hypotheses
remain in the denominator. LLM latency measures structured complaint analysis
only; it excludes speech and database time.

## Interpretation and Limits

This panel tests error propagation, not general ASR accuracy. Sahara synthesized
the speech, so the 100% Sahara ASR result may reflect same-provider affinity. The
separate 400-clip natural AfriSwitch benchmark counters that limitation and remains
the primary ASR comparison. The audio uses one synthetic female voice and should
not be generalized to male voices, natural speakers, telephone networks, or new
fault domains.

Raw audio, hypotheses, traces, hashes, model versions, code commits, and dependency
lock are preserved in the private evidence archive. After extracting it at the
repository root, `make benchmark-verify-agent-evidence` verifies every file and
WAV hash, reruns `faultbridge-agent-scorer-v1` over both panels, and byte-compares
the four regenerated public JSON and CSV files.
