from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from faultbridge.adapters.llm import OpenAICompatibleAgentModel
from faultbridge.domain.models import CallSession, Outcome, Tier
from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database, apply_migrations
from faultbridge.services.privacy import pseudonymize_caller, redact_text
from faultbridge.tools.telco import TelcoTools
from faultbridge_eval.agent_grader import grade_agent_trace
from faultbridge_eval.runner import environment_provenance

EFFECT_TABLES = (
    "call_sessions",
    "action_events",
    "complaint_signals",
    "candidate_incidents",
    "tickets",
    "compensation_commands",
    "callback_commands",
)


def require_evaluation_database() -> str:
    database_url = os.environ.get("EVALUATION_DATABASE_URL", "")
    runtime_url = os.environ.get("DATABASE_URL", "")
    if not database_url and runtime_url:
        parsed = urlparse(runtime_url)
        runtime_name = parsed.path.strip("/")
        database_url = parsed._replace(path=f"/{runtime_name}_eval").geturl()
    if not database_url:
        raise ValueError("EVALUATION_DATABASE_URL is required")
    database_name = urlparse(database_url).path.strip("/").lower()
    if not any(marker in database_name for marker in ("eval", "test")):
        raise ValueError("evaluation database name must contain 'eval' or 'test'")
    if database_url == runtime_url:
        raise ValueError("EVALUATION_DATABASE_URL must differ from DATABASE_URL")
    return database_url


def build_model(args: argparse.Namespace) -> OpenAICompatibleAgentModel:
    if args.agent_provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    else:
        key = os.environ.get("GROQ_API_KEY", "")
        base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    if not key:
        raise ValueError(f"{args.agent_provider.upper()} API key is required")
    return OpenAICompatibleAgentModel(
        api_key=key,
        model=args.agent_model,
        base_url=base_url,
        timeout_seconds=args.timeout_seconds,
    )


