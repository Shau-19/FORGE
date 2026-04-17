"""
api/docschat.py — Knowledge Base RAG using PageIndex Cloud API

Real PageIndex API (from docs.pageindex.ai/endpoints):
  Auth:     header "api_key": YOUR_KEY  (NOT Authorization: Bearer)
  PDF:      POST /doc/  multipart/form-data  → doc_id, then poll
  Markdown: POST /markdown/  multipart/form-data → synchronous, returns structure
  Poll:     GET  /doc/{doc_id}/?type=tree  → {status, result}
  Chat:     POST /chat/completions  {doc_id, messages} → choices[0].message.content

Three input sources:
  PDF upload   → POST /doc/         → poll → tree → Chat API Q&A
  URL scrape   → scrape → POST /markdown/ → tree immediately → Chat API Q&A
  GitHub docs  → fetch .md → POST /markdown/ → tree immediately → Chat API Q&A
"""

import json
import re
import time
import base64
import io
import urllib.request
import urllib.error
import urllib.parse
import html as _html
import os as _os

PAGEINDEX_KEY_ENV = _os.getenv("PAGEINDEX_API_KEY", "")
PAGEINDEX_BASE    = "https://api.pageindex.ai"


# ════════════════════════════════════════════════════════════════════════════
# PageIndex API helpers — correct auth + endpoints
# ════════════════════════════════════════════════════════════════════════════

def _pi_headers(api_key: str) -> dict:
    """PageIndex uses 'api_key' header, NOT 'Authorization: Bearer'."""
    return {"api_key": api_key}


def _pi_get(api_key: str, path: str) -> dict:
    req = urllib.request.Request(
        f"{PAGEINDEX_BASE}{path}",
        headers=_pi_headers(api_key),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"PageIndex API error {e.code}: {body}")


