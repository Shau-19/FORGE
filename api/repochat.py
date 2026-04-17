"""
api/repochat.py — Repo Chat with PageIndex-style tree RAG

No vector DB. No chunking. Two clean steps:

Step 1 — Index:  fetch repo file tree from GitHub, extract function names
Step 2 — Ask:    LLM picks relevant files from tree, fetches them, answers

That's it. Transparent, debuggable, no black boxes.
"""

import json
import re
import base64
import urllib.request
from core import llm as _llm


# ── GitHub helpers ──────────────────────────────────────────────────────────

def _gh_get(token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _resolve_repo(repo_url: str) -> str:
    """'https://github.com/owner/repo' → 'owner/repo'"""
    m = re.search(r"github\.com[/:]([^/\s]+/[^/\s]+?)(?:\.git)?$", repo_url.strip())
    if m:
        return m.group(1).rstrip("/")
    if re.match(r"^[^/\s]+/[^/\s]+$", repo_url.strip()):
        return repo_url.strip()
    raise ValueError(f"Cannot parse GitHub repo from: {repo_url!r}")


def _fetch_file(token: str, repo: str, path: str, branch: str) -> str:
    """Fetch file content, capped at 6000 chars."""
    data = _gh_get(token, f"/repos/{repo}/contents/{path}?ref={branch}")
    content = base64.b64decode(data["content"].replace("\n", "")).decode("utf-8", errors="replace")
    return content[:6000]


# ── Symbol extractor (the "PageIndex" part — no external lib needed) ────────

def _extract_top_symbols(content: str, ext: str) -> list[str]:
    """
    Pull top-level function/class names from file content.
    Simple regex — transparent and fast.
    """
    if ext == ".py":
        found = re.findall(r"^(?:def|class)\s+(\w+)", content, re.MULTILINE)
    elif ext in {".js", ".ts", ".jsx", ".tsx", ".mjs"}:
        found = re.findall(
            r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\(|class\s+(\w+))",
            content
        )
        found = [next(s for s in tup if s) for tup in found if any(tup)]
    else:
        found = []
    return found[:8]  # top 8 symbols only


# ── Tree builder ─────────────────────────────────────────────────────────────

CODE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".mjs",
             ".json", ".md", ".html", ".css", ".yml", ".yaml"}

SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".next"}


def build_tree(token: str, repo: str, branch: str) -> dict:
    """
    Build hierarchical tree index of the repo.

    Returns:
      {
        "repo": "owner/repo",
        "branch": "main",
        "files": {
          "routes/api.js": ["getCards", "createCard"],   # symbols
          "services/core.py": ["CardService", "connect"],
          ...
        },
        "dirs": {
          "routes": ["routes/api.js"],
          "services": ["services/core.py"],
          ...
        }
      }
    """
    raw = _gh_get(token, f"/repos/{repo}/git/trees/{branch}?recursive=1")
    all_items = raw.get("tree", [])

    files = {}   # path → [symbols]
    dirs  = {}   # dir  → [paths]

    for item in all_items:
        if item["type"] != "blob":
            continue
        path = item["path"]

        # Skip unwanted dirs
        if any(skip in path for skip in SKIP_DIRS):
            continue

        # Only code files
        ext = ("." + path.rsplit(".", 1)[-1]) if "." in path else ""
        if ext not in CODE_EXTS:
            continue

        # Build dir map
        directory = "/".join(path.split("/")[:-1]) or "(root)"
        dirs.setdefault(directory, []).append(path)

        # Fetch symbols for JS/PY files (skip large JSON, md, etc.)
        symbols = []
        if ext in {".py", ".js", ".ts", ".jsx", ".tsx", ".mjs"}:
            try:
                content = _fetch_file(token, repo, path, branch)
                symbols = _extract_top_symbols(content, ext)
            except Exception:
                pass

        files[path] = symbols

        # Stop at 50 files to keep indexing fast
        if len(files) >= 50:
            break

    return {
        "repo": repo,
        "branch": branch,
        "files": files,
        "dirs": dirs,
    }


