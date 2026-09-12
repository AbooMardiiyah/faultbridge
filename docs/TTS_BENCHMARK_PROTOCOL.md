# FaultBridge Code-Switched TTS Benchmark Protocol

## Decision and Scope

FaultBridge uses Sahara TTS in the submitted product, so the benchmark must test
that component directly. The TTS track asks whether Sahara speaks the requested
Hausa-English, Igbo-English, Pidgin-English, and Yoruba-English text completely,
intelligibly, naturally, and quickly. It remains separate from the ASR leaderboard
and the end-to-end agent score so a strong recognizer cannot hide a synthesis
failure, and an ASR judge error cannot be presented as certain TTS failure.

The organizer-requested measures—hallucination, transcript loss, segment loss,
WER, and accuracy—are reported with frozen definitions below. The cited
ASR-FAIRBENCH paper motivates stratified equity reporting, but it is an ASR
fairness paper; it does not define the TTS measures.[^1] TTS fidelity follows the
established round-trip method of transcribing synthesized audio and aligning that
hypothesis to the input text.[^2] Automatic scores are paired with native-speaker
listening because WER cannot measure naturalness or decide every pronunciation
question.[^2]

## Predeclared Questions

The benchmark answers these questions in order:

1. Does every request produce valid, audible speech using the required language,
   accent, and gender parameters?
2. Is the input message preserved, especially complete local-language and switched
   English spans?
3. Are critical words understandable to bilingual listeners?
4. Is pronunciation and switching natural enough for a Nigerian support call?
5. Do fidelity, quality, or latency differ materially by language pair or voice?
6. Does telephone transmission change the conclusion?

## Frozen Panel

`benchmark/tts_prompts.csv` contains 100 prompts selected from the frozen
AfriSwitch ASR manifest: 25 per language pair. Selection seed `20260915`
round-robins across Code-Mixing Index bands and switch-count bands. Every prompt
has at least one switch point and retains AfriSwitch's `[[EN]]` span annotation.
The prompt-manifest SHA-256 is
`882d814fff276e27abb0623312f9f0e38c7c335eba68205ea4fb3be7e93216c0`.

This is natural code-switched text from human speech, rather than authored test
copy. The source audio is not used as a waveform reference because speakers,
prosody, and wording disfluencies differ from the requested synthetic voice. It is
used only for text provenance. The panel is evaluation-only and inherits the
AfriSwitch access and license conditions.

Each prompt is synthesized once with female and male voices, producing 200 primary
outputs. The API parameters are fixed as follows:

| Pair | `voice_language` | `voice_accent` | Voices |
|---|---:|---|---|
| Hausa-English | `ha` | `hausa` | female, male |
| Igbo-English | `ig` | `igbo` | female, male |
| Pidgin-English | `pcm` | `pidgin` | female, male |
| Yoruba-English | `yo` | `yoruba` | female, male |

These language codes match Intron's code-switched STT list, and the TTS values
match Intron's supported-language and accent table.[^3] The runner records exact
text, parameters, request time, time to first audio, time to last audio, session
close time, WAV properties, audio SHA-256, code commit, dependency-lock hash, and
failures. The real-time factor uses time to last audio, excluding the later commit
acknowledgement wait. It merges multiple provider WAV chunks by decoding and
concatenating PCM frames; binary WAV files are never joined blindly.

The live streaming endpoint can return a complete `READY` WAV chunk without later
returning its persisted-session `COMMITTED_AUDIO` summary. The adapter always
sends `COMMIT`, waits up to 10 seconds for that summary, and retains the already
complete audio if the summary is absent. The generation log records this timeout
policy. A missing summary is a provider observability limitation; it is not counted
as missing speech when the fetched WAV validates and its hash is retained.

## Metric Definitions

Let an independent ASR judge align normalized input words to its transcript.
`S`, `D`, and `I` are substitutions, deletions, and insertions, and `N` is the
number of input words.

| Requested measure | Frozen operational definition | Interpretation |
|---|---|---|
| WER | `(S + D + I) / N` | Overall lexical intelligibility proxy |
| Hallucination rate | `I / N` | Added spoken content detected by alignment |
| Hallucination incidence | Share of outputs with at least one insertion, confirmed by a majority of ASR judges or human audit | Frequency of affected outputs |
| Transcript loss | `D / N` and share of outputs with a deletion | Missing requested words; comparable to word-deletion robustness measures |
| Segment loss | Share of contiguous tagged language spans with no correctly aligned word | Complete loss of a matrix-language or switched-English span |
| Accuracy | Exact normalized utterance match rate, plus human keyword-identification accuracy | A transparent success measure; `1-WER` is not relabelled as accuracy |

