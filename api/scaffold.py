"""api/scaffold.py — POST /api/scaffold
File-by-file generation — one LLM call per file.
No forced directory structure — LLM decides what the project needs.
"""
import os, sys, json, urllib.request, urllib.error, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm
from core.prompts import (get_ci_template, generate_scaffold,
                           generate_file_content, generate_readme)


# ── JSON parser ─────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    def sanitize(s):
        result, in_str = [], False
        i = 0
        while i < len(s):
            c = s[i]
            if c == "\\" and in_str:
                result.append(c)
                if i + 1 < len(s):
                    result.append(s[i + 1]); i += 2; continue
            elif c == '"':
                in_str = not in_str; result.append(c)
            elif in_str:
                if   c == "\n": result.append("\\n")
                elif c == "\r": result.append("\\r")
                elif c == "\t": result.append("\\t")
                elif ord(c) < 32: result.append(f"\\u{ord(c):04x}")
                else: result.append(c)
            else:
                result.append(c)
            i += 1
        return "".join(result)

    try:
        return json.loads(sanitize(text))
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(sanitize(text[start:end+1]))
        except json.JSONDecodeError:
            pass
    raise json.JSONDecodeError("Could not parse scaffold response", text, 0)


# ── Scope classifier ────────────────────────────────────────────────────────

def _classify_scope(idea: str, stack: list) -> str:
    idea_lower = idea.lower()
    complex_kw = {"saas", "platform", "marketplace", "enterprise", "multi-tenant",
                  "microservice", "distributed", "real-time analytics", "payment"}
    simple_kw  = {"chatbot", "chat bot", "simple", "basic", "crud", "todo",
                  "calculator", "converter", "scraper", "bot", "cli", "script", "api"}
    if any(k in idea_lower for k in complex_kw):
        return "production"
    if any(k in idea_lower for k in simple_kw):
        return "minimal"
    return "mvp"


# ── Step 1: Spec ────────────────────────────────────────────────────────────

def _get_spec(idea: str, stack: list, structure: str, prd_overview: str, scope: str) -> dict:
    """One small LLM call → file plan. No code generated here."""
    system, user = generate_scaffold(idea, stack, structure, prd_overview)
    result = llm.call(prompt=user, system=system, max_tokens=800, agent="spec")
    try:
        spec = _parse_json(result["text"])
        files = spec.get("files", [])
        if not files:
            raise ValueError("empty files list")
        return spec
    except Exception as e:
        print(f"  [SCAFFOLD] spec parse failed ({e}), using minimal defaults")
        return _default_spec(idea, stack)


def _default_spec(idea: str, stack: list) -> dict:
    """Fallback flat structure — no forced routes/services."""
    raw = " ".join(s.lower() for s in stack)
    is_node = any(k in raw for k in {"node", "express", "react"})
    if is_node:
        return {"project_type": "node", "needs_docker": False, "files": [
            {"path": "index.js",      "purpose": f"Express server with endpoints for: {idea}", "key_imports": ["express"], "key_functions": ["app"]},
            {"path": "package.json",  "purpose": "Node dependencies and scripts",               "key_imports": [],          "key_functions": []},
            {"path": "test/app.test.js", "purpose": "Jest tests for all endpoints",            "key_imports": ["supertest"],"key_functions": ["test"]},
            {"path": ".env.example",  "purpose": "Environment variable template",              "key_imports": [],          "key_functions": []},
        ]}
    return {"project_type": "python", "needs_docker": False, "files": [
        {"path": "app.py",         "purpose": f"FastAPI app with all endpoints for: {idea}",   "key_imports": ["fastapi","uvicorn","httpx"], "key_functions": ["app","main_endpoint"]},
        {"path": "requirements.txt","purpose": "CI-safe Python dependencies",                  "key_imports": [],                           "key_functions": []},
        {"path": "test_app.py",    "purpose": "Pytest tests using FastAPI TestClient",         "key_imports": ["fastapi.testclient"],        "key_functions": ["test_endpoint"]},
        {"path": ".env.example",   "purpose": "Environment variable template",                 "key_imports": [],                           "key_functions": []},
    ]}


# ── Step 2: Per-file generation ─────────────────────────────────────────────

def _gen_file(path: str, purpose: str, key_imports: list, key_functions: list,
              idea: str, stack: list, scope: str, all_files: list, prd_overview: str) -> str:
    """One LLM call per file — full context, focused prompt, no truncation."""
    system, user = generate_file_content(
        path=path, purpose=purpose,
        key_imports=key_imports, key_functions=key_functions,
        idea=idea, stack=stack, scope=scope,
        all_files_spec=all_files, prd_overview=prd_overview
    )
    result = llm.call(prompt=user, system=system, max_tokens=1200, agent="scaffold")
    content = result["text"].strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return content.strip()


# ── Step 3: README ───────────────────────────────────────────────────────────

def _gen_readme(idea: str, stack: list, files_spec: list, scope: str, prd_overview: str) -> str:
    from core.prompts import generate_readme as _readme_prompt
    system, user = _readme_prompt(idea, stack, files_spec, scope, prd_overview)
    result = llm.call(prompt=user, system=system, max_tokens=1000, agent="readme")
    return result["text"].strip()


