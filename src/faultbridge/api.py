from __future__ import annotations

import base64
import hmac
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from faultbridge.adapters.llm import AgentModelError
from faultbridge.adapters.registry import (
    ProviderConfigurationError,
    build_agent_model,
    build_stt,
    build_telephony,
    build_tts,
)
from faultbridge.adapters.sahara import SaharaError
from faultbridge.config import Settings
from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database
from faultbridge.services.privacy import pseudonymize_caller
from faultbridge.services.voice import VoicePipeline
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


class PlaybookRequest(BaseModel):
    issue_type: str = Field(min_length=2)
    title: str = Field(min_length=2)
    steps: list[str] = Field(min_length=1)
    language_pair: str | None = None
    operator: str | None = None
    device_os: str | None = None
    status: Literal["draft", "approved", "retired"]
    source_system: str = Field(min_length=2)
    source_reference: str = Field(min_length=2)
    verified_at: datetime
    version: int = Field(ge=1)


class OutboundCallRequest(BaseModel):
    phone_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    variables: dict[str, str] = Field(default_factory=dict)
    accent: Literal["pidgin", "english"] = "pidgin"
    gender: Literal["male", "female"] = "female"


class VoiceTurnResponse(BaseModel):
    transcript: str
    response_text: str
    response_audio_chunks_base64: list[str]
    call: dict


class CallerDeletionRequest(BaseModel):
    caller_id: str = Field(min_length=3)


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
logger = logging.getLogger("faultbridge.api")
static_directory = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=static_directory), name="assets")


@app.exception_handler(SaharaError)
async def sahara_failure(_, error: SaharaError) -> JSONResponse:
    logger.warning("sahara_provider_failure type=%s", type(error).__name__)
    return JSONResponse(
        status_code=502,
        content={"detail": "Sahara voice service is temporarily unavailable"},
    )


@app.exception_handler(AgentModelError)
async def agent_model_failure(_, error: AgentModelError) -> JSONResponse:
    logger.warning("agent_provider_failure type=%s", type(error).__name__)
    return JSONResponse(
        status_code=502,
        content={"detail": "Agent reasoning service is temporarily unavailable"},
    )


@app.middleware("http")
async def operational_headers(request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    logger.info(
        "request_complete method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.monotonic() - started) * 1000,
        request_id,
    )
    return response


@app.get("/", include_in_schema=False)
def dashboard_page() -> FileResponse:
    return FileResponse(static_directory / "index.html")


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


@app.put("/internal/playbooks")
def upsert_playbook(request: PlaybookRequest, _: InternalAccess) -> dict[str, str]:
    playbook_id = database.upsert_playbook(request.model_dump())
    return {"playbook_id": playbook_id, "status": "accepted"}


@app.delete("/internal/caller-data")
def delete_caller_data(
    request: CallerDeletionRequest, _: InternalAccess
) -> dict[str, object]:
    caller_ref = pseudonymize_caller(
        request.caller_id,
        settings.faultbridge_pseudonym_secret.get_secret_value(),
    )
    deleted = database.delete_caller_data(caller_ref)
    return {"caller_ref": caller_ref, "deleted": deleted}


def voice_pipeline() -> VoicePipeline:
    try:
        return VoicePipeline(
            stt=build_stt(settings),
            tts=build_tts(settings),
            agent_model=build_agent_model(settings),
            orchestrator=orchestrator,
        )
    except ProviderConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/internal/voice/calls", response_model=VoiceTurnResponse)
async def start_voice_call(
    _: InternalAccess,
    caller_id: Annotated[str, Query(min_length=3)],
    area: Annotated[str, Query(min_length=2)],
    cell_id: Annotated[str, Query(min_length=2)],
    language_pair: Annotated[str, Query(min_length=2)],
    consent: bool,
    voice_language: str = "en",
    voice_accent: str = "pidgin",
    audio: bytes = Body(media_type="audio/L16", max_length=10 * 1024 * 1024),
) -> VoiceTurnResponse:
    result = await voice_pipeline().start_call(
        pcm16_audio=audio,
        caller_id=caller_id,
        area=area,
        cell_id=cell_id,
        default_language_pair=language_pair,
        consent=consent,
        voice_language=voice_language,
        voice_accent=voice_accent,
    )
    return VoiceTurnResponse(
        transcript=result.transcript,
        response_text=result.response_text,
        response_audio_chunks_base64=[
            base64.b64encode(chunk).decode("ascii")
            for chunk in result.response_audio_chunks
        ],
        call=result.call,
    )


@app.post("/internal/voice/calls/{call_id}/verify", response_model=VoiceTurnResponse)
async def verify_voice_call(
    call_id: str,
    _: InternalAccess,
    language_pair: Annotated[str, Query(min_length=2)],
    voice_language: str = "en",
    voice_accent: str = "pidgin",
    audio: bytes = Body(media_type="audio/L16", max_length=10 * 1024 * 1024),
) -> VoiceTurnResponse:
    try:
        result = await voice_pipeline().verify_call(
            pcm16_audio=audio,
            call_id=call_id,
            language_pair=language_pair,
            voice_language=voice_language,
            voice_accent=voice_accent,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="call session not found") from error
    return VoiceTurnResponse(
        transcript=result.transcript,
        response_text=result.response_text,
        response_audio_chunks_base64=[
            base64.b64encode(chunk).decode("ascii")
            for chunk in result.response_audio_chunks
        ],
        call=result.call,
    )


@app.post("/internal/outbound-calls/sahara")
async def launch_sahara_call(request: OutboundCallRequest, _: InternalAccess) -> dict:
    if settings.sahara_api_key is None or not settings.sahara_voicebot_workflow_id:
        raise HTTPException(status_code=503, detail="Sahara calling is not configured")
    try:
        transport = build_telephony(settings)
    except ProviderConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return await transport.start_call(
        request.phone_number,
        variables=request.variables,
        accent=request.accent,
        gender=request.gender,
    )


@app.post("/internal/text-calls")
def start_call(request: StartCallRequest, _: InternalAccess) -> dict:
    session = orchestrator.start_call(**request.model_dump())
    return asdict(session)


@app.post("/internal/text-calls/{call_id}/verify")
def verify_call(call_id: str, request: VerifyRequest, _: InternalAccess) -> dict:
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


@app.get("/internal/dashboard")
def dashboard(_: InternalAccess) -> dict:
    return database.dashboard_snapshot()
