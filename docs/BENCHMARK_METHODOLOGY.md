# Benchmark Methodology

## Evaluation Scope

FaultBridge measures speech components and the decisions they produce. Frozen
manifests, identical inputs, explicit failure accounting, and downstream policy
assertions make the comparison reproducible. The final results are in the
[benchmark report](BENCHMARK_REPORT.pdf).

## Natural Speech Recognition

The panel contains 400 licensed AfriSwitch clips: 100 each for Hausa-English,
Igbo-English, Pidgin-English, and Yoruba-English. Selection is stratified by
Code-Mixing Index, switch count, duration, and source group. Sahara, SBPN
Multilingual Base, Meta OmniASR CTC 300M v2, and Faster-Whisper
`large-v3-turbo` receive the same hashed audio.

WER, CER, language-role errors, switch-context recall, failures, and latency are
reported by language and as equal-language aggregates. Empty and failed outputs
remain in the denominator. Paired differences and 95% intervals use 2,000
source-group-clustered bootstrap samples.

## Speech Synthesis

One hundred genuine code-switched AfriSwitch transcripts, 25 per language pair,
are synthesized once with Sahara female and male voices, producing 200 outputs.
SBPN, OmniASR, and Faster-Whisper independently transcribe every output.

Automatic measures include WER, insertion-based hallucination rate,
deletion-based transcript loss, complete language-segment loss, exact normalized
match, latency, silence, and clipping. These are diagnostic indicators because an
ASR judge can introduce errors. The planned 40-file bilingual listening audit is
still pending, so no MOS or confirmed human-quality claim is made.

## Executable Agent Evaluation

Forty-eight synthetic scenarios, 12 per language pair, execute the real
orchestrator, tools, and isolated PostgreSQL database. Three repetitions over gold
and controlled-stress text produce 288 runs. Assertions cover tool order,
arguments, database effects, grounded claims, privacy gates, and final state.

A separate 24-utterance panel passes gold text and four named ASR hypotheses into
the same agent, producing 360 runs. Metrics include strict task success, assertion
rate, critical failure rate, pass@1, pass@3, pass³, propagation loss, and capability
retention. Together these panels contain 648 agent executions.

## Privacy Evaluation

The privacy panel has 100 synthetic cases, including negative controls and 100
labelled spans across phone, email, account, SIM, and numeric identifiers. Exact
typed-span precision, recall, F1, and leakage count are reported. Results apply
only to this declared pattern scope.

## Evidence and Reproduction

Manifests preserve sample IDs, language, text, and SHA-256 hashes. Append-only raw
JSONL retains empty responses, failures, provider metadata, model versions,
parameters, latency, code revision, and dependency-lock hashes. Public aggregate
files live in `benchmark/results/`; scoring commands and definitions are in
[`eval/README.md`](../eval/README.md).

Natural-audio evidence is stored privately to preserve AfriSwitch access terms at
[`Tiamz/faultbridge-asr-benchmark-evidence`](https://huggingface.co/datasets/Tiamz/faultbridge-asr-benchmark-evidence),
revision `ef320d7f367e040c47b4021a397011dae894fe00`. The difficult natural panel,
synthetic TTS agent audio, pending human TTS audit, and incomparable local versus
cloud latency are declared limitations.
