from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
import sys
import wave
from array import array
from dataclasses import asdict
from pathlib import Path

from faultbridge_eval.manifest import (
    REQUIRED_COLUMNS,
    BenchmarkSample,
    read_manifest,
    sha256_file,
)

CONDITIONS = (
    "pstn-mulaw",
    "noise-20db",
    "noise-10db",
    "noise-5db",
    "packet-loss-1pct",
    "packet-loss-3pct",
    "packet-loss-5pct",
    "burst-loss-5pct",
    "mild-reverb",
)


def read_wav(path: Path) -> tuple[list[int], int]:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f"{path} must be mono PCM16 WAV")
        sample_rate = source.getframerate()
        samples = array("h", source.readframes(source.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    return list(samples), sample_rate


def write_wav(path: Path, samples: list[int], sample_rate: int) -> None:
    values = array("h", (max(-32768, min(32767, value)) for value in samples))
    if sys.byteorder != "little":
        values.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(values.tobytes())


def mulaw_roundtrip(samples: list[int]) -> list[int]:
    """Approximate an 8 kHz G.711 μ-law phone path and return 16 kHz PCM."""
    mu = 255.0
    downsampled = [
        round((samples[index] + samples[min(index + 1, len(samples) - 1)]) / 2)
        for index in range(0, len(samples), 2)
    ]
    decoded: list[int] = []
    for sample in downsampled:
        normalized = max(-1.0, min(1.0, sample / 32768.0))
        compressed = math.copysign(
            math.log1p(mu * abs(normalized)) / math.log1p(mu), normalized
        )
        quantized = round((compressed + 1.0) * 127.5)
        quantized_value = quantized / 127.5 - 1.0
        expanded = math.copysign(
            math.expm1(abs(quantized_value) * math.log1p(mu)) / mu,
            quantized_value,
        )
        decoded.append(round(expanded * 32767))
    restored = [value for sample in decoded for value in (sample, sample)]
    return restored[: len(samples)]


def add_noise(samples: list[int], snr_db: float, generator: random.Random) -> list[int]:
    signal_power = sum(sample * sample for sample in samples) / max(1, len(samples))
    if signal_power == 0:
        return samples.copy()
    noise_rms = math.sqrt(signal_power / (10 ** (snr_db / 10)))
    return [round(sample + generator.gauss(0, noise_rms)) for sample in samples]


def erase_frames(
    samples: list[int],
    sample_rate: int,
    loss_rate: float,
    generator: random.Random,
    *,
    burst: bool,
) -> list[int]:
    frame_size = sample_rate // 50
    frames = [
        samples[index : index + frame_size]
        for index in range(0, len(samples), frame_size)
    ]
    erase_count = max(1, round(len(frames) * loss_rate))
    if burst:
        start = generator.randrange(max(1, len(frames) - erase_count + 1))
        erased = set(range(start, min(len(frames), start + erase_count)))
    else:
        erased = set(
            generator.sample(range(len(frames)), min(erase_count, len(frames)))
        )
    return [
        sample
        for index, frame in enumerate(frames)
        for sample in ([0] * len(frame) if index in erased else frame)
    ]


def add_reverb(samples: list[int], sample_rate: int) -> list[int]:
    output = samples.copy()
    for delay_seconds, gain in ((0.06, 0.3), (0.11, 0.15)):
        delay = round(sample_rate * delay_seconds)
        for index in range(delay, len(samples)):
            output[index] += round(samples[index - delay] * gain)
    return output


def transform(
    samples: list[int], sample_rate: int, condition: str, *, seed: int
) -> list[int]:
    generator = random.Random(seed)
    if condition == "pstn-mulaw":
        return mulaw_roundtrip(samples)
    if condition.startswith("noise-"):
        snr = float(condition.removeprefix("noise-").removesuffix("db"))
        return add_noise(samples, snr, generator)
    if condition.startswith("packet-loss-"):
        rate = float(condition.removeprefix("packet-loss-").removesuffix("pct")) / 100
        return erase_frames(samples, sample_rate, rate, generator, burst=False)
    if condition == "burst-loss-5pct":
        return erase_frames(samples, sample_rate, 0.05, generator, burst=True)
    if condition == "mild-reverb":
        return add_reverb(samples, sample_rate)
    raise ValueError(f"unsupported condition {condition}")


def row_for_sample(
    sample: BenchmarkSample, audio_path: str, condition: str
) -> dict[str, str]:
    values = asdict(sample)
    values.update(
        {
            "sample_id": f"{sample.sample_id}--{condition}",
            "audio_path": audio_path,
            "audio_sha256": "",
            "condition": condition,
        }
    )
    return {key: str(values[key]) for key in REQUIRED_COLUMNS}


def run(args: argparse.Namespace) -> None:
    samples = read_manifest(args.manifest)
    root = args.output.parent.resolve()
    rows: list[dict[str, str]] = []
    if args.include_clean:
        for sample in samples:
            relative = sample.audio_path.relative_to(root)
            row = row_for_sample(sample, str(relative), sample.condition)
            row["sample_id"] = sample.sample_id
            row["audio_sha256"] = sample.audio_sha256
            rows.append(row)
    for sample in samples:
        values, sample_rate = read_wav(sample.audio_path)
        for condition in args.conditions:
            derived = (
                root / "audio" / "robustness" / f"{sample.sample_id}--{condition}.wav"
            )
            condition_seed = int(
                hashlib.sha256(
                    f"{args.seed}:{sample.sample_id}:{condition}".encode()
                ).hexdigest()[:16],
                16,
            )
            write_wav(
                derived,
                transform(values, sample_rate, condition, seed=condition_seed),
                sample_rate,
            )
            row = row_for_sample(sample, str(derived.relative_to(root)), condition)
            row["audio_sha256"] = sha256_file(derived)
            rows.append(row)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {args.output} with {len(rows)} clean and robustness rows")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Build deterministic acoustic robustness variants"
    )
    command.add_argument(
        "--manifest", type=Path, default=Path("benchmark/manifest.csv")
    )
    command.add_argument(
        "--output", type=Path, default=Path("benchmark/robustness_manifest.csv")
    )
    command.add_argument("--seed", type=int, default=20260915)
    command.add_argument(
        "--include-clean", action=argparse.BooleanOptionalAction, default=True
    )
    command.add_argument(
        "--conditions",
        nargs="+",
        choices=CONDITIONS,
        default=["pstn-mulaw", "noise-10db", "packet-loss-3pct"],
    )
    return command


if __name__ == "__main__":
    run(parser().parse_args())
