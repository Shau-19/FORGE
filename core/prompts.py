


'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from ruff/pytest):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<exact relative file path from log e.g. main.py>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim, never multi-line>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error code>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- Log format: "filename.py:line_num: ERROR_CODE" — use THAT exact filename for "file" field
- F401 unused import → old_line=the import line verbatim, new_line=""
- F811 redefined import → old_line=the DUPLICATE line (higher line number), new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line="" (it already exists at top)
- F821 undefined name X → old_line=FIRST import line in file, new_line="import X\\n" + that first import line
- old_line must be a SINGLE line only — never span multiple lines
- NEVER guess filenames — read from log
- One patch per error — never use # type: ignore
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''


'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. index.js or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file" must be a SHORT relative path: "index.js", "src/main.py" — NEVER "/home/runner/work/..." absolute paths
- Strip any leading absolute path prefix — only keep the repo-relative portion
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- For JS SyntaxError: find the EXACT broken line in the FILE CONTENTS and provide it as old_line
- For "return outside function": old_line=the orphaned return line, new_line=""  (delete it)
- For missing closing brace: old_line=the function signature line, new_line=same line + closing brace on next
- F401 unused import → old_line=the import line verbatim, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''



'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. index.js or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file" must be a SHORT relative path: "index.js", "src/main.py" — NEVER "/home/runner/work/..." absolute paths
- Strip any leading absolute path prefix — only keep the repo-relative portion
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- For JS SyntaxError: find the EXACT broken line in the FILE CONTENTS and provide it as old_line
- For "return outside function": old_line=the orphaned return line, new_line=""  (delete it)
- For missing closing brace: old_line=the function signature line, new_line=same line + closing brace on next
- F401 unused import → old_line=the import line verbatim, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: always end with module.exports = app (or appropriate export)
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''


'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. index.js or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file" must be a SHORT relative path: "index.js", "src/main.py" — NEVER "/home/runner/work/..." absolute paths
- Strip any leading absolute path prefix — only keep the repo-relative portion
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- For JS SyntaxError: find the EXACT broken line in the FILE CONTENTS and provide it as old_line
- For "return outside function": old_line=the orphaned return line, new_line=""  (delete it)
- For missing closing brace: old_line=the function signature line, new_line=same line + closing brace on next
- F401 unused import → old_line=the import line verbatim, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''


'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. routes/api.py or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file": ruff log format is "routes/api.py:2:1: F401" — use THAT exact path e.g. "routes/api.py" NOT "backend.py"
- NEVER invent or shorten filenames — copy the FULL relative path exactly as shown before the colon in the log
- Strip only the absolute runner prefix /home/runner/work/repo/repo/ — keep everything after
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- F401 unused import → old_line=the EXACT import line verbatim, new_line=""
- F811 redefined import → old_line=the duplicate import line, new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''


'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. routes/api.py or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file": ruff log format is "routes/api.py:2:1: F401" — use THAT exact path e.g. "routes/api.py" NOT "backend.py"
- NEVER invent or shorten filenames — copy the FULL relative path exactly as shown before the colon in the log
- Strip only the absolute runner prefix /home/runner/work/repo/repo/ — keep everything after
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- F401 unused import → old_line=the EXACT import line verbatim, new_line=""
- F811 redefined import → old_line=the duplicate import line, new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''

'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. routes/api.py or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file": ruff log format is "routes/api.py:2:1: F401" — use THAT exact path e.g. "routes/api.py" NOT "backend.py"
- NEVER invent or shorten filenames — copy the FULL relative path exactly as shown before the colon in the log
- Strip only the absolute runner prefix /home/runner/work/repo/repo/ — keep everything after
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- F401 unused import → old_line=the EXACT import line verbatim, new_line=""
- F811 redefined import → old_line=the duplicate import line, new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
    - If multiple jobs failed (backend + frontend), include rewrites for ALL failed files
    - "frontend/package.json not found": include it in rewrites with full valid content
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''


'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. routes/api.py or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file": ruff log format is "routes/api.py:2:1: F401" — use THAT exact path e.g. "routes/api.py" NOT "backend.py"
- NEVER invent or shorten filenames — copy the FULL relative path exactly as shown before the colon in the log
- Strip only the absolute runner prefix /home/runner/work/repo/repo/ — keep everything after
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- F401 unused import → old_line=the EXACT import line verbatim, new_line=""
- F811 redefined import → old_line=the duplicate import line, new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
    - If multiple jobs failed (backend + frontend), include rewrites for ALL failed files
    - "frontend/package.json not found": include it in rewrites with full valid content
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''

