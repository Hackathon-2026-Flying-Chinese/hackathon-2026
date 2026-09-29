/* window.VivaInterview: the full-page interview. The camera is on for the whole interview, every answer is recorded
   for the senior reviewer, and answers can be spoken or typed. The code under review is never shown. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const D = V.data;
  const { $, $$, esc, icon, fmtTime } = V;

  const arrow = `<span class="arrow">${icon('arrow', 16)}</span>`;
  const ANALYSIS = ['Collecting your answers', 'Looking for specifics', 'Checking your reasoning', 'Comparing what you decided yourself'];

  function shell(view) {
    const pr = view.pr, second = view.attempt > 1;
    return `
      <div class="iv-stage">
        <div class="iv-gate" hidden>
          <p class="micro">${second ? 'Second attempt' : 'Before you start'}</p>
          <h1 class="iv-q mask">${V.mask(['Turn on your camera', 'to begin.'])}</h1>
          <p class="lede">Your camera and microphone stay on for the whole interview, and a senior reviewer watches the recording.</p>
          <ul class="iv-facts">${second ? '<li>New questions about the same change. Your first attempt is kept.</li>' : ''}<li>Your code is not shown. Answer in your own words.</li><li>The score uses your words only. Never your face or your voice tone.</li></ul>
          <div class="iv-gate-actions">
            <button class="btn btn-primary" type="button" id="cam-on" data-magnetic>Turn on camera and microphone ${arrow}</button>
            <button class="btn-text" type="button" id="cam-skip" hidden>Continue without camera (presenter only)</button>
          </div>
          <p class="error-text" id="cam-err" role="alert" hidden></p>
        </div>

        <div class="iv-main" hidden>
          <div class="iv-bar">
            <div class="iv-prog"><span class="micro iv-count"></span><span class="iv-ticks" aria-hidden="true"></span></div>
            <button class="btn-text iv-leave" type="button">Leave</button>
          </div>
          <div class="iv-meta"><span class="chip iv-label"></span><span class="chip chip-signal iv-src" hidden>Follow-up</span>${second ? `<span class="chip chip-signal">Attempt ${Number(view.attempt)} of ${Number(view.max_attempts)}</span>` : ''}</div>
          <h1 class="iv-q" aria-live="polite" aria-atomic="true"></h1>
          <p class="iv-ground">About pull request #${Number(pr.number)} in ${esc(pr.repo)}. Your code is not shown. Answer in your own words.</p>

          <div class="iv-answer" hidden>
            <div class="seg iv-tabs" data-seg role="radiogroup" aria-label="Answer by"><label><input type="radio" name="iv-mode" value="speak" checked><span>Speak</span></label><label><input type="radio" name="iv-mode" value="type"><span>Type</span></label><i class="seg-thumb"></i></div>
            <div class="iv-pane iv-speak">
              <canvas class="iv-wave" aria-hidden="true"></canvas>
              <div class="iv-speak-row"><p class="hint">Speak now. Press done when you finish.</p><button class="btn btn-ghost" type="button" id="iv-done">Done speaking</button></div>
            </div>
            <div class="iv-pane iv-type" hidden>
              <label class="sr-only" for="iv-text">Your answer</label>
              <textarea class="textarea" id="iv-text" rows="6" aria-describedby="iv-type-hint"></textarea>
              <span class="hint" id="iv-type-hint">At least ${D.minAnswerChars} characters. The camera keeps recording while you type.</span>
            </div>
            <div class="iv-pane iv-review" hidden>
              <div class="iv-review-head"><label class="label" for="iv-tx">Transcript</label><span class="chip">Simulated</span></div>
              <textarea class="textarea" id="iv-tx" rows="5" aria-describedby="iv-tx-hint"></textarea>
              <span class="hint" id="iv-tx-hint">Simulated transcript: edit it so it matches what you said. The real build transcribes speech on the server.</span>
              <button class="btn-text" type="button" id="iv-again">Speak again</button>
            </div>
            <p class="error-text" id="iv-err" role="alert" hidden></p>
            <p class="hint iv-cap" hidden>The recording reached its limit. Finish your answer now.</p>
            <div class="iv-foot"><button class="btn btn-primary" type="button" id="iv-submit" data-magnetic disabled>Submit answer ${arrow}</button></div>
          </div>
        </div>

        <div class="iv-analysis" hidden aria-live="polite">
          <p class="micro">Submitted</p>
          <h1 class="iv-q mask">${V.mask(['Reading your', 'answers.'])}</h1>
          <ol class="iv-steps">${ANALYSIS.map((t, i) => `<li style="--i:${i}"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path pathLength="1" d="M5 12.5l4.5 4.5L19 7.5"/></svg><span>${t}</span></li>`).join('')}</ol>
        </div>
      </div>

      <figure class="cam" data-pos="center" data-state="off">
        <video muted playsinline autoplay></video>
        <span class="cam-empty">${icon('camera', 30)}</span>
        <figcaption><span class="cam-rec"><i></i><b>Recording</b><span class="mono num cam-time">0:00</span></span><span class="cam-idle">Camera on</span><span class="cam-off">Camera off</span></figcaption>
      </figure>`;
  }

  function mount(host, ctx) {
    const { api, sid, presenter } = ctx;
    let view = ctx.view, cam = null, cur = null, mode = 'speak', upload = null, busy = false, destroyed = false, stopWave = null, clock = 0;

    host.className = 'iv';
    host.innerHTML = shell(view);
    V.seg(host);
    const gate = $('.iv-gate', host), main = $('.iv-main', host), analysis = $('.iv-analysis', host), answer = $('.iv-answer', host);
    const camEl = $('.cam', host), video = $('video', camEl), q = $('.iv-q', main);
    const submit = $('#iv-submit', host), done = $('#iv-done', host), text = $('#iv-text', host), tx = $('#iv-tx', host), err = $('#iv-err', host);
    const panes = { speak: $('.iv-speak', host), type: $('.iv-type', host), review: $('.iv-review', host) };

    const say = m => { err.textContent = m || ''; err.hidden = !m; };

    // ---------- camera card ----------
    async function dock() {
      if (camEl.dataset.pos === 'dock') return;
      const first = camEl.getBoundingClientRect();
      camEl.dataset.pos = 'dock';
      const last = camEl.getBoundingClientRect();
      if (V.reduced()) return;
      const t = V.SPRING.soft.duration + 200;
      camEl.style.transformOrigin = '0 0';
      const a = camEl.animate([{ transform: `translate(${first.left - last.left}px, ${first.top - last.top}px) scale(${first.width / last.width})` }, { transform: 'none' }], { duration: t, easing: V.SPRING.soft.easing });
      await V.settle(a, t);
      camEl.style.transformOrigin = '';
    }
    function paintClock() {
      camEl.toggleAttribute('data-rec', !!(cam && cam.recording));
      if (cam && cam.recording) $('.cam-time', camEl).textContent = fmtTime(cam.elapsed());
    }
    clock = setInterval(paintClock, 500);

    async function startCamera() {
      const btn = $('#cam-on', host);
      $('#cam-err', host).hidden = true;
      btn.disabled = true;
      cam = cam || V.media.camera({ maxSeconds: D.clipSeconds, onCap: () => { $('.iv-cap', host).hidden = false; paintClock(); } });
      try {
        const stream = await cam.start();
        video.srcObject = stream;
        video.play().catch(() => {});
        camEl.dataset.state = 'on';
        cam.onLost = () => { if (!destroyed) { V.toast('The camera stopped. Turn it back on to continue.', { kind: 'error' }); toGate('The camera stopped. Turn it back on to continue.'); } };
        await dock();
        if (destroyed) return;
        begin();
      } catch (e) {
        if (e && e.name === 'Cancelled') return;
        const box = $('#cam-err', host);
        box.textContent = V.media.explain(e);
        box.hidden = false;
        btn.disabled = false;
      }
    }
    function toGate(message) {
      if (cam) cam.takeClip();
      if (stopWave) { stopWave(); stopWave = null; }
      camEl.dataset.state = 'off';
      camEl.dataset.pos = 'center';
      video.srcObject = null;
      main.hidden = true; analysis.hidden = true; gate.hidden = false;
      $('#cam-on', host).disabled = false;
      const box = $('#cam-err', host);
      box.textContent = message || ''; box.hidden = !message;
    }
    $('#cam-on', host).addEventListener('click', startCamera);
    $('#cam-skip', host).addEventListener('click', async () => { camEl.dataset.state = 'skipped'; await dock(); begin(); });

    // ---------- progress ----------
    function paintBar(turn) {
      const total = Math.max(view.interview.standard, view.interview.turns.length);
      $('.iv-count', main).textContent = turn.source === 'follow-up' ? 'One more question' : `Question ${turn.turn} of ${view.interview.standard}`;
      $('.iv-ticks', main).innerHTML = Array.from({ length: total }, (_, i) => `<i data-state="${i + 1 < turn.turn ? 'done' : i + 1 === turn.turn ? 'on' : ''}"></i>`).join('');
      $('.iv-label', main).textContent = turn.label;
      $('.iv-src', main).hidden = turn.source !== 'follow-up';
    }

    // ---------- answering ----------
    function setMode(m) {
      mode = m;
      const reviewing = !!upload;
      panes.speak.hidden = m !== 'speak' || reviewing;
      panes.type.hidden = m !== 'type';
      panes.review.hidden = !reviewing;
      $('.iv-tabs', host).toggleAttribute('data-locked', reviewing);
      const r = $(`input[name=iv-mode][value=${m}]`, host);
      if (r && !r.checked) { r.checked = true; r.dispatchEvent(new Event('change')); }
      if (stopWave) { stopWave(); stopWave = null; }
      if (m === 'speak' && !reviewing && cam) stopWave = V.media.wave($('.iv-wave', host), cam);
      refresh();
    }
    const current = () => (mode === 'speak' ? (upload ? tx.value : '') : text.value);
    function refresh() {
      submit.disabled = busy || current().trim().length < D.minAnswerChars;
      done.disabled = busy;
      // while speaking, "Done speaking" is the only action, so the submit bar stays out of its way
      $('.iv-foot', host).hidden = mode === 'speak' && !upload;
    }
    $$('input[name=iv-mode]', host).forEach(r => r.addEventListener('change', () => { if (busy || upload) { setMode(mode); return; } setMode(r.value === 'type' ? 'type' : 'speak'); }));
    [text, tx].forEach(t => {
      t.addEventListener('input', () => { say(''); refresh(); });
      t.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !submit.disabled) submit.click(); });
    });

    const send = (clip, how) => api.mediaUpload(sid, { blob: clip.blob, turn: cur.turn, kind: clip.kind, duration: Math.min(clip.duration, D.clipSeconds), mode: how });

    done.addEventListener('click', async () => {
      if (busy || !cam) return;
      busy = true; refresh(); say('');
      done.textContent = 'Sending';
      try {
        const clip = await cam.takeClip();
        if (!clip) throw new Error('Nothing was recorded. Try again.');
        upload = await send(clip, 'voice');
        tx.value = upload.transcript || '';
        setMode('speak');
        V.enter(panes.review, { y: 10, dur: 700 });
      } catch (e) {
        say((e && e.message) || 'The recording could not be sent. Try again.');
        cam.startClip();
      } finally { busy = false; done.textContent = 'Done speaking'; refresh(); }
    });
    $('#iv-again', host).addEventListener('click', () => {
      if (busy) return;
      if (upload) { api.mediaDiscard(sid, { media_id: upload.media_id }).catch(() => {}); upload = null; }
      tx.value = '';
      if (cam) { cam.startClip(); paintClock(); }
      setMode('speak');
    });

    submit.addEventListener('click', async () => {
      if (busy) return;
      const body = current().trim();
      if (body.length < D.minAnswerChars) { say(`Say a little more (at least ${D.minAnswerChars} characters).`); return; }
      busy = true; refresh(); say('');
      let sent = upload ? upload.media_id : null, fresh = null;
      try {
        if (!sent && cam) {
          const clip = await cam.takeClip();
          if (clip) { fresh = await send(clip, 'text'); sent = fresh.media_id; }
        }
        const res = await api.interviewAnswer(sid, { version: view.version, turn: cur.turn, text: body, media_id: sent, mode: mode === 'speak' ? 'voice' : 'text' }, { presenter });
        view = res.view; ctx.onView(view);
        upload = null;
        await leaveQuestion();
        if (res.done) { analyse(); return; }
        await ask(view.interview.turns[view.interview.turns.length - 1]);
      } catch (e) {
        if (fresh) api.mediaDiscard(sid, { media_id: fresh.media_id }).catch(() => {});
        if (cam && !cam.recording && !upload) cam.startClip();
        if (e.status === 409) ctx.fail(e); else say(e.status === 422 ? e.message : 'The answer could not be sent. Try again.');
      } finally { busy = false; refresh(); }
    });

    // ---------- flow ----------
    async function leaveQuestion() {
      if (stopWave) { stopWave(); stopWave = null; }
      if (V.reduced()) { answer.hidden = true; return; }
      const a = main.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-14px)' }], { duration: 260, easing: V.EASE.out, fill: 'forwards' });
      await V.settle(a, 260);
      answer.hidden = true;
      a.cancel(); // a lingering fill would keep the next question invisible
    }
    function resetAnswer() {
      upload = null; text.value = ''; tx.value = ''; say('');
      $('.iv-cap', host).hidden = true;
      answer.hidden = true;
    }
    async function ask(turn) {
      cur = turn;
      resetAnswer();
      main.hidden = false; gate.hidden = true; analysis.hidden = true;
      paintBar(turn);
      const typed = V.typeWords(q, turn.question, { perWord: 46 });
      V.enter($$('.iv-bar, .iv-meta, .iv-ground', main), { y: 10, step: 60, dur: 700 });
      await typed;
      if (destroyed || cur !== turn) return;
      answer.hidden = false;
      V.enter(answer, { y: 16, dur: 800 });
      if (cam) { cam.startClip(); paintClock(); }
      // without a camera there is no microphone either, so only typing is possible
      $('.iv-tabs', host).hidden = !cam;
      setMode(cam ? 'speak' : 'type');
      (cam ? done : text).focus({ preventScroll: true });
    }
    async function begin() {
      gate.hidden = true;
      const open = view.interview.turns.find(t => !t.answered);
      if (open) { await ask(open); return; }
      main.hidden = false;
      try {
        const res = await api.interviewNext(sid, { version: view.version }, { presenter });
        view = res.view; ctx.onView(view);
        await ask(view.interview.turns[view.interview.turns.length - 1]);
      } catch (e) { main.hidden = true; gate.hidden = false; ctx.fail(e); }
    }

    async function analyse() {
      if (cam) { await cam.takeClip(); cam.destroy(); cam = null; } // the interview is over: release the camera
      video.srcObject = null;
      main.hidden = true; analysis.hidden = false;
      camEl.dataset.state = 'done';
      V.revealMask(analysis);
      V.enter($$('.micro', analysis), { y: 8, dur: 600 });
      $$('.iv-steps li', analysis).forEach((li, i) => {
        const path = $('path', li);
        li.style.opacity = '0';
        setTimeout(() => {
          li.style.opacity = '';
          if (V.reduced()) return;
          V.enter(li, { y: 10, dur: 600 });
          path.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: 600, delay: 250, easing: V.EASE.io, fill: 'backwards' });
        }, V.reduced() ? 0 : 500 + i * 620);
      });
      const minimum = V.sleep(V.reduced() ? 0 : 500 + ANALYSIS.length * 620 + 300);
      try {
        const [v] = await Promise.all([api.interviewFinish(sid, { version: view.version }, { presenter }), minimum]);
        if (!destroyed) ctx.onFinish(v);
      } catch (e) {
        ctx.fail(e);
        analysis.hidden = true; main.hidden = false;
      }
    }

    $('.iv-leave', host).addEventListener('click', () => ctx.onLeave());

    // ---------- start ----------
    $('#cam-skip', host).hidden = view.camera_required;
    V.enter(camEl, { y: 24, dur: 900, delay: 300 });
    (async () => {
      // if the browser already allows the camera for this site, skip the gate
      let granted = false;
      try { granted = (await navigator.permissions.query({ name: 'camera' })).state === 'granted'; } catch { /* not supported */ }
      if (destroyed) return;
      gate.hidden = false;
      V.revealMask(gate);
      V.enter($$('.micro, .lede, .iv-facts, .iv-gate-actions', gate), { y: 14, step: 70, dur: 800, delay: 100 });
      if (granted) startCamera();
    })();

    return {
      fill(body) {
        if (answer.hidden || upload) return false;
        $('input[name=iv-mode][value=type]', host).click();
        text.value = body;
        text.dispatchEvent(new Event('input'));
        return true;
      },
      get turn() { return cur; },
      destroy() {
        destroyed = true;
        clearInterval(clock);
        if (stopWave) stopWave();
        if (cam) cam.destroy();
      }
    };
  }

  V.interview = { mount };
  window.VivaInterview = V.interview;
})();