The report also shows CER, substitutions, embedded-English segment loss,
matrix-language segment loss, and switch-context recall. Segment loss is a
FaultBridge operational definition because the phrase does not have one universal
TTS formula. Publishing its code and definition makes it reproducible. A one-word
span counts as lost when that word is not recovered; a multiword span counts as
lost only when none of its words is recovered.

Insertion and deletion rates are automatic indicators, not final semantic labels.
An ASR can invent or miss a word even when the TTS is correct. A severe case is
confirmed when at least two of the three independent judges agree, or when a
bilingual reviewer verifies it. Examples in the report retain the input, each
judge transcript, alignment, audio hash, and reviewer decision.

Research on robust TTS introduced Word Deletion Rate for under-generation and
Unaligned Duration Ratio for over-generation, babbling, or excessive silence.[^4]
FaultBridge implements the deletion measure directly and uses duration, silence,
and clipping diagnostics to flag audio for review. It does not label silence alone
as hallucination. Recent work on speech-language-model TTS likewise combines
ASR-based intelligibility with listening tests and explicitly examines
unintelligible speech, non-speech sounds, and hallucination.[^5]

## Independent ASR-Judge Protocol

The primary judges are SBPN Multilingual Base, Meta
`omniASR_CTC_300M_v2`, and Faster-Whisper `large-v3-turbo`. They represent Nigerian,
massively multilingual, and broad multilingual model families. Each receives the
same generated WAV manifest; language selection is supplied only when the model
interface supports it, and that configuration is recorded. Report each judge
separately before any consensus. The consensus column uses median WER
and majority flags, never the most favorable judge.

Sahara ASR may appear as a sensitivity row, but it cannot be the sole judge of
Sahara TTS. Using one provider to grade its own synthesis creates correlated
errors. If judges disagree on a high-impact output, the human audit decides the
case. ASR-provider failures remain visible and are not converted into evidence of
TTS hallucination.

Normalization is identical to the ASR benchmark: Unicode NFKC, case folding,
whitespace collapse, and frozen punctuation handling. Diacritics are preserved in
the primary score, with a diacritic-insensitive sensitivity result. No LLM fixes a
transcript. The report lists exact model identifiers and parameters.

## Human Listening Protocol

Automatic TTS metrics are useful smoke tests, but subjective listening remains the
standard for perceived quality.[^2] ITU-T P.800 defines subjective transmission
quality methods, while P.808 adapts speech-quality evaluation to controlled
crowdsourcing.[^6] FaultBridge uses a small, auditable P.800/P.808-inspired study
rather than claiming formal ITU compliance.

Select 40 primary outputs: five per language-pair and voice cell. Oversample any
automatic hallucination, transcript-loss, segment-loss, clipping, or long-silence
flag, then fill remaining slots with a seeded random sample. Recruit at least three
bilingual listeners per language pair. A listener must understand both languages
in the pair and must not see provider or automatic-score labels.

Randomize playback order and include a headphone check, one obvious attention
check, and replay limits. After one complete playback, collect:

- naturalness, 1–5 Mean Opinion Score;
- pronunciation clarity, 1–5;
- code-switch appropriateness, 1–5;
- whether any requested content is missing or extra;
- typed identification of a preselected critical word or short phrase.

Code-switched TTS research has found lower intelligibility for code-switched than
monolingual conditions and used bilingual listeners plus keyword identification
to expose the difference.[^7] That result supports the critical-word task here.
It does not justify borrowing another study's score as FaultBridge evidence.

Report the number of listeners and ratings, median and mean scores with 95%
bootstrap intervals, language-pair slices, voice slices, and inter-rater agreement.
Do not publish MOS until the planned listener count and quality gates are met.
Reviewer notes must not contain names, phone numbers, or account identifiers.

## Reliability, Fairness, and Statistics

Generate a second output for a seeded 20-prompt subset to measure stochastic
stability. Report absolute within-prompt WER change, repeated generation-failure
rate, and whether majority hallucination or loss flags change. A single favorable
render is not sufficient evidence.

