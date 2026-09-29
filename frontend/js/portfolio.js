/* window.VivaPortfolio: the person's portfolio. Points from confirmed reviews, the understanding score and its trend,
   the concept level, and the work behind them. Private to the person: a reviewer link cannot read any of it. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const { $, $$, esc, icon } = V;
  const D = V.data, api = V.api, root = $('#app');
  const keep = new URLSearchParams(location.search).get('presenter') === '1' ? '?presenter=1' : '';

  const LEVEL = ['Needs more practice or a person to help.', 'Not proven yet. Every concept starts here.', 'Proven once on a new task.', 'Proven more than once, recently.'];
  const ROW = {
    earned: { chip: 'Confirmed', cls: 'chip-solid', sub: 'points' },
    pending: { chip: 'Waiting for a senior', cls: 'chip-signal', sub: 'if confirmed' },
    retake: { chip: 'Second attempt open', cls: '', sub: 'if confirmed' },
    declined: { chip: 'Follow-up asked', cls: '', sub: 'points' }
  };
  const day = ts => new Date(ts * 1000).toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

  // ---------- trend chart: inline SVG, no library ----------
  // Dashed grey is the synthetic illustration. Solid dots are this person's real first attempts. They never share a line.
  function chartSvg(w, synth, real) {
    const H = w < 520 ? 220 : 260, L = 34, R = 10, T = 14, B = 30, iw = w - L - R, ih = H - T - B;
    const y = v => T + ih * (1 - v / 100);
    const share = real.length ? Math.min(0.5, 0.18 + 0.03 * real.length) : 0.2, sep = 1 - share;
    const xs = i => L + iw * (0.02 + (sep - 0.06) * i / (synth.length - 1));
    const xr = i => L + iw * (sep + 0.04 + (share - 0.08) * (real.length > 1 ? i / (real.length - 1) : 0.5));
    const path = (list, x) => list.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
    const sx = L + iw * sep;
    return `<svg width="${w}" height="${H}" viewBox="0 0 ${w} ${H}" aria-hidden="true">
      <defs><linearGradient id="ch-grad" x1="0" y1="0" x2="1" y2="0"><stop offset="0" style="stop-color:var(--accent)"/><stop offset="1" style="stop-color:var(--blue)"/></linearGradient></defs>
      ${[0, 25, 50, 75, 100].map(v => `<line class="ch-grid" x1="${L}" x2="${w - R}" y1="${y(v)}" y2="${y(v)}"/><text class="ch-t" x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`).join('')}
      <line class="ch-sep" x1="${sx}" x2="${sx}" y1="${T}" y2="${H - B}"/>
      <text class="ch-t" x="${L}" y="${H - 8}">6 weeks ago</text><text class="ch-t" x="${sx}" y="${H - 8}" text-anchor="middle">Now</text>
      <g class="ch-syn"><path class="ch-sl" d="${path(synth, xs)}"/>${synth.map((v, i) => `<circle class="ch-sd" cx="${xs(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="3"/>`).join('')}</g>
      <g class="ch-real">${real.length > 1 ? `<path class="ch-rl" pathLength="1" d="${path(real, xr)}"/>` : ''}${real.map((v, i) => `<circle class="ch-rd" cx="${xr(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="5.5"/>`).join('')}${real.length ? `<text class="ch-v" x="${xr(real.length - 1).toFixed(1)}" y="${(y(real[real.length - 1]) - 13).toFixed(1)}">${real[real.length - 1]}</text>` : ''}</g>
    </svg>`;
  }
  function mountChart(host, data) {
    const synth = D.syntheticHistory, real = data.score.real.map(p => p.score);
    host.setAttribute('role', 'img');
    host.setAttribute('aria-label', `Understanding score trend. A synthetic illustration in dashed grey${real.length ? `, then your first attempts: ${real.join(', ')}` : '. Your first attempts will appear after it'}.`);
    const draw = () => { host.innerHTML = chartSvg(Math.round(host.clientWidth), synth, real); };
    draw();
    let last = host.clientWidth;
    new ResizeObserver(() => { if (Math.abs(host.clientWidth - last) > 1) { last = host.clientWidth; draw(); } }).observe(host);
    if (V.reduced()) return;
    let played = false;
    new IntersectionObserver((es, io) => {
      if (!es[0].isIntersecting || played) return;
      played = true; io.disconnect();
      const opts = { duration: 900, easing: V.EASE.out, fill: 'backwards' };
      $('.ch-syn', host).animate([{ opacity: 0 }, { opacity: 1 }], opts);
      const line = $('.ch-rl', host);
      if (line) line.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { ...opts, duration: 1200, delay: 500 });
      $$('.ch-rd', host).forEach((c, i) => c.animate([{ transform: 'scale(0)' }, { transform: 'scale(1)' }], { duration: V.SPRING.bounce.duration, easing: V.SPRING.bounce.easing, delay: 700 + i * 160, fill: 'backwards' }));
      const v = $('.ch-v', host);
      if (v) v.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 700 + Math.max(0, real.length - 1) * 160 + 300, fill: 'backwards' });
    }, { threshold: 0.3 }).observe(host);
  }

  // ---------- page ----------
  function entryHtml(e) {
    const r = ROW[e.status] || ROW.retake, on = e.status === 'earned', shows = ['earned', 'pending', 'retake'].includes(e.status);
    return `<li class="pf-row" data-status="${esc(e.status)}">
      <div class="pf-row-main">
        <h3>${esc(e.title)}</h3>
        <p class="muted small">${esc(e.repo)} #${Number(e.number)} · ${day(Number(e.at))} · <a href="index.html${keep}#${encodeURIComponent(e.sid)}">Open results</a></p>
        <p class="pf-chips"><span class="chip ${r.cls}">${r.chip}</span>${e.attempt > 1 ? `<span class="chip">Attempt ${Number(e.attempt)}</span>` : ''}<span class="chip">${Number(e.r)} × ${Number(e.n)} × ${Number(e.g)}</span></p>
      </div>
      <div class="pf-row-pts" data-on="${on}"><b class="num">${shows ? `+${Number(e.s)}` : '0'}</b><span>${r.sub}</span></div>
    </li>`;
  }

  function render(data) {
    const me = D.me, p = data.points, sc = data.score, c = data.concept, nx = c.next, nxBand = data.bands.find(b => b.key === nx.band);
    document.title = 'Portfolio | Viva';
    const dots = Array.from({ length: sc.needed }, (_, i) => `<i data-on="${i < sc.n}"></i>`).join('');
    root.innerHTML = `
      <section class="pf-head" data-enter>
        <span class="pf-avatar"><img src="${esc(me.avatar)}" alt="" width="104" height="104"></span>
        <div>
          <p class="micro">Portfolio</p>
          <h1 class="display mask">${V.mask([esc(me.name)])}</h1>
          <p class="lede">Private to you. Nothing here is used to rank or review anyone.</p>
        </div>
      </section>

      <section class="pf-stats" data-enter>
        <div class="pf-stat">
          <p class="micro">Portfolio points</p>
          <p class="pf-big"><span data-odo="${Number(p.total)}"></span></p>
          <p class="pf-sub">${plural(p.confirmed, 'confirmed review')}. Up to ${Number(p.max_per_change)} per change.</p>
        </div>
        <div class="pf-stat">
          <p class="micro">Understanding score</p>
          ${sc.value != null ? `<p class="pf-big"><span data-odo="${Number(sc.value)}"></span></p><p class="pf-sub">Average of your last ${Math.min(10, sc.n)} first attempts, weighted by risk.</p>` : `<p class="pf-big pf-none">Not enough evidence</p><p class="pf-sub"><span class="pf-dots" aria-hidden="true">${dots}</span>${sc.n} of ${sc.needed} first attempts. Retakes do not count.</p>`}
        </div>
        <div class="pf-stat">
          <p class="micro">${esc(c.name)}</p>
          <p class="pf-big"><span data-odo="${Number(c.level)}"></span><span class="pf-of">of ${Number(c.max)}</span></p>
          <p class="pf-sub">Next similar change: ${Number(nx.r)} × ${Number(nx.n)} × ${Number(nx.g)} = ${Number(nx.s)}, ${esc(nxBand.name)} check.</p>
        </div>
      </section>

      <section class="pf-block" data-reveal>
        <div class="pf-block-head"><h2 class="h2">Understanding trend</h2>
          <ul class="pf-legend">
            <li><svg width="26" height="8" viewBox="0 0 26 8" aria-hidden="true"><path d="M1 4h24" class="ch-sl"/></svg><b>SYNTHETIC</b> Illustration, not a real learner.</li>
            <li><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" class="ch-rd"/></svg>Your first attempts</li>
          </ul>
        </div>
        <div class="card pf-chart"><div id="chart"></div>
          <p class="pf-cap">${sc.n ? 'First attempts only. A retake is not counted again.' : 'Your first attempts will appear after the dashed line.'} The dashed history is a fixed illustration and is never counted.</p>
        </div>
      </section>

      <section class="pf-block" data-reveal>
        <div class="pf-block-head"><h2 class="h2">Concept level</h2></div>
        <div class="card pf-concept">
          <div class="pf-cl-top">
            <div><h3>${esc(c.name)}</h3><p class="muted">${LEVEL[c.level]}</p></div>
            <div class="pf-meter" role="img" aria-label="Level ${Number(c.level)} of ${Number(c.max)}">${[1, 2, 3].map(i => `<span data-on="${i <= c.level}"><i></i></span>`).join('')}<b class="num">Level ${Number(c.level)}</b></div>
          </div>
          <p class="pf-next">Next similar change: <b class="num">${Number(nx.r)} × ${Number(nx.n)} × ${Number(nx.g)} = ${Number(nx.s)}</b>, ${esc(nxBand.name)} check. ${esc(nxBand.note)}${nx.floor ? ` ${esc(nx.floor)}` : ''}</p>
          ${c.events.length ? `<ul class="pf-events">${c.events.map(e => `<li><span class="mono num">${day(Number(e.at))}</span><span class="pf-lv num">${Number(e.from)}${icon('arrow', 13)}${Number(e.to)}</span><span>${esc(e.reason)} <em>${esc(e.title)}</em></span></li>`).join('')}</ul>` : '<p class="muted small">No level changes yet. A pass moves it up, a failed retake moves it down, and a first failure leaves it alone.</p>'}
        </div>
      </section>

      <section class="pf-block" data-reveal>
        <div class="pf-block-head"><h2 class="h2">Work</h2><p class="muted small">Only a review a senior confirms earns points.</p></div>
        ${p.entries.length
          ? `<ul class="pf-work">${p.entries.map(entryHtml).join('')}</ul><div class="pf-total"><span>Total</span><b class="num">${Number(p.total)}</b></div>`
          : `<div class="card pf-empty"><p>No reviews yet. Finish an interview, and when a senior confirms it, the points appear here.</p><a class="btn btn-primary btn-sm" href="index.html${keep}">Start an interview <span class="arrow">${icon('arrow', 14)}</span></a></div>`}
      </section>

      <section class="pf-block" data-reveal>
        <div class="pf-block-head"><h2 class="h2">How points work</h2></div>
        <div class="card">
          <p class="pts-lede">A confirmed review adds Risk × Novelty × Gap points. Each factor scores 1 to 3, so one change is worth 1 to ${Number(p.max_per_change)}. Gap follows the concept level above, so proven ground earns fewer points.</p>
          ${V.results.rubricHtml(data.rubric, null, null)}
          <ul class="pf-bands">${data.bands.map(b => `<li><b>${esc(b.name)}</b><span class="mono num">${Number(b.from)} to ${Number(b.to)}</span><span>${esc(b.note)}</span></li>`).join('')}</ul>
        </div>
      </section>`;

    // numbers roll once the stats are on screen
    $$('[data-odo]', root).forEach(el => {
      const v = el.dataset.odo, o = V.odometer(el, '0'.repeat(v.length));
      if (V.reduced()) { o.set(v, { duration: 0 }); return; }
      setTimeout(() => o.set(v, { duration: 1300, stagger: 90 }), 500);
    });
    mountChart($('#chart', root), data);
    V.revealMask(root);
    V.enter($$('[data-enter]', root), { y: 18, step: 70, dur: 900, delay: 120 });
    V.observe(root);
  }

  async function boot() {
    V.boot();
    try { render(await api.portfolio()); } catch (e) {
      root.innerHTML = `<p class="lede">${esc((e && e.message) || 'The portfolio could not be loaded.')}</p>`;
    }
  }
  boot();
  V.portfolio = { boot };
  window.VivaPortfolio = V.portfolio;
})();
