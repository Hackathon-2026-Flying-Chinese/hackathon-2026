/* Learner app: the check page a GitHub check links to, the interview, and the results.
   Everything is a function of the latest view from Viva.api. */
(() => {
  'use strict';
  const V = window.Viva, api = V.api, D = V.data;
  const { $, $$, esc, icon } = V;
  const params = new URLSearchParams(location.search);
  const presenter = params.get('presenter') === '1';
  const root = $('#app');

  let state = null, home = null, ivCtl = null, poll = 0, busy = false;

  // ---------- helpers ----------
  const arrow = `<span class="arrow">${icon('arrow', 14)}</span>`;
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

  // ---------- header: breadcrumb and the three-step rail ----------
  const RAIL = ['Check', 'Interview', 'Results'];
  function paintHeader() {
    const pr = state ? state.pr : home ? home.pr : D.pr, repo = String(pr.repo).split('/').pop();
    $('#crumb').innerHTML = `<span>${esc(repo)}</span><span class="sep" aria-hidden="true">/</span><b>#${Number(pr.number)}</b>`;
    const el = $('#rail'), idx = !state ? 0 : state.stage === 'results' ? 2 : 1;
    if (!el.dataset.ready) {
      el.innerHTML = `<ol class="rail-list" style="--n:${RAIL.length}">${RAIL.map((l, i) => `<li class="rail-step"><b>${i + 1}</b>${l}</li>`).join('')}<span class="rail-track"></span><span class="rail-fill"></span></ol>`;
      el.dataset.ready = '1';
    }
    el.hidden = false;
    $('.rail-list', el).style.setProperty('--p', idx);
    $$('.rail-step', el).forEach((n, i) => {
      n.dataset.state = i < idx ? 'done' : i === idx ? 'current' : 'todo';
      $('b', n).innerHTML = i < idx ? icon('check', 10) : String(i + 1);
    });
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
      await V.settle(root.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-6px)' }], { duration: 160, easing: V.EASE.out, fill: 'forwards' }), 160);
    }
    root.getAnimations().forEach(a => a.cancel());
    render();
    scrollTo({ top: 0, left: 0, behavior: 'instant' });
    V.enter($$('[data-enter]', root), { y: 8, step: 50, dur: 480, delay: 40 });
    V.observe(root);
    V.seg(root);
  }
  function accept(view) { state = view; persist(view.id); return swap(render); }
  async function refresh() {
    if (!state) return;
    await accept(await api.session(state.id, opts()));
  }
  async function goHome() {
    stopStage(); forget(); state = null;
    home = await api.check({ pr: prParams() });
    await swap(render);
  }

  async function leave() {
    if (!await V.confirmDialog({ title: 'Leave this interview?', body: 'Your recordings are deleted from this device and you return to the check.', confirm: 'Leave', danger: true })) return;
    const r = await api.leave(state.id);
    if (r.failed) V.toast('Some recordings could not be deleted.', { kind: 'error' });
    await goHome();
  }
  async function removeAll() {
    if (!await V.confirmDialog({ title: 'Delete this session?', body: 'This permanently deletes the answers and the recordings from this device.', confirm: 'Delete', danger: true })) return;
    const r = await api.remove(state.id);
    if (r.failed) V.toast('Some recordings could not be deleted.', { kind: 'error' });
    await goHome();
  }

  // ---------- check page: what the GitHub check links to. Four steps and one button. ----------
  function renderHome() {
    document.title = 'Decision check | Viva';
    const sc = home.scoring;
    const steps = [
      ['talk', 'Interview', 'Two questions, about 3 minutes. Speak or type.'],
      ['peek', 'Assessment', 'Reads your words only.'],
      ['sage', 'Senior review', `${D.reviewer.name} confirms it is your own work.`],
      ['yay', 'Check passes', `+${Number(sc.s)} points go to your portfolio.`]
    ];
    root.innerHTML = `
      <section class="home" aria-labelledby="home-title">
        <header class="home-head">
          <h1 class="home-title" id="home-title" data-enter>Decision <span class="sq">check<svg viewBox="0 0 200 20" preserveAspectRatio="none" aria-hidden="true"><path pathLength="1" d="M3 12Q13 3 23 12T43 12T63 12T83 12T103 12T123 12T143 12T163 12T183 12T197 10"/></svg></span></h1>
          <p class="home-sub" data-enter>Explain this change in your own words before it merges. It takes about 3 minutes.</p>
        </header>
        <ol class="steps" aria-label="How the check works">
          ${steps.map(([m, t, p], i) => `<li class="step" data-step="${i + 1}"><div class="step-art">${V.mascot(m)}</div><div><span class="step-n">${i + 1}</span><h2>${t}</h2><p>${esc(p)}</p></div>${i < steps.length - 1 ? `<span class="step-to" aria-hidden="true">${icon('arrow', 14)}</span>` : ''}</li>`).join('')}
        </ol>
        <div class="home-cta"><button class="btn btn-primary btn-xl" id="start" type="button">Start interview <kbd aria-hidden="true">↵</kbd><span class="arrow">${icon('arrow', 22)}</span></button></div>
      </section>`;
    const btn = $('#start');
    btn.onclick = () => action(async () => {
      const lift = await V.portal(btn);
      try { await accept(await api.start({ pr: prParams() })); } finally { lift(); }
    });
    if (V.reduced()) return;
    // the cards drop in one by one and land on their tilt, the characters pop, the squiggle draws, the button nudges once
    $$('.step', root).forEach((li, i) => {
      const tilt = parseFloat(getComputedStyle(li).getPropertyValue('--tilt')) || 0;
      li.animate([{ opacity: 0, transform: `translateY(48px) rotate(${tilt - 7}deg) scale(.9)` }, { opacity: 1, transform: `rotate(${tilt}deg)` }], { duration: V.SPRING.bounce.duration, delay: 120 + i * 90, easing: V.SPRING.bounce.easing, fill: 'backwards' });
      $('.mascot', li).animate([{ transform: 'scale(.3) rotate(-18deg)' }, { transform: 'none' }], { duration: V.SPRING.bounce.duration, delay: 320 + i * 90, easing: V.SPRING.bounce.easing, fill: 'backwards' });
    });
    $('.sq path', root).animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: 700, delay: 450, easing: V.EASE.io, fill: 'backwards' });
    btn.animate([{ opacity: 0, transform: 'translateY(24px) scale(.94)' }, { opacity: 1, transform: 'none' }], { duration: V.SPRING.bounce.duration, delay: 560, easing: V.SPRING.bounce.easing, fill: 'backwards' });
    setTimeout(() => { if (btn.isConnected && !btn.matches(':hover')) btn.animate([{ transform: 'rotate(0)' }, { transform: 'rotate(-2.5deg)' }, { transform: 'rotate(2deg)' }, { transform: 'rotate(-1deg)' }, { transform: 'rotate(0)' }], { duration: 620, easing: V.EASE.io }); }, 1700);
  }
  // Enter starts the interview from the check page (the key shown on the button)
  document.addEventListener('keydown', e => {
    if (e.key !== 'Enter' || state || e.metaKey || e.ctrlKey || e.altKey || e.target.closest('input, textarea, button, a, [contenteditable]')) return;
    const b = $('#start');
    if (b) { e.preventDefault(); b.click(); }
  });

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
  // the end of the page: start over, delete, or keep the private link to come back
  const sessionHtml = () => `<section class="card session" id="session-card" data-reveal>
    <div class="session-copy">
      <h2><span class="bub" data-tone="lilac">${icon('lock', 14)}</span>This session</h2>
      <p class="resume">Private resume link. Treat it as a password.</p>
      <div class="resume-row"><code>${esc(location.origin + location.pathname + location.hash)}</code><button class="btn btn-secondary btn-sm" id="copy-link" type="button">${icon('copy', 14)}Copy</button></div>
    </div>
    <div class="btns">
      ${presenter && state.reviewer_link ? `<a class="btn btn-secondary btn-lg" target="_blank" rel="noopener" href="${esc(state.reviewer_link)}">Reviewer view (presenter) ${icon('external', 14)}</a>` : ''}
      <button class="btn btn-danger btn-lg" id="delete" type="button">${icon('trash', 16)}Delete my data</button>
      <button class="btn btn-primary btn-lg" id="restart" type="button">${icon('refresh', 16)}Start over</button>
    </div>
  </section>`;
  function wireSession() {
    $('#restart').onclick = () => action(leave);
    $('#delete').onclick = () => action(removeAll);
    $('#copy-link').onclick = () => V.copy(location.origin + location.pathname + location.hash).then(ok => V.toast(ok ? 'Link copied.' : 'Copy failed.'));
  }

  function renderResults() {
    document.title = 'Results | Viva';
    root.innerHTML = V.results.html(state);
    root.insertAdjacentHTML('beforeend', sessionHtml());
    V.results.mount(root, state);
    wireSession();
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
      const swapCard = (sel, html) => { const old = $(sel, root); if (!old) return null; const open = old.open; old.outerHTML = html; const el = $(sel, root); if (open) el.open = true; V.enter(el, { y: 6, dur: 420 }); return el; };
      if (reviewChanged || pointsChanged) {
        V.results.playFlow(root, v);
        const b = $('#status-badge', root);
        if (b) b.outerHTML = V.results.badge(V.results.status(v));
        swapCard('#gh-card', V.results.ghHtml(v));
      }
      if (reviewChanged) swapCard('#review-card', V.results.reviewHtml(v));
      if (pointsChanged && swapCard('#points-card', V.results.pointsHtml(v))) V.results.mountPoints(root, v);
      if (logChanged) swapCard('#log-card', V.results.logHtml(v));
      if (v.scoring.status === 'earned' && was.scoring.status !== 'earned') {
        V.confetti($('#status-badge', root));
        V.toast(`${D.reviewer.name} confirmed your work. +${v.scoring.points} points added to your portfolio.`, { action: { label: 'View portfolio', run: () => { location.href = `portfolio.html${presenter ? '?presenter=1' : ''}`; } } });
        V.pulse($('.avatar'));
      } else if (reviewChanged) V.toast(`${D.reviewer.name} left a decision.`);
    } catch { /* keep the current view if a poll fails */ }
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
  addEventListener('focus', check);

  // both "try again" buttons (in the header and in the card) start the second attempt
  root.addEventListener('click', e => {
    if (e.target.closest('[data-retake]')) action(async () => accept(await api.retake(state.id, { version: state.version }, opts())));
  });

  // ---------- router ----------
  function render() {
    stopStage();
    document.body.dataset.stage = state ? state.stage : 'home';
    paintHeader();
    if (!state) { renderHome(); return; }
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
    end.insertAdjacentHTML('afterbegin', `<button class="pres-toggle" type="button" aria-expanded="false">Presenter ${icon('chevron', 12)}</button>`);
    end.insertAdjacentHTML('beforeend', '<div class="pres-panel" hidden></div>');
    const toggle = $('.pres-toggle', end), panel = $('.pres-panel', end);
    const paint = () => {
      const link = state && state.reviewer_link, lines = script();
      panel.innerHTML = `
        <h3>Windows</h3>
        <div class="pres-row"><span>Reviewer view</span>${link ? `<a class="btn btn-secondary btn-sm" href="${esc(link)}" target="_blank" rel="noopener">Open ${icon('external', 13)}</a>` : '<span class="muted small">Appears when a senior review is requested</span>'}</div>
        <h3>Interview</h3>
        <div class="pres-row"><label class="check"><input type="checkbox" id="pm-cam" ${api.sim.cameraRequired() ? 'checked' : ''}><span>Camera required</span></label></div>
        <p class="muted pres-help">Untick only if the camera hardware fails. The interview then runs on text. Applies to the next interview.</p>
        <div class="pres-row"><span>Voice answers become</span>
          <div class="seg pres-seg" data-seg role="radiogroup" aria-label="Voice answers become"><label><input type="radio" name="pm-voice" value="specific" ${api.sim.voice() === 'specific' ? 'checked' : ''}><span>Specific</span></label><label><input type="radio" name="pm-voice" value="generic" ${api.sim.voice() === 'generic' ? 'checked' : ''}><span>Generic</span></label><i class="seg-thumb"></i></div></div>
        <div class="pres-row"><span>Fill the open question</span><span class="pres-btns"><button class="btn btn-secondary btn-sm" id="pm-fill-specific" type="button">Specific</button><button class="btn btn-secondary btn-sm" id="pm-fill-generic" type="button">Generic</button></span></div>
        <div class="pres-row"><span>Clear all local demo data</span><button class="btn btn-danger btn-sm" id="pm-reset" type="button">Reset</button></div>
        <h3>Script, attempt ${attemptNo()}</h3>
        ${lines.map(([t, x], i) => `<div class="pres-snip"><b>${esc(t)}</b><button class="btn-icon" data-copy="${i}" type="button" aria-label="Copy: ${esc(t)}">${icon('copy', 14)}</button><p>${esc(x)}</p></div>`).join('')}`;
      V.seg(panel);
      $('#pm-cam', panel).onchange = e => { api.sim.setCameraRequired(e.target.checked); V.toast(e.target.checked ? 'The camera is required.' : 'The camera is optional for the next interview.'); };
      $$('input[name=pm-voice]', panel).forEach(r => { r.onchange = () => { api.sim.setVoice(r.value); V.toast(`Spoken answers will read as ${r.value}.`); }; });
      $('#pm-fill-specific', panel).onclick = () => fillOpenQuestion('specific');
      $('#pm-fill-generic', panel).onclick = () => fillOpenQuestion('generic');
      $('#pm-reset', panel).onclick = async () => {
        if (!await V.confirmDialog({ title: 'Clear all local demo data?', body: 'This removes every session and recording stored by the simulator on this device.', confirm: 'Clear everything', danger: true })) return;
        await api.sim.reset();
        await goHome();
        V.toast('Local demo data cleared.');
      };
      $$('[data-copy]', panel).forEach(b => { b.onclick = () => V.copy(lines[+b.dataset.copy][1]).then(ok => V.toast(ok ? 'Copied.' : 'Copy failed.')); });
    };
    toggle.onclick = () => {
      const open = panel.hidden;
      if (open) paint();
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      if (open && !V.reduced()) panel.animate([{ opacity: 0, transform: 'translateY(-4px) scale(.98)' }, { opacity: 1, transform: 'none' }], { duration: V.SPRING.snap.duration, easing: V.SPRING.snap.easing });
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
    if (!state) home = await api.check({ pr: prParams() });
    render();
    V.enter($$('[data-enter]', root), { y: 8, step: 50, dur: 480, delay: 40 });
    V.observe(root);
    V.seg(root);
  }
  addEventListener('hashchange', () => {
    const id = hashId();
    if (id && (!state || state.id !== id)) action(async () => accept(await api.session(id, opts())));
  });
  boot();
})();
