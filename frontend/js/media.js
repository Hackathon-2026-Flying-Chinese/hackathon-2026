/* window.VivaMedia: the interview camera. Camera and microphone stay on for the whole interview, and each answer is
   recorded as one clip for the senior reviewer. The clip is not used by the score. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const { $ } = V;

  const recBar = show => { const b = $('#rec-bar'); if (b) b.hidden = !show; };
  const MIMES = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'];
  const pickMime = () => (window.MediaRecorder && MIMES.find(t => MediaRecorder.isTypeSupported(t))) || '';

  function explain(err) {
    const name = err && err.name;
    if (name === 'InsecureContext') return 'The camera needs localhost or https. Open this page from http://127.0.0.1.';
    if (name === 'NotAllowedError') return 'Camera or microphone access is blocked. Allow both for this site in the browser, then try again.';
    if (name === 'NotFoundError') return 'No camera or microphone was found. Connect one, then try again.';
    if (name === 'NotReadableError') return 'Another app is using the camera. Close it, then try again.';
    return 'The camera could not start. Try again.';
  }

  function camera({ maxSeconds = 180, onCap } = {}) {
    let stream = null, audioCtx = null, analyser = null, buf = null, clip = null, capTimer = 0, capped = null, destroyed = false, token = 0;

    function release() {
      if (stream) stream.getTracks().forEach(t => t.stop());
      stream = null;
      if (audioCtx) { const c = audioCtx; audioCtx = null; analyser = null; c.close().catch(() => {}); }
    }

    // One permission request; a later destroy() or a second start() cancels this one and frees its tracks.
    async function start() {
      const mine = ++token;
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw Object.assign(new Error('insecure'), { name: 'InsecureContext' });
      const s = await navigator.mediaDevices.getUserMedia({ audio: true, video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } } });
      if (destroyed || mine !== token) { s.getTracks().forEach(t => t.stop()); throw Object.assign(new Error('cancelled'), { name: 'Cancelled' }); }
      release();
      stream = s;
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) {
        audioCtx = new Ctx();
        audioCtx.resume().catch(() => {});
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        buf = new Uint8Array(analyser.fftSize);
        audioCtx.createMediaStreamSource(new MediaStream(s.getAudioTracks())).connect(analyser);
      }
      s.getTracks().forEach(t => t.addEventListener('ended', () => { if (!destroyed && stream === s && ctl.onLost) ctl.onLost(); }));
      return s;
    }

    function stop() {
      return new Promise(res => {
        const c = clip;
        if (!c) { res(null); return; }
        clip = null;
        clearTimeout(capTimer);
        recBar(false);
        const done = () => res({ blob: new Blob(c.chunks, { type: c.mr.mimeType || 'video/webm' }), duration: (performance.now() - c.t0) / 1000, kind: 'video' });
        if (c.mr.state !== 'inactive') { c.mr.onstop = done; c.mr.stop(); } else done();
      });
    }

    // A clip covers the whole time an answer is open, spoken or typed. A timer (not a frame loop) enforces the cap.
    function startClip() {
      if (!stream || clip || destroyed) return false;
      const chunks = [], mime = pickMime();
      const mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      mr.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
      clip = { mr, chunks, t0: performance.now() };
      capped = null;
      mr.start(500);
      recBar(true);
      capTimer = setTimeout(() => { capped = stop(); if (onCap) onCap(); }, maxSeconds * 1000);
      return true;
    }
    function takeClip() { const p = capped || stop(); capped = null; return p; }

    function level() {
      if (!analyser) return 0;
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
      return Math.min(1, Math.sqrt(sum / buf.length) * 4.2);
    }

    function destroy() {
      destroyed = true; token++;
      clearTimeout(capTimer);
      if (clip) { const c = clip; clip = null; c.mr.onstop = null; try { c.mr.stop(); } catch { /* already stopped */ } }
      capped = null;
      recBar(false);
      release();
    }

    // an object literal keeps the getters live (Object.assign would copy their current values)
    const ctl = {
      onLost: null, start, startClip, takeClip, level, destroy,
      get stream() { return stream; },
      get recording() { return !!clip; },
      elapsed: () => (clip ? (performance.now() - clip.t0) / 1000 : 0)
    };
    return ctl;
  }

  // Scrolling level meter drawn from the microphone. Returns a stop function.
  function wave(canvas, cam) {
    const bars = [];
    let raf = 0, last = 0, alive = true;
    const fit = () => {
      const r = canvas.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(r.width * d)); canvas.height = Math.max(1, Math.round(r.height * d));
    };
    function draw() {
      const g = canvas.getContext('2d'), w = canvas.width, h = canvas.height, st = getComputedStyle(document.documentElement);
      const ink = st.getPropertyValue('--lilac-strong').trim(), dim = st.getPropertyValue('--accent-line').trim(), acc = st.getPropertyValue('--sky-strong').trim();
      const d = w / (canvas.getBoundingClientRect().width || w), bw = 3 * d, gap = 4 * d, n = Math.floor(w / (bw + gap));
      g.clearRect(0, 0, w, h);
      for (let i = 0; i < n; i++) {
        const idx = bars.length - n + i, a = idx >= 0 ? bars[idx] : 0, bh = Math.max(2 * d, a * h * 0.92);
        g.fillStyle = a > 0.03 ? (i > n - 6 ? acc : ink) : dim;
        g.beginPath();
        if (g.roundRect) g.roundRect(i * (bw + gap), (h - bh) / 2, bw, bh, bw / 2); else g.rect(i * (bw + gap), (h - bh) / 2, bw, bh);
        g.fill();
      }
    }
    function tick(now) {
      if (!alive) return;
      if (now - last > 34) { bars.push(cam.level()); if (bars.length > 600) bars.splice(0, 300); last = now; draw(); }
      raf = requestAnimationFrame(tick);
    }
    fit(); draw();
    const ro = new ResizeObserver(() => { fit(); draw(); });
    ro.observe(canvas);
    raf = requestAnimationFrame(tick);
    return () => { alive = false; cancelAnimationFrame(raf); ro.disconnect(); };
  }

  V.media = { camera, wave, recBar, explain };
  window.VivaMedia = V.media;
})();
