"""
server.py — FORGE entry point

Pure Python HTTP server. No Node, no npm, no external web framework.
Routes incoming requests to LangGraph agents (or direct handlers as fallback).

Run:  python server.py
Open: http://localhost:8000
"""
'''
import os
import sys
import json
import mimetypes
import time
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
# Sliding-window rate limiter with two layers:
#   Per-IP  — max runs and tokens per hour (prevents individual abuse)
#   Global  — hard token cap across all users (prevents runaway API costs)
#
# Limits are read from env vars so they're easy to adjust on Render
# without a code change.

class RateLimiter:
    MAX_RUNS_PER_HOUR   = int(os.getenv("RL_MAX_RUNS_PER_HOUR",   "10"))
    MAX_TOKENS_PER_HOUR = int(os.getenv("RL_MAX_TOKENS_PER_HOUR", "50000"))
    GLOBAL_TOKEN_BUDGET = int(os.getenv("RL_GLOBAL_TOKENS",       "200000"))
    WINDOW_SECS         = 3600  # 1-hour sliding window

    def __init__(self):
        self._lock        = threading.Lock()
        self._ip_runs     = {}  # ip -> [(timestamp, 1)]
        self._ip_tokens   = {}  # ip -> [(timestamp, n_tokens)]
        self._global_toks = []  # [(timestamp, n_tokens)]
        self.stats = {
            "total_requests":       0,
            "blocked_rate_limit":   0,
            "blocked_token_budget": 0,
            "total_tokens_served":  0,
        }

    def _prune(self, lst: list) -> list:
        """Drop entries that have fallen outside the sliding window."""
        cutoff = time.time() - self.WINDOW_SECS
        return [(t, v) for t, v in lst if t > cutoff]

    def check_run(self, ip: str) -> tuple[bool, str]:
        """
        Gate a pipeline run before the LLM call is made.
        Returns (allowed, reason_message).
        """
        with self._lock:
            self.stats["total_requests"] += 1
            now = time.time()

            self._ip_runs[ip]   = self._prune(self._ip_runs.get(ip, []))
            self._ip_tokens[ip] = self._prune(self._ip_tokens.get(ip, []))
            self._global_toks   = self._prune(self._global_toks)

            if len(self._ip_runs[ip]) >= self.MAX_RUNS_PER_HOUR:
                self.stats["blocked_rate_limit"] += 1
                wait = int(self._ip_runs[ip][0][0] + self.WINDOW_SECS - now)
                return False, (
                    f"Rate limit: max {self.MAX_RUNS_PER_HOUR} runs/hour. "
                    f"Retry in {wait // 60}m {wait % 60}s."
                )

            ip_toks = sum(v for _, v in self._ip_tokens[ip])
            if ip_toks >= self.MAX_TOKENS_PER_HOUR:
                self.stats["blocked_token_budget"] += 1
                return False, (
                    f"Token budget exhausted: {ip_toks:,} / "
                    f"{self.MAX_TOKENS_PER_HOUR:,} tokens used this hour."
                )

            global_toks = sum(v for _, v in self._global_toks)
            if global_toks >= self.GLOBAL_TOKEN_BUDGET:
                self.stats["blocked_token_budget"] += 1
                return False, "Global token budget reached. Try again later."

            self._ip_runs[ip].append((now, 1))
            return True, "ok"

    def record_tokens(self, ip: str, n: int):
        """Record actual token usage after the LLM call returns."""
        with self._lock:
            now = time.time()
            self._ip_tokens[ip] = self._prune(self._ip_tokens.get(ip, []))
            self._ip_tokens[ip].append((now, n))
            self._global_toks.append((now, n))
            self.stats["total_tokens_served"] += n

    def get_status(self, ip: str) -> dict:
        """Current usage snapshot for a given IP — served at /api/metrics."""
        with self._lock:
            self._ip_runs[ip]   = self._prune(self._ip_runs.get(ip, []))
            self._ip_tokens[ip] = self._prune(self._ip_tokens.get(ip, []))
            self._global_toks   = self._prune(self._global_toks)
            ip_toks     = sum(v for _, v in self._ip_tokens[ip])
            global_toks = sum(v for _, v in self._global_toks)
            runs_used   = len(self._ip_runs[ip])
            return {
                "ip":               ip,
                "runs_used":        runs_used,
                "runs_limit":       self.MAX_RUNS_PER_HOUR,
                "runs_remaining":   max(0, self.MAX_RUNS_PER_HOUR - runs_used),
                "tokens_used":      ip_toks,
                "tokens_limit":     self.MAX_TOKENS_PER_HOUR,
                "tokens_remaining": max(0, self.MAX_TOKENS_PER_HOUR - ip_toks),
                "global_tokens":    global_toks,
                "global_limit":     self.GLOBAL_TOKEN_BUDGET,
                "window_secs":      self.WINDOW_SECS,
            }


# Singleton shared across all requests
_rate_limiter = RateLimiter()

# Only these endpoints trigger expensive LLM calls
RATE_LIMITED_PATHS = {
    "/api/validate", "/api/prd", "/api/scaffold",
    "/api/checklist", "/api/diagram/modify", "/api/checklist/doit",
    "/api/knowledge/generate",
}


# ---------------------------------------------------------------------------
# Bootstrap — load .env and imports
# ---------------------------------------------------------------------------

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent))

# LangGraph is optional — server starts normally without it
try:
    from agents.pipeline import get_pipeline
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

from api.validate  import handle_validate
from api.prd       import handle_prd, handle_prd_refine
from api.scaffold  import handle_scaffold
from api.checklist import handle_checklist
from api.cicd      import handle_cicd_watch, handle_cicd_autofix
from api.diagram   import handle_diagram_modify
from api.knowledge import handle_knowledge_generate
from api.doit      import handle_doit
from api.export    import handle_export_zip, handle_export_pdf
from api.health    import handle_health

PORT       = int(os.getenv("PORT", 8000))
STATIC_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ForgeHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path == "/api/health":
            info = handle_health()
            info["langgraph"] = LANGGRAPH_AVAILABLE
            self._json(200, info)
            return

        if path == "/api/metrics":
            ip     = self._get_ip()
            status = _rate_limiter.get_status(ip)
            status["global_stats"] = _rate_limiter.stats
            self._json(200, status)
            return

        self._serve_static(path)

    def do_POST(self):
        path   = urlparse(self.path).path.rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        # Block expensive calls if the IP has hit its limit
        if path in RATE_LIMITED_PATHS:
            ip = self._get_ip()
            allowed, reason = _rate_limiter.check_run(ip)
            if not allowed:
                self._json(429, {
                    "error":        reason,
                    "rate_limited": True,
                    "status":       _rate_limiter.get_status(ip),
                })
                return

        try:
            if LANGGRAPH_AVAILABLE:
                self._route_langgraph(path, body)
            else:
                self._route_direct(path, body)
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except RuntimeError as e:
            self._json(503, {"error": str(e)})
        except Exception as e:
            self._json(500, {"error": f"Internal error: {e}"})

    # -----------------------------------------------------------------------
    # Routing
    # -----------------------------------------------------------------------

    def _route_langgraph(self, path: str, body: dict):
        """Run requests through the LangGraph agent pipeline."""
        pipeline = get_pipeline()

        # Binary downloads bypass the agent pipeline
        if path == "/api/export/zip":
            self._send_binary(handle_export_zip(body), "application/zip")
            return
        if path == "/api/export/pdf":
            self._send_binary(handle_export_pdf(body), "application/pdf")
            return

        # CI/CD always runs direct — patch application and GitHub API calls
        # don't fit cleanly into the LangGraph state model
        if path in ("/api/cicd/watch", "/api/cicd/autofix", "/api/knowledge/generate"):
            self._route_direct(path, body)
            return

        routes = {
            "/api/validate":       ("validator",  self._fmt_validate),
            "/api/prd":            ("prd",        self._fmt_prd),
            "/api/prd/refine":     ("prd_refine", self._fmt_prd_refine),
            "/api/prd_refine":     ("prd_refine", self._fmt_prd_refine),
            "/api/scaffold":       ("scaffold",   self._fmt_scaffold),
            "/api/checklist":      ("checklist",  self._fmt_checklist),
            "/api/checklist/doit": ("doit",       self._fmt_doit),
            "/api/diagram/modify":    ("diagram",    self._fmt_diagram),
            "/api/knowledge/generate": ("knowledge", self._fmt_knowledge),
        }

        if path not in routes:
            self._json(404, {"error": f"Unknown route: {path}"})
            return

        agent_name, formatter = routes[path]
        result   = pipeline.run_agent(agent_name, body)
        response = formatter(result, body)

        if path in RATE_LIMITED_PATHS:
            tokens = response.get("tokens_used", 0) or result.get("tokens_total", 0)
            if tokens:
                _rate_limiter.record_tokens(self._get_ip(), tokens)

        self._json(200, response)

    def _route_direct(self, path: str, body: dict):
        """Fallback routing when LangGraph is unavailable, and for CI/CD."""
        handlers = {
            "/api/validate":       lambda: handle_validate(body),
            "/api/prd":            lambda: handle_prd(body),
            "/api/prd/refine":     lambda: handle_prd_refine(body),
            "/api/prd_refine":     lambda: handle_prd_refine(body),
            "/api/scaffold":       lambda: handle_scaffold(body),
            "/api/checklist":      lambda: handle_checklist(body),
            "/api/checklist/doit": lambda: handle_doit(body),
            "/api/cicd/watch":     lambda: handle_cicd_watch(body),
            "/api/cicd/autofix":   lambda: handle_cicd_autofix(body),
            "/api/diagram/modify": lambda: handle_diagram_modify(body),
            "/api/knowledge/generate": lambda: handle_knowledge_generate(body),
        }

        if path == "/api/export/zip":
            self._send_binary(handle_export_zip(body), "application/zip")
            return
        if path == "/api/export/pdf":
            self._send_binary(handle_export_pdf(body), "application/pdf")
            return
        if path not in handlers:
            self._json(404, {"error": f"Unknown route: {path}"})
            return

        resp = handlers[path]()
        if resp is not None:
            if path in RATE_LIMITED_PATHS:
                tokens = resp.get("tokens_used", 0) if isinstance(resp, dict) else 0
                if tokens:
                    _rate_limiter.record_tokens(self._get_ip(), tokens)
            self._json(200, resp)

    # -----------------------------------------------------------------------
    # Response formatters
    # Translate the LangGraph state dict into the JSON shape the frontend expects
    # -----------------------------------------------------------------------

    def _fmt_validate(self, r, _):
        v = r.get("validation", {})
        return {**v, "stack": r.get("stack", v.get("stack", [])),
                "tokens_used": r.get("tokens_total", 0)}

    def _fmt_prd(self, r, _):
        p = r.get("prd", {})
        return {
            "sections":    p.get("sections", {}),
            "tokens_used": r.get("tokens_total", 0),
            "model":       p.get("model", ""),
            "provider":    p.get("provider", ""),
            "latency_ms":  p.get("latency_ms", 0),
        }

    def _fmt_prd_refine(self, r, body):
        return {
            "section_key":     r.get("section_key", body.get("section_key", "")),
            "updated_content": r.get("refined_content", ""),
            "tokens_used":     r.get("tokens_total", 0),
        }

    def _fmt_scaffold(self, r, _):
        s = r.get("scaffold", {})
        return {
            "files":        s.get("files", []),
            "repo_url":     s.get("repo_url", ""),
            "pushed":       s.get("pushed", 0),
            "github_error": s.get("github_error"),
            "tokens_used":  r.get("tokens_total", 0),
            "model":        s.get("model", ""),
            "provider":     s.get("provider", ""),
            "latency_ms":   s.get("latency_ms", 0),
        }

    def _fmt_checklist(self, r, _):
        c = r.get("checklist", {})
        return {
            "items":       c.get("items", []),
            "tokens_used": r.get("tokens_total", 0),
            "model":       c.get("model", ""),
            "provider":    c.get("provider", ""),
            "latency_ms":  c.get("latency_ms", 0),
        }

    def _fmt_doit(self, r, _):
        d = r.get("doit_result", {})
        return {
            "steps":          d.get("steps", []),
            "code_snippet":   d.get("code_snippet", ""),
            "references":     d.get("references", []),
            "estimated_time": d.get("estimated_time", ""),
            "tokens_used":    r.get("tokens_total", 0),
            "model":          d.get("model", ""),
            "provider":       d.get("provider", ""),
            "latency_ms":     d.get("latency_ms", 0),
        }

    def _fmt_diagram(self, r, _):
        return {
            "nodes":          r.get("diagram_nodes", []),
            "edges":          r.get("diagram_edges", []),
            "change_summary": r.get("diagram_summary", "Diagram updated."),
            "tokens_used":    r.get("tokens_total", 0),
        }

    def _fmt_knowledge(self, r, body):
        # Knowledge generation runs direct (not via LangGraph pipeline state)
        # so we fall back to direct handler
        return handle_knowledge_generate(body)

    # -----------------------------------------------------------------------
    # HTTP helpers
    # -----------------------------------------------------------------------

    def _get_ip(self) -> str:
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def _serve_static(self, path: str):
        """Serve files from the project root. Unknown paths fall back to index.html (SPA)."""
        fp = STATIC_DIR / "index.html" if path in ("", "/") else STATIC_DIR / path.lstrip("/")
        if fp.is_file():
            mime, _ = mimetypes.guess_type(str(fp))
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", len(data))
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        else:
            idx  = STATIC_DIR / "index.html"
            data = idx.read_bytes() if idx.exists() else b"Not found"
            self.send_response(200 if idx.exists() else 404)
            self.send_header("Content-Type", "text/html")
            self._cors()
            self.end_headers()
            self.wfile.write(data)

    def _send_binary(self, result_tuple, content_type: str):
        data, filename = result_tuple
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(data))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        """Compact request log that replaces httpd's noisy default."""
        code = args[1] if len(args) > 1 else "?"
        path = args[0].split()[1] if args else "?"
        meth = args[0].split()[0] if args else "?"
        color = "\033[32m" if str(code).startswith("2") else "\033[31m" if str(code)[0] in "45" else "\033[33m"
        mode  = "LG" if LANGGRAPH_AVAILABLE else "Direct"
        print(f"  {color}{code}\033[0m  {meth:6} {path}  [{mode}]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mode = (
        "\033[32mLangGraph ✓\033[0m" if LANGGRAPH_AVAILABLE
        else "\033[33mDirect (pip install langgraph langchain-core)\033[0m"
    )
    print(f"\n  \033[1m⬡ FORGE — LangGraph Multi-Agent Pipeline\033[0m")
    print(f"  Mode     : {mode}")
    print(f"  Provider : {os.getenv('LLM_PROVIDER', 'groq').upper()}")
    print(f"  Port     : {PORT}")
    print(f"  URL      : \033[4mhttp://localhost:{PORT}\033[0m\n")

    httpd = HTTPServer(("", PORT), ForgeHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


        '''

