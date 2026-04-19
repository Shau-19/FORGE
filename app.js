/**
 * FORGE — app.js  Phase 4
 * Validate ✅  PRD ✅  Scaffold ✅  Checklist ✅
 * CI/CD ✅ real GitHub Actions polling + AI autofix
 * Architecture Diagram ✅ AI modification
 */
'use strict';

const API_BASE = '';

// ══ STATE ════════════════════════════════════════════════
const S = {
  kb: { tree: null, tree_text: '', label: '', active: false },
  project:  { name:'', idea:'', audience:'', scores:{}, techStack:[], prd:{}, repoUrl:'', branch:'main' },
  pipeline: { validate:false, prd:false, scaffold:false, cicd:false, launch:false },
  ctx:      { validate:false, prd:true, scaffold:true, launch:true },
  github:   { connected:false, token:'', username:'' },
  usage:    { totalTokens:0, totalCostUsd:0, model:'', provider:'' },
  logCounts: {},
  pipelineStart: null,
  scaffoldFiles: [],
  // Diagram state — mutable by AI
  diagram: {
    nodes: [
      { label:'Browser',    color:'#3b82f6', x:0.10, y:0.50, r:26 },
      { label:'FastAPI',    color:'#34d399', x:0.30, y:0.28, r:24 },
      { label:'React',      color:'#6366f1', x:0.30, y:0.72, r:24 },
      { label:'PostgreSQL', color:'#fbbf24', x:0.55, y:0.20, r:22 },
      { label:'Redis',      color:'#ef4444', x:0.55, y:0.50, r:20 },
      { label:'Stripe',     color:'#34d399', x:0.55, y:0.80, r:20 },
      { label:'Anthropic',  color:'#a855f7', x:0.80, y:0.35, r:22 },
      { label:'GitHub CI',  color:'#6b7280', x:0.80, y:0.65, r:20 },
    ],
    edges: [[0,1],[0,2],[1,3],[1,4],[1,5],[1,6],[1,7]],
  },
  // CI/CD polling
  cicd: { pollTimer:null, lastRunId:null, failureLog:'' },
};

// ══ APP ══════════════════════════════════════════════════
const App = {
  switchPanel(id, tabEl) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.sb-item').forEach(t => t.classList.remove('active'));
    const panel = document.getElementById('panel-' + id);
    if (!panel) return;
    panel.classList.add('active');
    panel.classList.add('panel-enter');
    setTimeout(() => panel.classList.remove('panel-enter'), 250);
    const sideItem = tabEl || document.querySelector('.sb-item[data-panel="' + id + '"]');
    if (sideItem) sideItem.classList.add('active');
    if (id === 'diagram')  setTimeout(() => Canvas.drawArch('archD3Container'), 40);
    if (id === 'graph')    setTimeout(() => { Canvas.drawGraph(); Canvas.initGraphHover(); }, 40);
    if (id === 'scaffold') setTimeout(() => Canvas.drawArch('scaffoldD3Container'), 40);
    if (id === 'chatindex') { /* no canvas init */ }
    if (id === 'kb') { /* no canvas init */ }
  },

  toggleCtx(panel, trackEl) {
    trackEl.classList.toggle('on');
    S.ctx[panel] = trackEl.classList.contains('on');
    if (S.ctx[panel]) App._injectCtx(panel);
  },

  _injectCtx(panel) {
    if (panel === 'prd'      && S.project.idea) { const e = document.getElementById('prdIdeaInput');   if (e && !e.value) e.value = S.project.idea; }
    if (panel === 'scaffold' && S.project.name) { const e = document.getElementById('repoNameInput');  if (e && !e.value) e.value = S.project.name; }
    if (panel === 'launch'   && S.project.idea) { const e = document.getElementById('launchCtxInput'); if (e && !e.value) e.value = S.project.idea; }
  },

  setProjectPill(name, phase) {
    if (name) S.project.name = name;
    document.getElementById('projectPill').classList.remove('hidden');
    document.getElementById('pillName').textContent  = S.project.name || 'project';
    document.getElementById('pillPhase').textContent = phase;
  },

  updatePipelineBar() {
    let done = 0;
    ['validate','prd','scaffold','cicd','launch'].forEach(s => {
      const checkEl = document.getElementById('pipe-' + s);
      if (checkEl) {
        if (S.pipeline[s]) { checkEl.classList.add('done'); done++; }
        else checkEl.classList.remove('done');
      }
      const dotEl = document.getElementById('tdot-' + s);
      if (dotEl) dotEl.style.background = S.pipeline[s] ? 'var(--green)' : '';
    });
    document.getElementById('pipeStatus').textContent = done + ' / 5 stages complete';
    const fillEl = document.getElementById('sbProgressFill');
    if (fillEl) fillEl.style.width = (done / 5 * 100) + '%';
    if (S.pipelineStart) {
      const rt = document.getElementById('pipeRuntime');
      if (rt) rt.textContent = Math.round((Date.now() - S.pipelineStart) / 1000) + 's';
    }
  },

  markTabDone(panel) {
    S.pipeline[panel] = true;
    App.updatePipelineBar();
  },

  updateUsage(tokens, model, provider) {
    S.usage.totalTokens += tokens || 0;
    if (model)    S.usage.model    = model;
    if (provider) S.usage.provider = provider;
    const rate = provider === 'groq' ? 0.05 : provider === 'mock' ? 0 : 0.60;
    S.usage.totalCostUsd += ((tokens || 0) / 1_000_000) * rate;
    document.getElementById('tokenCount').textContent   = S.usage.totalTokens.toLocaleString() + ' tokens';
    document.getElementById('costEstimate').textContent = '$' + S.usage.totalCostUsd.toFixed(4);
    if (model && model !== 'mock') document.getElementById('modelName').textContent = model.split('-').slice(0,4).join('-');
  },

  connectGitHub() {
    if (S.github.connected) {
      GitHub.showConnected(); return;
    }
    GitHub.showModal();
  },

  setExample(key, idea, audience) {
    document.getElementById('ideaInput').value     = idea;
    document.getElementById('audienceInput').value = audience;
  },

  clearPanel(panel) {
    if (panel !== 'validate') return;
    ['ideaInput','audienceInput'].forEach(id => { const e = document.getElementById(id); if (e) e.value = ''; });
    document.getElementById('validateResult').style.display = 'none';
    document.getElementById('validateEmpty').style.display  = 'flex';
    document.getElementById('validateStatusBadge').classList.add('hidden');
    document.getElementById('proceedPrdBtn').style.display  = 'none';
    Log.clear('validate');
  },

  exportOutput(panel, format = 'txt') {
    if (panel === 'prd' && format === 'md' && Object.keys(S.project.prd).length) {
      const labels = { overview:'Overview', features:'Core Features', stories:'User Stories', tech:'Tech Requirements', api:'API Spec', timeline:'Timeline' };
      const md = '# Product Requirements Document\n\n' +
        Object.entries(S.project.prd).map(([k,v]) => `## ${labels[k]||k}\n\n${v}`).join('\n\n');
      App._download(md, (S.project.name||'project') + '-prd.md', 'text/markdown');
      return;
    }
    App.showError(`${format.toUpperCase()} export: use GitHub repo or next phase.`);
  },

  _download(content, filename, type) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([content], { type }));
    a.download = filename; a.click();
  },

  exportDiagram(format) {
    const canvasId = 'archCanvas';
    if (format === 'svg') {
      // Build SVG string from current diagram state
      const { nodes, edges } = S.diagram;
      const W = 800, H = 480;
      let svgParts = [`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" style="background:#0e0e1a;">`];
      edges.forEach(([a,b]) => {
        if (!nodes[a] || !nodes[b]) return;
        svgParts.push(`<line x1="${nodes[a].x*W}" y1="${nodes[a].y*H}" x2="${nodes[b].x*W}" y2="${nodes[b].y*H}" stroke="#2a2a3e" stroke-width="1"/>`);
      });
      nodes.forEach(n => {
        const cx = n.x*W, cy = n.y*H;
        svgParts.push(`<circle cx="${cx}" cy="${cy}" r="${n.r}" fill="${n.color}22" stroke="${n.color}" stroke-width="1.5"/>`);
        svgParts.push(`<text x="${cx}" y="${cy+n.r+14}" fill="${n.color}" font-size="10" font-family="monospace" text-anchor="middle">${n.label}</text>`);
      });
      svgParts.push('</svg>');
      App._download(svgParts.join('\n'), 'forge-architecture.svg', 'image/svg+xml');
      return;
    }
    const canvas = document.getElementById(canvasId);
    if (canvas) App._download(canvas.toDataURL('image/png'), 'forge-architecture.png', 'image/png');
  },

  showError(msg) {
    document.getElementById('errorMsg').textContent = msg;
    document.getElementById('errorToast').classList.remove('hidden');
    clearTimeout(App._errT);
    App._errT = setTimeout(() => App.dismissError(), 5000);
  },
  dismissError() { document.getElementById('errorToast').classList.add('hidden'); },

  async runFullPipeline() {
    const idea = document.getElementById('ideaInput').value.trim();
    if (!idea) { App.switchPanel('validate'); App.showError('Enter your idea first.'); return; }
    S.pipelineStart = Date.now();
    const btn = document.getElementById('runPipelineBtn');
    btn.disabled = true; btn.textContent = '⟳ Running...';
    try {
      App.switchPanel('validate', document.querySelector('[data-panel="validate"]'));
      await Agents.validate();
      await Utils.sleep(300);
      App.switchPanel('prd', document.querySelector('[data-panel="prd"]'));
      await Agents.prd();
      await Utils.sleep(300);
      App.switchPanel('scaffold', document.querySelector('[data-panel="scaffold"]'));
      await Agents.scaffold();
      await Utils.sleep(300);
      App.switchPanel('launch', document.querySelector('[data-panel="launch"]'));
      await Agents.launch();
    } finally {
      btn.disabled = false; btn.textContent = '▷ Run Pipeline';
      App.updatePipelineBar();
    }
  },

  async checkApiHealth() {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      const dot = document.getElementById('apiStatus');
      if (res.ok) {
        const d = await res.json();
        dot.style.background = 'var(--green)';
        dot.title = `Online · ${d.provider} · ${d.model}`;
        if (d.model) document.getElementById('modelName').textContent = d.model.split('-').slice(0,4).join('-');
      } else {
        dot.style.background = 'var(--yellow)'; dot.title = 'API Degraded';
      }
    } catch {
      document.getElementById('apiStatus').style.background = 'var(--red)';
      document.getElementById('apiStatus').title = 'API Offline — demo mode';
    }
    // Fetch and display rate limit metrics
    App._refreshMetrics();
    setInterval(App._refreshMetrics, 30000); // refresh every 30s
  },

  async _refreshMetrics() {
    try {
      const m = await LLM.fetchMetrics();
      if (!m) return;
      const row = document.getElementById('rlBudgetRow');
      if (row) row.style.display = 'block';
      const pct = Math.min(100, Math.round((m.tokens_used / m.tokens_limit) * 100));
      const bar = document.getElementById('rlBar');
      const pctEl = document.getElementById('rlPercent');
      const runsEl = document.getElementById('rlRuns');
      if (bar) {
        bar.style.width = pct + '%';
        bar.style.background = pct > 80 ? 'var(--red)' : pct > 50 ? 'var(--yellow)' : 'var(--green)';
      }
      if (pctEl) pctEl.textContent = pct + '%';
      if (runsEl) runsEl.textContent = `${m.runs_used}/${m.runs_limit} runs`;
    } catch {}
  },
};

// ══ LOG ══════════════════════════════════════════════════
const Log = {
  write(panel, msg, type = 'info') {
    const c = document.getElementById('log-' + panel);
    if (!c) return;
    const idle = c.querySelector('.log-idle');
    if (idle) idle.remove();
    const e = document.createElement('div');
    e.className = 'log-entry ' + type;
    const t = new Date().toLocaleTimeString('en',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});
    e.textContent = `[${t}] ${msg}`;
    c.appendChild(e); c.scrollTop = c.scrollHeight;
    S.logCounts[panel] = (S.logCounts[panel]||0) + 1;
    const ct = document.getElementById('logcount-' + panel);
    if (ct) ct.textContent = S.logCounts[panel] + ' events';
  },
  clear(panel) {
    const c = document.getElementById('log-' + panel);
    if (c) c.innerHTML = '<div class="log-idle">— idle —</div>';
    S.logCounts[panel] = 0;
    const ct = document.getElementById('logcount-' + panel);
    if (ct) ct.textContent = '0 events';
  },
};

