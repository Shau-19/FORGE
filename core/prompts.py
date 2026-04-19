"""
core/prompts.py - All LLM prompts in one place.
KB injection is wired into validate_idea, generate_prd, and generate_scaffold.
"""
import json
from core.kb_injection import inject_into_system, inject_into_user

# ── CI/CD Templates ────────────────────────────────────────────────────────

_CI_PYTHON = """name: CI
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install ruff pytest
      - name: Lint
        run: ruff check .
      - name: Run tests
        run: pytest
        env:
          PYTHONPATH: .
"""

_CI_NODE = """name: CI
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "18"
      - name: Install dependencies
        run: npm install
      - name: Lint
        run: npx eslint . --ext .js,.jsx,.ts,.tsx || true
      - name: Run tests
        run: npm test --if-present
"""

_CI_FULLSTACK = """name: CI
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install backend deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install ruff pytest
      - name: Lint backend
        run: ruff check .
      - name: Test backend
        run: pytest
        env:
          PYTHONPATH: .
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "18"
      - name: Install frontend deps
        run: cd frontend && npm install
      - name: Test frontend
        run: cd frontend && npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular",
                "react native", "node.js", "express.js", "next.js", "vue.js", "reactnative"}


def get_ci_template(stack: list, files: list = None) -> str:
    if files:
        paths = {f["path"] for f in files if isinstance(f, dict) and f.get("type") == "file"}
        has_python   = any(p.endswith(".py") for p in paths) or "requirements.txt" in paths
        has_frontend = "frontend/package.json" in paths
        has_node     = "package.json" in paths or has_frontend
    else:
        raw = " ".join(s.lower() for s in (stack or []))
        has_python   = any(k in raw for k in _PYTHON_KEYS)
        has_node     = any(k in raw for k in _NODE_KEYS)
        has_frontend = False

    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


# ── PROMPT FUNCTIONS ────────────────────────────────────────────────────────


def validate_idea(idea: str, audience: str, kb_context: dict = None) -> tuple[str, str]:
    system = (
        "You are a senior product strategist. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    # Inject KB context if provided — helps validator understand domain
    system = inject_into_system(system, kb_context)

    user = f"""Analyze this product idea:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON:
{{
  "viability": <integer 0-100>,
  "market": <integer 0-100>,
  "risk": <integer 0-100>,
  "metrics": {{
    "technical_feasibility": <integer 0-100>,
    "revenue_potential": <integer 0-100>,
    "time_to_market": <integer 0-100>,
    "competitive_moat": <integer 0-100>
  }},
  "analysis": {{
    "strength": "<one concrete sentence about this idea's strongest advantage>",
    "risk": "<one sentence about the biggest risk>",
    "recommendation": "<one sentence: most important first action>"
  }},
  "stack": ["<tech1>", "<tech2>", "<tech3>", "<tech4>", "<tech5>"]
}}

