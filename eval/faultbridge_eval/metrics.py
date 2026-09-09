from __future__ import annotations

import random
import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

_ENGLISH_OPEN = "[[EN]]"
_ENGLISH_CLOSE = "[[/EN]]"


@dataclass(frozen=True, slots=True)
class ErrorCounts:
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0
    reference_units: int = 0

    @property
    def error_rate(self) -> float:
        if self.reference_units == 0:
            return 0.0 if self.insertions == 0 else 1.0
        return (
            self.substitutions + self.deletions + self.insertions
        ) / self.reference_units

    def __add__(self, other: ErrorCounts) -> ErrorCounts:
        return ErrorCounts(
            self.substitutions + other.substitutions,
            self.deletions + other.deletions,
            self.insertions + other.insertions,
            self.reference_units + other.reference_units,
        )


@dataclass(frozen=True, slots=True)
class AlignmentStep:
    operation: str
    reference_index: int | None
    hypothesis_index: int | None


@dataclass(frozen=True, slots=True)
class RoleErrorCounts:
    embedded_english_errors: int = 0
    embedded_english_units: int = 0
    matrix_errors: int = 0
    matrix_units: int = 0

    @property
    def embedded_english_rate(self) -> float:
        if not self.embedded_english_units:
            return 0.0
        return self.embedded_english_errors / self.embedded_english_units

    @property
    def matrix_rate(self) -> float:
        if not self.matrix_units:
            return 0.0
        return self.matrix_errors / self.matrix_units

    def __add__(self, other: RoleErrorCounts) -> RoleErrorCounts:
        return RoleErrorCounts(
            self.embedded_english_errors + other.embedded_english_errors,
            self.embedded_english_units + other.embedded_english_units,
            self.matrix_errors + other.matrix_errors,
            self.matrix_units + other.matrix_units,
        )


def canonical_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def normalize_text(text: str, *, remove_diacritics: bool = False) -> str:
    text = canonical_text(text).casefold()
    if remove_diacritics:
        text = "".join(
            character
            for character in unicodedata.normalize("NFD", text)
            if unicodedata.category(character) != "Mn"
        )
    text = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in text
    )
    return " ".join(text.split())


def _alignment(
    reference: Sequence[str], hypothesis: Sequence[str]
) -> list[AlignmentStep]:
    rows = len(reference) + 1
    columns = len(hypothesis) + 1
    costs = [[0] * columns for _ in range(rows)]
    back: list[list[str | None]] = [[None] * columns for _ in range(rows)]
    for index in range(1, rows):
        costs[index][0] = index
        back[index][0] = "delete"
    for index in range(1, columns):
        costs[0][index] = index
        back[0][index] = "insert"

    priority = {"equal": 0, "substitute": 1, "delete": 2, "insert": 3}
    for ref_index in range(1, rows):
        for hyp_index in range(1, columns):
            diagonal_operation = (
                "equal"
                if reference[ref_index - 1] == hypothesis[hyp_index - 1]
                else "substitute"
            )
            candidates = [
                (
                    costs[ref_index - 1][hyp_index - 1]
                    + (diagonal_operation == "substitute"),
                    diagonal_operation,
                ),
                (costs[ref_index - 1][hyp_index] + 1, "delete"),
                (costs[ref_index][hyp_index - 1] + 1, "insert"),
            ]
            cost, operation = min(
                candidates, key=lambda candidate: (candidate[0], priority[candidate[1]])
            )
            costs[ref_index][hyp_index] = int(cost)
            back[ref_index][hyp_index] = operation

    steps: list[AlignmentStep] = []
    ref_index, hyp_index = len(reference), len(hypothesis)
    while ref_index or hyp_index:
        operation = back[ref_index][hyp_index]
        if operation in {"equal", "substitute"}:
            steps.append(AlignmentStep(operation, ref_index - 1, hyp_index - 1))
            ref_index -= 1
            hyp_index -= 1
        elif operation == "delete":
            steps.append(AlignmentStep(operation, ref_index - 1, None))
            ref_index -= 1
        elif operation == "insert":
            steps.append(AlignmentStep(operation, None, hyp_index - 1))
            hyp_index -= 1
        else:
            raise RuntimeError("alignment backtrace is incomplete")
    steps.reverse()
    return steps


def error_counts(reference: Sequence[str], hypothesis: Sequence[str]) -> ErrorCounts:
    substitutions = deletions = insertions = 0
    for step in _alignment(reference, hypothesis):
        substitutions += step.operation == "substitute"
        deletions += step.operation == "delete"
        insertions += step.operation == "insert"
    return ErrorCounts(substitutions, deletions, insertions, len(reference))


def word_errors(reference: str, hypothesis: str, *, normalized: bool) -> ErrorCounts:
    transform = normalize_text if normalized else canonical_text
    return error_counts(transform(reference).split(), transform(hypothesis).split())


def character_errors(
    reference: str, hypothesis: str, *, normalized: bool
) -> ErrorCounts:
    transform = normalize_text if normalized else canonical_text
    ref = [character for character in transform(reference) if not character.isspace()]
    hyp = [character for character in transform(hypothesis) if not character.isspace()]
    return error_counts(ref, hyp)


