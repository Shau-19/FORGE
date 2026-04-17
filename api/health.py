import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

PROVIDER = os.getenv('LLM_PROVIDER', 'groq').lower()
MODEL    = (os.getenv('LLM_MODEL_GROQ',   'llama-3.3-70b-versatile')
            if PROVIDER == 'groq'
            else os.getenv('LLM_MODEL_OPENAI', 'gpt-4o-mini'))

def handle_health() -> dict:
    return {'status':'ok','provider':PROVIDER,'model':MODEL,'version':'1.0'}