"""
server.py — FORGE entry point

Pure Python HTTP server. No Node, no npm, no external web framework.
Routes incoming requests to LangGraph agents (or direct handlers as fallback).

Run:  python server.py
Open: http://localhost:8000
"""

import os
import sys
import json
import mimetypes
import time
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
# Sliding-window rate limiter with two layers:
#   Per-IP  — max runs and tokens per hour (prevents individual abuse)
#   Global  — hard token cap across all users (prevents runaway API costs)
#
# Limits are read from env vars so they're easy to adjust on Render
# without a code change.

class RateLimiter:
    MAX_RUNS_PER_HOUR   = int(os.getenv("RL_MAX_RUNS_PER_HOUR",   "10"))
    MAX_TOKENS_PER_HOUR = int(os.getenv("RL_MAX_TOKENS_PER_HOUR", "50000"))
    GLOBAL_TOKEN_BUDGET = int(os.getenv("RL_GLOBAL_TOKENS",       "200000"))
    WINDOW_SECS         = 3600  # 1-hour sliding window

    def __init__(self):
        self._lock        = threading.Lock()
        self._ip_runs     = {}  # ip -> [(timestamp, 1)]
        self._ip_tokens   = {}  # ip -> [(timestamp, n_tokens)]
        self._global_toks = []  # [(timestamp, n_tokens)]
        self.stats = {
            "total_requests":       0,
            "blocked_rate_limit":   0,
            "blocked_token_budget": 0,
            "total_tokens_served":  0,
        }

    def _prune(self, lst: list) -> list:
        """Drop entries that have fallen outside the sliding window."""
        cutoff = time.time() - self.WINDOW_SECS
        return [(t, v) for t, v in lst if t > cutoff]

    def check_run(self, ip: str) -> tuple[bool, str]:
        """
        Gate a pipeline run before the LLM call is made.
        Returns (allowed, reason_message).
        """
        with self._lock:
            self.stats["total_requests"] += 1
            now = time.time()

            self._ip_runs[ip]   = self._prune(self._ip_runs.get(ip, []))
            self._ip_tokens[ip] = self._prune(self._ip_tokens.get(ip, []))
            self._global_toks   = self._prune(self._global_toks)

            if len(self._ip_runs[ip]) >= self.MAX_RUNS_PER_HOUR:
                self.stats["blocked_rate_limit"] += 1
                wait = int(self._ip_runs[ip][0][0] + self.WINDOW_SECS - now)
                return False, (
                    f"Rate limit: max {self.MAX_RUNS_PER_HOUR} runs/hour. "
                    f"Retry in {wait // 60}m {wait % 60}s."
                )

            ip_toks = sum(v for _, v in self._ip_tokens[ip])
            if ip_toks >= self.MAX_TOKENS_PER_HOUR:
                self.stats["blocked_token_budget"] += 1
                return False, (
                    f"Token budget exhausted: {ip_toks:,} / "
                    f"{self.MAX_TOKENS_PER_HOUR:,} tokens used this hour."
                )

            global_toks = sum(v for _, v in self._global_toks)
            if global_toks >= self.GLOBAL_TOKEN_BUDGET:
                self.stats["blocked_token_budget"] += 1
                return False, "Global token budget reached. Try again later."

            self._ip_runs[ip].append((now, 1))
            return True, "ok"

    def record_tokens(self, ip: str, n: int):
        """Record actual token usage after the LLM call returns."""
        with self._lock:
            now = time.time()
            self._ip_tokens[ip] = self._prune(self._ip_tokens.get(ip, []))
            self._ip_tokens[ip].append((now, n))
            self._global_toks.append((now, n))
            self.stats["total_tokens_served"] += n

    def get_status(self, ip: str) -> dict:
        """Current usage snapshot for a given IP — served at /api/metrics."""
        with self._lock:
            self._ip_runs[ip]   = self._prune(self._ip_runs.get(ip, []))
            self._ip_tokens[ip] = self._prune(self._ip_tokens.get(ip, []))
            self._global_toks   = self._prune(self._global_toks)
            ip_toks     = sum(v for _, v in self._ip_tokens[ip])
            global_toks = sum(v for _, v in self._global_toks)
            runs_used   = len(self._ip_runs[ip])
            return {
                "ip":               ip,
                "runs_used":        runs_used,
                "runs_limit":       self.MAX_RUNS_PER_HOUR,
                "runs_remaining":   max(0, self.MAX_RUNS_PER_HOUR - runs_used),
                "tokens_used":      ip_toks,
                "tokens_limit":     self.MAX_TOKENS_PER_HOUR,
                "tokens_remaining": max(0, self.MAX_TOKENS_PER_HOUR - ip_toks),
                "global_tokens":    global_toks,
                "global_limit":     self.GLOBAL_TOKEN_BUDGET,
                "window_secs":      self.WINDOW_SECS,
            }