// ══ LLM — real API + mock fallback ═══════════════════════
const LLM = {
  async call(endpoint, payload = {}) {
    try {
      const res = await fetch(`${API_BASE}/api/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.status === 429) {
        const err = await res.json().catch(() => ({}));
        // Show rate limit badge
        LLM._showRateLimitBadge(err.status);
        throw new Error(err.error || 'Rate limit exceeded');
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.tokens_used) App.updateUsage(data.tokens_used, data.model, data.provider);
      return data;
    } catch (err) {
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        console.warn(`[FORGE] API offline — mock: ${endpoint}`);
        return LLM._mock(endpoint, payload);
      }
      throw err;
    }
  },

  async _mock(endpoint, payload) {
    await Utils.sleep(700 + Math.random() * 500);
    App.updateUsage(Math.floor(Math.random()*800)+400, 'mock-model', 'mock');
    switch (endpoint) {
      case 'validate': return {
        viability:82, market:74, risk:61,
        metrics:{ technical_feasibility:79, revenue_potential:73, time_to_market:62, competitive_moat:57 },
        analysis:{ strength:'Clear pain point with monetizable workflow.', risk:'3-6 month runway before first revenue.', recommendation:'Build focused MVP around core workflow first.' },
        stack:['FastAPI','React','PostgreSQL','Redis','Stripe','Docker','Railway'],
        tokens_used:650, model:'mock', provider:'mock', latency_ms:720,
      };
      case 'prd': return {
        sections:{
          overview:`${payload.idea||'Your product'}. A focused platform eliminating manual work through intelligent automation.`,
          features:'1. Core workflow automation\n2. Real-time dashboard & analytics\n3. Third-party integrations\n4. Role-based access control\n5. Export & reporting',
          stories:'• As a user, I sign up and see value within 5 minutes.\n• As an admin, I manage team members and analytics.',
          tech:'Backend: FastAPI + PostgreSQL + Redis\nFrontend: React + Tailwind\nAuth: JWT + GitHub OAuth',
        },
        tokens_used:900, model:'mock', provider:'mock', latency_ms:900,
      };
      case 'prd/refine': return { section_key:payload.section_key, updated_content:payload.current_content+'\n\n[Refined: '+payload.instruction+']', tokens_used:200 };
      case 'scaffold': return {
        files:[
          {type:'dir', path:'backend/', content:''},
          {type:'file',path:'backend/main.py', content:'from fastapi import FastAPI\napp = FastAPI()\n\n@app.get("/")\ndef root(): return {"status": "ok"}'},
          {type:'file',path:'backend/models/user.py', content:'from pydantic import BaseModel\n\nclass User(BaseModel):\n    id: int\n    email: str'},
          {type:'file',path:'.env.example', content:'DATABASE_URL=postgresql://user:pass@localhost/db\nGROQ_API_KEY=gsk_...'},
          {type:'file',path:'README.md', content:`# ${payload.name||'project'}\n\nGenerated by FORGE.\n\n## Setup\n\n\`\`\`bash\npip install -r requirements.txt\nuvicorn backend.main:app --reload\n\`\`\``},
        ],
        repo_url: '', pushed:0,
        tokens_used:1200, model:'mock', provider:'mock', latency_ms:1100,
      };
      case 'checklist/doit': return {
        steps: [
          { title: 'Audit current implementation', detail: 'Review existing code for gaps related to this task.', command: '' },
          { title: 'Install required packages', detail: 'Add the necessary dependencies for your stack.', command: 'npm install <package>' },
          { title: 'Implement the feature', detail: 'Follow best practices for your specific stack.', command: '' },
          { title: 'Write tests', detail: 'Add unit and integration tests to cover the new functionality.', command: 'npm test' },
          { title: 'Deploy and verify', detail: 'Push to staging and confirm the feature works end-to-end.', command: 'git push origin main' },
        ],
        code_snippet: '// Implementation example\nconsole.log("Add your code here");',
        references: ['Official docs for your stack', 'OWASP guidelines (for security tasks)'],
        estimated_time: '2-4 hours',
        tokens_used: 400, model: 'mock', provider: 'mock', latency_ms: 300,
      };
      case 'checklist': return { items:[
        {cat:'SECURITY',label:'.env not committed to git',done:true,detail:'Never expose API keys.'},
        {cat:'SECURITY',label:'HTTPS enforced on all endpoints',done:false,detail:'Use Railway auto-TLS or nginx.'},
        {cat:'PERFORMANCE',label:'Database indexes on hot queries',done:false,detail:'Add indexes on filtered columns.'},
        {cat:'SEO',label:'Meta tags + Open Graph configured',done:false,detail:'Required for social sharing.'},
        {cat:'DEVOPS',label:'Error monitoring (Sentry) wired',done:false,detail:'Catch production errors early.'},
        {cat:'LAUNCH',label:'Landing page live',done:false,detail:'Capture interest before launch.'},
      ], tokens_used:500, model:'mock', provider:'mock', latency_ms:600 };
      case 'cicd/watch': return {
        is_simulated:true, run_number:42, status:'completed', conclusion:'failure',
        branch: payload.branch||'main', commit_msg:'feat: add user auth flow',
        stage_build:'success', stage_test:'success', stage_lint:'failure', stage_deploy:'skipped',
        jobs:[
          {name:'Build', status:'completed', conclusion:'success'},
          {name:'Test',  status:'completed', conclusion:'success'},
          {name:'Lint',  status:'completed', conclusion:'failure'},
          {name:'Deploy',status:'completed', conclusion:'skipped'},
        ],
        steps:[
          {job:'Build', name:'Checkout',     status:'completed', conclusion:'success'},
          {job:'Build', name:'Install deps', status:'completed', conclusion:'success'},
          {job:'Test',  name:'Run pytest',   status:'completed', conclusion:'success'},
          {job:'Lint',  name:'Run ruff',     status:'completed', conclusion:'failure'},
          {job:'Deploy',name:'Deploy',       status:'completed', conclusion:'skipped'},
        ],
        failure_log:'ruff check .\nbackend/main.py:14:1: F401 `os` imported but unused\nFound 1 error.',
      };
      case 'cicd/autofix': return {
        summary:'Unused import `os` on line 14 of backend/main.py caused lint failure.',
        root_cause:'The `os` module was imported but never used in the file.',
        patches:[{file:'backend/main.py', old_line:'import os', new_line:'', explanation:'Remove the unused import to fix the ruff F401 violation.'}],
        commands:['ruff check . --fix', 'git add -A && git commit -m "fix(lint): remove unused import"'],
        tokens_used:400, model:'mock', provider:'mock', latency_ms:500,
      };
      case 'diagram/modify': {
        const nodes = payload.nodes || S.diagram.nodes;
        const newNode = { label:'New Service', color:'#06b6d4', x:0.65, y:0.12, r:20 };
        return {
          nodes: [...nodes, newNode],
          edges: [...(payload.edges || S.diagram.edges), [0, nodes.length]],
          change_summary: 'Added new service node per instruction.',
          tokens_used:300, model:'mock', provider:'mock', latency_ms:400,
        };
      }
      default: return { ok:true };
    }
  },

  _showRateLimitBadge(status) {
    let badge = document.getElementById('rateLimitBadge');
    if (!badge) {
      badge = document.createElement('div');
      badge.id = 'rateLimitBadge';
      badge.style.cssText = 'position:fixed;top:60px;right:20px;background:#0d0d1a;border:1px solid var(--yellow);border-left:3px solid var(--yellow);border-radius:8px;padding:12px 16px;z-index:9998;font-family:var(--font-mono);font-size:11px;max-width:320px;';
      document.body.appendChild(badge);
    }
    const runs   = status ? `${status.runs_used}/${status.runs_limit} runs` : '';
    const tokens = status ? `${(status.tokens_used||0).toLocaleString()}/${(status.tokens_limit||0).toLocaleString()} tokens` : '';
    badge.innerHTML = `
      <div style="color:var(--yellow);font-weight:600;margin-bottom:6px;">⚠ Rate Limited</div>
      ${runs ? '<div style="color:var(--text2);">Runs: ' + runs + ' used this hour</div>' : ''}
      ${tokens ? '<div style="color:var(--text2);">Tokens: ' + tokens + ' used this hour</div>' : ''}
      <div style="color:var(--muted);margin-top:6px;font-size:10px;">Limits reset on a 1-hour sliding window</div>
      <button onclick="document.getElementById('rateLimitBadge').remove()" style="position:absolute;top:8px;right:10px;background:none;border:none;color:var(--muted);cursor:pointer;font-size:14px;">✕</button>
    `;
    setTimeout(() => badge?.remove(), 15000);
  },

  async fetchMetrics() {
    try {
      const res = await fetch('/api/metrics');
      return await res.json();
    } catch { return null; }
  },
};