'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. routes/api.py or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file": ruff log format is "routes/api.py:2:1: F401" — use THAT exact path e.g. "routes/api.py" NOT "backend.py"
- NEVER invent or shorten filenames — copy the FULL relative path exactly as shown before the colon in the log
- Strip only the absolute runner prefix /home/runner/work/repo/repo/ — keep everything after
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- F401 unused import → old_line=the EXACT import line verbatim, new_line=""
- F811 redefined import → old_line=the duplicate import line, new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
    - If multiple jobs failed (backend + frontend), include rewrites for ALL failed files
    - "frontend/package.json not found": include it in rewrites with full valid content
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''


'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. routes/api.py or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file": ruff log format is "routes/api.py:2:1: F401" — use THAT exact path e.g. "routes/api.py" NOT "backend.py"
- NEVER invent or shorten filenames — copy the FULL relative path exactly as shown before the colon in the log
- Strip only the absolute runner prefix /home/runner/work/repo/repo/ — keep everything after
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- F401 unused import → old_line=the EXACT import line verbatim, new_line=""
- F811 redefined import → old_line=the duplicate import line, new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
    - If multiple jobs failed (backend + frontend), include rewrites for ALL failed files
    - "frontend/package.json not found": include it in rewrites with full valid content
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''



'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. routes/api.py or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file": ruff log format is "routes/api.py:2:1: F401" — use THAT exact path e.g. "routes/api.py" NOT "backend.py"
- NEVER invent or shorten filenames — copy the FULL relative path exactly as shown before the colon in the log
- Strip only the absolute runner prefix /home/runner/work/repo/repo/ — keep everything after
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- F401 unused import → old_line=the EXACT import line verbatim, new_line=""
- F811 redefined import → old_line=the duplicate import line, new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
    - If multiple jobs failed (backend + frontend), include rewrites for ALL failed files
    - "frontend/package.json not found": include it in rewrites with full valid content
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''

