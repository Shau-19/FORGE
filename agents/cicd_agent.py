"""
agents/cicd_agent.py — CI/CD Monitor + Diagram Modifier Agents
"""
import json
from agents.base import BaseAgent
from agents.state import ForgeState
from core import prompts


class CICDAgent(BaseAgent):
    """Monitors GitHub Actions and suggests AI fixes."""
    name = "cicd"

    def run(self, state: ForgeState) -> dict:
        repo_url  = state.get("repo_url", "")
        branch    = state.get("branch", "main")
        gh_token  = state.get("github_token", "")

        if gh_token and repo_url:
            run_data = self._fetch_github_run(gh_token, repo_url, branch)
        else:
            # Demo mode
            run_data = self._demo_run()

        return {"cicd": run_data, "_tokens": 0}

    def _fetch_github_run(self, token: str, repo_url: str, branch: str) -> dict:
        import urllib.request, urllib.error
        repo_path = repo_url.replace("https://github.com/", "").rstrip("/")
        api_url   = f"https://api.github.com/repos/{repo_path}/actions/runs?branch={branch}&per_page=1"
        req = urllib.request.Request(
            api_url,
            headers={"Authorization": f"token {token}",
                     "Accept": "application/vnd.github.v3+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
                runs = data.get("workflow_runs", [])
                if not runs:
                    return self._demo_run()
                return self._parse_run(runs[0], token=token, repo_path=repo_path)
        except Exception:
            return self._demo_run()

    def _parse_run(self, run: dict, token: str = "", repo_path: str = "") -> dict:
        import urllib.request
        run_id = run.get("id")
        conclusion = run.get("conclusion") or "in_progress"

        jobs = []
        failure_log = ""

        # Fetch jobs for this run
        if token and repo_path and run_id:
            try:
                jobs_url = f"https://api.github.com/repos/{repo_path}/actions/runs/{run_id}/jobs"
                req = urllib.request.Request(jobs_url,
                    headers={"Authorization": f"token {token}",
                             "Accept": "application/vnd.github.v3+json"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    jobs_data = json.loads(r.read()).get("jobs", [])
                    jobs = [{"name": j["name"], "conclusion": j.get("conclusion") or j.get("status","in_progress")} for j in jobs_data]
                    # Fetch real log text from GitHub — gives LLM actual error lines
                    for j in jobs_data:
                        if j.get("conclusion") == "failure":
                            try:
                                log_req = urllib.request.Request(
                                    f"https://api.github.com/repos/{repo_path}/actions/jobs/{j['id']}/logs",
                                    headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"})
                                with urllib.request.urlopen(log_req, timeout=15) as r:
                                    raw = r.read().decode("utf-8", errors="replace")
                                failure_log += f"=== {j['name']} ===\n" + raw[-3000:] + "\n"
                            except Exception:
                                for step in j.get("steps", []):
                                    if step.get("conclusion") == "failure":
                                        failure_log += f"{j['name']} / {step['name']} failed\n"

            except Exception as e:
                print(f"  [CICD] jobs fetch failed: {e}")

        def job_conclusion(fragment):
            for j in jobs:
                if fragment.lower() in j["name"].lower():
                    c = j["conclusion"]
                    return "success" if c == "success" else "failure" if c == "failure" else "skipped" if c == "skipped" else "in_progress"
            return conclusion if conclusion != "in_progress" else "in_progress"

        return {
            "run_id":       run_id,
            "name":         run.get("name", "CI"),
            "branch":       run.get("head_branch", "main"),
            "conclusion":   conclusion,
            "url":          run.get("html_url", ""),
            "jobs":         jobs,
            "failure_log":  failure_log,
            "stage_build":  job_conclusion("build") if jobs else conclusion,
            "stage_test":   job_conclusion("test")  if jobs else conclusion,
            "stage_lint":   job_conclusion("lint")  if jobs else conclusion,
            "stage_deploy": job_conclusion("deploy") if jobs else "skipped",
        }

    def _demo_run(self) -> dict:
        return {
            "run_id":   42,
            "name":     "feat: add user authentication flow",
            "branch":   "main",
            "conclusion": "failure",
            "stage_build":  "success",
            "stage_test":   "success",
            "stage_lint":   "failure",
            "stage_deploy": "skipped",
            "failure_log":  "ruff check .\nbackend/main.py:14:1: F401 `os` imported but unused\nFound 1 error.",
            "jobs": [
                {"name": "Build", "conclusion": "success"},
                {"name": "Test",  "conclusion": "success"},
                {"name": "Lint",  "conclusion": "failure"},
                {"name": "Deploy","conclusion": "skipped"},
            ],
        }


class CICDAutoFixAgent(BaseAgent):
    """Analyzes CI/CD failures and generates patches."""
    name = "cicd_autofix"

    def run(self, state: ForgeState) -> dict:
        failure_log = state.get("failure_log", "")
        stack       = state.get("stack", [])

        system, user = prompts.analyze_cicd_failure(failure_log, stack)
        result = self.llm_call(user, system=system, max_tokens=900)
        parsed = self.parse_json(result["text"])

        return {
            "autofix": {
                "summary":    parsed.get("summary", ""),
                "root_cause": parsed.get("root_cause", ""),
                "patches":    parsed.get("patches", []),
                "commands":   parsed.get("commands", []),
                "model":      result["model"],
                "provider":   result["provider"],
                "latency_ms": result["latency_ms"],
            },
            "_tokens": result["tokens_used"],
        }


class DiagramAgent(BaseAgent):
    """AI-modifies architecture diagram based on natural language."""
    name = "diagram"

    DEFAULT_NODES = [
        {"label": "Browser",    "color": "#3b82f6", "x": 0.10, "y": 0.50, "r": 26},
        {"label": "FastAPI",    "color": "#34d399", "x": 0.30, "y": 0.28, "r": 24},
        {"label": "React",      "color": "#6366f1", "x": 0.30, "y": 0.72, "r": 24},
        {"label": "PostgreSQL", "color": "#fbbf24", "x": 0.55, "y": 0.20, "r": 22},
        {"label": "Redis",      "color": "#ef4444", "x": 0.55, "y": 0.50, "r": 20},
        {"label": "Stripe",     "color": "#34d399", "x": 0.55, "y": 0.80, "r": 20},
    ]
    DEFAULT_EDGES = [[0,1],[0,2],[1,3],[1,4],[1,5]]

    def run(self, state: ForgeState) -> dict:
        instruction = state.get("instruction", "")
        nodes       = state.get("diagram_nodes") or self.DEFAULT_NODES
        edges       = state.get("diagram_edges") or self.DEFAULT_EDGES
        stack       = state.get("stack", [])

        if not instruction:
            raise ValueError("instruction required")

        system, user = prompts.modify_diagram(nodes, edges, instruction, stack)
        result = self.llm_call(user, system=system, max_tokens=1000)
        parsed = self.parse_json(result["text"])

        clean_nodes = []
        for n in parsed.get("nodes", []):
            clean_nodes.append({
                "label": str(n.get("label", "Node")),
                "color": str(n.get("color", "#6366f1")),
                "x":     float(max(0.05, min(0.95, n.get("x", 0.5)))),
                "y":     float(max(0.05, min(0.95, n.get("y", 0.5)))),
                "r":     int(max(14, min(32, n.get("r", 20)))),
            })

        clean_edges = [
            [int(e[0]), int(e[1])]
            for e in parsed.get("edges", [])
            if isinstance(e, (list, tuple)) and len(e) == 2
            and 0 <= int(e[0]) < len(clean_nodes)
            and 0 <= int(e[1]) < len(clean_nodes)
            and e[0] != e[1]
        ]

        return {
            "diagram_nodes":  clean_nodes,
            "diagram_edges":  clean_edges,
            "diagram_summary": parsed.get("change_summary", "Diagram updated."),
            "_tokens":        result["tokens_used"],
        }