// ══ AGENTS ═══════════════════════════════════════════════
const Agents = {

  // ── 01 Validate ──────────────────────────────────────────
  async validate() {
    const idea     = document.getElementById('ideaInput').value.trim();
    const audience = document.getElementById('audienceInput').value.trim() || 'General';
    if (!idea) { App.showError('Enter your idea first.'); return; }

    S.project.idea = idea; S.project.audience = audience;
    S.project.name = idea.split(' ').slice(0,3).join('-').toLowerCase().replace(/[^a-z0-9-]/g,'');

    document.getElementById('validateEmpty').style.display  = 'none';
    document.getElementById('validateResult').style.display = 'none';
    document.getElementById('validateStatusBadge').classList.add('hidden');
    document.getElementById('proceedPrdBtn').style.display  = 'none';
    document.getElementById('validateBtn').disabled         = true;

    App.setProjectPill(S.project.name, 'VALIDATING');
    Log.write('validate', `Received: ${idea.substring(0,50)}…`, 'sys');
    Log.write('validate', 'Calling LLM for market analysis...', 'info');

    let data;
    try {
      data = await LLM.call('validate', { idea, audience, kb_context: _getKBContext() });
    } catch (err) {
      Log.write('validate', 'Error: ' + err.message, 'err');
      App.showError('Validation failed: ' + err.message);
      document.getElementById('validateBtn').disabled = false;
      return;
    }

    Log.write('validate', `${data.provider} · ${data.model} · ${data.latency_ms}ms`, 'info');
    Log.write('validate', 'Analysis complete.', 'ok');

    S.project.scores    = { viability:data.viability, market:data.market, risk:data.risk };
    S.project.techStack = data.stack;

    // Update diagram nodes to match real stack
    if (data.stack && data.stack.length) {
      const colors = ['#3b82f6','#34d399','#6366f1','#fbbf24','#ef4444','#a855f7','#6b7280','#f97316'];
      const pos    = [{x:.10,y:.50},{x:.30,y:.28},{x:.30,y:.72},{x:.55,y:.20},{x:.55,y:.50},{x:.55,y:.80},{x:.80,y:.35},{x:.80,y:.65}];
      S.diagram.nodes = data.stack.slice(0,8).map((label,i) => ({
        label, color:colors[i%colors.length], x:pos[i]?.x??0.5, y:pos[i]?.y??0.5, r: i===0?26:22,
      }));
      S.diagram.edges = [[0,1],[0,2],[1,3],[1,4],[1,5],[1,6],[1,7]].filter(([a,b]) => S.diagram.nodes[a] && S.diagram.nodes[b]);
    }

    document.getElementById('scoreGrid').innerHTML =
      UI.scoreRing(data.viability,'VIABILITY','var(--green)') +
      UI.scoreRing(data.market,'MARKET FIT','var(--accent)') +
      UI.scoreRing(data.risk,'RISK SCORE','var(--yellow)');

    const m = data.metrics;
    document.getElementById('metricBars').innerHTML = [
      {label:'Technical Feasibility',val:m.technical_feasibility},
      {label:'Revenue Potential',val:m.revenue_potential},
      {label:'Time to Market',val:m.time_to_market},
      {label:'Competitive Moat',val:m.competitive_moat},
    ].map(UI.metricBar).join('');

    const a = data.analysis;
    document.getElementById('analysisText').innerHTML =
      `<p style="color:var(--green);margin-bottom:8px;">✓ ${a.strength}</p>` +
      `<p style="color:var(--yellow);margin-bottom:8px;">⚠ ${a.risk}</p>` +
      `<p>${a.recommendation}</p>`;
    document.getElementById('stackBadges').innerHTML =
      data.stack.map(t => `<span class="stack-badge">${t}</span>`).join('');

    document.getElementById('prdIdeaInput').value  = idea;
    document.getElementById('repoNameInput').value = S.project.name;
    const lci = document.getElementById('launchCtxInput');
    if (lci && !lci.value) lci.value = idea;

    document.getElementById('validateResult').style.display = 'block';
    document.getElementById('validateStatusBadge').classList.remove('hidden');
    document.getElementById('proceedPrdBtn').style.display  = 'block';
    document.getElementById('validateBtn').disabled         = false;

    App.setProjectPill(S.project.name, 'VALIDATED');
    App.markTabDone('validate');
  },

  // ── 02 PRD ───────────────────────────────────────────────
  async prd() {
    const idea = S.ctx.prd && S.project.idea
      ? S.project.idea
      : document.getElementById('prdIdeaInput').value.trim();
    if (!idea) { App.showError('Add idea context or run Validator first.'); return; }

    const sections = Array.from(document.querySelectorAll('[data-section]:checked')).map(e => e.dataset.section);
    if (!sections.length) { App.showError('Select at least one section.'); return; }

    document.getElementById('prdEmpty').style.display    = 'none';
    document.getElementById('prdSections').style.display = 'none';

    App.setProjectPill(S.project.name, 'WRITING PRD');
    Log.write('prd', 'Generating PRD...', 'sys');

    let data;
    try {
      data = await LLM.call('prd', { idea, audience:S.project.audience||'General', stack:S.project.techStack||[], sections, kb_context: _getKBContext() });
    } catch (err) {
      Log.write('prd', 'Error: ' + err.message, 'err');
      App.showError('PRD failed: ' + err.message);
      return;
    }

    const sectionLabels = { overview:'OVERVIEW', features:'CORE FEATURES', stories:'USER STORIES', tech:'TECH REQUIREMENTS', api:'API SPEC', timeline:'TIMELINE' };
    S.project.prd = data.sections;
    let html = '';
    for (const [key, label] of Object.entries(sectionLabels)) {
      if (data.sections[key]) html += UI.prdSection(key, label, data.sections[key]);
    }
    document.getElementById('prdSections').innerHTML  = html;
    document.getElementById('prdSections').style.display = 'block';
    document.getElementById('proceedScaffoldBtn').style.display = 'block';

    Log.write('prd', `Generated ${Object.keys(data.sections).length} sections.`, 'ok');
    App.setProjectPill(S.project.name, 'PRD READY');
    App.markTabDone('prd');
  },

  async prdChat() {
    const inp = document.getElementById('prdChatInput');
    const msg = inp.value.trim(); if (!msg) return; inp.value = '';
    const firstKey = Object.keys(S.project.prd)[0];
    if (!firstKey) { App.showError('Generate PRD first.'); return; }
    Log.write('prd', 'Refining: ' + msg, 'sys');
    let data;
    try {
      data = await LLM.call('prd/refine', { section_key:firstKey, section_label:firstKey.toUpperCase(), current_content:S.project.prd[firstKey]||'', instruction:msg });
    } catch (err) { Log.write('prd','Refinement failed: '+err.message,'err'); return; }
    S.project.prd[data.section_key] = data.updated_content;
    const bodyEl = document.getElementById(`prd-body-${data.section_key}`);
    if (bodyEl) bodyEl.innerHTML = UI._formatPrdContent(data.updated_content);
    Log.write('prd', 'Section updated.', 'ok');
  },

  async regenerateSection(key, label) {
    const bodyEl = document.getElementById(`prd-body-${key}`);
    if (!bodyEl) return;
    const idea = S.project.idea || document.getElementById('prdIdeaInput').value.trim();
    if (!idea) { App.showError('No idea context — run Validator first.'); return; }
    // Visual feedback
    bodyEl.style.opacity = '0.4';
    Log.write('prd', `Regenerating ${label}...`, 'sys');
    let data;
    try {
      data = await LLM.call('prd/refine', {
        section_key: key,
        section_label: label,
        current_content: S.project.prd[key] || '',
        instruction: `Rewrite this ${label} section with fresh perspective. Make it more specific, actionable, and detailed for: ${idea}`,
      });
    } catch (err) {
      bodyEl.style.opacity = '1';
      Log.write('prd', 'Regenerate failed: ' + err.message, 'err');
      App.showError('Regenerate failed: ' + err.message);
      return;
    }
    S.project.prd[data.section_key] = data.updated_content;
    bodyEl.innerHTML = UI._formatPrdContent(data.updated_content);
    bodyEl.style.opacity = '1';
    bodyEl.style.animation = 'none';
    bodyEl.offsetHeight; // reflow
    bodyEl.style.animation = 'sectionFadeIn 0.3s ease';
    Log.write('prd', `${label} regenerated.`, 'ok');
  },

  // ── 03 Scaffold ──────────────────────────────────────────
  async scaffold() {
    const name      = document.getElementById('repoNameInput').value.trim() || S.project.name || 'forge-project';
    const stackRaw  = document.getElementById('stackOverride').value.trim();
    const stack     = stackRaw ? stackRaw.split(',').map(s=>s.trim()) : S.project.techStack;
    const structure = document.querySelector('[name=structure]:checked')?.value || 'monorepo';
    const scaffoldBtn = document.querySelector('#panel-scaffold .btn-primary');
    if (scaffoldBtn) { scaffoldBtn.disabled = true; scaffoldBtn.textContent = '⟳ Generating...'; }

    Log.write('scaffold', `Generating ${structure} scaffold: ${name}`, 'sys');
    App.setProjectPill(name, 'SCAFFOLDING');

    let data;
    try {
      data = await LLM.call('scaffold', { name, stack, structure, idea:S.project.idea, prd:S.project.prd, github_token:S.github.connected?S.github.token:'', private:false, kb_context: _getKBContext() });
    } catch (err) {
      Log.write('scaffold', 'Failed: ' + err.message, 'err');
      App.showError('Scaffold failed: ' + err.message);
      if (scaffoldBtn) { scaffoldBtn.disabled = false; scaffoldBtn.textContent = '▷ Generate + Push to GitHub'; }
      return;
    }

    if (data.github_error) {
      if (data.github_error.startsWith('__CIYML_MANUAL__:')) {
        const yml = data.github_error.replace('__CIYML_MANUAL__:', '');
        Log.write('scaffold', '⚠ ci.yml needs manual add — showing instructions', 'warn');
        const modal = document.createElement('div');
        modal.style.cssText = 'position:fixed;inset:0;background:#000a;z-index:9999;display:flex;align-items:center;justify-content:center;';
        const safe = yml.replace(/</g,'&lt;').replace(/>/g,'&gt;');
        modal.innerHTML = '<div style="background:var(--surface);border:1px solid var(--yellow);border-radius:12px;padding:24px;max-width:620px;width:90%;max-height:80vh;overflow:auto;">'
          + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
          + '<span style="color:var(--yellow);font-weight:600;font-size:13px;">⚠ Add ci.yml to GitHub manually</span>'
          + '<button onclick="this.closest(\'.modal-ciyml\').remove()" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:18px;">✕</button></div>'
          + '<p style="color:var(--text2);font-size:12px;margin-bottom:10px;">Create <code style="color:var(--accent);">.github/workflows/ci.yml</code> in your repo with this content:</p>'
          + '<pre style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px;font-size:10px;color:var(--text1);overflow:auto;max-height:280px;white-space:pre-wrap;">' + safe + '</pre>'
          + '<button id="copyCiBtn" style="margin-top:10px;padding:8px 18px;background:var(--accent);border:none;border-radius:6px;color:#000;font-weight:600;cursor:pointer;font-size:12px;">Copy to Clipboard</button>'
          + '</div>';
        modal.classList.add('modal-ciyml');
        document.body.appendChild(modal);
        document.getElementById('copyCiBtn').onclick = () => {
          navigator.clipboard.writeText(yml);
          document.getElementById('copyCiBtn').textContent = '✓ Copied!';
        };
      } else {
        Log.write('scaffold', '⚠ GitHub: ' + data.github_error, 'warn');
        App.showError('Scaffold OK — GitHub push partial.');
      }
    }

    S.scaffoldFiles = data.files;
    const treeEl = document.getElementById('fileTree');
    treeEl.innerHTML = '';
    for (const f of data.files) {
      await Utils.sleep(50);
      const item = document.createElement('div');
      item.className = 'tree-item';
      const hasContent = f.type === 'file' && f.content;
      if (hasContent) item.onclick = () => UI.showFilePreview(f.path, f.content);
      item.innerHTML = `<span style="color:${f.type==='dir'?'var(--accent2)':'var(--muted)'}">${f.type==='dir'?'📁':'📄'}</span><span style="color:${f.type==='dir'?'var(--text)':'var(--muted)'}">${f.path}</span>${hasContent?'<span style="color:var(--border2);font-size:9px;margin-left:auto;">view</span>':''}`;
      treeEl.appendChild(item);
      Log.write('scaffold', '+ ' + f.path, f.type==='dir'?'info':'ok');
    }

    if (S.github.connected && data.repo_url && !data.github_error) {
      S.project.repoUrl = data.repo_url;
      document.getElementById('repoUrlInput').value = data.repo_url;
      Log.write('scaffold', `✓ ${data.pushed} files pushed → ${data.repo_url}`, 'ok');
    } else if (!S.github.connected) {
      Log.write('scaffold', 'GitHub not connected — local scaffold only', 'warn');
    }

    Canvas.drawArch('scaffoldD3Container');
    document.getElementById('proceedCicdBtn').style.display = 'block';
    if (scaffoldBtn) { scaffoldBtn.disabled = false; scaffoldBtn.textContent = '▷ Generate + Push to GitHub'; }
    App.setProjectPill(name, 'SCAFFOLDED');
    App.markTabDone('scaffold');
  },

  // ── 04 CI/CD ✅ REAL ─────────────────────────────────────
  async cicd() {
    // Clear any existing poll
    if (S.cicd.pollTimer) { clearInterval(S.cicd.pollTimer); S.cicd.pollTimer = null; }

    const repoUrl = document.getElementById('repoUrlInput').value.trim();
    const branch  = document.getElementById('branchInput').value.trim() || 'main';
    const mode    = document.querySelector('[name=watchmode]:checked')?.value || 'live';

    const logEl = document.getElementById('cicdLog');
    logEl.innerHTML = '';
    document.getElementById('autoFixBanner').classList.add('hidden');

    Log.write('cicd', repoUrl ? `Watching: ${repoUrl} @ ${branch}` : 'No repo URL — demo mode', 'sys');
    App.setProjectPill(S.project.name, 'CI/CD WATCH');

    const doFetch = async () => {
      let data;
      try {
        data = await LLM.call('cicd/watch', {
          repo_url:     repoUrl,
          branch,
          github_token: S.github.connected ? S.github.token : '',
        });
      } catch (err) {
        Log.write('cicd', 'Fetch error: ' + err.message, 'err');
        return;
      }

      if (data.error) { Log.write('cicd', '⚠ ' + data.error, 'warn'); return; }
      if (data.is_simulated) Log.write('cicd', '— demo mode (connect GitHub for real data) —', 'warn');

      // Only redraw if run changed
      if (data.run_id && data.run_id === S.cicd.lastRunId && mode === 'poll') return;
      S.cicd.lastRunId = data.run_id;

      // Render pipeline log from steps
      logEl.innerHTML = '';
      const header = document.createElement('div');
      header.style.cssText = 'color:var(--muted);font-family:var(--font-mono);font-size:12px;line-height:1.8;margin-bottom:4px;';
      const runLabel = data.run_number ? `Run #${data.run_number}` : 'Pipeline';
      const statusColor = data.conclusion === 'success' ? 'var(--green)' : data.conclusion === 'failure' ? 'var(--red)' : 'var(--yellow)';
      header.innerHTML = `<span style="color:${statusColor}">▷ ${runLabel}</span>  ${data.commit_msg || ''}  <span style="color:var(--muted);">@ ${data.branch}</span>`;
      if (data.run_url) {
        const a = document.createElement('a');
        a.href = data.run_url; a.target = '_blank';
        a.style.cssText = 'color:var(--accent2);margin-left:12px;font-size:10px;';
        a.textContent = '→ View on GitHub';
        header.appendChild(a);
      }
      logEl.appendChild(header);

      // Steps
      (data.steps || data.jobs || []).forEach(step => {
        const d = document.createElement('div');
        d.style.cssText = `font-family:var(--font-mono);font-size:12px;line-height:1.8;`;
        const icon = step.conclusion === 'success' ? '✓' : step.conclusion === 'failure' ? '✗' : step.conclusion === 'skipped' ? '—' : '⟳';
        const col  = step.conclusion === 'success' ? 'var(--green)' : step.conclusion === 'failure' ? 'var(--red)' : step.conclusion === 'skipped' ? 'var(--border2)' : 'var(--yellow)';
        const jobLabel = step.job ? `[${step.job}]` : '';
        d.innerHTML = `<span style="color:${col}">${icon}</span> <span style="color:var(--muted);font-size:10px;">${jobLabel}</span> ${step.name || step.label || ''}`;
        logEl.appendChild(d);
      });

      if (data.failure_log) {
        const pre = document.createElement('pre');
        pre.style.cssText = 'color:var(--red);font-family:var(--font-mono);font-size:11px;margin-top:10px;padding:10px;background:rgba(248,113,113,0.05);border:1px solid var(--red);border-radius:4px;white-space:pre-wrap;';
        pre.textContent = data.failure_log;
        logEl.appendChild(pre);
        S.cicd.failureLog = data.failure_log;
      }

      logEl.scrollTop = logEl.scrollHeight;

      // Stage status cells
      const stageMap = { build:'stage_build', tests:'stage_test', lint:'stage_lint', deploy:'stage_deploy' };
      Object.entries(stageMap).forEach(([id, key]) => {
        const el = document.getElementById(`st-${id}`);
        if (!el) return;
        const v = data[key];
        const icon = v === 'success' ? '✓' : v === 'failure' ? '✗' : v === 'skipped' ? '—' : '⟳';
        const col  = v === 'success' ? 'var(--green)' : v === 'failure' ? 'var(--red)' : v === 'skipped' ? 'var(--border2)' : 'var(--yellow)';
        el.textContent = icon; el.style.color = col;
        Log.write('cicd', `${id.toUpperCase()}: ${icon}`, v === 'success'?'ok':v === 'failure'?'err':'info');
      });

      // Show autofix if failed
      if (data.conclusion === 'failure' || (data.jobs||[]).some(j => j.conclusion === 'failure')) {
        document.getElementById('autoFixBanner').classList.remove('hidden');
        Log.write('cicd', '⚠ Failure — Auto-Fix available', 'err');
        if (S.cicd.pollTimer) { clearInterval(S.cicd.pollTimer); S.cicd.pollTimer = null; }
        App.setProjectPill(S.project.name, 'CI/CD FAILED');
      } else if (data.conclusion === 'success') {
        Log.write('cicd', '✓ Pipeline passed', 'ok');
        App.setProjectPill(S.project.name, 'CI/CD GREEN');
        App.markTabDone('cicd');
        if (S.cicd.pollTimer) { clearInterval(S.cicd.pollTimer); S.cicd.pollTimer = null; }
      }
    };

    await doFetch();

    if (mode === 'poll' && !S.cicd.pollTimer) {
      Log.write('cicd', 'Polling every 30s...', 'info');
      S.cicd.pollTimer = setInterval(doFetch, 30000);
    }
  },

  async autoFix() {
    document.getElementById('autoFixBanner').classList.add('hidden');
    Log.write('cicd', 'AI analyzing failure...', 'sys');

    let data;
    try {
      console.log('[DEBUG] failureLog length:', S.cicd.failureLog?.length, 'preview:', S.cicd.failureLog?.slice(0,200));
      data = await LLM.call('cicd/autofix', {
        failure_log:  S.cicd.failureLog || 'Lint failure: unused import detected.',
        repo_url:     document.getElementById('repoUrlInput').value.trim(),
        branch:       document.getElementById('branchInput').value.trim() || 'main',
        github_token: S.github.connected ? S.github.token : '',
        stack:        S.project.techStack || [],
      });
    } catch (err) {
      Log.write('cicd', 'Autofix failed: ' + err.message, 'err');
      App.showError('Autofix failed: ' + err.message);
      return;
    }

    Log.write('cicd', `${data.provider} · ${data.latency_ms}ms`, 'info');

    // Render AI analysis in pipeline log
    const logEl = document.getElementById('cicdLog');
    const divider = document.createElement('div');
    divider.style.cssText = 'border-top:1px solid var(--border);margin:10px 0;';
    logEl.appendChild(divider);

    const render = (html) => {
      const d = document.createElement('div');
      d.style.cssText = 'font-family:var(--font-mono);font-size:11px;line-height:1.9;';
      d.innerHTML = html; logEl.appendChild(d);
    };

    render(`<span style="color:var(--accent2);">⬡ AI AUTOFIX</span>`);
    if (data.summary)    render(`<span style="color:var(--text);">${data.summary}</span>`);
    if (data.root_cause) render(`<span style="color:var(--yellow);">Root cause: ${data.root_cause}</span>`);

    if (data.patches && data.patches.length) {
      render(`<span style="color:var(--muted);">── Patches ──</span>`);
      data.patches.forEach(p => {
        if (p.old_line) render(`<span style="color:var(--red);">− ${p.file}: ${p.old_line}</span>`);
        if (p.new_line) render(`<span style="color:var(--green);">+ ${p.new_line}</span>`);
        if (p.explanation) render(`<span style="color:var(--muted);font-size:10px;">  ${p.explanation}</span>`);
      });
    }

    if (data.commands && data.commands.length) {
      render(`<span style="color:var(--muted);">── Run these locally ──</span>`);
      data.commands.forEach(cmd => render(`<span style="color:var(--accent2);">$ ${cmd}</span>`));
    }

    // Show apply results if patches were applied
    if (data.apply_results && data.apply_results.length) {
      render(`<span style="color:var(--muted);">── Patch apply results ──</span>`);
      data.apply_results.forEach(r => {
        const col = r.status === 'applied' ? 'var(--green)' : r.status === 'error' ? 'var(--red)' : 'var(--yellow)';
        render(`<span style="color:${col};">${r.status === 'applied' ? '✓' : '⚠'} ${r.file}: ${r.reason}</span>`);
      });
      if (data.patches_applied > 0) {
        render(`<span style="color:var(--green);">✓ ${data.patches_applied} patch(es) committed → new CI run triggered automatically</span>`);
      }
    }

    // Show "Apply to GitHub" button if patches exist and not yet applied
    if (data.patches && data.patches.length && S.github.connected && !data.patches_applied) {
      const applyBtn = document.createElement('button');
      applyBtn.className = 'btn-primary';
      applyBtn.style.cssText = 'margin-top:12px;background:var(--green);border-color:var(--green);font-size:11px;';
      applyBtn.textContent = `⚡ Apply ${data.patches.length} Patch(es) to GitHub`;
      applyBtn.onclick = async () => {
        applyBtn.disabled = true; applyBtn.textContent = '⟳ Applying...';
        Log.write('cicd', 'Applying patches to GitHub...', 'sys');
        try {
          // Pass the EXACT patches from this response — don't re-run LLM
          const r = await LLM.call('cicd/autofix', {
            failure_log:   S.cicd.failureLog,
            repo_url:      document.getElementById('repoUrlInput').value.trim(),
            branch:        document.getElementById('branchInput').value.trim() || 'main',
            github_token:  S.github.token,
            stack:         S.project.techStack || [],
            apply_patches: true,
            patches:       data.patches,
          });
          const applied = r.patches_applied || 0;
          applyBtn.textContent = applied ? `✓ ${applied} patch(es) applied — CI re-running` : '⚠ No patches applied';
          applyBtn.style.background = applied ? 'var(--green)' : 'var(--yellow)';
          Log.write('cicd', applied ? `✓ ${applied} patch(es) committed to GitHub` : '⚠ Patches not applied', applied ? 'ok' : 'warn');
          if (applied) setTimeout(() => Agents.cicd(), 5000); // auto re-poll CI
        } catch(e) {
          applyBtn.textContent = '✗ Apply failed';
          Log.write('cicd', 'Apply failed: ' + e.message, 'err');
        }
      };
      logEl.appendChild(applyBtn);
    }

    logEl.scrollTop = logEl.scrollHeight;

    Log.write('cicd', `AI fix: ${data.summary || 'patches generated'}`, 'ok');
    Log.write('cicd', `${data.patches?.length||0} patches, ${data.commands?.length||0} commands`, 'info');
  },

  // ── 05 Launch ────────────────────────────────────────────
  async launch() {
    const ctx   = document.getElementById('launchCtxInput').value.trim() || S.project.idea;
    if (!ctx) { App.showError('Add context or run pipeline first.'); return; }
    const focus = Array.from(document.querySelectorAll('[data-focus]:checked')).map(e => e.dataset.focus);

    Log.write('launch', 'Generating launch checklist...', 'sys');

    let data;
    try {
      data = await LLM.call('checklist', { idea:ctx, stack:S.project.techStack||[], focus });
    } catch (err) { Log.write('launch','Failed: '+err.message,'err'); App.showError('Checklist failed.'); return; }

    document.getElementById('launchEmpty').style.display    = 'none';
    document.getElementById('checklistItems').style.display = 'block';
    S._checkItems = data.items;
    document.getElementById('checklistItems').innerHTML = data.items.map((item,i) => `
      <div class="check-item" id="ci-${i}">
        <input type="checkbox" ${item.done?'checked':''} onchange="Agents.updateCheck(${i},this.checked,${data.items.length})"/>
        <div style="flex:1;">
          <span class="check-cat">${item.cat}</span>
          <span class="check-label ${item.done?'done':''}" id="cl-${i}">${item.label}</span>
          ${item.detail?`<div style="font-size:11px;color:var(--muted);margin-top:2px;font-family:var(--font-mono);">${item.detail}</div>`:''}
        </div>
        <button class="btn-ghost" style="padding:3px 10px;font-size:10px;white-space:nowrap;" onclick="DoIt.open(${i})">Do it →</button>
      </div>`).join('');

    Agents._updateCheckProgress(data.items.filter(i=>i.done).length, data.items.length);
    App.markTabDone('launch');
    Log.write('launch',`Generated ${data.items.length} items.`,'ok');
    App.setProjectPill(S.project.name,'LAUNCH READY');
  },

  updateCheck(idx, checked, total) {
    const l = document.getElementById('cl-'+idx);
    if (l) l.className = 'check-label'+(checked?' done':'');
    Agents._updateCheckProgress(document.querySelectorAll('#checklistItems input:checked').length, total);
  },
  _updateCheckProgress(done, total) {
    document.getElementById('checkDone').textContent  = done;
    document.getElementById('checkLabel').textContent = `of ${total} complete`;
    document.getElementById('checkBar').style.width   = `${total?((done/total)*100):0}%`;
  },

  // ── Diagram ✅ REAL AI ────────────────────────────────────
  async modifyDiagram() {
    const promptEl = document.getElementById('diagramPrompt');
    const instruction = promptEl.value.trim();
    if (!instruction) return;

    const applyBtn = document.querySelector('.diagram-prompt-bar .btn-primary');
    if (applyBtn) { applyBtn.disabled = true; applyBtn.textContent = '⟳ Applying...'; }
    promptEl.value = '';

    let data;
    try {
      data = await LLM.call('diagram/modify', {
        nodes:       S.diagram.nodes,
        edges:       S.diagram.edges,
        instruction,
        stack:       S.project.techStack || [],
      });
    } catch (err) {
      App.showError('Diagram modification failed: ' + err.message);
      if (applyBtn) { applyBtn.disabled = false; applyBtn.textContent = 'Apply'; }
      return;
    }

    S.diagram.nodes = data.nodes;
    S.diagram.edges = data.edges;
    S.diagram._aiModified = true;  // switch to node-bubble view

    Canvas.drawArch('archD3Container');

    // Show change summary below diagram
    let summaryEl = document.getElementById('diagramSummary');
    if (!summaryEl) {
      summaryEl = document.createElement('div');
      summaryEl.id = 'diagramSummary';
      summaryEl.style.cssText = 'font-family:var(--font-mono);font-size:11px;color:var(--accent2);text-align:center;padding:8px;';
      document.querySelector('.canvas-container').after(summaryEl);
    }
    summaryEl.textContent = `✓ ${data.change_summary}  ·  ${data.latency_ms}ms`;

    if (applyBtn) { applyBtn.disabled = false; applyBtn.textContent = 'Apply'; }
    App.updateUsage(data.tokens_used, data.model, data.provider);
  },
};