'''
"""
core/prompts.py
All LLM prompts in one place.
Tuning prompts = editing this file only. No touching agent logic.
"""

# ── Deterministic CI/CD Templates ─────────────────────────────────────────────

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
        run: npx eslint .

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
        run: |
          cd frontend
          npm install

      - name: Lint frontend
        run: |
          cd frontend
          npx eslint .

      - name: Test frontend
        run: |
          cd frontend
          npm test --if-present
"""

_PYTHON_KEYS = {"fastapi", "flask", "django", "python"}
_NODE_KEYS   = {"react", "node", "express", "nextjs", "vue", "angular"}


def get_ci_template(stack: list) -> str:
    """Return correct CI YAML based on stack. Fully hardcoded — no file I/O."""
    low = {s.lower() for s in (stack or [])}
    has_python = bool(low & _PYTHON_KEYS)
    has_node   = bool(low & _NODE_KEYS)
    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "You are direct, honest, and specific. Never vague. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object exactly matching this schema:

IDEA: {idea}
TARGET AUDIENCE: {audience}

Return this exact JSON structure (fill in real values, no placeholders):
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
    "strength": "<one sentence: the strongest aspect of this idea>",
    "risk": "<one sentence: the biggest risk or challenge>",
    "recommendation": "<one sentence: most important next action>"
  }},
  "stack": ["<technology1>", "<technology2>", "<technology3>", "<technology4>", "<technology5>"]
}}

Rules:
- viability: overall product viability score
- market: market size and fit score
- risk: higher score = higher risk (not desirability)
- stack: suggest 5-7 realistic technologies suited to this specific idea and audience
- Be specific to the idea — no generic responses
- Return ONLY the JSON object, nothing else"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a Product Requirements Document. "
        "You write clearly, concisely, and specifically. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a Product Requirements Document for this product idea.

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}
SECTIONS REQUESTED: {sections_str}

Return this exact JSON structure (only include keys for requested sections):
{{
  "overview": "<2-3 sentences describing the product, its purpose, and core value proposition>",
  "features": "<numbered list of 5-7 core features, one per line, format: '1. Feature name — brief description'>",
  "stories": "<bullet list of 4-6 user stories, format: '• As a [role], I can [action] so that [benefit]'>",
  "tech": "<technical requirements covering backend, frontend, auth, infra, integrations — one line each>",
  "api": "<key API endpoints if requested: GET/POST /resource — description>",
  "timeline": "<phased timeline: Phase 1 (weeks 1-4): ..., Phase 2 (weeks 5-8): ..., etc.>"
}}

Rules:
- Be specific to the idea — reference the actual product domain
- features should be concrete, not generic
- Only include keys for requested sections: {sections_str}
- Return ONLY the JSON object"""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text — no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section based on the instruction.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text, preserving the same format style."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    """
    Returns prompts for Code Scaffold agent.
    Generates real, extensible code with clear section markers and upgrade comments.
    """
    system = (
        "You are a senior software engineer building a REAL v0.1 MVP that ships and is easy to extend. "
        "ARCHITECTURE PHILOSOPHY: Write code in clearly separated, numbered sections with upgrade comments. "
        "Every section must be independently swappable — devs can replace one section without touching others. "
        "Pattern: each file has sections (1. Setup, 2. Config, 3. Core Logic, 4. Interface) "
        "with # 🔼 UPGRADE: comments showing what to change for the next level. "
        "This is NOT tutorial code — it must actually run. But it MUST be readable and extensible. "
        "For LLM/AI: use httpx to call Groq/OpenAI APIs — NEVER transformers.pipeline or torch. "
        "services/core.py must be importable in CI with zero heavy ML deps. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"

    user = f"""Build a working, extensible v0.1 MVP. Code must run AND be easy to upgrade.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern AI-powered web application.'}

Return JSON (NO github_actions key — CI handled separately):
{{
  "files": [
    {{"type": "dir"|"file", "path": "...", "content": "..."}}
  ],
  "readme": "<setup + run + curl examples + ASCII architecture diagram>",
  "docker_compose": "<working docker-compose or empty string>"
}}

MANDATORY FILES:
1.  {{"type":"dir","path":"routes/","content":""}}
2.  {{"type":"dir","path":"services/","content":""}}
3.  {{"type":"dir","path":"tests/","content":""}}
4.  {{"type":"file","path":"main.py","content":"..."}}
5.  {{"type":"file","path":"models.py","content":"..."}}
6.  {{"type":"file","path":"routes/api.py","content":"..."}}
7.  {{"type":"file","path":"services/core.py","content":"..."}}
8.  {{"type":"file","path":"tests/test_main.py","content":"..."}}
9.  {{"type":"file","path":"requirements.txt","content":"..."}}
10. {{"type":"file","path":"requirements-prod.txt","content":"..."}}
11. {{"type":"file","path":".env.example","content":"..."}}

FILE PATTERNS — follow exactly:

main.py:
  # ==============================\\n# 1. Environment & App Setup\\n# ==============================\\n
  import uvicorn  <- FIRST LINE, before anything else
  from fastapi import FastAPI\\nfrom fastapi.middleware.cors import CORSMiddleware\\nfrom dotenv import load_dotenv
  load_dotenv()\\napp = FastAPI(title="...", version="0.1.0")
  # 🔼 UPGRADE: Add auth middleware, rate limiting, Sentry tracing\\n
  # ==============================\\n# 2. Routes\\n# ==============================\\n
  from routes.api import router\\napp.include_router(router)
  # 🔼 UPGRADE: Add /auth, /admin, /webhooks routers\\n
  # ==============================\\n# 3. Run\\n# ==============================\\n
  if __name__ == "__main__":\\n    uvicorn.run(app, host="0.0.0.0", port=8000)
  # ⚠️ NEVER call uvicorn.run() outside this guard — pytest imports main.py and the server starts, hanging CI forever

services/core.py — adapt sections to the stack:
  # ==============================\\n# 1. Setup & Config\\n# ==============================\\n
  (imports + env vars + client/db/api init for THIS specific stack)
  For AI/LLM stacks: use httpx to call external APIs — NEVER transformers/torch
  For CRUD stacks: SQLAlchemy engine + session factory
  For data/scraping: httpx or requests client setup
  # 🔼 UPGRADE: swap provider, add connection pooling, add config validation\\n
  # ==============================\\n# 2. Core Logic\\n# ==============================\\n
  (the real implementation — DB ops, API calls, business rules for THIS idea)
  # 🔼 UPGRADE: add caching, retry logic, rate limiting\\n
  # ==============================\\n# 3. Service Functions\\n# ==============================\\n
  (named functions that routes/api.py imports — one function per feature)
  # 🔼 UPGRADE: add streaming, pagination, background tasks

routes/api.py:
  # ==============================\\n# 1. Router & Models\\n# ==============================\\n
  from fastapi import APIRouter\\nrouter = APIRouter()
  # ==============================\\n# 2. Endpoints\\n# ==============================\\n
  @router.get("/health")\\ndef health(): return {{"status": "ok", "version": "0.1.0"}}
  (real endpoints calling services)
  # 🔼 UPGRADE: Add auth, pagination, WebSocket for streaming

requirements.txt (CI-SAFE — installs in <15 seconds, NO heavy ML libs):
  fastapi\\nuvicorn\\npydantic\\nhttpx\\npython-dotenv

requirements-prod.txt (full production deps):
  -r requirements.txt\\nlangchain-core\\nlangchain-groq\\n(other LLM/DB libs as needed)

tests/test_main.py:
  from fastapi.testclient import TestClient\\nfrom main import app
  client = TestClient(app)
  def test_health(): assert client.get("/health").status_code == 200
  def test_main_endpoint(): (POST to main feature endpoint with EXACT fields from ChatRequest/RequestModel, assert 200)
  # ⚠️ Request body must match Pydantic model exactly — wrong fields = 422
  def test_bad_input(): (POST with empty/invalid input, assert 422 or 400)

STRICT RULES:
- JSON strings: use \\n not literal newlines inside JSON values
- ALL imports at TOP of every file — never mid-file, never inside functions
- NEVER use: transformers, torch, tensorflow, pipeline() — breaks CI
- services/core.py must work with only: httpx, python-dotenv, pydantic
- Every section must have # 🔼 UPGRADE: with 3+ specific next steps
- tests pass with requirements.txt only (no prod deps needed)
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert generating a pre-launch checklist. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist for this product.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return a JSON object:
{{
  "items": [
    {{
      "cat": "<SECURITY | PERFORMANCE | SEO | DEVOPS | LEGAL | LAUNCH>",
      "label": "<specific actionable checklist item>",
      "done": false,
      "detail": "<one sentence explaining why this matters>"
    }}
  ]
}}

Rules:
- Generate 12-16 items total
- Items must be SPECIFIC to the stack ({stack_str}) — not generic
- Only include categories from focus areas: {focus_str}
- All done: false except obvious auto-complete items
- Return ONLY the JSON object"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD pipeline failures. "
        "You are precise, specific, and always return actionable fixes. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""You are given a REAL CI failure log. Read every error line carefully and return EXACT fixes.

STACK: {stack_str}

FAILURE LOG (real output from CI):
{failure_log[:3000]}

Return this exact JSON structure:
{{
  "summary": "<one sentence: what failed and why>",
  "root_cause": "<one sentence: the underlying cause>",
  "patches": [
    {{
      "file": "<RELATIVE file path only e.g. routes/api.py or src/main.py — never absolute paths>",
      "old_line": "<the EXACT single line to remove/replace — copy verbatim from the FILE CONTENTS shown in log>",
      "new_line": "<replacement line, or empty string to delete>",
      "explanation": "<why this fix resolves the error>"
    }}
  ],
  "commands": ["<shell command 1>", "<shell command 2>"]
}}

CRITICAL RULES:
- "file": ruff log format is "routes/api.py:2:1: F401" — use THAT exact path e.g. "routes/api.py" NOT "backend.py"
- NEVER invent or shorten filenames — copy the FULL relative path exactly as shown before the colon in the log
- Strip only the absolute runner prefix /home/runner/work/repo/repo/ — keep everything after
- old_line must be copied VERBATIM from the actual file content shown in the log
- old_line must be a SINGLE line only — never span multiple lines, never include line numbers
- old_line must NEVER be empty — if you cannot find the exact line, omit the patch entirely
- NEVER patch package.json, requirements.txt, .github/, or config files — only patch source code
- F401 unused import → old_line=the EXACT import line verbatim, new_line=""
- F811 redefined import → old_line=the duplicate import line, new_line=""
- E402 import not at top → old_line=the misplaced import line, new_line=""
- One patch per distinct error — return ONLY the JSON"""
    return system, user


def rewrite_broken_file(failure_log: str, stack: list[str]) -> tuple[str, str]:
    """
    Called when structural syntax errors are detected (SyntaxError, IndentationError, etc.).
    Returns full corrected file content instead of line patches.
    Universal — works for Python, JS, TS, and any language.
    """
    system = (
        "You are a senior software engineer fixing structural syntax errors in source files. "
        "You return complete, corrected file contents — not diffs or patches. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )
    stack_str = ", ".join(stack) if stack else "Node.js"
    user = f"""A CI build failed with structural syntax errors. Fix the broken files completely.

STACK: {stack_str}

FAILURE LOG (contains error details and file contents):
{failure_log[:4000]}

Return this exact JSON:
{{
  "summary": "<one sentence: what was broken>",
  "root_cause": "<one sentence: the structural cause>",
  "rewrites": [
    {{
      "file": "<SHORT relative path only e.g. index.js or src/main.py — NEVER absolute paths>",
      "full_content": "<the COMPLETE corrected file content as a single string with \n for newlines>",
      "explanation": "<one sentence: what you fixed>"
    }}
  ],
  "commands": ["<shell command if needed>"]
}}

CRITICAL RULES:
- "file" must be SHORT relative path — strip /home/runner/work/repo/repo/ prefix completely
- "full_content" must be the ENTIRE file — not a snippet, not a diff
- Fix ALL syntax errors in the file — missing braces, orphaned returns, unclosed functions
- Preserve all working logic — only fix the structural errors
- JS files: use // comments only, NEVER # (hash breaks JS parsers)
- JS: separate server start from app export using require.main guard:
    if (require.main === module) { app.listen(3000); }
    module.exports = app;  // always export for testing
- Python: uvicorn.run() only inside if __name__ == "__main__":
- Only rewrite files shown in the failure log — do not invent new files
    - If multiple jobs failed (backend + frontend), include rewrites for ALL failed files
    - "frontend/package.json not found": include it in rewrites with full valid content
- Return ONLY the JSON"""
    return system, user


def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying system architecture diagrams. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram based on the instruction.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES (pairs of node indices):
{json.dumps(current_edges)}

Return the UPDATED diagram as JSON:
{{
  "nodes": [
    {{
      "label": "<technology name>",
      "color": "<hex color>",
      "x": <float 0.05-0.95>,
      "y": <float 0.05-0.95>,
      "r": <integer radius 16-30>
    }}
  ],
  "edges": [[<node_index_a>, <node_index_b>]],
  "change_summary": "<one sentence describing what changed>"
}}

Rules:
- Keep existing nodes unless instruction says to remove them
- Add new nodes for any new technologies mentioned
- x/y are fractional canvas positions (0=left/top, 1=right/bottom)
- Space nodes well — no overlaps
- Use sensible colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- Return ONLY the JSON"""
    return system, user


import json'''



