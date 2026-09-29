/* Shared helpers: DOM, motion primitives (spring, enter, mask, odometer, magnetic, spotlight), theme, toast, dialog. */
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
  const fmtClock = ts => { const d = new Date(ts * 1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
  const group = s => String(s).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

  // ---------- icons (composed from simple strokes; no icon font or CDN so the demo works offline) ----------
  const ICONS = {
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    mic: '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3"/>',
    camera: '<rect x="3" y="6" width="13" height="12" rx="3"/><path d="M16 10.5l5-3v9l-5-3"/>',
    stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="2.5"/>',
    play: '<path d="M8 5.5v13l11-6.5z"/>',
    pause: '<path d="M8.5 6v12M15.5 6v12"/>',
    lock: '<rect x="5" y="10.5" width="14" height="10" rx="3"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/>',
    moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="3"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    external: '<path d="M14 5h5v5M19 5l-8 8M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>',
    volume: '<path d="M4 10v4h3.5L12 18V6L7.5 10H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.6-5.9M20 4v4.5h-4.5"/>',
    chevron: '<path d="M9 6l6 6-6 6"/>',
    flag: '<path d="M6 21V4M6 5h11l-2 4 2 4H6"/>',
    trash: '<path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>'
  };
  const icon = (name, size = 18) => `<svg class="ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;

  // ---------- motion ----------
  const EASE = { out: 'cubic-bezier(.16,1,.3,1)', io: 'cubic-bezier(.65,0,.35,1)', spring: 'cubic-bezier(.34,1.56,.64,1)' };
  const linearOk = () => window.CSS && CSS.supports('transition-timing-function', 'linear(0, 1)');

  // Damped spring step response, sampled into a linear() easing so CSS and WAAPI share one curve.
  function spring(stiffness = 170, damping = 22) {
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
    return { easing: linearOk() ? `linear(${out.join(', ')})` : EASE.spring, duration: Math.round(pts.length * dt * 1000) };
  }
  const SPRING = { soft: spring(140, 24), snap: spring(260, 24), bounce: spring(190, 15) };

  // Fade + rise for one or many elements. WAAPI with backwards fill: no inline styles are left behind.
  function enter(els, o = {}) {
    if (reduced()) return;
    const { y = 16, blur = 0, step = 60, delay = 0, dur = 800, ease = EASE.out } = o;
    [].concat(els).filter(Boolean).forEach((el, i) => {
      el.animate(
        [{ opacity: 0, transform: `translateY(${y}px)`, filter: `blur(${blur}px)` }, { opacity: 1, transform: 'none', filter: 'blur(0)' }],
        { duration: dur, delay: delay + i * step, easing: ease, fill: 'backwards' }
      );
    });
  }

  // Headline lines rise out of a clipped box.
  const mask = lines => lines.map(l => `<span class="ln"><span>${l}</span></span>`).join(' ');
  function revealMask(root = document, o = {}) {
    if (reduced()) return;
    $$('.mask .ln > span', root).forEach((s, i) => {
      s.animate([{ transform: 'translateY(108%)' }, { transform: 'none' }], { duration: 950, delay: (o.delay || 0) + i * 90, easing: EASE.out, fill: 'backwards' });
    });
  }

  // Elements marked data-reveal wait (hidden) until they scroll into view; IntersectionObserver, no scroll listeners.
  const revealIO = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      revealIO.unobserve(e.target);
      const kids = e.target.hasAttribute('data-stagger') ? $$(':scope > [data-item]', e.target) : [];
      e.target.classList.remove('pre');
      if (kids.length) { kids.forEach(k => k.classList.remove('pre')); enter(kids, { y: 18, step: 80, dur: 900 }); } else enter(e.target, { y: 22, dur: 950 });
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0 }); // 0, so a tall block reveals as soon as its top edge shows
  function observe(root = document) {
    $$('[data-reveal]', root).forEach(el => {
      if (!reduced()) {
        const kids = el.hasAttribute('data-stagger') ? $$(':scope > [data-item]', el) : [];
        if (kids.length) kids.forEach(k => k.classList.add('pre')); else el.classList.add('pre');
      }
      revealIO.observe(el);
    });
  }

  // Word-by-word reveal for a question. Returns a promise that resolves when the text is fully shown.
  function typeWords(el, text, { perWord = 42 } = {}) {
    const parts = text.split(/(\s+)/);
    el.innerHTML = parts.map(p => (/^\s+$/.test(p) ? p : `<span class="w">${esc(p)}</span>`)).join('');
    if (reduced()) return Promise.resolve();
    const spans = $$('.w', el);
    spans.forEach((s, i) => s.animate([{ opacity: 0, transform: 'translateY(6px)', filter: 'blur(5px)' }, { opacity: 1, transform: 'none', filter: 'blur(0)' }], { duration: 520, delay: i * perWord, easing: EASE.out, fill: 'backwards' }));
    return sleep((spans.length - 1) * perWord + 580);
  }

  // Wait for an animation, but never longer than its duration: a hidden tab stops producing frames,
  // and control flow must not hang on a decorative transition.
  const settle = (anim, ms) => Promise.race([anim.finished.then(() => {}, () => {}), sleep(ms + 120)]);

  // Odometer: digit columns roll to the new value; separators and length changes fade.
  function odometer(el, text, o = {}) {
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
    function set(next, { duration = 1000, stagger = 42, from } = {}) {
      next = String(next);
      el.setAttribute('aria-label', next);
      if (from != null && !cells.length) set(from, { duration: 0 });
      const anim = !reduced() && duration > 0;
      const n = Math.max(cells.length, next.length);
      const out = [];
      for (let i = 0; i < n; i++) {
        const old = cells[i], ch = next[i];
        const rank = n - 1 - i; // cascade from the last digit
        if (ch === undefined) {
          // removed trailing cell
          if (anim) old.el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 280, easing: EASE.out, fill: 'forwards' }).finished.then(() => old.el.remove()).catch(() => old.el.remove());
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
          if (anim) cell.el.animate([{ opacity: 0, transform: 'translateY(35%)' }, { opacity: 1, transform: 'none' }], { duration: 520, delay: old ? 0 : rank * stagger, easing: EASE.out, fill: 'backwards' });
          out.push(cell);
        }
      }
      cells = out;
    }
    set(text, { duration: 0 });
    return { set, get text() { return cells.map(c => c.ch).join(''); }, get cells() { return cells.map(c => c.el); } };
  }

  // Hover physics, delegated on the document. Values go straight into CSS variables (no re-render, no state).
  function pointerFx() {
    const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
    if (!fine || reduced()) return;
    let raf = 0, last = null;
    document.addEventListener('pointermove', e => {
      last = e;
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const t = last.target.closest && last.target.closest('[data-magnetic],[data-spot]');
        if (!t) return;
        const r = t.getBoundingClientRect();
        if (t.hasAttribute('data-magnetic')) {
          t.style.setProperty('--mx', ((last.clientX - (r.left + r.width / 2)) * 0.16).toFixed(1) + 'px');
          t.style.setProperty('--my', ((last.clientY - (r.top + r.height / 2)) * 0.26).toFixed(1) + 'px');
        }
        if (t.hasAttribute('data-spot')) {
          t.style.setProperty('--sx', (last.clientX - r.left).toFixed(0) + 'px');
          t.style.setProperty('--sy', (last.clientY - r.top).toFixed(0) + 'px');
        }
      });
    }, { passive: true });
    document.addEventListener('pointerout', e => {
      const t = e.target.closest && e.target.closest('[data-magnetic]');
      if (t && !t.contains(e.relatedTarget)) { t.style.setProperty('--mx', '0px'); t.style.setProperty('--my', '0px'); }
    });
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
      document.documentElement.animate({ clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] }, { duration: 750, easing: EASE.out, pseudoElement: '::view-transition-new(root)' });
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
    if (!reduced()) t.animate([{ opacity: 0, transform: 'translateY(16px) scale(.98)' }, { opacity: 1, transform: 'none' }], { duration: SPRING.snap.duration, easing: SPRING.snap.easing });
    const close = () => {
      if (!t.isConnected) return;
      const a = reduced() ? null : t.animate([{ opacity: 1 }, { opacity: 0, transform: 'translateY(8px)' }], { duration: 220, easing: EASE.out, fill: 'forwards' });
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
      d.innerHTML = `<form method="dialog"><h2>${esc(title)}</h2><p class="muted">${esc(body)}</p><div class="dialog-actions"><button value="cancel" class="btn btn-ghost">Cancel</button><button value="ok" class="btn ${danger ? 'btn-danger' : 'btn-primary'}">${esc(confirm)}</button></div></form>`;
      document.body.appendChild(d);
      d.addEventListener('close', () => { resolve(d.returnValue === 'ok'); d.remove(); });
      d.showModal();
      if (!reduced()) d.animate([{ opacity: 0, transform: 'translateY(12px) scale(.97)' }, { opacity: 1, transform: 'none' }], { duration: SPRING.snap.duration, easing: SPRING.snap.easing });
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
    el.animate([{ boxShadow: `0 0 0 0 ${c}8c` }, { boxShadow: `0 0 0 14px ${c}00` }], { duration: 1400, iterations: times, easing: EASE.out });
  }

  // ---------- boot ----------
  function boot() {
    document.documentElement.dataset.theme = theme();
    // the person's photo in the header; an initial shows if the file is missing
    const me = V.data && V.data.me, av = $('.avatar');
    if (av && me) {
      av.dataset.initial = (me.name || '?').trim().charAt(0).toUpperCase();
      const img = $('img', av);
      if (img) {
        img.addEventListener('error', () => img.remove());
        if (!img.getAttribute('src')) img.src = me.avatar;
        else if (img.complete && !img.naturalWidth) img.remove();
      }
    }
    // a presenter session keeps its flag when it moves between pages
    if (new URLSearchParams(location.search).get('presenter') === '1') $$('a.brand, a.avatar').forEach(a => { a.href = `${a.getAttribute('href')}?presenter=1`; });
    if (linearOk()) {
      document.documentElement.style.setProperty('--spring', SPRING.soft.easing);
      document.documentElement.style.setProperty('--spring-snap', SPRING.snap.easing);
    }
    pointerFx();
    // header hairline appears once the page has scrolled (sentinel + observer, no scroll listener)
    const sentinel = document.createElement('div');
    sentinel.className = 'top-sentinel';
    document.body.prepend(sentinel);
    const top = $('.top');
    if (top) new IntersectionObserver(([e]) => top.toggleAttribute('data-stuck', !e.isIntersecting)).observe(sentinel);
    const tt = $('#theme-toggle');
    if (tt) {
      const paint = () => { tt.innerHTML = icon(document.documentElement.dataset.theme === 'dark' ? 'sun' : 'moon', 18); tt.setAttribute('aria-label', document.documentElement.dataset.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'); };
      paint();
      tt.addEventListener('click', e => { setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', { x: e.clientX || tt.getBoundingClientRect().left, y: e.clientY || tt.getBoundingClientRect().top }); setTimeout(paint, 60); });
    }
  }

  Object.assign(V, { $, $$, esc, sleep, settle, reduced, fmtTime, fmtClock, group, icon, EASE, SPRING, spring, enter, mask, revealMask, observe, typeWords, odometer, seg, setTheme, toast, confirmDialog, copy, pulse, boot });
})();