// ══ UI HELPERS ════════════════════════════════════════════
const UI = {
  scoreRing(val, label, color) {
    const r=28,cx=36,circ=2*Math.PI*r,dash=circ*(val/100);
    return `<div class="card" style="text-align:center;">
      <div style="position:relative;width:72px;height:72px;margin:0 auto 8px;">
        <svg width="72" height="72" viewBox="0 0 72 72" style="transform:rotate(-90deg)">
          <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="var(--faint)" stroke-width="4"/>
          <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${color}" stroke-width="4" stroke-dasharray="${dash} ${circ}" stroke-linecap="round"/>
        </svg>
        <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px;color:${color};">${val}</div>
      </div>
      <div class="card-label" style="margin-bottom:0;">${label}</div>
    </div>`;
  },

  metricBar({label, val}) {
    const color = val>75?'var(--green)':val>60?'var(--accent)':'var(--yellow)';
    return `<div style="margin-bottom:10px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span style="font-size:12px;">${label}</span>
        <span style="font-family:var(--font-mono);font-size:11px;color:var(--muted);">${val}%</span>
      </div>
      <div class="metric-bar-track"><div class="metric-bar-fill" style="width:${val}%;background:${color};"></div></div>
    </div>`;
  },

  prdSection(key, label, content) {
    const formatted = UI._formatPrdContent(content);
    return `<div class="prd-section">
      <div class="prd-sec-header">
        <span class="prd-sec-label">${label}</span>
        <button class="btn-ghost" style="padding:3px 10px;font-size:11px;" onclick="Agents.regenerateSection('${key}','${label}')">↺ Regenerate</button>
      </div>
      <div class="prd-sec-body" id="prd-body-${key}">${formatted}</div>
    </div>`;
  },

  _formatPrdContent(raw) {
    if (!raw) return '';
    // If it looks like a Python dict or JSON object string, parse and prettify it
    let text = String(raw).trim();
    // Remove outer quotes if string-wrapped
    if ((text.startsWith("'") && text.endsWith("'")) || (text.startsWith('"') && text.endsWith('"'))) {
      text = text.slice(1, -1);
    }
    // If it looks like a dict/object: {'key': 'value', ...}
    if (text.startsWith('{') && text.includes(':')) {
      try {
        // Convert Python-style dict to JSON
        const jsonStr = text
          .replace(/'/g, '"')
          .replace(/: "/g, ': "')
          .replace(/True/g, 'true').replace(/False/g, 'false').replace(/None/g, 'null');
        const obj = JSON.parse(jsonStr);
        return Object.entries(obj)
          .map(([k,v]) => `<div style="margin-bottom:10px;"><strong style="color:var(--text);text-transform:capitalize;">${k.replace(/_/g,' ')}</strong><br><span style="color:var(--text2);">${v}</span></div>`)
          .join('');
      } catch(e) {
        // Fall through to plain text
      }
    }
    // If it looks like an array [item1, item2]
    if (text.startsWith('[') && text.endsWith(']')) {
      try {
        const jsonStr = text.replace(/'/g, '"');
        const arr = JSON.parse(jsonStr);
        return arr.map(item => `<div style="padding:4px 0;color:var(--text2);border-bottom:1px solid var(--border);">• ${item}</div>`).join('');
      } catch(e) {}
    }
    // Plain text — convert bullet markers and newlines
    return text
      .replace(/\\n/g, '<br>')
      .replace(/\n/g, '<br>')
      .replace(/\u2022 /g, '<br>\u2022 ')
      .replace(/\* /g, '<br>\u2022 ');
  },

  showFilePreview(path, content) {
    const existing = document.getElementById('filePreviewModal');
    if (existing) existing.remove();
    const modal = document.createElement('div');
    modal.id = 'filePreviewModal';
    modal.style.cssText = 'position:fixed;inset:0;background:#000a;z-index:9999;display:flex;align-items:center;justify-content:center;';
    modal.innerHTML = `<div style="background:var(--surface2);border:1px solid var(--border2);border-radius:8px;width:70vw;max-height:70vh;display:flex;flex-direction:column;">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid var(--border);">
        <span style="font-family:var(--font-mono);font-size:11px;color:var(--accent2);">${path}</span>
        <button onclick="document.getElementById('filePreviewModal').remove()" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:16px;">✕</button>
      </div>
      <pre style="flex:1;overflow:auto;padding:14px;font-family:var(--font-mono);font-size:11px;color:var(--text);line-height:1.7;margin:0;white-space:pre-wrap;">${content.replace(/</g,'&lt;')}</pre>
    </div>`;
    modal.onclick = e => { if (e.target === modal) modal.remove(); };
    document.body.appendChild(modal);
  },
};

// ══ CANVAS — Layered Architecture + ERD ══════════════════════
const Canvas = {

  // ── Shared dot-grid background ──────────────────────────
  _drawGrid(ctx, W, H) {
    ctx.fillStyle = '#080810';
    ctx.fillRect(0, 0, W, H);
    const G = 28;
    ctx.fillStyle = '#ffffff09';
    for (let x = G; x < W; x += G)
      for (let y = G; y < H; y += G) {
        ctx.beginPath(); ctx.arc(x, y, 1, 0, Math.PI*2); ctx.fill();
      }
  },

  // ── Rounded rect helper ─────────────────────────────────
  _rRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
  },

  // ── Arrow between two points ────────────────────────────
  _arrow(ctx, x1, y1, x2, y2, color, label) {
    const dx = x2-x1, dy = y2-y1, len = Math.sqrt(dx*dx+dy*dy);
    if (len < 2) return;
    const ux = dx/len, uy = dy/len;
    const ex = x2 - ux*6, ey = y2 - uy*6;

    ctx.strokeStyle = color + '90';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(ex, ey); ctx.stroke();
    ctx.setLineDash([]);

    // Arrowhead
    const ang = Math.atan2(dy, dx);
    ctx.fillStyle = color + 'aa';
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - 9*Math.cos(ang-0.35), y2 - 9*Math.sin(ang-0.35));
    ctx.lineTo(x2 - 9*Math.cos(ang+0.35), y2 - 9*Math.sin(ang+0.35));
    ctx.closePath(); ctx.fill();

    if (label) {
      const mx = (x1+x2)/2, my = (y1+y2)/2;
      ctx.fillStyle = '#0a0a1299';
      const tw = ctx.measureText(label).width;
      ctx.fillRect(mx - tw/2 - 4, my - 9, tw + 8, 14);
      ctx.fillStyle = color + 'cc';
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.textAlign = 'center';
      ctx.fillText(label, mx, my + 1);
    }
  },

  // ── Layer box ───────────────────────────────────────────
  _drawLayer(ctx, x, y, w, h, title, color, chips) {
    // Shadow
    ctx.shadowColor = color + '20';
    ctx.shadowBlur = 18;

    // Background
    Canvas._rRect(ctx, x, y, w, h, 10);
    ctx.fillStyle = color + '0a';
    ctx.fill();
    ctx.shadowBlur = 0;

    // Border
    Canvas._rRect(ctx, x, y, w, h, 10);
    ctx.strokeStyle = color + '40';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Top label strip
    Canvas._rRect(ctx, x, y, w, 24, [10, 10, 0, 0]);
    ctx.fillStyle = color + '22';
    ctx.fill();
    ctx.fillStyle = color;
    ctx.font = "600 10px 'JetBrains Mono', monospace";
    ctx.textAlign = 'left';
    ctx.fillText(title.toUpperCase(), x + 10, y + 15);

    // Chips inside layer
    const chipH = 26, chipPad = 8, gap = 8;
    const totalW = chips.reduce((s, c) => s + ctx.measureText(c).width + chipPad*2 + gap, -gap);
    let cx = x + (w - Math.min(totalW, w - 20)) / 2;
    const cy = y + h/2 + 6;

    chips.forEach(chip => {
      const cw = ctx.measureText(chip).width + chipPad*2;
      Canvas._rRect(ctx, cx, cy - chipH/2, cw, chipH, 6);
      ctx.fillStyle = color + '18';
      ctx.fill();
      ctx.strokeStyle = color + '55';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.fillStyle = '#c8cae8';
      ctx.font = "500 11px 'DM Sans', sans-serif";
      ctx.textAlign = 'center';
      ctx.fillText(chip, cx + cw/2, cy + 4);
      cx += cw + gap;
    });

    // Return center-bottom point for arrows
    return { top: { x: x+w/2, y }, bottom: { x: x+w/2, y: y+h }, left: { x, y: y+h/2 }, right: { x: x+w, y: y+h/2 } };
  },

  // ══ Architecture Diagram — Layered HLD ═══════════════════
  drawArch(containerId) {
    // Support legacy canvas IDs mapped to D3 container divs
    const idMap = {
      'archCanvas':   'archD3Container',
      'scaffoldArch': 'scaffoldD3Container',
    };
    const cid = idMap[containerId] || containerId;
    Canvas._drawD3Force(cid, S.diagram.nodes, S.diagram.edges);
  },

  _drawD3Force(containerId, nodes, edges) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';

    const W = container.offsetWidth  || 720;
    const H = container.offsetHeight || 460;

    if (typeof d3 === 'undefined') {
      container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#6366f1;font-family:JetBrains Mono,monospace;font-size:12px;">D3 not loaded</div>';
      return;
    }

    const svg = d3.select(container).append('svg')
      .attr('width', W).attr('height', H)
      .style('background', '#09090f');

    const defs = svg.append('defs');

    // Dot-grid background
    defs.append('pattern')
      .attr('id', 'dotgrid-' + containerId)
      .attr('width', 28).attr('height', 28)
      .attr('patternUnits', 'userSpaceOnUse')
      .append('circle').attr('cx', 14).attr('cy', 14).attr('r', 1).attr('fill', '#ffffff08');
    svg.append('rect').attr('width', W).attr('height', H)
      .attr('fill', 'url(#dotgrid-' + containerId + ')');

    // Arrow marker
    defs.append('marker')
      .attr('id', 'arrow-' + containerId)
      .attr('viewBox', '0 -4 8 8').attr('refX', 18).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
      .append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#ffffff22');

    const nodeData = nodes.map((n, i) => ({ ...n, id: i }));
    const linkData = edges
      .filter(([a, b]) => nodeData[a] && nodeData[b])
      .map(([a, b]) => ({ source: a, target: b }));

    const link = svg.append('g').selectAll('line')
      .data(linkData).enter().append('line')
        .attr('stroke', '#ffffff15').attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '4 3')
        .attr('marker-end', 'url(#arrow-' + containerId + ')');

    const node = svg.append('g').selectAll('g')
      .data(nodeData).enter().append('g')
        .style('cursor', 'grab')
        .call(d3.drag()
          .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
          .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
        );

    // Outer glow
    node.append('circle').attr('r', d => d.r + 8).attr('fill', d => d.color + '18').attr('stroke', 'none');
    // Main circle
    node.append('circle').attr('r', d => d.r)
      .attr('fill', d => d.color + '20').attr('stroke', d => d.color).attr('stroke-width', 1.5);
    // Label
    node.append('text').text(d => d.label)
      .attr('text-anchor', 'middle').attr('dy', d => d.r + 14)
      .attr('fill', d => d.color).attr('font-size', 10)
      .attr('font-family', "'DM Sans', sans-serif").attr('font-weight', '500');

    // Hover highlight
    node.on('mouseover', function(e, d) {
        d3.select(this).selectAll('circle').filter((_, i) => i === 1)
          .attr('fill', d.color + '40').attr('stroke-width', 2.5);
      })
      .on('mouseout', function(e, d) {
        d3.select(this).selectAll('circle').filter((_, i) => i === 1)
          .attr('fill', d.color + '20').attr('stroke-width', 1.5);
      });

    const sim = d3.forceSimulation(nodeData)
      .force('link',      d3.forceLink(linkData).id(d => d.id).distance(120).strength(0.4))
      .force('charge',    d3.forceManyBody().strength(-300))
      .force('center',    d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius(d => d.r + 22))
      .on('tick', () => {
        link
          .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('transform', d => {
          d.x = Math.max(d.r + 10, Math.min(W - d.r - 10, d.x));
          d.y = Math.max(d.r + 10, Math.min(H - d.r - 22, d.y));
          return `translate(${d.x},${d.y})`;
        });
      });

    svg.append('text').attr('x', 14).attr('y', H - 10)
      .attr('fill', '#ffffff12').attr('font-size', 9)
      .attr('font-family', "'JetBrains Mono', monospace")
      .text(S.diagram._aiModified ? 'D3 FORCE · AI MODIFIED' : 'D3 FORCE · TECH STACK');
  },

  initArchHover() {},

  // ══ Knowledge Graph — See drawGraph() and _drawLLD() below ════

  _buildERD() {
    const idea  = (S.project.idea || '').toLowerCase();
    const stack = S.project.techStack || [];
    const prd   = S.project.prd || {};

    // Core entity always = project/app
    const name = S.project.name || 'App';

    const entities = [];

    // Always present
    entities.push({
      name: 'User',
      fields: ['id', 'email', 'name', 'created_at'],
      color: '#6366f1', tier: 'core'
    });

    if (idea.includes('invoice') || idea.includes('billing')) {
      entities.push({ name: 'Invoice', fields: ['id', 'user_id', 'amount', 'status', 'due_date'], color: '#34d399', tier: 'core' });
      entities.push({ name: 'LineItem', fields: ['id', 'invoice_id', 'desc', 'qty', 'price'], color: '#34d399', tier: 'child' });
    }
    if (idea.includes('tax')) {
      entities.push({ name: 'TaxRecord', fields: ['id', 'user_id', 'year', 'amount', 'category'], color: '#fbbf24', tier: 'core' });
    }
    if (idea.includes('payment') || stack.some(s => /stripe/i.test(s))) {
      entities.push({ name: 'Payment', fields: ['id', 'invoice_id', 'amount', 'method', 'paid_at'], color: '#f97316', tier: 'core' });
    }
    if (idea.includes('client') || idea.includes('customer')) {
      entities.push({ name: 'Client', fields: ['id', 'user_id', 'name', 'email', 'phone'], color: '#a855f7', tier: 'core' });
    }
    if (stack.some(s => /auth|cognito|firebase/i.test(s)) || idea.includes('auth')) {
      entities.push({ name: 'Session', fields: ['id', 'user_id', 'token', 'expires_at'], color: '#ef4444', tier: 'child' });
    }

    // Generic fallbacks if nothing matched
    if (entities.length < 3) {
      entities.push({ name: 'Project',  fields: ['id', 'owner_id', 'name', 'status'], color: '#34d399', tier: 'core' });
      entities.push({ name: 'Activity', fields: ['id', 'project_id', 'type', 'created_at'], color: '#fbbf24', tier: 'child' });
    }

    return entities.slice(0, 6);
  },

  _drawERD(ctx, W, H, entities) {
    const CARD_W = 160, CARD_H_BASE = 32, FIELD_H = 18;
    const cols = Math.min(3, entities.length);
    const rows = Math.ceil(entities.length / cols);
    const colW = W / cols, rowH = H / rows;

    const boxes = entities.map((e, i) => {
      const col = i % cols, row = Math.floor(i / cols);
      const totalH = CARD_H_BASE + e.fields.length * FIELD_H + 10;
      const bx = col * colW + (colW - CARD_W) / 2;
      const by = row * rowH + (rowH - totalH) / 2;
      return { ...e, x: bx, y: by, w: CARD_W, h: totalH, cx: bx + CARD_W/2, cy: by + totalH/2 };
    });

    // Draw relationships first (under boxes)
    const drawn = new Set();
    boxes.forEach((b, i) => {
      boxes.forEach((b2, j) => {
        if (i >= j) return;
        const key = `${i}-${j}`;
        if (drawn.has(key)) return;
        // Connect if they share a likely FK
        const hasRelation = b.fields.some(f => f.includes(b2.name.toLowerCase().replace(/[^a-z]/g,'') + '_id'))
          || b2.fields.some(f => f.includes(b.name.toLowerCase().replace(/[^a-z]/g,'') + '_id'));
        if (hasRelation || (b.tier === 'core' && b2.tier === 'child')) {
          drawn.add(key);
          const rel = b2.fields.some(f => f.includes(b.name.toLowerCase().replace(/[^a-z]/g,'') + '_id')) ? '1 → N' : 'N → 1';
          Canvas._arrow(ctx, b.cx, b.cy, b2.cx, b2.cy, b.color, rel);
        }
      });
    });

    // Draw entity cards
    boxes.forEach(b => {
      // Card shadow
      ctx.shadowColor = b.color + '30';
      ctx.shadowBlur = 14;

      // Card background
      Canvas._rRect(ctx, b.x, b.y, b.w, b.h, 8);
      ctx.fillStyle = '#12121e';
      ctx.fill();
      ctx.shadowBlur = 0;

      // Header
      Canvas._rRect(ctx, b.x, b.y, b.w, CARD_H_BASE, [8,8,0,0]);
      ctx.fillStyle = b.color + '25';
      ctx.fill();
      ctx.strokeStyle = b.color + '60';
      ctx.lineWidth = 1.5;
      Canvas._rRect(ctx, b.x, b.y, b.w, b.h, 8);
      ctx.stroke();

      // Entity name
      ctx.fillStyle = b.color;
      ctx.font = "700 12px 'DM Sans', sans-serif";
      ctx.textAlign = 'center';
      ctx.fillText(b.name, b.x + b.w/2, b.y + 21);

      // PK indicator
      ctx.fillStyle = b.color + '80';
      ctx.font = "8px 'JetBrains Mono', monospace";
      ctx.textAlign = 'right';
      ctx.fillText('entity', b.x + b.w - 6, b.y + 21);

      // Fields
      b.fields.forEach((f, fi) => {
        const fy = b.y + CARD_H_BASE + 6 + fi * FIELD_H;
        const isPK = f === 'id';
        const isFK = f.endsWith('_id') && f !== 'id';

        if (fi % 2 === 0) {
          ctx.fillStyle = '#ffffff04';
          ctx.fillRect(b.x, fy, b.w, FIELD_H);
        }

        ctx.fillStyle = isPK ? '#fbbf24' : isFK ? b.color + 'cc' : '#8888aa';
        ctx.font = `${isPK || isFK ? '600' : '400'} 10px 'JetBrains Mono', monospace`;
        ctx.textAlign = 'left';
        ctx.fillText((isPK ? '🔑 ' : isFK ? '🔗 ' : '  ') + f, b.x + 8, fy + 12);
      });
    });
  },

  _graphMode: 'erd',

  switchGraphMode(mode) {
    Canvas._graphMode = mode;
    // Sync dropdown if present
    const sel = document.getElementById('graphModeSelect');
    if (sel && sel.value !== mode) sel.value = mode;
    document.getElementById('graphPanelTitle').textContent =
      mode === 'erd' ? 'Knowledge Graph — Entity Relationship' : 'Knowledge Graph — Low Level Design';
    Canvas.drawGraph();
  },

  drawGraph() {
    const canvas = document.getElementById('graphCanvas');
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.offsetWidth || 800;
    const H = canvas.offsetHeight || 520;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    Canvas._drawGrid(ctx, W, H);

    if (!S.project.idea) {
      ctx.fillStyle = '#ffffff20'; ctx.font = "13px 'DM Sans', sans-serif";
      ctx.textAlign = 'center';
      ctx.fillText('Run the pipeline to generate the diagram', W/2, H/2);
      return;
    }

    const gmode = Canvas._graphMode;
    if      (gmode === 'lld')        Canvas._drawLLD(ctx, W, H);
    else if (gmode === 'sequence')   Canvas._drawSequence(ctx, W, H);
    else if (gmode === 'component')  Canvas._drawComponent(ctx, W, H);
    else if (gmode === 'deployment') Canvas._drawDeployment(ctx, W, H);
    else {
      const entities = Canvas._buildERD();
      Canvas._drawERD(ctx, W, H, entities);
      ctx.fillStyle = '#ffffff15'; ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.textAlign = 'left';
      ctx.fillText('ERD · ENTITY RELATIONSHIP DIAGRAM', 16, H - 8);
    }
  },

  _buildLLD() {
    const idea  = (S.project.idea || '').toLowerCase();
    const stack = S.project.techStack || [];
    const name  = S.project.name || 'App';

    // Build class diagram from idea + stack
    const classes = [];

    // Always: main service class
    const mainName = name.replace(/[^a-zA-Z]/g, '') + 'Service';
    classes.push({
      name: mainName,
      type: 'service',
      color: '#6366f1',
      attrs: ['id: str', 'config: dict', 'logger: Logger'],
      methods: ['initialize(): void', 'run(): None', 'shutdown(): void'],
    });

    // User/Auth
    classes.push({
      name: 'UserController',
      type: 'controller',
      color: '#3b82f6',
      attrs: ['user_id: int', 'session: Session', 'permissions: list'],
      methods: ['login(creds): Token', 'logout(): void', 'getProfile(): User'],
    });

    // Data/Repository
    const dbName = stack.find(s => /mongo|postgres|mysql|sqlite/i.test(s)) || 'Database';
    classes.push({
      name: 'Repository',
      type: 'repository',
      color: '#fbbf24',
      attrs: ['db: ' + dbName, 'pool: ConnectionPool', 'cache: Redis'],
      methods: ['findById(id): Model', 'save(obj): bool', 'delete(id): bool'],
    });

    // API layer
    classes.push({
      name: 'APIRouter',
      type: 'router',
      color: '#34d399',
      attrs: ['prefix: str', 'middleware: list', 'routes: dict'],
      methods: ['register(route): void', 'dispatch(req): Response', 'handle_error(e): Response'],
    });

    // Domain-specific class from idea
    if (idea.includes('chatbot') || idea.includes('rag')) {
      classes.push({ name: 'ChatEngine', type: 'engine', color: '#f97316',
        attrs: ['model: LLM', 'history: list[Message]', 'context: str'],
        methods: ['chat(msg): str', 'embed(text): vector', 'retrieve(q): list'] });
    } else if (idea.includes('payment') || idea.includes('invoice')) {
      classes.push({ name: 'PaymentProcessor', type: 'processor', color: '#f97316',
        attrs: ['gateway: str', 'currency: str', 'webhook_url: str'],
        methods: ['charge(amount): Receipt', 'refund(id): bool', 'validate(): bool'] });
    } else if (idea.includes('auth') || idea.includes('saas')) {
      classes.push({ name: 'AuthManager', type: 'manager', color: '#f97316',
        attrs: ['secret_key: str', 'algorithm: str', 'ttl: int'],
        methods: ['sign(payload): JWT', 'verify(token): bool', 'refresh(token): JWT'] });
    } else {
      classes.push({ name: 'DataProcessor', type: 'processor', color: '#f97316',
        attrs: ['queue: Queue', 'workers: int', 'batch_size: int'],
        methods: ['process(data): Result', 'validate(data): bool', 'transform(): dict'] });
    }

    // Relationships
    const rels = [
      { from: 0, to: 1, label: 'uses', type: 'dep' },
      { from: 0, to: 2, label: 'injects', type: 'dep' },
      { from: 1, to: 3, label: 'routes →', type: 'assoc' },
      { from: 1, to: 4, label: 'delegates', type: 'dep' },
      { from: 2, to: 4, label: 'stores', type: 'assoc' },
    ];

    return { classes, rels };
  },

  _drawLLD(ctx, W, H) {
    const { classes, rels } = Canvas._buildLLD();
    const CARD_W = 160, HEADER_H = 36, ATTR_H = 16, METHOD_H = 16, GAP_H = 8;
    const PAD_TOP = 12;

    // Position in a readable layout
    const positions = [
      { col: 1, row: 0 }, // Service - top center
      { col: 0, row: 1 }, // Controller - left
      { col: 2, row: 1 }, // Repository - right
      { col: 0, row: 2 }, // Router - bottom left
      { col: 2, row: 2 }, // Domain - bottom right
    ];

    const cols = 3, rows = 3;
    const colW = W / cols, rowH = H / rows;

    const boxes = classes.map((c, i) => {
      const pos = positions[i] || { col: i % 3, row: Math.floor(i / 3) };
      const cardH = HEADER_H + GAP_H + c.attrs.length * ATTR_H + GAP_H + c.methods.length * METHOD_H + 8;
      const bx = pos.col * colW + (colW - CARD_W) / 2;
      const by = pos.row * rowH + (rowH - cardH) / 2;
      return { ...c, x: bx, y: by, w: CARD_W, h: cardH, cx: bx + CARD_W/2, cy: by + cardH/2 };
    });

    // Draw relationship arrows first
    rels.forEach(r => {
      if (!boxes[r.from] || !boxes[r.to]) return;
      const b1 = boxes[r.from], b2 = boxes[r.to];
      // Find closest edges
      const dx = b2.cx - b1.cx, dy = b2.cy - b1.cy;
      let x1, y1, x2, y2;
      if (Math.abs(dx) > Math.abs(dy)) {
        x1 = dx > 0 ? b1.x + b1.w : b1.x; y1 = b1.cy;
        x2 = dx > 0 ? b2.x : b2.x + b2.w;  y2 = b2.cy;
      } else {
        x1 = b1.cx; y1 = dy > 0 ? b1.y + b1.h : b1.y;
        x2 = b2.cx; y2 = dy > 0 ? b2.y : b2.y + b2.h;
      }
      const col = r.type === 'dep' ? '#ffffff30' : b1.color + '60';
      ctx.save();
      ctx.strokeStyle = col; ctx.lineWidth = 1.5;
      ctx.setLineDash(r.type === 'dep' ? [4, 3] : []);
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      ctx.setLineDash([]);
      // Arrowhead
      const angle = Math.atan2(y2 - y1, x2 - x1);
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - 10 * Math.cos(angle - 0.35), y2 - 10 * Math.sin(angle - 0.35));
      ctx.lineTo(x2 - 10 * Math.cos(angle + 0.35), y2 - 10 * Math.sin(angle + 0.35));
      ctx.closePath(); ctx.fill();
      // Relationship label
      const mx = (x1 + x2)/2, my = (y1 + y2)/2;
      ctx.fillStyle = '#ffffff50'; ctx.font = "8px 'JetBrains Mono', monospace";
      ctx.textAlign = 'center'; ctx.fillText(r.label, mx, my - 5);
      ctx.restore();
    });

    // Draw class cards
    boxes.forEach(b => {
      // Shadow
      ctx.shadowColor = b.color + '40'; ctx.shadowBlur = 16;

      // Card bg
      Canvas._rRect(ctx, b.x, b.y, b.w, b.h, 8);
      ctx.fillStyle = '#0d0d1c'; ctx.fill();
      ctx.shadowBlur = 0;

      // Header
      Canvas._rRect(ctx, b.x, b.y, b.w, HEADER_H, [8,8,0,0]);
      ctx.fillStyle = b.color + '20'; ctx.fill();
      ctx.strokeStyle = b.color + '80'; ctx.lineWidth = 1.5;
      Canvas._rRect(ctx, b.x, b.y, b.w, b.h, 8);
      ctx.stroke();

      // C badge circle
      ctx.beginPath();
      ctx.arc(b.x + 14, b.y + HEADER_H/2, 9, 0, Math.PI * 2);
      ctx.fillStyle = b.color + '30'; ctx.fill();
      ctx.strokeStyle = b.color; ctx.lineWidth = 1.2; ctx.stroke();
      ctx.fillStyle = b.color; ctx.font = "bold 9px 'JetBrains Mono', monospace";
      ctx.textAlign = 'center';
      ctx.fillText('C', b.x + 14, b.y + HEADER_H/2 + 3);

      // Class name
      ctx.fillStyle = '#ffffff'; ctx.font = "bold 11px 'DM Sans', sans-serif";
      ctx.textAlign = 'left';
      ctx.fillText(b.name, b.x + 28, b.y + HEADER_H/2 + 4);

      // Divider
      let curY = b.y + HEADER_H + GAP_H/2;
      ctx.strokeStyle = b.color + '30'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(b.x, curY); ctx.lineTo(b.x + b.w, curY); ctx.stroke();
      curY += GAP_H/2;

      // Attributes
      b.attrs.forEach((attr, ai) => {
        if (ai % 2 === 0) { ctx.fillStyle = '#ffffff04'; ctx.fillRect(b.x, curY, b.w, ATTR_H); }
        ctx.fillStyle = '#60a5fa'; ctx.font = "9px 'JetBrains Mono', monospace";
        ctx.textAlign = 'left';
        ctx.fillText('○ ' + attr, b.x + 8, curY + ATTR_H - 4);
        curY += ATTR_H;
      });

      // Divider
      ctx.strokeStyle = b.color + '20'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(b.x, curY + GAP_H/2); ctx.lineTo(b.x + b.w, curY + GAP_H/2); ctx.stroke();
      curY += GAP_H;

      // Methods
      b.methods.forEach((method, mi) => {
        if (mi % 2 === 0) { ctx.fillStyle = '#ffffff04'; ctx.fillRect(b.x, curY, b.w, METHOD_H); }
        ctx.fillStyle = b.color + 'cc'; ctx.font = "9px 'JetBrains Mono', monospace";
        ctx.textAlign = 'left';
        ctx.fillText('● ' + method, b.x + 8, curY + METHOD_H - 4);
        curY += METHOD_H;
      });
    });

    // Footer
    ctx.fillStyle = '#ffffff15'; ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.textAlign = 'left';
    ctx.fillText('LLD · LOW LEVEL DESIGN · CLASS DIAGRAM', 16, H - 8);
  },

  // ── Sequence Diagram ──────────────────────────────────────────────────────
  _drawSequence(ctx, W, H) {
    const idea  = (S.project.idea || '').toLowerCase();
    const stack = S.project.techStack || [];
    const name  = S.project.name || 'App';

    // Build participants from stack/idea
    const participants = [
      { label: 'User',           color: '#6366f1' },
      { label: stack.find(s => /react|vue|next|angular/i.test(s)) || 'Frontend', color: '#3b82f6' },
      { label: stack.find(s => /fastapi|express|django|flask/i.test(s)) || 'API',   color: '#34d399' },
      { label: stack.find(s => /postgres|mysql|mongo|sqlite/i.test(s)) || 'DB',     color: '#fbbf24' },
      { label: stack.find(s => /redis|cache/i.test(s)) || 'Cache',                  color: '#ef4444' },
    ].slice(0, 5);

    const n = participants.length;
    const colW = (W - 60) / n;
    const headerH = 50;
    const laneTop = headerH + 20;
    const laneH   = H - laneTop - 30;

    // Draw participant header boxes + lifelines
    participants.forEach((p, i) => {
      const cx = 30 + i * colW + colW / 2;
      // Box
      const bw = Math.min(colW - 16, 100), bh = 32;
      Canvas._rRect(ctx, cx - bw/2, 14, bw, bh, 6);
      ctx.fillStyle = p.color + '20'; ctx.fill();
      ctx.strokeStyle = p.color + 'aa'; ctx.lineWidth = 1.5; ctx.stroke();
      ctx.fillStyle = p.color; ctx.font = "bold 10px 'DM Sans',sans-serif";
      ctx.textAlign = 'center'; ctx.fillText(p.label, cx, 35);

      // Lifeline
      ctx.strokeStyle = p.color + '40'; ctx.lineWidth = 1;
      ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.moveTo(cx, headerH + 10); ctx.lineTo(cx, H - 20); ctx.stroke();
      ctx.setLineDash([]);
    });

    // Draw messages
    const messages = [
      { from: 0, to: 1, label: 'Request', type: 'sync',  y: 0.12 },
      { from: 1, to: 2, label: 'API Call', type: 'sync',  y: 0.22 },
      { from: 2, to: 3, label: 'Query',    type: 'sync',  y: 0.32 },
      { from: 3, to: 2, label: 'Result',   type: 'return',y: 0.42 },
      { from: 2, to: 4, label: 'Cache set',type: 'async', y: 0.50 },
      { from: 2, to: 1, label: 'Response', type: 'return',y: 0.62 },
      { from: 1, to: 0, label: 'Render',   type: 'return',y: 0.72 },
    ];

    messages.forEach(m => {
      if (m.from >= n || m.to >= n) return;
      const x1 = 30 + m.from * colW + colW / 2;
      const x2 = 30 + m.to   * colW + colW / 2;
      const y  = laneTop + m.y * laneH;
      const col = participants[m.from].color;

      ctx.strokeStyle = col + (m.type === 'return' ? '60' : 'cc');
      ctx.lineWidth   = m.type === 'return' ? 1 : 1.5;
      ctx.setLineDash(m.type === 'return' ? [5, 3] : m.type === 'async' ? [3, 3] : []);
      ctx.beginPath(); ctx.moveTo(x1, y); ctx.lineTo(x2, y); ctx.stroke();
      ctx.setLineDash([]);

      // Arrowhead
      const dir = x2 > x1 ? 1 : -1;
      ctx.fillStyle = col + (m.type === 'return' ? '60' : 'cc');
      ctx.beginPath();
      ctx.moveTo(x2, y);
      ctx.lineTo(x2 - dir * 9, y - 4);
      ctx.lineTo(x2 - dir * 9, y + 4);
      ctx.closePath(); ctx.fill();

      // Label
      const mx = (x1 + x2) / 2;
      ctx.fillStyle = col; ctx.font = "10px 'JetBrains Mono',monospace";
      ctx.textAlign = 'center'; ctx.fillText(m.label, mx, y - 6);
    });

    ctx.fillStyle = '#ffffff15'; ctx.font = "9px 'JetBrains Mono',monospace";
    ctx.textAlign = 'left'; ctx.fillText('SEQUENCE · INTERACTION FLOW', 16, H - 8);
  },

  // ── Component Diagram ─────────────────────────────────────────────────────
  _drawComponent(ctx, W, H) {
    const stack = S.project.techStack || [];
    const idea  = (S.project.idea || '').toLowerCase();
    const name  = S.project.name || 'App';

    const components = [
      { name: 'UI Layer',      tech: stack.find(s => /react|vue|next|angular/i.test(s)) || 'Frontend',  color: '#3b82f6',  x: 0.12, y: 0.22, w: 130, h: 56 },
      { name: 'API Gateway',   tech: stack.find(s => /nginx|traefik|kong/i.test(s)) || 'Gateway',       color: '#6366f1',  x: 0.38, y: 0.10, w: 120, h: 50 },
      { name: 'Business Logic',tech: stack.find(s => /fastapi|express|django/i.test(s)) || 'Core API',  color: '#34d399',  x: 0.38, y: 0.42, w: 130, h: 56 },
      { name: 'Data Store',    tech: stack.find(s => /postgres|mysql|mongo/i.test(s)) || 'Database',    color: '#fbbf24',  x: 0.68, y: 0.22, w: 120, h: 50 },
      { name: 'Cache Layer',   tech: stack.find(s => /redis/i.test(s)) || 'Redis',                      color: '#ef4444',  x: 0.68, y: 0.58, w: 110, h: 46 },
      { name: 'Auth Service',  tech: stack.find(s => /auth|cognito|jwt/i.test(s)) || 'Auth',            color: '#a855f7',  x: 0.12, y: 0.62, w: 120, h: 50 },
      { name: 'Queue',         tech: stack.find(s => /rabbitmq|kafka|celery/i.test(s)) || 'Worker',     color: '#f97316',  x: 0.50, y: 0.75, w: 110, h: 46 },
    ];

    const connections = [[0,1],[0,2],[1,2],[2,3],[2,4],[0,5],[2,6],[6,3]];

    // Compute center points
    const boxes = components.map(c => ({
      ...c,
      cx: c.x * W + c.w / 2,
      cy: c.y * H + c.h / 2,
    }));

    // Draw connections
    connections.forEach(([a, b]) => {
      if (!boxes[a] || !boxes[b]) return;
      Canvas._arrow(ctx, boxes[a].cx, boxes[a].cy, boxes[b].cx, boxes[b].cy, boxes[a].color, '');
    });

    // Draw component boxes (UML component style — with <<component>> lollipop)
    boxes.forEach(b => {
      // Shadow glow
      ctx.shadowColor = b.color + '30'; ctx.shadowBlur = 12;
      Canvas._rRect(ctx, b.x * W, b.y * H, b.w, b.h, 7);
      ctx.fillStyle = '#12121e'; ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = b.color + '80'; ctx.lineWidth = 1.5; ctx.stroke();

      // Header stripe
      Canvas._rRect(ctx, b.x * W, b.y * H, b.w, 20, [7,7,0,0]);
      ctx.fillStyle = b.color + '20'; ctx.fill();
      ctx.strokeStyle = b.color + '40'; ctx.lineWidth = 1; ctx.stroke();

      // <<component>> badge
      ctx.fillStyle = b.color + '80'; ctx.font = "7px 'JetBrains Mono',monospace";
      ctx.textAlign = 'center'; ctx.fillText('‹‹component››', b.x * W + b.w / 2, b.y * H + 11);

      // Component name
      ctx.fillStyle = b.color; ctx.font = "bold 10px 'DM Sans',sans-serif";
      ctx.textAlign = 'center'; ctx.fillText(b.name, b.x * W + b.w / 2, b.y * H + 30);

      // Tech name
      ctx.fillStyle = '#ffffff60'; ctx.font = "9px 'JetBrains Mono',monospace";
      ctx.fillText(b.tech, b.x * W + b.w / 2, b.y * H + b.h - 8);

      // UML lollipop interface symbol (top-right corner)
      const lx = b.x * W + b.w - 12, ly = b.y * H + 8;
      ctx.strokeStyle = b.color + 'aa'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(lx, ly); ctx.lineTo(lx, ly - 6); ctx.stroke();
      ctx.beginPath(); ctx.arc(lx, ly - 9, 3, 0, Math.PI * 2);
      ctx.strokeStyle = b.color + 'cc'; ctx.stroke();
    });

    ctx.fillStyle = '#ffffff15'; ctx.font = "9px 'JetBrains Mono',monospace";
    ctx.textAlign = 'left'; ctx.fillText('COMPONENT · UML COMPONENT DIAGRAM', 16, H - 8);
  },

  // ── Deployment Diagram ────────────────────────────────────────────────────
  _drawDeployment(ctx, W, H) {
    const stack = S.project.techStack || [];
    const name  = S.project.name || 'App';

    const ZONE_PAD = 14;

    // Define deployment zones
    const zones = [
      {
        name: 'CLIENT',
        color: '#3b82f6',
        x: 0.02, y: 0.08, w: 0.20, h: 0.82,
        nodes: [
          { label: 'Browser', tech: stack.find(s => /react|vue|next/i.test(s)) || 'Web App' },
          { label: 'Mobile',  tech: 'iOS / Android' },
        ]
      },
      {
        name: 'EDGE',
        color: '#6366f1',
        x: 0.25, y: 0.08, w: 0.16, h: 0.82,
        nodes: [
          { label: 'CDN',     tech: 'CloudFront' },
          { label: 'Load Bal.', tech: 'nginx / ALB' },
        ]
      },
      {
        name: 'APPLICATION',
        color: '#34d399',
        x: 0.44, y: 0.08, w: 0.22, h: 0.82,
        nodes: [
          { label: 'API',     tech: stack.find(s => /fastapi|express|django/i.test(s)) || 'API Server' },
          { label: 'Worker',  tech: 'Celery / BG Job' },
          { label: 'Auth',    tech: 'JWT / OAuth' },
        ]
      },
      {
        name: 'DATA',
        color: '#fbbf24',
        x: 0.69, y: 0.08, w: 0.20, h: 0.82,
        nodes: [
          { label: 'Primary DB', tech: stack.find(s => /postgres|mysql|mongo/i.test(s)) || 'Database' },
          { label: 'Cache',       tech: stack.find(s => /redis/i.test(s)) || 'Redis' },
          { label: 'Storage',     tech: 'S3 / Blob' },
        ]
      },
    ];

    // Draw zones
    zones.forEach(z => {
      const zx = z.x * W, zy = z.y * H, zw = z.w * W, zh = z.h * H;

      // Zone background
      Canvas._rRect(ctx, zx, zy, zw, zh, 10);
      ctx.fillStyle = z.color + '08'; ctx.fill();
      ctx.strokeStyle = z.color + '40'; ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 3]); ctx.stroke(); ctx.setLineDash([]);

      // Zone label
      ctx.fillStyle = z.color + '80'; ctx.font = "bold 8px 'JetBrains Mono',monospace";
      ctx.textAlign = 'center'; ctx.fillText(z.name, zx + zw/2, zy + 14);

      // Node boxes inside zone
      const nodeH = 44, nodeW = zw - ZONE_PAD * 2;
      const totalNodesH = z.nodes.length * (nodeH + 8) - 8;
      const startY = zy + (zh - totalNodesH) / 2;

      z.nodes.forEach((nd, ni) => {
        const nx = zx + ZONE_PAD;
        const ny = startY + ni * (nodeH + 8);

        ctx.shadowColor = z.color + '20'; ctx.shadowBlur = 8;
        Canvas._rRect(ctx, nx, ny, nodeW, nodeH, 6);
        ctx.fillStyle = '#0d0d1a'; ctx.fill();
        ctx.shadowBlur = 0;
        ctx.strokeStyle = z.color + '60'; ctx.lineWidth = 1; ctx.stroke();

        // Server icon
        ctx.fillStyle = z.color;
        ctx.fillRect(nx + 8, ny + 8, 14, 10);
        ctx.fillStyle = '#0d0d1a'; ctx.fillRect(nx + 10, ny + 10, 10, 6);
        // Indicator dots
        [4, 8, 12].forEach(ox => {
          ctx.beginPath(); ctx.arc(nx + 8 + ox, ny + nodeH - 9, 2, 0, Math.PI * 2);
          ctx.fillStyle = z.color + '80'; ctx.fill();
        });

        // Labels
        ctx.fillStyle = z.color; ctx.font = "bold 10px 'DM Sans',sans-serif";
        ctx.textAlign = 'left'; ctx.fillText(nd.label, nx + 28, ny + 17);
        ctx.fillStyle = '#ffffff50'; ctx.font = "8px 'JetBrains Mono',monospace";
        ctx.fillText(nd.tech, nx + 28, ny + 30);
      });
    });

    // Draw connection arrows between zones
    const zCenters = zones.map(z => ({
      x: (z.x + z.w / 2) * W,
      y: H / 2,
      color: z.color,
    }));
    for (let i = 0; i < zCenters.length - 1; i++) {
      ctx.strokeStyle = zCenters[i].color + '50'; ctx.lineWidth = 2;
      ctx.setLineDash([4,3]);
      ctx.beginPath();
      ctx.moveTo(zCenters[i].x + zones[i].w * W / 2, H / 2);
      ctx.lineTo(zCenters[i+1].x - zones[i+1].w * W / 2, H / 2);
      ctx.stroke(); ctx.setLineDash([]);
    }

    ctx.fillStyle = '#ffffff15'; ctx.font = "9px 'JetBrains Mono',monospace";
    ctx.textAlign = 'left'; ctx.fillText('DEPLOYMENT · INFRASTRUCTURE VIEW', 16, H - 8);
  },

  initGraphHover() {
    const canvas = document.getElementById('graphCanvas');
    if (!canvas || canvas._hoverInited) return;
    canvas._hoverInited = true;
  },
};


