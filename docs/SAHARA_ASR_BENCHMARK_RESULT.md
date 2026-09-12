# Sahara ASR Benchmark Result

## Scope

This result evaluates Sahara's provider-default file ASR on the frozen FaultBridge
AfriSwitch panel: 400 natural code-switched clips, 100 each for Hausa-English,
Igbo-English, Pidgin-English, and Yoruba-English. The panel contains 68.63 minutes
from 351 source groups. Its manifest SHA-256 is
`3d139832dcead055489cb6c668747db56c06090983d3a95ad644d65ff012b3c2`.

Requests used Intron's documented
[`POST /file/v1/upload/sync`](https://docs.voice.intron.io/docs/stt/file-upload-sync)
endpoint, 16 kHz mono PCM16 WAV, and the explicit [language
codes](https://docs.voice.intron.io/docs/stt/supported-languages) `ha`, `ig`, `pcm`,
and `yo`. Optional LLM transcript correction was disabled to measure ASR output.
Accepted queued jobs were polled by file ID rather than uploaded again. The
append-only log contains 401 attempt rows because one locally blocked DNS attempt
was rerun; every one of the 400 clips reached Sahara exactly once.

## Results

| Language pair | Clips | Empty outputs | Normalized WER (95% CI) | Normalized CER | Switch-context recall | Successful latency p50 / p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hausa-English | 100 | 13 | 38.9% (34.3–43.7) | 21.9% | 30.5% | 2.52s / 5.36s |
| Igbo-English | 100 | 10 | 62.1% (56.1–68.1) | 39.5% | 18.2% | 4.86s / 7.68s |
| Pidgin-English | 100 | 0 | 35.6% (31.3–40.3) | 23.3% | 40.2% | 4.84s / 6.60s |
| Yoruba-English | 100 | 19 | 83.6% (79.7–87.2) | 63.1% | 5.4% | 4.90s / 7.13s |

The equal-language normalized WER is 55.0% micro and 57.7% macro. Normalized CER
is 37.0%, and the failure rate is 10.5%. Failed calls remain in WER as empty
hypotheses; latency percentiles cover successful responses only.

## Paired Comparison and Interpretation

On the identical clips, Sahara reduced WER versus SBPN by 6.2 percentage points
for Hausa (95% CI 3.7–8.7), 3.7 points for Igbo (0.1–7.2), and 3.7 points for
Pidgin (0.8–6.6). Yoruba differed by +1.5 points, with an interval crossing zero,
so that comparison is inconclusive.

All 42 final failures were `FILE_TRANSCRIBED` responses with an empty documented
`audio_transcript` field. They were language-dependent and sometimes clustered,
while Pidgin completed 100/100. The files had speech and nonempty references. This
supports reporting completion reliability separately from accuracy, without
claiming an internal provider cause. File API latency is network turnaround and
must not be compared directly with SBPN's local CPU inference latency.
