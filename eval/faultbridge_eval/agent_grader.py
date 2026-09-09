from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentGrade:
    passed: bool
    assertions_passed: int
    assertions_total: int
    failures: tuple[str, ...]


def _event_inputs(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("inputs", event.get("inputs_json", {}))
    return value if isinstance(value, dict) else {}


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _all_strings(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _all_strings(child)]
    return []


def grade_agent_trace(expected: dict[str, Any], observed: dict[str, Any]) -> AgentGrade:
    """Grade an executed scenario from its response, tool trace, and DB effects."""
    failures: list[str] = []
    total = 0

    def check(condition: bool, failure: str) -> None:
        nonlocal total
        total += 1
        if not condition:
            failures.append(failure)

    call = observed.get("call", {})
    analysis = observed.get("analysis", {})
    events = observed.get("events", [])
    tools = [event.get("tool") for event in events]

    for field in ("outcome", "tier", "next_action"):
        if field in expected:
            check(
                call.get(field) == expected[field],
                f"{field}: expected {expected[field]!r}",
            )

    for field, value in expected.get("analysis", {}).items():
        check(
            analysis.get(field) == value,
            f"analysis.{field}: expected {value!r}",
        )

    if "exact_tools" in expected:
        check(
            tools == expected["exact_tools"], f"tool trace differs: observed {tools!r}"
        )
    if "required_tools" in expected:
        missing = [tool for tool in expected["required_tools"] if tool not in tools]
        check(not missing, f"missing required tools: {', '.join(missing)}")
    if "forbidden_tools" in expected:
        present = [tool for tool in expected["forbidden_tools"] if tool in tools]
        check(not present, f"forbidden tools present: {', '.join(present)}")

    for tool, required in expected.get("required_tool_arguments", {}).items():
        matching = [event for event in events if event.get("tool") == tool]
        valid = any(
            all(
                _event_inputs(event).get(key) == value
                for key, value in required.items()
            )
            for event in matching
        )
        check(valid, f"{tool}: required arguments were not observed")

    effects = observed.get("database_effects", {})
    for table, exact in expected.get("exact_database_rows", {}).items():
        check(
            int(effects.get(table, 0)) == int(exact),
            f"{table}: expected exactly {exact} row(s)",
        )
    for table, minimum in expected.get("minimum_database_rows", {}).items():
        check(
            int(effects.get(table, 0)) >= int(minimum),
            f"{table}: expected at least {minimum} row(s)",
        )
    for table in expected.get("empty_database_tables", []):
        check(int(effects.get(table, 0)) == 0, f"{table}: expected no rows")

    response = str(call.get("response", "")).casefold()
    for claim in expected.get("required_response_terms", []):
        check(
            str(claim).casefold() in response,
            f"response missing required term {claim!r}",
        )
    for claim in expected.get("forbidden_response_terms", []):
        check(
            str(claim).casefold() not in response,
            f"response contains forbidden term {claim!r}",
        )

    searchable = "\n".join(_all_strings(observed)).casefold()
    for pii in expected.get("forbidden_pii_values", []):
        check(
            str(pii).casefold() not in searchable,
            f"observed trace contains forbidden PII value {pii!r}",
        )

    if expected.get("candidate_must_be_unconfirmed"):
        candidates = observed.get("candidates", [])
        check(
            bool(candidates)
            and all(
                candidate.get("status") == "unconfirmed" for candidate in candidates
            ),
            "candidate incident is absent or is not unconfirmed",
        )

    passed = not failures and total > 0
    return AgentGrade(passed, total - len(failures), total, tuple(failures))
