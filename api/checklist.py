"""api/checklist.py — POST /api/checklist
Phase 3: Real LLM-generated launch checklist specific to project stack.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm, prompts


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
    return json.loads(text.strip())


def handle_checklist(body: dict) -> dict:
    idea    = body.get('idea', '').strip()
    stack   = body.get('stack', [])
    focus   = body.get('focus', ['security', 'performance', 'seo', 'devops'])
    if not idea:
        raise ValueError('idea required')

    system, user = prompts.generate_checklist(idea, stack, focus)
    result = llm.call(prompt=user, system=system, max_tokens=1000, agent='checklist')

    try:
        parsed = _parse_json(result['text'])
    except json.JSONDecodeError as e:
        raise RuntimeError(f'LLM returned invalid JSON: {e}')

    items = parsed.get('items', [])
    # Normalise — ensure all fields exist
    clean = []
    for item in items:
        clean.append({
            'cat':    str(item.get('cat', 'GENERAL')).upper(),
            'label':  str(item.get('label', '')),
            'done':   bool(item.get('done', False)),
            'detail': str(item.get('detail', '')),
        })

    return {
        'items':      clean,
        'tokens_used': result['tokens_used'],
        'model':      result['model'],
        'provider':   result['provider'],
        'latency_ms': result['latency_ms'],
    }