# ── Scaffold validation (fullstack skeleton guard) ───────────────────────────

_FRONTEND_PKG   = '{"name":"frontend","version":"1.0.0","private":true,"scripts":{"start":"react-scripts start","build":"react-scripts build","test":"react-scripts test --passWithNoTests"},"dependencies":{"react":"^18.2.0","react-dom":"^18.2.0","react-scripts":"5.0.1","axios":"^1.4.0"}}'
_FRONTEND_HTML  = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>App</title></head><body><div id="root"></div></body></html>'
_FRONTEND_INDEX = "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App';\nconst root = ReactDOM.createRoot(document.getElementById('root'));\nroot.render(<React.StrictMode><App /></React.StrictMode>);"
_FRONTEND_APP   = "import React from 'react';\nfunction App() { return <div><h1>App</h1></div>; }\nexport default App;"
_SKELETON_DEFAULTS = {
    "frontend/package.json":      _FRONTEND_PKG,
    "frontend/public/index.html": _FRONTEND_HTML,
    "frontend/src/index.js":      _FRONTEND_INDEX,
    "frontend/src/App.js":        _FRONTEND_APP,
}
# (structure is now spec-driven, no forced dirs)


def _validate_scaffold(files: list, stack: list) -> list:
    """Only enforces fullstack skeleton — no other structure is forced."""
    paths = {f["path"] for f in files if f.get("type") == "file"}
    has_py  = any(p.endswith(".py") for p in paths)
    has_frontend = "frontend/package.json" in paths or any("frontend/" in p for p in paths)
    stack_lower = " ".join(s.lower() for s in stack)
    needs_frontend = any(k in stack_lower for k in {"react", "vue", "nextjs"})

    if not (has_py and needs_frontend):
        return files  # not fullstack — leave structure as-is

    # Fullstack: ensure frontend skeleton exists
    path_map = {f["path"]: f for f in files if f.get("type") == "file"}
    for skel in ["frontend/package.json", "frontend/public/index.html",
                 "frontend/src/App.js", "frontend/src/index.js"]:
        if skel not in path_map:
            print(f"  [SCAFFOLD] injecting: {skel}")
            files.append({"type": "file", "path": skel,
                          "content": _SKELETON_DEFAULTS.get(skel, f"// {skel}")})
    return files


# ── GitHub helpers ───────────────────────────────────────────────────────────

def _gh_get_user(token):
    req = urllib.request.Request(
        "https://api.github.com/user",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _gh_resolve_repo(repo_url: str) -> str:
    repo = repo_url.strip().rstrip("/")
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if repo.startswith(prefix):
            repo = repo[len(prefix):]
            break
    repo = repo.strip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    if repo.count("/") != 1:
        raise RuntimeError(f"Invalid GitHub repo URL: {repo_url}")
    return repo


def _gh_get_repo(token, repo_full):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo_full}",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _gh_create_repo(token, name, private=False):
    data = json.dumps({"name": name, "private": private,
                       "auto_init": False, "description": "Generated by FORGE"}).encode()
    req = urllib.request.Request(
        "https://api.github.com/user/repos", data=data,
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 422:
            try:
                username = _gh_get_user(token).get("login", "user")
                return _gh_get_repo(token, f"{username}/{name}")
            except Exception:
                pass
        raise RuntimeError(f"GitHub repo creation failed ({e.code}): {body[:200]}")


def _gh_push_file(token, repo_full, path, content, message="Initial scaffold by FORGE"):
    encoded = base64.b64encode(content.encode()).decode()
    payload = {"message": message, "content": encoded}
    data = json.dumps(payload).encode()
    url = f"https://api.github.com/repos/{repo_full}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json",
               "Content-Type": "application/json"}
    req = urllib.request.Request(
        url, data=data,
        headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 422:
            try:
                get_req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(get_req, timeout=10) as existing:
                    current = json.loads(existing.read())
                sha = current.get("sha")
                if sha:
                    payload["sha"] = sha
                    retry = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode(),
                        headers=headers,
                        method="PUT",
                    )
                    with urllib.request.urlopen(retry, timeout=10) as updated:
                        return json.loads(updated.read())
            except Exception:
                pass
        raise RuntimeError(f"GitHub push failed for {path} ({e.code}): {e.read().decode()[:100]}")


# ── Main handler ─────────────────────────────────────────────────────────────

