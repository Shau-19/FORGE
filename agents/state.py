"""
agents/state.py — FORGE Pipeline State
Defines the shared state that flows through all LangGraph agent nodes.
"""
from typing import TypedDict, Optional, Any


class ForgeState(TypedDict):
    """
    Single shared state object passed between all pipeline agents.
    Each agent reads what it needs and writes its output back to state.
    """
    # ── Inputs ──────────────────────────────────────────────
    idea:       str                    # Raw product idea from user
    audience:   str                    # Target audience
    stack:      list[str]              # Tech stack (set by validator, used downstream)
    structure:  str                    # Scaffold structure: monorepo | separate | microservices
    sections:   list[str]              # PRD sections requested

    # ── Agent outputs ────────────────────────────────────────
    validation: Optional[dict]         # Output of ValidatorAgent
    prd:        Optional[dict]         # Output of PRDAgent
    scaffold:   Optional[dict]         # Output of ScaffoldAgent
    checklist:  Optional[dict]         # Output of ChecklistAgent
    cicd:       Optional[dict]         # Output of CICDAgent

    # ── Pipeline metadata ────────────────────────────────────
    project_name:   str                # Derived from idea
    current_stage:  str                # Which stage is active
    completed:      list[str]          # Which stages are done
    errors:         list[str]          # Any errors encountered
    tokens_total:   int                # Cumulative token usage
    cost_estimate:  float              # Estimated cost in USD

    # ── Optional overrides ───────────────────────────────────
    github_token:   Optional[str]
    repo_name:      Optional[str]
    diagram_nodes:  Optional[list]
    diagram_edges:  Optional[list]