"""
core/prompts.py - All LLM prompts in one place.
"""
import json

# ── CI/CD Templates (hardcoded, never LLM-generated) ──────────────────────────

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
    """
    Select CI template based on ACTUAL generated files, not stack keywords.
    Falls back to stack-based detection if no files provided.
    """
    if files:
        paths = {f["path"] for f in files if isinstance(f, dict) and f.get("type") == "file"}
        has_python   = any(p.endswith(".py") for p in paths) or "requirements.txt" in paths
        has_frontend = "frontend/package.json" in paths
        has_node     = "package.json" in paths or has_frontend
        print(f"  [CI] file-based detection: python={has_python} node={has_node} frontend={has_frontend}")
    else:
        raw = " ".join(s.lower() for s in (stack or []))
        has_python = any(k in raw for k in _PYTHON_KEYS)
        has_node   = any(k in raw for k in _NODE_KEYS)
        has_frontend = False
        print(f"  [CI] stack-based detection: python={has_python} node={has_node}")

    if has_python and has_node:
        return _CI_FULLSTACK
    if has_node:
        return _CI_NODE
    return _CI_PYTHON


def validate_idea(idea: str, audience: str) -> tuple[str, str]:
    system = (
        "You are a senior product strategist and startup advisor. "
        "You analyze product ideas and return structured JSON assessments. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    user = f"""Analyze this product idea and return a JSON object:

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
    "strength": "<one sentence>",
    "risk": "<one sentence>",
    "recommendation": "<one sentence>"
  }},
  "stack": ["<tech1>", "<tech2>", "<tech3>", "<tech4>", "<tech5>"]
}}

