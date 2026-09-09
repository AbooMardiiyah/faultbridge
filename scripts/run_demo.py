from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database
from faultbridge.tools.telco import TelcoTools


def main() -> None:
    database = Database(":memory:")
    database.initialize()
    faults = json.loads(Path("data/faults.json").read_text())
    database.seed_faults(faults)
    agent = FaultBridgeOrchestrator(
        TelcoTools(database, signal_threshold=3),
        "demo-secret-at-least-16-characters",
    )

    known = agent.start_call(
        caller_id="08031234567",
        transcript="Network no dey work. My number na 08031234567.",
        area="Tarauni, Kano",
        cell_id="KANO-014",
        language_pair="Hausa-English",
        symptom="no_service",
        consent=True,
    )
    print("KNOWN FAULT")
    print(json.dumps(asdict(known), indent=2, default=str))

    for index in range(3):
        session = agent.start_call(
            caller_id=f"0804000000{index}",
            transcript="Data no gree connect; account number AB12345678.",
            area="Bodija, Ibadan",
            cell_id="IBD-207",
            language_pair="Yoruba-English",
            symptom="data_unavailable",
            consent=True,
        )
        agent.verify_resolution(session, resolved=False)
        print(f"\nUNKNOWN FAULT CALL {index + 1}")
        print(json.dumps(asdict(session), indent=2, default=str))

    print("\nCANDIDATE INCIDENTS")
    print(json.dumps(database.list_candidates(), indent=2))


if __name__ == "__main__":
    main()

