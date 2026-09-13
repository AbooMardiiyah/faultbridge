"""Load labelled synthetic state for the repeatable hackathon demonstration."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def put_json(url: str, api_key: str, payload: dict[str, object]) -> None:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Internal-API-Key": api_key,
        },
        method="PUT",
    )
    with urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"demo seed failed with HTTP {response.status}")


def main() -> None:
    api_key = os.environ.get("FAULTBRIDGE_INTERNAL_API_KEY")
    if not api_key:
        raise SystemExit("FAULTBRIDGE_INTERNAL_API_KEY is required")
    base_url = os.environ.get(
        "FAULTBRIDGE_DEMO_BASE_URL", "http://127.0.0.1:8010"
    ).rstrip("/")
    verified_at = datetime.now(UTC).replace(microsecond=0)
    restoration = (verified_at + timedelta(hours=2)).replace(minute=30, second=0)

    incident = {
        "operator": "FaultBridge Demo Network",
        "cell_id": "EVAL-002",
        "area": "Evaluation Area 02",
        "fault_type": "fibre cut",
        "status": "active",
        "cause": "confirmed third-party road works",
        "estimated_restoration": restoration.isoformat(),
        "source_system": "synthetic-demo-noc",
        "source_reference": "DEMO-ALARM-002",
        "verified_at": verified_at.isoformat(),
    }
    account = {
        "caller_id": "08030000002",
        "data_balance_mb": 2048,
        "barred": False,
        "compensation_eligible": True,
        "source_system": "synthetic-demo-crm",
        "source_reference": "DEMO-SUBSCRIBER-002",
        "verified_at": verified_at.isoformat(),
    }

    try:
        put_json(
            f"{base_url}/internal/network-incidents/DEMO-FIBRE-002",
            api_key,
            incident,
        )
        put_json(f"{base_url}/internal/accounts", api_key, account)
    except (HTTPError, URLError, TimeoutError) as error:
        raise SystemExit(
            f"Could not seed the running FaultBridge API: {error}"
        ) from error

    print("Synthetic demo state is ready for EVAL-002 and 08030000002.")
    print(f"Restoration estimate: {restoration.isoformat()} (displayed in WAT)")


if __name__ == "__main__":
    main()
