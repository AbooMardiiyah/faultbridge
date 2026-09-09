from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from faultbridge.config import Settings
from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database
from faultbridge.services.privacy import pseudonymize_caller
from faultbridge.tools.telco import TelcoTools


class StartCallRequest(BaseModel):
    caller_id: str = Field(min_length=3)
    transcript: str = Field(min_length=1)
    area: str = Field(min_length=2)
    cell_id: str = Field(min_length=2)
    language_pair: str = Field(min_length=2)
    symptom: str = Field(min_length=2)
    consent: bool


class VerifyRequest(BaseModel):
    resolved: bool


class NetworkIncidentRequest(BaseModel):
    operator: str = Field(min_length=2)
    cell_id: str = Field(min_length=2)
    area: str = Field(min_length=2)
    fault_type: str = Field(min_length=2)
    status: Literal["active", "resolved", "cancelled"]
    cause: str | None = None
    estimated_restoration: datetime | None = None
    source_system: str = Field(min_length=2)
    source_reference: str = Field(min_length=2)
    verified_at: datetime


class AccountRequest(BaseModel):
    caller_id: str = Field(min_length=3)
    data_balance_mb: int = Field(ge=0)
    barred: bool
    compensation_eligible: bool
    source_system: str = Field(min_length=2)
    source_reference: str = Field(min_length=2)
    verified_at: datetime


settings = Settings()
database = Database(settings.database_url)
tools = TelcoTools(database)
orchestrator = FaultBridgeOrchestrator(
    tools, settings.faultbridge_pseudonym_secret.get_secret_value()
)


def require_internal_key(
    supplied_key: Annotated[str | None, Header(alias="X-Internal-API-Key")] = None,
) -> None:
    expected = settings.faultbridge_internal_api_key.get_secret_value()
    if supplied_key is None or not hmac.compare_digest(supplied_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal API key",
        )


InternalAccess = Annotated[None, Depends(require_internal_key)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    database.close()


app = FastAPI(
    title="FaultBridge",
    description="Evidence-bound telco fault resolution and discovery agent",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    if not database.is_ready():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}


@app.put("/internal/network-incidents/{incident_id}")
def upsert_network_incident(
    incident_id: str,
    request: NetworkIncidentRequest,
    _: InternalAccess,
) -> dict[str, str]:
    payload = request.model_dump()
    payload["incident_id"] = incident_id
    payload["cell_id"] = request.cell_id.strip().upper()
    database.upsert_incident(payload)
    return {"incident_id": incident_id, "status": "accepted"}


@app.put("/internal/accounts")
def upsert_account(request: AccountRequest, _: InternalAccess) -> dict[str, str]:
    caller_ref = pseudonymize_caller(
        request.caller_id,
        settings.faultbridge_pseudonym_secret.get_secret_value(),
    )
    payload = request.model_dump(exclude={"caller_id"})
    payload["caller_ref"] = caller_ref
    database.upsert_account(payload)
    return {"caller_ref": caller_ref, "status": "accepted"}


@app.post("/calls")
def start_call(request: StartCallRequest) -> dict:
    session = orchestrator.start_call(**request.model_dump())
    return asdict(session)


@app.post("/calls/{call_id}/verify")
def verify_call(call_id: str, request: VerifyRequest) -> dict:
    session = database.get_session(call_id)
    if session is None:
        raise HTTPException(status_code=404, detail="call session not found")
    try:
        orchestrator.verify_resolution(session, resolved=request.resolved)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return asdict(session)


@app.get("/internal/calls/{call_id}/events")
def call_events(call_id: str, _: InternalAccess) -> list[dict]:
    return database.list_events(call_id)


@app.get("/internal/candidate-incidents")
def candidate_incidents(_: InternalAccess) -> list[dict]:
    return database.list_candidates()
