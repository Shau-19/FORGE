import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm, prompts

def _clamp(v, lo=0, hi=100):
    try: return max(lo, min(hi, int(v)))
    except: return 50

def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].strip()=='```' else lines[1:])
    return json.loads(text.strip())

def handle_validate(body: dict) -> dict:
    idea     = body.get('idea','').strip()
    audience = body.get('audience','General').strip() or 'General'
    if len(idea) < 5:
        raise ValueError('idea must be at least 5 characters')

    system, user = prompts.validate_idea(idea, audience)
    result = llm.call(prompt=user, system=system, max_tokens=900)

    try:
        p = _parse_json(result['text'])
    except json.JSONDecodeError as e:
        raise RuntimeError(f'LLM returned invalid JSON: {e} | raw: {result["text"][:200]}')

    m = p.get('metrics', {})
    a = p.get('analysis', {})
    return {
        'viability': _clamp(p.get('viability', 70)),
        'market':    _clamp(p.get('market', 65)),
        'risk':      _clamp(p.get('risk', 50)),
        'metrics': {
            'technical_feasibility': _clamp(m.get('technical_feasibility', 70)),
            'revenue_potential':     _clamp(m.get('revenue_potential', 65)),
            'time_to_market':        _clamp(m.get('time_to_market', 60)),
            'competitive_moat':      _clamp(m.get('competitive_moat', 55)),
        },
        'analysis': {
            'strength':       str(a.get('strength', 'Strong value proposition.')),
            'risk':           str(a.get('risk', 'Execution complexity.')),
            'recommendation': str(a.get('recommendation', 'Build a focused MVP.')),
        },
        'stack':       list(p.get('stack', ['FastAPI','React','PostgreSQL']))[:8],
        'tokens_used': result['tokens_used'],
        'model':       result['model'],
        'provider':    result['provider'],
        'latency_ms':  result['latency_ms'],
    }