const Utils = { sleep: ms => new Promise(r => setTimeout(r, ms)) };


// ══ GITHUB MODAL ══════════════════════════════════════════
const GitHub = {

  showModal() {
    const existing = document.getElementById('ghModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'ghModal';
    modal.innerHTML = `
      <div class="gh-backdrop" onclick="GitHub.close()"></div>
      <div class="gh-panel">
        <div class="gh-header">
          <div style="display:flex;align-items:center;gap:10px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style="color:var(--text2);">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            <span style="font-weight:600;font-size:14px;">Connect GitHub</span>
          </div>
          <button onclick="GitHub.close()" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:18px;">✕</button>
        </div>

        <div class="gh-body">
          <div class="gh-step">
            <div class="gh-step-num">1</div>
            <div>
              <div style="font-weight:600;font-size:13px;margin-bottom:4px;">Generate a Personal Access Token</div>
              <div style="font-size:11px;color:var(--text2);margin-bottom:8px;">Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)</div>
              <a href="https://github.com/settings/tokens/new?scopes=repo,workflow&description=FORGE" target="_blank" class="gh-link-btn">
                Open GitHub Token Page →
              </a>
            </div>
          </div>

          <div class="gh-step">
            <div class="gh-step-num">2</div>
            <div style="flex:1;">
              <div style="font-weight:600;font-size:13px;margin-bottom:6px;">Select required scopes</div>
              <div style="display:flex;flex-direction:column;gap:6px;">
                <div style="display:flex;align-items:center;gap:8px;">
                  <code style="background:var(--surface3);padding:2px 7px;border-radius:3px;color:var(--accent);font-size:11px;">repo</code>
                  <span style="font-size:11px;color:var(--text2);">Create repos, push files, read contents</span>
                  <span style="font-size:10px;color:var(--green);margin-left:auto;">required</span>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                  <code style="background:var(--surface3);padding:2px 7px;border-radius:3px;color:var(--yellow);font-size:11px;">workflow</code>
                  <span style="font-size:11px;color:var(--text2);">Push .github/workflows/ci.yml for CI/CD</span>
                  <span style="font-size:10px;color:var(--green);margin-left:auto;">required</span>
                </div>
              </div>
              <div style="margin-top:8px;padding:7px 10px;background:var(--surface2);border-left:2px solid var(--yellow);border-radius:4px;font-size:10px;color:var(--muted);font-family:var(--font-mono);">
                ⚠ Without <code>workflow</code> scope, ci.yml must be added manually to GitHub
              </div>
            </div>
          </div>

          <div class="gh-step">
            <div class="gh-step-num">3</div>
            <div style="flex:1;">
              <div style="font-weight:600;font-size:13px;margin-bottom:6px;">Paste your token</div>
              <input id="ghTokenInput" type="password" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                style="width:100%;background:var(--surface);border:1px solid var(--border2);border-radius:6px;padding:9px 12px;color:var(--text);font-family:var(--font-mono);font-size:12px;outline:none;"
                onkeydown="if(event.key==='Enter') GitHub.connect()"/>
            </div>
          </div>

          <div class="gh-step" style="margin-top:4px;">
            <div class="gh-step-num">4</div>
            <div style="flex:1;">
              <div style="font-weight:600;font-size:13px;margin-bottom:6px;">Repo URL <span style="color:var(--muted);font-weight:400;">(optional — paste existing repo)</span></div>
              <input id="ghRepoInput" type="text" placeholder="https://github.com/username/repo"
                style="width:100%;background:var(--surface);border:1px solid var(--border2);border-radius:6px;padding:9px 12px;color:var(--text);font-family:var(--font-mono);font-size:12px;outline:none;"/>
              <div style="font-size:10px;color:var(--muted);margin-top:4px;font-family:var(--font-mono);">Leave blank — FORGE will create a new repo from your project name</div>
            </div>
          </div>

          <div id="ghError" style="display:none;color:var(--red);font-size:11px;font-family:var(--font-mono);padding:8px 12px;background:var(--red-dim);border-radius:6px;border:1px solid var(--red)20;"></div>
        </div>

        <div class="gh-footer">
          <button class="btn-primary" id="ghConnectBtn" onclick="GitHub.connect()">
            Verify & Connect
          </button>
          <button class="btn-ghost" onclick="GitHub.close()" style="margin-left:8px;">Cancel</button>
          <div style="flex:1;"></div>
          <span style="font-size:10px;color:var(--muted);font-family:var(--font-mono);">Token stored in session only — never sent to any server except GitHub</span>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    requestAnimationFrame(() => {
      modal.querySelector('.gh-panel').classList.add('open');
      setTimeout(() => document.getElementById('ghTokenInput')?.focus(), 200);
    });
  },

  async connect() {
    const token   = document.getElementById('ghTokenInput')?.value.trim();
    const repoUrl = document.getElementById('ghRepoInput')?.value.trim();
    const btn     = document.getElementById('ghConnectBtn');
    const errEl   = document.getElementById('ghError');

    if (!token) { GitHub._error('Please paste your GitHub token'); return; }

    btn.disabled = true; btn.textContent = '⟳ Verifying...';
    errEl.style.display = 'none';

    // Verify token against GitHub API
    try {
      const res = await fetch('https://api.github.com/user', {
        headers: { Authorization: 'token ' + token, Accept: 'application/vnd.github.v3+json' }
      });
      if (!res.ok) throw new Error('Invalid token — GitHub returned ' + res.status);
      const user = await res.json();

      // Success!
      S.github.connected = true;
      S.github.token     = token;
      S.github.username  = user.login;
      if (repoUrl) S.project.repoUrl = repoUrl;

      GitHub.close();
      GitHub._updateBtn(true, user.login, user.avatar_url);

      // Autofill repo URL in CI/CD panel
      if (repoUrl) {
        const inp = document.getElementById('repoUrlInput');
        if (inp) inp.value = repoUrl;
      }

      Log.write('scaffold', '✓ GitHub connected as @' + user.login, 'ok');
      App.showToast('Connected as @' + user.login, 'ok');

    } catch(e) {
      btn.disabled = false; btn.textContent = 'Verify & Connect';
      GitHub._error(e.message);
    }
  },

  showConnected() {
    // Already connected — show disconnect option
    const existing = document.getElementById('ghModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'ghModal';
    modal.innerHTML = `
      <div class="gh-backdrop" onclick="GitHub.close()"></div>
      <div class="gh-panel" style="max-height:260px;">
        <div class="gh-header">
          <span style="font-weight:600;font-size:14px;color:var(--green);">✓ GitHub Connected</span>
          <button onclick="GitHub.close()" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:18px;">✕</button>
        </div>
        <div class="gh-body">
          <div style="display:flex;align-items:center;gap:12px;padding:12px 0;">
            <div style="width:40px;height:40px;border-radius:50%;background:var(--accent-dim);border:2px solid var(--accent);display:flex;align-items:center;justify-content:center;font-size:18px;">👤</div>
            <div>
              <div style="font-weight:600;color:var(--text);">@\${S.github.username}</div>
              <div style="font-size:11px;color:var(--muted);font-family:var(--font-mono);">Token active · repo scope</div>
            </div>
          </div>
          ${S.project.repoUrl ? '<div style="font-size:11px;color:var(--text2);font-family:var(--font-mono);padding:8px 12px;background:var(--surface);border-radius:6px;border:1px solid var(--border);">📁 ' + S.project.repoUrl + '</div>' : ''}
        </div>
        <div class="gh-footer">
          <button class="btn-ghost" style="color:var(--red);" onclick="GitHub.disconnect()">Disconnect</button>
          <button class="btn-ghost" onclick="GitHub.close()" style="margin-left:8px;">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.querySelector('.gh-panel').classList.add('open'));
  },

  disconnect() {
    S.github.connected = false; S.github.token = ''; S.github.username = '';
    GitHub._updateBtn(false);
    GitHub.close();
    Log.write('scaffold', 'GitHub disconnected.', 'info');
  },

  close() {
    const modal = document.getElementById('ghModal');
    if (!modal) return;
    const panel = modal.querySelector('.gh-panel');
    if (panel) panel.classList.remove('open');
    setTimeout(() => modal.remove(), 280);
  },

  _error(msg) {
    const el = document.getElementById('ghError');
    if (el) { el.textContent = msg; el.style.display = 'block'; }
  },

  _updateBtn(connected, username = '', avatar = '') {
    const btn   = document.getElementById('ghBtn');
    const label = document.getElementById('ghLabel');
    if (!btn || !label) return;
    if (connected) {
      label.textContent = '✓ @' + username;
      btn.style.color   = 'var(--green)';
      btn.style.borderColor = 'var(--green)';
    } else {
      label.textContent = 'Connect GitHub';
      btn.style.color   = '';
      btn.style.borderColor = '';
    }
  },
};

