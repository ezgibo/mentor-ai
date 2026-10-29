// Mentor AI frontend — vanilla JS, no build step.
// The backend decides every status change; this file renders the current status and polls
// while a background agent (Web Search, Review) is working.

import { MicStream, PcmPlayer, encodeWav, base64ToArrayBuffer } from './audio.js';

const SAMPLE_REQUEST =
  'Entry-level or new grad software engineer roles (backend or full-stack) in New York City. Hybrid or onsite is fine, remote also OK.';

const SOURCE_LABELS = { reported: 'Reported by candidates', jd_concept: 'From the job description', resume_deep_dive: 'From your resume' };
const RUBRIC = ['accuracy', 'depth', 'structure', 'communication'];

const state = {
  health: null,
  profile: null,
  search: null,
  jobs: [],
  job: null,
  tab: 'search',
  selected: new Set(),
  ratings: {},
  busyAgent: null,       // agent working in the foreground right now
  voiceMode: null,       // per-session override of VOICE_MODE
  session: null,         // the running interview (live or turn)
};

const $ = (selector) => document.querySelector(selector);

// ---------- helpers ----------

async function api(path, { method = 'GET', body, form } = {}) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  if (form) options.body = form;
  const response = await fetch(path, options);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = Array.isArray(data?.detail) ? data.detail.map((d) => d.msg).join(' ') : data?.detail;
    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Tiny markdown: bullet lists, **bold**, *italic*, paragraphs. Everything is escaped first.
function md(text) {
  const html = [];
  let list = [];
  const inline = (line) => esc(line)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, '$1<em>$2</em>');
  const flush = () => {
    if (list.length) html.push(`<ul>${list.map((item) => `<li>${inline(item)}</li>`).join('')}</ul>`);
    list = [];
  };
  for (const raw of String(text ?? '').split('\n')) {
    const line = raw.trim();
    const bullet = line.match(/^([-*•]|\d+\.)\s+(.*)$/);
    if (bullet) list.push(bullet[2]);
    else {
      flush();
      if (line) html.push(`<p>${inline(line)}</p>`);
    }
  }
  flush();
  return html.join('');
}

function showAlert(message, kind = 'error') {
  const alert = $('#alert');
  alert.className = `alert ${kind}`;
  alert.innerHTML = `<span>${esc(message)}</span><button class="close" aria-label="Dismiss">×</button>`;
  alert.querySelector('.close').onclick = hideAlert;
}

function hideAlert() {
  $('#alert').className = 'alert hidden';
}

function handleError(error) {
  showAlert(error.message, error.status === 423 ? 'locked' : 'error');
}

