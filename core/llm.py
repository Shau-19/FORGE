"""
core/llm.py
Universal LLM caller — supports OpenAI and Groq.
Supports per-call model routing: each agent picks the best model for its job.

Model strategy:
  scaffold      → openai/gpt-4o-mini  (best instruction following, 16k output)
  validate/prd  → groq/llama-3.3-70b  (fast, cheap, good reasoning)
  checklist     → groq/llama-3.3-70b  (fast, simple JSON)
  cicd autofix  → openai/gpt-4o-mini  (precise patch generation)
  readme        → openai/gpt-4o-mini  (quality writing)
  diagram       → groq/llama-3.3-70b  (simple JSON, fast)
"""

import os
import time
from typing import Any

# Default provider — used when no override is specified
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")
GROQ_KEY     = os.getenv("GROQ_API_KEY", "")

# Default models per provider
OPENAI_MODEL = os.getenv("LLM_MODEL_OPENAI", "gpt-4o-mini")
GROQ_MODEL   = os.getenv("LLM_MODEL_GROQ",   "llama-3.3-70b-versatile")

# ── Per-agent model routing ───────────────────────────────
# Format: "provider/model"
# Agents import and pass AGENT_MODELS[agent_name] to llm.call()
AGENT_MODELS = {
    # Quality-critical — needs precise instruction following + large output
    "scaffold":     ("openai", "gpt-4o-mini"),
    "cicd_autofix": ("openai", "gpt-4o-mini"),
    "readme":       ("openai", "gpt-4o-mini"),
    "prd_refine":   ("openai", "gpt-4o-mini"),

    # Fast + cheap — good reasoning, simple JSON output
    "validator":    ("groq", "llama-3.3-70b-versatile"),
    "prd":          ("groq", "llama-3.3-70b-versatile"),
    "checklist":    ("groq", "llama-3.3-70b-versatile"),
    "diagram":      ("groq", "llama-3.3-70b-versatile"),
    "doit":         ("groq", "llama-3.3-70b-versatile"),
    "cicd_watch":   ("groq", "llama-3.3-70b-versatile"),
    "knowledge":    ("groq", "meta-llama/llama-4-scout-17b-16e-instruct"),
    "repochat":     ("groq", "llama-3.3-70b-versatile"),
    "spec":         ("groq", "llama-3.3-70b-versatile"),  # scaffold spec step
}


def call(
    prompt: str,
    system: str = "",
    max_tokens: int = 1500,
    agent: str = "",           # pass agent name for automatic routing
    provider: str = "",        # or pass provider+model directly
    model: str = "",
) -> dict[str, Any]:
    """
    Call the LLM. Resolution order:
    1. If agent= is set, use AGENT_MODELS[agent] routing
    2. If provider= and model= are set, use those directly
    3. Fall back to DEFAULT_PROVIDER + default model
    """
    if agent and agent in AGENT_MODELS:
        resolved_provider, resolved_model = AGENT_MODELS[agent]
    elif provider and model:
        resolved_provider, resolved_model = provider, model
    elif provider:
        resolved_provider = provider
        resolved_model = OPENAI_MODEL if provider == "openai" else GROQ_MODEL
    else:
        resolved_provider = DEFAULT_PROVIDER
        resolved_model = OPENAI_MODEL if DEFAULT_PROVIDER == "openai" else GROQ_MODEL

    # Graceful fallback: if OpenAI key missing, fall back to Groq
    if resolved_provider == "openai" and not OPENAI_KEY:
        print(f"  [LLM] OPENAI_API_KEY not set — falling back to Groq for agent={agent or 'direct'}")
        resolved_provider = "groq"
        resolved_model = GROQ_MODEL

    # Graceful fallback: if Groq key missing, try OpenAI
    if resolved_provider == "groq" and not GROQ_KEY:
        if OPENAI_KEY:
            print(f"  [LLM] GROQ_API_KEY not set — falling back to OpenAI for agent={agent or 'direct'}")
            resolved_provider = "openai"
            resolved_model = OPENAI_MODEL
        else:
            raise RuntimeError("Neither OPENAI_API_KEY nor GROQ_API_KEY is set.")

    print(f"  [LLM] agent={agent or 'direct'} → {resolved_provider}/{resolved_model} max_tokens={max_tokens}")

    if resolved_provider == "openai":
        return _call_openai(prompt, system, max_tokens, resolved_model)
    elif resolved_provider == "groq":
        return _call_groq(prompt, system, max_tokens, resolved_model)
    else:
        raise RuntimeError(f"Unknown provider: '{resolved_provider}'. Use 'openai' or 'groq'.")


# ── OpenAI ────────────────────────────────────────────────
def _call_openai(prompt: str, system: str, max_tokens: int, model: str) -> dict:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    client   = OpenAI(api_key=OPENAI_KEY)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    t0 = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.4,
    )
    latency = int((time.time() - t0) * 1000)

    return {
        "text":        response.choices[0].message.content.strip(),
        "tokens_used": response.usage.total_tokens,
        "model":       model,
        "provider":    "openai",
        "latency_ms":  latency,
    }


# ── Groq ──────────────────────────────────────────────────
def _call_groq(prompt: str, system: str, max_tokens: int, model: str) -> dict:
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY not set in environment.")
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    client   = Groq(api_key=GROQ_KEY)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    t0 = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.4,
    )
    latency = int((time.time() - t0) * 1000)

    return {
        "text":        response.choices[0].message.content.strip(),
        "tokens_used": response.usage.total_tokens,
        "model":       model,
        "provider":    "groq",
        "latency_ms":  latency,
    }