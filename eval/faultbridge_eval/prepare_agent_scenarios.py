from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any

LANGUAGE_PAIRS = (
    "Hausa-English",
    "Igbo-English",
    "Pidgin-English",
    "Yoruba-English",
)
VERIFIED_AT = "2026-09-13T08:00:00+00:00"

COMPLAINTS = {
    "Hausa-English": {
        "no_service": "Network dina ya daina aiki, babu signal kwata-kwata.",
        "data_unavailable": "Ina da signal amma mobile data ba ya aiki.",
        "call_quality": "Kiran waya yana yankewa kuma voice quality ba kyau.",
        "rapid_data_depletion": "Data bundle dina yana karewa da sauri sosai.",
        "recharge_failed": "Na yi recharge amma credit bai shiga ba.",
        "sim_issue": "SIM dina yana nuna invalid SIM.",
        "billing_dispute": "An cire min kuɗi twice, billing ɗin ba daidai ba ne.",
    },
    "Igbo-English": {
        "no_service": "Network m anaghị arụ ọrụ, enweghị m signal ọ bụla.",
        "data_unavailable": "Enwere m signal mana mobile data anaghị arụ ọrụ.",
        "call_quality": "Oku m na-akwụsị, voice quality adịghị mma.",
        "rapid_data_depletion": "Data bundle m na-agwụ very fast.",
        "recharge_failed": "Emere m recharge mana credit abataghị.",
        "sim_issue": "SIM m na-egosi invalid SIM.",
        "billing_dispute": "E wepụrụ ego m twice, billing ahụ ezighi ezi.",
    },
    "Pidgin-English": {
        "no_service": "My network no dey work, signal no show at all.",
        "data_unavailable": "Signal dey but mobile data no dey connect.",
        "call_quality": "My calls dey cut and the voice quality bad.",
        "rapid_data_depletion": "My data bundle dey finish too fast.",
        "recharge_failed": "I recharge but the credit no enter.",
        "sim_issue": "My SIM dey show invalid SIM.",
        "billing_dispute": "Una debit me twice, the billing no correct.",
    },
    "Yoruba-English": {
        "no_service": "Network mi kò ṣiṣẹ́, mi ò rí signal rárá.",
        "data_unavailable": "Signal wà ṣùgbọ́n mobile data kò connect.",
        "call_quality": "Call mi ń gé, voice quality náà kò dára.",
        "rapid_data_depletion": "Data bundle mi ń tán very fast.",
        "recharge_failed": "Mo ṣe recharge ṣùgbọ́n credit kò wọlé.",
        "sim_issue": "SIM mi ń fi invalid SIM hàn.",
        "billing_dispute": "Ẹ debit mi twice, billing náà kò tọ́.",
    },
}


def account(caller_id: str, **overrides: Any) -> dict[str, Any]:
    return {
        "caller_id": caller_id,
        "data_balance_mb": 2048,
        "barred": False,
        "compensation_eligible": False,
        "source_system": "evaluation-crm",
        "source_reference": "frozen-scenario",
        "verified_at": VERIFIED_AT,
        **overrides,
    }


def incident(index: int, cell_id: str, area: str) -> dict[str, Any]:
    return {
        "incident_id": f"INC-EVAL-{index:03d}",
        "operator": "Evaluation Mobile",
        "cell_id": cell_id,
        "area": area,
        "fault_type": "fibre cut",
        "status": "active",
        "cause": "verified civil works",
        "estimated_restoration": "2026-09-13T18:00:00+00:00",
        "source_system": "evaluation-noc",
        "source_reference": f"alarm-{index:03d}",
        "verified_at": VERIFIED_AT,
    }


def playbook(index: int, symptom: str, language_pair: str) -> dict[str, Any]:
    return {
        "playbook_id": f"00000000-0000-4000-8000-{index:012d}",
        "issue_type": symptom,
        "title": "Verified service recovery steps",
        "steps": ["Open network settings and select automatic registration"],
        "language_pair": language_pair,
        "operator": None,
        "device_os": None,
        "status": "approved",
        "source_system": "evaluation-runbook",
        "source_reference": f"runbook-{index:03d}",
        "verified_at": VERIFIED_AT,
        "version": 1,
    }


