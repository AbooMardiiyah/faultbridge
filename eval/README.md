# FaultBridge Evaluation Harness

The harness implements the evaluation protocol in
[`docs/VOICE_BENCHMARK_RESEARCH.md`](../docs/VOICE_BENCHMARK_RESEARCH.md). It keeps
model inference, transcript scoring, and executable agent grading separate so a
provider error cannot be hidden by downstream aggregation.

## Manifest

The frozen UTF-8 CSV manifest requires these columns:

```text
sample_id,audio_path,audio_sha256,language_pair,reference,reference_tagged,duration_seconds,cmi,switch_points,source_group,source_kind,condition
```

Audio paths are relative to the manifest. Every WAV must be mono PCM16, and its
SHA-256 must match the manifest. `reference_tagged` uses AfriSwitch's
`[[EN]]...[[/EN]]` English-span notation.

## Run Providers

Accept AfriSwitch's access conditions on Hugging Face, set `HF_TOKEN`, and install
the benchmark tools in their own virtual environment:

```bash
make benchmark-install
make benchmark-prepare
```

Preparation streams dataset metadata, deterministically chooses 100 samples from
each language, materializes only the frozen panel as 16 kHz PCM16 WAV, and writes
content hashes to `benchmark/manifest.csv`. The selection balances CMI, switch
count, and duration strata. Do not tune against this test-only panel.

`make benchmark-robustness` creates a second manifest with the clean clips plus
fixed PSTN μ-law, 10 dB noise, and 3% 20 ms frame-erasure variants. The command can
also generate 5/20 dB noise, 1/5% random loss, burst loss, and mild reverberation.
The transforms preserve duration, use stable per-clip seeds, and never modify the
frozen originals.

The application environment is enough for Sahara and AssemblyAI. Faster-Whisper,
SBPN, and Meta OmniASR use isolated environments so their research dependencies do
not enlarge the product container:

```bash
make benchmark-install
make benchmark-install-sbpn
make benchmark-install-omni
```

Install Faster-Whisper's CUDA runtime with
`make benchmark-install-faster-whisper-cuda`. The target adds only cuBLAS and
cuDNN to its isolated environment.

On a CUDA 12.8-compatible NVIDIA system, install OmniASR's isolated GPU runtime
instead with `make benchmark-install-omni-cuda`. This replaces only the
`.venv-omni` CPU Torch and fairseq2 binaries; it does not enlarge the application
container.

The local weights download only when each provider first starts. Use
`TORCH_BACKEND=cu128` on the two PyTorch install targets only after CUDA is visible;
CPU is the safe default. Results resume by successful sample ID. The runner refuses
to mix a changed model, device configuration, or manifest in an existing file;
`--retry-failures` records a new attempt without deleting the original evidence.
For paid Sahara ASR, the Make targets use the documented synchronous file-upload
endpoint and its required code-switch language parameter. Each result is appended
immediately, completed sample IDs are skipped on resume, requests start no faster
than once every 2.1 seconds, and three consecutive failures stop the run:

```bash
make benchmark-sahara-batch ASR_BATCH_SIZE=10
make benchmark-sahara-retry ASR_BATCH_SIZE=10
```

The retry command processes untouched samples before previous failures, then
retries samples with the fewest attempts. Accepted jobs are polled by file ID, so
a queued file is never uploaded and billed again. Results record the explicit
language code, provider file ID, processing status, and returned rate-limit
headers. Other providers can be run directly:

```bash
PYTHONPATH=src:eval uv run --env-file .env -m faultbridge_eval.runner \
  --manifest benchmark/manifest.csv --provider assemblyai
PYTHONPATH=src:eval .venv-benchmark/bin/python -m faultbridge_eval.runner \
  --manifest benchmark/manifest.csv --provider faster-whisper
PYTHONPATH=src:eval .venv-sbpn/bin/python -m faultbridge_eval.runner \
  --manifest benchmark/manifest.csv --provider sbpn
PYTHONPATH=src:eval .venv-omni/bin/python -m faultbridge_eval.runner \
  --manifest benchmark/manifest.csv --provider omniasr
```

For the reproducible GPU configurations used in the four-model report, run
`make benchmark-faster-whisper-cuda` and `make benchmark-omni-cuda`. These use
Faster-Whisper `int8_float16` and OmniASR CUDA inference respectively. Both set
`HF_HUB_OFFLINE=1`, so first cache the model checkpoints with an online pilot.
Result metadata records model, device, compute type, and runtime versions, and the
runner rejects configuration changes in an existing append-only result file.

AssemblyAI and the optional Sahara WebSocket provider receive audio at real-time
pace unless `--no-realtime-pacing` is supplied. AssemblyAI uses `whisper-rt`
because Universal-3 Pro Streaming does not currently cover the four Nigerian
languages. File-upload latency is reported separately from streaming latency.