Rules:
- risk: higher = higher risk
- stack: 5-7 realistic technologies for this idea
- Be specific, not generic
- Return ONLY the JSON"""
    return system, user


def generate_prd(idea: str, audience: str, stack: list[str], sections: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior product manager writing a PRD. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    stack_str    = ", ".join(stack) if stack else "to be determined"
    sections_str = ", ".join(sections)
    user = f"""Write a PRD. Return ALL of these keys: {sections_str}

IDEA: {idea}
AUDIENCE: {audience}
TECH STACK: {stack_str}

Return JSON with EXACTLY these keys (all required): {sections_str}

Key formats:
- "overview": "2-3 sentences on product purpose and value"
- "features": "1. Feature - description\\n2. Feature - description\\n3. Feature - description\\n4. Feature - description\\n5. Feature - description"
- "stories": "As a user I can ... so that ...\\nAs a user I can ... so that ..."
- "tech": "Backend: ...\\nFrontend: ...\\nAuth: ...\\nInfra: ..."
- "api": "GET /health - health check\\nPOST /resource - create\\nGET /resource - list"
- "timeline": "Phase 1 (weeks 1-4): ...\\nPhase 2 (weeks 5-8): ...\\nPhase 3 (weeks 9-12): ..."

CRITICAL: Every requested key must have real content. Empty strings not acceptable.
Specific to this idea only - no generic placeholders.
Return ONLY the JSON object."""
    return system, user


def refine_prd_section(section_label: str, current_content: str, instruction: str) -> tuple[str, str]:
    system = (
        "You are a senior product manager refining a PRD section. "
        "Return ONLY the updated section text - no JSON wrapper, no explanation."
    )
    user = f"""Refine this PRD section.

