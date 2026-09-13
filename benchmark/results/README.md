# ASR Result Reproduction

The public repository stores aggregate results. Clip-level hypotheses remain in a
local private archive pending creation of the private Hugging Face dataset
repository `tiamz/faultbridge-asr-benchmark-evidence`; they are model outputs tied
to the gated AfriSwitch panel. No source audio is included.

Once the private repository exists, upload
`asr-benchmark-evidence-20260913.tar.gz`; reviewers with AfriSwitch access can
extract it at the FaultBridge repository root and run:

```bash
make benchmark-verify-asr-evidence
```

The target performs two independent checks. First,
`scripts/verify_asr_evidence.py` verifies every raw result, frozen manifest,
diagnostic, report, and aggregate file against
`asr_evidence_manifest.json`. It then runs `faultbridge-scorer-v1` on the four raw
JSONL files and compares the reproduced aggregate byte-for-byte with
`asr_four_model_summary.json`.

The archive SHA-256 is
`57100b24e76c574928c3eee254f0d560cabd55ff14ce4d7a6f285af9f39f1479`.
The frozen 400-clip manifest SHA-256 is
`3d139832dcead055489cb6c668747db56c06090983d3a95ad644d65ff012b3c2`.
Access and use remain subject to the AfriSwitch dataset card and CC BY-NC-SA 4.0.
The private evidence is uploaded at
`https://huggingface.co/datasets/Tiamz/faultbridge-asr-benchmark-evidence`, revision
`ef320d7f367e040c47b4021a397011dae894fe00`.

## TTS evidence

The TTS public aggregate is `tts_benchmark_summary.json` and `.csv`; its report is
`docs/TTS_BENCHMARK_REPORT.md`. The private local archive includes the raw Sahara
generation log, 600 independent-ASR hypotheses, 200 generated WAVs, their hash
manifest, and the blinded audit materials. After extracting the archive at the
repository root, run:

```bash
make benchmark-verify-tts-evidence
```

The target verifies every evidence and audio hash, reruns
`faultbridge-tts-scorer-v1`, and compares the regenerated public JSON and CSV
byte-for-byte. Private distribution remains subject to AfriSwitch access and
license conditions.

The local archive is `artifacts/tts-benchmark-evidence-20260913.tar.gz` (62,755,397
bytes) with SHA-256
`e78776afd90fdcbb210e8e2ac2328bf1f7f45f34f7544fee34e9784366125cc4`.

## Downstream agent evidence

The public `agent_summary.json` and `.csv` contain the 288-run capability
scorecard; `agent_audio_summary.json` and `.csv` contain the 360-run named-ASR
scorecard. The private archive contains both raw trace sets, the 24 generated
WAVs, generation log, four ASR result files, and attached scenarios. Extract it
at the repository root and run:

```bash
make benchmark-verify-agent-evidence
```

The command verifies every saved file and WAV hash, reruns both agent scorecards,
and byte-compares all four regenerated aggregates. The archive filename is
`artifacts/agent-benchmark-evidence-20260913.tar.gz`; its final size and SHA-256
are recorded in `agent_audio_checkpoint.json`.
Its structure is recorded in `agent_evidence_manifest.json`; completion metadata
is recorded in `agent_audio_checkpoint.json`.