def parse_tagged_reference(text: str) -> tuple[list[str], list[str]]:
    expanded = text.replace(_ENGLISH_OPEN, f" {_ENGLISH_OPEN} ").replace(
        _ENGLISH_CLOSE, f" {_ENGLISH_CLOSE} "
    )
    english = False
    tokens: list[str] = []
    roles: list[str] = []
    for token in expanded.split():
        if token == _ENGLISH_OPEN:
            english = True
        elif token == _ENGLISH_CLOSE:
            english = False
        else:
            normalized = normalize_text(token)
            for normalized_token in normalized.split():
                tokens.append(normalized_token)
                roles.append("embedded_english" if english else "matrix")
    return tokens, roles


def language_role_counts(tagged_reference: str, hypothesis: str) -> RoleErrorCounts:
    reference, roles = parse_tagged_reference(tagged_reference)
    hypothesis_tokens = normalize_text(hypothesis).split()
    totals = {"embedded_english": 0, "matrix": 0}
    errors = {"embedded_english": 0, "matrix": 0}
    steps = _alignment(reference, hypothesis_tokens)
    next_reference: list[int | None] = [None] * len(steps)
    upcoming: int | None = None
    for index in range(len(steps) - 1, -1, -1):
        next_reference[index] = upcoming
        if steps[index].reference_index is not None:
            upcoming = steps[index].reference_index
    previous_reference: int | None = None
    for index, step in enumerate(steps):
        if step.reference_index is not None:
            role = roles[step.reference_index]
            totals[role] += 1
            errors[role] += step.operation != "equal"
            previous_reference = step.reference_index
        elif roles:
            neighbor = previous_reference
            if neighbor is None:
                neighbor = next_reference[index]
            role = roles[neighbor if neighbor is not None else 0]
            errors[role] += 1
    return RoleErrorCounts(
        embedded_english_errors=errors["embedded_english"],
        embedded_english_units=totals["embedded_english"],
        matrix_errors=errors["matrix"],
        matrix_units=totals["matrix"],
    )


def language_role_errors(tagged_reference: str, hypothesis: str) -> dict[str, float]:
    counts = language_role_counts(tagged_reference, hypothesis)
    rates = {
        "embedded_english": counts.embedded_english_rate,
        "matrix": counts.matrix_rate,
    }
    rates["language_role_gap"] = abs(rates["embedded_english"] - rates["matrix"])
    return rates


def switch_context_recall(tagged_reference: str, hypothesis: str) -> float:
    reference, roles = parse_tagged_reference(tagged_reference)
    switches = [
        index for index in range(1, len(roles)) if roles[index] != roles[index - 1]
    ]
    if not switches:
        return 1.0
    hypothesis_tokens = normalize_text(hypothesis).split()
    matched_positions = {
        step.reference_index: step.hypothesis_index
        for step in _alignment(reference, hypothesis_tokens)
        if step.operation == "equal"
    }
    preserved = sum(
        matched_positions.get(index - 1) is not None
        and matched_positions.get(index) == matched_positions[index - 1] + 1
        for index in switches
    )
    return preserved / len(switches)


def entity_scores(expected: Sequence[str], hypothesis: str) -> dict[str, float]:
    expected_normalized = {normalize_text(entity) for entity in expected if entity}
    hypothesis_tokens = normalize_text(hypothesis).split()
    matched = 0
    for entity in expected_normalized:
        entity_tokens = entity.split()
        matched += any(
            hypothesis_tokens[index : index + len(entity_tokens)] == entity_tokens
            for index in range(len(hypothesis_tokens) - len(entity_tokens) + 1)
        )
    recall = matched / len(expected_normalized) if expected_normalized else 1.0
    return {
        "matched": float(matched),
        "expected": float(len(expected_normalized)),
        "recall": recall,
    }


def set_prf(expected: Sequence[str], predicted: Sequence[str]) -> dict[str, float]:
    expected_set = {normalize_text(value) for value in expected if value}
    predicted_set = {normalize_text(value) for value in predicted if value}
    true_positives = len(expected_set & predicted_set)
    precision = (
        true_positives / len(predicted_set)
        if predicted_set
        else float(not expected_set)
    )
    recall = (
        true_positives / len(expected_set) if expected_set else float(not predicted_set)
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def percentile(values: Sequence[float], proportion: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile of no values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * proportion
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_interval(
    items: Sequence[object],
    statistic: Callable[[Sequence[object]], float],
    *,
    iterations: int = 2000,
    seed: int = 20260915,
) -> tuple[float, float]:
    if not items:
        raise ValueError("bootstrap requires at least one item")
    generator = random.Random(seed)
    estimates = [
        statistic([generator.choice(items) for _ in items]) for _ in range(iterations)
    ]
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def cluster_bootstrap_interval(
    items: Sequence[object],
    group_key: Callable[[object], str],
    statistic: Callable[[Sequence[object]], float],
    *,
    iterations: int = 2000,
    seed: int = 20260915,
) -> tuple[float, float]:
    groups: dict[str, list[object]] = {}
    for item in items:
        groups.setdefault(group_key(item), []).append(item)
    if not groups:
        raise ValueError("cluster bootstrap requires at least one group")
    group_names = sorted(groups)
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(iterations):
        sample: list[object] = []
        for _ in group_names:
            sample.extend(groups[generator.choice(group_names)])
        estimates.append(statistic(sample))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def tagged_text_without_markers(text: str) -> str:
    return re.sub(r"\[\[/?EN\]\]", "", text, flags=re.IGNORECASE)