SECTION: {section_label}
CURRENT CONTENT:
{current_content}

INSTRUCTION: {instruction}

Return only the updated section text."""
    return system, user


def generate_scaffold(idea: str, stack: list[str], structure: str, prd_overview: str) -> tuple[str, str]:
    system = (
        "You are a senior software engineer building a real v0.1 MVP. "
        "Generate code matching the EXACT stack - Node/React Native = JS files only, Python/FastAPI = Python files only. "
        "Code must actually run. Return ONLY valid JSON - no markdown fences, no explanation."
    )

    stack_str = ", ".join(stack) if stack else "FastAPI, Python"
    raw       = " ".join(s.lower() for s in stack)
    is_python = any(k in raw for k in {"fastapi", "flask", "django", "python"})
    is_node   = any(k in raw for k in {"node", "express", "react native", "node.js", "express.js"})

    if is_python and not is_node:
        file_spec = """MANDATORY FILES (Python/FastAPI):
- routes/, services/, tests/ directories
- main.py:
  * ALL imports at very top (import uvicorn FIRST)
  * uvicorn.run() ONLY inside: if __name__ == "__main__":
  * NEVER call uvicorn.run() outside that guard - pytest will hang
- models.py: Pydantic models with typed fields
- routes/api.py:
  * Use Pydantic BaseModel for ALL request bodies (NOT raw str/int params)
  * class ChatRequest(BaseModel): message: str  <- then use req: ChatRequest
  * Every optional field must have a default value to avoid 422 errors
- services/core.py:
  * NO transformers, torch, tensorflow - breaks CI
  * Use httpx for external API calls
  * Must be importable with only: fastapi, uvicorn, pydantic, httpx, python-dotenv
- tests/test_main.py:
  * from fastapi.testclient import TestClient; from main import app
  * Request body fields MUST exactly match Pydantic model field names
  * Wrong field name = 422 error
- requirements.txt: fastapi, uvicorn, pydantic, httpx, python-dotenv ONLY (CI-safe)
- requirements-prod.txt: -r requirements.txt + heavy deps (sqlalchemy, langchain, etc.)
- .env.example"""

    elif is_node:
        # Check if React is also in stack → Node+React fullstack
        is_react = any(k in raw for k in {'react', 'vue', 'angular', 'nextjs', 'next.js'})

        if is_react:
            file_spec = """MANDATORY FILES (Node.js + React fullstack):