def reset_state(database: Database) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            TRUNCATE network_incidents, accounts, call_sessions,
                     troubleshooting_playbooks, candidate_incidents
            RESTART IDENTITY CASCADE
            """,
            prepare=False,
        )


def verified_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def seed_state(
    database: Database, seed: dict[str, Any], *, pseudonym_secret: str
) -> None:
    for incident in seed.get("incidents", []):
        database.upsert_incident(
            {
                "status": "active",
                "cause": None,
                "estimated_restoration": None,
                "source_system": "faultbridge-evaluation",
                "source_reference": str(incident["incident_id"]),
                **incident,
                "verified_at": verified_at(incident.get("verified_at")),
            }
        )
    for account in seed.get("accounts", []):
        payload = {
            "data_balance_mb": 100,
            "barred": False,
            "compensation_eligible": False,
            "source_system": "faultbridge-evaluation",
            "source_reference": "scenario-seed",
            **account,
            "verified_at": verified_at(account.get("verified_at")),
        }
        caller_id = payload.pop("caller_id", None)
        if caller_id:
            payload["caller_ref"] = pseudonymize_caller(caller_id, pseudonym_secret)
        database.upsert_account(payload)
    for playbook in seed.get("playbooks", []):
        database.upsert_playbook(
            {
                "language_pair": None,
                "operator": None,
                "device_os": None,
                "status": "approved",
                "source_system": "faultbridge-evaluation",
                "source_reference": "scenario-seed",
                "version": 1,
                **playbook,
                "verified_at": verified_at(playbook.get("verified_at")),
            }
        )
    for signal in seed.get("prior_signals", []):
        caller_ref = pseudonymize_caller(str(signal["caller_id"]), pseudonym_secret)
        session = CallSession(
            caller_ref=caller_ref,
            area=str(signal["area"]),
            cell_id=str(signal["cell_id"]).strip().upper(),
            language_pair=str(signal["language_pair"]),
            symptom=str(signal["symptom"]),
            safe_transcript="Seeded prior complaint signal.",
            consent=True,
            tier=Tier.COMPLETE,
            outcome=Outcome.ESCALATED,
            response="Seeded evaluation state.",
        )
        database.save_session(session)
        database.record_signal(
            session.call_id,
            caller_ref,
            session.cell_id,
            session.symptom,
            30,
        )


def observe(database: Database, session: Any) -> dict[str, Any]:
    with database.connect() as connection:
        effects = {
            table: int(
                connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()[
                    "count"
                ]
            )
            for table in EFFECT_TABLES
        }
    return {
        "call": {
            "call_id": session.call_id,
            "caller_ref": session.caller_ref,
            "area": session.area,
            "cell_id": session.cell_id,
            "language_pair": session.language_pair,
            "symptom": session.symptom,
            "safe_transcript": session.safe_transcript,
            "tier": session.tier.value,
            "outcome": session.outcome.value,
            "next_action": session.next_action,
            "response": session.response,
        },
        "events": database.list_events(session.call_id),
        "database_effects": effects,
        "candidates": database.list_candidates(),
    }


async def run_variant(
    scenario: dict[str, Any],
    variant: str,
    transcript: str,
    *,
    database: Database,
    model: OpenAICompatibleAgentModel,
    pseudonym_secret: str,
    repetition: int,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    reset_state(database)
    seed_state(database, scenario.get("seed", {}), pseudonym_secret=pseudonym_secret)
    inputs = scenario["input"]
    safe_transcript = redact_text(transcript)
    analysis = await model.analyze_complaint(
        safe_transcript,
        default_language_pair=inputs["language_pair"],
    )
    orchestrator = FaultBridgeOrchestrator(TelcoTools(database), pseudonym_secret)
    session = orchestrator.start_call(
        caller_id=inputs["caller_id"],
        transcript=safe_transcript,
        area=inputs["area"],
        cell_id=inputs["cell_id"],
        language_pair=analysis.language_pair,
        symptom=analysis.symptom,
        consent=bool(inputs["consent"]),
    )
    if "resolved" in inputs:
        session = orchestrator.verify_resolution(
            session, resolved=bool(inputs["resolved"])
        )
    observed = observe(database, session)
    observed["analysis"] = asdict(analysis)
    expected = {
        **scenario["expected"],
        **scenario.get("expected_by_variant", {}).get(variant, {}),
    }
    grade = grade_agent_trace(expected, observed)
    critical_expected = {
        **scenario["expected"].get("critical", {}),
        **scenario.get("expected_by_variant", {}).get(variant, {}).get("critical", {}),
    }
    critical_grade = (
        asdict(grade_agent_trace(critical_expected, observed))
        if critical_expected
        else None
    )
    return {
        "benchmark_version": "faultbridge-agent-v1",
        **provenance,
        "scenario_id": scenario["scenario_id"],
        "variant": variant,
        "repetition": repetition,
        "input_sha256": hashlib.sha256(transcript.encode()).hexdigest(),
        "analysis": asdict(analysis),
        "observed": observed,
        "grade": asdict(grade),
        "critical_grade": critical_grade,
    }


async def run(args: argparse.Namespace) -> None:
    database_url = require_evaluation_database()
    pseudonym_secret = os.environ.get("FAULTBRIDGE_PSEUDONYM_SECRET", "")
    if len(pseudonym_secret) < 32:
        raise ValueError(
            "FAULTBRIDGE_PSEUDONYM_SECRET must contain at least 32 characters"
        )
    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenario file must contain a non-empty JSON array")
    provenance = {
        **environment_provenance(args.scenarios),
        "agent_provider": args.agent_provider,
        "agent_model": args.agent_model,
    }
    completed: set[tuple[str, str, int]] = set()
    mode = "w"
    if args.output.is_file() and not args.overwrite:
        existing = [
            json.loads(line)
            for line in args.output.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for record in existing:
            for key in (
                "manifest_sha256",
                "code_commit",
                "lock_sha256",
                "agent_provider",
                "agent_model",
            ):
                if record.get(key) != provenance.get(key):
                    raise ValueError(
                        f"existing agent results use a different {key}; "
                        "pass --overwrite for a new benchmark run"
                    )
            completed.add(
                (
                    str(record["scenario_id"]),
                    str(record["variant"]),
                    int(record["repetition"]),
                )
            )
        mode = "a"
    model = build_model(args)
    apply_migrations(database_url, Path("migrations"))
    database = Database(database_url, min_size=1, max_size=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open(mode, encoding="utf-8") as stream:
            for scenario in scenarios:
                variants = {"gold": scenario["input"]["transcript"]}
                variants.update(scenario.get("hypotheses", {}))
                for variant, transcript in variants.items():
                    for repetition in range(1, args.repetitions + 1):
                        key = (str(scenario["scenario_id"]), variant, repetition)
                        if key in completed:
                            print(*key, "skipped")
                            continue
                        record = await run_variant(
                            scenario,
                            variant,
                            transcript,
                            database=database,
                            model=model,
                            pseudonym_secret=pseudonym_secret,
                            repetition=repetition,
                            provenance=provenance,
                        )
                        stream.write(json.dumps(record, default=str) + "\n")
                        print(
                            scenario["scenario_id"],
                            variant,
                            repetition,
                            "pass" if record["grade"]["passed"] else "fail",
                        )
    finally:
        database.close()


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Run gold and ASR transcripts through the real FaultBridge stack"
    )
    command.add_argument("--scenarios", type=Path, required=True)
    command.add_argument(
        "--output", type=Path, default=Path("eval/results/agent_runs.jsonl")
    )
    command.add_argument(
        "--agent-provider", choices=["openai", "groq"], default="openai"
    )
    command.add_argument("--agent-model", default="gpt-4.1-mini")
    command.add_argument("--timeout-seconds", type=float, default=30.0)
    command.add_argument("--repetitions", type=int, default=3)
    command.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing result log instead of resuming it",
    )
    return command


if __name__ == "__main__":
    asyncio.run(run(parser().parse_args()))
