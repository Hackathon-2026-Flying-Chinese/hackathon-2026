/* Shared helpers: DOM, icons, motion primitives (spring, enter, word reveal, odometer), theme, toast, dialog. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const reducedQuery = matchMedia('(prefers-reduced-motion: reduce)');
  const reduced = () => reducedQuery.matches;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const pad = n => String(n).padStart(2, '0');

  const fmtTime = sec => `${Math.floor(sec / 60)}:${pad(Math.floor(sec % 60))}`;
  const fmtClock = ts => { const d = new Date(ts * 1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const fmtDay = ts => new Date(ts * 1000).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
  const initials = name => String(name || '?').trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase();

  // ---------- icons (composed from simple strokes; no icon font or CDN so the demo works offline) ----------
  const ICONS = {
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    dash: '<path d="M7 12h10"/>',
    mic: '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3"/>',
    camera: '<rect x="3" y="6" width="13" height="12" rx="3"/><path d="M16 10.5l5-3v9l-5-3"/>',
    keyboard: '<rect x="3" y="6" width="18" height="12" rx="2.5"/><path d="M7 10h.01M11 10h.01M15 10h.01M7.5 14h9"/>',
    play: '<path d="M8 5.5v13l11-6.5z"/>',
    pause: '<path d="M8.5 6v12M15.5 6v12"/>',
    lock: '<rect x="5" y="10.5" width="14" height="10" rx="3"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/>',
    moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="3"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    external: '<path d="M14 5h5v5M19 5l-8 8M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.6-5.9M20 4v4.5h-4.5"/>',
    chevron: '<path d="M9 6l6 6-6 6"/>',
    flag: '<path d="M6 21V4M6 5h11l-2 4 2 4H6"/>',
    trash: '<path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6"/>',
    pr: '<circle cx="6" cy="6" r="2.2"/><circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="18" r="2.2"/><path d="M6 8.2v7.6M18 15.8V9.5A3.5 3.5 0 0 0 14.5 6H11"/><path d="M13.2 3.6L10.8 6l2.4 2.4"/>',
    branch: '<circle cx="6.5" cy="5.5" r="2.2"/><circle cx="6.5" cy="18.5" r="2.2"/><circle cx="17.5" cy="7.5" r="2.2"/><path d="M6.5 7.7v8.6M17.5 9.7c0 3.8-3.2 4.8-6.4 5.6-2.2.6-3.8 1.3-4.4 2.4"/>',
    commit: '<circle cx="12" cy="12" r="3.2"/><path d="M3 12h5.8M15.2 12H21"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.8"/>',
    eye: '<path d="M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    shield: '<path d="M12 3.2l7.2 2.9v5.3c0 4.4-3 8-7.2 9.4-4.2-1.4-7.2-5-7.2-9.4V6.1z"/><path d="M8.9 12.1l2.2 2.2 4.1-4.3"/>',
    user: '<circle cx="12" cy="8.5" r="3.7"/><path d="M4.8 20c1.2-3.5 4-5.3 7.2-5.3s6 1.8 7.2 5.3"/>',
    file: '<path d="M13.5 3.5H7.5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V8.5z"/><path d="M13.5 3.5v5h5"/>',
    list: '<path d="M9 6.5h10.5M9 12h10.5M9 17.5h10.5M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01"/>',
    award: '<circle cx="12" cy="9" r="5.2"/><path d="M8.7 13.2L7.3 20.5l4.7-2.4 4.7 2.4-1.4-7.3"/>',
    trend: '<path d="M3.5 17l5.5-5.5 4 4 7.5-7.5"/><path d="M15 8h5.5v5.5"/>',
    chat: '<path d="M4.5 18.5V7A2.5 2.5 0 0 1 7 4.5h10A2.5 2.5 0 0 1 19.5 7v7a2.5 2.5 0 0 1-2.5 2.5H8.5z"/>',
    scan: '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M8 10h8M8 14h5"/>',
    inbox: '<path d="M3.5 13.5L6 5.5h12l2.5 8v4.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M3.5 13.5h5l1.5 2.5h4l1.5-2.5h5"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>'
  };
  const icon = (name, size = 16) => `<svg class="ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${size <= 16 ? 1.9 : 1.75}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;

  // ---------- motion ----------
  const EASE = { out: 'cubic-bezier(.2,.8,.2,1)', io: 'cubic-bezier(.65,0,.35,1)' };
  const linearOk = () => window.CSS && CSS.supports('transition-timing-function', 'linear(0, 1)');

  // Damped spring step response, sampled into a linear() easing so CSS and WAAPI share one curve.
  function spring(stiffness = 170, damping = 26) {
    const dt = 1 / 120, pts = [];
    let x = 0, v = 0, calm = 0;
    for (let t = 0; t < 4; t += dt) {
      v += (-stiffness * (x - 1) - damping * v) * dt;
      x += v * dt;
      pts.push(x);
      if (Math.abs(x - 1) < 0.0008 && Math.abs(v) < 0.01) { if (++calm > 6) break; } else calm = 0;
    }
    const step = Math.max(1, Math.floor(pts.length / 48)), out = [0];
    for (let i = step - 1; i < pts.length; i += step) out.push(+pts[i].toFixed(4));
    out.push(1);
    return { easing: linearOk() ? `linear(${out.join(', ')})` : EASE.out, duration: Math.round(pts.length * dt * 1000) };
  }
  // soft is critically damped (big moves), snap overshoots a little (controls), bounce overshoots on purpose (small playful things)
  const SPRING = { soft: spring(170, 26), snap: spring(260, 24), bounce: spring(210, 14) };

  // Fade and rise for one or many elements. WAAPI with backwards fill: no inline styles are left behind.
  function enter(els, o = {}) {
    if (reduced()) return;
    const { y = 8, step = 40, delay = 0, dur = 480, ease = EASE.out } = o;
    [].concat(els).filter(Boolean).forEach((el, i) => {
      el.animate([{ opacity: 0, transform: `translateY(${y}px)` }, { opacity: 1, transform: 'none' }], { duration: dur, delay: delay + i * step, easing: ease, fill: 'backwards' });
    });
  }

  // Elements marked data-reveal wait (hidden) until they scroll into view; IntersectionObserver, no scroll listeners.
  const revealIO = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      revealIO.unobserve(e.target);
      e.target.classList.remove('pre');
      enter(e.target, { y: 10, dur: 560 });
    });
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0 });
  function observe(root = document) {
    $$('[data-reveal]', root).forEach(el => {
      if (!reduced()) el.classList.add('pre');
      revealIO.observe(el);
    });
  }

  // Word-by-word reveal for a question. Returns a promise that resolves when the text is fully shown.
  function typeWords(el, text, { perWord = 30 } = {}) {
    const parts = text.split(/(\s+)/);
    el.innerHTML = parts.map(p => (/^\s+$/.test(p) ? p : `<span class="w">${esc(p)}</span>`)).join('');
    if (reduced()) return Promise.resolve();
    const spans = $$('.w', el);
    spans.forEach((s, i) => s.animate([{ opacity: 0, transform: 'translateY(4px)', filter: 'blur(4px)' }, { opacity: 1, transform: 'none', filter: 'blur(0)' }], { duration: 420, delay: i * perWord, easing: EASE.out, fill: 'backwards' }));
    return sleep((spans.length - 1) * perWord + 460);
  }

  // Wait for an animation, but never longer than its duration: a hidden tab stops producing frames,
  // and control flow must not hang on a decorative transition.
  const settle = (anim, ms) => Promise.race([anim.finished.then(() => {}, () => {}), sleep(ms + 120)]);

  // Odometer: digit columns roll to the new value; separators and length changes fade.
  function odometer(el, text) {
    el.classList.add('odo');
    el.setAttribute('role', 'img');
    let cells = [];
    const digitCell = d => {
      const w = document.createElement('span');
      w.className = 'odo-d';
      w.innerHTML = `<span class="odo-col">${'0123456789'.split('').map(n => `<i>${n}</i>`).join('')}</span>`;
      w.firstChild.style.transform = `translateY(${-d}em)`;
      return { ch: String(d), el: w, digit: true };
    };
    const sepCell = ch => {
      const w = document.createElement('span');
      w.className = 'odo-s';
      w.textContent = ch;
      return { ch, el: w, digit: false };
    };
    const make = ch => (/\d/.test(ch) ? digitCell(+ch) : sepCell(ch));
    function set(next, { duration = 1000, stagger = 42 } = {}) {
      next = String(next);
      el.setAttribute('aria-label', next);
      const anim = !reduced() && duration > 0;
      const n = Math.max(cells.length, next.length);
      const out = [];
      for (let i = 0; i < n; i++) {
        const old = cells[i], ch = next[i];
        const rank = n - 1 - i; // cascade from the last digit
        if (ch === undefined) {
          if (anim) old.el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 240, easing: EASE.out, fill: 'forwards' }).finished.then(() => old.el.remove()).catch(() => old.el.remove());
          else old.el.remove();
          continue;
        }
        if (old && old.digit && /\d/.test(ch)) {
          const col = old.el.firstChild, from = +old.ch, to = +ch;
          if (from !== to && anim) col.animate([{ transform: `translateY(${-from}em)` }, { transform: `translateY(${-to}em)` }], { duration, delay: rank * stagger, easing: SPRING.soft.easing, fill: 'both' }).finished.then(() => { col.style.transform = `translateY(${-to}em)`; }).catch(() => {});
          else col.style.transform = `translateY(${-to}em)`;
          old.ch = ch;
          out.push(old);
        } else if (old && !old.digit && !/\d/.test(ch)) {
          old.el.textContent = ch; old.ch = ch; out.push(old);
        } else {
          const cell = make(ch);
          if (old) old.el.replaceWith(cell.el); else el.appendChild(cell.el);
          if (anim) cell.el.animate([{ opacity: 0, transform: 'translateY(30%)' }, { opacity: 1, transform: 'none' }], { duration: 420, delay: old ? 0 : rank * stagger, easing: EASE.out, fill: 'backwards' });
          out.push(cell);
        }
      }
      cells = out;
    }
    set(text, { duration: 0 });
    return { set };
  }

  // Segmented control: a sliding thumb follows the checked radio.
  function seg(root) {
    $$('[data-seg]', root).forEach(el => {
      const inputs = $$('input', el);
      const sync = () => {
        el.style.setProperty('--n', inputs.length);
        const i = inputs.findIndex(x => x.checked);
        el.style.setProperty('--i', Math.max(0, i));
        el.toggleAttribute('data-empty', i < 0);
      };
      inputs.forEach(x => x.addEventListener('change', sync));
      sync();
    });
  }

  // ---------- the characters: one per step of a check, drawn from plain shapes ----------
  // Eyes are .eye groups (a white .eye-w and a .pupil); eyes() moves every pupil toward the pointer.
  const eyeSvg = (cx, cy, r, pr, max) => `<g class="eye" data-max="${max}"><circle class="eye-w" cx="${cx}" cy="${cy}" r="${r}" fill="#fff"/><g class="pupil"><circle cx="${cx}" cy="${cy}" r="${pr}" style="fill:var(--pupil)"/><circle cx="${cx + pr * .38}" cy="${cy - pr * .38}" r="${(pr * .32).toFixed(1)}" fill="#fff"/></g></g>`;
  // a seal with scalloped edges, the "approved" stamp
  function seal(cx, cy, R, n, a) {
    let d = '';
    for (let i = 0; i <= n * 8; i++) {
      const t = (i / (n * 8)) * Math.PI * 2, r = R + a * Math.cos(n * t);
      d += `${i ? 'L' : 'M'}${(cx + r * Math.cos(t)).toFixed(1)} ${(cy + r * Math.sin(t)).toFixed(1)}`;
    }
    return d + 'Z';
  }
  const INK = 'stroke="#17151f" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none"';
  const WHITE = 'stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"';
  const MASCOTS = {
    // interview: a speech bubble that talks
    talk: `<path d="M140 46c6 7 6 19 0 26" style="stroke:var(--lilac-strong)" stroke-width="5" stroke-linecap="round" fill="none" opacity=".35"/><path d="M150 38c11 12 11 30 0 42" style="stroke:var(--lilac-strong)" stroke-width="5" stroke-linecap="round" fill="none" opacity=".18"/>
      <path d="M48 96L38 124L74 100Z" style="fill:var(--lilac-strong);stroke:var(--lilac-strong)" stroke-width="8" stroke-linejoin="round"/><rect x="22" y="18" width="110" height="84" rx="32" style="fill:var(--lilac-strong)"/>
      ${eyeSvg(62, 54, 13, 6.5, 5.5)}${eyeSvg(94, 54, 13, 6.5, 5.5)}<path d="M68 78q9 9 18 0" ${WHITE}/>`,
    // assessment: a magnifying glass reading the words, with one big eye
    peek: `<rect x="12" y="30" width="58" height="10" rx="5" style="fill:var(--sky-strong)" opacity=".2"/><rect x="12" y="50" width="42" height="10" rx="5" style="fill:var(--sky-strong)" opacity=".2"/><rect x="12" y="70" width="52" height="10" rx="5" style="fill:var(--sky-strong)" opacity=".2"/><rect x="12" y="90" width="30" height="10" rx="5" style="fill:var(--sky-strong)" opacity=".2"/>
      <path d="M120 90L142 114" style="stroke:var(--sky-strong)" stroke-width="15" stroke-linecap="round"/><circle cx="98" cy="62" r="37" fill="#fff" style="stroke:var(--sky-strong)" stroke-width="11"/>
      ${eyeSvg(98, 62, 25, 12, 10)}`,
    // senior review: round glasses, one raised eyebrow, a moustache
    sage: `<path d="M68 26q4-14 14-6q6-12 14-2" style="stroke:var(--lemon-strong)" stroke-width="6" stroke-linecap="round" fill="none"/><circle cx="80" cy="74" r="50" style="fill:var(--lemon-strong)"/>
      ${eyeSvg(60, 68, 15, 6, 6)}${eyeSvg(100, 68, 15, 6, 6)}
      <circle cx="60" cy="68" r="15" ${INK}/><circle cx="100" cy="68" r="15" ${INK}/><path d="M75 66q5-4 10 0M45 64L33 60M115 64L127 60" ${INK}/>
      <path d="M47 45q11-9 24-3" ${INK}/><path d="M89 48q11-3 23 1" ${INK}/>
      <path d="M63 98c5-8 12-7 17-1c5-6 12-7 17 1c-5 5-12 5-17-1c-5 6-12 6-17 1z" fill="#17151f"/>`,
    // check passes: an approval seal, very pleased, with confetti
    yay: `<rect x="16" y="24" width="12" height="7" rx="2" transform="rotate(-24 22 27)" style="fill:var(--lilac-strong)"/><circle cx="142" cy="30" r="5" style="fill:var(--sky-strong)"/><rect x="130" y="104" width="12" height="7" rx="2" transform="rotate(28 136 107)" style="fill:var(--lemon-strong)"/><circle cx="22" cy="108" r="4.5" style="fill:var(--sky-strong)"/><path d="M40 8l3.5 7 7.5 1-5.5 5 1.5 7.5-7-3.5-7 3.5 1.5-7.5-5.5-5 7.5-1z" style="fill:var(--lemon-strong)"/>
      <path d="${seal(80, 72, 46, 12, 4)}" style="fill:var(--mint-strong)"/>
      <path d="M60 66q7-10 14 0M86 66q7-10 14 0" ${WHITE}/><path d="M64 82q16 17 32 0" ${WHITE}/><circle cx="54" cy="82" r="5" fill="#fff" opacity=".28"/><circle cx="106" cy="82" r="5" fill="#fff" opacity=".28"/>`
  };
  // the interview buddy: a penguin in a violet tie. It hauls each question in on a rope, then hangs around the camera.
  MASCOTS.buddy = `<path d="M44 15q-3-7 3-10" style="stroke:var(--peng)" stroke-width="3" stroke-linecap="round" fill="none"/>
      <ellipse cx="35" cy="104" rx="8.5" ry="3.8" fill="#ffab2e"/><ellipse cx="55" cy="104" rx="8.5" ry="3.8" fill="#ffab2e"/>
      <path d="M45 14c-17 0-26 16-26 38v24c0 16 11 26 26 26s26-10 26-26V52c0-22-9-38-26-38z" style="fill:var(--peng)"/>
      <path d="M45 41c-11 0-16 10-16 22v13c0 11 7 18 16 18s16-7 16-18V63c0-12-5-22-16-22z" fill="#fff"/>
      <path d="M67 53c7 6 9 16 6 25-6-4-9-12-8-21z" style="fill:var(--peng)"/>
      <g class="b-arm"><path d="M23 53c-7 4-12 10-14 17 7-1 12-5 15-11z" style="fill:var(--peng)"/><circle class="b-hand" cx="10" cy="69" r="2.5" style="fill:var(--peng)"/></g>
      ${eyeSvg(37, 30, 6.5, 3.2, 2.5)}${eyeSvg(53, 30, 6.5, 3.2, 2.5)}
      <path d="M40.5 37.5h9l-4.5 5.5z" fill="#ffab2e" stroke="#ffab2e" stroke-width="2" stroke-linejoin="round"/>
      <rect x="42.5" y="44" width="5" height="3.6" rx="1.2" style="fill:var(--accent)"/><path d="M43 47.4h4l1.6 11-3.6 3.6-3.6-3.6z" style="fill:var(--accent)"/>
      <path class="b-sweat" d="M70 17c2 3 3 5 1.6 6.4s-4.2.4-4.2-1.6 2.6-4.8 2.6-4.8z" style="fill:var(--sky-strong)"/>`;
  const VIEWBOX = { buddy: '0 0 90 120' };
  function mascot(kind) {
    const blink = (4 + Math.random() * 3).toFixed(1), delay = (Math.random() * 3).toFixed(1);
    return `<svg class="mascot" data-kind="${kind}" viewBox="${VIEWBOX[kind] || '0 0 160 140'}" style="--blink:${blink}s;--blink-delay:-${delay}s" aria-hidden="true">${MASCOTS[kind]}</svg>`;
  }
  // Every pupil on the page looks toward the pointer (one delegated listener, one frame at a time).
  function eyes() {
    if (!matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    let raf = 0, px = 0, py = 0;
    const look = () => {
      raf = 0;
      $$('.mascot .eye').forEach(e => {
        const w = e.firstElementChild, p = e.lastElementChild, r = w.getBoundingClientRect();
        if (!r.width) return;
        const scale = r.width / (2 * w.r.baseVal.value), dx = (px - r.left - r.width / 2) / scale, dy = (py - r.top - r.height / 2) / scale;
        const d = Math.hypot(dx, dy) || 1, m = Math.min(+e.dataset.max, d / 6);
        p.style.transform = `translate(${(dx / d * m).toFixed(2)}px, ${(dy / d * m).toFixed(2)}px)`;
      });
    };
    document.addEventListener('pointermove', e => { px = e.clientX; py = e.clientY; if (!raf) raf = requestAnimationFrame(look); }, { passive: true });
    document.documentElement.addEventListener('pointerleave', () => $$('.mascot .pupil').forEach(p => { p.style.transform = ''; }));
  }

  // A burst of paper from an element, for the one moment that deserves it.
  function confetti(from, count = 70) {
    if (reduced() || !from) return;
    const r = from.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
    const st = getComputedStyle(document.documentElement), colors = ['--lilac-strong', '--sky-strong', '--lemon-strong', '--mint-strong', '--accent'].map(c => st.getPropertyValue(c).trim());
    const host = document.createElement('div');
    host.className = 'confetti';
    document.body.appendChild(host);
    for (let i = 0; i < count; i++) {
      const p = document.createElement('i'), a = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.1, v = 180 + Math.random() * 260, spin = (Math.random() - 0.5) * 900;
      p.style.cssText = `left:${x}px;top:${y}px;background:${colors[i % colors.length]}`;
      host.appendChild(p);
      const dx = Math.cos(a) * v, dy = Math.sin(a) * v;
      p.animate([
        { transform: 'translate(0, 0) rotate(0deg)', opacity: 1 },
        { transform: `translate(${dx}px, ${dy}px) rotate(${spin * 0.6}deg)`, opacity: 1, offset: 0.45 },
        { transform: `translate(${dx * 1.25}px, ${dy + 320}px) rotate(${spin}deg)`, opacity: 0 }
      ], { duration: 1300 + Math.random() * 700, easing: 'cubic-bezier(.15,.7,.35,1)', fill: 'forwards' });
    }
    setTimeout(() => host.remove(), 2200);
  }

  // Page change from a button: a violet circle grows out of it and covers the screen. Returns a function that lifts it.
  async function portal(from) {
    if (reduced() || !from) return () => {};
    const r = from.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
    const R = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    const o = document.createElement('div');
    o.className = 'portal';
    document.body.appendChild(o);
    await settle(o.animate({ clipPath: [`circle(${r.height / 2}px at ${x}px ${y}px)`, `circle(${R}px at ${x}px ${y}px)`] }, { duration: 460, easing: 'cubic-bezier(.7,0,.25,1)', fill: 'forwards' }), 460);
    return () => settle(o.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 380, easing: EASE.out, fill: 'forwards' }), 380).then(() => o.remove());
  }

  // ---------- theme ----------
  function theme() {
    let saved = null;
    try { saved = localStorage.getItem('viva-theme'); } catch { /* storage may be blocked */ }
    return saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function setTheme(next, origin) {
    const apply = () => { document.documentElement.dataset.theme = next; };
    try { localStorage.setItem('viva-theme', next); } catch { /* ignore */ }
    if (!document.startViewTransition || reduced()) { apply(); return; }
    const x = origin ? origin.x : innerWidth / 2, y = origin ? origin.y : 0;
    const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    const t = document.startViewTransition(apply);
    t.ready.then(() => {
      document.documentElement.animate({ clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] }, { duration: 600, easing: EASE.out, pseudoElement: '::view-transition-new(root)' });
    }).catch(() => {});
  }

  // ---------- toast and dialog ----------
  function toast(message, { kind = 'info', action, ms = 6500 } = {}) {
    let host = $('#toasts');
    if (!host) { host = document.createElement('div'); host.id = 'toasts'; host.setAttribute('aria-live', 'polite'); document.body.appendChild(host); }
    const t = document.createElement('div');
    t.className = `toast ${kind}`;
    t.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    t.innerHTML = `<span class="toast-msg">${esc(message)}</span>${action ? `<button class="btn-text" type="button">${esc(action.label)}</button>` : ''}<button class="toast-x" type="button" aria-label="Dismiss">${icon('x', 14)}</button>`;
    host.appendChild(t);
    if (!reduced()) t.animate([{ opacity: 0, transform: 'translateY(10px) scale(.98)' }, { opacity: 1, transform: 'none' }], { duration: SPRING.snap.duration, easing: SPRING.snap.easing });
    const close = () => {
      if (!t.isConnected) return;
      const a = reduced() ? null : t.animate([{ opacity: 1 }, { opacity: 0, transform: 'translateY(6px)' }], { duration: 180, easing: EASE.out, fill: 'forwards' });
      if (a) a.finished.then(() => t.remove()).catch(() => t.remove()); else t.remove();
    };
    t.querySelector('.toast-x').onclick = close;
    if (action) t.querySelector('.btn-text').onclick = () => { action.run(); close(); };
    setTimeout(close, ms);
  }

  function confirmDialog({ title, body, confirm = 'Confirm', danger = false }) {
    return new Promise(resolve => {
      const d = document.createElement('dialog');
      d.className = 'dialog';
      d.innerHTML = `<form method="dialog"><h2>${esc(title)}</h2><p class="muted">${esc(body)}</p><div class="dialog-actions"><button value="cancel" class="btn btn-secondary">Cancel</button><button value="ok" class="btn ${danger ? 'btn-danger' : 'btn-primary'}">${esc(confirm)}</button></div></form>`;
      document.body.appendChild(d);
      d.addEventListener('close', () => { resolve(d.returnValue === 'ok'); d.remove(); });
      d.showModal();
      if (!reduced()) d.animate([{ opacity: 0, transform: 'translateY(8px) scale(.98)' }, { opacity: 1, transform: 'none' }], { duration: SPRING.snap.duration, easing: SPRING.snap.easing });
    });
  }

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch {
      const t = document.createElement('textarea');
      t.value = text; t.style.position = 'fixed'; t.style.opacity = '0';
      document.body.appendChild(t); t.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch { /* ignore */ }
      t.remove();
      return ok;
    }
  }

  // A ring that spreads from an element, to draw the eye to something that just changed.
  function pulse(el, times = 2) {
    if (reduced() || !el) return;
    const c = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    el.animate([{ boxShadow: `0 0 0 0 ${c}8c` }, { boxShadow: `0 0 0 12px ${c}00` }], { duration: 1300, iterations: times, easing: EASE.out });
  }

  // ---------- boot ----------
  function boot() {
    const D = V.data || {};
    document.documentElement.dataset.theme = theme();
    // the company from data.js, so the header and the fixtures never disagree
    $$('[data-org]').forEach(el => { el.textContent = D.org.name; });
    $$('[data-org-initial]').forEach(el => { el.textContent = D.org.name.charAt(0); });
    // the person's photo in the header; an initial shows if the file is missing
    const me = D.me, av = $('.avatar');
    if (av && me) {
      av.dataset.initial = initials(me.name).charAt(0);
      const img = $('img', av);
      if (img) {
        img.addEventListener('error', () => img.remove());
        if (img.complete && !img.naturalWidth) img.remove();
      }
    }
    // a presenter session keeps its flag when it moves between pages
    if (new URLSearchParams(location.search).get('presenter') === '1') $$('a.brand, a.avatar').forEach(a => { a.href = `${a.getAttribute('href')}?presenter=1`; });
    if (linearOk()) {
      document.documentElement.style.setProperty('--spring', SPRING.snap.easing);
      document.documentElement.style.setProperty('--bounce', SPRING.bounce.easing);
    }
    eyes();
    const tt = $('#theme-toggle');
    if (tt) {
      const paint = () => { const dark = document.documentElement.dataset.theme === 'dark'; tt.innerHTML = icon(dark ? 'sun' : 'moon', 16); tt.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme'); };
      paint();
      tt.addEventListener('click', e => { setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', { x: e.clientX || tt.getBoundingClientRect().left, y: e.clientY || tt.getBoundingClientRect().top }); setTimeout(paint, 60); });
    }
  }

  Object.assign(V, { $, $$, esc, sleep, settle, reduced, fmtTime, fmtClock, fmtDay, initials, icon, mascot, confetti, portal, EASE, SPRING, spring, enter, observe, typeWords, odometer, seg, setTheme, toast, confirmDialog, copy, pulse, boot });
})();
