/* window.VivaReview: the senior reviewer page. Watch each recorded answer, read what the score looked at, decide.
   The role is decided by the reviewer token, never by anything this page sends. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const api = V.api;
  const { $, $$, esc, icon, fmtTime } = V;
  const root = $('#app');

  let token = '';
  try { token = decodeURIComponent(location.hash.slice(1)); } catch { token = ''; }

  let data = null, players = [];
  const KINDS = ['specific', 'reason', 'own', 'generic'];
  const MODE = { voice: 'Spoken', text: 'Typed' };
  const CHIP = { genuine: 'Likely their own work', unclear: 'Needs a closer look', weak: 'Could not confirm' };
  const ACT = { sign: 'requested a signed link for', play: 'played', open_review: 'opened the review page' };
  const who = a => (a === 'learner' ? 'The learner' : `Reviewer ${esc(String(a).split(':')[1] || '')}`);
  const marks = segs => segs.map(s => (KINDS.includes(s.kind) ? `<mark data-kind="${s.kind}" class="on">${esc(s.text)}</mark>` : esc(s.text))).join('');

  // ---------- player ----------
  function playerHtml(m) {
    return `<div class="player" data-id="${esc(m.id)}">
      <video class="p-video" playsinline preload="none"></video>
      <div class="p-wave" role="slider" tabindex="0" aria-label="Recording position" aria-valuemin="0" aria-valuemax="${Number(m.duration)}" aria-valuenow="0"><canvas></canvas><i class="p-head"></i></div>
      <div class="p-bar">
        <button class="btn-icon p-play" type="button" aria-label="Play">${icon('play', 18)}</button>
        <span class="mono num p-time">0:00 / ${fmtTime(Number(m.duration))}</span>
        <span class="p-exp small muted">A signed link is requested when you press play.</span>
        <button class="btn-text p-renew" type="button" hidden>Request a new link</button>
      </div></div>`;
  }

  function mountPlayer(el, media, segs, { onActive, onAccess }) {
    const video = $('video', el), wave = $('.p-wave', el), cv = $('canvas', wave), head = $('.p-head', el);
    const btn = $('.p-play', el), time = $('.p-time', el), exp = $('.p-exp', el), renewBtn = $('.p-renew', el);
    let peaks = null, expiresAt = 0, raf = 0, expTimer = 0, loading = null, expired = false, lastActive = -1, url = null;
    const total = () => (isFinite(video.duration) && video.duration > 0 ? video.duration : media.duration);

    function fit() {
      const r = cv.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2);
      cv.width = Math.max(1, Math.round(r.width * d)); cv.height = Math.max(1, Math.round(r.height * d));
    }
    function draw() {
      const g = cv.getContext('2d'), w = cv.width, h = cv.height, st = getComputedStyle(document.documentElement);
      const ink = st.getPropertyValue('--ink').trim(), dim = st.getPropertyValue('--line-strong').trim(), acc = st.getPropertyValue('--accent').trim();
      const d = w / (cv.getBoundingClientRect().width || w), bw = 3 * d, gap = 3 * d, n = Math.floor(w / (bw + gap));
      g.clearRect(0, 0, w, h);
      g.save(); g.globalAlpha = 0.14; g.fillStyle = acc; // phrases the score marked as generic sit on a soft band
      segs.filter(s => s.flag).forEach(s => { g.fillRect((s.start / total()) * w, 0, ((s.end - s.start) / total()) * w, h); });
      g.restore();
      const playedTo = (video.currentTime / total()) * n;
      for (let i = 0; i < n; i++) {
        const a = peaks ? peaks[Math.min(peaks.length - 1, Math.floor((i / n) * peaks.length))] : 0.1 + 0.05 * Math.sin(i * 0.7);
        const bh = Math.max(2 * d, a * h * 0.86);
        g.fillStyle = i < playedTo ? ink : dim;
        g.beginPath();
        if (g.roundRect) g.roundRect(i * (bw + gap), (h - bh) / 2, bw, bh, bw / 2); else g.rect(i * (bw + gap), (h - bh) / 2, bw, bh);
        g.fill();
      }
    }
    function paint() {
      const t = video.currentTime || 0;
      time.textContent = `${fmtTime(t)} / ${fmtTime(total())}`;
      head.style.transform = `translateX(${(t / total()) * wave.clientWidth}px)`;
      wave.setAttribute('aria-valuenow', t.toFixed(1));
      const idx = segs.reduce((a, s, i) => (s.start <= t + 0.05 ? i : a), -1);
      if (idx !== lastActive) { lastActive = idx; onActive(idx); }
      draw();
    }
    const loop = () => { paint(); if (!video.paused) raf = requestAnimationFrame(loop); };

    async function peaksOf(objectUrl) {
      let ctx;
      try {
        const buf = await (await fetch(objectUrl)).arrayBuffer();
        const Ctx = window.AudioContext || window.webkitAudioContext;
        ctx = new Ctx();
        const audio = await ctx.decodeAudioData(buf);
        const ch = audio.getChannelData(0), n = 140, size = Math.floor(ch.length / n) || 1, out = [];
        for (let i = 0; i < n; i++) { let m = 0; for (let j = i * size; j < (i + 1) * size && j < ch.length; j++) m = Math.max(m, Math.abs(ch[j])); out.push(m); }
        const top = Math.max(...out, 0.001);
        peaks = out.map(x => Math.max(0.06, x / top));
        draw();
      } catch { /* the placeholder waveform stays */ } finally { if (ctx) ctx.close().catch(() => {}); }
    }
    function clock() {
      clearInterval(expTimer);
      const tick = () => {
        const left = Math.ceil(expiresAt - Date.now() / 1000);
        if (left > 0) { exp.textContent = `Signed link expires in ${fmtTime(left)}`; return; }
        expired = true; clearInterval(expTimer); video.pause();
        exp.textContent = 'This link has expired.'; renewBtn.hidden = false; btn.disabled = true;
      };
      tick(); expTimer = setInterval(tick, 1000);
    }
    async function load() {
      if (loading) return loading;
      loading = (async () => {
        exp.textContent = 'Requesting a signed link';
        const link = await api.mediaLink(media.id, { token });
        expiresAt = link.expires_at;
        const f = await api.mediaFetch(link.url);
        const at = video.currentTime || 0;
        if (url) URL.revokeObjectURL(url);
        url = f.objectUrl;
        video.src = url;
        await new Promise(r => { video.onloadedmetadata = r; setTimeout(r, 2000); });
        if (!isFinite(video.duration)) { // MediaRecorder files have no length until the end is visited
          await new Promise(r => { const d = () => { video.removeEventListener('timeupdate', d); video.currentTime = at; r(); }; video.addEventListener('timeupdate', d); video.currentTime = 1e6; setTimeout(r, 1500); });
        } else video.currentTime = at;
        expired = false; renewBtn.hidden = true; btn.disabled = false;
        clock();
        if (!peaks) peaksOf(url);
        onAccess();
      })();
      try { await loading; } catch (e) { exp.textContent = e.message; V.toast(e.message, { kind: 'error' }); throw e; } finally { loading = null; }
    }
    async function play(t) {
      if (!video.src || expired) await load();
      if (t != null) video.currentTime = t;
      await video.play().catch(() => {});
    }
    btn.addEventListener('click', async () => { try { if (video.paused) await play(); else video.pause(); } catch { /* shown in the status line */ } });
    renewBtn.addEventListener('click', async () => { video.removeAttribute('src'); try { await load(); play(); } catch { /* shown in the status line */ } });
    video.addEventListener('play', () => { btn.innerHTML = icon('pause', 18); btn.setAttribute('aria-label', 'Pause'); cancelAnimationFrame(raf); loop(); });
    video.addEventListener('pause', () => { btn.innerHTML = icon('play', 18); btn.setAttribute('aria-label', 'Play'); paint(); });
    video.addEventListener('ended', () => { btn.innerHTML = icon('play', 18); paint(); });
    video.addEventListener('seeked', paint);
    const scrub = e => { const r = wave.getBoundingClientRect(); play(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * total()).catch(() => {}); };
    wave.addEventListener('pointerdown', scrub);
    wave.addEventListener('keydown', e => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); play(Math.max(0, (video.currentTime || 0) + (e.key === 'ArrowRight' ? 2 : -2))).catch(() => {}); } });
    fit(); draw();
    const ro = new ResizeObserver(() => { fit(); paint(); });
    ro.observe(wave);
    return { seek: t => play(t), destroy() { cancelAnimationFrame(raf); clearInterval(expTimer); ro.disconnect(); video.pause(); video.removeAttribute('src'); if (url) URL.revokeObjectURL(url); url = null; } };
  }

  // ---------- page ----------
  function turnHtml(t) {
    const segs = t.segments
      ? `<ol class="rv-tr">${t.segments.map((s, i) => `<li><button type="button" class="seg-row" data-turn="${Number(t.turn)}" data-i="${i}" ${s.flag ? 'data-flag' : ''}><span class="mono num">${fmtTime(Number(s.start))}</span><span class="seg-body"><span class="seg-text">${esc(s.text)}</span>${s.flag ? `<span class="seg-flag">${icon('flag', 13)} ${esc(s.flag)}</span>` : ''}</span></button></li>`).join('')}</ol>`
      : `<blockquote class="rq-a">${marks(t.marks)}</blockquote>`;
    return `<article class="rv-turn" data-reveal>
      <header><span class="micro">Question ${Number(t.turn)}</span><span class="chip">${esc(t.label)}</span><span class="chip">${MODE[t.mode] || 'Answered'}</span>${t.source === 'follow-up' ? '<span class="chip chip-signal">Follow-up</span>' : ''}</header>
      <p class="rv-q">${esc(t.question)}</p>
      ${t.media ? playerHtml(t.media) : '<p class="muted small">No recording for this answer.</p>'}
      <h4 class="micro rv-tr-h">${t.segments ? 'Transcript' : 'Typed answer'}</h4>
      ${segs}
    </article>`;
  }
  function decisionHtml() {
    const r = data.decision;
    if (!r || r.status !== 'decided') return '';
    const ok = r.verdict === 'genuine';
    return `<div class="senior saved" data-enter><header><span class="chip ${ok ? 'chip-solid' : 'chip-signal'}">${ok ? 'Confirmed' : 'Follow-up'}</span></header><p>${ok ? 'Looks like their own work.' : 'Needs a follow-up conversation.'}</p>${r.note ? `<blockquote>${esc(r.note)}</blockquote>` : ''}</div>`;
  }
  const logHtml = () => (data.access_log.length ? data.access_log.map(e => `<li><span class="mono num">${V.fmtClock(Number(e.at))}</span><span>${who(e.actor)} ${ACT[e.action] || 'opened'}${e.media_id ? ` the question ${Number(e.turn)} recording` : ''}.</span></li>`).join('') : '<li class="muted">No entries yet.</li>');

  function render() {
    players.forEach(p => p.destroy()); players = [];
    const pr = data.pr, a = data.assessment;
    document.title = `Review #${Number(pr.number)} | Viva`;
    root.innerHTML = `
      <div class="stage-head" data-enter>
        <div><p class="micro">Senior review</p><h1 class="h1 mask">${V.mask(['Watch the answers,', 'then decide.'])}</h1></div>
        <div class="head-meta"><span class="chip">${esc(pr.repo)} #${Number(pr.number)}</span><p class="timer">${esc(pr.title)}</p></div>
      </div>
      <div class="rv-grid">
        <div class="rv-main">
          <section data-enter>
            <div class="rv-score">
              <div class="rv-scorenum"><b class="num">${Number(a.score)}</b><span>Understanding score</span></div>
              <div class="rv-scoremeta"><span class="chip res-verdict" data-verdict="${esc(a.verdict)}">${CHIP[a.verdict] || ''}</span>${a.simulated ? '<span class="chip">Simulated assessment</span>' : ''}${data.attempt > 1 ? `<span class="chip chip-signal">Attempt ${Number(data.attempt)} of ${Number(data.max_attempts)}</span>` : ''}<p class="muted small">Words only. The score never uses the face, the voice tone or expressions in the recording.</p>${data.previous.map(p => `<p class="muted small">Attempt ${Number(p.attempt)} scored ${Number(p.score)} and did not pass. This is the retake, with different questions.</p>`).join('')}</div>
            </div>
            <ul class="rv-dims">${a.dims.map(d => `<li><span>${esc(d.label)}</span><b class="num">${Number(d.value)}</b><p>${esc(d.note)}</p></li>`).join('')}</ul>
          </section>
          <section class="rv-interview">
            <h2 class="h2">Interview</h2>
            ${data.turns.map(turnHtml).join('') || '<p class="muted">No answers were recorded.</p>'}
          </section>
        </div>
        <aside class="rv-side">
          <section class="panel composer" data-enter>
            <h2 class="h2">Your decision</h2>
            <div id="saved" aria-live="polite">${decisionHtml()}</div>
            <div class="rv-choices" role="radiogroup" aria-label="Decision">
              <label class="ev" data-spot><input type="radio" name="verdict" value="genuine"><span class="ev-mark"></span><span class="ev-text"><b>Looks like their own work</b><em>The answers match the change.</em></span></label>
              <label class="ev" data-spot><input type="radio" name="verdict" value="followup"><span class="ev-mark"></span><span class="ev-text"><b>Needs a follow-up conversation</b><em>Some answers stayed general.</em></span></label>
            </div>
            <div class="field"><label for="note">Note for the author (optional)</label><textarea class="textarea" id="note" rows="4" maxlength="500" aria-describedby="note-hint"></textarea><span class="hint" id="note-hint">The author sees your decision and this note on their results page.</span></div>
            <p class="error-text" id="err" role="alert" hidden></p>
            <div class="form-foot"><button class="btn btn-primary" id="save" type="button" data-magnetic>Save decision <span class="arrow">${icon('arrow', 16)}</span></button></div>
          </section>
          <section class="card log" data-reveal>
            <header class="card-head"><h3>Recording access log</h3></header>
            <ul id="rv-log">${logHtml()}</ul>
            <p class="hint">Visible to the author. Signed links expire after 5 minutes.</p>
          </section>
        </aside>
      </div>`;

    const refreshLog = async () => {
      try { data.access_log = (await api.review(token, { silent: true })).access_log; $('#rv-log').innerHTML = logHtml(); } catch { /* keep the old log */ }
    };
    $$('.player', root).forEach(el => {
      const turn = data.turns.find(t => t.media && t.media.id === el.dataset.id), turnEl = el.closest('.rv-turn');
      const rows = $$('.seg-row', turnEl), segs = turn.segments || [];
      const pl = mountPlayer(el, turn.media, segs, { onActive: idx => rows.forEach((r, i) => r.toggleAttribute('data-active', i === idx)), onAccess: refreshLog });
      pl.turn = turn.turn;
      players.push(pl);
    });
    $$('.seg-row', root).forEach(b => b.addEventListener('click', () => {
      const pl = players.find(p => p.turn === Number(b.dataset.turn));
      const seg = data.turns.find(t => t.turn === Number(b.dataset.turn)).segments[Number(b.dataset.i)];
      if (pl) pl.seek(seg.start).catch(() => {});
    }));
    $('#save').onclick = save;
    V.revealMask(root);
    V.enter($$('[data-enter]', root), { y: 18, step: 70, dur: 900, delay: 120 });
    V.observe(root);
  }

  async function save() {
    const verdict = ($('input[name=verdict]:checked', root) || {}).value, err = $('#err'), btn = $('#save');
    err.hidden = true;
    if (!verdict) { err.textContent = 'Choose a decision.'; err.hidden = false; return; }
    btn.disabled = true;
    try {
      // no role in the body: the server reads it from the token
      data.decision = await api.decide(token, { verdict, note: $('#note').value });
      $('#saved').innerHTML = decisionHtml();
      V.enter($('#saved').lastElementChild, { y: 14, dur: 800 });
      V.toast('Decision saved. The author sees it on their results page.');
    } catch (e) { err.textContent = e.message; err.hidden = false; } finally { btn.disabled = false; }
  }

  function forbidden(message) {
    document.title = 'No access | Viva';
    root.innerHTML = `<div class="rv-locked-page" data-enter>
      <span class="lockmark">${icon('lock', 26)}</span>
      <h1 class="h1 mask">${V.mask(['This link does not', 'open a review.'])}</h1>
      <p class="lede">${message === 'This link does not open a review.' ? '' : `${esc(message)} `}Reviewer links are separate from learner links, and each one opens exactly one interview.</p>
      <a class="btn btn-ghost" href="index.html">Back to Viva</a></div>`;
    V.revealMask(root);
    V.enter($$('[data-enter]', root), { y: 18, dur: 900, delay: 100 });
  }

  async function boot() {
    V.boot();
    if (!token) { forbidden('There is no token in this address.'); return; }
    try { data = await api.review(token); } catch (e) { forbidden(e.message); return; }
    render();
  }
  addEventListener('hashchange', () => location.reload()); // a pasted token opens its own review
  window.addEventListener('pagehide', () => players.forEach(p => p.destroy()));
  boot();
  V.review = { boot };
  window.VivaReview = V.review;
})();
