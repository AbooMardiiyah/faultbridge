from __future__ import annotations

import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from faultbridge.domain.models import CallSession
from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database
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


database = Database(os.getenv("FAULTBRIDGE_DB_PATH", "data/faultbridge.db"))
database.initialize()
tools = TelcoTools(database)
orchestrator = FaultBridgeOrchestrator(
    tools,
    os.getenv("FAULTBRIDGE_PSEUDONYM_SECRET", "development-secret-change-me"),
)
sessions: dict[str, CallSession] = {}

app = FastAPI(
    title="FaultBridge",
    description="Evidence-bound telco fault resolution and discovery agent",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/calls")
def start_call(request: StartCallRequest) -> dict:
    session = orchestrator.start_call(**request.model_dump())
    sessions[session.call_id] = session
    return asdict(session)


@app.post("/calls/{call_id}/verify")
def verify_call(call_id: str, request: VerifyRequest) -> dict:
    session = sessions.get(call_id)
    if session is None:
        raise HTTPException(status_code=404, detail="call session not found")
    try:
        orchestrator.verify_resolution(session, resolved=request.resolved)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return asdict(session)


@app.get("/calls/{call_id}/events")
def call_events(call_id: str) -> list[dict]:
    return database.list_events(call_id)


@app.get("/candidate-incidents")
def candidate_incidents() -> list[dict]:
    return database.list_candidates()
