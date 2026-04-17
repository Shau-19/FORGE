"""
api/cicd.py — POST /api/cicd/watch  POST /api/cicd/autofix
"""
import os, sys, json, urllib.request, urllib.error, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import llm, prompts


def _gh_get(token: str, path: str) -> dict:
    url = f'https://api.github.com{path}'
    req = urllib.request.Request(url, headers={
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'GitHub API {e.code}: {e.read().decode()[:200]}')


def _resolve_repo(token: str, repo_url: str) -> str:
    repo_url = repo_url.strip().rstrip('/')
    for prefix in ['https://github.com/', 'http://github.com/', 'github.com/']:
        if repo_url.startswith(prefix):
            repo_url = repo_url[len(prefix):]
    return repo_url


def handle_cicd_watch(body: dict) -> dict:
    repo_url = body.get('repo_url', '').strip()
    branch   = body.get('branch', 'main').strip()
    gh_token = body.get('github_token', '').strip()

    if not gh_token or not repo_url:
        return _simulate_run(branch)

    repo = _resolve_repo(gh_token, repo_url)

    try:
        runs_data = _gh_get(gh_token, f'/repos/{repo}/actions/runs?branch={branch}&per_page=5')
        runs = runs_data.get('workflow_runs', [])
        if not runs:
            return {'is_simulated': False, 'error': 'No workflow runs found. Push a commit to trigger CI.', 'steps': [], 'jobs': []}

        run    = runs[0]
        run_id = run['id']

        jobs_data = _gh_get(gh_token, f'/repos/{repo}/actions/runs/{run_id}/jobs')
        jobs = jobs_data.get('jobs', [])

        # Fetch real failure logs via logs API (requires actions:read scope)
        failure_log = ''
        for job in jobs:
            if job.get('conclusion') == 'failure':
                try:
                    log_req = urllib.request.Request(
                        f'https://api.github.com/repos/{repo}/actions/jobs/{job["id"]}/logs',
                        headers={'Authorization': f'token {gh_token}', 'Accept': 'application/vnd.github+json'})
                    with urllib.request.urlopen(log_req, timeout=15) as r:
                        raw = r.read().decode('utf-8', errors='replace')
                    failure_log += f"=== {job['name']} ===\n" + (raw[-3000:] if len(raw) > 3000 else raw) + "\n"
                    print(f'  [CICD] log fetched: {len(raw)} chars')
                except Exception as e:
                    print(f'  [CICD] log fetch failed: {e} — falling back to file scan')
                    # Fallback: detect repo type, then run appropriate checks
                    try:
                        import base64 as _b64f, subprocess, tempfile, os as _osf, shutil as _shutil
                        tree = _gh_get(gh_token, f'/repos/{repo}/git/trees/{branch}?recursive=1')
                        all_files = tree.get('tree', [])
                        py_files = [t['path'] for t in all_files if t['type']=='blob' and t['path'].endswith('.py')]
                        js_files = [t['path'] for t in all_files if t['type']=='blob'
                                    and t['path'].endswith(('.js','.ts','.jsx','.tsx','.mjs'))
                                    and 'node_modules' not in t['path']]
                        is_js_repo = len(js_files) > len(py_files)
                        print(f'  [CICD] fallback: {"JS/TS" if is_js_repo else "Python"} repo ({len(js_files)} js, {len(py_files)} py)')
                        with tempfile.TemporaryDirectory() as tmpdir:
                            if is_js_repo:
                                # Download JS files and check syntax
                                for fpath in js_files[:20]:
                                    try:
                                        fd = _gh_get(gh_token, f'/repos/{repo}/contents/{fpath}?ref={branch}')
                                        code = _b64f.b64decode(fd['content'].replace('\n','')).decode('utf-8',errors='replace')
                                        dest = _osf.path.join(tmpdir, fpath)
                                        _osf.makedirs(_osf.path.dirname(dest), exist_ok=True)
                                        open(dest,'w').write(code)
                                    except Exception: continue
                                # Also fetch package.json for context
                                for pkg_candidate in ['package.json', 'frontend/package.json']:
                                    try:
                                        pkg = _gh_get(gh_token, f'/repos/{repo}/contents/{pkg_candidate}?ref={branch}')
                                        pkg_content = _b64f.b64decode(pkg['content'].replace('\n','')).decode('utf-8',errors='replace')
                                        dest = _osf.path.join(tmpdir, pkg_candidate)
                                        _osf.makedirs(_osf.path.dirname(dest), exist_ok=True)
                                        open(dest,'w').write(pkg_content)
                                    except Exception: pass
                                # Check syntax with node if available
                                node_cmd = _shutil.which('node') or _shutil.which('node.exe')
                                syntax_errors = []
                                if node_cmd:
                                    for fpath in js_files[:20]:
                                        dest = _osf.path.join(tmpdir, fpath)
                                        if not _osf.path.exists(dest): continue
                                        try:
                                            r = subprocess.run([node_cmd,'--check',dest],
                                                capture_output=True, text=True, timeout=10)
                                            if r.returncode != 0:
                                                err = (r.stderr or r.stdout).strip()
                                                syntax_errors.append(f"{fpath}: {err[:200]}")
                                        except Exception: continue
                                if syntax_errors:
                                    failure_log += "=== JS Syntax Errors ===\n" + "\n".join(syntax_errors) + "\n"
                                else:
                                    # No syntax errors — likely an npm install failure
                                    # Include package.json contents so LLM can diagnose bad versions
                                    pkg_log = ""
                                    for pkg_candidate in ['package.json', 'frontend/package.json']:
                                        pkg_dest = _osf.path.join(tmpdir, pkg_candidate)
                                        if _osf.path.exists(pkg_dest):
                                            try:
                                                pkg_content = open(pkg_dest).read()
                                                pkg_log += f"\n=== {pkg_candidate} ===\n{pkg_content[:1000]}\n"
                                            except Exception: pass
                                    failure_log += f"Job '{job['name']}' failed at: Install dependencies\n"
                                    failure_log += "npm install failed — possible bad package version or missing package\n"
                                    if pkg_log:
                                        failure_log += pkg_log
                                if not failure_log.strip():
                                    failure_log += f"Job '{job['name']}' failed (no errors captured)\n"
                            else:
                                # Python fallback
                                for fpath in py_files:
                                    try:
                                        fd = _gh_get(gh_token, f'/repos/{repo}/contents/{fpath}?ref={branch}')
                                        code = _b64f.b64decode(fd['content'].replace('\n','')).decode('utf-8',errors='replace')
                                        dest = _osf.path.join(tmpdir, fpath)
                                        _osf.makedirs(_osf.path.dirname(dest), exist_ok=True)
                                        open(dest,'w').write(code)
                                    except Exception: continue
                                proc = subprocess.run(['ruff','check','.'], cwd=tmpdir,
                                                      capture_output=True, text=True, timeout=30)
                                ruff_out = (proc.stdout + proc.stderr).strip()
                                if ruff_out and ruff_out != 'All checks passed!':
                                    failure_log += ruff_out + "\n"
                                    print(f'  [CICD] ruff fallback: {len(ruff_out)} chars')
                                try:
                                    pytest_proc = subprocess.run(
                                        [sys.executable, '-m', 'pytest', '--tb=short', '-q'],
                                        cwd=tmpdir, capture_output=True, text=True, timeout=60,
                                        env={**_osf.environ, 'PYTHONPATH': tmpdir}
                                    )
                                    pytest_out = (pytest_proc.stdout + pytest_proc.stderr).strip()
                                    if pytest_proc.returncode != 0 and pytest_out:
                                        failure_log += "=== pytest output ===\n" + pytest_out[-2000:] + "\n"
                                        print(f'  [CICD] pytest fallback: {len(pytest_out)} chars')
                                except Exception as pe:
                                    print(f'  [CICD] pytest fallback failed: {pe}')
                                if not failure_log.strip():
                                    failure_log += f"Job '{job['name']}' failed (no errors captured)\n"
                    except FileNotFoundError:
                        failed_steps = [s['name'] for s in job.get('steps',[]) if s.get('conclusion')=='failure']
                        failure_log += f"Job '{job['name']}' failed at: {', '.join(failed_steps)}\n"
                        print('  [CICD] ruff not installed — pip install ruff')
                    except Exception as e2:
                        failed_steps = [s['name'] for s in job.get('steps',[]) if s.get('conclusion')=='failure']
                        failure_log += f"Job '{job['name']}' failed at: {', '.join(failed_steps)}\n"
                        print(f'  [CICD] fallback failed: {e2}')

        steps = []
        for job in jobs:
            for step in job.get('steps', []):
                steps.append({
                    'job':          job['name'],
                    'name':         step['name'],
                    'status':       step['status'],
                    'conclusion':   step.get('conclusion'),
                    'started_at':   step.get('started_at'),
                    'completed_at': step.get('completed_at'),
                })

        def job_conclusion(frag):
            for j in jobs:
                if frag.lower() in j['name'].lower():
                    return j.get('conclusion') or j.get('status', 'queued')
            return 'queued'

        return {
            'is_simulated': False,
            'run_id':       run_id,
            'run_url':      run['html_url'],
            'run_number':   run['run_number'],
            'status':       run['status'],
            'conclusion':   run.get('conclusion'),
            'branch':       run['head_branch'],
            'commit_msg':   run['head_commit']['message'][:80] if run.get('head_commit') else '',
            'created_at':   run['created_at'],
            'updated_at':   run['updated_at'],
            'jobs':         [{'name': j['name'], 'status': j['status'], 'conclusion': j.get('conclusion')} for j in jobs],
            'steps':        steps,
            'stage_build':  job_conclusion('build'),
            'stage_test':   job_conclusion('test'),
            'stage_lint':   job_conclusion('lint'),
            'stage_deploy': job_conclusion('deploy'),
            'failure_log':  failure_log,
        }

    except RuntimeError as e:
        return {'is_simulated': False, 'error': str(e), 'steps': [], 'jobs': []}


def handle_cicd_autofix(body: dict) -> dict:
    failure_log   = body.get('failure_log', '')
    repo_url      = body.get('repo_url', '')
    branch        = body.get('branch', 'main')
    gh_token      = body.get('github_token', '')
    stack         = body.get('stack', [])
    apply_patches = body.get('apply_patches', False)

    if not failure_log:
        raise ValueError('failure_log required')

    # If patches already supplied (Apply button) — skip LLM re-generation
    prefilled = body.get('patches', None)
    if prefilled is not None:
        patches = prefilled
        parsed  = {'summary': 'Applying pre-generated patches', 'root_cause': '', 'commands': []}
        result  = {'tokens_used': 0, 'model': 'cached', 'provider': 'cached', 'latency_ms': 0}
    else:
        system, user = prompts.analyze_cicd_failure(failure_log, stack)
        result = llm.call(prompt=user, system=system, max_tokens=1200)
        text = result['text'].strip()
        if text.startswith('```'):
            lines = text.split('\n')
            text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {'summary': text, 'patches': [], 'commands': []}
        patches = parsed.get('patches', [])

    apply_results = []
    print(f'  [AUTOFIX] apply={apply_patches} patches={len(patches)} token={bool(gh_token)} repo={bool(repo_url)}')

    if apply_patches and gh_token and repo_url:
        try:
            import base64 as _b64
            repo = _resolve_repo(gh_token, repo_url)

            for patch in patches:
                filepath = patch.get('file', '')
                old_line = patch.get('old_line', '')
                new_line = patch.get('new_line', '')

                if not filepath or not old_line:
                    apply_results.append({'file': filepath, 'status': 'skipped', 'reason': 'missing fields'})
                    continue

                try:
                    # 1. Fetch file — exact path first, then fuzzy search
                    resolved_path = filepath
                    fdata = None
                    try:
                        fdata = _gh_get(gh_token, f'/repos/{repo}/contents/{filepath}?ref={branch}')
                    except Exception:
                        fname = filepath.split('/')[-1]
                        try:
                            tree = _gh_get(gh_token, f'/repos/{repo}/git/trees/{branch}?recursive=1')
                            matches = [t['path'] for t in tree.get('tree', [])
                                       if t['path'].endswith(fname) and t['type'] == 'blob']
                            if matches:
                                resolved_path = matches[0]
                                fdata = _gh_get(gh_token, f'/repos/{repo}/contents/{resolved_path}?ref={branch}')
                        except Exception:
                            pass

                    if not fdata:
                        print(f'  [AUTOFIX] ✗ file not found: {filepath}')
                        apply_results.append({'file': filepath, 'status': 'not_found',
                                              'reason': f'File not found (tried fuzzy for {filepath.split("/")[-1]})'})
                        continue

                    current    = _b64.b64decode(fdata['content'].replace('\n', '')).decode('utf-8')
                    file_lines = current.split('\n')

                    # 2. Fuzzy line match — search specified file first
                    matched_idx = None
                    for i, line in enumerate(file_lines):
                        if old_line.strip() and (old_line.strip() in line or line.strip() == old_line.strip()):
                            matched_idx = i
                            break

                    # 3. If not found — scan all .py files in repo
                    if matched_idx is None:
                        print(f'  [AUTOFIX] line not in {resolved_path}, scanning repo...')
                        found_elsewhere = False
                        try:
                            tree = _gh_get(gh_token, f'/repos/{repo}/git/trees/{branch}?recursive=1')
                            for item in tree.get('tree', []):
                                if item['type'] != 'blob' or not item['path'].endswith('.py'):
                                    continue
                                if item['path'] == resolved_path:
                                    continue  # already checked
                                try:
                                    d = _gh_get(gh_token, f'/repos/{repo}/contents/{item["path"]}?ref={branch}')
                                    txt = _b64.b64decode(d['content'].replace('\n', '')).decode('utf-8', errors='replace')
                                    alt_lines = txt.split('\n')
                                    for j, ln in enumerate(alt_lines):
                                        if old_line.strip() and (old_line.strip() in ln or ln.strip() == old_line.strip()):
                                            alt_lines[j] = new_line if new_line else ''
                                            fixed2   = '\n'.join(alt_lines)
                                            put2     = json.dumps({
                                                'message': f'fix(autofix): {patch.get("explanation","AI patch")}',
                                                'content': _b64.b64encode(fixed2.encode()).decode(),
                                                'sha': d['sha'], 'branch': branch,
                                            }).encode()
                                            req2 = urllib.request.Request(
                                                f'https://api.github.com/repos/{repo}/contents/{item["path"]}',
                                                data=put2, method='PUT',
                                                headers={'Authorization': f'token {gh_token}',
                                                         'Content-Type': 'application/json',
                                                         'Accept': 'application/vnd.github+json'})
                                            with urllib.request.urlopen(req2, timeout=15): pass
                                            print(f'  [AUTOFIX] ✓ found+applied in {item["path"]}')
                                            apply_results.append({'file': item['path'], 'status': 'applied',
                                                                   'reason': f'committed ({item["path"]}) — new CI run triggered'})
                                            found_elsewhere = True
                                            break
                                except Exception:
                                    continue
                                if found_elsewhere:
                                    break
                        except Exception as scan_err:
                            print(f'  [AUTOFIX] scan error: {scan_err}')
                        if not found_elsewhere:
                            print(f'  [AUTOFIX] ✗ not found anywhere: {repr(old_line)}')
                            apply_results.append({'file': resolved_path, 'status': 'not_found',
                                                  'reason': f'"{old_line}" not found in any .py file'})
                        continue

                    # 4. Apply and push — handle multi-line new_line
                    if new_line and '\n' in new_line:
                        parts = new_line.split('\n')
                        file_lines[matched_idx:matched_idx+1] = parts
                    else:
                        file_lines[matched_idx] = new_line if new_line else ''
                    fixed    = '\n'.join(file_lines)
                    put_data = json.dumps({
                        'message': f'fix(autofix): {patch.get("explanation", "AI patch")}',
                        'content': _b64.b64encode(fixed.encode()).decode(),
                        'sha':     fdata['sha'],
                        'branch':  branch,
                    }).encode()
                    req = urllib.request.Request(
                        f'https://api.github.com/repos/{repo}/contents/{resolved_path}',
                        data=put_data, method='PUT',
                        headers={'Authorization': f'token {gh_token}',
                                 'Content-Type': 'application/json',
                                 'Accept': 'application/vnd.github+json'})
                    with urllib.request.urlopen(req, timeout=15): pass
                    print(f'  [AUTOFIX] ✓ applied: {resolved_path}')
                    apply_results.append({'file': resolved_path, 'status': 'applied',
                                          'reason': f'committed ({resolved_path}) — new CI run triggered'})

                except Exception as e:
                    print(f'  [AUTOFIX] ✗ error {filepath}: {e}')
                    apply_results.append({'file': filepath, 'status': 'error', 'reason': str(e)})

        except Exception as e:
            apply_results.append({'file': '?', 'status': 'error', 'reason': str(e)})

    return {
        'summary':         parsed.get('summary', ''),
        'root_cause':      parsed.get('root_cause', ''),
        'patches':         patches,
        'commands':        parsed.get('commands', []),
        'apply_results':   apply_results,
        'patches_applied': len([r for r in apply_results if r['status'] == 'applied']),
        'tokens_used':     result['tokens_used'],
        'model':           result['model'],
        'provider':        result['provider'],
        'latency_ms':      result['latency_ms'],
    }


def _simulate_run(branch: str) -> dict:
    return {
        'is_simulated': True,
        'run_number':   42,
        'run_url':      '',
        'status':       'completed',
        'conclusion':   'failure',
        'branch':       branch,
        'commit_msg':   'feat: add user authentication flow',
        'created_at':   '2025-01-01T00:00:00Z',
        'stage_build':  'success',
        'stage_test':   'success',
        'stage_lint':   'failure',
        'stage_deploy': 'skipped',
        'jobs': [
            {'name': 'Build',  'status': 'completed', 'conclusion': 'success'},
            {'name': 'Test',   'status': 'completed', 'conclusion': 'success'},
            {'name': 'Lint',   'status': 'completed', 'conclusion': 'failure'},
            {'name': 'Deploy', 'status': 'completed', 'conclusion': 'skipped'},
        ],
        'steps': [
            {'job': 'Build', 'name': 'Checkout code', 'status': 'completed', 'conclusion': 'success'},
            {'job': 'Build', 'name': 'Set up Python', 'status': 'completed', 'conclusion': 'success'},
            {'job': 'Build', 'name': 'Install deps',  'status': 'completed', 'conclusion': 'success'},
            {'job': 'Test',  'name': 'Run pytest',    'status': 'completed', 'conclusion': 'success'},
            {'job': 'Lint',  'name': 'Run ruff',      'status': 'completed', 'conclusion': 'failure'},
            {'job': 'Deploy','name': 'Deploy',         'status': 'completed', 'conclusion': 'skipped'},
        ],
        'failure_log': 'ruff check .\nbackend/main.py:14:1: F401 `os` imported but unused\nFound 1 error.',
    }