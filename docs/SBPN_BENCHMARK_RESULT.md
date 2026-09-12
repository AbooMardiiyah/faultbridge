# SBPN ASR Benchmark Result

## Scope

This result evaluates `ogunlao/SBPN_multilingual_base` on the frozen FaultBridge
AfriSwitch clean-speech panel: 400 natural code-switched clips, 100 each for
Hausa-English, Igbo-English, Pidgin-English, and Yoruba-English. The panel contains
68.63 minutes from 351 source groups. Its manifest SHA-256 is
`3d139832dcead055489cb6c668747db56c06090983d3a95ad644d65ff012b3c2`.

Inference ran locally on CPU with NeMo 2.7.3 and PyTorch 2.14.0+cpu, batch size
one. The checkpoint's unavailable `graph_rnnt` training loss was replaced by
NeMo's inference-safe PyTorch RNNT loss during restoration. Model weights and
decoding settings were unchanged.

## Results

| Language pair | Clips | Empty outputs | Normalized WER (95% CI) | Normalized CER | Switch-context recall | Latency p50 / p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hausa-English | 100 | 12 | 45.1% (40.6–49.5) | 23.7% | 28.6% | 0.54s / 1.31s |
| Igbo-English | 100 | 11 | 65.7% (60.5–71.0) | 41.8% | 15.6% | 0.63s / 0.90s |
| Pidgin-English | 100 | 0 | 39.3% (35.7–43.2) | 26.4% | 39.9% | 0.68s / 1.07s |
| Yoruba-English | 100 | 12 | 82.1% (77.9–86.5) | 57.2% | 5.7% | 0.67s / 0.91s |

The equal-language macro normalized WER is 58.1%, normalized CER is 37.3%, and
failure rate is 8.75%. Embedded-English error is 55.7%, matrix-language error is
60.2%, and switch-context recall is 22.4%.

## Failure Analysis

All 400 sample IDs have a final outcome. The runner retried the 35 empty outputs
once; all 35 remained empty. The files are valid, non-silent WAVs, and failures do
not concentrate among long clips or low-volume audio. They are language-dependent:
12 Hausa, 11 Igbo, 12 Yoruba, and no Pidgin failures. Igbo and Yoruba failures also
show somewhat higher code-switch density than their successful subsets.

The directly observed failure is blank-only decoding. The evidence supports a
model limitation on these utterances, but it cannot isolate whether the cause is
acoustic coverage, language balance, or decoder behavior without training data or
internal logits. Failed requests are scored as empty hypotheses rather than
excluded, preventing survivorship bias.

## Interpretation

This is a complete single-model result, not the final comparative report. The
latency measures local offline inference and is not directly comparable with a
network streaming API. Model rankings and routing recommendations require the same
frozen clips from Sahara, Faster-Whisper Turbo, and OmniASR, followed by paired
source-clustered confidence intervals.