STACK RULES:
- Recommend ONLY what's needed to build this idea
- Chatbot/API: FastAPI + httpx + Groq API + python-dotenv (4 things max)
- NEVER add transformers/torch unless idea explicitly needs local ML
- 3-4 techs for simple ideas, 5-6 for complex
- Specific names: "Groq API" not "LLM", "PostgreSQL" not "database"
- Return ONLY the JSON"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str],
                 kb_context: dict = None) -> tuple[str, str]:
    system = (
        "You are a senior product manager. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)

    user = f"""Write a concise PRD for: {idea}

AUDIENCE: {audience}
STACK: {stack_str}
SECTIONS NEEDED: {sections_str}
"""
    # Inject KB context into user prompt — gives PRD domain-specific details
    user = inject_into_user(user, kb_context)

    user += f"""
Return JSON with exactly these keys: {sections_str}

Formats:
- "overview": "2-3 sentences: what it is, who it's for, core value"
- "features": "1. Feature — what it does\\n2. Feature — what it does\\n(5-6 features)"
- "stories": "• As a [role], I can [action] so that [benefit]\\n(4-5 stories)"
- "tech": "Backend: ...\\nAPI: ...\\nStorage: ...\\nDeploy: ..."
- "api": "POST /endpoint — description\\nGET /endpoint — description"
- "timeline": "Week 1-2: ...\\nWeek 3-4: ...\\nWeek 5-6: ..."

Be specific to this exact idea. No generic filler. Return ONLY the JSON."""
    return system, user


def refine_prd_section(section_label: str, current_content: str,
                       instruction: str, kb_context: dict = None) -> tuple[str, str]:
    system = (
        "You are a senior product manager. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    system = inject_into_system(system, kb_context)
    user = f"""Refine this PRD section per the instruction.

SECTION: {section_label}
CURRENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated text, same format."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str,
                      prd_overview: str, kb_context: dict = None) -> tuple[str, str]:
    """Used by scaffold.py _generate_spec() — asks for file plan only."""
    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    system = (
        "You are a senior engineer planning a minimal working project. "
        "Return ONLY valid JSON — no markdown, no explanation."
    )

    user = f"""Plan the file structure for this project. Return a spec — no code yet.

IDEA: {idea}
STACK: {stack_str}
OVERVIEW: {prd_overview or 'A focused backend service.'}
"""
    # Inject KB context — helps scaffold understand domain-specific requirements
    user = inject_into_user(user, kb_context)

    user += """
Return JSON:
{
  "project_type": "python" | "node" | "fullstack",
  "files": [
    {
      "path": "app.py",
      "purpose": "FastAPI app with /chat endpoint that calls Groq API and returns response",
      "key_imports": ["fastapi", "httpx", "os"],
      "key_functions": ["chat_endpoint", "call_groq"]
    }
  ],
  "needs_docker": false
}

STRUCTURE PHILOSOPHY:
- Flat is fine: app.py + test_app.py + requirements.txt is complete
- Only add subdirectories if the idea genuinely needs them
- A chatbot does NOT need routes/ + services/ + models/ — just app.py
- Every file must earn its place

MANDATORY regardless of structure:
- At least one main entry file
- At least one test file
- requirements.txt (Python) or package.json (Node)
- .env.example

FILE PURPOSE must be specific — not "business logic" but what it actually does.
Return ONLY the JSON"""

    return system, user


def generate_file_content(path: str, purpose: str, key_imports: list, key_functions: list,
                           idea: str, stack: list, scope: str,
                           all_files_spec: list, prd_overview: str,
                           kb_context: dict = None) -> tuple[str, str]:
    stack_str = ", ".join(stack) if stack else "FastAPI, Python"
    ext  = path.rsplit(".", 1)[-1] if "." in path else "py"
    lang = "Python" if ext == "py" else "JavaScript"

    siblings = "\n".join(
        f"  - {f['path']}: {f['purpose']}"
        for f in all_files_spec if f["path"] != path
    )

    rules_map = {
        "main.py": (
            "- ALL imports at the very top\n"
            "- uvicorn.run() ONLY inside: if __name__ == '__main__':\n"
            "- app = FastAPI(...) at module level\n"
            "- Add CORS middleware with allow_origins=['*']"
        ),
        "app.py": (
            "- ALL imports at the very top\n"
            "- uvicorn.run() ONLY inside: if __name__ == '__main__':\n"
            "- app = FastAPI(...) at module level\n"
            "- Add CORS middleware with allow_origins=['*']"
        ),
        "requirements.txt": (
            "- CI-SAFE only: fastapi, uvicorn, pydantic, httpx, python-dotenv, pytest\n"
            "- Pin versions: fastapi==0.111.0, uvicorn==0.29.0, etc.\n"
            "- NO langchain, NO transformers, NO torch"
        ),
        ".env.example": (
            "- List every env var the code reads with os.getenv()\n"
            "- Comment explaining each one\n"
            "- Use placeholder values like: GROQ_API_KEY=your_groq_key_here"
        ),
    }

    if "test" in path:
        file_rules = (
            "- from fastapi.testclient import TestClient; from app import app\n"
            "- client = TestClient(app) at module level\n"
            "- Mock ALL external API calls with @patch — tests must work without real keys\n"
            "- Test happy path AND one error case per endpoint\n"
            "- Field names MUST exactly match Pydantic model"
        )
    else:
        file_rules = rules_map.get(path, "")

    if any(x in path for x in ["service", "core", "llm", "chat", "api"]) and ext == "py":
        file_rules += (
            "\n- httpx for ALL external calls — no requests library\n"
            "- NO transformers, torch, sklearn\n"
            "- Read API keys with os.getenv() and raise clear error if missing\n"
            "- Implement REAL logic — actually call the API, return real data"
        )

    system = (
        f"You are a senior {lang} engineer. Write production-quality code — "
        "real implementation, no stubs, no placeholders. "
        "Return ONLY the raw file content — no JSON, no markdown fences."
    )
    # Inject KB context into system for file generation
    system = inject_into_system(system, kb_context)

    user = f"""Write the complete content of: {path}

PROJECT: {idea}
STACK: {stack_str}
SCOPE: {scope}
THIS FILE'S JOB: {purpose}
KEY IMPORTS: {', '.join(key_imports) if key_imports else 'standard library'}
KEY FUNCTIONS: {', '.join(key_functions) if key_functions else 'as needed'}

OTHER FILES:
{siblings or '  (no other files)'}

CONTEXT: {prd_overview or 'A focused backend service.'}

RULES:
{file_rules or '- Write real working implementation'}

UNIVERSAL:
- Real code only — no 'pass', no placeholder returns
- Every function does actual work for: {idea}
- Do NOT output markdown fences or wrapper text
- Return ONLY the raw {lang} code"""

    return system, user


def generate_readme(idea: str, stack: list, files_spec: list,
                    scope: str, prd_overview: str) -> tuple[str, str]:
    stack_str  = ", ".join(stack) if stack else "Python"
    file_list  = "\n".join(f"- {f['path']}: {f['purpose']}" for f in files_spec)
    entry_file = next((f["path"] for f in files_spec
                       if f["path"] in ("app.py", "main.py", "index.js")), "app.py")
    is_python  = any(f["path"].endswith(".py") for f in files_spec)
    run_cmd    = f"uvicorn {entry_file.replace('.py','')}:app --reload" if is_python else "node index.js"

    system = "You are a technical writer. Return only raw markdown — no explanation, no wrapper."
    user = f"""Write a complete README.md for this project.

PROJECT: {idea}
STACK: {stack_str}
OVERVIEW: {prd_overview or idea}

FILES:
{file_list}

INCLUDE IN THIS ORDER:

# Project Name
One-line description of what it does.

## What it does
2-3 concrete sentences. What happens when you run it.

## Setup
```bash
git clone <repo>
cd <repo>
pip install -r requirements.txt
cp .env.example .env
# edit .env — add your API keys
```

## Configuration
| Variable | Required | Description |
|----------|----------|-------------|
| GROQ_API_KEY | Yes | Get from console.groq.com |

## Run
```bash
{run_cmd}
```

## API
For every endpoint: method + path, request JSON example, response JSON example, working curl command.

## Project Structure
```
file.py    — what it does
```

## Extending
2-3 specific sentences about the most likely next additions.

RULES:
- Real curl examples with correct field names from the actual code
- No filler phrases
- Return ONLY the markdown"""
    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    idea_lower = idea.lower()
    complex_signals = {"saas", "platform", "marketplace", "enterprise", "multi-tenant",
                       "payment", "stripe", "billing", "subscription", "analytics", "dashboard"}
    simple_signals  = {"chatbot", "chat bot", "simple", "basic", "crud", "todo",
                       "calculator", "converter", "bot", "scraper", "cli", "script", "tool", "api"}

    if any(k in idea_lower for k in complex_signals):
        item_count, scope_note = "10-14", "Complex — include auth, compliance, scaling."
    elif any(k in idea_lower for k in simple_signals):
        item_count, scope_note = "5-7", "Simple tool — essential items only, no enterprise concerns."
    else:
        item_count, scope_note = "7-10", "Standard MVP — practical, actionable only."

    user = f"""Generate a launch checklist for this project.

IDEA: {idea}
STACK: {stack_str}
FOCUS: {focus_str}
SCOPE: {scope_note}

Return:
{{
  "items": [
    {{
      "cat": "<SECURITY|PERFORMANCE|SEO|DEVOPS|LEGAL|LAUNCH>",
      "label": "<specific action naming the actual technology and endpoint>",
      "done": false,
      "detail": "<one sentence: what to do and why it matters here>"
    }}
  ]
}}

Rules:
- {item_count} items — match scope, never pad
- Specific labels: "Add rate limiting to /chat with slowapi" not "add rate limiting"
- Skip irrelevant items: no CDN/SOC2/multi-region for a simple API
- Return ONLY the JSON"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI failures. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"

    # Check if actual file contents are embedded in the failure log
    has_file_contents = "=== ACTUAL FILE CONTENTS" in failure_log

    user = f"""Analyze this CI failure and return exact fixes.

STACK: {stack_str}

FAILURE LOG + FILE CONTENTS:
{failure_log[:6000]}

Return:
{{
  "summary": "<one sentence: what failed>",
  "root_cause": "<one sentence: why>",
  "patches": [
    {{
      "file": "<relative path e.g. app.py>",
      "old_line": "<EXACT verbatim line copied from the FILE CONTENTS above>",
      "new_line": "<fixed replacement line>",
      "explanation": "<why this fixes it>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL — HOW TO GENERATE PATCHES:
{"" if not has_file_contents else """
The failure log above contains '=== ACTUAL FILE CONTENTS ===' sections.
You MUST use these to find exact lines. DO NOT guess or invent function names.
Steps:
1. Read the pytest/ruff error to understand WHAT failed
2. Find the relevant file in '--- filename ---' section
3. Read the actual code to find the REAL function/variable names
4. Copy the EXACT line you want to change as old_line
5. Write the correct fixed version as new_line

Example: if test patches 'app.call_groq_api' but file has 'async def call_groq()',
the fix is: old_line='with patch("app.call_groq_api"', new_line='with patch("app.call_groq"'
"""}

CORE PRINCIPLE — REPAIR, NEVER DELETE:
- NameError/AttributeError: the mock/patch uses wrong name — fix the name to match actual code
- Wrong function name in test: find real name from FILE CONTENTS, fix the patch/mock string
- Missing import: add the import — do NOT delete the code that needs it  
- Async error: fix the async/await — do NOT delete the function
- Wrong indentation: fix it — do NOT delete the block
- DELETE ONLY: F401 unused import (new_line=""), F811 duplicate import (new_line="")

FILE RULES:
- old_line: copy VERBATIM from the FILE CONTENTS section — never invent or approximate
- old_line: NEVER empty — skip patch entirely if you cannot find the exact line
- Relative path only — strip /home/runner/work/repo/repo/ prefix and any temp paths
- NEVER patch .github/, Dockerfile, docker-compose
- Package errors: commands array only
- Patch ALL failed jobs
- Return ONLY JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list,
                   instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, Python"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES:
{json.dumps(current_edges)}

Return:
{{
  "nodes": [
    {{"label": "<n>", "color": "<hex>", "x": <0.05-0.95>, "y": <0.05-0.95>, "r": <16-30>}}
  ],
  "edges": [[<a>, <b>]],
  "change_summary": "<one sentence>"
}}

Colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
No overlapping nodes. Keep existing nodes unless told to remove. Return ONLY the JSON"""
    return system, user