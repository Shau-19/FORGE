"""
agents/state.py — FORGE Pipeline State
"""
from typing import TypedDict, Optional, Any


class ForgeState(TypedDict):
    # ── Inputs ──────────────────────────────────────────────
    idea:       str
    audience:   str
    stack:      list[str]
    structure:  str
    sections:   list[str]

    # ── Agent outputs ────────────────────────────────────────
    validation: Optional[dict]
    prd:        Optional[dict]
    scaffold:   Optional[dict]
    checklist:  Optional[dict]
    cicd:       Optional[dict]

    # ── Pipeline metadata ────────────────────────────────────
    project_name:   str
    current_stage:  str
    completed:      list[str]
    errors:         list[str]
    tokens_total:   int
    cost_estimate:  float

    # ── Optional overrides ───────────────────────────────────
    github_token:   Optional[str]
    repo_url:       Optional[str]
    repo_name:      Optional[str]
    diagram_nodes:  Optional[list]
    diagram_edges:  Optional[list]

    # ── KB injection ─────────────────────────────────────────
    # Set by frontend when "Inject into Agents" toggle is ON.
    # Shape: { tree, tree_text, source, doc_id?, url? }
    kb_context:     Optional[dict]
