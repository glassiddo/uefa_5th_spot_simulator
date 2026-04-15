"""FastAPI app for serving the simulator data and frontend shell."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from .data import load_dataset
from .simulation import MatchOverride, simulate

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_INDEX = BASE_DIR / "frontend" / "index.html"

app = FastAPI(title="UEFA 5th Spot Simulator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class OverridePayload(BaseModel):
    competition: str = Field(..., description="UCL, UEL, or UECL")
    round_name: str = Field(..., description="Tie round label")
    team1: str
    team2: str
    leg: int = Field(..., ge=1, le=2)
    home_score: int | None = Field(default=None, ge=0)
    away_score: int | None = Field(default=None, ge=0)
    advancer: str | None = None


class SimulationPayload(BaseModel):
    overrides: list[OverridePayload] = Field(default_factory=list)


@app.get("/")
def read_root():
    """Serve the frontend entry point if it exists."""
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return HTMLResponse(
        "<!doctype html><html><body><h1>UEFA 5th Spot Simulator</h1></body></html>"
    )


@app.get("/api/data")
def api_data():
    """Return the current fixture snapshot."""
    return load_dataset()


@app.post("/api/simulate")
def api_simulate(payload: SimulationPayload):
    """Simulate the current snapshot with optional user overrides."""
    snapshot = load_dataset()
    overrides = [
        MatchOverride(
            competition=item.competition,
            round_name=item.round_name,
            team1=item.team1,
            team2=item.team2,
            leg=item.leg,
            home_score=item.home_score,
            away_score=item.away_score,
            advancer=item.advancer,
        )
        for item in payload.overrides
    ]
    return jsonable_encoder(simulate(snapshot, overrides))
