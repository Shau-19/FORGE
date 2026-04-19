"""agents/prd_agent.py — PRD Generator Agent"""
from agents.base import BaseAgent
from agents.state import ForgeState
from core import prompts


class PRDAgent(BaseAgent):
    name = "prd"

    def run(self, state: ForgeState) -> dict:
        idea       = state["idea"]
        audience   = state.get("audience", "General")
        stack      = state.get("stack", [])
        sections   = state.get("sections", ["overview", "features", "stories", "tech"])
        kb_context = state.get("kb_context")

        if len(idea) < 5:
            raise ValueError("idea too short")

        system, user = prompts.generate_prd(idea, audience, stack, sections,
                                            kb_context=kb_context)
        result = self.llm_call(user, system=system, max_tokens=1600)
        parsed = self.parse_json(result["text"])

        sections_out = {k: str(v) for k, v in parsed.items() if k in sections and v}

        return {
            "prd": {
                "sections":   sections_out,
                "model":      result["model"],
                "provider":   result["provider"],
                "latency_ms": result["latency_ms"],
            },
            "_tokens": result["tokens_used"],
        }


class PRDRefineAgent(BaseAgent):
    name = "prd_refine"

    def run(self, state: ForgeState) -> dict:
        section_key     = state.get("section_key", "")
        section_label   = state.get("section_label", section_key.upper())
        current_content = state.get("current_content", "")
        instruction     = state.get("instruction", "")
        kb_context      = state.get("kb_context")

        if not instruction:
            raise ValueError("instruction required")

        system, user = prompts.refine_prd_section(
            section_label, current_content, instruction, kb_context=kb_context
        )
        result = self.llm_call(user, system=system, max_tokens=700)

        return {
            "refined_content": result["text"],
            "section_key":     section_key,
            "_tokens":         result["tokens_used"],
        }