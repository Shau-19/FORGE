
from langgraph.graph import StateGraph, END
from agents.state import ForgeState
from agents.validator import ValidatorAgent
from agents.prd_agent import PRDAgent, PRDRefineAgent
from agents.scaffold_agent import ScaffoldAgent
from agents.checklist_agent import ChecklistAgent, DoItAgent
from agents.cicd_agent import CICDAgent, CICDAutoFixAgent, DiagramAgent


class ForgePipeline:
    """
    FORGE multi-agent pipeline built on LangGraph.
    
    Graph structure:
    
        START
          │
          ▼
      [validator] ──► [prd] ──► [scaffold] ──► [checklist] ──► END
    
    Each node is a FORGE agent that reads from shared ForgeState
    and writes its output back into the same state object.
    """

    def __init__(self):
        self._agents = {
            "validator":    ValidatorAgent(),
            "prd":          PRDAgent(),
            "scaffold":     ScaffoldAgent(),
            "checklist":    ChecklistAgent(),
            "cicd":         CICDAgent(),
            "cicd_autofix": CICDAutoFixAgent(),
            "diagram":      DiagramAgent(),
            "prd_refine":   PRDRefineAgent(),
            "doit":         DoItAgent(),
        }
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph pipeline."""
        graph = StateGraph(ForgeState)

        # ── Add all pipeline nodes ──────────────────────────
        graph.add_node("validator", self._agents["validator"])
        graph.add_node("prd",       self._agents["prd"])
        graph.add_node("scaffold",  self._agents["scaffold"])
        graph.add_node("checklist", self._agents["checklist"])

        # ── Sequential edges ────────────────────────────────
        graph.set_entry_point("validator")
        graph.add_edge("validator", "prd")
        graph.add_edge("prd",       "scaffold")
        graph.add_edge("scaffold",  "checklist")
        graph.add_edge("checklist", END)

        return graph.compile()

    def _default_state(self, overrides: dict) -> ForgeState:
        """Build a full ForgeState with sensible defaults."""
        return {
            "idea":          overrides.get("idea", ""),
            "audience":      overrides.get("audience", "General"),
            "stack":         overrides.get("stack", []),
            "structure":     overrides.get("structure", "monorepo"),
            "sections":      overrides.get("sections", ["overview", "features", "stories", "tech"]),
            "validation":    None,
            "prd":           None,
            "scaffold":      None,
            "checklist":     None,
            "cicd":          None,
            "project_name":  overrides.get("project_name", ""),
            "current_stage": "idle",
            "completed":     [],
            "errors":        [],
            "tokens_total":  0,
            "cost_estimate": 0.0,
            "github_token":  overrides.get("github_token"),
            "repo_name":     overrides.get("repo_name"),
            "diagram_nodes": overrides.get("diagram_nodes"),
            "diagram_edges": overrides.get("diagram_edges"),
            **{k: v for k, v in overrides.items() if k not in ForgeState.__annotations__},
        }

    # ── Public API ──────────────────────────────────────────

    def run_full(self, inputs: dict) -> ForgeState:
        """
        Run the complete pipeline: validate → prd → scaffold → checklist.
        Returns the final state with all agent outputs.
        """
        state = self._default_state(inputs)
        return self._graph.invoke(state)

    def run_agent(self, agent_name: str, inputs: dict) -> dict:
        """
        Run a single agent by name. Used by the HTTP server
        to serve individual API endpoints.
        
        Returns the agent's output dict (not full state).
        """
        if agent_name not in self._agents:
            raise ValueError(f"Unknown agent: {agent_name}. Available: {list(self._agents.keys())}")

        agent  = self._agents[agent_name]
        state  = self._default_state(inputs)

        # Merge any extra inputs that aren't ForgeState keys
        for k, v in inputs.items():
            state[k] = v

        result = agent(state)

        # Return the diff — what the agent added/changed
        return {k: v for k, v in result.items() if k not in state or result[k] != state.get(k)}

    def get_agent_names(self) -> list[str]:
        return list(self._agents.keys())


# ── Singleton ────────────────────────────────────────────────
_pipeline: ForgePipeline | None = None

def get_pipeline() -> ForgePipeline:
    """Get or create the singleton pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = ForgePipeline()
    return _pipeline