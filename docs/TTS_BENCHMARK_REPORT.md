# Sahara Code-Switched TTS Benchmark

## Evaluation Design

This benchmark evaluates Sahara's synchronous TTS endpoint on 100 prompts sampled
deterministically from the approved AfriSwitch panel: 25 each for Hausa-English,
Igbo-English, Pidgin-English, and Yoruba-English. Each prompt was generated once
with female and male voices, giving 200 outputs. These are natural dataset
transcripts, not hand-written examples. The selection seed is `20260915`; the
prompt-manifest SHA-256 is
`882d814fff276e27abb0623312f9f0e38c7c335eba68205ea4fb3be7e93216c0`.

All 200 requests succeeded on their first paid attempt. The resulting 22.05 kHz,
mono PCM16 WAVs total 1,672.29 seconds and 73,756,720 bytes; no sample clipped.
At the posted NGN 0.65 per generated second, this run cost approximately
NGN 1,086.99. Median synchronous response-to-audio availability was 5.41 seconds
and median real-time factor was 0.78. This endpoint returns completed audio, so
the timing must not be presented as streaming time to first audio.

## Independent ASR Judges

Three independent models transcribed every generated audio hash with no judge
failures or empty outputs:

- Faster-Whisper `large-v3-turbo`, CTranslate2 4.8.2, CUDA `int8_float16`, VAD on;
- Meta `omniASR_CTC_300M_v2`, OmniLingual ASR 0.2.0 and fairseq2 0.6, CUDA;
- `ogunlao/SBPN_multilingual_base`, NeMo 2.7.3, CPU, batch size one.

The scorer preserves diacritics and uses the frozen ASR normalization and word
alignment. Hallucination is insertion rate (`I/N`), transcript loss is deletion
rate (`D/N`), and segment loss is the share of tagged contiguous language spans
with no correctly aligned word. Accuracy is strict normalized whole-utterance
accuracy. Intervals below are 95% source-clustered bootstrap intervals with 2,000
iterations; the language-level rate is the equal-voice mean.

## Transcript-Fidelity Results

| Judge | Pair | Female WER (95% CI) | Male WER (95% CI) | WER | Extra | Loss | Segment loss | Exact |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Faster-Whisper | Hausa-English | 79.3% (74.5–84.5) | 76.9% (72.3–81.1) | 78.1% | 1.0% | 18.9% | 50.3% | 0.0% |
| Faster-Whisper | Igbo-English | 58.2% (44.4–73.4) | 56.4% (42.5–71.5) | 57.3% | 3.3% | 12.3% | 45.0% | 6.0% |
| Faster-Whisper | Pidgin-English | 29.3% (23.3–34.8) | 29.3% (23.3–35.2) | 29.3% | 4.3% | 1.9% | 12.2% | 0.0% |
| Faster-Whisper | Yoruba-English | 70.9% (57.8–82.2) | 68.2% (55.6–80.2) | 69.5% | 4.8% | 17.8% | 50.7% | 0.0% |
| OmniASR | Hausa-English | 41.4% (35.3–47.1) | 38.5% (31.9–44.7) | 40.0% | 3.6% | 7.8% | 36.3% | 0.0% |
| OmniASR | Igbo-English | 62.9% (55.2–70.4) | 62.1% (52.9–72.0) | 62.5% | 2.1% | 13.3% | 40.1% | 0.0% |
| OmniASR | Pidgin-English | 28.6% (24.1–34.1) | 27.4% (23.3–31.6) | 28.0% | 2.1% | 1.9% | 11.0% | 0.0% |
| OmniASR | Yoruba-English | 73.8% (64.4–82.3) | 75.3% (67.8–82.3) | 74.6% | 0.7% | 14.8% | 60.0% | 0.0% |
| SBPN | Hausa-English | 24.4% (17.8–30.9) | 25.3% (18.5–32.1) | **24.9%** | 4.8% | 3.1% | 20.7% | 0.0% |
| SBPN | Igbo-English | 43.4% (36.1–50.9) | 45.1% (36.5–54.4) | **44.2%** | 0.8% | 11.8% | 29.0% | 0.0% |
| SBPN | Pidgin-English | 22.1% (19.0–25.0) | 21.8% (18.3–24.8) | **21.9%** | 0.9% | 1.8% | 6.9% | 0.0% |
| SBPN | Yoruba-English | 68.5% (57.9–78.1) | 67.0% (56.5–76.8) | **67.8%** | 2.2% | 13.5% | 54.1% | 0.0% |

| Judge | Equal-language WER | CER | Extra-word rate | Transcript-loss rate | Segment-loss rate | Exact accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Faster-Whisper | 58.6% | 21.5% | 3.3% | 12.7% | 39.6% | 1.5% |
| OmniASR | 51.3% | 19.0% | 2.1% | 9.4% | 36.8% | 0.0% |
| SBPN | **39.7%** | **18.9%** | 2.2% | **7.6%** | **27.7%** | 0.0% |

The female-versus-male equal-language WER difference is small within every judge:
1.7 points for Faster-Whisper, 0.9 for OmniASR, and 0.2 for SBPN. This is a voice
slice, not a demographic fairness claim.

## Consensus and Interpretation

Across the 200 outputs, the median per-sample median-judge WER is 42.9%. At least
two judges flag extra words in 27.5%, word loss in 71.0%, and complete loss of a
tagged span in 69.0% of outputs. These are conservative automatic audit triggers,
not confirmed TTS defect rates: an ASR error can create the same alignment signal.

Judge disagreement is material. For Hausa, apparent WER ranges from 24.9% with
SBPN to 78.1% with Faster-Whisper; Yoruba remains difficult for all three. Pidgin
is consistently strongest at 21.9–29.3%. The evidence therefore supports strong
generation reliability and roughly stable female/male intelligibility, while
bilingual listening is required before claiming semantic error prevalence or
naturalness.

The deterministic audit command selected 40 outputs, five per language/voice
cell, prioritizing consensus error flags. Its controller and randomized rating
sheet are stored with private evidence. At least three bilingual listeners per
language pair must score naturalness, pronunciation, code-switch appropriateness,
missing or extra content, and a typed target phrase. No MOS or human-confirmed
hallucination result is reported until those ratings exist.

## Reproducibility and Limitations

`benchmark/results/tts_benchmark_summary.json` and `.csv` contain the public
24-cell aggregate. The raw generation log, three 200-row hypothesis files,
generated-audio manifest, audit sheets, and WAVs remain in ignored private paths
because they contain model output derived from gated AfriSwitch text. Every WAV
is bound to the evidence by SHA-256. Run `make benchmark-tts-score` to reproduce
the aggregate and `make benchmark-tts-audit` to reproduce the audit selection.

The synchronous API exposed `x-ratelimit-limit: 60` on observed responses, while
the documentation stated 30 generation requests per minute when accessed. The
run used the conservative documented limit and 2.1-second request spacing. The
earlier WebSocket diagnostic's failures are excluded from every table. There is no
natural reference recording of the same speaker and prosody, so full-reference
quality metrics are inappropriate; ASR fidelity also cannot replace MOS.
