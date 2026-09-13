# Four-Model Code-Switched ASR Benchmark

## Evaluation Design

This report compares Sahara, SBPN, Faster-Whisper, and Meta OmniASR on the same
frozen AfriSwitch panel. The panel has 400 natural code-switched clips: 100 each
for Hausa-English, Igbo-English, Pidgin-English, and Yoruba-English. It contains
68.63 minutes from 351 source groups. The manifest SHA-256 is
`3d139832dcead055489cb6c668747db56c06090983d3a95ad644d65ff012b3c2`.

The scorer normalizes case and punctuation, retains every failed transcription as
an empty hypothesis, and reports micro WER, CER, switch-context recall, and
failure rate. Confidence intervals use source-clustered bootstrap resampling so
segments from one recording cannot be treated as independent speakers.

## Model Configurations

- **Sahara:** documented synchronous file API, provider-default model, explicit
  `ha`, `ig`, `pcm`, or `yo` language, with LLM correction disabled.
- **SBPN:** `ogunlao/SBPN_multilingual_base`, NeMo 2.7.3, CPU, batch size one.
- **Faster-Whisper:** `large-v3-turbo`, CTranslate2 CUDA, `int8_float16`, default
  voice-activity filtering.
- **OmniASR:** `omniASR_CTC_300M_v2`, fairseq2 0.6, PyTorch 2.8 CUDA, batch size
  one. The CTC model ignores language conditioning.

Local GPU inference used an NVIDIA RTX 3050 Ti Laptop GPU with 4 GB VRAM. API,
CPU, and GPU latency values are different operating conditions and should not be
used as a direct speed ranking.

## Results

| Model | Language pair | Empty | Normalized WER | Normalized CER | Switch recall |
| --- | --- | ---: | ---: | ---: | ---: |
| Sahara | Hausa-English | 13 | **38.9%** | **21.9%** | **30.5%** |
| SBPN | Hausa-English | 12 | 45.1% | 23.7% | 28.6% |
| OmniASR | Hausa-English | 8 | 68.0% | 35.2% | 10.7% |
| Faster-Whisper | Hausa-English | 6 | 98.3% | 64.3% | 1.1% |
| Sahara | Igbo-English | 10 | **62.1%** | **39.5%** | **18.2%** |
| SBPN | Igbo-English | 11 | 65.7% | 41.8% | 15.6% |
| OmniASR | Igbo-English | 5 | 79.9% | 40.7% | 6.4% |
| Faster-Whisper | Igbo-English | 2 | 85.0% | 55.0% | 4.0% |
| Sahara | Pidgin-English | 0 | **35.6%** | **23.3%** | **40.2%** |
| SBPN | Pidgin-English | 0 | 39.3% | 26.4% | 39.9% |
| Faster-Whisper | Pidgin-English | 0 | 51.5% | **32.2%** | **27.4%** |
| OmniASR | Pidgin-English | 0 | 55.7% | 32.6% | 22.7% |
| OmniASR | Yoruba-English | 5 | **81.4%** | **45.4%** | 2.5% |
| SBPN | Yoruba-English | 12 | 82.1% | 57.2% | **5.7%** |
| Sahara | Yoruba-English | 19 | 83.6% | 63.1% | 5.4% |
| Faster-Whisper | Yoruba-English | 8 | 91.2% | 70.6% | 2.2% |

| Model | Equal-language WER | Macro WER | CER | Empty-output rate |
| --- | ---: | ---: | ---: | ---: |
| Sahara | **55.0%** | **57.7%** | **37.0%** | 10.5% |
| SBPN | 58.1% | 60.4% | 37.3% | 8.8% |
| OmniASR | 71.2% | 72.4% | 38.5% | 4.5% |
| Faster-Whisper | 81.5% | 84.0% | 55.5% | **4.0%** |

Sahara's paired WER advantage over SBPN is statistically supported for Hausa
(6.2 percentage points), Igbo (3.7), and Pidgin (3.7); the Yoruba interval crosses
zero. Sahara also beats Faster-Whisper on all four pairs. Against OmniASR, Sahara
wins Hausa, Igbo, and Pidgin, while Yoruba is inconclusive. These results support
Sahara as the default accuracy route, with provider reliability tracked as a
separate production signal.

## Empty-Output Audit

Sahara, SBPN, Faster-Whisper, and OmniASR returned 42, 35, 16, and 18 empty final
outputs respectively. Eight clips were empty for every model. All 16
Faster-Whisper empty clips were also empty for Sahara and SBPN, showing a shared
hard subset rather than random missing files.

A diagnostic reran those 16 Faster-Whisper cases with voice-activity filtering
disabled. All produced text, but median WER was 100% and mean per-clip WER was
113.4%; outputs included repetitions and unrelated boilerplate. The official
VAD-on results therefore remain unchanged. This audit demonstrates the tradeoff
between blank rejection and hallucinated transcription without claiming an
internal cause for any provider.

## Reproducibility

The committed machine-readable aggregate contains all language, slice, latency,
confidence-interval, and paired-comparison results in
`benchmark/results/asr_four_model_summary.json` and `.csv`. Clip-level transcripts,
audio, provider identifiers, and diagnostic outputs stay in ignored local paths to
respect dataset access conditions and voice-data handling rules.
