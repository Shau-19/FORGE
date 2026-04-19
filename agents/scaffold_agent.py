"""
agents/scaffold_agent.py — Code Scaffold Agent
Node 3 in the FORGE LangGraph pipeline.
Delegates to api/scaffold.py handle_scaffold() so both
LangGraph mode and direct mode share identical generation logic.
"""
import json
import urllib.request, urllib.error, base64
from agents.base import BaseAgent
from agents.state import ForgeState
from api.scaffold import handle_scaffold as _handle_scaffold


class ScaffoldAgent(BaseAgent):
    name = "scaffold"

    def run(self, state: ForgeState) -> dict:
        idea      = state["idea"]
        stack     = state.get("stack", [])
        structure = state.get("structure", "monorepo")
        name      = (state.get("repo_name")
                     or state.get("name")
                     or state.get("project_name", "forge-project"))
        gh_token  = state.get("github_token", "")
        repo_url  = state.get("repo_url", "")
        prd       = state.get("prd", {})

        # Extract overview from PRD sections if available
        prd_overview = ""
        if isinstance(prd, dict):
            prd_overview = prd.get("sections", {}).get("overview", "") or prd.get("overview", "")

        # Delegate entirely to api/scaffold.py — file-by-file generation,
        # scope detection, validation, and GitHub push all happen there.
        result = _handle_scaffold({
            "idea":         idea,
            "stack":        stack,
            "structure":    structure,
            "prd":          {"overview": prd_overview},
            "name":         name,
            "github_token": gh_token,
            "repo_url":     repo_url,
            "private":      False,
        })

        scaffold = {
            "files":        result.get("files", []),
            "repo_url":     result.get("repo_url", ""),
            "pushed":       result.get("pushed", 0),
            "github_error": result.get("github_error"),
            "scope":        result.get("scope", "mvp"),
            "model":        result.get("model", "multi-call"),
            "provider":     result.get("provider", "groq"),
            "latency_ms":   result.get("latency_ms", 0),
        }

        return {"scaffold": scaffold, "_tokens": result.get("tokens_used", 0)}

    # ── GitHub helpers kept here for any future agent-level use ─────────────

    def _github_get_username(self, token: str) -> str:
        req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}",
                     "Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("login", "user")

    def _github_create_repo(self, token: str, name: str, private: bool) -> dict:
        data = json.dumps({"name": name, "private": private, "auto_init": True}).encode()
        req  = urllib.request.Request(
            "https://api.github.com/user/repos",
            data=data, method="POST",
            headers={"Authorization": f"token {token}",
                     "Accept": "application/vnd.github.v3+json",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 422:
                return self._github_get_repo(token, name)
            raise RuntimeError(f"GitHub create repo failed: {e.code} — {body[:200]}")

    def _github_get_repo(self, token: str, name: str) -> dict:
        req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}",
                     "Accept": "application/vnd.github.v3+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                username = json.loads(r.read()).get("login", "user")
            req2 = urllib.request.Request(
                f"https://api.github.com/repos/{username}/{name}",
                headers={"Authorization": f"token {token}",
                         "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req2, timeout=10) as r:
                return json.loads(r.read())
        except Exception:
            return {"full_name": f"user/{name}", "html_url": f"https://github.com/user/{name}"}

    def _github_push_file(self, token: str, repo_full: str, path: str, content: str):
        encoded = base64.b64encode(content.encode()).decode()
        url     = f"https://api.github.com/repos/{repo_full}/contents/{path}"
        headers = {"Authorization": f"token {token}",
                   "Accept": "application/vnd.github.v3+json",
                   "Content-Type": "application/json"}
        payload = {"message": f"feat: add {path}", "content": encoded}
        data    = json.dumps(payload).encode()
        req     = urllib.request.Request(url, data=data, method="PUT", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 422:
                try:
                    get_req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(get_req, timeout=10) as r:
                        sha = json.loads(r.read()).get("sha")
                    payload["sha"] = sha
                    data = json.dumps(payload).encode()
                    req2 = urllib.request.Request(url, data=data, method="PUT", headers=headers)
                    with urllib.request.urlopen(req2, timeout=15) as r:
                        return json.loads(r.read())
                except Exception as e2:
                    raise RuntimeError(f"GitHub update {path} failed: {e2}")
            body = e.read().decode()
            raise RuntimeError(f"GitHub push {path} failed: {e.code} — {body[:100]}")
