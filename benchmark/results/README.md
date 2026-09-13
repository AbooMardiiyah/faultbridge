# ASR Result Reproduction

The public repository stores aggregate results. Clip-level hypotheses are in the
private Hugging Face dataset repository
`tiamz/faultbridge-asr-benchmark-evidence`, because they are model outputs tied to
the gated AfriSwitch panel. No audio is uploaded.

Download `asr-benchmark-evidence-20260913.tar.gz` from that repository and extract
it at the FaultBridge repository root. Then run:

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