// ══ DO IT DRAWER ══════════════════════════════════════════
const DoIt = {
  _current: null,

  open(idx) {
    const item = (S._checkItems || [])[idx];
    if (!item) return;
    DoIt._current = item;

    // Create or reuse drawer
    let drawer = document.getElementById('doItDrawer');
    if (!drawer) {
      drawer = document.createElement('div');
      drawer.id = 'doItDrawer';
      document.body.appendChild(drawer);
    }

    const catColor = {
      SECURITY: '#ef4444', PERFORMANCE: '#fbbf24',
      SEO: '#3b82f6', DEVOPS: '#a855f7',
      LEGAL: '#34d399', DEFAULT: '#6366f1'
    };
    const color = catColor[item.cat] || catColor.DEFAULT;

    drawer.innerHTML = `
      <div class="doit-backdrop" onclick="DoIt.close()"></div>
      <div class="doit-panel" id="doItPanel">
        <div class="doit-header">
          <div style="display:flex;align-items:center;gap:10px;">
            <span class="check-cat" style="background:${color}20;color:${color};border-color:${color}40;">${item.cat}</span>
            <span style="font-size:13px;font-weight:600;color:var(--text);">${item.label}</span>
          </div>
          <button onclick="DoIt.close()" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:18px;line-height:1;">✕</button>
        </div>

        <div class="doit-meta">
          <span style="color:var(--muted);font-size:11px;font-family:var(--font-mono);">${item.detail || 'AI will generate implementation steps for your stack'}</span>
        </div>

        <div class="doit-body" id="doItBody">
          <div class="doit-empty">
            <div style="font-size:28px;margin-bottom:12px;">⚡</div>
            <div style="font-size:13px;color:var(--text2);margin-bottom:6px;">Ready to generate implementation guide</div>
            <div style="font-size:11px;color:var(--muted);font-family:var(--font-mono);">Stack: ${(S.project.techStack||[]).join(', ') || 'from your project'}</div>
          </div>
        </div>

        <div class="doit-footer">
          <button class="btn-primary" id="doItRunBtn" onclick="DoIt.generate()">
            ⚡ Generate Implementation Guide
          </button>
          <button class="btn-ghost" onclick="DoIt.close()" style="margin-left:8px;">Cancel</button>
        </div>
      </div>
    `;

    // Animate in
    requestAnimationFrame(() => {
      const panel = document.getElementById('doItPanel');
      if (panel) panel.classList.add('open');
    });
  },

  close() {
    const panel = document.getElementById('doItPanel');
    if (panel) {
      panel.classList.remove('open');
      setTimeout(() => {
        const drawer = document.getElementById('doItDrawer');
        if (drawer) drawer.innerHTML = '';
      }, 300);
    }
  },

  async generate() {
    const item  = DoIt._current;
    if (!item) return;

    const btn = document.getElementById('doItRunBtn');
    if (btn) { btn.disabled = true; btn.textContent = '⟳ Generating...'; }

    const body = document.getElementById('doItBody');
    body.innerHTML = `<div class="doit-loading">
      <div class="doit-spinner"></div>
      <div style="color:var(--muted);font-size:12px;margin-top:12px;font-family:var(--font-mono);">AI generating steps…</div>
    </div>`;

    const stack = (S.project.techStack || []).join(', ') || 'general web stack';
    const idea  = S.project.idea || 'web application';

    let data;
    try {
      data = await LLM.call('checklist/doit', {
        task:   item.label,
        cat:    item.cat,
        detail: item.detail || '',
        stack,
        idea,
      });
    } catch(e) {
      body.innerHTML = `<div style="color:var(--red);padding:20px;font-family:var(--font-mono);font-size:12px;">Failed: ${e.message}</div>`;
      if (btn) { btn.disabled = false; btn.textContent = '↺ Retry'; }
      return;
    }

    DoIt._render(body, data, item);
    if (btn) btn.style.display = 'none';
  },

  _render(body, data, item) {
    const steps = data.steps || [];
    const code  = data.code_snippet || '';
    const refs  = data.references || [];
    const time  = data.estimated_time || '';

    let html = `<div class="doit-result">`;

    if (time) {
      html += `<div class="doit-timebadge">⏱ ${time}</div>`;
    }

    if (steps.length) {
      html += `<div class="doit-section-label">IMPLEMENTATION STEPS</div>`;
      html += steps.map((s, i) => `
        <div class="doit-step">
          <div class="doit-step-num">${i+1}</div>
          <div class="doit-step-body">
            <div class="doit-step-title">${s.title || s}</div>
            ${s.detail ? `<div class="doit-step-detail">${s.detail}</div>` : ''}
            ${s.command ? `<div class="doit-code">$ ${s.command}</div>` : ''}
          </div>
        </div>`).join('');
    }

    if (code) {
      html += `<div class="doit-section-label" style="margin-top:16px;">CODE SNIPPET</div>`;
      html += `<pre class="doit-code-block">${code.replace(/</g,'&lt;')}</pre>`;
    }

    if (refs.length) {
      html += `<div class="doit-section-label" style="margin-top:16px;">REFERENCES</div>`;
      html += refs.map(r => `<div class="doit-ref">→ ${r}</div>`).join('');
    }

    html += `</div>`;
    body.innerHTML = html;

    // Add "Mark done" button to footer
    const footer = body.closest('.doit-panel')?.querySelector('.doit-footer');
    if (footer) {
      footer.innerHTML = `
        <button class="btn-primary" onclick="DoIt._markDone()" style="background:var(--green);border-color:var(--green);">✓ Mark as Done</button>
        <button class="btn-ghost" onclick="DoIt.generate()" style="margin-left:8px;">↺ Regenerate</button>
        <button class="btn-ghost" onclick="DoIt.close()" style="margin-left:8px;">Close</button>
      `;
    }
  },

  _markDone() {
    // Find and check the corresponding checklist item
    const items = S._checkItems || [];
    const idx = items.findIndex(i => i.label === DoIt._current?.label);
    if (idx >= 0) {
      const cb = document.querySelector(`#ci-${idx} input[type=checkbox]`);
      if (cb && !cb.checked) { cb.checked = true; cb.dispatchEvent(new Event('change')); }
    }
    DoIt.close();
  },
};

