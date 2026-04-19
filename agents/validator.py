
"""agents/validator.py — Idea Validator Agent"""
import re
from agents.base import BaseAgent
from agents.state import ForgeState
from core import prompts


class ValidatorAgent(BaseAgent):
    name = "validator"

    def run(self, state: ForgeState) -> dict:
        idea       = state["idea"].strip()
        audience   = state.get("audience", "General") or "General"
        kb_context = state.get("kb_context")  # injected if toggle ON

        if len(idea) < 5:
            raise ValueError("Idea must be at least 5 characters")

        system, user = prompts.validate_idea(idea, audience, kb_context=kb_context)
        result = self.llm_call(user, system=system, max_tokens=900)
        p = self.parse_json(result["text"])

        m = p.get("metrics", {})
        a = p.get("analysis", {})
        stack = list(p.get("stack", ["FastAPI", "Python"]))[:8]

        project_name = "-".join(idea.split()[:3]).lower()
        project_name = re.sub(r"[^a-z0-9-]", "", project_name)

        validation = {
            "viability": self.clamp(p.get("viability", 70)),
            "market":    self.clamp(p.get("market", 65)),
            "risk":      self.clamp(p.get("risk", 50)),
            "metrics": {
                "technical_feasibility": self.clamp(m.get("technical_feasibility", 70)),
                "revenue_potential":     self.clamp(m.get("revenue_potential", 65)),
                "time_to_market":        self.clamp(m.get("time_to_market", 60)),
                "competitive_moat":      self.clamp(m.get("competitive_moat", 55)),
            },
            "analysis": {
                "strength":       str(a.get("strength", "Strong value proposition.")),
                "risk":           str(a.get("risk", "Execution complexity.")),
                "recommendation": str(a.get("recommendation", "Build a focused MVP.")),
            },
            "stack":      stack,
            "model":      result["model"],
            "provider":   result["provider"],
            "latency_ms": result["latency_ms"],
        }

        return {
            "validation":   validation,
            "stack":        stack,
            "project_name": project_name,
            "_tokens":      result["tokens_used"],
        }