# FaultBridge AfriSwitch Evaluation Panel

This directory defines the frozen natural-speech panel used for the FaultBridge
ASR comparison. It contains 400 AfriSwitch test utterances selected with seed
`20260915`: 100 each from Hausa-English, Igbo-English, Pidgin-English, and
Yoruba-English. The panel totals 68.7 minutes and spans 351 inferred source groups.

Selection round-robins across within-language thirds of Code-Mixing Index and
duration, plus switch-count bands of 1–2, 3–5, and 6+ transitions. This prevents
easy, short, or lightly switched clips from dominating the report. Repeated source
filenames are disambiguated with their immutable dataset row index.

`manifest.csv` is the audit index. It records the local audio path, SHA-256,
language pair, human reference and English-span tags, duration, CMI, switch count,
source group, provenance, and condition for every sample. Its SHA-256 is
`3d139832dcead055489cb6c668747db56c06090983d3a95ad644d65ff012b3c2`.

`robustness_manifest.csv` adds fixed PSTN G.711 μ-law, 10 dB noise, and 3% frame
loss variants for every clip, producing 1,600 rows. Its SHA-256 is
`a12c826e1f372422d25543791cec7fdd4fa8ccdceb1e27c6694843524c948f01`.

`tts_prompts.csv` freezes 100 code-switched text prompts derived from this panel,
25 per language pair, for female and male Sahara TTS evaluation. It contains no
generated audio. Its SHA-256 is
`882d814fff276e27abb0623312f9f0e38c7c335eba68205ea4fb3be7e93216c0`.
Generated WAV files live under ignored `benchmark/tts_audio/`; the generation log
retains their hashes, timing, parameters, and failures.

Rebuild and verify the panel with:

```bash
make benchmark-install
make benchmark-prepare
make benchmark-robustness
make benchmark-tts-prepare
PYTHONPATH=src:eval .venv-benchmark/bin/python -c \
  "from pathlib import Path; from faultbridge_eval.manifest import read_manifest; print(len(read_manifest(Path('benchmark/manifest.csv'))))"
```

The 16 kHz mono PCM16 WAV files live under ignored `benchmark/audio/` and are not
committed. Obtain AfriSwitch access and set `HF_TOKEN` to reproduce them. Provider
failures remain scored as empty hypotheses; the panel must not be pruned after any
model run.

AfriSwitch is published by Intron Innovation under CC BY-NC-SA 4.0. Use and
redistribution remain subject to its dataset card and access conditions. FaultBridge
does not claim ownership of the source recordings or transcripts.
