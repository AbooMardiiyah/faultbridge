from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict, deque
from pathlib import Path

from faultbridge_eval.manifest import BenchmarkSample, read_manifest, sha256_file

TTS_SETTINGS = {
    "Hausa-English": ("ha", "hausa"),
    "Igbo-English": ("ig", "igbo"),
    "Pidgin-English": ("pcm", "pidgin"),
    "Yoruba-English": ("yo", "yoruba"),
}

FIELDS = (
    "prompt_id",
    "source_sample_id",
    "source_audio_sha256",
    "source_manifest_sha256",
    "language_pair",
    "language",
    "accent",
    "text",
    "text_tagged",
    "cmi",
    "switch_points",
    "source_group",
)


def _stable_rank(seed: int, sample_id: str) -> str:
    return hashlib.sha256(f"{seed}:{sample_id}".encode()).hexdigest()


def _cmi_band(value: float) -> str:
    if value < 15:
        return "low"
    if value <= 30:
        return "medium"
    return "high"


def _switch_band(value: int) -> str:
    if value <= 2:
        return "1-2"
    if value <= 5:
        return "3-5"
    return "6+"


def select_prompts(
    samples: list[BenchmarkSample], *, per_language: int, seed: int
) -> list[BenchmarkSample]:
    selected: list[BenchmarkSample] = []
    by_language: dict[str, list[BenchmarkSample]] = defaultdict(list)
    for sample in samples:
        if sample.language_pair in TTS_SETTINGS and sample.switch_points > 0:
            by_language[sample.language_pair].append(sample)

    for language_pair in TTS_SETTINGS:
        candidates = by_language[language_pair]
        if len(candidates) < per_language:
            raise ValueError(
                f"{language_pair} has {len(candidates)} eligible prompts; "
                f"{per_language} requested"
            )
        strata: dict[tuple[str, str], deque[BenchmarkSample]] = defaultdict(deque)
        for sample in sorted(
            candidates, key=lambda item: _stable_rank(seed, item.sample_id)
        ):
            strata[(_cmi_band(sample.cmi), _switch_band(sample.switch_points))].append(
                sample
            )
        order = sorted(strata, key=lambda key: _stable_rank(seed, "|".join(key)))
        language_selection: list[BenchmarkSample] = []
        while len(language_selection) < per_language:
            progressed = False
            for stratum in order:
                if strata[stratum] and len(language_selection) < per_language:
                    language_selection.append(strata[stratum].popleft())
                    progressed = True
            if not progressed:
                raise RuntimeError("TTS prompt sampler exhausted unexpectedly")
        selected.extend(language_selection)
    return selected


def write_prompt_manifest(
    source_manifest: Path,
    output: Path,
    *,
    per_language: int,
    seed: int,
) -> None:
    samples = read_manifest(source_manifest, verify_audio=False)
    selected = select_prompts(samples, per_language=per_language, seed=seed)
    source_hash = sha256_file(source_manifest)
    rows = []
    for sample in selected:
        language, accent = TTS_SETTINGS[sample.language_pair]
        rows.append(
            {
                "prompt_id": f"tts-{sample.sample_id}",
                "source_sample_id": sample.sample_id,
                "source_audio_sha256": sample.audio_sha256,
                "source_manifest_sha256": source_hash,
                "language_pair": sample.language_pair,
                "language": language,
                "accent": accent,
                "text": sample.reference,
                "text_tagged": sample.reference_tagged,
                "cmi": sample.cmi,
                "switch_points": sample.switch_points,
                "source_group": sample.source_group,
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {output} with {len(rows)} frozen code-switched TTS prompts")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Freeze the Sahara TTS prompt panel")
    command.add_argument(
        "--source-manifest", type=Path, default=Path("benchmark/manifest.csv")
    )
    command.add_argument(
        "--output", type=Path, default=Path("benchmark/tts_prompts.csv")
    )
    command.add_argument("--per-language", type=int, default=25)
    command.add_argument("--seed", type=int, default=20260915)
    return command


if __name__ == "__main__":
    args = parser().parse_args()
    write_prompt_manifest(
        args.source_manifest,
        args.output,
        per_language=args.per_language,
        seed=args.seed,
    )