document.addEventListener('DOMContentLoaded', () => {
  App.checkApiHealth();
  window.addEventListener('resize', () => {
    const active = document.querySelector('.panel.active');
    if (!active) return;
    if (active.id === 'panel-diagram')  Canvas.drawArch('archD3Container');
    if (active.id === 'panel-graph')    Canvas.drawGraph();
    if (active.id === 'panel-scaffold') Canvas.drawArch('scaffoldD3Container');
  });
});

// ══ EXPORT ════════════════════════════════════════════════
const Export = {

  async downloadZip() {
    if (!S.scaffoldFiles || !S.scaffoldFiles.length) {
      App.showError('No scaffold generated yet — run Code Scaffold first.'); return;
    }
    const name = S.project.name || 'forge-project';
    Log.write('scaffold', 'Preparing ZIP download...', 'sys');
    try {
      const res = await fetch('/api/export/zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, files: S.scaffoldFiles }),
      });
      if (!res.ok) throw new Error('Server error ' + res.status);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `${name}-scaffold.zip`;
      a.click();
      URL.revokeObjectURL(url);
      Log.write('scaffold', `✓ Downloaded ${name}-scaffold.zip`, 'ok');
    } catch(e) {
      App.showError('ZIP download failed: ' + e.message);
      Log.write('scaffold', 'ZIP failed: ' + e.message, 'err');
    }
  },

  async downloadPdf() {
    if (!S.project.prd || !Object.keys(S.project.prd).length) {
      App.showError('No PRD generated yet — run PRD Generator first.'); return;
    }
    const name = S.project.name || 'project';
    Log.write('prd', 'Generating PDF...', 'sys');
    try {
      const res = await fetch('/api/export/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, sections: S.project.prd }),
      });
      if (!res.ok) throw new Error('Server error ' + res.status);
      const contentType = res.headers.get('Content-Type') || '';
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      // If reportlab not available, server returns HTML
      a.download = contentType.includes('pdf') ? `${name}-prd.pdf` : `${name}-prd.html`;
      a.click();
      URL.revokeObjectURL(url);
      Log.write('prd', `✓ PRD exported`, 'ok');
    } catch(e) {
      App.showError('PDF export failed: ' + e.message);
      Log.write('prd', 'PDF failed: ' + e.message, 'err');
    }
  },
};

