/* window.VivaResults: the results page. A score for how well the answers show that the person understands their own
   change (words only), the phrases it looked at, the senior review that follows, and what a confirmed review adds to
   the portfolio. The scoring table is also used on the portfolio page. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const { $, $$, esc, icon } = V;

  const KINDS = ['specific', 'reason', 'own', 'generic'];
  const CHIP = { genuine: 'Likely your own work', unclear: 'Needs a closer look', weak: 'Could not confirm' };
  const MODE = { voice: 'Spoken', text: 'Typed' };
  const ACT = { sign: 'requested a signed link for', play: 'played', open_review: 'opened your review' };
  const STATUS = { pending: 'Pending review', retake: 'Not earned yet', earned: 'Added', declined: 'No points', none: 'Not earned yet' };
  const actor = a => (a === 'learner' ? 'You' : `Reviewer ${esc(String(a).split(':')[1] || '')}`);
  const arrow = `<span class="arrow">${icon('arrow', 14)}</span>`;

  const marks = segs => segs.map(s => (KINDS.includes(s.kind) ? `<mark data-kind="${s.kind}">${esc(s.text)}</mark>` : esc(s.text))).join('');
  // split a headline into two lines of similar length
  function twoLines(text) {
    const w = text.split(' ');
    let best = 1, gap = Infinity;
    for (let i = 1; i < w.length; i++) {
      const d = Math.abs(w.slice(0, i).join(' ').length - w.slice(i).join(' ').length);
      if (d < gap) { gap = d; best = i; }
    }
    return [w.slice(0, best).join(' '), w.slice(best).join(' ')].filter(Boolean);
  }

  function reviewHtml(view) {
    const r = view.review || { status: 'pending' };
    if (r.status === 'decided') {
      const ok = r.verdict === 'genuine';
      return `<section class="card review" id="review-card" data-status="decided" data-verdict="${ok ? 'genuine' : 'followup'}">
        <header class="card-head"><h3>Senior review</h3><span class="chip ${ok ? 'chip-solid' : 'chip-signal'}">${ok ? 'Confirmed' : 'Follow-up'}</span></header>
        <p class="review-line">${ok ? 'A senior reviewer confirmed this looks like your own work.' : 'A senior reviewer would like a short follow-up conversation.'}</p>
        ${r.note ? `<blockquote class="review-note">${esc(r.note)}</blockquote>` : ''}
      </section>`;
    }
    if (r.status === 'not_requested') {
      return `<section class="card review" id="review-card" data-status="retake">
        <header class="card-head"><h3>Second attempt</h3><span class="chip">Attempt ${Number(view.attempt)} of ${Number(view.max_attempts)}</span></header>
        <p class="review-line">This attempt did not pass, so nothing goes to a senior yet. Read the marked answers, then try once more with different questions.</p>
        <button class="btn btn-primary btn-sm" type="button" data-retake>Try again with new questions ${arrow}</button>
      </section>`;
    }
    return `<section class="card review" id="review-card" data-status="pending">
      <header class="card-head"><h3>Senior review</h3><span class="chip">Waiting</span></header>
      <p class="review-line">A senior reviewer watches your recording and reads these answers${view.attempt > 1 ? ', starting with your second attempt' : ''}. This page updates when they decide.</p>
    </section>`;
  }
  function logHtml(view) {
    const rows = view.access_log.filter(e => e.action !== 'sign' || e.media_id);
    return `<section class="card log" id="log-card">
      <header class="card-head"><h3>Who watched your recording</h3></header>
      ${rows.length
        ? `<ul>${rows.map(e => `<li><span class="mono num">${V.fmtClock(Number(e.at))}</span><span>${actor(e.actor)} ${ACT[e.action] || 'opened'}${e.media_id ? ` the question ${Number(e.turn)} recording${e.attempt > 1 ? ` from attempt ${Number(e.attempt)}` : ''}` : ''}.</span></li>`).join('')}</ul>`
        : '<p class="muted">Nobody has opened it yet.</p>'}
      <p class="hint">Visible only to you. Links expire after 5 minutes and every open is logged.</p>
    </section>`;
  }

  // ---------- the scoring standard ----------
  // hit: the level each factor scored for this change ({r, n, g}); why: the reason shown in the matching cell. Both optional.
  function rubricHtml(rows, hit, why) {
    return `<div class="pts-table" role="table" aria-label="Scoring standard">
      <div class="pts-head" role="row"><span></span>${[1, 2, 3].map(n => `<span role="columnheader">${n} point${n > 1 ? 's' : ''}</span>`).join('')}</div>
      ${rows.map(r => `<div class="pts-row" role="row">
        <div class="pts-name" role="rowheader"><b>${esc(r.name)}</b><span>${esc(r.ask)}</span></div>
        ${r.levels.map((t, i) => {
          const on = hit && hit[r.key] === i + 1;
          return `<div class="pts-cell" role="cell" data-pt="${i + 1} point${i ? 's' : ''}"${on ? ' data-hit' : ''}><span>${esc(t)}</span>${on && why ? `<em>${icon('check', 14)}<span>${esc(why[r.key])}</span></em>` : ''}</div>`;
        }).join('')}
      </div>`).join('')}
    </div>`;
  }
  // The 1 to 27 scale in its four bands, with a marker at the score.
  function scaleHtml(bands, n, bandKey, floor) {
    const max = bands[bands.length - 1].to, cur = bands.find(b => b.key === bandKey);
    return `<div class="pts-scale" role="img" aria-label="${n} of ${max}, ${esc(cur.name)} check">
      <div class="pts-bar">${bands.map(b => `<span class="pts-seg" style="flex:${b.to - b.from + 1}"${b.key === bandKey ? ' data-on' : ''}><i></i><em>${esc(b.name)}</em></span>`).join('')}<b class="pts-mark" style="left:${(((n - 0.5) / max) * 100).toFixed(2)}%"><span class="num">${n}</span></b></div>
      <p class="pts-band"><b>${esc(cur.name)} check.</b> ${esc(cur.note)}${floor ? ` ${esc(floor)}` : ''}</p>
    </div>`;
  }

  function pointsHtml(view) {
    const sc = view.scoring, st = sc.status, c = sc.concept, nx = sc.next, nxBand = sc.bands.find(b => b.key === nx.band), moved = c.after !== c.before;
    const note = {
      pending: `A senior reviews your final attempt. When they confirm it is your own work, +${sc.s} points go to your portfolio.`,
      retake: `Nothing is at stake until your final attempt. When a senior confirms it, +${sc.s} points go to your portfolio.`,
      earned: `+${sc.s} points were added to your portfolio.`,
      declined: 'A senior asked for a follow-up conversation, so no points were added.'
    }[st] || '';
    const small = sc.s < 18 ? ' A small change like this adds fewer points than a first-time change in a risky area, which can add up to 27.' : '';
    return `<section class="card pts" id="points-card" data-status="${esc(st)}" data-reveal>
      <header class="card-head"><h3>Portfolio points</h3><span class="chip pts-chip" data-status="${esc(st)}">${STATUS[st] || ''}</span></header>
      <p class="pts-lede">A confirmed review adds Risk × Novelty × Gap points to your portfolio. Each factor scores 1 to 3, so one change is worth 1 to ${Number(sc.max)}.</p>
      ${rubricHtml(sc.rubric, { r: sc.r, n: sc.n, g: sc.g }, sc.why)}
      <div class="pts-sum">
        <p class="pts-eq" aria-label="${sc.r} times ${sc.n} times ${sc.g} equals ${sc.s}"><span class="num">${Number(sc.r)}</span><i>×</i><span class="num">${Number(sc.n)}</span><i>×</i><span class="num">${Number(sc.g)}</span><i>=</i><b class="num" data-pts>${Number(sc.s)}</b><em>points</em></p>
        ${scaleHtml(sc.bands, sc.s, sc.band, sc.floor)}
      </div>
      <p class="pts-note">${esc(note)}${small}</p>
      <dl class="pts-facts">
        <div><dt>Concept level</dt><dd><b>${esc(c.name)}</b> ${moved ? `level ${Number(c.before)} to ${Number(c.after)}. ${esc(c.reason || '')}` : `level ${Number(c.before)} of 3. ${esc(c.reason || 'A first failure leaves the level alone.')}`}</dd></div>
        <div><dt>Next similar change</dt><dd><b class="num">${Number(nx.r)} × ${Number(nx.n)} × ${Number(nx.g)} = ${Number(nx.s)}</b>, ${esc(nxBand.name)} check. ${esc(nxBand.note)}</dd></div>
      </dl>
      <a class="btn btn-ghost btn-sm pts-link" href="portfolio.html">View portfolio ${arrow}</a>
    </section>`;
  }

  function html(view) {
    const a = view.assessment, retake = view.can_retake, second = view.attempt > 1, first = view.previous[0];
    const dims = a.dims.map(d => `<li class="dimrow" data-reveal>
        <div class="dim-l"><h3>${esc(d.label)}</h3><p>${esc(d.note)}</p></div>
        <div class="dim-r"><span class="dim-val num" data-dim="${Number(d.value)}"></span><span class="dim-line" aria-hidden="true"><i style="--w:${(Number(d.value) / 100).toFixed(2)}"></i></span></div>
      </li>`).join('');
    const qs = a.questions.map(q => `<article class="rq" data-reveal>
        <header><span class="micro">Question ${Number(q.turn)}</span><span class="chip">${esc(q.label)}</span><span class="chip">${MODE[q.mode] || 'Answered'}</span>${q.source === 'follow-up' ? '<span class="chip chip-signal">Follow-up</span>' : ''}</header>
        <p class="rq-q">${esc(q.question)}</p>
        <blockquote class="rq-a">${marks(q.segments)}</blockquote>
        <ul class="rq-notes">${q.notes.map(n => `<li data-tone="${n.tone === 'good' ? 'good' : 'warn'}">${icon(n.tone === 'good' ? 'check' : 'flag', 15)}<span>${esc(n.text)}</span></li>`).join('')}</ul>
      </article>`).join('');
    const lede = retake
      ? 'This attempt did not pass. Read the marked answers below, then try once more with different questions.'
      : `${second && first ? `This is your second attempt. The first scored ${Number(first.score)}. ` : ''}The score reads your words only. A senior reviewer also watches your recording.`;
    return `
      <div class="res-top">
        <div class="res-copy">
          <p class="micro">Interview complete</p>
          <h1 class="display mask">${V.mask(twoLines(a.headline))}</h1>
          <p class="lede">${lede}</p>
          <div class="res-chips"><span class="chip res-verdict" data-verdict="${esc(a.verdict)}">${CHIP[a.verdict] || ''}</span>${a.simulated ? '<span class="chip">Simulated assessment</span>' : ''}${second || retake ? `<span class="chip">Attempt ${Number(view.attempt)} of ${Number(view.max_attempts)}</span>` : ''}</div>
          ${retake ? `<div class="res-cta"><button class="btn btn-primary" type="button" data-retake data-magnetic>Try again with new questions ${arrow}</button></div>` : ''}
        </div>
        <div class="score" data-verdict="${esc(a.verdict)}" role="img" aria-label="Understanding score ${Number(a.score)} out of 100">
          <svg class="ring" viewBox="0 0 120 120" aria-hidden="true">
            <defs><linearGradient id="ring-grad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--accent)"/><stop offset="1" style="stop-color:var(--blue)"/></linearGradient></defs>
            <circle class="ring-bg" cx="60" cy="60" r="52"/><circle class="ring-fg" cx="60" cy="60" r="52" pathLength="1"/>
          </svg>
          <div class="score-num"><span class="odo-host" data-score></span><span class="score-of">Understanding</span></div>
        </div>
      </div>

      <section class="res-dims" data-reveal>
        <h2 class="h2">What the score looked at</h2>
        <ul>${dims}</ul>
      </section>

      <section class="res-qs">
        <div class="res-qs-head" data-reveal><h2 class="h2">Your answers</h2>
          <ul class="legend"><li><mark data-kind="specific" class="on">Concrete detail</mark></li><li><mark data-kind="reason" class="on">Reasoning</mark></li><li><mark data-kind="own" class="on">Your decision</mark></li><li><mark data-kind="generic" class="on">Generic phrasing</mark></li></ul>
        </div>
        ${qs}
      </section>

      <div class="grid-2" id="res-grid">${reviewHtml(view)}${logHtml(view)}</div>
      ${pointsHtml(view)}
      <p class="notice" data-reveal>Your recording goes to a senior reviewer with these results. The score above never uses your face, your voice tone or your expressions.</p>`;
  }

  // The points card plays once when it scrolls into view: the matching cells light up, the product rolls, the marker drops.
  function mountPoints(root, view) {
    const card = $('#points-card', root);
    if (!card || card.dataset.mounted) return;
    card.dataset.mounted = '1';
    const hits = $$('.pts-cell[data-hit]', card), mark = $('.pts-mark', card), total = $('[data-pts]', card), n = String(view.scoring.s);
    if (V.reduced()) { hits.forEach(h => h.classList.add('on')); card.classList.add('run'); return; }
    total.textContent = ''; // the odometer draws its own digits
    const odo = V.odometer(total, '0'.repeat(n.length));
    new IntersectionObserver((es, io) => {
      if (!es[0].isIntersecting) return;
      io.disconnect();
      hits.forEach((h, i) => setTimeout(() => h.classList.add('on'), 200 + i * 240));
      setTimeout(() => odo.set(n, { duration: 1000, stagger: 80 }), 700);
      setTimeout(() => card.classList.add('run'), 1000);
      mark.animate([{ opacity: 0, transform: 'translate(-50%, -16px) scale(.6)' }, { opacity: 1, transform: 'translate(-50%, 0)' }], { duration: V.SPRING.snap.duration, delay: 1000, easing: V.SPRING.snap.easing, fill: 'backwards' });
    }, { threshold: 0.2, rootMargin: '0px 0px -8% 0px' }).observe(card);
  }

  function mount(root, view) {
    const a = view.assessment, reduced = V.reduced();
    // score ring and number
    const fg = $('.ring-fg', root), num = V.odometer($('[data-score]', root), '0'.repeat(String(a.score).length));
    const target = 1 - a.score / 100;
    if (reduced) { fg.style.strokeDashoffset = target; num.set(String(a.score), { duration: 0 }); } else {
      fg.style.strokeDashoffset = 1;
      const run = fg.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: target }], { duration: 1700, delay: 500, easing: V.EASE.out, fill: 'both' });
      run.finished.then(() => { fg.style.strokeDashoffset = target; run.cancel(); }).catch(() => {});
      setTimeout(() => num.set(String(a.score), { duration: 1500, stagger: 90 }), 700);
    }
    // per-dimension numbers roll and lines draw when they scroll into view
    $$('.dimrow', root).forEach(li => {
      const el = $('.dim-val', li), v = String(Number(el.dataset.dim)), line = $('.dim-line i', li);
      const o = V.odometer(el, '0'.repeat(v.length));
      let ran = false;
      new IntersectionObserver((es, io) => {
        if (!es[0].isIntersecting || ran) return;
        ran = true; io.disconnect();
        o.set(v, { duration: reduced ? 0 : 1100, stagger: 70 });
        if (!reduced) line.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 1200, easing: V.EASE.out, fill: 'backwards' });
      }, { threshold: 0.4 }).observe(li);
    });
    // highlighter sweep over the phrases the score looked at
    $$('.rq', root).forEach(card => {
      const ms = $$('mark', card);
      if (reduced) { ms.forEach(m => m.classList.add('on')); return; }
      new IntersectionObserver((es, io) => {
        if (!es[0].isIntersecting) return;
        io.disconnect();
        ms.forEach((m, i) => setTimeout(() => m.classList.add('on'), 250 + i * 90));
      }, { threshold: 0.35 }).observe(card);
    });
    mountPoints(root, view);
  }

  V.results = { html, mount, reviewHtml, logHtml, pointsHtml, mountPoints, rubricHtml, scaleHtml };
  window.VivaResults = V.results;
})();
