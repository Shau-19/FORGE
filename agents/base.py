"""
agents/base.py — Base Agent Class
All FORGE agents inherit from this. Handles LLM calling, JSON parsing,
token tracking, and error handling in one place.
"""
import json
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm
from agents.state import ForgeState


class BaseAgent:
    """
    Base class for all FORGE pipeline agents.

    Subclasses must implement:
        - name: str          — agent identifier
        - run(state) -> dict — returns dict to merge into state
    """
    name: str = "base"

    def __call__(self, state: ForgeState) -> ForgeState:
        """LangGraph calls this. Wraps run() with error handling + token tracking."""
        try:
            updates = self.run(state)
            # Accumulate token usage
            tokens = updates.pop("_tokens", 0)
            new_total = state.get("tokens_total", 0) + tokens
            updates["tokens_total"] = new_total
            # Mark stage complete
            completed = list(state.get("completed", []))
            if self.name not in completed:
                completed.append(self.name)
            updates["completed"] = completed
            updates["current_stage"] = self.name
            return {**state, **updates}
        except Exception as e:
            errors = list(state.get("errors", []))
            errors.append(f"{self.name}: {str(e)}")
            return {**state, "errors": errors, "current_stage": self.name}

    def run(self, state: ForgeState) -> dict:
        """Override in each agent. Return dict of state updates."""
        raise NotImplementedError

    def llm_call(self, prompt: str, system: str = "", max_tokens: int = 1500) -> dict:
        """Convenience wrapper — returns result dict from core.llm."""
        return llm.call(prompt=prompt, system=system, max_tokens=max_tokens)

    def parse_json(self, text: str) -> dict:
        """Robust JSON parser — strips markdown fences, handles control chars."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Sanitize control characters inside strings
            result, in_str = [], False
            i = 0
            while i < len(text):
                c = text[i]
                if c == "\\" and in_str:
                    result.append(c)
                    if i + 1 < len(text):
                        result.append(text[i+1]); i += 2; continue
                elif c == '"':
                    in_str = not in_str; result.append(c)
                elif in_str and ord(c) < 32:
                    escapes = {"\n":"\\n","\r":"\\r","\t":"\\t"}
                    result.append(escapes.get(c, f"\\u{ord(c):04x}"))
                else:
                    result.append(c)
                i += 1
            return json.loads("".join(result))

    def clamp(self, v, lo=0, hi=100) -> int:
        try: return max(lo, min(hi, int(v)))
        except: return 50