def handle_scaffold(body: dict) -> dict:
    name      = body.get("name", "forge-project").strip() or "forge-project"
    stack     = body.get("stack", [])
    structure = body.get("structure", "monorepo")
    prd       = body.get("prd", {})
    idea      = body.get("idea", "")
    gh_token  = body.get("github_token", "")
    repo_url_input = body.get("repo_url", "").strip()
    private   = body.get("private", False)

    prd_overview = prd.get("overview", "") if isinstance(prd, dict) else ""

    # ── 1. Classify scope ──────────────────────────────────────────────────
    scope = _classify_scope(idea, stack)
    print(f"  [SCAFFOLD] scope={scope}  idea={idea[:60]}")

    # ── 2. Get file spec (one small LLM call) ──────────────────────────────
    spec       = _get_spec(idea, stack, structure, prd_overview, scope)
    files_spec = spec.get("files", [])
    needs_docker = spec.get("needs_docker", False) and scope != "minimal"
    print(f"  [SCAFFOLD] spec: {len(files_spec)} files planned")

    # ── 3. Generate each file individually ─────────────────────────────────
    files = []
    seen_dirs = set()

    for fspec in files_spec:
        path = fspec["path"]
        # Auto-create parent dir entries
        if "/" in path:
            dir_path = "/".join(path.split("/")[:-1]) + "/"
            if dir_path not in seen_dirs:
                seen_dirs.add(dir_path)
                files.append({"type": "dir", "path": dir_path, "content": ""})

        print(f"  [SCAFFOLD] generating: {path}")
        try:
            content = _gen_file(
                path=path,
                purpose=fspec.get("purpose", ""),
                key_imports=fspec.get("key_imports", []),
                key_functions=fspec.get("key_functions", []),
                idea=idea, stack=stack, scope=scope,
                all_files=files_spec, prd_overview=prd_overview
            )
            files.append({"type": "file", "path": path, "content": content})
        except Exception as e:
            print(f"  [SCAFFOLD] FAILED {path}: {e}")
            # Safe fallbacks for known files
            fallback = {
                "requirements.txt":     "fastapi==0.111.0\nuvicorn==0.29.0\npydantic==2.7.1\nhttpx==0.27.0\npython-dotenv==1.0.1\npytest==8.2.0\n",
                ".env.example":         "# Copy to .env and fill in\nGROQ_API_KEY=your_key_here\n",
                "requirements-prod.txt":"# Production extras\n-r requirements.txt\n",
            }.get(path, f"# {path}\n# Generation failed: {e}\n")
            files.append({"type": "file", "path": path, "content": fallback})

    # ── 4. README (dedicated call, high quality) ───────────────────────────
    try:
        readme = _gen_readme(idea, stack, files_spec, scope, prd_overview)
    except Exception as e:
        print(f"  [SCAFFOLD] README failed: {e}")
        readme = f"# {name}\n\n{idea}\n\n## Setup\n\n```bash\npip install -r requirements.txt\ncp .env.example .env\nuvicorn app:app --reload\n```\n"

    # ── 5. Docker (non-minimal only) ───────────────────────────────────────
    docker = ""
    if needs_docker:
        docker = "version: '3.8'\nservices:\n  app:\n    build: .\n    ports:\n      - \"8000:8000\"\n    env_file: .env\n"

    # ── 6. Validate + inject skeleton ──────────────────────────────────────
    files = _validate_scaffold(files, stack)

    # ── 7. CI template ─────────────────────────────────────────────────────
    gh_actions = get_ci_template(stack, files)

    existing = {f["path"] for f in files}
    if readme and "README.md" not in existing:
        files.append({"type": "file", "path": "README.md", "content": readme})
    if docker and "docker-compose.yml" not in existing:
        files.append({"type": "file", "path": "docker-compose.yml", "content": docker})
    if gh_actions:
        files += [
            {"type": "dir",  "path": ".github/"},
            {"type": "dir",  "path": ".github/workflows/"},
            {"type": "file", "path": ".github/workflows/ci.yml", "content": gh_actions},
        ]

    repo_url = repo_url_input or f"https://github.com/user/{name}"
    pushed   = 0

    # ── 8. GitHub push ──────────────────────────────────────────────────────
    if gh_token:
        try:
            if repo_url_input:
                repo_full = _gh_resolve_repo(repo_url_input)
                repo_info = _gh_get_repo(gh_token, repo_full)
            else:
                repo_info = _gh_create_repo(gh_token, name, private)
                repo_full = repo_info.get("full_name", f"user/{name}")
            repo_url  = repo_info.get("html_url", repo_url)

            workflow = [f for f in files if ".github" in f.get("path", "")]
            regular  = [f for f in files if ".github" not in f.get("path", "")]

            for f in regular:
                if f["type"] == "file" and f.get("content", "").strip():
                    _gh_push_file(gh_token, repo_full, f["path"], f["content"])
                    print(f"  [GitHub] pushed: {f['path']}")
                    pushed += 1
            for f in workflow:
                if f["type"] == "file" and f.get("content", "").strip():
                    _gh_push_file(gh_token, repo_full, f["path"], f["content"])
                    print(f"  [GitHub] pushed workflow: {f['path']}")
                    pushed += 1

        except RuntimeError as e:
            msg = str(e)
            if "Resource not accessible by personal access token" in msg and not repo_url_input:
                msg += " Hint: create the repo manually on GitHub, paste its URL in Connect GitHub, then run Scaffold again."
            return {"files": files, "repo_url": "", "pushed": 0,
                    "github_error": msg, "tokens_used": 0,
                    "model": "multi-call", "provider": "groq", "latency_ms": 0}

    return {"files": files, "repo_url": repo_url, "pushed": pushed,
            "scope": scope, "tokens_used": 0,
            "model": "multi-call", "provider": "groq", "latency_ms": 0}
