"""
api/knowledge.py — POST /api/knowledge/generate
Generates Mermaid diagram syntax via LLM based on project context.
Supports: erd, class, sequence, flowchart, stateDiagram
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm


DIAGRAM_TYPES = {
    "erd":        "Entity Relationship Diagram",
    "class":      "Class Diagram (Low Level Design)",
    "sequence":   "Sequence Diagram",
    "flowchart":  "System Flowchart",
    "stateDiagram": "State Machine Diagram",
}


def _make_prompt(idea: str, stack: list, prd: dict, diagram_type: str) -> tuple[str, str]:
    stack_str = ", ".join(stack) if stack else "general web stack"
    prd_overview = ""
    if isinstance(prd, dict):
        secs = prd.get("sections", prd)
        prd_overview = secs.get("overview", "") or secs.get("features", "")
    prd_overview = prd_overview[:500] if prd_overview else ""

    system = (
        "You are a software architect and technical diagram expert. "
        "You generate precise, valid Mermaid diagram syntax. "
        "Return ONLY the raw Mermaid code — no markdown fences, no explanation, no ```mermaid wrapper. "
        "Start directly with the diagram type keyword (e.g. 'erDiagram', 'classDiagram', etc.). "
        "Make diagrams specific to the actual project — never generic placeholders."
    )

    type_label = DIAGRAM_TYPES.get(diagram_type, diagram_type)

    prompts = {
        "erd": f"""Generate a Mermaid erDiagram for this project.

PROJECT: {idea}
STACK: {stack_str}
CONTEXT: {prd_overview}

