/* window.VivaInterview: the interview. The camera is on for the whole interview, every answer is recorded for the senior
   reviewer, and answers can be spoken or typed. The code under review is never shown. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const D = V.data;
  const { $, $$, esc, icon, fmtTime } = V;

  const arrow = `<span class="arrow">${icon('arrow', 14)}</span>`;
  const ANALYSIS = ['Collecting your answers', 'Looking for specifics', 'Checking your reasoning', 'Comparing what you decided yourself'];
  const mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

  function shell(view) {
    const pr = view.pr, second = view.attempt > 1, reviewer = esc(D.reviewer.name);
    return `
      <div class="iv-stage">
        <div class="iv-gate" hidden>
          <div class="gate-grid">
            <div class="gate-preview"><div class="cam-slot" data-slot="gate"></div></div>
            <div class="gate-panel">
              <div class="gate-art">${V.mascot('talk')}</div>
              <p class="ph-eyebrow">Decision check<span class="sep" aria-hidden="true">/</span><span class="mono">${esc(pr.repo)}</span>#${Number(pr.number)}</p>
              <h1 class="gate-title">${second ? 'Round two. New questions, same change.' : 'Say hi to your camera'}</h1>
              <p class="muted gate-sub">Your camera and microphone stay on for the whole interview, and ${reviewer} watches the recording.</p>
              <div class="gate-check" hidden>
                <div><span class="bub" data-tone="mint">${icon('camera', 14)}</span><span class="gate-dev">Camera</span><b>${icon('check', 14)}</b></div>
                <div><span class="bub" data-tone="mint">${icon('mic', 14)}</span><span>Microphone. Say something.</span><canvas class="gate-wave" aria-hidden="true"></canvas></div>
              </div>
              <ul class="gate-list">
                ${second ? `<li><span class="bub" data-tone="mint">${icon('refresh', 14)}</span><span>New questions about the same change. Your first attempt is kept.</span></li>` : ''}
                <li><span class="bub" data-tone="lilac">${icon('chat', 14)}</span><span>Two questions, and at most one follow-up.</span></li>
                <li><span class="bub" data-tone="sky">${icon('lock', 14)}</span><span>Your code is not shown. Answer in your own words.</span></li>
                <li><span class="bub" data-tone="lemon">${icon('scan', 14)}</span><span>The score uses your words only. Never your face or your voice tone.</span></li>
              </ul>
              <div class="gate-actions">
                <button class="btn btn-primary btn-lg" type="button" id="cam-on">${icon('camera')}Turn on camera and microphone</button>
                <button class="btn btn-primary btn-lg" type="button" id="cam-go" hidden>I'm ready, start ${arrow}</button>
                <button class="btn-text" type="button" id="cam-skip" hidden>Continue without camera (presenter only)</button>
              </div>
              <p class="error-text" id="cam-err" role="alert" hidden></p>
            </div>
          </div>
        </div>

        <div class="iv-main" hidden>
          <div class="iv-col">
            <div class="iv-bar">
              <div class="iv-prog"><span class="iv-count"></span><span class="iv-ticks" aria-hidden="true"></span></div>
              <button class="btn btn-ghost btn-sm iv-leave" type="button">Leave</button>
            </div>
            <div class="iv-pull">
              <div class="iv-meta"><span class="tag iv-label" data-tone="lilac"></span><span class="tag iv-src" data-tone="lemon" hidden>Follow-up</span>${second ? `<span class="tag">Attempt ${Number(view.attempt)} of ${Number(view.max_attempts)}</span>` : ''}</div>
              <h1 class="iv-q" aria-live="polite" aria-atomic="true"></h1>
              <i class="iv-hook" aria-hidden="true"></i>
            </div>
            <p class="iv-ground">${icon('lock', 14)}About pull request #${Number(pr.number)} in ${esc(pr.repo)}. Your code is not shown. Answer in your own words.</p>

            <div class="iv-answer card" hidden>
              <div class="iv-answer-h">
                <div class="seg iv-tabs" data-seg role="radiogroup" aria-label="Answer by"><label><input type="radio" name="iv-mode" value="speak" checked><span>${icon('mic', 14)}Speak</span></label><label><input type="radio" name="iv-mode" value="type"><span>${icon('keyboard', 14)}Type</span></label><i class="seg-thumb"></i></div>
                <span class="hint iv-rec-hint">The camera records while you speak or type.</span>
              </div>
              <div class="iv-pane iv-speak">
                <canvas class="iv-wave" aria-hidden="true"></canvas>
                <div class="iv-speak-row"><p class="hint">Listening. Press done when you finish.</p><button class="btn btn-secondary" type="button" id="iv-done">${icon('check', 14)}Done speaking</button></div>
              </div>
              <div class="iv-pane iv-type" hidden>
                <label class="sr-only" for="iv-text">Your answer</label>
                <textarea class="textarea" id="iv-text" rows="6" aria-describedby="iv-type-hint" placeholder="Answer in your own words"></textarea>
                <span class="hint" id="iv-type-hint">At least ${D.minAnswerChars} characters.</span>
              </div>
              <div class="iv-pane iv-review" hidden>
                <div class="iv-review-head"><label class="form-label" for="iv-tx">Transcript</label><span class="tag">Simulated</span></div>
                <textarea class="textarea" id="iv-tx" rows="5" aria-describedby="iv-tx-hint"></textarea>
                <span class="hint" id="iv-tx-hint">Simulated transcript: edit it so it matches what you said. The real build transcribes speech on the server.</span>
                <button class="btn-text" type="button" id="iv-again">Speak again</button>
              </div>
              <p class="error-text" id="iv-err" role="alert" hidden></p>
              <p class="hint iv-cap" hidden>The recording reached its limit. Finish your answer now.</p>
              <div class="iv-foot"><span class="hint"><kbd>${mac ? '⌘' : 'Ctrl'}</kbd><kbd>↵</kbd> to submit</span><button class="btn btn-primary" type="button" id="iv-submit" disabled>Submit answer ${arrow}</button></div>
            </div>
          </div>
          <aside class="iv-side" aria-label="Recording">
            <div class="cam-slot" data-slot="dock"></div>
            <div class="buddy" aria-hidden="true">${V.mascot('buddy')}</div>
            <p class="cam-note">${icon('eye', 14)}<span>Visible to you and ${reviewer}. The recording is never used for the score.</span></p>
            <div class="agenda"><p class="agenda-h">Questions</p><ol class="agenda-list"></ol></div>
          </aside>
        </div>

        <div class="iv-analysis" hidden aria-live="polite">
          <div class="card an-card">
            <div class="an-art">${V.mascot('peek')}</div>
            <p class="label">Submitted</p>
            <h1 class="an-title">Reading your answers</h1>
            <ol class="iv-steps">${ANALYSIS.map(t => `<li><span class="st"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path pathLength="1" d="M5 12.5l4.5 4.5L19 7.5"/></svg></span><span>${t}</span></li>`).join('')}</ol>
            <p class="hint">Simulated assessment. It reads your words only.</p>
          </div>
        </div>
      </div>`;
  }

  const camHtml = () => `<figure class="cam" data-state="off">
      <video muted playsinline autoplay></video>
      <span class="cam-empty"><span class="av"><img src="${esc(D.me.avatar)}" alt=""></span><span>Camera off</span></span>
      <figcaption><span class="cam-dev"></span><span class="cam-rec"><i></i><b>REC</b><span class="mono num cam-time">0:00</span></span><span class="cam-idle">Camera on</span></figcaption>
    </figure>`;

  function mount(host, ctx) {
    const { api, sid, presenter } = ctx;
    let view = ctx.view, cam = null, cur = null, mode = 'speak', upload = null, busy = false, destroyed = false, stopWave = null, clock = 0;

    host.className = 'iv';
    host.innerHTML = shell(view);
    $('[data-slot=gate]', host).innerHTML = camHtml();
    V.seg(host);
    const gate = $('.iv-gate', host), main = $('.iv-main', host), analysis = $('.iv-analysis', host), answer = $('.iv-answer', host);
    const camEl = $('.cam', host), video = $('video', camEl), q = $('.iv-q', main);
    const submit = $('#iv-submit', host), done = $('#iv-done', host), text = $('#iv-text', host), tx = $('#iv-tx', host), err = $('#iv-err', host);
    const panes = { speak: $('.iv-speak', host), type: $('.iv-type', host), review: $('.iv-review', host) };
    $('.cam-empty img', camEl).addEventListener('error', e => { e.target.replaceWith(document.createTextNode(V.initials(D.me.name))); });

    const say = m => { err.textContent = m || ''; err.hidden = !m; };

    // ---------- camera card: moves between the pre-join slot and the dock beside the question (FLIP) ----------
    // layout: a function that changes the page around the card; it runs between the two measurements
    async function moveCam(slotName, layout) {
      const slot = $(`[data-slot=${slotName}]`, host);
      const first = camEl.getBoundingClientRect();
      if (layout) layout();
      if (camEl.parentNode === slot) return;
      slot.appendChild(camEl);
      video.play().catch(() => {});
      const last = camEl.getBoundingClientRect();
      if (V.reduced() || !first.width || !last.width) return;
      const t = V.SPRING.soft.duration;
      const a = camEl.animate([{ transform: `translate(${first.left - last.left}px, ${first.top - last.top}px) scale(${first.width / last.width})` }, { transform: 'none' }], { duration: t, easing: V.SPRING.soft.easing });
      await V.settle(a, t);
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
        const track = stream.getVideoTracks()[0];
        $('.cam-dev', camEl).textContent = (track && track.label) || '';
        cam.onLost = () => { if (!destroyed) { V.toast('The camera stopped. Turn it back on to continue.', { kind: 'error' }); toGate('The camera stopped. Turn it back on to continue.'); } };
        ready((track && track.label) || 'Camera');
      } catch (e) {
        if (e && e.name === 'Cancelled') return;
        const box = $('#cam-err', host);
        box.textContent = V.media.explain(e);
        box.hidden = false;
        btn.disabled = false;
      }
    }
    // The camera is on: stay on the pre-join screen with the live picture and a sound bar, and wait for a yes.
    let stopGateWave = null;
    const gateTitle = $('.gate-title', host).textContent, gateSub = $('.gate-sub', host).textContent;
    function ready(device) {
      gate.dataset.state = 'ready';
      $('.gate-title', host).textContent = 'There you are!';
      $('.gate-sub', host).textContent = 'Check that you can see yourself and the bar moves when you talk. Start when you are ready.';
      $('.gate-dev', host).textContent = device;
      $('.gate-check', host).hidden = false;
      $('#cam-on', host).hidden = true;
      $('#cam-go', host).hidden = false;
      $('#cam-go', host).focus({ preventScroll: true });
      V.enter($$('.gate-title, .gate-sub, .gate-check, #cam-go', host), { y: 8, step: 60, dur: 480 });
      if (stopGateWave) stopGateWave();
      stopGateWave = V.media.wave($('.gate-wave', host), cam);
    }
    function unready() {
      delete gate.dataset.state;
      if (stopGateWave) { stopGateWave(); stopGateWave = null; }
      $('.gate-title', host).textContent = gateTitle;
      $('.gate-sub', host).textContent = gateSub;
      $('.gate-check', host).hidden = true;
      $('#cam-on', host).hidden = false;
      $('#cam-go', host).hidden = true;
    }
    function toGate(message) {
      if (cam) cam.takeClip();
      if (stopWave) { stopWave(); stopWave = null; }
      unready();
      camEl.dataset.state = 'off';
      video.srcObject = null;
      main.hidden = true; analysis.hidden = true; gate.hidden = false;
      $('[data-slot=gate]', host).appendChild(camEl);
      $('#cam-on', host).disabled = false;
      const box = $('#cam-err', host);
      box.textContent = message || ''; box.hidden = !message;
    }
    $('#cam-on', host).addEventListener('click', startCamera);
    $('#cam-go', host).addEventListener('click', () => {
      if (stopGateWave) { stopGateWave(); stopGateWave = null; }
      $('#cam-go', host).disabled = true;
      begin();
    });
    $('#cam-skip', host).addEventListener('click', () => { camEl.dataset.state = 'skipped'; begin(); });

    // ---------- progress: the count, the ticks and the question plan ----------
    function paintBar(turn) {
      const total = Math.max(view.interview.standard, view.interview.turns.length);
      $('.iv-count', main).innerHTML = turn.source === 'follow-up' ? '<b>One more question</b>' : `<b>Question ${turn.turn}</b> of ${view.interview.standard}`;
      $('.iv-ticks', main).innerHTML = Array.from({ length: total }, (_, i) => `<i data-state="${i + 1 < turn.turn ? 'done' : i + 1 === turn.turn ? 'on' : ''}"></i>`).join('');
      $('.iv-label', main).textContent = turn.label;
      $('.iv-src', main).hidden = turn.source !== 'follow-up';
      // the plan: the two standard questions of this attempt, then the follow-up (asked only when an answer stays weak)
      const qs = D.sets[Math.min(view.attempt, D.sets.length) - 1].questions, turns = view.interview.turns;
      const probe = turns.find(t => t.source === 'follow-up');
      const plan = [{ n: '1', label: qs.implementation.label }, { n: '2', label: qs.rationale.label }, { n: '+', label: probe ? probe.label : 'Follow-up', note: probe ? '' : 'Only if needed' }];
      $('.agenda-list', host).innerHTML = plan.map((p, i) => {
        const at = i + 1, st = at < turn.turn ? 'done' : at === turn.turn ? 'on' : '';
        return `<li data-state="${st}"><span>${st === 'done' ? icon('check', 11) : p.n}</span><b>${esc(p.label)}</b>${p.note ? `<em>${esc(p.note)}</em>` : ''}</li>`;
      }).join('');
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
      done.innerHTML = 'Sending';
      try {
        const clip = await cam.takeClip();
        if (!clip) throw new Error('Nothing was recorded. Try again.');
        upload = await send(clip, 'voice');
        tx.value = upload.transcript || '';
        setMode('speak');
        V.enter(panes.review, { y: 6, dur: 420 });
      } catch (e) {
        say((e && e.message) || 'The recording could not be sent. Try again.');
        cam.startClip();
      } finally { busy = false; done.innerHTML = `${icon('check', 14)}Done speaking`; refresh(); }
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

    // ---------- the buddy hauls each question in on a rope ----------
    const buddy = $('.buddy', host), hand = $('.b-hand', buddy), arm = $('.b-arm', buddy), hook = $('.iv-hook', main), pullEl = $('.iv-pull', main);
    let rope = null;
    const ropeSvg = () => {
      if (!rope) {
        rope = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        rope.setAttribute('class', 'rope');
        rope.setAttribute('aria-hidden', 'true');
        rope.innerHTML = '<path/><circle r="4"/>';
        document.body.appendChild(rope);
      }
      return rope;
    };
    const mid = r => [r.left + r.width / 2, r.top + r.height / 2];
    function drawRope(a, b, sag) {
      const [ax, ay] = a, [bx, by] = b, r = ropeSvg();
      r.firstChild.setAttribute('d', `M${ax.toFixed(1)} ${ay.toFixed(1)}Q${((ax + bx) / 2).toFixed(1)} ${(Math.max(ay, by) + sag).toFixed(1)} ${bx.toFixed(1)} ${by.toFixed(1)}`);
      r.lastChild.setAttribute('cx', bx.toFixed(1));
      r.lastChild.setAttribute('cy', by.toFixed(1));
    }
    // Tug of war: the penguin leans back and hauls the question in a hand-over-hand at a time. Each heave gains a little,
    // the question slips back a touch, and the rope stays taut and trembling until the question lands.
    // Returns false when there is no room for the penguin (narrow screens) or motion is reduced.
    async function pull() {
      if (V.reduced() || !buddy.getClientRects().length) return false;
      const X = $('.iv-col', main).getBoundingClientRect().right + 60, N = 7, dur = 3600;
      const q_ = [], b_ = [], a_ = [];
      const at = (x, deg) => `translateX(${(-X * x).toFixed(1)}px) rotate(${deg}deg)`;
      let cur = 1;
      for (let k = 0; k < N; k++) {
        const t = k / N, seg = 1 / N, tilt = k % 2 ? 1.6 : -1.6;
        // each heave gains a little (less near the end, where it resists most), then the question slips back a touch
        const gain = 1 - Math.pow((k + 1) / N, 0.9), slipped = k < N - 1 ? gain + 0.035 : gain;
        q_.push({ transform: at(cur, -tilt / 2), offset: t, easing: 'cubic-bezier(.25,.9,.35,1)' });
        q_.push({ transform: at(gain, tilt), offset: t + seg * 0.45, easing: 'cubic-bezier(.5,0,.6,1)' });
        q_.push({ transform: at(slipped, -tilt / 2), offset: t + seg * 0.8, easing: 'linear' });
        cur = slipped;
        b_.push({ transform: 'translateX(4px) rotate(11deg)', offset: t }, { transform: 'translateX(9px) rotate(19deg)', offset: t + seg * 0.45 }, { transform: 'translateX(6px) rotate(14deg)', offset: t + seg * 0.8 });
        a_.push({ transform: 'rotate(10deg)', offset: t }, { transform: 'rotate(-34deg)', offset: t + seg * 0.45 }, { transform: 'rotate(4deg)', offset: t + seg * 0.8 });
      }
      q_.push({ transform: 'translateX(-10px) rotate(-1deg)', offset: 0.985, easing: 'cubic-bezier(.34,1.56,.64,1)' }, { transform: 'none', offset: 1 });
      b_.unshift({ transform: 'none', offset: 0 }); b_[1].offset = 0.03; b_.push({ transform: 'translateX(-3px) rotate(-6deg)', offset: 0.99 }, { transform: 'none', offset: 1 });
      a_.unshift({ transform: 'rotate(0)', offset: 0 }); a_[1].offset = 0.03; a_.push({ transform: 'rotate(0)', offset: 1 });
      buddy.dataset.pulling = '';
      pullEl.animate(q_, { duration: dur, fill: 'backwards' });
      buddy.animate(b_, { duration: dur, easing: 'ease-in-out' });
      arm.animate(a_, { duration: dur, easing: 'ease-in-out' });
      // taut the whole way, with a tremble; after it lands the penguin lets go, the rope sags and is reeled in
      const t0 = performance.now(), reel = 560;
      let sag = 4;
      ropeSvg().style.opacity = '1';
      await new Promise(done => {
        const tick = now => {
          if (destroyed) { done(); return; }
          const t = now - t0, a = mid(hand.getBoundingClientRect());
          let b = mid(hook.getBoundingClientRect());
          if (t < dur) sag = 2 + Math.random() * 3;
          else {
            const k = Math.min(1, (t - dur) / reel), e = k * k * (3 - 2 * k);
            sag += (40 * (1 - e) - sag) * 0.3;
            b = [b[0] + (a[0] - b[0]) * e, b[1] + (a[1] - b[1]) * e];
            if (k >= 1) { done(); return; }
          }
          drawRope(a, b, sag);
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
        setTimeout(done, dur + reel + 400); // a hidden tab stops frames; never hang on the show
      });
      ropeSvg().style.opacity = '0';
      delete buddy.dataset.pulling;
      return true;
    }
    // the question text with the pull request title (between the curly quotes) in violet
    function setQuestion(text) {
      const m = /“[^”]*”/.exec(text);
      q.innerHTML = m ? `${esc(text.slice(0, m.index))}<span class="hl">${esc(m[0])}</span>${esc(text.slice(m.index + m[0].length))}` : esc(text);
    }

    // ---------- flow ----------
    async function leaveQuestion() {
      if (stopWave) { stopWave(); stopWave = null; }
      if (!V.reduced()) buddy.animate([{ transform: 'none' }, { transform: 'translateY(-18px) rotate(-10deg)', offset: 0.4 }, { transform: 'none' }], { duration: V.SPRING.bounce.duration, easing: V.SPRING.bounce.easing });
      const col = $('.iv-col', main);
      if (V.reduced()) { answer.hidden = true; return; }
      const a = col.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-8px)' }], { duration: 200, easing: V.EASE.out, fill: 'forwards' });
      await V.settle(a, 200);
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
      setQuestion(turn.question);
      V.enter($$('.iv-bar, .iv-ground', main), { y: 6, step: 50, dur: 420 });
      if (!await pull().catch(() => false)) await V.typeWords(q, turn.question, { perWord: 32 }).then(() => setQuestion(turn.question));
      if (destroyed || cur !== turn) return;
      answer.hidden = false;
      V.enter(answer, { y: 10, dur: 480 });
      if (cam) { cam.startClip(); paintClock(); }
      // without a camera there is no microphone either, so only typing is possible
      $('.iv-tabs', host).hidden = !cam;
      $('.iv-rec-hint', host).hidden = !cam;
      setMode(cam ? 'speak' : 'type');
      (cam ? done : text).focus({ preventScroll: true });
    }
    async function begin() {
      let turn = view.interview.turns.find(t => !t.answered);
      if (!turn) {
        try {
          const res = await api.interviewNext(sid, { version: view.version }, { presenter });
          view = res.view; ctx.onView(view);
          turn = view.interview.turns[view.interview.turns.length - 1];
        } catch (e) { ctx.fail(e); $('#cam-on', host).disabled = false; return; }
      }
      if (destroyed) return;
      // the camera flies from the pre-join screen to its dock first; the question types in after it lands
      const col = $('.iv-col', main);
      col.style.visibility = 'hidden';
      await moveCam('dock', () => { gate.hidden = true; main.hidden = false; });
      col.style.visibility = '';
      if (destroyed) return;
      V.enter($$('.cam-note, .agenda', main), { y: 6, step: 60, dur: 420 });
      // the buddy pops up beside the camera before the first pull
      if (!V.reduced()) await V.settle(buddy.animate([{ opacity: 0, transform: 'translateY(40px) scale(.5)' }, { opacity: 1, transform: 'none' }], { duration: V.SPRING.bounce.duration, easing: V.SPRING.bounce.easing }), V.SPRING.bounce.duration);
      await ask(turn);
    }

    async function analyse() {
      if (cam) { await cam.takeClip(); cam.destroy(); cam = null; } // the interview is over: release the camera
      video.srcObject = null;
      camEl.dataset.state = 'done';
      main.hidden = true; analysis.hidden = false;
      V.enter($('.an-card', analysis), { y: 10, dur: 520 });
      const steps = $$('.iv-steps li', analysis), gap = V.reduced() ? 0 : 560, lead = V.reduced() ? 0 : 350;
      steps.forEach((li, i) => {
        setTimeout(() => { li.dataset.state = 'active'; }, lead + i * gap);
        setTimeout(() => {
          li.dataset.state = 'done';
          if (!V.reduced()) $('path', li).animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: 320, easing: V.EASE.io, fill: 'backwards' });
        }, lead + (i + 1) * gap);
      });
      const minimum = V.sleep(lead + steps.length * gap + 250);
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
    (async () => {
      // if the browser already allows the camera for this site, turn it on straight away (the start still waits for a yes)
      let granted = false;
      try { granted = (await navigator.permissions.query({ name: 'camera' })).state === 'granted'; } catch { /* not supported */ }
      if (destroyed) return;
      gate.hidden = false;
      V.enter($$('.gate-preview, .gate-panel > *', gate), { y: 8, step: 40, dur: 480 });
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
        if (stopGateWave) stopGateWave();
        if (rope) rope.remove();
        if (cam) cam.destroy();
      }
    };
  }

  V.interview = { mount };
  window.VivaInterview = V.interview;
})();
