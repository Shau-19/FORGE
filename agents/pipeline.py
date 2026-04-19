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
    kb_context flows through state and is injected into
    validator, prd, and scaffold agents when provided.
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
        graph = StateGraph(ForgeState)
        graph.add_node("validator", self._agents["validator"])
        graph.add_node("prd",       self._agents["prd"])
        graph.add_node("scaffold",  self._agents["scaffold"])
        graph.add_node("checklist", self._agents["checklist"])
        graph.set_entry_point("validator")
        graph.add_edge("validator", "prd")
        graph.add_edge("prd",       "scaffold")
        graph.add_edge("scaffold",  "checklist")
        graph.add_edge("checklist", END)
        return graph.compile()

    def _default_state(self, overrides: dict) -> ForgeState:
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
            # KB injection — passed from frontend when "Inject into Agents" is ON
            "kb_context":    overrides.get("kb_context"),
            **{k: v for k, v in overrides.items() if k not in ForgeState.__annotations__},
        }

    def run_full(self, inputs: dict) -> ForgeState:
        state = self._default_state(inputs)
        return self._graph.invoke(state)

    def run_agent(self, agent_name: str, inputs: dict) -> dict:
        if agent_name not in self._agents:
            raise ValueError(f"Unknown agent: {agent_name}. Available: {list(self._agents.keys())}")
        agent  = self._agents[agent_name]
        state  = self._default_state(inputs)
        for k, v in inputs.items():
            state[k] = v
        result = agent(state)
        return {k: v for k, v in result.items() if k not in state or result[k] != state.get(k)}

    def get_agent_names(self) -> list[str]:
        return list(self._agents.keys())


_pipeline: ForgePipeline | None = None

def get_pipeline() -> ForgePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ForgePipeline()
    return _pipeline