Rules:
- Use real entity names from the domain (e.g. Invoice, User, Payment — not generic Entity1)
- 4-7 entities with realistic field names and types (int, string, datetime, decimal, boolean)
- Include primary keys (PK) and foreign keys (FK) annotations
- Show realistic relationships: ||--o{{, }}|--|{{, ||--||, etc.
- Include relationship labels ("places", "contains", "belongs to", etc.)
- Reflect the actual tech stack and domain

- CRITICAL: Relationship labels must be single unquoted words or quoted single words only
- Wrong: USER ||--o{{ EMAIL : "belongs to"  |  Correct: USER ||--o{{ EMAIL : "has"
- Use short single words for labels: "has", "contains", "places", "owns", "includes"

Return ONLY valid Mermaid erDiagram syntax starting with 'erDiagram'""",

        "class": f"""Generate a Mermaid classDiagram for this project's backend architecture.

PROJECT: {idea}
STACK: {stack_str}
CONTEXT: {prd_overview}

Rules:
- 5-7 classes reflecting the actual architecture (Services, Controllers, Repositories, Models)
- Include attributes with types and methods with signatures
- Show inheritance (--|>), composition (--*), dependency (..>), association (--)
- Use real class names from the domain
- Include +/- visibility modifiers on members
- Reflect the stack: if FastAPI use Pydantic models, if Node use TypeScript interfaces, etc.

Return ONLY valid Mermaid classDiagram syntax starting with 'classDiagram'""",

        "sequence": f"""Generate a Mermaid sequenceDiagram showing the main user flow for this project.

PROJECT: {idea}
STACK: {stack_str}
CONTEXT: {prd_overview}

Rules:
- Show the most important end-to-end flow (e.g. user signup, core feature usage, payment)
- 4-7 participants: Browser/Client, API/Backend, Database, and relevant services (Auth, Stripe, etc.)
- Use real service names from the stack
- Include alt/opt/loop blocks where meaningful
- Show both success path and at least one error/failure case
- Use ->> for async, -->> for responses

Return ONLY valid Mermaid sequenceDiagram syntax starting with 'sequenceDiagram'""",

        "flowchart": f"""Generate a Mermaid flowchart TD showing the system architecture or main business process for this project.

PROJECT: {idea}
STACK: {stack_str}
CONTEXT: {prd_overview}

Rules:
- Show either: the request flow through system layers OR the main business process flow
- Use meaningful node labels (not A, B, C — use real names)
- Include decision diamonds where logic branches
- Group related nodes with subgraphs if the diagram has clear layers
- 8-15 nodes total for good readability
- Use -- labels on edges to explain transitions

Return ONLY valid Mermaid flowchart syntax starting with 'flowchart TD'""",

        "stateDiagram": f"""Generate a Mermaid stateDiagram-v2 showing the main entity state machine for this project.

PROJECT: {idea}
STACK: {stack_str}
CONTEXT: {prd_overview}

Rules:
- Pick the most important stateful entity (e.g. Order, Invoice, Task, User Account, Session)
- 5-8 states with realistic transition labels
- Include [*] for start and end states
- Do NOT use note statements — they cause parse errors
- Show parallel states if applicable (using -- inside state)
- Transitions should reflect real domain events ("submit", "approve", "reject", "expire", etc.)

- CRITICAL: Use --> for ALL transitions, NEVER use -- (double dash without arrow)
- Wrong: "Approved -- Scheduled" | Correct: "Approved --> Scheduled : process"

Return ONLY valid Mermaid stateDiagram-v2 syntax starting with 'stateDiagram-v2'""",
    }

    user = prompts.get(diagram_type, prompts["flowchart"])
    return system, user


def handle_knowledge_generate(body: dict) -> dict:
    idea         = body.get("idea", "").strip()
    stack        = body.get("stack", [])
    prd          = body.get("prd", {})
    diagram_type = body.get("diagram_type", "erd")

    if not idea:
        raise ValueError("idea required")
    if diagram_type not in DIAGRAM_TYPES:
        raise ValueError(f"diagram_type must be one of: {list(DIAGRAM_TYPES.keys())}")

    system, user = _make_prompt(idea, stack, prd, diagram_type)
    result = llm.call(prompt=user, system=system, max_tokens=1200)

    # Clean up — strip any markdown fences the model might have added anyway
    import re
    text = result["text"].strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop first line (```mermaid or ```) and last line (```)
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    text = text.strip()

    # Fix common LLM Mermaid syntax errors:
    # -->|label|>  ->  -->|label|  (spurious > after closing pipe)
    text = re.sub(r'(\|[^|\n]*)\|>', r'\1|', text)
    # -->>  ->  -->
    text = re.sub(r'-->>', '-->', text)
    # stateDiagram: "State -- label" (invalid) -> "State --> label"
    # Only fix lines that look like transitions (not note/class/[*] lines)
    if diagram_type == 'stateDiagram':
        fixed = []
        for line in text.split('\n'):
            stripped = line.strip()
            # Drop ALL note lines — LLMs consistently produce invalid note syntax
            # Valid form requires multi-line block; inline note always fails
            if stripped.startswith('note ') or stripped == 'end note':
                continue
            # Fix "State -- label" -> "State --> label" (LLM omits >)
            if (' -- ' in stripped and '-->' not in stripped):
                line = line.replace(' -- ', ' --> ')
            fixed.append(line)
        text = '\n'.join(fixed)
    # ERD: strip quoted relationship labels like |"belongs to"| -> |belongsTo|
    # Mermaid ERD only accepts unquoted alphanumeric relationship labels
    if diagram_type == 'erd':
        import re as _re
        def _fix_rel_label(m):
            label = m.group(1).strip('"\' ').replace(' ', '_')
            return f'"{label}"'
        # Fix quoted multi-word labels in relationship lines
        # e.g. USER ||--o{ EMAIL : "belongs to"  ->  USER ||--o{ EMAIL : "belongs_to"
        text = _re.sub(r': "([^"]+)"', lambda m: ': "' + m.group(1).replace(' ', '_') + '"', text)

    return {
        "mermaid":     text,
        "diagram_type": diagram_type,
        "type_label":  DIAGRAM_TYPES[diagram_type],
        "tokens_used": result["tokens_used"],
        "model":       result["model"],
        "provider":    result["provider"],
        "latency_ms":  result["latency_ms"],
    }