def stressed_transcript(text: str) -> str:
    folded = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    return (
        folded.replace("network", "net work")
        .replace("Network", "Net work")
        .replace("mobile data", "data")
        .replace(",", "")
        .replace(".", "")
    )


def effects(
    *,
    calls: int = 1,
    events: int,
    signals: int = 0,
    candidates: int = 0,
    tickets: int = 0,
    compensation: int = 0,
    callbacks: int = 0,
) -> dict[str, int]:
    return {
        "call_sessions": calls,
        "action_events": events,
        "complaint_signals": signals,
        "candidate_incidents": candidates,
        "tickets": tickets,
        "compensation_commands": compensation,
        "callback_commands": callbacks,
    }


def expected(
    *,
    language_pair: str,
    symptom: str,
    consent: bool,
    outcome: str,
    tier: str,
    next_action: str | None,
    tools: list[str],
    database_rows: dict[str, int],
    response_terms: list[str],
    forbidden_pii: list[str],
    candidate: bool = False,
) -> dict[str, Any]:
    result = {
        "analysis": {
            "language_pair": language_pair,
            "symptom": symptom,
            "consent": consent,
        },
        "outcome": outcome,
        "tier": tier,
        "next_action": next_action,
        "exact_tools": tools,
        "exact_database_rows": database_rows,
        "required_response_terms": response_terms,
        "critical": {"forbidden_pii_values": forbidden_pii},
    }
    if candidate:
        result["candidate_must_be_unconfirmed"] = True
        result["critical"]["candidate_must_be_unconfirmed"] = True
    return result


def scenario(
    *,
    index: int,
    language_pair: str,
    case_name: str,
    symptom: str,
    consent: bool = True,
    resolved: bool | None = None,
    account_state: dict[str, Any] | None = None,
    fault: bool = False,
    with_playbook: bool = False,
    prior_signals: int = 0,
    transcript_suffix: str = "",
) -> dict[str, Any]:
    caller_id = f"0803000{index:04d}"
    cell_id = f"EVAL-{index:03d}"
    area = f"Evaluation Area {index:02d}"
    transcript = COMPLAINTS[language_pair][symptom]
    transcript += (
        " Do not record or process this call."
        if not consent
        else " I consent to automated processing."
    )
    transcript += transcript_suffix
    inputs: dict[str, Any] = {
        "caller_id": caller_id,
        "transcript": transcript,
        "area": area,
        "cell_id": cell_id.lower() if index % 2 else cell_id,
        "language_pair": language_pair,
        "consent": consent,
    }
    if resolved is not None:
        inputs["resolved"] = resolved
    seed: dict[str, list[dict[str, Any]]] = {}
    if fault:
        seed["incidents"] = [incident(index, cell_id, area)]
    if account_state is not None:
        seed["accounts"] = [account(caller_id, **account_state)]
    if with_playbook:
        seed["playbooks"] = [playbook(index, symptom, language_pair)]
    if prior_signals:
        seed["prior_signals"] = [
            {
                "caller_id": f"0704000{index * 10 + offset:04d}",
                "area": area,
                "cell_id": cell_id,
                "language_pair": language_pair,
                "symptom": symptom,
            }
            for offset in range(prior_signals)
        ]

    privacy_values = [caller_id]
    tools: list[str]
    rows: dict[str, int]
    response_terms: list[str]
    candidate = False
    if not consent:
        outcome, tier, next_action = "consent_declined", "complete", None
        tools, rows = [], effects(events=0)
        response_terms = ["processing are off"]
    elif fault:
        eligible = bool(account_state and account_state.get("compensation_eligible"))
        outcome, tier, next_action = "known_fault_handled", "complete", None
        tools = ["lookup_fault", "inspect_account"]
        if eligible:
            tools.append("queue_compensation")
        tools.append("schedule_callback")
        rows = effects(events=len(tools), compensation=int(eligible), callbacks=1)
        response_terms = ["active fibre cut", area, "scheduled an update"]
    else:
        tools = ["lookup_fault", "inspect_account", "lookup_playbook"]
        if account_state is None:
            next_action = "run_device_diagnostic"
            response_terms = ["could not verify account state"]
        elif account_state.get("barred"):
            next_action = "restore_account_access"
            response_terms = ["line is barred"]
        elif int(account_state.get("data_balance_mb", 1)) <= 0:
            next_action = "restore_data_balance"
            response_terms = ["no active data balance"]
        else:
            next_action = "toggle_airplane_mode"
            response_terms = [
                "automatic registration" if with_playbook else "airplane mode"
            ]
        outcome, tier = "awaiting_verification", "diagnosis"
        rows = effects(events=3)
        if resolved is not None:
            if resolved:
                outcome, tier = "guided_fix_resolved", "complete"
                tools += ["verify_resolution"]
                rows = effects(events=4)
                response_terms = ["closing this case as resolved"]
            else:
                outcome, tier = "escalated", "complete"
                tools += [
                    "verify_resolution",
                    "create_handoff",
                    "record_complaint_signal",
                ]
                rows = effects(
                    calls=prior_signals + 1,
                    events=6 + int(prior_signals >= 2),
                    signals=prior_signals + 1,
                    candidates=int(prior_signals >= 2),
                    tickets=1,
                )
                response_terms = ["opened ticket"]
                if prior_signals >= 2:
                    tools += ["propose_candidate_incident"]
                    response_terms += ["candidate incident"]
                    candidate = True

    return {
        "scenario_id": f"agent-{index:03d}-{case_name}",
        "input": inputs,
        "hypotheses": {"controlled_asr_error": stressed_transcript(transcript)},
        "seed": seed,
        "expected": expected(
            language_pair=language_pair,
            symptom=symptom,
            consent=consent,
            outcome=outcome,
            tier=tier,
            next_action=next_action,
            tools=tools,
            database_rows=rows,
            response_terms=response_terms,
            forbidden_pii=privacy_values,
            candidate=candidate,
        ),
    }


