/* Learner app: a short home page, the interview, and the results. Everything is a function of the latest view from Viva.api. */
(() => {
  'use strict';
  const V = window.Viva, api = V.api, D = V.data;
  const { $, $$, esc, icon } = V;
  const params = new URLSearchParams(location.search);
  const presenter = params.get('presenter') === '1';
  const root = $('#app');

  let state = null, ivCtl = null, poll = 0, busy = false;

  // ---------- helpers ----------
  const arrow = `<span class="arrow">${icon('arrow', 16)}</span>`;
  const opts = () => ({ presenter });
  function fail(e) {
    const stale = e && e.status === 409 && /already changed/i.test(e.message);
    V.toast((e && e.message) || 'Something went wrong.', { kind: 'error', action: stale ? { label: 'Reload', run: () => refresh().catch(fail) } : undefined });
  }
  async function action(fn) {
    if (busy) return;
    busy = true;
    try { await fn(); } catch (e) { fail(e); } finally { busy = false; }
  }
  const persist = id => {
    try { localStorage.setItem('viva-session', id); } catch { /* storage may be blocked */ }
    if (location.hash.slice(1) !== id) history.replaceState(null, '', `${location.pathname}${location.search}#${id}`);
  };
  const forget = () => {
    try { localStorage.removeItem('viva-session'); } catch { /* ignore */ }
    history.replaceState(null, '', location.pathname + location.search);
  };
  const hashId = () => { try { return decodeURIComponent(location.hash.slice(1)); } catch { return ''; } };

  // The GitHub link can carry the pull request. Anything missing falls back to the sample PR.
  const prParams = () => ({ repo: params.get('repo'), number: params.get('pr'), title: params.get('title'), author: params.get('author'), branch: params.get('branch'), sha: params.get('sha') });
  function prForDisplay(pr) {
    const p = prParams(), out = { ...pr };
    ['repo', 'title', 'author', 'branch', 'sha'].forEach(k => { if (p[k]) out[k] = p[k].slice(0, 120); });
    if (Number(p.number) > 0) out.number = Number(p.number);
    return out;
  }

  // ---------- rail: two steps ----------
  const RAIL = ['Interview', 'Results'];
  function paintRail() {
    const el = $('#rail');
    if (!state) { el.hidden = true; return; }
    const idx = state.stage === 'results' ? 1 : 0;
    if (!el.dataset.ready) {
      el.innerHTML = `<ol class="rail-list" style="--n:${RAIL.length}">${RAIL.map(l => `<li class="rail-step">${l}</li>`).join('')}<span class="rail-track"></span><span class="rail-fill"></span><span class="rail-dot"><i></i></span></ol>`;
      el.dataset.ready = '1';
    }
    el.hidden = false;
    $('.rail-list', el).style.setProperty('--p', idx);
    $$('.rail-step', el).forEach((n, i) => { n.dataset.state = i < idx ? 'done' : i === idx ? 'current' : 'todo'; });
    el.setAttribute('aria-label', `Progress: ${RAIL[idx]}`);
  }

  // ---------- stage swap ----------
  function stopStage() {
    if (ivCtl) { ivCtl.destroy(); ivCtl = null; }
    clearInterval(poll); poll = 0;
    V.media.recBar(false);
  }
  async function swap(render) {
    stopStage();
    if (!V.reduced() && root.firstElementChild) {
      await V.settle(root.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-10px)' }], { duration: 200, easing: V.EASE.out, fill: 'forwards' }), 200);
    }
    root.getAnimations().forEach(a => a.cancel());
    paintRail();
    render();
    scrollTo({ top: 0, left: 0, behavior: 'instant' });
    V.revealMask(root);
    V.enter($$('[data-enter]', root), { y: 18, step: 70, dur: 900, delay: 120 });
    V.observe(root);
    V.seg(root);
  }
  function accept(view) { state = view; persist(view.id); return swap(render); }
  async function refresh() {
    if (!state) return;
    await accept(await api.session(state.id, opts()));
  }

  async function leave() {
    if (!await V.confirmDialog({ title: 'Leave this interview?', body: 'Your recordings are deleted from this device and you return to the start.', confirm: 'Leave', danger: true })) return;
    const r = await api.leave(state.id);
    if (r.failed) V.toast('Some recordings could not be deleted.', { kind: 'error' });
    stopStage(); forget(); state = null;
    await swap(render);
  }
  async function removeAll() {
    if (!await V.confirmDialog({ title: 'Delete this session?', body: 'This permanently deletes the answers and the recordings from this device.', confirm: 'Delete', danger: true })) return;
    const r = await api.remove(state.id);
    if (r.failed) V.toast('Some recordings could not be deleted.', { kind: 'error' });
    stopStage(); forget(); state = null;
    await swap(render);
  }

  // ---------- home ----------
  function renderHome() {
    document.title = 'Viva | Explain your pull request';
    const pr = prForDisplay(D.pr);
    root.innerHTML = `
      <section class="hero">
        <div class="hero-copy">
          <h1 class="display mask">${V.mask(['<span class="dim">Your PR is in.</span>', 'Now explain it.'])}</h1>
          <p class="lede" data-enter>Answer a few short questions about your own code. Voice or text, camera on.</p>
          <div class="hero-cta" data-enter>
            <button class="btn btn-primary" id="start" type="button" data-magnetic>Start interview ${arrow}</button>
          </div>
          <ul class="facts" data-enter><li>About 3 minutes</li><li>Your code is not shown</li><li>A senior reviews the recording</li></ul>
        </div>
        <aside class="prcard" data-enter aria-label="Pull request">
          <div class="pr-top"><span class="mono">${esc(pr.repo)}</span><span class="mono">#${Number(pr.number)}</span></div>
          <h2 class="pr-title">${esc(pr.title)}</h2>
          <p class="pr-meta"><span class="mono">${esc(pr.branch)}</span> <span class="pr-to">${icon('arrow', 14)}</span> <span class="mono">${esc(pr.base)}</span> by ${esc(pr.author)}</p>
          <ul class="pr-files">${pr.files.map(f => `<li><span class="mono">${esc(f.name)}</span><span class="diffstat mono num"><b class="add">+${Number(f.add)}</b><b class="del">-${Number(f.del)}</b></span></li>`).join('')}</ul>
          <div class="pr-check"><span class="pr-pulse" aria-hidden="true"></span><p><b>Viva check</b> Explain your change to finish this pull request.</p></div>
        </aside>
      </section>`;
    $('#start').onclick = () => action(async () => accept(await api.start({ pr: prParams() })));
  }

  // ---------- interview ----------
  function renderInterview() {
    document.title = 'Interview | Viva';
    root.innerHTML = '<section id="iv"></section>';
    ivCtl = V.interview.mount($('#iv', root), {
      api, sid: state.id, view: state, presenter, fail,
      onView: v => { state = v; },
      onFinish: v => accept(v),
      onLeave: () => action(leave)
    });
  }

  // ---------- results ----------
  const sessionBar = () => `<div class="session-bar">
    <button class="btn btn-ghost btn-sm" id="restart" type="button">Start over</button>
    <button class="btn btn-danger btn-sm" id="delete" type="button">${icon('trash', 15)} Delete my data</button>
    ${presenter && state.reviewer_link ? `<a class="btn btn-ghost btn-sm" target="_blank" rel="noopener" href="${esc(state.reviewer_link)}">Presenter: open reviewer view ${icon('external', 15)}</a>` : ''}
    <p class="resume">Private resume link: <code>${esc(location.origin + location.pathname + location.hash)}</code>. Treat it as a password.</p></div>`;
  function wireSessionBar() {
    $('#restart').onclick = () => action(leave);
    $('#delete').onclick = () => action(removeAll);
  }

  function renderResults() {
    document.title = 'Results | Viva';
    root.innerHTML = V.results.html(state) + sessionBar();
    V.results.mount(root, state);
    wireSessionBar();
    startPolling();
  }

  // Wait for the senior: refresh on focus and on a light poll (works with any backend).
  function startPolling() {
    clearInterval(poll);
    poll = setInterval(check, 2000);
  }
  async function check() {
    if (!state || state.stage !== 'results' || document.hidden) return;
    try {
      const v = await api.session(state.id, opts());
      if (v.stage !== 'results' || v.attempt !== state.attempt) return;
      const reviewChanged = JSON.stringify(v.review) !== JSON.stringify(state.review), logChanged = v.access_log.length !== state.access_log.length;
      const pointsChanged = v.scoring.status !== state.scoring.status;
      if (!reviewChanged && !logChanged && !pointsChanged) return;
      const was = state;
      state = v;
      const swapCard = (sel, html) => { const old = $(sel, root); if (!old) return null; old.outerHTML = html; const el = $(sel, root); V.enter(el, { y: 16, dur: 900 }); return el; };
      if (reviewChanged) {
        const el = swapCard('#review-card', V.results.reviewHtml(v));
        if (el) el.scrollIntoView({ block: 'center', behavior: V.reduced() ? 'auto' : 'smooth' });
        $('.session-bar', root).outerHTML = sessionBar();
        wireSessionBar();
      }
      if (pointsChanged && swapCard('#points-card', V.results.pointsHtml(v))) V.results.mountPoints(root, v);
      if (logChanged) swapCard('#log-card', V.results.logHtml(v));
      if (v.scoring.status === 'earned' && was.scoring.status !== 'earned') {
        V.toast(`A senior confirmed your work. +${v.scoring.points} points added to your portfolio.`, { action: { label: 'View portfolio', run: () => { location.href = `portfolio.html${presenter ? '?presenter=1' : ''}`; } } });
        V.pulse($('.avatar'));
      } else if (reviewChanged) V.toast('A senior reviewer left a decision.');
    } catch { /* keep the current view if a poll fails */ }
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
  addEventListener('focus', check);

  // both "try again" buttons (under the headline and in the card) start the second attempt
  root.addEventListener('click', e => {
    if (e.target.closest('[data-retake]')) action(async () => accept(await api.retake(state.id, { version: state.version }, opts())));
  });

  // ---------- router ----------
  function render() {
    stopStage();
    document.body.dataset.stage = state ? state.stage : 'home';
    if (!state) { $('#rail').hidden = true; renderHome(); return; }
    (state.stage === 'results' ? renderResults : renderInterview)();
  }

  // ---------- presenter drawer (?presenter=1) ----------
  // The retake asks different questions, so the stand-in answers follow the attempt on screen.
  const attemptNo = () => Math.min((state && state.attempt) || 1, D.sets.length);
  const answers = () => D.sets[attemptNo() - 1].answers;
  function script() {
    const A = answers();
    return [
      ['Specific answer, question 1', A.specific.implementation], ['Specific answer, question 2', A.specific.rationale], ['Specific answer, follow-up', A.specific.probe],
      ['Generic answer, question 1', A.generic.implementation], ['Generic answer, question 2', A.generic.rationale], ['Generic answer, follow-up', A.generic.probe]
    ];
  }
  function fillOpenQuestion(profile) {
    const turn = ivCtl && ivCtl.turn;
    if (!turn) { V.toast('Open a question first.'); return; }
    const body = answers()[profile][turn.key.startsWith('probe') ? 'probe' : turn.key];
    if (!ivCtl.fill(body)) V.toast('Wait for the answer box to open.');
  }
  function mountPresenter() {
    const end = $('.top-end');
    end.insertAdjacentHTML('afterbegin', `<button class="pres-toggle" type="button" aria-expanded="false">Presenter ${icon('chevron', 14)}</button>`);
    end.insertAdjacentHTML('beforeend', '<div class="pres-panel" hidden></div>');
    const toggle = $('.pres-toggle', end), panel = $('.pres-panel', end);
    const paint = () => {
      const link = state && state.reviewer_link, lines = script();
      panel.innerHTML = `
        <h3>Windows</h3>
        <div class="pres-row"><span>Reviewer view</span>${link ? `<a class="btn btn-ghost btn-sm" href="${esc(link)}" target="_blank" rel="noopener">Open ${icon('external', 14)}</a>` : '<span class="muted small">Appears when a senior review is requested</span>'}</div>
        <h3>Interview</h3>
        <div class="pres-row"><label class="check"><input type="checkbox" id="pm-cam" ${api.sim.cameraRequired() ? 'checked' : ''}><span>Camera required</span></label></div>
        <p class="muted small pres-help">Untick only if the camera hardware fails. The interview then runs on text. Applies to the next interview.</p>
        <div class="pres-row"><span>Voice answers become</span>
          <div class="seg pres-seg" data-seg role="radiogroup" aria-label="Voice answers become"><label><input type="radio" name="pm-voice" value="specific" ${api.sim.voice() === 'specific' ? 'checked' : ''}><span>Specific</span></label><label><input type="radio" name="pm-voice" value="generic" ${api.sim.voice() === 'generic' ? 'checked' : ''}><span>Generic</span></label><i class="seg-thumb"></i></div></div>
        <div class="pres-row"><span>Fill the open question</span><span class="pres-btns"><button class="btn btn-ghost btn-sm" id="pm-fill-specific" type="button">Specific</button><button class="btn btn-ghost btn-sm" id="pm-fill-generic" type="button">Generic</button></span></div>
        <div class="pres-row"><span>Clear all local demo data</span><button class="btn btn-danger btn-sm" id="pm-reset" type="button">Reset</button></div>
        <h3>Script, attempt ${attemptNo()}</h3>
        ${lines.map(([t, x], i) => `<div class="pres-snip"><b>${esc(t)}</b><button class="btn-icon" data-copy="${i}" type="button" aria-label="Copy: ${esc(t)}">${icon('copy', 15)}</button><p>${esc(x)}</p></div>`).join('')}`;
      V.seg(panel);
      $('#pm-cam', panel).onchange = e => { api.sim.setCameraRequired(e.target.checked); V.toast(e.target.checked ? 'The camera is required.' : 'The camera is optional for the next interview.'); };
      $$('input[name=pm-voice]', panel).forEach(r => { r.onchange = () => { api.sim.setVoice(r.value); V.toast(`Spoken answers will read as ${r.value}.`); }; });
      $('#pm-fill-specific', panel).onclick = () => fillOpenQuestion('specific');
      $('#pm-fill-generic', panel).onclick = () => fillOpenQuestion('generic');
      $('#pm-reset', panel).onclick = async () => {
        if (!await V.confirmDialog({ title: 'Clear all local demo data?', body: 'This removes every session and recording stored by the simulator on this device.', confirm: 'Clear everything', danger: true })) return;
        await api.sim.reset();
        stopStage(); forget(); state = null;
        await swap(render);
        V.toast('Local demo data cleared.');
      };
      $$('[data-copy]', panel).forEach(b => { b.onclick = () => V.copy(lines[+b.dataset.copy][1]).then(ok => V.toast(ok ? 'Copied.' : 'Copy failed.')); });
    };
    toggle.onclick = () => {
      const open = panel.hidden;
      if (open) paint();
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      if (open && !V.reduced()) panel.animate([{ opacity: 0, transform: 'translateY(10px) scale(.98)' }, { opacity: 1, transform: 'none' }], { duration: V.SPRING.snap.duration, easing: V.SPRING.snap.easing });
    };
  }

  // ---------- boot ----------
  async function boot() {
    V.boot();
    if (presenter) mountPresenter();
    const saved = hashId() || (() => { try { return localStorage.getItem('viva-session'); } catch { return null; } })();
    if (saved) {
      try { state = await api.session(saved, opts()); persist(state.id); } catch (e) {
        state = null;
        if (e.status === 404) forget(); // an unknown id: drop it. Any other failure keeps the saved pointer.
        else fail(e);
      }
    }
    paintRail();
    render();
    V.revealMask(root);
    V.enter($$('[data-enter]', root), { y: 18, step: 70, dur: 900, delay: 120 });
    V.observe(root);
    V.seg(root);
  }
  addEventListener('hashchange', () => {
    const id = hashId();
    if (id && (!state || state.id !== id)) action(async () => accept(await api.session(id, opts())));
  });
  boot();
})();