BACKEND (root level):
- package.json:
  * scripts: {"start": "node index.js", "test": "jest --passWithNoTests"}
  * dependencies: express, cors + all require()'d packages
  * devDependencies: {"jest": "^29.0.0", "supertest": "^6.3.4"}
- index.js:
  * Use // comments NEVER # comments
  * ALWAYS: if (require.main === module) { app.listen(3000); } module.exports = app;
- routes/api.js: Express Router, // comments only
- services/core.js: business logic, // comments only
- tests/app.test.js: supertest tests, jest.mock('../services/core')
- .env.example

FRONTEND — ALL files MUST be inside frontend/ subdirectory:
- frontend/package.json  ← MANDATORY, CI will fail without this
  * scripts: {"start": "react-scripts start", "build": "react-scripts build", "test": "react-scripts test --passWithNoTests"}
  * dependencies: react, react-dom, react-scripts, axios
- frontend/src/App.js: main React component, // comments only
- frontend/src/index.js: ReactDOM entry point, // comments only
- frontend/public/index.html: basic HTML shell

CRITICAL:
- frontend/package.json MUST exist — non-negotiable
- ALL React files inside frontend/src/
- NEVER put App.js at root level
- // comments only in ALL JS files"""
        else:
            file_spec = """MANDATORY FILES (Node.js/Express):
- package.json:
  * scripts: {"start": "node index.js", "test": "jest"}
  * dependencies: express + all packages that are require()'d in any file
  * devDependencies: {"jest": "^29.0.0", "supertest": "^6.3.4"}
  * ALL packages used via require() MUST be listed here or CI fails
- index.js:
  * Use // comments NEVER # comments (# is Python only, breaks JS)
  * ALWAYS separate listen from export:
    const app = express();
    // ... routes ...
    if (require.main === module) { app.listen(3000); }  // only start when run directly
    module.exports = app;  // export for supertest — no listen when imported
  * This allows supertest to import app without starting server
  * Connect to DB only when running as main, not when imported by tests
- routes/api.js: Express Router; use // comments only
- services/core.js: business logic; use // comments only; mock DB calls for testability
- tests/app.test.js:
  * Use // comments NEVER # comments
  * const request = require('supertest'); const app = require('../index');
  * Mock mongoose/DB connections so tests don't need real DB:
    jest.mock('../services/core');
  * Test only HTTP layer - mock the service layer
- .env.example
NO Python files. NO requirements.txt. NO main.py."""

    else:
        file_spec = f"""MANDATORY FILES (Fullstack: Python backend + React frontend):

BACKEND (root level):
- main.py, models.py, routes/api.py, services/core.py
- tests/test_main.py: FastAPI TestClient tests
- requirements.txt: fastapi, uvicorn, pydantic, httpx, python-dotenv ONLY
- requirements-prod.txt, .env.example
- uvicorn.run() ONLY inside if __name__ == "__main__":

FRONTEND — ALL files MUST be inside frontend/ subdirectory:
- frontend/package.json  ← MANDATORY, CI will fail without this
  * name, version, scripts (start/test/build), dependencies (react, react-dom, axios), devDependencies (jest)
- frontend/src/App.js: main React component using // comments only
- frontend/src/index.js: ReactDOM entry point using // comments only

CRITICAL:
- frontend/package.json MUST exist — non-negotiable
- NEVER put App.js or any JS file at root level
- ALL React files inside frontend/src/
- Stack: {stack_str}"""

    user = f"""Build a working v0.1 MVP.

IDEA: {idea}
STACK: {stack_str}
STRUCTURE: {structure}
OVERVIEW: {prd_overview or 'A modern web application.'}

Return JSON (NO github_actions key):
{{
  "files": [{{"type": "dir"|"file", "path": "...", "content": "..."}}],
  "readme": "<setup + run + examples>",
  "docker_compose": "<docker-compose or empty string>"
}}

{file_spec}

UNIVERSAL RULES:
- JSON strings: use \\n for newlines inside JSON values, never literal newlines
- ALL imports/requires at TOP of every file
- JS files: // comments only, NEVER # (hash comments break JS parsers)
- Python files: # comments ok, but uvicorn.run() must be inside if __name__ == "__main__":
- DO NOT include github_actions key
- Return ONLY the JSON object"""

    return system, user


