"""
agents/checklist_agent.py — Launch Checklist Agent
Node 4 in the FORGE LangGraph pipeline.
"""
from agents.base import BaseAgent
from agents.state import ForgeState
from core import prompts


class ChecklistAgent(BaseAgent):
    name = "checklist"

    def run(self, state: ForgeState) -> dict:
        idea  = state["idea"]
        stack = state.get("stack", [])
        focus = state.get("focus", ["security", "performance", "seo", "devops"])

        if not idea:
            raise ValueError("idea required")

        system, user = prompts.generate_checklist(idea, stack, focus)
        result = self.llm_call(user, system=system, max_tokens=1000)
        parsed = self.parse_json(result["text"])

        items = [
            {
                "cat":    str(item.get("cat", "GENERAL")).upper(),
                "label":  str(item.get("label", "")),
                "done":   bool(item.get("done", False)),
                "detail": str(item.get("detail", "")),
            }
            for item in parsed.get("items", [])
        ]

        checklist = {
            "items":      items,
            "model":      result["model"],
            "provider":   result["provider"],
            "latency_ms": result["latency_ms"],
        }

        return {"checklist": checklist, "_tokens": result["tokens_used"]}


class DoItAgent(BaseAgent):
    """
    On-demand agent — generates step-by-step implementation guide
    for a specific checklist item. Not part of the main pipeline.
    """
    name = "doit"

    def run(self, state: ForgeState) -> dict:
        task   = state.get("task", "")
        cat    = state.get("cat", "")
        detail = state.get("detail", "")
        stack  = state.get("stack", [])
        idea   = state.get("idea", "web application")

        if not task:
            raise ValueError("task required")

        stack_str = ", ".join(stack) if stack else "general web stack"

        system = (
            "You are a senior software engineer and DevOps expert. "
            "You generate precise, actionable implementation guides. "
            "Return ONLY valid JSON — no prose, no markdown fences."
        )

        user = f"""Generate a step-by-step implementation guide for this task:

TASK: {task}
CATEGORY: {cat}
CONTEXT: {detail}
TECH STACK: {stack_str}
PROJECT: {idea}

Return this exact JSON structure:
{{
  "steps": [
    {{
      "title": "<short action title>",
      "detail": "<1-2 sentence explanation>",
      "command": "<optional shell command or empty string>"
    }}
  ],
  "code_snippet": "<relevant code example, 5-15 lines, or empty string>",
  "references": ["<doc or resource link>"],
  "estimated_time": "<e.g. 30 mins, 2-4 hours>"
}}

Rules:
- 4-7 concrete steps specific to the stack ({stack_str})
- Commands must be real and runnable
- Code snippet must be directly relevant
- No placeholders — real implementation details
- Return ONLY the JSON object"""

        result = self.llm_call(user, system=system, max_tokens=1200)
        parsed = self.parse_json(result["text"])

        return {
            "doit_result": {
                "steps":          parsed.get("steps", []),
                "code_snippet":   parsed.get("code_snippet", ""),
                "references":     parsed.get("references", []),
                "estimated_time": parsed.get("estimated_time", ""),
                "model":          result["model"],
                "provider":       result["provider"],
                "latency_ms":     result["latency_ms"],
            },
            "_tokens": result["tokens_used"],
        }