// Run a foreground call with a button spinner; `agent` lights up that agent's chip.
async function busy(button, label, fn, agent = null) {
  const original = button?.innerHTML;
  if (button) {
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span>${esc(label)}`;
  }
  state.busyAgent = agent;
  renderRail();
  hideAlert();
  try {
    return await fn();
  } catch (error) {
    handleError(error);
    return null;
  } finally {
    state.busyAgent = null;
    renderRail();
    if (button && button.isConnected) {
      button.disabled = false;
      button.innerHTML = original;
    }
  }
}

const pollers = {};
function poll(key, fn, ms = 2000) {
  if (pollers[key]) return;
  pollers[key] = setInterval(async () => {
    try {
      if (!(await fn())) stopPoll(key);
    } catch (error) {
      stopPoll(key);
      handleError(error);
    }
  }, ms);
}
function stopPoll(key) {
  clearInterval(pollers[key]);
  delete pollers[key];
}

const agentActive = (name) => state.health?.agents.find((a) => a.name === name)?.active;
const agentInfo = (name) => state.health?.agents.find((a) => a.name === name) || { icon: '', title: name };

function lockNotice(name) {
  if (!state.health || agentActive(name)) return '';
  const a = agentInfo(name);
  if (a.problem) {
    return `<div class="lock-notice">⚠️ <strong>${esc(a.title)}</strong>: ${esc(a.problem)} File: <code>backend/agents/${name}.py</code></div>`;
  }
  return `<div class="lock-notice">🔒 <strong>${esc(a.title)}</strong> is not active yet. Step ${a.step}: paste its prompt from
    <code>agents/${name}_agent.md</code> into <code>backend/agents/${name}.py</code>.</div>`;
}

// ---------- agent rail & resume ----------

function workingAgents() {
  const working = new Set();
  if (state.busyAgent) working.add(state.busyAgent);
  if (state.search?.status === 'searching') working.add('web_search');
  const status = state.job?.interview?.status;
  if (status === 'researching') working.add('web_search');
  if (status === 'composing') working.add('summary');
  if (status === 'reviewing') working.add('review');
  if (state.session) working.add('mock_interview');
  return working;
}

function renderRail() {
  if (!state.health) return;
  const working = workingAgents();
  $('#agent-rail').innerHTML = state.health.agents.map((a) => {
    const status = a.problem ? 'problem' : !a.active ? 'locked' : working.has(a.name) ? 'working' : 'active';
    const label = { problem: 'Fix the paste', locked: `Step ${a.step} · locked`, active: 'Ready', working: 'Working…' }[status];
    return `<div class="chip ${status}" title="${esc(a.title)}: ${label}">
      <span class="chip-icon">${a.icon}</span>
      <span class="chip-text"><strong>${esc(a.title.replace(' Agent', ''))}</strong><small>${label}</small></span>
    </div>`;
  }).join('');
}

async function loadHealth() {
  state.health = await api('/api/health');
  renderRail();
}

function renderResume() {
  const bar = $('#resume-bar');
  const p = state.profile;
  if (p?.has_resume) {
    bar.innerHTML = `<span>📄 Resume: <strong>${esc(p.resume_filename)}</strong></span>
      <a href="/api/profile/resume" target="_blank" rel="noopener">View</a>
      <label class="link">Replace<input type="file" id="resume-file" accept=".pdf,.png,.jpg,.jpeg,.txt" hidden /></label>`;
  } else {
    bar.innerHTML = `<span>Start by adding your resume — Gemini reads the PDF or image directly.</span>
      <label class="button primary">Upload resume<input type="file" id="resume-file" accept=".pdf,.png,.jpg,.jpeg,.txt" hidden /></label>
      <button class="ghost" id="sample-resume">Use sample resume</button>`;
    $('#sample-resume').onclick = (e) => busy(e.currentTarget, 'Loading…', async () => {
      state.profile = await api('/api/profile/sample-resume', { method: 'POST' });
      renderResume();
    });
  }
  $('#resume-file').onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    await busy(null, '', async () => {
      state.profile = await api('/api/profile/resume', { method: 'POST', form });
      renderResume();
    });
  };
}

// ---------- tabs ----------

function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.tab').forEach((b) => {
    b.classList.toggle('active', b.dataset.tab === tab);
    b.setAttribute('aria-selected', b.dataset.tab === tab);
  });
  ['search', 'saved', 'prep'].forEach((name) => $(`#panel-${name}`).classList.toggle('hidden', name !== tab));
  if (tab === 'saved') loadJobs();
  if (tab === 'prep') renderPrep();
}

// ============================================================
// Flow 1 — Find Jobs
// ============================================================

function renderSearch() {
  const s = state.search;
  const messages = s?.messages || [];
  const chat = $('#search-chat');

  chat.innerHTML = lockNotice('summary') + (messages.length ? '' : `
    <div class="bubble summary intro">
      <span class="avatar">🧭</span>
      <div>${md(`Hi! I'm **Mentor**. Tell me what kind of job you want — role, level, and location — and I'll read your resume, confirm what I understood, and send the Web Search Agent to find matching posts from the past 3 months.`)}</div>
    </div>`) + messages.map((m) => m.role === 'summary'
    ? `<div class="bubble summary"><span class="avatar">🧭</span><div>${md(m.content)}</div></div>`
    : `<div class="bubble user ${m.role === 'feedback' ? 'feedback' : ''}"><div>${m.role === 'feedback' ? '<small>Feedback</small>' : ''}${md(m.content)}</div></div>`
  ).join('');

  // Confirm card: the user — not the model — decides when the search starts.
  if (s?.status === 'collecting' && s.understanding) {
    chat.insertAdjacentHTML('beforeend', `
      <div class="confirm-card">
        <div>${understandingHtml(s.understanding)}</div>
        ${lockNotice('web_search')}
        <div class="actions">
          <span class="hint">Not right? Just reply below to correct it.</span>
          <button class="primary" id="confirm-search" ${agentActive('web_search') ? '' : 'disabled'}>Yes, search ✨</button>
        </div>
      </div>`);
    $('#confirm-search').onclick = (e) => busy(e.currentTarget, 'Starting…', async () => {
      state.search = await api(`/api/search/${s.id}/confirm`, { method: 'POST' });
      renderSearch();
    });
  }
  chat.scrollTop = chat.scrollHeight;

  const status = $('#search-status');
  status.innerHTML = '';
  if (s?.status === 'searching') {
    status.innerHTML = `<div class="working"><span class="spinner"></span>🔎 <strong>Web Search Agent</strong> is searching LinkedIn, Handshake, and the public web (past 3 months)… then 🧭 Mentor explains each match. Usually 20–60 seconds.</div>`;
    poll('search', refreshSearch);
  } else if (s?.status === 'failed') {
    status.innerHTML = `<div class="alert error inline">${esc(s.error)} <button class="ghost" id="retry-search">Try again</button></div>`;
    $('#retry-search').onclick = (e) => busy(e.currentTarget, 'Retrying…', async () => {
      state.search = await api(`/api/search/${s.id}/confirm`, { method: 'POST' });
      renderSearch();
    });
  } else if (s?.status === 'saved') {
    status.innerHTML = `<div class="success">✅ Saved! Open <a href="#" id="go-saved">Saved Jobs</a> to start preparing, or start a new search below.</div>`;
    $('#go-saved').onclick = (e) => { e.preventDefault(); setTab('saved'); };
  }

  renderResults();

  const input = $('#search-input');
  const send = $('#search-send');
  input.disabled = send.disabled = s?.status === 'searching';
  input.placeholder = s?.status === 'results_ready'
    ? 'Not quite right? Tell me what to change (e.g. "more backend roles, no startups")…'
    : !s || s.status === 'saved'
      ? 'What kind of job are you looking for? Role, level, location…'
      : 'Reply to Mentor…';
  send.textContent = s?.status === 'results_ready' ? 'Search again' : 'Send';
  $('#new-search').classList.toggle('hidden', !s);
  renderRail();
}

function understandingHtml(u) {
  const row = (label, values) => (values && values.length ? `<div><dt>${label}</dt><dd>${esc([].concat(values).join(', '))}</dd></div>` : '');
  return `<h3>Here's what I'll search for</h3><dl class="understanding">
    ${row('Roles', u.target_roles)}${row('Level', u.levels)}${row('Location', u.locations)}${row('Work mode', u.work_mode)}
    ${row('Must-haves', u.must_haves)}${row('Avoid', u.deal_breakers)}${row('Matching on', u.resume_highlights)}</dl>`;
}

function renderResults() {
  const s = state.search;
  const box = $('#search-results');
  if (!s || !['results_ready', 'saved'].includes(s.status) || !s.results.length) {
    box.innerHTML = '';
    return;
  }
  const canSave = s.status === 'results_ready';
  box.innerHTML = `
    <div class="results-head">
      <h2>Top matches <span class="muted">· round ${s.round}</span></h2>
      ${canSave ? `<button class="primary" id="save-jobs" ${state.selected.size ? '' : 'disabled'}>Save selected (${state.selected.size})</button>` : ''}
    </div>
    <div class="job-grid">${s.results.map((r) => jobCard(r, canSave)).join('')}</div>`;
  box.querySelectorAll('input[data-result]').forEach((cb) => {
    cb.onchange = () => {
      const id = Number(cb.dataset.result);
      cb.checked ? state.selected.add(id) : state.selected.delete(id);
      renderResults();
    };
  });
  const save = $('#save-jobs');
  if (save) save.onclick = (e) => busy(e.currentTarget, 'Saving…', async () => {
    const data = await api(`/api/search/${s.id}/save`, { method: 'POST', body: { result_ids: [...state.selected] } });
    state.search = data.search;
    state.selected.clear();
    renderSearch();
    loadJobs();
  });
}

function jobLink(job) {
  return job.url
    ? `<a href="${esc(job.url)}" target="_blank" rel="noopener">Open post ↗</a>`
    : `<a href="https://www.google.com/search?q=${encodeURIComponent(`${job.title} ${job.company} job`)}" target="_blank" rel="noopener">Search for post ↗</a>`;
}

function jobCard(r, selectable) {
  const saved = r.status === 'saved';
  return `<article class="job-card ${state.selected.has(r.id) ? 'selected' : ''}">
    <header>
      ${selectable ? `<input type="checkbox" data-result="${r.id}" ${state.selected.has(r.id) ? 'checked' : ''} aria-label="Select ${esc(r.title)}" />` : ''}
      <div><h3>${esc(r.title)}</h3><p class="muted">${esc(r.company)} · ${esc(r.location || 'Location unknown')}</p></div>
      ${saved ? '<span class="pill done">Saved</span>' : ''}
    </header>
    <div class="badges"><span class="badge">${esc(r.source || 'other')}</span>${r.fit_score != null ? `<span class="badge fit">Fit ${r.fit_score}</span>` : ''}<span class="badge">${r.posted_date && r.posted_date !== 'unknown' ? `Posted ${esc(r.posted_date)}` : 'Date unknown'}</span>${r.level ? `<span class="badge">${esc(r.level)}</span>` : ''}</div>
    ${r.summary ? `<p>${esc(r.summary)}</p>` : ''}
    ${r.why_relevant ? `<p class="why"><strong>Why it fits you:</strong> ${esc(r.why_relevant)}</p>` : ''}
    <footer>${jobLink(r)}</footer>
  </article>`;
}

async function refreshSearch() {
  if (!state.search) return false;
  state.search = await api(`/api/search/${state.search.id}`);
  renderSearch();
  return state.search.status === 'searching';
}

async function submitSearch(event) {
  event.preventDefault();
  const input = $('#search-input');
  const message = input.value.trim();
  if (!message) return;
  const s = state.search;
  await busy($('#search-send'), s?.status === 'results_ready' ? 'Sending…' : 'Thinking…', async () => {
    if (!s || s.status === 'saved') {
      state.search = await api('/api/search', { method: 'POST', body: { message } });
    } else if (s.status === 'results_ready') {
      state.search = await api(`/api/search/${s.id}/feedback`, { method: 'POST', body: { message } });
      state.selected.clear();
    } else {
      state.search = await api(`/api/search/${s.id}/messages`, { method: 'POST', body: { message } });
    }
    input.value = '';
    renderSearch();
  }, s?.status === 'results_ready' ? 'web_search' : 'summary');
}

// ============================================================
// Saved Jobs
// ============================================================

const STUDY_LABEL = { not_started: 'Study: not started', studying: 'Studying', done: 'Study done' };
const INTERVIEW_LABEL = { not_started: 'Interview: not started', started: 'Interview started', done: 'Interview done' };

async function loadJobs() {
  state.jobs = await api('/api/jobs');
  $('#saved-count').textContent = state.jobs.length ? `(${state.jobs.length})` : '';
  renderSaved();
}

function renderSaved() {
  const list = $('#saved-list');
  if (!state.jobs.length) {
    list.innerHTML = `<div class="empty">No saved jobs yet. Find some in <a href="#" id="go-search">Find Jobs</a>.</div>`;
    $('#go-search').onclick = (e) => { e.preventDefault(); setTab('search'); };
    return;
  }
  list.innerHTML = state.jobs.map((j) => `<article class="job-card">
    <header><div><h3>${esc(j.title)}</h3><p class="muted">${esc(j.company)} · ${esc(j.location || '')}</p></div>
      <button class="icon" data-delete="${j.id}" aria-label="Remove ${esc(j.title)}">×</button></header>
    <div class="badges">
      <span class="pill ${j.study_status}">${STUDY_LABEL[j.study_status]}</span>
      <span class="pill ${j.interview_status}">${INTERVIEW_LABEL[j.interview_status]}</span>
      ${j.has_description ? '' : '<span class="pill warn">Needs job description</span>'}
    </div>
    ${j.why_relevant ? `<p class="why">${esc(j.why_relevant)}</p>` : ''}
    <footer>${jobLink(j)}<button class="primary" data-open="${j.id}">Prepare →</button></footer>
  </article>`).join('');
  list.querySelectorAll('[data-open]').forEach((b) => { b.onclick = () => openJob(Number(b.dataset.open)); });
  list.querySelectorAll('[data-delete]').forEach((b) => {
    b.onclick = async () => {
      if (!confirm('Remove this saved job and its study plan and interviews?')) return;
      await busy(null, '', async () => {
        await api(`/api/jobs/${b.dataset.delete}`, { method: 'DELETE' });
        if (state.job?.id === Number(b.dataset.delete)) state.job = null;
        await loadJobs();
      });
    };
  });
}

async function openJob(id) {
  stopPoll('job');
  state.job = await api(`/api/jobs/${id}`);
  state.ratings = {};
  state.voiceMode = null;
  setTab('prep');
}

// ============================================================
// Flow 2 — Interview Prep (topics → study plan → interview → review)
// ============================================================

const PREP_STEPS = ['researching', 'composing', 'ready'];

async function refreshJob() {
  if (!state.job || state.session) return false;
  state.job = await api(`/api/jobs/${state.job.id}`);
  renderPrep();
  return ['researching', 'composing', 'reviewing'].includes(state.job.interview?.status);
}

function renderPrep() {
  const box = $('#prep');
  const job = state.job;
  if (state.session) return; // never redraw over a running interview
  if (!job) {
    box.innerHTML = `<div class="empty">Pick a job in <a href="#" id="go-saved2">Saved Jobs</a> to start preparing.</div>`;
    $('#go-saved2').onclick = (e) => { e.preventDefault(); setTab('saved'); };
    return;
  }
  const lastMessage = [...(job.messages || [])].reverse().find((m) => m.role === 'summary');
  box.innerHTML = `
    <div class="prep-head">
      <div><h2>${esc(job.title)}</h2><p class="muted">${esc(job.company)} · ${esc(job.location || '')} · ${jobLink(job)}</p></div>
      <div class="badges"><span class="pill ${job.study_status}">${STUDY_LABEL[job.study_status]}</span><span class="pill ${job.interview_status}">${INTERVIEW_LABEL[job.interview_status]}</span></div>
    </div>
    ${lastMessage ? `<div class="bubble summary"><span class="avatar">🧭</span><div>${md(lastMessage.content)}</div></div>` : ''}
    ${descriptionSection(job)}
    <section class="step"><h3><span class="num">1</span> Know the topics</h3>${topicsSection(job)}</section>
    <section class="step"><h3><span class="num">2</span> Mock interview</h3>${interviewSection(job)}</section>
    ${job.interview?.status === 'done' ? `<section class="step"><h3><span class="num">3</span> Review</h3>${reviewSection(job.interview)}</section>` : ''}`;
  bindPrep(job);
  renderRail();
  if (['researching', 'composing', 'reviewing'].includes(job.interview?.status)) poll('job', refreshJob, 2500);
}

function descriptionSection(job) {
  if (!job.has_description) {
    return `<section class="step warn-box">
      <h3>📋 Paste the job description</h3>
      <p>The Web Search Agent couldn't summarize this post (some sites hide it). Every interview step is built from the description, so paste it from the ${jobLink(job)} page.</p>
      <textarea id="jd-input" rows="6" placeholder="Paste the full job description…">${esc(job.job_description || '')}</textarea>
      <div class="actions"><button class="primary" id="jd-save">Save description</button></div>
    </section>`;
  }
  return `<details class="jd"><summary>Job description <span class="muted small">— summary from search; paste the full post for the best interview prep</span></summary><div class="jd-text">${md(job.job_description)}</div>
    <button class="ghost small" id="jd-edit">Edit</button></details>`;
}

function topicsSection(job) {
  const topics = job.topics || [];
  if (!job.has_description) return '<p class="muted">Add the job description first.</p>';
  if (!topics.length) {
    return `${lockNotice('summary')}<p>Mentor reads the job description and your resume and lists what the interview will test.</p>
      <button class="primary" id="load-topics" ${agentActive('summary') ? '' : 'disabled'}>What do I need to know?</button>`;
  }
  if (job.study_status === 'not_started') {
    return `<p>Rate how well you know each topic: <strong>1</strong> never used it · <strong>5</strong> could teach it.</p>
      <div class="topics">${topics.map((t) => `<div class="topic">
        <div><strong>${esc(t.name)}</strong><p class="muted small">${esc(t.why_needed)}</p><p class="small">📄 ${esc(t.resume_evidence)}</p></div>
        <div class="rating" role="radiogroup" aria-label="Rate ${esc(t.name)}">${[1, 2, 3, 4, 5].map((n) =>
          `<button class="${state.ratings[t.id] === n ? 'on' : ''}" data-topic="${t.id}" data-rate="${n}" aria-pressed="${state.ratings[t.id] === n}">${n}</button>`).join('')}</div>
      </div>`).join('')}</div>
      <div class="actions"><span class="hint">${Object.keys(state.ratings).length}/${topics.length} rated</span>
        <button class="primary" id="make-plan" ${Object.keys(state.ratings).length === topics.length ? '' : 'disabled'}>Make my study plan</button></div>`;
  }
  const ordered = [...topics].sort((a, b) => (a.priority === 'study_first' ? 0 : 1) - (b.priority === 'study_first' ? 0 : 1));
  const done = topics.filter((t) => t.status === 'done').length;
  return `<div class="plan">${ordered.map((t) => `<div class="plan-item ${t.status}">
      <label class="check"><input type="checkbox" data-topic-done="${t.id}" ${t.status === 'done' ? 'checked' : ''} ${job.study_status === 'done' ? 'disabled' : ''} /></label>
      <div><div class="plan-title"><strong>${esc(t.name)}</strong>
        <span class="pill ${t.priority === 'study_first' ? 'warn' : 'neutral'}">${t.priority === 'study_first' ? 'Study first' : 'Review later'}</span>
        <span class="muted small">self-rating ${t.self_rating ?? '–'}/5</span></div>
        <div class="small">${md(t.plan)}</div></div>
    </div>`).join('')}</div>
    ${job.study_status === 'studying' ? `${lockNotice('web_search')}<div class="actions"><span class="hint">${done}/${topics.length} topics done</span>
      <button class="primary" id="study-done" ${agentActive('web_search') ? '' : 'disabled'}>I'm done studying →</button></div>` : ''}`;
}

function interviewSection(job) {
  const iv = job.interview;
  if (!iv) return `<p class="muted">Finish studying to unlock the mock interview. When you do, the Web Search Agent looks for questions real candidates were asked at ${esc(job.company)}, and Mentor writes your ${state.health?.question_count ?? 7}-question interview.</p>`;

  if (PREP_STEPS.includes(iv.status) && iv.status !== 'ready') {
    const step = (key, label) => {
      const index = PREP_STEPS.indexOf(key);
      const current = PREP_STEPS.indexOf(iv.status);
      return `<li class="${index < current ? 'done' : index === current ? 'now' : ''}">${index === current ? '<span class="spinner"></span>' : index < current ? '✓' : '○'} ${label}</li>`;
    };
    return `<ol class="progress">${step('researching', '🔎 Web Search Agent: finding questions candidates reported')}${step('composing', '🧭 Mentor: writing your interview')}${step('ready', 'Ready')}</ol>`;
  }
  if (iv.status === 'failed') {
    return `<div class="alert error inline">${esc(iv.error)} <button class="ghost" id="retry-interview">Retry</button></div>`;
  }
  if (iv.status === 'reviewing') {
    return `<div class="working"><span class="spinner"></span>📝 <strong>Review Agent</strong> is grading your answers as a senior ${esc(job.company)} interviewer…</div>`;
  }
  if (iv.status === 'done') {
    return `<p class="muted">Interview finished ${esc((iv.completed_at || '').slice(0, 10))}.</p>
      <button class="ghost" id="retake">Retake with new questions</button>`;
  }

  // ready / in_progress
  const mode = state.voiceMode || iv.voice_mode;
  const answered = iv.questions.filter((q) => q.transcript).length;
  return `${lockNotice('mock_interview')}
    <ol class="question-list">${iv.questions.map((q) => `<li class="${q.transcript ? 'answered' : ''}">
      <span class="badge src-${q.source}">${SOURCE_LABELS[q.source]}</span> ${esc(q.question)}
      ${q.source_url ? `<a href="${esc(q.source_url)}" target="_blank" rel="noopener" class="small">source ↗</a>` : ''}</li>`).join('')}</ol>
    <div class="interview-controls">
      <div class="segmented" role="radiogroup" aria-label="Voice mode">
        <button data-mode="live" class="${mode === 'live' ? 'on' : ''}">🎙️ Live conversation</button>
        <button data-mode="turn" class="${mode === 'turn' ? 'on' : ''}">🔁 Turn by turn</button>
      </div>
      <span class="hint">🎧 Use headphones so the interviewer doesn't hear itself.</span>
      <button class="primary" id="start-interview" ${agentActive('mock_interview') ? '' : 'disabled'}>${iv.status === 'in_progress' ? 'Resume interview' : 'Start interview'}</button>
      ${iv.status === 'in_progress' && answered ? `${lockNotice('review')}<button class="ghost" id="finish-interview" ${agentActive('review') ? '' : 'disabled'}>Finish &amp; review (${answered} answered)</button>` : ''}
    </div>
    <div id="stage"></div>`;
}

function reviewSection(iv) {
  const review = iv.review || {};
  const scored = iv.questions.filter((q) => q.review);
  const average = scored.length ? (scored.reduce((s, q) => s + q.review.score, 0) / scored.length).toFixed(1) : '–';
  return `<div class="review-summary">
      <div class="score-ring big"><strong>${average}</strong><small>/10 avg</small></div>
      <div>${md(iv.summary_message)}
        ${review.prepare_next?.length ? `<h4>Prepare next</h4><ol>${review.prepare_next.map((p) => `<li>${esc(p)}</li>`).join('')}</ol>` : ''}</div>
    </div>
    ${iv.questions.map((q) => {
      const r = q.review;
      if (!r) return '';
      return `<article class="review-card">
        <header><div class="score-ring"><strong>${r.score}</strong></div>
          <div><span class="badge src-${q.source}">${SOURCE_LABELS[q.source]}</span><h4>Q${q.position}. ${esc(q.question)}</h4></div></header>
        <div class="rubric">${RUBRIC.map((k) => `<div class="bar"><span>${k}</span><div class="track"><div style="width:${(r.rubric[k] || 0) * 10}%"></div></div><b>${r.rubric[k] ?? '–'}</b></div>`).join('')}</div>
        <details><summary>Your answer (transcript)</summary><p class="transcript-text">${esc(q.transcript || '(no answer)')}</p></details>
        <div class="feedback-grid">
          <div><h5>👍 Strengths</h5>${md(r.strengths)}</div>
          <div><h5>🛠 Prepare</h5>${md(r.improvements)}</div>
          <div><h5>👀 What a senior interviewer listens for</h5>${md(r.senior_lens)}</div>
        </div>
      </article>`;
    }).join('')}`;
}

function bindPrep(job) {
  const on = (id, handler) => { const el = $(id); if (el) el.onclick = handler; };
  const update = (data) => { state.job = data; renderPrep(); loadJobs(); };

  on('#jd-save', (e) => busy(e.currentTarget, 'Saving…', async () => {
    update(await api(`/api/jobs/${job.id}`, { method: 'PATCH', body: { job_description: $('#jd-input').value } }));
  }));
  on('#jd-edit', () => { state.job = { ...job, has_description: false }; renderPrep(); });
  on('#load-topics', (e) => busy(e.currentTarget, 'Mentor is reading the job…', async () => {
    update(await api(`/api/jobs/${job.id}/topics`, { method: 'POST' }));
  }, 'summary'));
  document.querySelectorAll('[data-rate]').forEach((b) => {
    b.onclick = () => { state.ratings[b.dataset.topic] = Number(b.dataset.rate); renderPrep(); };
  });
  on('#make-plan', (e) => busy(e.currentTarget, 'Mentor is planning…', async () => {
    update(await api(`/api/jobs/${job.id}/ratings`, { method: 'POST', body: { ratings: state.ratings } }));
  }, 'summary'));
  document.querySelectorAll('[data-topic-done]').forEach((cb) => {
    cb.onchange = () => busy(null, '', async () => {
      await api(`/api/topics/${cb.dataset.topicDone}`, { method: 'PATCH', body: { status: cb.checked ? 'done' : 'studying' } });
      state.job = await api(`/api/jobs/${job.id}`);
      renderPrep();
    });
  });
  on('#study-done', (e) => busy(e.currentTarget, 'Starting…', async () => {
    update(await api(`/api/jobs/${job.id}/study-done`, { method: 'POST' }));
  }));
  on('#retry-interview', (e) => busy(e.currentTarget, 'Retrying…', async () => {
    await api(`/api/interviews/${job.interview.id}/retry`, { method: 'POST' });
    update(await api(`/api/jobs/${job.id}`));
  }));
  on('#retake', (e) => busy(e.currentTarget, 'Starting…', async () => {
    update(await api(`/api/jobs/${job.id}/interviews`, { method: 'POST' }));
  }));
  document.querySelectorAll('[data-mode]').forEach((b) => {
    b.onclick = () => { state.voiceMode = b.dataset.mode; renderPrep(); };
  });
  on('#start-interview', () => {
    const mode = state.voiceMode || job.interview.voice_mode;
    (mode === 'turn' ? startTurnInterview : startLiveInterview)(job.interview);
  });
  on('#finish-interview', (e) => finishInterview(job.interview.id, e.currentTarget));
}

async function finishInterview(sessionId, button) {
  await busy(button, 'Sending to review…', async () => {
    await api(`/api/interviews/${sessionId}/finish`, { method: 'POST' });
    state.job = await api(`/api/jobs/${state.job.id}`);
    renderPrep();
    loadJobs();
  });
}

function endSession() {
  const session = state.session;
  if (!session) return;
  session.mic?.stop();
  session.player?.close();
  state.session = null;
}

// ---------- Live interview (Gemini Live API via the backend relay) ----------

function stageHtml(iv, mode) {
  return `<div class="stage">
    <div class="tracker">${iv.questions.map((q) => `<span data-q="${q.position}" class="${q.transcript ? 'answered' : ''}">${q.position}</span>`).join('')}</div>
    <div class="stage-main">
      <div class="interviewer"><div class="orb" id="orb">🎙️</div><div><strong>Senior interviewer · ${esc(state.job.company)}</strong>
        <p class="muted small" id="stage-status">${mode === 'live' ? 'Connecting…' : 'Loading the first question…'}</p></div></div>
      <div class="meter"><div id="mic-level"></div></div>
    </div>
    <div class="live-transcript" id="live-transcript" aria-live="polite"></div>
    <div class="actions" id="stage-actions"></div>
  </div>`;
}

function setStageStatus(text) {
  const el = $('#stage-status');
  if (el) el.textContent = text;
}

function setLevel(peak) {
  const el = $('#mic-level');
  if (el) el.style.width = `${Math.min(100, peak * 140)}%`;
}

function markQuestion(position) {
  document.querySelectorAll('.tracker span').forEach((s) => s.classList.toggle('now', Number(s.dataset.q) === position));
}

// Gemini 2.5 native audio sometimes speaks a tool call into its transcript, e.g.
// "忱call:next_question{number:3}<ctrl46>". Hide it (and half-received pieces of it) from captions.
function cleanCaption(raw) {
  return raw
    .replace(/[^\x00-\x7F]?\s*call:\s*\w+\s*\{[^}]*\}\s*(<ctrl\d+>)?/g, ' ')
    .replace(/<ctrl\d+>/g, '')
    .replace(/[^\x00-\x7F]?\s*call:[^\s]*$/, '')
    .replace(/\s{2,}/g, ' ');
}