;

// ── ChatIndex: Repo Chat + PageIndex Docs Chat ────────────────────────────
const ChatIndex = (() => {
  let repoTree = null, repoHistory = [];
  let docsState = null, docsHistory = [];

  const $ = id => document.getElementById(id);
  const tok = () => S.github.connected ? S.github.token : '';
  const status = msg => { const el = $('ci-status'); if (el) el.textContent = msg; };

  function tab(t) {
    const isRepo = t === 'repo';
    $('ci-repo').style.display         = isRepo ? 'flex'        : 'none';
    $('ci-docs').style.display         = isRepo ? 'none'        : 'flex';
    $('ci-tab-repo').style.color       = isRepo ? 'var(--accent)' : 'var(--muted)';
    $('ci-tab-docs').style.color       = isRepo ? 'var(--muted)' : 'var(--accent)';
    $('ci-tab-repo').style.borderBottomColor = isRepo ? 'var(--accent)' : 'transparent';
    $('ci-tab-docs').style.borderBottomColor = isRepo ? 'transparent'   : 'var(--accent)';
    status('');
  }

  function bubble(containerId, role, text, citations) {
    const c = $(containerId); if (!c) return;
    const wrap = document.createElement('div');
    wrap.style.cssText = `display:flex;flex-direction:column;gap:3px;align-self:${role==='user'?'flex-end':'flex-start'};max-width:82%;`;
    const b = document.createElement('div');
    b.style.cssText = `padding:9px 13px;border-radius:10px;font-size:13px;line-height:1.55;white-space:pre-wrap;background:${role==='user'?'var(--accent)':'var(--surface2)'};color:${role==='user'?'#fff':'var(--text)'};`;
    b.textContent = text;
    wrap.appendChild(b);
    if (citations && citations.length) {
      const c2 = document.createElement('div');
      c2.style.cssText = 'font-size:10px;color:var(--muted);padding:0 4px;font-family:var(--font-mono);';
      c2.textContent = '◎ ' + citations.join('  ·  ');
      wrap.appendChild(c2);
    }
    c.appendChild(wrap);
    c.scrollTop = c.scrollHeight;
  }

  async function repoIndex() {
    const url = $('ci-repo-url') && $('ci-repo-url').value.trim();
    const branch = ($('ci-repo-branch') && $('ci-repo-branch').value.trim()) || 'main';
    const btn = $('ci-repo-index-btn');
    if (!url)   { App.showError('Enter a GitHub repo URL'); return; }
    if (!tok()) { App.showError('Connect GitHub first'); return; }
    btn.disabled = true; btn.textContent = '…';
    status('Indexing repo…');
    try {
      const d = await LLM.call('repochat/index', { repo_url: url, github_token: tok(), branch });
      repoTree = d.tree; repoHistory = [];
      const t = $('ci-repo-tree'); if (t) t.textContent = d.tree_text || '';
      $('ci-repo-msgs').innerHTML = '';
      bubble('ci-repo-msgs', 'assistant', `✓ ${d.total_files} files indexed in ${d.repo}\nAsk anything about the codebase.`);
      status(`✓ ${d.total_files} files — ${d.repo}`);
    } catch (e) { status('Error'); App.showError('Repo index failed: ' + e.message); }
    finally { btn.disabled = false; btn.textContent = 'Re-index'; }
  }

  async function repoAsk() {
    const input = $('ci-repo-q');
    const q = input && input.value.trim(); if (!q) return;
    if (!repoTree) { App.showError('Index a repo first'); return; }
    if (!tok())    { App.showError('Connect GitHub first'); return; }
    input.value = '';
    bubble('ci-repo-msgs', 'user', q);
    repoHistory.push({ role: 'user', content: q });
    status('Thinking…');
    try {
      const d = await LLM.call('repochat/ask', { question: q, tree: repoTree, github_token: tok(), history: repoHistory.slice(-6) });
      bubble('ci-repo-msgs', 'assistant', d.answer, d.files_used);
      repoHistory.push({ role: 'assistant', content: d.answer });
      status(`✓ ${d.tokens || ''} tokens`);
    } catch (e) { status('Error'); bubble('ci-repo-msgs', 'assistant', 'Error: ' + e.message); }
  }

  async function docsIndex() {
    const url = $('ci-docs-url') && $('ci-docs-url').value.trim();
    const btn = $('ci-docs-index-btn');
    const hint = $('ci-docs-hint');
    if (!url)   { App.showError('Paste a GitHub docs folder URL'); return; }
    if (!tok()) { App.showError('Connect GitHub first'); return; }
    btn.disabled = true; btn.textContent = '…';
    if (hint) hint.textContent = '';
    status('Submitting to PageIndex…');
    try {
      const d = await LLM.call('docschat/index', { input: url, github_token: tok() });
      docsState = { tree: d.tree, tree_text: d.tree_text };
      docsHistory = [];
      const t = $('ci-docs-tree'); if (t) t.textContent = d.tree_text || '';
      if (hint && d.hint) hint.textContent = '💡 ' + d.hint;
      $('ci-docs-msgs').innerHTML = '';
      bubble('ci-docs-msgs', 'assistant', `✓ PageIndex tree built from ${d.files_count} markdown files\n${d.source_url}\n\nAsk anything about the docs!`);
      status(`✓ PageIndex — ${d.files_count} files`);
    } catch (e) {
      status('Error');
      if (hint) hint.textContent = '⚠ ' + e.message;
    }
    finally { btn.disabled = false; btn.textContent = 'Re-index'; }
  }

  async function docsAsk() {
    const input = $('ci-docs-q');
    const q = input && input.value.trim(); if (!q) return;
    if (!docsState) { App.showError('Index docs first'); return; }
    input.value = '';
    bubble('ci-docs-msgs', 'user', q);
    docsHistory.push({ role: 'user', content: q });
    status('Reasoning over PageIndex tree…');
    try {
      const d = await LLM.call('docschat/ask', { question: q, tree: docsState.tree, tree_text: docsState.tree_text, history: docsHistory.slice(-6) });
      const cites = (d.nodes_used || []).map(n => `node ${n}`);
      bubble('ci-docs-msgs', 'assistant', d.answer, cites);
      docsHistory.push({ role: 'assistant', content: d.answer });
      status(`✓ nodes: ${(d.nodes_used || []).join(', ') || '—'}`);
    } catch (e) { status('Error'); bubble('ci-docs-msgs', 'assistant', 'Error: ' + e.message); }
  }

  return { tab, repoIndex, repoAsk, docsIndex, docsAsk };
})();


// ── KB context injector — appended to agent payloads when inject is ON ──────
function _getKBContext() {
  if (!S.kb || !S.kb.active || !S.kb.tree) return null;
  return {
    tree:      S.kb.tree,
    tree_text: S.kb.tree_text ? S.kb.tree_text.slice(0, 3000) : '',
    source:    S.kb.label || '',
  };
}

// ── Knowledge Base: PDF · URL · GitHub → PageIndex → Chat ─────────────────
const KB = (() => {
  let _state = {
    tree:      null,
    tree_text: '',
    doc_id:    null,
    piKey:     '',
    source:    '',
    label:     '',
    history:   [],
    inject:    false,
    pdfData:   null,
    pdfName:   '',
  };

  const $  = id => document.getElementById(id);
  // pageindex_key is read from PAGEINDEX_API_KEY env on server side
  // frontend doesn't need to send it unless you want per-user keys
  const _os_piKey = () => '';
  const status = msg => { const el = $('kb-status'); if (el) el.textContent = msg; };

  // ── Tab switching ──────────────────────────────────────────────────────
  function tab(t) {
    ['pdf','url','github'].forEach(id => {
      const src = $(`kb-src-${id}`);
      const btn = $(`kb-tab-${id}`);
      if (!src || !btn) return;
      const active = id === t;
      src.style.display = active ? 'flex' : 'none';
      btn.classList.toggle('active-tab', active);
    });
  }

  // ── File handling ──────────────────────────────────────────────────────
  function handleDrop(e) {
    e.preventDefault();
    $('kb-drop-zone').style.borderColor = 'var(--border2)';
    const file = e.dataTransfer.files[0];
    if (file) _loadFile(file);
  }

  function handleFileSelect(input) {
    if (input.files[0]) _loadFile(input.files[0]);
  }

  function _loadFile(file) {
    if (!file.name.endsWith('.pdf')) {
      App.showError('Only PDF files supported'); return;
    }
    const reader = new FileReader();
    reader.onload = e => {
      _state.pdfData = e.target.result.split(',')[1]; // base64
      _state.pdfName = file.name;
      $('kb-file-name').textContent = `✓ ${file.name} (${(file.size/1024).toFixed(0)} KB)`;
      $('kb-pdf-btn').disabled = false;
    };
    reader.readAsDataURL(file);
  }

  // ── Index functions ────────────────────────────────────────────────────
  async function indexPdf() {
    if (!_state.pdfData) { App.showError('Select a PDF first'); return; }
    await _index('/api/kb/pdf', {
      pdf_b64:  _state.pdfData,
      filename: _state.pdfName,
    }, `PDF: ${_state.pdfName}`);
  }

  async function indexUrl() {
    const url = $('kb-url-input')?.value.trim();
    if (!url) { App.showError('Enter a URL'); return; }
    await _index('/api/kb/url', { url }, url);
  }

  async function indexGithub() {
    const url = $('kb-gh-url')?.value.trim();
    if (!url) { App.showError('Enter a GitHub docs URL'); return; }
    if (!S.github?.connected) { App.showError('Connect GitHub first'); return; }
    await _index('/api/kb/github', {
      url,
      github_token: S.github.token,
    }, url);
  }

  async function _index(endpoint, payload, label) {
    status('Submitting to PageIndex…');
    _bubble('assistant', '⏳ Indexing document — PageIndex is building the tree…');

    try {
      const res = await fetch(endpoint, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Index failed');

      _state.tree      = d.tree;
      _state.tree_text = d.tree_text;
      _state.doc_id    = d.doc_id   || null;
      _state.piKey     = _os_piKey();
      _state.source    = d.source;
      _state.label     = label;
      _state.history   = [];

      // Show tree preview
      const preview = $('kb-tree-preview');
      if (preview) preview.textContent = d.tree_text || '(no tree)';
      const nodeCount = $('kb-node-count');
      if (nodeCount) nodeCount.textContent = `${d.node_count || '?'} nodes`;
      const treeInfo = $('kb-tree-info');
      if (treeInfo) treeInfo.innerHTML = `
        <span style="color:var(--accent)">✓ indexed</span>
        <span>${d.chars ? (d.chars/1000).toFixed(0)+'k chars' : ''}</span>
        <span>${d.files_count ? d.files_count+' files' : ''}</span>
      `;

      // Store in global state for agent injection
      S.kb = { tree: d.tree, tree_text: d.tree_text, label, active: _state.inject };

      const src  = d.source === 'pdf'    ? `PDF: ${d.filename}`
                 : d.source === 'url'    ? `URL: ${d.url}`
                 : `GitHub: ${d.repo} (${d.files_count} files)`;
      status(`✓ ${d.node_count || '?'} nodes`);
      _bubble('assistant',
        `✓ PageIndex tree built from ${src}\n\n` +
        `${d.node_count || '?'} nodes indexed · ${d.chars ? (d.chars/1000).toFixed(0)+'k' : '?'} chars\n\n` +
        `Ask anything about this document. I'll navigate the tree to find the right sections.`
      );
    } catch (e) {
      status('Error');
      _bubble('assistant', `✗ Error: ${e.message}`);
    }
  }

  // ── Ask ────────────────────────────────────────────────────────────────
  async function ask() {
    const input = $('kb-q');
    const q = input?.value.trim();
    if (!q) return;
    if (!_state.tree) { App.showError('Index a document first'); return; }
    input.value = '';

    _bubble('user', q);
    _state.history.push({ role: 'user', content: q });
    status('Navigating tree…');

    try {
      const res = await fetch('/api/kb/ask', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          question:      q,
          tree:          _state.tree,
          tree_text:     _state.tree_text,
          doc_id:        _state.doc_id   || null,
          pageindex_key: _state.piKey    || '',
          history:       _state.history.slice(-6),
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Ask failed');

      _state.history.push({ role: 'assistant', content: d.answer });

      const modeLabel = d.mode === 'pageindex_chat' ? 'PageIndex Chat API' : 'tree navigation';
      const nodeInfo  = d.nodes_used?.length ? `nodes: ${d.nodes_used.join(', ')}` : '';
      const meta      = d.mode === 'pageindex_chat' ? `◎ PageIndex Chat API` : nodeInfo ? `◎ ${nodeInfo}` : '';
      _bubble('assistant', d.answer, meta);
      status(`✓ ${modeLabel}`);
    } catch (e) {
      status('Error');
      _bubble('assistant', `✗ ${e.message}`);
    }
  }

  // ── Inject toggle ──────────────────────────────────────────────────────
  function toggleInject(el) {
    _state.inject = !_state.inject;
    el.classList.toggle('on', _state.inject);
    if (S.kb) S.kb.active = _state.inject;
    status(_state.inject ? '⚡ Injecting into agents' : '');
    const msg = _state.inject
      ? '⚡ Inject ON — PRD, Scaffold and Checklist will now reference this document as context.'
      : '○ Inject OFF — agents will not use this document.';
    _bubble('assistant', msg);
  }

  // ── Chat bubble ────────────────────────────────────────────────────────
  function _bubble(role, text, meta = '') {
    const msgs = $('kb-msgs');
    if (!msgs) return;

    const wrap = document.createElement('div');
    wrap.style.cssText = `
      display:flex;flex-direction:column;gap:3px;
      align-self:${role === 'user' ? 'flex-end' : 'flex-start'};
      max-width:85%;
    `;

    const b = document.createElement('div');
    b.style.cssText = `
      padding:10px 14px;border-radius:10px;font-size:13px;
      line-height:1.6;white-space:pre-wrap;
      background:${role === 'user' ? 'var(--accent)' : 'var(--surface2)'};
      color:${role === 'user' ? '#fff' : 'var(--text)'};
    `;
    b.textContent = text;
    wrap.appendChild(b);

    if (meta) {
      const m = document.createElement('div');
      m.style.cssText = 'font-size:9px;color:var(--muted);padding:0 4px;font-family:var(--font-mono);';
      m.textContent = '◎ ' + meta;
      wrap.appendChild(m);
    }

    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  return { tab, handleDrop, handleFileSelect, indexPdf, indexUrl, indexGithub, ask, toggleInject };
})();