# Singleton shared across all requests
_rate_limiter = RateLimiter()

# Only these endpoints trigger expensive LLM calls
RATE_LIMITED_PATHS = {
    "/api/validate", "/api/prd", "/api/scaffold",
    "/api/checklist", "/api/diagram/modify", "/api/checklist/doit",
}


# ---------------------------------------------------------------------------
# Bootstrap — load .env and imports
# ---------------------------------------------------------------------------

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent))

# LangGraph is optional — server starts normally without it
try:
    from agents.pipeline import get_pipeline
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

from api.validate  import handle_validate
from api.prd       import handle_prd, handle_prd_refine
from api.scaffold  import handle_scaffold
from api.checklist import handle_checklist
from api.cicd      import handle_cicd_watch, handle_cicd_autofix
from api.diagram   import handle_diagram_modify
from api.repochat  import handle_repochat_index, handle_repochat_ask
from api.docschat  import (handle_docschat_index, handle_docschat_ask,
                            handle_kb_pdf, handle_kb_url,
                            handle_kb_github, handle_kb_ask)
from api.doit      import handle_doit
from api.export    import handle_export_zip, handle_export_pdf
from api.health    import handle_health

PORT       = int(os.getenv("PORT", 8000))
STATIC_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ForgeHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path == "/api/health":
            info = handle_health()
            info["langgraph"] = LANGGRAPH_AVAILABLE
            self._json(200, info)
            return

        if path == "/api/metrics":
            ip     = self._get_ip()
            status = _rate_limiter.get_status(ip)
            status["global_stats"] = _rate_limiter.stats
            self._json(200, status)
            return

        self._serve_static(path)

    def do_POST(self):
        path   = urlparse(self.path).path.rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        # Block expensive calls if the IP has hit its limit
        if path in RATE_LIMITED_PATHS:
            ip = self._get_ip()
            allowed, reason = _rate_limiter.check_run(ip)
            if not allowed:
                self._json(429, {
                    "error":        reason,
                    "rate_limited": True,
                    "status":       _rate_limiter.get_status(ip),
                })
                return

        try:
            if LANGGRAPH_AVAILABLE:
                self._route_langgraph(path, body)
            else:
                self._route_direct(path, body)
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except RuntimeError as e:
            self._json(503, {"error": str(e)})
        except Exception as e:
            self._json(500, {"error": f"Internal error: {e}"})

    # -----------------------------------------------------------------------
    # Routing
    # -----------------------------------------------------------------------

    def _route_langgraph(self, path: str, body: dict):
        """Run requests through the LangGraph agent pipeline."""
        pipeline = get_pipeline()

        # Binary downloads bypass the agent pipeline
        if path == "/api/export/zip":
            self._send_binary(handle_export_zip(body), "application/zip")
            return
        if path == "/api/export/pdf":
            self._send_binary(handle_export_pdf(body), "application/pdf")
            return

        # CI/CD and KB routes always run direct
        if path in ("/api/cicd/watch", "/api/cicd/autofix",
                    "/api/repochat/index", "/api/repochat/ask",
                    "/api/docschat/index", "/api/docschat/ask",
                    "/api/kb/pdf", "/api/kb/url",
                    "/api/kb/github", "/api/kb/ask"):
            self._route_direct(path, body)
            return

        routes = {
            "/api/validate":       ("validator",  self._fmt_validate),
            "/api/prd":            ("prd",        self._fmt_prd),
            "/api/prd/refine":     ("prd_refine", self._fmt_prd_refine),
            "/api/prd_refine":     ("prd_refine", self._fmt_prd_refine),
            "/api/scaffold":       ("scaffold",   self._fmt_scaffold),
            "/api/checklist":      ("checklist",  self._fmt_checklist),
            "/api/checklist/doit": ("doit",       self._fmt_doit),
            "/api/diagram/modify": ("diagram",    self._fmt_diagram),
        }

        if path not in routes:
            self._json(404, {"error": f"Unknown route: {path}"})
            return

        agent_name, formatter = routes[path]
        result   = pipeline.run_agent(agent_name, body)
        response = formatter(result, body)

        if path in RATE_LIMITED_PATHS:
            tokens = response.get("tokens_used", 0) or result.get("tokens_total", 0)
            if tokens:
                _rate_limiter.record_tokens(self._get_ip(), tokens)

        self._json(200, response)

    def _route_direct(self, path: str, body: dict):
        """Fallback routing when LangGraph is unavailable, and for CI/CD."""
        handlers = {
            "/api/validate":       lambda: handle_validate(body),
            "/api/prd":            lambda: handle_prd(body),
            "/api/prd/refine":     lambda: handle_prd_refine(body),
            "/api/prd_refine":     lambda: handle_prd_refine(body),
            "/api/scaffold":       lambda: handle_scaffold(body),
            "/api/checklist":      lambda: handle_checklist(body),
            "/api/checklist/doit": lambda: handle_doit(body),
            "/api/cicd/watch":     lambda: handle_cicd_watch(body),
            "/api/cicd/autofix":   lambda: handle_cicd_autofix(body),
            "/api/diagram/modify": lambda: handle_diagram_modify(body),
            "/api/repochat/index": lambda: handle_repochat_index(body),
            "/api/repochat/ask":   lambda: handle_repochat_ask(body),
            "/api/docschat/index": lambda: handle_docschat_index(body),
            "/api/docschat/ask":   lambda: handle_docschat_ask(body),
            "/api/kb/pdf":         lambda: handle_kb_pdf(body),
            "/api/kb/url":         lambda: handle_kb_url(body),
            "/api/kb/github":      lambda: handle_kb_github(body),
            "/api/kb/ask":         lambda: handle_kb_ask(body),
        }

        if path == "/api/export/zip":
            self._send_binary(handle_export_zip(body), "application/zip")
            return
        if path == "/api/export/pdf":
            self._send_binary(handle_export_pdf(body), "application/pdf")
            return
        if path not in handlers:
            self._json(404, {"error": f"Unknown route: {path}"})
            return

        resp = handlers[path]()
        if resp is not None:
            if path in RATE_LIMITED_PATHS:
                tokens = resp.get("tokens_used", 0) if isinstance(resp, dict) else 0
                if tokens:
                    _rate_limiter.record_tokens(self._get_ip(), tokens)
            self._json(200, resp)

    # -----------------------------------------------------------------------
    # Response formatters
    # Translate the LangGraph state dict into the JSON shape the frontend expects
    # -----------------------------------------------------------------------

    def _fmt_validate(self, r, _):
        v = r.get("validation", {})
        return {**v, "stack": r.get("stack", v.get("stack", [])),
                "tokens_used": r.get("tokens_total", 0)}

    def _fmt_prd(self, r, _):
        p = r.get("prd", {})
        return {
            "sections":    p.get("sections", {}),
            "tokens_used": r.get("tokens_total", 0),
            "model":       p.get("model", ""),
            "provider":    p.get("provider", ""),
            "latency_ms":  p.get("latency_ms", 0),
        }

    def _fmt_prd_refine(self, r, body):
        return {
            "section_key":     r.get("section_key", body.get("section_key", "")),
            "updated_content": r.get("refined_content", ""),
            "tokens_used":     r.get("tokens_total", 0),
        }

    def _fmt_scaffold(self, r, _):
        s = r.get("scaffold", {})
        return {
            "files":        s.get("files", []),
            "repo_url":     s.get("repo_url", ""),
            "pushed":       s.get("pushed", 0),
            "github_error": s.get("github_error"),
            "tokens_used":  r.get("tokens_total", 0),
            "model":        s.get("model", ""),
            "provider":     s.get("provider", ""),
            "latency_ms":   s.get("latency_ms", 0),
        }

    def _fmt_checklist(self, r, _):
        c = r.get("checklist", {})
        return {
            "items":       c.get("items", []),
            "tokens_used": r.get("tokens_total", 0),
            "model":       c.get("model", ""),
            "provider":    c.get("provider", ""),
            "latency_ms":  c.get("latency_ms", 0),
        }

    def _fmt_doit(self, r, _):
        d = r.get("doit_result", {})
        return {
            "steps":          d.get("steps", []),
            "code_snippet":   d.get("code_snippet", ""),
            "references":     d.get("references", []),
            "estimated_time": d.get("estimated_time", ""),
            "tokens_used":    r.get("tokens_total", 0),
            "model":          d.get("model", ""),
            "provider":       d.get("provider", ""),
            "latency_ms":     d.get("latency_ms", 0),
        }

    def _fmt_diagram(self, r, _):
        return {
            "nodes":          r.get("diagram_nodes", []),
            "edges":          r.get("diagram_edges", []),
            "change_summary": r.get("diagram_summary", "Diagram updated."),
            "tokens_used":    r.get("tokens_total", 0),
        }

    # -----------------------------------------------------------------------
    # HTTP helpers
    # -----------------------------------------------------------------------

    def _get_ip(self) -> str:
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def _serve_static(self, path: str):
        """Serve files from the project root. Unknown paths fall back to index.html (SPA)."""
        fp = STATIC_DIR / "index.html" if path in ("", "/") else STATIC_DIR / path.lstrip("/")
        if fp.is_file():
            mime, _ = mimetypes.guess_type(str(fp))
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", len(data))
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        else:
            idx  = STATIC_DIR / "index.html"
            data = idx.read_bytes() if idx.exists() else b"Not found"
            self.send_response(200 if idx.exists() else 404)
            self.send_header("Content-Type", "text/html")
            self._cors()
            self.end_headers()
            self.wfile.write(data)

    def _send_binary(self, result_tuple, content_type: str):
        data, filename = result_tuple
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(data))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        """Compact request log that replaces httpd's noisy default."""
        code = args[1] if len(args) > 1 else "?"
        path = args[0].split()[1] if args else "?"
        meth = args[0].split()[0] if args else "?"
        color = "\033[32m" if str(code).startswith("2") else "\033[31m" if str(code)[0] in "45" else "\033[33m"
        mode  = "LG" if LANGGRAPH_AVAILABLE else "Direct"
        print(f"  {color}{code}\033[0m  {meth:6} {path}  [{mode}]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mode = (
        "\033[32mLangGraph ✓\033[0m" if LANGGRAPH_AVAILABLE
        else "\033[33mDirect (pip install langgraph langchain-core)\033[0m"
    )
    print(f"\n  \033[1m⬡ FORGE — LangGraph Multi-Agent Pipeline\033[0m")
    print(f"  Mode     : {mode}")
    print(f"  Provider : {os.getenv('LLM_PROVIDER', 'groq').upper()}")
    print(f"  Port     : {PORT}")
    print(f"  URL      : \033[4mhttp://localhost:{PORT}\033[0m\n")

    httpd = HTTPServer(("", PORT), ForgeHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")