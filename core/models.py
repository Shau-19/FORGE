"""
core/models.py
Pydantic models for all API request/response shapes.
Type safety + automatic FastAPI validation.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Validate ──────────────────────────────────────────────
class ValidateRequest(BaseModel):
    idea: str = Field(..., min_length=5, max_length=1000)
    audience: str = Field(default="General", max_length=200)


class ValidateMetrics(BaseModel):
    technical_feasibility: int
    revenue_potential: int
    time_to_market: int
    competitive_moat: int


class ValidateAnalysis(BaseModel):
    strength: str
    risk: str
    recommendation: str


class ValidateResponse(BaseModel):
    viability: int
    market: int
    risk: int
    metrics: ValidateMetrics
    analysis: ValidateAnalysis
    stack: list[str]
    tokens_used: int
    model: str
    provider: str
    latency_ms: int


# ── PRD ───────────────────────────────────────────────────
class PRDRequest(BaseModel):
    idea: str = Field(..., min_length=5, max_length=1000)
    audience: str = Field(default="General", max_length=200)
    stack: list[str] = Field(default_factory=list)
    sections: list[str] = Field(
        default=["overview", "features", "stories", "tech"]
    )


class PRDResponse(BaseModel):
    sections: dict[str, str]
    tokens_used: int
    model: str
    provider: str
    latency_ms: int


# ── PRD Refine ────────────────────────────────────────────
class PRDRefineRequest(BaseModel):
    section_key: str
    section_label: str
    current_content: str
    instruction: str = Field(..., min_length=3, max_length=500)


class PRDRefineResponse(BaseModel):
    section_key: str
    updated_content: str
    tokens_used: int


# ── Health ────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    version: str = "1.0"