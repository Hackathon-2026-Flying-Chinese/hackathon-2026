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
    earned: { chip: 'Confirmed', tone: 'mint', sub: 'points' },
    pending: { chip: 'Waiting for a senior', tone: 'lemon', sub: 'if confirmed' },
    retake: { chip: 'Second attempt open', tone: '', sub: 'if confirmed' },
    declined: { chip: 'Follow-up asked', tone: '', sub: 'points' }
  };
  const bub = (tone, name) => `<span class="bub" data-tone="${tone}">${icon(name, 14)}</span>`;
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

  // ---------- trend chart: inline SVG, no library ----------
  // Dashed grey is the synthetic illustration. Solid dots are this person's real first attempts. They never share a line.
  function chartSvg(w, synth, real) {
    const H = w < 520 ? 200 : 232, L = 30, R = 12, T = 16, B = 28, iw = w - L - R, ih = H - T - B;
    const y = v => T + ih * (1 - v / 100);
    const share = real.length ? Math.min(0.5, 0.18 + 0.03 * real.length) : 0.2, sep = 1 - share;
    const xs = i => L + iw * (0.02 + (sep - 0.06) * i / (synth.length - 1));
    const xr = i => L + iw * (sep + 0.04 + (share - 0.08) * (real.length > 1 ? i / (real.length - 1) : 0.5));
    const path = (list, x) => list.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
    const sx = L + iw * sep;
    return `<svg width="${w}" height="${H}" viewBox="0 0 ${w} ${H}" aria-hidden="true">
      <defs><linearGradient id="ch-grad" x1="0" y1="0" x2="1" y2="0"><stop offset="0" style="stop-color:var(--accent)"/><stop offset="1" style="stop-color:var(--blue)"/></linearGradient>
      <linearGradient id="ch-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--faint);stop-opacity:.16"/><stop offset="1" style="stop-color:var(--faint);stop-opacity:0"/></linearGradient></defs>
      ${[0, 25, 50, 75, 100].map(v => `<line class="ch-grid" x1="${L}" x2="${w - R}" y1="${y(v)}" y2="${y(v)}"/><text class="ch-t" x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`).join('')}
      <rect class="ch-now" x="${sx}" y="${T}" width="${w - R - sx}" height="${ih}" rx="6"/>
      <line class="ch-sep" x1="${sx}" x2="${sx}" y1="${T}" y2="${H - B}"/>
      <text class="ch-t" x="${L}" y="${H - 8}">6 weeks ago</text><text class="ch-t ch-t-now" x="${sx + 8}" y="${H - 8}">Now</text>
      <g class="ch-syn"><path class="ch-sa" d="${path(synth, xs)}L${xs(synth.length - 1).toFixed(1)},${y(0)}L${xs(0).toFixed(1)},${y(0)}Z"/><path class="ch-sl" d="${path(synth, xs)}"/>${synth.map((v, i) => `<circle class="ch-sd" cx="${xs(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="2.5"/>`).join('')}</g>
      <g class="ch-real">${real.length > 1 ? `<path class="ch-rl" pathLength="1" d="${path(real, xr)}"/>` : ''}${real.map((v, i) => `<circle class="ch-rd" cx="${xr(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="5"/>`).join('')}${real.length ? `<text class="ch-v" x="${xr(real.length - 1).toFixed(1)}" y="${(y(real[real.length - 1]) - 12).toFixed(1)}">${real[real.length - 1]}</text>` : ''}</g>
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
      const opts = { duration: 800, easing: V.EASE.out, fill: 'backwards' };
      $('.ch-syn', host).animate([{ opacity: 0 }, { opacity: 1 }], opts);
      const line = $('.ch-rl', host);
      if (line) line.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { ...opts, duration: 1000, delay: 400 });
      $$('.ch-rd', host).forEach((c, i) => c.animate([{ transform: 'scale(0)' }, { transform: 'scale(1)' }], { duration: V.SPRING.snap.duration, easing: V.SPRING.snap.easing, delay: 600 + i * 140, fill: 'backwards' }));
      const v = $('.ch-v', host);
      if (v) v.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 400, delay: 600 + Math.max(0, real.length - 1) * 140 + 250, fill: 'backwards' });
    }, { threshold: 0.3 }).observe(host);
  }

  // ---------- page ----------
  function entryHtml(e) {
    const r = ROW[e.status] || ROW.retake, on = e.status === 'earned', shows = ['earned', 'pending', 'retake'].includes(e.status);
    return `<li class="pf-row" data-status="${esc(e.status)}">
      <a class="pf-row-link" href="index.html${keep}#${encodeURIComponent(e.sid)}" title="${esc(e.repo)} #${Number(e.number)}, ${V.fmtDay(Number(e.at))}">
        <span class="pf-row-main"><b>${esc(e.title)}</b><span class="mono">#${Number(e.number)}</span></span>
        <span class="badge"${r.tone ? ` data-tone="${r.tone}"` : ''}>${r.chip}</span>
        <span class="pf-row-pts" data-on="${on}"><b class="num">${shows ? `+${Number(e.s)}` : '0'}</b></span>
      </a>
    </li>`;
  }
  const SHOWN = 5; // the latest few; the rest are counted, not listed

  function render(data) {
    const me = D.me, p = data.points, sc = data.score, c = data.concept, nx = c.next, nxBand = data.bands.find(b => b.key === nx.band);
    document.title = 'Portfolio | Viva';
    // only the changes that moved the level, newest first
    const moves = c.events.filter(e => e.from !== e.to);
    const dots = Array.from({ length: sc.needed }, (_, i) => `<i data-on="${i < sc.n}"></i>`).join('');
    root.innerHTML = `
      <header class="ph pf-head" data-enter>
        <div class="pf-id">
          <span class="av pf-av" style="--s:56px"><img src="${esc(me.avatar)}" alt=""></span>
          <div>
            <p class="ph-eyebrow">${icon('lock', 14)}Private to you</p>
            <h1 class="ph-title">${esc(me.name)}</h1>
            <p class="pf-role">${esc(me.role)}, ${esc(D.org.team)}</p>
          </div>
        </div>
        <p class="pf-note">${icon('eye', 14)}Nothing here is used to rank or review anyone. A reviewer link cannot open this page.</p>
      </header>

      <section class="kpis">
        <div class="card kpi" data-enter data-tone="lilac">
          <p class="kpi-l">${icon('award', 14)}Portfolio points</p>
          <p class="kpi-v"><span data-odo="${Number(p.total)}"></span></p>
          <p class="kpi-s">${plural(p.confirmed, 'confirmed review')}. Up to ${Number(p.max_per_change)} per change.</p>
        </div>
        <div class="card kpi" data-enter data-tone="sky">
          <p class="kpi-l">${icon('trend', 14)}Understanding score</p>
          ${sc.value != null ? `<p class="kpi-v"><span data-odo="${Number(sc.value)}"></span><span class="kpi-of">of 100</span></p><p class="kpi-s">Average of your last ${Math.min(10, sc.n)} first attempts, weighted by risk.</p>` : `<p class="kpi-v kpi-none">Not enough evidence</p><p class="kpi-s"><span class="pf-dots" aria-hidden="true">${dots}</span>${sc.n} of ${sc.needed} first attempts. Retakes do not count.</p>`}
        </div>
        <div class="card kpi" data-enter data-tone="mint">
          <p class="kpi-l">${icon('shield', 14)}${esc(c.name)}</p>
          <p class="kpi-v"><span data-odo="${Number(c.level)}"></span><span class="kpi-of">of ${Number(c.max)}</span></p>
          <div class="pf-meter" role="img" aria-label="Level ${Number(c.level)} of ${Number(c.max)}">${[1, 2, 3].map(i => `<span data-on="${i <= c.level}"><i></i></span>`).join('')}</div>
        </div>
      </section>

      <div class="cols">
        <div class="stack">
          <section class="card pf-chart" data-reveal>
            <div class="card-h"><h2>${bub('sky', 'trend')}Understanding trend</h2>
              <ul class="pf-legend">
                <li><svg width="22" height="8" viewBox="0 0 22 8" aria-hidden="true"><path d="M1 4h20" class="ch-sl"/></svg><b>SYNTHETIC</b>Illustration, not a real learner</li>
                <li><svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="4" class="ch-rd"/></svg>Your first attempts</li>
              </ul>
            </div>
            <div id="chart"></div>
            <p class="card-foot">${sc.n ? 'First attempts only. A retake is not counted again.' : 'Your first attempts will appear after the dashed line.'} The dashed history is a fixed illustration and is never counted.</p>
          </section>

          <section class="card pf-work" data-reveal>
            <div class="card-h"><h2>${bub('lilac', 'list')}Work</h2><span class="meta">${plural(p.confirmed, 'confirmed review')}</span></div>
            ${p.entries.length
              ? `<ul class="pf-list">${p.entries.slice(0, SHOWN).map(entryHtml).join('')}</ul>
                 ${p.entries.length > SHOWN ? `<p class="pf-more">and ${p.entries.length - SHOWN} older ${p.entries.length - SHOWN === 1 ? 'check' : 'checks'}</p>` : ''}
                 <div class="pf-total"><span>Total points</span><b class="num">${Number(p.total)}</b></div>`
              : `<div class="pf-empty"><p class="muted">No reviews yet. When a senior confirms a check, its points appear here.</p><a class="btn btn-primary btn-sm" href="index.html${keep}">Open the check <span class="arrow">${icon('arrow', 14)}</span></a></div>`}
          </section>
        </div>

        <aside class="stack">
          <section class="card pf-concept" data-reveal>
            <div class="card-h"><h2>${bub('mint', 'shield')}Concept level</h2><span class="tag" data-tone="mint">${esc(c.name)}</span></div>
            <p class="pf-lv"><b class="num">${Number(c.level)}</b><span>of ${Number(c.max)}</span></p>
            <div class="pf-meter pf-meter-lg" role="img" aria-label="Level ${Number(c.level)} of ${Number(c.max)}">${[1, 2, 3].map(i => `<span data-on="${i <= c.level}"><i></i></span>`).join('')}</div>
            <p class="pf-lv-note">${LEVEL[c.level]}</p>
            <p class="pf-next"><span>Next similar change</span><b>${esc(nxBand.name)} check</b><em class="num">+${Number(nx.s)}</em></p>
            ${moves.length ? `<details class="pf-hist"><summary>${icon('chevron', 13)}Level history<span>${plural(moves.length, 'change')}</span></summary>
              <ul class="pf-moves">${moves.map(e => `<li><b class="num">${Number(e.from)}${icon('arrow', 11)}${Number(e.to)}</b><span>${esc(e.reason)}<em>${esc(e.title)}</em></span><time class="num">${V.fmtDay(Number(e.at))}</time></li>`).join('')}</ul></details>` : ''}
          </section>
          <section class="card" data-reveal>
            <div class="card-h"><h2>${bub('lemon', 'lock')}Who can see this</h2></div>
            <dl class="kv small">
              <div><dt>Points, score and trend</dt><dd>Only you</dd></div>
              <div><dt>Reviewer links</dt><dd>No access</dd></div>
              <div><dt>Used for ranking</dt><dd>Never</dd></div>
            </dl>
          </section>
        </aside>
      </div>

      <section class="card pf-how" data-reveal>
        <div class="card-h"><h2>${bub('mint', 'award')}How points work</h2></div>
        <div class="how-eq">
          <span data-tone="lilac"><b>Risk</b><em>What a mistake costs</em><i>×</i></span>
          <span data-tone="sky"><b>Novelty</b><em>How new this is to you</em><i>×</i></span>
          <span data-tone="lemon"><b>Gap</b><em>How little you have proven</em><i>=</i></span>
          <span data-tone="mint"><b>Points</b><em>1 to ${Number(p.max_per_change)}, once a senior confirms</em></span>
        </div>
        <ol class="how-bands" aria-label="Check bands">${data.bands.map(b => `<li style="flex:${b.to - b.from + 1}" title="${esc(b.note)}"><i></i><b>${esc(b.name)}</b><span class="num">${Number(b.from)} to ${Number(b.to)}</span></li>`).join('')}</ol>
        <details class="how-more"><summary>${icon('chevron', 13)}See the full scoring table</summary>${V.results.rubricHtml(data.rubric, null, null)}</details>
      </section>`;

    // numbers roll once the stats are on screen
    $$('[data-odo]', root).forEach(el => {
      const v = el.dataset.odo, o = V.odometer(el, '0'.repeat(v.length));
      if (V.reduced()) { o.set(v, { duration: 0 }); return; }
      setTimeout(() => o.set(v, { duration: 1100, stagger: 80 }), 350);
    });
    mountChart($('#chart', root), data);
    V.enter($$('[data-enter]', root), { y: 8, step: 50, dur: 480, delay: 40 });
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