def generate_checklist(idea: str, stack: list[str], focus_areas: list[str]) -> tuple[str, str]:
    system = (
        "You are a DevOps and launch expert. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    focus_str = ", ".join(focus_areas) if focus_areas else "security, performance, seo, devops"
    stack_str = ", ".join(stack) if stack else "FastAPI, React"
    user = f"""Generate a pre-launch checklist.

IDEA: {idea}
STACK: {stack_str}
FOCUS AREAS: {focus_str}

Return:
{{
  "items": [
    {{
      "cat": "<SECURITY|PERFORMANCE|SEO|DEVOPS|LEGAL|LAUNCH>",
      "label": "<actionable item>",
      "done": false,
      "detail": "<one sentence why this matters>"
    }}
  ]
}}

Rules:
- 12-16 items total
- Specific to stack ({stack_str}), not generic
- Only categories from: {focus_str}
- Return ONLY the JSON"""
    return system, user


def analyze_cicd_failure(failure_log: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a senior DevOps engineer analyzing CI/CD failures. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    stack_str = ", ".join(stack) if stack else "Python, FastAPI"
    user = f"""Analyze this CI failure log and return exact fixes.

STACK: {stack_str}

FAILURE LOG:
{failure_log[:3000]}

Return:
{{
  "summary": "<one sentence: what failed>",
  "root_cause": "<one sentence: why>",
  "patches": [
    {{
      "file": "<RELATIVE path only e.g. index.js — NEVER /home/runner/... absolute paths>",
      "old_line": "<EXACT verbatim line from file — never empty, never include line numbers like 5:>",
      "new_line": "<replacement or empty string to delete>",
      "explanation": "<why this fixes it>"
    }}
  ],
  "commands": ["<command 1>"]
}}

RULES:
- file: use EXACT relative path from log e.g. "routes/api.py" NOT "backend.py" — NEVER invent names
- file: strip /home/runner/work/repo/repo/ prefix — keep only the short relative path after it
- old_line: NEVER empty — omit patch entirely if you cannot find exact verbatim line
- old_line: NEVER include "5:" line number prefix — just the code itself
- NEVER patch .github/, Dockerfile, docker-compose, Makefile
- Python F401 unused import: old_line=exact import line, new_line=""
- Python F811 duplicate import: old_line=duplicate line (higher line number), new_line=""
- JS "return outside function": old_line=orphaned return line exactly, new_line=""
- JS missing brace: old_line=function opening line, new_line=same line with closing brace appended
- "Cannot find module X": add "npm install X" to commands array — do NOT patch package.json
- "version does not exist" or "404 Not Found" for npm package: add "npm install packagename@latest" to commands — do NOT patch package.json
- ANY package.json dependency error: use commands array only — NEVER generate a patch with file="package.json"
- "frontend/package.json not found" or "ENOENT.*package.json": add "create frontend/package.json" to commands AND generate backend patches too
- "no such file or directory.*package.json": add "create frontend/package.json" to commands
- Multi-job failures (backend + frontend both failed): generate patches for BOTH — do not skip backend patches just because frontend also failed
- ALWAYS generate patches for Python lint errors even when frontend errors are also present
- Return ONLY JSON"""
    return system, user
def modify_diagram(current_nodes: list, current_edges: list, instruction: str, stack: list[str]) -> tuple[str, str]:
    system = (
        "You are a software architect modifying architecture diagrams. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences."
    )
    user = f"""Modify this architecture diagram.

INSTRUCTION: {instruction}
STACK: {", ".join(stack) if stack else "FastAPI, React"}

CURRENT NODES:
{json.dumps(current_nodes, indent=2)}

CURRENT EDGES:
{json.dumps(current_edges)}

Return:
{{
  "nodes": [
    {{"label": "<name>", "color": "<hex>", "x": <0.05-0.95>, "y": <0.05-0.95>, "r": <16-30>}}
  ],
  "edges": [[<a>, <b>]],
  "change_summary": "<one sentence>"
}}

Rules:
- Keep existing nodes unless told to remove
- Colors: databases=amber, caches=red, APIs=green, frontend=indigo, auth=purple, queues=blue
- No overlapping nodes
- Return ONLY the JSON"""
    return system, user