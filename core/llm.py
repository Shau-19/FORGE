"""
core/llm.py
Universal LLM caller — supports OpenAI and Groq.
Every agent calls llm.call(), never touches SDKs directly.
"""

import os
import time
from typing import Any

# ── Provider detection ────────────────────────────────────
PROVIDER      = os.getenv("LLM_PROVIDER", "groq").lower()
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
GROQ_KEY      = os.getenv("GROQ_API_KEY", "")

OPENAI_MODEL  = os.getenv("LLM_MODEL_OPENAI", "gpt-4o-mini")
GROQ_MODEL    = os.getenv("LLM_MODEL_GROQ",   "llama-3.3-70b-versatile")


def call(prompt: str, system: str = "", max_tokens: int = 1500) -> dict[str, Any]:
    
    if PROVIDER == "groq":
        return _call_groq(prompt, system, max_tokens)
    elif PROVIDER == "openai":
        return _call_openai(prompt, system, max_tokens)
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {PROVIDER}. Use 'openai' or 'groq'.")


# ── Groq ──────────────────────────────────────────────────
def _call_groq(prompt: str, system: str, max_tokens: int) -> dict:
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY not set in environment.")

    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    client = Groq(api_key=GROQ_KEY)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    t0 = time.time()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.4,
    )
    latency = int((time.time() - t0) * 1000)

    return {
        "text":        response.choices[0].message.content.strip(),
        "tokens_used": response.usage.total_tokens,
        "model":       GROQ_MODEL,
        "provider":    "groq",
        "latency_ms":  latency,
    }


# ── OpenAI ────────────────────────────────────────────────
def _call_openai(prompt: str, system: str, max_tokens: int) -> dict:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    client = OpenAI(api_key=OPENAI_KEY)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    t0 = time.time()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.4,
    )
    latency = int((time.time() - t0) * 1000)

    return {
        "text":        response.choices[0].message.content.strip(),
        "tokens_used": response.usage.total_tokens,
        "model":       OPENAI_MODEL,
        "provider":    "openai",
        "latency_ms":  latency,
    }