function appendTranscript(role, text) {
  const box = $('#live-transcript');
  if (!box) return;
  let last = box.lastElementChild;
  if (!last || last.dataset.role !== role) {
    last = document.createElement('p');
    last.dataset.role = role;
    last.className = role;
    last.innerHTML = `<strong>${role === 'interviewer' ? 'Interviewer' : 'You'}:</strong> <span></span>`;
    box.appendChild(last);
  }
  const span = last.querySelector('span');
  span.dataset.raw = (span.dataset.raw || '') + text;
  span.textContent = cleanCaption(span.dataset.raw);
  box.scrollTop = box.scrollHeight;
}

async function startLiveInterview(iv) {
  $('#stage').innerHTML = stageHtml(iv, 'live');
  $('#start-interview').disabled = true;
  const player = new PcmPlayer(24000);
  await player.resume();
  const mic = new MicStream();
  const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/interviews/${iv.id}`);
  socket.binaryType = 'arraybuffer';
  state.session = { mode: 'live', socket, mic, player, id: iv.id };
  renderRail();

  $('#stage-actions').innerHTML = `<button class="danger" id="end-live">End interview</button>`;
  $('#end-live').onclick = () => {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'end' }));
  };

  let ended = false;
  const orb = () => $('#orb')?.classList.toggle('speaking', player.speaking);
  const orbTimer = setInterval(orb, 200);

  socket.onmessage = async (event) => {
    if (typeof event.data !== 'string') {
      player.play(event.data);
      return;
    }
    const msg = JSON.parse(event.data);
    if (msg.type === 'ready') {
      setStageStatus('Connected — the interviewer is joining. Speak naturally; you can interrupt any time.');
      try {
        await mic.start((pcm) => socket.readyState === WebSocket.OPEN && socket.send(pcm), setLevel);
      } catch {
        showAlert('Microphone access was blocked. Allow the microphone in your browser and try again.');
        socket.close();
      }
    } else if (msg.type === 'question') {
      markQuestion(msg.position);
      setStageStatus(`Question ${msg.position} of ${msg.total}`);
    } else if (msg.type === 'transcript') {
      appendTranscript(msg.role, msg.text);
    } else if (msg.type === 'interrupted') {
      player.clear();
    } else if (msg.type === 'ending') {
      setStageStatus('Wrapping up…');
      await player.idle();
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'end' }));
    } else if (msg.type === 'reconnecting') {
      player.clear();
      setStageStatus(msg.message);
    } else if (msg.type === 'error') {
      showAlert(`${msg.message} — you can switch to "Turn by turn" and try again.`);
    } else if (msg.type === 'done') {
      ended = true;
      setStageStatus('Interview ended.');
    }
  };

  socket.onclose = async (event) => {
    clearInterval(orbTimer);
    if (!ended && !event.wasClean) {
      showAlert('The connection to the interviewer closed unexpectedly. Your answers so far are saved — press Resume interview, or switch to Turn by turn.');
    }
    endSession();
    state.job = await api(`/api/jobs/${state.job.id}`);
    const answered = state.job.interview?.questions.some((q) => q.transcript);
    if (answered && agentActive('review') && state.job.interview.status === 'in_progress') {
      await finishInterview(iv.id, null);
    } else {
      renderPrep();
    }
  };
}

// ---------- Turn-by-turn interview (TTS question → recorded answer → transcript) ----------

async function startTurnInterview(iv) {
  $('#stage').innerHTML = stageHtml(iv, 'turn');
  $('#start-interview').disabled = true;
  const player = new PcmPlayer(24000);
  await player.resume();
  state.session = { mode: 'turn', player, id: iv.id, mic: null };
  renderRail();
  const first = iv.questions.find((q) => !q.transcript) || iv.questions[0];
  await askTurn(iv, first.position);
}

async function askTurn(iv, position) {
  const session = state.session;
  if (!session) return;
  markQuestion(position);
  setStageStatus(`Question ${position} of ${iv.questions.length} — the interviewer is speaking…`);
  $('#stage-actions').innerHTML = '';
  const data = await busy(null, '', () => api(`/api/interviews/${iv.id}/turn/${position}`), 'mock_interview');
  if (!data || !state.session) return;
  appendTranscript('interviewer', `${data.spoken_text}\n`);
  if (data.audio_b64) {
    if (session.player.sampleRate !== data.sample_rate) {
      session.player.close();
      session.player = new PcmPlayer(data.sample_rate);
      await session.player.resume();
    }
    session.player.play(base64ToArrayBuffer(data.audio_b64));
    await session.player.idle();
  } else if (data.audio_error) {
    showAlert(`Voice unavailable (${data.audio_error}). Read the question and answer out loud.`, 'locked');
  }
  setStageStatus(`Question ${position} of ${iv.questions.length} — your turn.`);
  $('#stage-actions').innerHTML = `<button class="primary" id="record">⏺ Record answer</button>
    <button class="ghost" id="end-turn">End interview</button>`;
  $('#end-turn').onclick = () => stopTurnInterview(iv);
  $('#record').onclick = () => recordTurn(iv, position);
}

async function recordTurn(iv, position) {
  const session = state.session;
  const chunks = [];
  session.mic = new MicStream();
  try {
    await session.mic.start((pcm) => chunks.push(pcm), setLevel);
  } catch {
    showAlert('Microphone access was blocked. Allow the microphone in your browser and try again.');
    return;
  }
  setStageStatus('Recording… press Stop when you finish your answer.');
  $('#stage-actions').innerHTML = `<button class="danger" id="stop">⏹ Stop &amp; submit</button>`;
  $('#stop').onclick = async (e) => {
    session.mic.stop();
    session.mic = null;
    setLevel(0);
    const form = new FormData();
    form.append('audio', encodeWav(chunks), 'answer.wav');
    const result = await busy(e.currentTarget, 'Transcribing…', () =>
      api(`/api/interviews/${iv.id}/turn/${position}/answer`, { method: 'POST', form }), 'mock_interview');
    if (!result) {
      $('#stage-actions').innerHTML = `<button class="primary" id="record">⏺ Record again</button>`;
      $('#record').onclick = () => recordTurn(iv, position);
      return;
    }
    appendTranscript('candidate', `${result.transcript || '(no speech detected)'}\n`);
    document.querySelector(`.tracker span[data-q="${position}"]`)?.classList.add('answered');
    if (position < iv.questions.length) await askTurn(iv, position + 1);
    else await stopTurnInterview(iv);
  };
}

async function stopTurnInterview(iv) {
  endSession();
  state.job = await api(`/api/jobs/${state.job.id}`);
  const answered = state.job.interview?.questions.some((q) => q.transcript);
  if (answered && agentActive('review')) await finishInterview(iv.id, null);
  else renderPrep();
}

// ============================================================
// Boot
// ============================================================

async function boot() {
  document.querySelectorAll('.tab').forEach((b) => { b.onclick = () => setTab(b.dataset.tab); });
  $('#search-form').onsubmit = submitSearch;
  $('#search-input').onkeydown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submitSearch(e);
  };
  $('#sample-request').onclick = () => { $('#search-input').value = SAMPLE_REQUEST; $('#search-input').focus(); };
  $('#new-search').onclick = () => {
    stopPoll('search');
    state.search = null;
    state.selected.clear();
    renderSearch();
  };

  try {
    await loadHealth();
    [state.profile, state.search] = await Promise.all([api('/api/profile'), api('/api/search/latest')]);
  } catch (error) {
    handleError(error);
  }
  renderResume();
  renderSearch();
  loadJobs();

  // Agents unlock as prompts are pasted: re-check every few seconds.
  setInterval(async () => {
    const before = JSON.stringify(state.health?.agents);
    try {
      await loadHealth();
    } catch {
      return;
    }
    if (JSON.stringify(state.health.agents) !== before) {
      if (!state.session) renderSearch();
      if (state.tab === 'prep') renderPrep();
    }
  }, 4000);
}

boot();
