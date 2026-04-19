"""
core/kb_injection.py — Knowledge Base context injection for pipeline agents.

When the user enables "Inject into Agents" toggle in the UI, the frontend
sends kb_context in the request body. This module extracts a clean text
summary from the KB tree and prepends it to any agent prompt.

Usage in prompts.py:
    from core.kb_injection import build_kb_context
    kb_snippet = build_kb_context(kb_context)
    # prepend to system prompt or user prompt
"""


def build_kb_context(kb_context: dict, max_chars: int = 2000) -> str:
    """
    Extract a flat readable summary from the KB tree for injection into prompts.
    Returns empty string if no KB context provided.

    kb_context shape (from frontend state):
    {
      "tree": [...],        # PageIndex tree nodes
      "tree_text": "...",   # pre-rendered tree text
      "source": "url|pdf|github",
      "doc_id": "...",      # optional, PDF only
      "url": "...",         # optional
    }
    """
    if not kb_context or not isinstance(kb_context, dict):
        return ""

    tree_text = kb_context.get("tree_text", "").strip()
    source    = kb_context.get("source", "")
    url       = kb_context.get("url", "") or kb_context.get("repo", "")

    if not tree_text:
        # Fallback: render tree nodes manually
        tree = kb_context.get("tree", [])
        if not tree:
            return ""
        tree_text = _flatten_tree(tree)

    if not tree_text.strip():
        return ""

    # Truncate to max_chars
    snippet = tree_text[:max_chars]
    if len(tree_text) > max_chars:
        snippet += "\n... (truncated)"

    source_label = f" ({url})" if url else f" ({source})" if source else ""

    return (
        f"=== KNOWLEDGE BASE CONTEXT{source_label} ===\n"
        f"{snippet}\n"
        f"=== END KNOWLEDGE BASE CONTEXT ===\n"
    )


def _flatten_tree(nodes, depth: int = 0, max_depth: int = 3) -> str:
    """Flatten PageIndex tree nodes into readable text."""
    if depth > max_depth or not nodes:
        return ""
    if not isinstance(nodes, list):
        nodes = [nodes]
    lines = []
    for node in nodes:
        indent  = "  " * depth
        title   = node.get("title", "")
        summary = node.get("summary", "") or node.get("text", "")[:200]
        if title:
            lines.append(f"{indent}• {title}")
        if summary:
            short = summary[:150] + "…" if len(summary) > 150 else summary
            lines.append(f"{indent}  {short}")
        children = node.get("nodes", [])
        if children:
            lines.append(_flatten_tree(children, depth + 1, max_depth))
    return "\n".join(filter(None, lines))


def inject_into_system(system: str, kb_context: dict) -> str:
    """
    Prepend KB context to a system prompt if KB context exists.
    Call this in any prompt function that should be KB-aware.
    """
    kb_snippet = build_kb_context(kb_context)
    if not kb_snippet:
        return system
    return f"{kb_snippet}\n\n{system}"


def inject_into_user(user: str, kb_context: dict) -> str:
    """
    Prepend KB context to a user prompt.
    Use for agents where system prompt is fixed (e.g. JSON-only agents).
    """
    kb_snippet = build_kb_context(kb_context)
    if not kb_snippet:
        return user
    return f"{kb_snippet}\n\n{user}"