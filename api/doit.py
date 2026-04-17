"""
api/doit.py — POST /api/checklist/doit
Generates step-by-step implementation guide for a checklist item.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm


def handle_doit(body: dict) -> dict:
    task   = body.get('task', '').strip()
    cat    = body.get('cat', '').strip()
    detail = body.get('detail', '').strip()
    stack  = body.get('stack', 'general web stack')
    idea   = body.get('idea', 'web application')

    if not task:
        raise ValueError('task required')

    system = (
        "You are a senior software engineer and DevOps expert. "
        "You generate precise, actionable implementation guides for specific tasks. "
        "Return ONLY valid JSON — no prose, no markdown fences."
    )

    user = f"""Generate a step-by-step implementation guide for this task:

TASK: {task}
CATEGORY: {cat}
CONTEXT: {detail}
TECH STACK: {stack}
PROJECT: {idea}

Return this exact JSON structure:
{{
  "steps": [
    {{
      "title": "<short action title>",
      "detail": "<1-2 sentence explanation>",
      "command": "<optional shell command or empty string>"
    }}
  ],
  "code_snippet": "<relevant code example, 5-15 lines, or empty string>",
  "references": ["<doc or resource link>"],
  "estimated_time": "<e.g. 30 mins, 2-4 hours>"
}}

Rules:
- 4-7 concrete steps, specific to the stack ({stack})
- Commands should be real and runnable
- Code snippet should be directly relevant to the task
- No placeholders — real implementation details
- Return ONLY the JSON object"""

    result = llm.call(prompt=user, system=system, max_tokens=1200)
    text = result['text'].strip()

    # Strip markdown fences
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'LLM returned invalid JSON: {e}')

    return {
        'steps':          parsed.get('steps', []),
        'code_snippet':   parsed.get('code_snippet', ''),
        'references':     parsed.get('references', []),
        'estimated_time': parsed.get('estimated_time', ''),
        'tokens_used':    result['tokens_used'],
        'model':          result['model'],
        'provider':       result['provider'],
        'latency_ms':     result['latency_ms'],
    }