def _pi_multipart(api_key: str, path: str, filename: str, content: bytes,
                  content_type: str = "text/markdown", extra_fields: dict = None) -> dict:
    """
    POST multipart/form-data to PageIndex.
    Builds boundary manually — no external deps.
    """
    boundary = "----PageIndexBoundary7f3a9b2c"

    body_parts = []

    # Extra form fields (e.g. if_add_node_summary=yes)
    for key, val in (extra_fields or {}).items():
        body_parts.append(
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f'{val}\r\n'
        )

    # File field
    body_parts.append(
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: {content_type}\r\n\r\n'
    )

    body = (
        "".join(body_parts).encode("utf-8")
        + content
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )

    req = urllib.request.Request(
        f"{PAGEINDEX_BASE}{path}",
        data=body,
        method="POST",
        headers={
            **_pi_headers(api_key),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"PageIndex API error {e.code}: {body_err}")


def _poll_pdf(api_key: str, doc_id: str, max_wait: int = 180) -> list:
    """
    Poll GET /doc/{doc_id}/?type=tree until status == completed.
    Returns the result list (tree nodes).
    """
    deadline = time.time() + max_wait
    while time.time() < deadline:
        data = _pi_get(api_key, f"/doc/{doc_id}/?type=tree")
        status = data.get("status", "")
        if status == "completed":
            return data.get("result", [])
        if status in ("failed", "error"):
            raise ValueError(f"PageIndex processing failed for {doc_id}: {data}")
        time.sleep(4)
    raise TimeoutError(f"PageIndex timed out after {max_wait}s for doc {doc_id}")


def _render_tree(nodes, depth: int = 0, max_depth: int = 4) -> str:
    """Render PageIndex tree nodes as readable text for display."""
    if depth > max_depth or not nodes:
        return ""
    lines = []
    if not isinstance(nodes, list):
        nodes = [nodes]
    for node in nodes:
        indent  = "  " * depth
        node_id = node.get("node_id", "?")
        title   = node.get("title", "")
        summary = node.get("summary", "") or node.get("text", "")[:100]
        line    = f"{indent}[{node_id}] {title}"
        if summary:
            short = summary[:130] + "…" if len(summary) > 130 else summary
            line += f"\n{indent}    {short}"
        lines.append(line)
        children = node.get("nodes", [])
        if children:
            lines.append(_render_tree(children, depth + 1, max_depth))
    return "\n".join(filter(None, lines))


def _count_nodes(nodes) -> int:
    if not nodes:
        return 0
    if not isinstance(nodes, list):
        nodes = [nodes]
    return sum(1 + _count_nodes(n.get("nodes", [])) for n in nodes)


# ════════════════════════════════════════════════════════════════════════════
# PageIndex Chat API — use this for Q&A instead of manual tree traversal
# ════════════════════════════════════════════════════════════════════════════

def _pi_chat(api_key: str, doc_id: str, messages: list) -> str:
    """
    POST /chat/completions with doc_id scoped to document.
    Returns answer string.
    """
    payload = json.dumps({
        "doc_id":   doc_id,
        "messages": messages,
        "stream":   False,
    }).encode()

    req = urllib.request.Request(
        f"{PAGEINDEX_BASE}/chat/completions",
        data=payload,
        method="POST",
        headers={
            **_pi_headers(api_key),
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"PageIndex Chat API error {e.code}: {body}")


# ════════════════════════════════════════════════════════════════════════════
# Source 1 — PDF upload → POST /doc/ → poll → tree
# ════════════════════════════════════════════════════════════════════════════

def handle_kb_pdf(body: dict) -> dict:
    """
    POST /api/kb/pdf
    Body: { pdf_b64, filename, pageindex_key? }
    """
    pdf_b64       = body.get("pdf_b64", "").strip()
    filename      = body.get("filename", "document.pdf")
    pageindex_key = (body.get("pageindex_key", "") or PAGEINDEX_KEY_ENV).strip()

    if not pdf_b64:
        raise ValueError("pdf_b64 is required")
    if not pageindex_key:
        raise ValueError("PageIndex API key required — add PAGEINDEX_API_KEY to .env")

    try:
        pdf_bytes = base64.b64decode(pdf_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 PDF: {e}")

    # Submit PDF as multipart/form-data to /doc/
    result = _pi_multipart(
        pageindex_key, "/doc/",
        filename=filename,
        content=pdf_bytes,
        content_type="application/pdf",
    )
    doc_id = result.get("doc_id")
    if not doc_id:
        raise ValueError(f"PageIndex did not return doc_id: {result}")

    # Poll until tree is ready
    tree_nodes = _poll_pdf(pageindex_key, doc_id)
    tree_text  = _render_tree(tree_nodes)

    return {
        "ok":         True,
        "doc_id":     doc_id,
        "source":     "pdf",
        "filename":   filename,
        "node_count": _count_nodes(tree_nodes),
        "tree":       tree_nodes,
        "tree_text":  tree_text,
    }


# ════════════════════════════════════════════════════════════════════════════
# Source 2 — URL scrape → markdown → POST /markdown/ → synchronous tree
# ════════════════════════════════════════════════════════════════════════════

def _scrape_to_markdown(url: str) -> str:
    """Fetch URL and convert HTML → clean markdown. No external deps."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; FORGE/1.0)",
            "Accept":     "text/html,text/plain,*/*",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw     = r.read()
            ct      = r.headers.get("Content-Type", "")
            m       = re.search(r"charset=([^\s;]+)", ct)
            charset = m.group(1) if m else "utf-8"
            html    = raw.decode(charset, errors="replace")
    except Exception as e:
        raise ValueError(f"Could not fetch URL: {e}")

    # Strip boilerplate
    html = re.sub(r'<(script|style|nav|footer|header|aside|noscript)[^>]*>.*?</\1>',
                  '', html, flags=re.DOTALL | re.IGNORECASE)
    # Headings
    for i in range(6, 0, -1):
        html = re.sub(
            rf'<h{i}[^>]*>(.*?)</h{i}>',
            lambda m, lv=i: '\n' + '#'*lv + ' ' + re.sub(r'<[^>]+>', '', m.group(1)).strip() + '\n',
            html, flags=re.DOTALL | re.IGNORECASE
        )
    # Paragraphs / lists / breaks
    html = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<li[^>]*>(.*?)</li>', r'\n• \1', html, flags=re.DOTALL | re.IGNORECASE)
    # Code
    html = re.sub(r'<pre[^>]*>(.*?)</pre>',
                  lambda m: '\n```\n' + re.sub(r'<[^>]+>', '', m.group(1)).strip() + '\n```\n',
                  html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<code[^>]*>(.*?)</code>',
                  lambda m: '`' + re.sub(r'<[^>]+>', '', m.group(1)) + '`',
                  html, flags=re.DOTALL | re.IGNORECASE)
    # Strip tags
    text = re.sub(r'<[^>]+>', ' ', html)
    text = _html.unescape(text)
    text = re.sub(r'[ \t]{3,}', '  ', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()[:120000]


def handle_kb_url(body: dict) -> dict:
    """
    POST /api/kb/url
    Body: { url, pageindex_key? }
    Scrapes URL → markdown → POST /markdown/ → synchronous tree
    """
    url           = body.get("url", "").strip()
    pageindex_key = (body.get("pageindex_key", "") or PAGEINDEX_KEY_ENV).strip()

    if not url:
        raise ValueError("url is required")
    if not url.startswith("http"):
        url = "https://" + url
    if not pageindex_key:
        raise ValueError("PageIndex API key required — add PAGEINDEX_API_KEY to .env")

    markdown = _scrape_to_markdown(url)
    if len(markdown.strip()) < 100:
        raise ValueError("Could not extract meaningful content from this URL")

    domain   = urllib.parse.urlparse(url).netloc.replace("www.", "")
    filename = f"{domain}.md"

    # POST /markdown/ — synchronous, returns structure immediately
    result = _pi_multipart(
        pageindex_key, "/markdown/",
        filename=filename,
        content=markdown.encode("utf-8"),
        content_type="text/markdown",
        extra_fields={
            "if_add_node_summary": "yes",
            "if_add_node_text":    "yes",
            "if_add_node_id":      "yes",
        }
    )

    # Markdown endpoint returns {success, doc_name, structure}
    # structure is synchronous — no polling needed
    if not result.get("success") and "structure" not in result:
        raise ValueError(f"PageIndex markdown failed: {result}")

    tree_nodes = result.get("structure", [])
    tree_text  = _render_tree(tree_nodes)

    # Note: markdown endpoint doesn't return a doc_id for Chat API
    # Store doc_name for reference
    doc_name = result.get("doc_name", domain)

    return {
        "ok":         True,
        "doc_id":     None,       # no doc_id for markdown — tree-only mode
        "doc_name":   doc_name,
        "source":     "url",
        "url":        url,
        "chars":      len(markdown),
        "node_count": _count_nodes(tree_nodes),
        "tree":       tree_nodes,
        "tree_text":  tree_text,
    }


# ════════════════════════════════════════════════════════════════════════════
# Source 3 — GitHub docs → markdown → POST /markdown/ → synchronous tree
# ════════════════════════════════════════════════════════════════════════════

def _gh_get(token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _resolve_github_url(url: str) -> tuple:
    m = re.search(r"github\.com/([^/]+/[^/]+)/tree/([^/]+)/(.+)", url.strip())
    if m:
        return m.group(1), m.group(3), m.group(2)
    m2 = re.search(r"github\.com/([^/\s]+/[^/\s]+?)(?:\.git)?/?$", url.strip())
    if m2:
        return m2.group(1), "docs", "main"
    raise ValueError(
        f"Could not parse GitHub URL: {url!r}\n"
        "Expected: https://github.com/owner/repo/tree/branch/docs-folder"
    )


def handle_kb_github(body: dict) -> dict:
    """
    POST /api/kb/github
    Body: { url, github_token, pageindex_key? }
    Fetches GitHub .md files → merges → POST /markdown/ → tree
    """
    url           = body.get("url", "").strip()
    github_token  = body.get("github_token", "").strip()
    pageindex_key = (body.get("pageindex_key", "") or PAGEINDEX_KEY_ENV).strip()

    if not url:
        raise ValueError("GitHub docs URL required")
    if not github_token:
        raise ValueError("GitHub token required — connect GitHub first")
    if not pageindex_key:
        raise ValueError("PageIndex API key required — add PAGEINDEX_API_KEY to .env")

    repo, folder, branch = _resolve_github_url(url)

    try:
        raw = _gh_get(github_token, f"/repos/{repo}/git/trees/{branch}?recursive=1")
    except Exception as e:
        raise ValueError(f"Could not access repo {repo}: {e}")

    md_files = [
        item["path"] for item in raw.get("tree", [])
        if item["type"] == "blob"
        and item["path"].startswith(folder)
        and item["path"].endswith(".md")
        and "node_modules" not in item["path"]
    ]

    if not md_files:
        raise ValueError(f"No .md files found under '{folder}' in {repo}")

    md_files.sort(key=lambda p: (len(p.split("/")), p))
    md_files = md_files[:20]

    merged  = ""
    fetched = []
    for path in md_files:
        try:
            data    = _gh_get(github_token, f"/repos/{repo}/contents/{path}?ref={branch}")
            content = base64.b64decode(data["content"].replace("\n", "")).decode("utf-8", errors="replace")
            merged += f"\n\n# {path}\n\n{content[:15000]}"
            fetched.append(path)
        except Exception:
            continue

    if not merged:
        raise ValueError(f"Could not fetch any files from {repo}/{folder}")

    safe_name = repo.replace("/", "_") + ".md"
    result    = _pi_multipart(
        pageindex_key, "/markdown/",
        filename=safe_name,
        content=merged.encode("utf-8"),
        content_type="text/markdown",
        extra_fields={
            "if_add_node_summary": "yes",
            "if_add_node_text":    "yes",
            "if_add_node_id":      "yes",
        }
    )

    if not result.get("success") and "structure" not in result:
        raise ValueError(f"PageIndex markdown failed: {result}")

    tree_nodes = result.get("structure", [])
    tree_text  = _render_tree(tree_nodes)

    return {
        "ok":          True,
        "doc_id":      None,
        "source":      "github",
        "repo":        repo,
        "files_count": len(fetched),
        "chars":       len(merged),
        "node_count":  _count_nodes(tree_nodes),
        "tree":        tree_nodes,
        "tree_text":   tree_text,
    }


# ════════════════════════════════════════════════════════════════════════════
# Ask — two modes:
#   doc_id present → use PageIndex Chat API directly (PDF source)
#   no doc_id → manual tree navigation + Groq answer (markdown sources)
# ════════════════════════════════════════════════════════════════════════════

def _find_node(nodes, node_id: str):
    if not nodes:
        return None
    if not isinstance(nodes, list):
        nodes = [nodes]
    for node in nodes:
        if str(node.get("node_id", "")) == str(node_id):
            return node
        found = _find_node(node.get("nodes", []), node_id)
        if found:
            return found
    return None


def handle_kb_ask(body: dict) -> dict:
    """
    POST /api/kb/ask
    Body: { question, tree, tree_text, doc_id?, pageindex_key?, history? }

    If doc_id is present (PDF source): use PageIndex Chat API directly.
    Otherwise (markdown sources): manual tree nav + Groq answer.
    """
    from core import llm as _llm

    question      = body.get("question", "").strip()
    tree          = body.get("tree", [])
    tree_text     = body.get("tree_text", "")
    doc_id        = body.get("doc_id")
    pageindex_key = (body.get("pageindex_key", "") or PAGEINDEX_KEY_ENV).strip()
    history       = body.get("history", [])

    if not question:
        raise ValueError("question is required")
    if not tree:
        raise ValueError("tree is required — index a document first")

    # ── Mode A: PDF with doc_id → PageIndex Chat API ──────────────────────
    if doc_id and pageindex_key:
        messages = history[-6:] + [{"role": "user", "content": question}]
        answer   = _pi_chat(pageindex_key, doc_id, messages)
        return {
            "answer":     answer,
            "nodes_used": [],
            "mode":       "pageindex_chat",
        }

    # ── Mode B: Markdown tree → manual node pick → Groq answer ────────────
    pick_prompt = f"""PageIndex document tree:
{tree_text[:4000]}

Question: {question}

Which 1-4 node_ids are most relevant? Return ONLY a JSON array, e.g. ["0003","0007"]"""

    try:
        raw = _llm.call(pick_prompt, max_tokens=120)["text"].strip()
        if "```" in raw:
            raw = raw.split("```")[1].strip().lstrip("json").strip()
        node_ids = [str(n) for n in json.loads(raw)][:4]
    except Exception:
        node_ids = []

    # Gather context from picked nodes
    context_parts = []
    for nid in node_ids:
        node = _find_node(tree, nid)
        if node:
            title   = node.get("title", "")
            text    = node.get("text", "") or node.get("summary", "")
            context_parts.append(f"[Node {nid}] {title}\n{text[:2000]}")

    if not context_parts and tree:
        for node in (tree if isinstance(tree, list) else [tree])[:4]:
            context_parts.append(
                f"[Node {node.get('node_id','')}] {node.get('title','')}\n"
                f"{node.get('text','') or node.get('summary','')}"
            )

    history_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-6:])

    system = (
        "You are a precise technical documentation assistant. "
        "Answer using the PageIndex tree sections provided. "
        "Cite the section title or node ID. Be concise."
    )
    prompt = f"""{f'Conversation so far:{history_text}' if history_text else ''}

Relevant PageIndex tree sections:
{chr(10).join(context_parts)}

Question: {question}

Answer concisely, citing the relevant section."""

    result = _llm.call(prompt, system=system, max_tokens=700)

    return {
        "answer":     result["text"],
        "nodes_used": node_ids,
        "mode":       "tree_nav",
        "tokens":     result.get("tokens_used", 0),
    }


# ════════════════════════════════════════════════════════════════════════════
# Legacy handlers — kept for existing Chat Index docs tab
# ════════════════════════════════════════════════════════════════════════════

def handle_docschat_index(body: dict) -> dict:
    return handle_kb_github({
        "url":           body.get("input", ""),
        "github_token":  body.get("github_token", ""),
        "pageindex_key": body.get("pageindex_key", ""),
    })


def handle_docschat_ask(body: dict) -> dict:
    return handle_kb_ask(body)