/* window.VivaReview: the senior reviewer page. Watch each recorded answer, read what the score looked at, decide.
   The role is decided by the reviewer token, never by anything this page sends. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const api = V.api, D = V.data;
  const { $, $$, esc, icon, fmtTime } = V;
  const root = $('#app');

  let token = '';
  try { token = decodeURIComponent(location.hash.slice(1)); } catch { token = ''; }

  let data = null, players = [];
  const KINDS = ['specific', 'reason', 'generic'];
  const MODE = { voice: 'Spoken', text: 'Typed' };
  const VERDICT = { shown: 'Understanding shown', gaps: 'Gaps to close', not_shown: 'Not shown yet' };
  const ACT = { sign: 'requested a signed link for', play: 'played', open_review: 'opened the review page' };
  const who = a => (a === 'learner' ? 'The author' : 'You');
  const bub = (tone, name) => `<span class="bub" data-tone="${tone}">${icon(name, 14)}</span>`;
  const marks = segs => segs.map(s => (KINDS.includes(s.kind) ? `<mark data-kind="${s.kind}" class="on">${esc(s.text)}</mark>` : esc(s.text))).join('');

  // ---------- player ----------
  function playerHtml(m) {
    return `<div class="player" data-id="${esc(m.id)}">
      <div class="p-stage"><video class="p-video" playsinline preload="none"></video><span class="p-cover">${icon('lock', 18)}<span>Signed link on play</span></span></div>
      <div class="p-bar">
        <button class="btn-icon p-play" type="button" aria-label="Play">${icon('play', 16)}</button>
        <div class="p-wave" role="slider" tabindex="0" aria-label="Recording position" aria-valuemin="0" aria-valuemax="${Number(m.duration)}" aria-valuenow="0"><canvas></canvas><i class="p-head"></i></div>
        <span class="mono num p-time">0:00 / ${fmtTime(Number(m.duration))}</span>
      </div>
      <p class="p-exp"><span class="p-exp-t">A signed link is requested when you press play.</span><button class="btn-text p-renew" type="button" hidden>Request a new link</button></p>
    </div>`;
  }

  function mountPlayer(el, media, segs, { onActive, onAccess }) {
    const video = $('video', el), wave = $('.p-wave', el), cv = $('canvas', wave), head = $('.p-head', el);
    const btn = $('.p-play', el), time = $('.p-time', el), exp = $('.p-exp-t', el), renewBtn = $('.p-renew', el);
    let peaks = null, expiresAt = 0, raf = 0, expTimer = 0, loading = null, expired = false, lastActive = -1, url = null;
    const total = () => (isFinite(video.duration) && video.duration > 0 ? video.duration : media.duration);

    function fit() {
      const r = cv.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2);
      cv.width = Math.max(1, Math.round(r.width * d)); cv.height = Math.max(1, Math.round(r.height * d));
    }
    function draw() {
      const g = cv.getContext('2d'), w = cv.width, h = cv.height, st = getComputedStyle(document.documentElement);
      const dim = st.getPropertyValue('--faint').trim(), acc = st.getPropertyValue('--accent').trim();
      const d = w / (cv.getBoundingClientRect().width || w), bw = 2 * d, gap = 2 * d, n = Math.floor(w / (bw + gap));
      g.clearRect(0, 0, w, h);
      g.save(); g.globalAlpha = 0.12; g.fillStyle = acc; // phrases the score marked as generic sit on a soft band
      segs.filter(s => s.flag).forEach(s => { g.fillRect((s.start / total()) * w, 0, ((s.end - s.start) / total()) * w, h); });
      g.restore();
      const playedTo = (video.currentTime / total()) * n;
      for (let i = 0; i < n; i++) {
        const a = peaks ? peaks[Math.min(peaks.length - 1, Math.floor((i / n) * peaks.length))] : 0.2 + 0.3 * Math.abs(Math.sin(i * 0.55)) * (0.6 + 0.4 * Math.sin(i * 0.13));
        const bh = Math.max(2 * d, a * h * 0.84);
        g.fillStyle = i < playedTo ? acc : dim;
        g.globalAlpha = i < playedTo ? 1 : 0.5;
        g.beginPath();
        if (g.roundRect) g.roundRect(i * (bw + gap), (h - bh) / 2, bw, bh, bw / 2); else g.rect(i * (bw + gap), (h - bh) / 2, bw, bh);
        g.fill();
      }
      g.globalAlpha = 1;
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
        const ch = audio.getChannelData(0), n = 160, size = Math.floor(ch.length / n) || 1, out = [];
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
        if (left > 0) { exp.textContent = `Signed link expires in ${fmtTime(left)}.`; return; }
        expired = true; clearInterval(expTimer); video.pause();
        exp.textContent = 'This link has expired.'; renewBtn.hidden = false; btn.disabled = true;
      };
      tick(); expTimer = setInterval(tick, 1000);
    }
    async function load() {
      if (loading) return loading;
      loading = (async () => {
        exp.textContent = 'Requesting a signed link.';
        const link = await api.mediaLink(media.id, { token });
        expiresAt = link.expires_at;
        const f = await api.mediaFetch(link.url);
        const at = video.currentTime || 0;
        if (url) URL.revokeObjectURL(url);
        url = f.objectUrl;
        video.src = url;
        el.dataset.loaded = '1';
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
    video.addEventListener('play', () => { btn.innerHTML = icon('pause', 16); btn.setAttribute('aria-label', 'Pause'); cancelAnimationFrame(raf); loop(); });
    video.addEventListener('pause', () => { btn.innerHTML = icon('play', 16); btn.setAttribute('aria-label', 'Play'); paint(); });
    video.addEventListener('ended', () => { btn.innerHTML = icon('play', 16); paint(); });
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
      ? `<ol class="rv-tr">${t.segments.map((s, i) => `<li><button type="button" class="seg-row" data-turn="${Number(t.turn)}" data-i="${i}" ${s.flag ? 'data-flag' : ''}><span class="mono num">${fmtTime(Number(s.start))}</span><span class="seg-body"><span class="seg-text">${esc(s.text)}</span>${s.flag ? `<span class="seg-flag">${icon('flag', 12)}${esc(s.flag)}</span>` : ''}</span></button></li>`).join('')}</ol>`
      : `<blockquote class="rq-a">${marks(t.marks)}</blockquote>`;
    return `<article class="rv-turn">
      <header><span class="rq-n num">${Number(t.turn)}</span><span class="tag" data-tone="lilac">${esc(t.label)}</span><span class="tag">${MODE[t.mode] || 'Answered'}</span>${t.source === 'follow-up' ? '<span class="tag" data-tone="lemon">Follow-up</span>' : ''}</header>
      <p class="rv-q">${esc(t.question)}</p>
      <div class="rv-body${t.media ? '' : ' rv-body-text'}">
        ${t.media ? playerHtml(t.media) : ''}
        <div class="rv-text"><p class="label rv-tr-h">${t.segments ? 'Transcript. Select a line to jump to it.' : t.media ? 'Typed answer, recorded on camera' : 'Typed answer. No recording.'}</p>${segs}</div>
      </div>
    </article>`;
  }
  function decisionHtml() {
    const r = data.decision;
    if (!r || r.status !== 'decided') return '';
    const ok = r.verdict === 'correction';
    return `<div class="saved" data-verdict="${ok ? 'correction' : 'followup'}"><span class="saved-i">${icon(ok ? 'check' : 'chat', 14)}</span><div><b>${ok ? 'Passed, with a correction' : 'Follow-up requested'}</b>${r.note ? `<p>${esc(r.note)}</p>` : ''}<span>Saved at ${V.fmtClock(Number(r.at))}. You can change it below.</span></div></div>`;
  }
  const statusOf = () => {
    const r = data.decision;
    if (r && r.status === 'decided') return r.verdict === 'correction' ? { tone: 'mint', text: 'Correction added' } : { tone: '', text: 'Follow-up requested' };
    return { tone: 'lemon', live: true, text: 'Waiting for your decision' };
  };
  const logHtml = () => (data.access_log.length
    ? data.access_log.map(e => `<li><span class="av" data-tone="ink" style="--s:20px">${esc(e.actor === 'learner' ? V.initials(D.me.name) : V.initials(D.reviewer.name))}</span><span><b>${who(e.actor)}</b> ${ACT[e.action] || 'opened'}${e.media_id ? ` the question ${Number(e.turn)} recording` : ''}.</span><time class="mono num">${V.fmtClock(Number(e.at))}</time></li>`).join('')
    : '<li class="muted">No entries yet.</li>');

  function render() {
    players.forEach(p => p.destroy()); players = [];
    const pr = data.pr, a = data.assessment, repo = String(pr.repo).split('/').pop(), st = statusOf();
    document.title = `Review #${Number(pr.number)} | Viva`;
    $('#crumb').innerHTML = `<span>Reviews</span><span class="sep" aria-hidden="true">/</span><b>${esc(repo)} #${Number(pr.number)}</b>`;
    root.innerHTML = `
      <header class="ph" data-enter>
        <div class="ph-main">
          <p class="ph-eyebrow">${icon('inbox', 15)}Review request<span class="sep" aria-hidden="true">/</span><span class="mono">${esc(pr.repo)}</span>#${Number(pr.number)}</p>
          <h1 class="ph-title">${esc(pr.title)}</h1>
          <div class="ph-meta">
            <span class="badge"${st.tone ? ` data-tone="${st.tone}"` : ''} id="rv-status">${st.live ? '<i class="dot" data-live></i>' : ''}${esc(st.text)}</span>
            <span><span class="av" style="--s:18px"><img src="${esc(D.me.avatar)}" alt=""></span>Author ${esc(pr.author)}</span>
            <span>${icon('commit', 14)}<span class="mono">${esc(pr.sha)}</span></span>
            <span>${icon('refresh', 14)}Attempt ${Number(data.attempt)} of ${Number(data.max_attempts)}</span>
            ${data.requested ? `<span>${icon('clock', 14)}Requested at ${V.fmtClock(Number(data.requested))}</span>` : ''}
          </div>
        </div>
        <div class="ph-actions rv-me"><span class="av" data-tone="lemon" style="--s:36px">${esc(V.initials(D.reviewer.name))}</span><div><b>${esc(D.reviewer.name)}</b><span>${esc(D.reviewer.role)}</span></div></div>
      </header>
      <div class="cols">
        <div class="stack">
          <section class="card rv-sum" data-enter data-verdict="${esc(a.verdict)}">
            <div class="rv-score">
              <div class="rv-scorenum"><b class="num">${Number(a.score)}</b><span>of 100</span></div>
              <div class="rv-scoremeta">
                <p class="label">Understanding score</p>
                <div class="score-tags"><span class="badge"${a.verdict === 'shown' ? ' data-tone="accent"' : a.verdict === 'gaps' ? ' data-tone="blue"' : ''}>${VERDICT[a.verdict] || ''}</span>${a.simulated ? '<span class="tag">Simulated assessment</span>' : ''}</div>
                <p class="muted small">Words only. The score never uses the face, the voice tone or the expressions in the recording.</p>
                ${data.previous.map(p => `<p class="muted small">Attempt ${Number(p.attempt)} scored ${Number(p.score)} and did not pass. This is the retake, with different questions.</p>`).join('')}
              </div>
            </div>
            <ul class="dims">${a.dims.map(d => `<li class="dim"><div class="dim-top"><b>${esc(d.label)}</b><span class="dim-val num">${Number(d.value)}</span></div><span class="dim-line" aria-hidden="true"><i style="--w:${(Number(d.value) / 100).toFixed(2)}"></i></span><p>${esc(d.note)}</p></li>`).join('')}</ul>
          </section>
          <section class="card rv-interview" data-enter>
            <div class="card-h"><h2>${bub('lilac', 'chat')}Interview</h2><span class="meta">${data.turns.length} ${data.turns.length === 1 ? 'answer' : 'answers'}</span></div>
            ${data.turns.map(turnHtml).join('') || '<p class="muted">No answers were recorded.</p>'}
          </section>
        </div>
        <aside class="stack rv-side">
          <section class="card composer" data-enter>
            <div class="card-h"><h2>${bub('lemon', 'shield')}Your decision</h2></div>
            <div id="saved" aria-live="polite">${decisionHtml()}</div>
            <div class="rv-choices" role="radiogroup" aria-label="Decision">
              <label class="ev"><input type="radio" name="verdict" value="correction"><span class="ev-mark"></span><span class="ev-text"><b>Pass, with a one-line correction</b><em>The author sees it next time they meet this concept.</em></span></label>
              <label class="ev"><input type="radio" name="verdict" value="followup"><span class="ev-mark"></span><span class="ev-text"><b>Needs a follow-up conversation</b><em>Some answers stayed general.</em></span></label>
            </div>
            <div class="field"><label for="note">One-line correction <span class="muted">(required to pass)</span></label><textarea class="textarea" id="note" rows="3" maxlength="500" aria-describedby="note-hint" placeholder="For example: round once, at the end. Rounding the fee on its own lets the cents drift."></textarea><span class="hint" id="note-hint">It goes to the author's gap record for this concept, not to their manager.</span></div>
            <p class="error-text" id="err" role="alert" hidden></p>
            <button class="btn btn-primary rv-save" id="save" type="button">Save decision</button>
            <p class="card-foot">Saving updates the viva / decision-check on GitHub.</p>
          </section>
          <section class="card log" data-enter>
            <div class="card-h"><h2>${bub('sky', 'eye')}Recording access log</h2></div>
            <ul class="log-list" id="rv-log">${logHtml()}</ul>
            <p class="card-foot">Visible to the author. Signed links expire after 5 minutes.</p>
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
    V.enter($$('[data-enter]', root), { y: 8, step: 50, dur: 480, delay: 40 });
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
      V.enter($('#saved').firstElementChild, { y: 6, dur: 420 });
      const st = statusOf();
      $('#rv-status').outerHTML = `<span class="badge"${st.tone ? ` data-tone="${st.tone}"` : ''} id="rv-status">${esc(st.text)}</span>`;
      if (verdict === 'correction') V.confetti(btn);
      V.toast('Decision saved. The author sees it on their results page.');
    } catch (e) { err.textContent = e.message; err.hidden = false; } finally { btn.disabled = false; }
  }

  function forbidden(message) {
    document.title = 'No access | Viva';
    root.innerHTML = `<div class="rv-locked-page"><section class="card" data-enter>
      <span class="lockmark">${icon('lock', 20)}</span>
      <h1 class="h1">This link does not open a review.</h1>
      <p class="muted">${message === 'This link does not open a review.' ? '' : `${esc(message)} `}Reviewer links are separate from learner links, and each one opens exactly one interview.</p>
      <a class="btn btn-secondary" href="index.html">Back to Viva</a></section></div>`;
    V.enter($$('[data-enter]', root), { y: 8, dur: 480 });
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
