import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm, prompts

def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].strip()=='```' else lines[1:])
    return json.loads(text.strip())

def handle_prd(body: dict) -> dict:
    idea     = body.get('idea','').strip()
    audience = body.get('audience','General')
    stack    = body.get('stack', [])
    sections = body.get('sections', ['overview','features','stories','tech'])
    if len(idea) < 5:
        raise ValueError('idea too short')

    system, user = prompts.generate_prd(idea, audience, stack, sections)
    result = llm.call(prompt=user, system=system, max_tokens=1600, agent='prd')

    try:
        parsed = _parse_json(result['text'])
    except json.JSONDecodeError as e:
        raise RuntimeError(f'LLM returned invalid JSON: {e}')

    sections_out = {k: str(v) for k, v in parsed.items() if k in sections and v}
    return {
        'sections':    sections_out,
        'tokens_used': result['tokens_used'],
        'model':       result['model'],
        'provider':    result['provider'],
        'latency_ms':  result['latency_ms'],
    }

def handle_prd_refine(body: dict) -> dict:
    section_key     = body.get('section_key', '')
    section_label   = body.get('section_label', section_key.upper())
    current_content = body.get('current_content', '')
    instruction     = body.get('instruction', '').strip()
    if not instruction:
        raise ValueError('instruction required')

    system, user = prompts.refine_prd_section(section_label, current_content, instruction)
    result = llm.call(prompt=user, system=system, max_tokens=700, agent='prd_refine')
    return {
        'section_key':     section_key,
        'updated_content': result['text'],
        'tokens_used':     result['tokens_used'],
    }