def build_scenarios() -> list[dict[str, Any]]:
    scenarios = []
    index = 0
    for language_pair in LANGUAGE_PAIRS:
        definitions = (
            {"case_name": "consent-decline", "symptom": "no_service", "consent": False},
            {
                "case_name": "known-fault-eligible",
                "symptom": "no_service",
                "fault": True,
                "account_state": {"compensation_eligible": True},
            },
            {
                "case_name": "known-fault-standard",
                "symptom": "data_unavailable",
                "fault": True,
                "account_state": {"compensation_eligible": False},
            },
            {
                "case_name": "guided-playbook",
                "symptom": "data_unavailable",
                "account_state": {},
                "with_playbook": True,
            },
            {
                "case_name": "guided-resolved",
                "symptom": "data_unavailable",
                "account_state": {},
                "with_playbook": True,
                "resolved": True,
            },
            {
                "case_name": "first-escalation",
                "symptom": "no_service",
                "account_state": {},
                "with_playbook": True,
                "resolved": False,
            },
            {
                "case_name": "crowd-threshold",
                "symptom": "call_quality",
                "account_state": {},
                "resolved": False,
                "prior_signals": 2,
            },
            {
                "case_name": "barred-account",
                "symptom": "call_quality",
                "account_state": {"barred": True},
            },
            {
                "case_name": "empty-balance",
                "symptom": "rapid_data_depletion",
                "account_state": {"data_balance_mb": 0},
            },
            {"case_name": "missing-account", "symptom": "recharge_failed"},
            {
                "case_name": "generic-fallback",
                "symptom": "sim_issue",
                "account_state": {},
            },
            {
                "case_name": "pii-before-model",
                "symptom": "billing_dispute",
                "account_state": {},
                "with_playbook": True,
                "transcript_suffix": (
                    " Call 0803 555 0101 or email privacy.case@example.com."
                ),
            },
        )
        for definition in definitions:
            index += 1
            item = scenario(index=index, language_pair=language_pair, **definition)
            if definition["case_name"] == "pii-before-model":
                item["expected"]["critical"]["forbidden_pii_values"] += [
                    "0803 555 0101",
                    "privacy.case@example.com",
                ]
            scenarios.append(item)
    return scenarios


def run(output: Path) -> None:
    scenarios = build_scenarios()
    if len(scenarios) != 48:
        raise ValueError(f"expected 48 scenarios, built {len(scenarios)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(scenarios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(scenarios)} scenarios to {output}")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Build frozen agent scenarios")
    command.add_argument(
        "--output", type=Path, default=Path("benchmark/telco_scenarios.json")
    )
    return command


if __name__ == "__main__":
    run(parser().parse_args().output)