def _render_tree_for_llm(tree: dict) -> str:
    """
    Render tree as readable text for the LLM to navigate.
    This is what the LLM 'reads' to decide which files are relevant.
    """
    lines = [f"REPO: {tree['repo']}  BRANCH: {tree['branch']}\n"]
    for directory, paths in sorted(tree["dirs"].items()):
        lines.append(f"{directory}/")
        for p in paths[:10]:
            syms = tree["files"].get(p, [])
            sym_str = f"  [{', '.join(syms[:5])}]" if syms else ""
            lines.append(f"  {p.split('/')[-1]}{sym_str}")
    return "\n".join(lines)


# ── API Handlers ─────────────────────────────────────────────────────────────

def handle_repochat_index(body: dict) -> dict:
    """
    POST /api/repochat/index
    Body: { repo_url, github_token, branch? }
    Returns: { tree, tree_text, total_files }
    """
    token  = body.get("github_token", "").strip()
    url    = body.get("repo_url", "").strip()
    branch = body.get("branch", "main").strip() or "main"

    if not token:
        raise ValueError("GitHub token required — connect GitHub first")
    if not url:
        raise ValueError("repo_url is required")

    repo = _resolve_repo(url)
    tree = build_tree(token, repo, branch)

    return {
        "ok": True,
        "repo": repo,
        "branch": branch,
        "total_files": len(tree["files"]),
        "tree": tree,                          # cached in frontend session state
        "tree_text": _render_tree_for_llm(tree),  # human-readable preview
    }


def handle_repochat_ask(body: dict) -> dict:
    """
    POST /api/repochat/ask
    Body: { question, tree, github_token, history? }
    Returns: { answer, files_used }

    Two-step RAG:
    1. LLM picks relevant files from tree text
    2. LLM answers using fetched file contents
    """
    question = body.get("question", "").strip()
    tree     = body.get("tree", {})
    token    = body.get("github_token", "").strip()
    history  = body.get("history", [])   # [{role, content}, ...]

    if not question:
        raise ValueError("question is required")
    if not tree or not tree.get("files"):
        raise ValueError("tree is required — index the repo first")

    repo   = tree["repo"]
    branch = tree["branch"]
    tree_text = _render_tree_for_llm(tree)
    all_files = list(tree["files"].keys())

    # ── Step 1: Pick relevant files ────────────────────────────────────────
    pick_prompt = f"""Repo tree:
{tree_text}

Question: {question}

Which 1-3 files are most relevant to answer this question?
Return ONLY a JSON array of file paths, e.g. ["routes/api.js"]
Return ONLY the JSON array, nothing else."""

    try:
        raw = _llm.call(pick_prompt, max_tokens=150)["text"].strip()
        # Strip markdown fences if present
        if "```" in raw:
            raw = raw.split("```")[1].strip().lstrip("json").strip()
        picked = json.loads(raw)
        # Validate — only files that actually exist
        picked = [f for f in picked if f in tree["files"]][:3]
    except Exception:
        # Fallback: first 2 code files
        picked = [f for f in all_files if f.endswith((".js", ".py"))][:2]

    if not picked:
        picked = all_files[:2]

    # ── Step 2: Fetch + answer ─────────────────────────────────────────────
    context_parts = []
    for fpath in picked:
        try:
            content = _fetch_file(token, repo, fpath, branch)
            context_parts.append(f"=== {fpath} ===\n{content}")
        except Exception as e:
            context_parts.append(f"=== {fpath} ===\n[Could not fetch: {e}]")

    # Build recent history string (last 3 exchanges)
    history_text = ""
    for msg in history[-6:]:
        history_text += f"\n{msg['role'].upper()}: {msg['content']}"

    answer_system = (
        "You are a helpful code assistant for a GitHub repository. "
        "Answer questions using the provided file contents. "
        "Always mention which file you're referencing. Be concise and specific."
    )
    answer_prompt = f"""Repo: {repo}
{f'Recent conversation:{history_text}' if history_text else ''}

FILE CONTENTS:
{chr(10).join(context_parts)}

Question: {question}

Answer concisely, citing the relevant file(s)."""

    result = _llm.call(answer_prompt, system=answer_system, max_tokens=600)

    return {
        "answer": result["text"],
        "files_used": picked,
        "tokens": result.get("tokens_used", 0),
    }