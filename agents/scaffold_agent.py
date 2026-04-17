



"""
agents/scaffold_agent.py — Code Scaffold Agent
Node 3 in the FORGE LangGraph pipeline.
"""
import os, urllib.request, urllib.error, base64, json
from agents.base import BaseAgent
from agents.state import ForgeState
from core import prompts
from api.scaffold import _validate_scaffold
from core.prompts import get_ci_template


class ScaffoldAgent(BaseAgent):
    name = "scaffold"

    def run(self, state: ForgeState) -> dict:
        idea       = state["idea"]
        stack      = state.get("stack", [])
        structure  = state.get("structure", "monorepo")
        name       = state.get("repo_name") or state.get("name") or state.get("project_name", "forge-project")
        gh_token   = state.get("github_token", "")
        prd        = state.get("prd", {})
        prd_overview = prd.get("sections", {}).get("overview", "") if prd else ""

        system, user = prompts.generate_scaffold(idea, stack, structure, prd_overview)
        result = self.llm_call(user, system=system, max_tokens=5000)
        parsed = self.parse_json(result["text"])

        files      = parsed.get("files", [])
        readme     = parsed.get("readme", "")
        docker     = parsed.get("docker_compose", "")
        files=_validate_scaffold(files, stack)  # raises ValueError if invalid — must be fixed before pushing to GitHub
        gh_actions = get_ci_template(stack,files)  # deterministic — never LLM-generated
        

        existing_paths = {f["path"] for f in files}
        if readme and "README.md" not in existing_paths:
            files.append({"type": "file", "path": "README.md", "content": readme})
        if docker and "docker-compose.yml" not in existing_paths:
            files.append({"type": "file", "path": "docker-compose.yml", "content": docker})
        if gh_actions:
            files += [
                {"type": "dir",  "path": ".github/"},
                {"type": "dir",  "path": ".github/workflows/"},
                {"type": "file", "path": ".github/workflows/ci.yml", "content": gh_actions},
            ]

        repo_url = f"https://github.com/user/{name}"
        pushed   = 0
        gh_error = None

        if gh_token:
            try:
                # Step 1: get real username
                username = self._github_get_username(gh_token)
                repo_full = f"{username}/{name}"
                repo_url  = f"https://github.com/{repo_full}"
                print(f"  [GitHub] username={username} repo={name} repo_full={repo_full}")

                # Step 2: create repo (or confirm exists)
                repo_info = self._github_create_repo(gh_token, name, private=False)
                print(f"  [GitHub] repo created/found: {repo_info.get('html_url','?')}")

                # Step 3: wait for GitHub to provision
                import time; time.sleep(2)

                # Step 4: push all files
                # Regular files → Contents API
                # .github/workflows/ → Git Tree API (Contents API blocks this path)
                import time as _time
                regular = [f for f in files if f["type"] == "file" 
                           and f.get("content","").strip() 
                           and ".github" not in f["path"]]
                workflow = [f for f in files if f["type"] == "file" 
                            and f.get("content","").strip() 
                            and ".github" in f["path"]]
                print(f"  [GitHub] pushing {len(regular)} files + {len(workflow)} workflow files...")
                for f in regular:
                    try:
                        self._github_push_file(gh_token, repo_full, f["path"], f["content"])
                        pushed += 1
                        print(f"  [GitHub] pushed: {f['path']}")
                    except RuntimeError as fe:
                        print(f"  [GitHub] FAILED {f['path']}: {fe}")
                        if gh_error is None:
                            gh_error = str(fe)
                # Push .github/workflows/ — try Contents API first (works for new files),
                # fall back to Tree API if blocked
                for f in workflow:
                    try:
                        _time.sleep(1)  # let GitHub settle after regular file pushes
                        self._github_push_file(gh_token, repo_full, f["path"], f["content"])
                        pushed += 1
                        print(f"  [GitHub] pushed workflow: {f['path']}")
                    except Exception as fe1:
                        print(f"  [GitHub] Contents API failed for {f['path']}: {fe1}, trying Tree API...")
                        try:
                            _time.sleep(1)
                            self._github_push_via_tree(gh_token, repo_full, f["path"], f["content"])
                            pushed += 1
                            print(f"  [GitHub] pushed via tree: {f['path']}")
                        except Exception as fe2:
                            print(f"  [GitHub] BOTH METHODS FAILED {f['path']}: {fe2}")
                            # Store ci.yml content in gh_error so UI can show copy-paste instructions
                            gh_error = f"__CIYML_MANUAL__:{f['content']}"
            except RuntimeError as e:
                gh_error = str(e)
                print(f"  [GitHub] FATAL: {e}")

        scaffold = {
            "files":       files,
            "repo_url":    repo_url,
            "pushed":      pushed,
            "github_error": gh_error,
            "model":       result["model"],
            "provider":    result["provider"],
            "latency_ms":  result["latency_ms"],
        }

        return {"scaffold": scaffold, "_tokens": result["tokens_used"]}

    def _github_push_via_tree(self, token: str, repo_full: str, path: str, content: str):
        """Push a file using Git Data API — works for .github/workflows/ (blocked by Contents API)."""
        headers = {"Authorization": f"token {token}",
                   "Accept": "application/vnd.github.v3+json",
                   "Content-Type": "application/json"}

        def api(endpoint, data=None, method="POST", full_url=None):
            url = full_url or f"https://api.github.com/repos/{repo_full}/git/{endpoint}"
            body = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, data=body, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())

        # 1. Create blob
        blob = api("blobs", {"content": content, "encoding": "utf-8"})

        # 2. Get latest commit SHA — retry up to 5x (repo may need a moment after file pushes)
        import time as _t
        latest_sha = None
        base_tree  = None
        for attempt in range(5):
            for branch_try in ("main", "master"):
                try:
                    # Use /branches endpoint — more reliable than /git/refs/heads/
                    branch_url = f"https://api.github.com/repos/{repo_full}/branches/{branch_try}"
                    bdata = api("", method="GET", full_url=branch_url)
                    latest_sha = bdata["commit"]["sha"]
                    base_tree  = bdata["commit"]["commit"]["tree"]["sha"]
                    break
                except Exception:
                    continue
            if latest_sha:
                break
            _t.sleep(1.5)

        if not latest_sha:
            raise RuntimeError("Could not resolve branch SHA after 5 attempts — check repo exists")

        # 3. Create tree with the new file
        tree = api("trees", {"base_tree": base_tree, "tree": [
            {"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}
        ]})

        # 4. Create commit
        new_commit = api("commits", {
            "message": f"ci: add {path}",
            "tree": tree["sha"],
            "parents": [latest_sha]
        })

        # 5. Update HEAD ref via PATCH (force=True handles diverged refs)
        for branch_try in ("main", "master"):
            try:
                patch_url = f"https://api.github.com/repos/{repo_full}/git/refs/heads/{branch_try}"
                api("", {"sha": new_commit["sha"], "force": True}, method="PATCH", full_url=patch_url)
                break
            except Exception:
                continue

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
            # 422 = repo already exists — fetch existing repo info instead
            if e.code == 422:
                return self._github_get_repo(token, name)
            raise RuntimeError(f"GitHub create repo failed: {e.code} — {body[:200]}")

    def _github_get_repo(self, token: str, name: str) -> dict:
        """Get existing repo info when creation fails due to existing repo."""
        # First get username
        req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}",
                     "Accept": "application/vnd.github.v3+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                user = json.loads(r.read())
                username = user.get("login", "user")
            # Now get repo
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

        # Try creating the file first (no SHA needed for new files)
        payload = {"message": f"feat: add {path}", "content": encoded}
        data    = json.dumps(payload).encode()
        req     = urllib.request.Request(url, data=data, method="PUT", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 422:
                # File already exists — fetch SHA and update
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