## Score

```bash
PYTHONPATH=src:eval uv run -m faultbridge_eval.scorer \
  --manifest benchmark/manifest.csv eval/results/raw/*.jsonl
```

The scorer reports raw and normalized WER/CER, separate substitution/deletion/
insertion rates, embedded-English and matrix-language error, switch-context recall,
failures, latency percentiles, and source-clustered 95% bootstrap intervals. It
also produces paired model-difference intervals and equal-language macro results.
Failed transcriptions remain in the denominator as empty hypotheses. Incomplete
provider panels are rejected unless `--allow-incomplete` is explicitly used for
development.

The final four-model aggregate is committed under `benchmark/results/`; raw
JSONL transcripts remain ignored. The Faster-Whisper empty-output audit also
reran its 16 blank cases without VAD. Forced decoding returned text for all 16 but
had 100% median WER and obvious repetitions or unrelated boilerplate, so the
official comparison retains the default VAD-on results.

## Code-switched TTS evaluation

The separate [TTS protocol](../docs/TTS_BENCHMARK_PROTOCOL.md) freezes 100 genuine
code-switched text prompts and generates every prompt once with each Sahara voice:
200 paired outputs in total. It preserves every request failure and audio hash:

```bash
make benchmark-tts-prepare
make benchmark-tts-batch TTS_BATCH_SIZE=10 TTS_GENDERS=female
```

Each completed request is appended immediately. Re-running the batch command skips
both successful and previously failed samples and continues with unattempted work.
After checking the provider and replenishing credit, retry failures fairly across
the panel with `make benchmark-tts-retry TTS_BATCH_SIZE=10 TTS_GENDERS=female`.
Successful audio is never regenerated. Generation also pauses automatically after
three consecutive provider failures, which limits spend during an outage or credit
failure. Use `make benchmark-tts-generate` only for an intentionally unbounded full
run. Sessions start no faster than once every two seconds; Intron does not publish
a separate per-minute limit for the streaming WebSocket endpoint. The runner also
records the balance reported in each `SESSION_CREATED` response. For a targeted
contract check, pass `--prompt-id ID --genders female --retry-failures --limit 1`
directly to `faultbridge_eval.tts_runner`.

Transcribe `benchmark/tts_generated.csv` with three independent model families,
then calculate the organizer-requested metrics:

```bash
make benchmark-tts-asr-faster-whisper
make benchmark-tts-asr-sbpn
make benchmark-tts-asr-omni
make benchmark-tts-score
make benchmark-tts-audit
```

The scorer reports judge-specific WER/CER, insertion-based hallucination,
deletion-based transcript loss, complete tagged-language segment loss, exact
utterance accuracy, judge consensus, generation failure, latency, clipping, and
silence. Sahara ASR cannot be the sole judge of Sahara TTS. Automatic flags must
be confirmed on the predeclared bilingual-listener audit subset before they are
described as verified failures.
`benchmark-tts-audit` oversamples majority-flagged failures within each
language/voice cell, fills the remainder deterministically, and writes a separate
controller key and randomized listener rating sheet. Do not expose the reference
or target phrase to a listener before their typed identification response.

## Executable agent evaluation

Write the 48 reviewed telco scenarios against `scenario.schema.json`. Set a
dedicated `EVALUATION_DATABASE_URL` whose database name contains `eval` or `test`;
the runner refuses the runtime database and clears this evaluation database before
each run. Then run the gold transcript and provider hypotheses three times through
the real configured LLM, orchestrator, PostgreSQL tools, and state assertions:

```bash
PYTHONPATH=src:eval uv run --env-file .env -m faultbridge_eval.agent_runner \
  --scenarios benchmark/telco_scenarios.json
make benchmark-agent-score
```

`grade_agent_trace` checks analysis, exact tool order and arguments, response
claims, PII absence, and final database effects. The agent scorer reports pass@1,
pass@k, pass^k, assertion pass rate, each ASR provider's propagation loss from the
gold-transcript result, and voice capability retention.

Put zero-tolerance privacy and groundedness checks under each scenario's
`expected.critical` object. After both scorecards exist, `make benchmark-route`
creates a draft whole-utterance routing policy. A non-Sahara route is recommended
only when its paired WER interval wins, its provider failure and p95 latency remain
inside budget, and all executable critical gates pass. Missing evidence keeps the
Sahara default.

For the dedicated redaction set, keep labelled inputs in the ignored
`benchmark/pii_cases.jsonl` file. Each JSONL row contains `text` and
`expected_spans`, where every span has `type`, `start`, and exclusive `end`.
`make benchmark-privacy-score` reports exact typed-span precision/recall/F1,
per-type scores, exact-case failures, and the hard leakage count without copying
PII text into the result artifact.
