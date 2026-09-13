from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database, apply_migrations
from faultbridge.services.privacy import redact_text
from faultbridge.tools.telco import TelcoTools
from faultbridge_eval.agent_grader import grade_agent_trace
from faultbridge_eval.agent_runner import (
    observe,
    require_evaluation_database,
    reset_state,
    seed_state,
)


def validate(scenario: dict[str, Any], database: Database, secret: str) -> list[str]:
    reset_state(database)
    seed_state(database, scenario.get("seed", {}), pseudonym_secret=secret)
    inputs = scenario["input"]
    analysis = scenario["expected"]["analysis"]
    orchestrator = FaultBridgeOrchestrator(TelcoTools(database), secret)
    session = orchestrator.start_call(
        caller_id=inputs["caller_id"],
        transcript=redact_text(inputs["transcript"]),
        area=inputs["area"],
        cell_id=inputs["cell_id"],
        language_pair=analysis["language_pair"],
        symptom=analysis["symptom"],
        consent=inputs["consent"],
    )
    if "resolved" in inputs:
        session = orchestrator.verify_resolution(session, resolved=inputs["resolved"])
    observed = observe(database, session)
    observed["analysis"] = analysis
    failures = list(grade_agent_trace(scenario["expected"], observed).failures)
    critical = scenario["expected"].get("critical", {})
    if critical:
        failures.extend(grade_agent_trace(critical, observed).failures)
    return failures


def run(args: argparse.Namespace) -> None:
    database_url = require_evaluation_database()
    secret = os.environ.get("FAULTBRIDGE_PSEUDONYM_SECRET", "")
    if len(secret) < 32:
        raise ValueError(
            "FAULTBRIDGE_PSEUDONYM_SECRET must contain at least 32 characters"
        )
    apply_migrations(database_url, Path("migrations"))
    database = Database(database_url, min_size=1, max_size=2)
    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
    failures: list[str] = []
    try:
        for scenario in scenarios:
            failures.extend(
                f"{scenario['scenario_id']}: {failure}"
                for failure in validate(scenario, database, secret)
            )
    finally:
        database.close()
    if failures:
        raise SystemExit("Scenario validation failed:\n" + "\n".join(failures))
    print(f"Validated {len(scenarios)} scenario oracles against the real policy stack")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Validate agent scenario oracles")
    command.add_argument(
        "--scenarios", type=Path, default=Path("benchmark/telco_scenarios.json")
    )
    return command


if __name__ == "__main__":
    run(parser().parse_args())