All primary tables show each language pair and voice separately, plus an
equal-language macro average. Corpus micro averages are secondary. Use paired,
source-group-clustered bootstrap resampling with 2,000 iterations and seed
`20260915` for 95% intervals. The source-group cluster prevents several excerpts
from one source recording from acting like independent speakers.

ASR-FAIRBENCH shows why pooled WER can conceal demographic disparity and uses
self-reported demographic attributes with mixed-effects regression.[^1]
AfriSwitch does not provide the equivalent complete demographic labels for this
panel. FaultBridge therefore reports language pair, CMI, switch count, source
group, and voice, and does not calculate its FAAS score or claim demographic
fairness. The limitation belongs beside the result, not in a footnote alone.

## Channel and End-to-End Tests

The clean generated WAV is the primary TTS result. A separately labelled
telephone condition converts the same output through G.711 μ-law and applies the
predeclared noise and frame-loss conditions. This measures message survival on a
call; it does not alter the clean TTS ranking. Full-loop tests then run Sahara STT,
the frozen FaultBridge agent, and Sahara TTS and report task success, grounded
claims, time to first audio, total turn latency, interruptions, and privacy gates.

Full-reference measures such as ViSQOL require matched reference audio and are not
appropriate when the natural source and synthetic target use different voices and
prosody.[^8] Large metric suites such as VERSA can be a useful post-submission
sensitivity analysis, but installing many neural predictors days before the
deadline would add hardware and reproducibility risk.[^9]

## Reproduction and Reporting

Prepare and generate the panel with:

```bash
make benchmark-tts-prepare
make benchmark-tts-generate
```

Then transcribe `benchmark/tts_generated.csv` with all three independent ASR
judges and score their JSONL outputs:

```bash
make benchmark-tts-asr-faster-whisper
make benchmark-tts-asr-sbpn
make benchmark-tts-asr-omni
make benchmark-tts-score
```

The final report must include the prompt-manifest hash, generated-audio hashes,
model versions, all failed requests, judge disagreement, human-audit sample size,
confidence intervals, and limitations. Empty cells remain empty until measured.
No estimated, mocked, or manually improved number may appear in a results table.

## Sources

[^1]: Rai et al. “[ASR-FAIRBENCH: Measuring and Benchmarking Equity Across Speech Recognition Systems](https://www.isca-archive.org/interspeech_2025/rai25_interspeech.pdf).” Interspeech, 2025.
[^2]: NVIDIA. “[Evaluate a TTS Pipeline](https://docs.nvidia.com/deeplearning/riva/archives/2-18-0/tutorials/tts-evaluate.html).” Riva documentation, 2024.
[^3]: Intron Voice. “[STT Supported Languages](https://docs.voice.intron.io/docs/stt/supported-languages)” and “[TTS Supported Languages and Accents](https://docs.voice.intron.io/docs/tts/supported-languages-and-accents).” Accessed 12 September 2026.
[^4]: Shen et al. “[Non-Attentive Tacotron: Robust and Controllable Neural TTS Synthesis Including Unsupervised Duration Modeling](https://arxiv.org/abs/2010.04301).” 2021.
[^5]: Wang and Székely. “[Evaluating Text-to-Speech Synthesis from a Large Discrete Token-based Speech Language Model](https://arxiv.org/abs/2405.09768).” LREC-COLING, 2024.
[^6]: ITU-T. “[P.800: Methods for Subjective Determination of Transmission Quality](https://www.itu.int/rec/T-REC-P.800)” and “[P.808: Subjective Evaluation of Speech Quality with a Crowdsourcing Approach](https://www.itu.int/rec/T-REC-P.808).”
[^7]: Méndez Kline and Zellou. “[The Perception of Code-Switched vs. Monolingual Sentences in TTS Voices](https://doi.org/10.3389/fcomp.2025.1565604).” Frontiers in Computer Science, 2025.
[^8]: Chinen et al. “[ViSQOL v3: An Open Source Production Ready Objective Speech and Audio Metric](https://research.google/pubs/visqol-v3-an-open-source-production-ready-objective-speech-and-audio-metric/).” 2020.
[^9]: Shi et al. “[VERSA: A Versatile Evaluation Toolkit for Speech, Audio, and Music](https://github.com/wavlab-speech/versa).” 2025.
