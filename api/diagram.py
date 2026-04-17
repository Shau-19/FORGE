"""
api/diagram.py — POST /api/diagram/modify
Phase 4: AI modifies architecture diagram nodes/edges.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm, prompts


DEFAULT_NODES = [
    {'label': 'Browser',    'color': '#3b82f6', 'x': 0.10, 'y': 0.50, 'r': 26},
    {'label': 'FastAPI',    'color': '#34d399', 'x': 0.30, 'y': 0.28, 'r': 24},
    {'label': 'React',      'color': '#6366f1', 'x': 0.30, 'y': 0.72, 'r': 24},
    {'label': 'PostgreSQL', 'color': '#fbbf24', 'x': 0.55, 'y': 0.20, 'r': 22},
    {'label': 'Redis',      'color': '#ef4444', 'x': 0.55, 'y': 0.50, 'r': 20},
    {'label': 'Stripe',     'color': '#34d399', 'x': 0.55, 'y': 0.80, 'r': 20},
    {'label': 'Anthropic',  'color': '#a855f7', 'x': 0.80, 'y': 0.35, 'r': 22},
    {'label': 'GitHub CI',  'color': '#6b7280', 'x': 0.80, 'y': 0.65, 'r': 20},
]

DEFAULT_EDGES = [[0,1],[0,2],[1,3],[1,4],[1,5],[1,6],[1,7]]


def handle_diagram_modify(body: dict) -> dict:
    instruction = body.get('instruction', '').strip()
    nodes       = body.get('nodes', DEFAULT_NODES)
    edges       = body.get('edges', DEFAULT_EDGES)
    stack       = body.get('stack', [])

    if not instruction:
        raise ValueError('instruction required')

    system, user = prompts.modify_diagram(nodes, edges, instruction, stack)
    result = llm.call(prompt=user, system=system, max_tokens=1000)

    text = result['text'].strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
    
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'LLM returned invalid diagram JSON: {e}')

    # Validate + normalise nodes
    clean_nodes = []
    for n in parsed.get('nodes', []):
        clean_nodes.append({
            'label': str(n.get('label', 'Node')),
            'color': str(n.get('color', '#6366f1')),
            'x':     float(max(0.05, min(0.95, n.get('x', 0.5)))),
            'y':     float(max(0.05, min(0.95, n.get('y', 0.5)))),
            'r':     int(max(14, min(32, n.get('r', 20)))),
        })

    clean_edges = []
    n_count = len(clean_nodes)
    for e in parsed.get('edges', []):
        if isinstance(e, (list, tuple)) and len(e) == 2:
            a, b = int(e[0]), int(e[1])
            if 0 <= a < n_count and 0 <= b < n_count and a != b:
                clean_edges.append([a, b])

    return {
        'nodes':          clean_nodes,
        'edges':          clean_edges,
        'change_summary': parsed.get('change_summary', 'Diagram updated.'),
        'tokens_used':    result['tokens_used'],
        'model':          result['model'],
        'provider':       result['provider'],
        'latency_ms':     result['latency_ms'],
    }