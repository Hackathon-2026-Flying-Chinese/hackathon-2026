/* window.VivaResults: the results page, read as a check report. The flow of the check, a score for how well the answers
   show that the person understands their own change (words only), the phrases it looked at, the senior review, the
   GitHub check, and what a confirmed review adds to the portfolio. The flow, the GitHub preview and the scoring table
   are also used by the check page and the portfolio. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const D = V.data;
  const { $, $$, esc, icon } = V;

  const KINDS = ['specific', 'reason', 'own', 'generic'];
  const VERDICT = { genuine: 'Likely your own work', unclear: 'Needs a closer look', weak: 'Could not confirm' };
  const MODE = { voice: 'Spoken', text: 'Typed' };
  const ACT = { sign: 'requested a signed link for', play: 'played', open_review: 'opened your review' };
  const POINTS = { pending: 'Pending review', retake: 'Not earned yet', earned: 'Added', declined: 'No points', none: 'Not earned yet' };
  const who = a => (a === 'learner' ? 'You' : D.reviewer.name);
  const arrow = `<span class="arrow">${icon('arrow', 14)}</span>`;
  const marks = segs => segs.map(s => (KINDS.includes(s.kind) ? `<mark data-kind="${s.kind}">${esc(s.text)}</mark>` : esc(s.text))).join('');
  const person = () => `<div class="person"><span class="av" data-tone="lemon" style="--s:34px">${esc(V.initials(D.reviewer.name))}</span><div><b>${esc(D.reviewer.name)}</b><span>${esc(D.reviewer.role)}</span></div></div>`;
  const bub = (tone, name) => `<span class="bub" data-tone="${tone}">${icon(name, 14)}</span>`;
  const MOOD = { genuine: 'happy', unclear: 'unsure', weak: 'oops' };

  // ---------- status of the whole check ----------
  function status(view) {
    const st = view.scoring.status;
    if (st === 'earned') return { tone: 'mint', text: 'Confirmed' };
    if (st === 'declined') return { tone: '', text: 'Follow-up requested' };
    if (st === 'retake') return { tone: '', text: 'Did not pass. Second attempt available' };
    return { tone: 'lemon', live: true, text: 'Waiting for senior review' };
  }
  const badge = s => `<span class="badge"${s.tone ? ` data-tone="${s.tone}"` : ''} id="status-badge">${s.live ? '<i class="dot" data-live></i>' : ''}${esc(s.text)}</span>`;

  // ---------- the flow: interview, assessment, senior review, check passes ----------
  // view null is the check page before anything happened.
  function flowSteps(view, points) {
    const reviewer = D.reviewer.name;
    if (!view) {
      return [
        { state: 'current', name: 'Interview', text: 'Two questions, about 3 minutes. Speak or type.' },
        { state: 'todo', name: 'Assessment', text: 'Reads your words only.' },
        { state: 'todo', name: 'Senior review', text: `${reviewer} confirms it is your own work.` },
        { state: 'todo', name: 'Check passes', text: `+${points} points go to your portfolio.` }
      ];
    }
    const a = view.assessment, sc = view.scoring, st = sc.status;
    const answered = view.interview.turns.filter(t => t.answered), follow = answered.some(t => t.source === 'follow-up');
    const secs = view.media.filter(m => m.attempt === view.attempt).reduce((s, m) => s + Number(m.duration || 0), 0);
    const passed = a.verdict === 'genuine';
    return [
      { state: 'done', name: 'Interview', text: `${answered.length} answers${follow ? ', one follow-up' : ''}${secs ? `. ${V.fmtTime(secs)} recorded` : ''}.` },
      { state: 'done', name: 'Assessment', text: `Score ${Number(a.score)}. ${passed ? 'Likely your own work.' : 'Did not pass.'}` },
      st === 'retake' ? { state: 'stop', name: 'Senior review', text: 'Not requested after a first attempt.' }
        : st === 'pending' ? { state: 'wait', name: 'Senior review', text: `Waiting for ${reviewer}.` }
          : st === 'earned' ? { state: 'done', name: 'Senior review', text: `Confirmed by ${reviewer}.` }
            : { state: 'stop', name: 'Senior review', text: `${reviewer} asked for a follow-up.` },
      st === 'earned' ? { state: 'done', name: 'Check passes', text: `+${Number(sc.s)} points added to your portfolio.` }
        : st === 'declined' ? { state: 'stop', name: 'Check passes', text: 'No points this time.' }
          : { state: 'todo', name: 'Check passes', text: `+${Number(sc.s)} points when a senior confirms.` }
    ];
  }
  const MARK = { done: icon('check', 13), stop: icon('dash', 13), wait: icon('clock', 13) };
  const markHtml = (s, i) => MARK[s.state] || String(i + 1);
  function flowHtml(view, points) {
    return `<ol class="flow" id="flow" aria-label="Check progress">${flowSteps(view, points).map((s, i) => `<li class="flow-step" data-state="${s.state}"><span class="flow-mark" aria-hidden="true">${markHtml(s, i)}</span><b>${esc(s.name)}</b><span>${esc(s.text)}</span></li>`).join('')}</ol>`;
  }
  // Set the states step by step, so the line fills from left to right. Used on load and when the senior decides.
  function playFlow(root, view, { from } = {}) {
    const el = $('#flow', root);
    if (!el) return;
    const steps = flowSteps(view), items = $$('.flow-step', el);
    const apply = (s, li, i) => {
      if (li.dataset.state === s.state && $('span:last-child', li).textContent === s.text) return;
      li.dataset.state = s.state;
      $('.flow-mark', li).innerHTML = markHtml(s, i);
      $('span:last-child', li).textContent = s.text;
      if (!V.reduced()) $('.flow-mark', li).animate([{ transform: 'scale(.6)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: V.SPRING.snap.duration, easing: V.SPRING.snap.easing });
    };
    if (V.reduced()) { steps.forEach((s, i) => apply(s, items[i], i)); return; }
    if (from === 'todo') items.forEach((li, i) => { li.dataset.state = 'todo'; $('.flow-mark', li).textContent = String(i + 1); });
    steps.forEach((s, i) => setTimeout(() => apply(s, items[i], i), (from === 'todo' ? 250 : 0) + i * 260));
  }

  // ---------- GitHub check preview ----------
  function ghHtml(view, sha) {
    const st = view ? view.scoring.status : 'home', reviewer = D.reviewer.name;
    const viva = {
      home: { s: 'wait', live: true, note: 'Waiting for you' },
      retake: { s: 'wait', note: 'Second attempt available' },
      pending: { s: 'wait', live: true, note: `In review by ${reviewer}` },
      earned: { s: 'ok', note: `Confirmed by ${reviewer}` },
      declined: { s: 'fail', note: 'Follow-up requested' }
    }[st] || { s: 'idle', note: 'Not started' };
    const sym = { ok: icon('check', 11), fail: icon('x', 11) };
    const row = (s, name, note, extra = '') => `<li${extra}><i class="gh-i" data-s="${s.s || s}"${s.live ? ' data-live' : ''}>${sym[s.s || s] || ''}</i><b>${esc(name)}${extra ? '<em>Required</em>' : ''}</b><span>${esc(note)}</span></li>`;
    const done = st === 'earned';
    return `<section class="card" id="gh-card">
      <div class="card-h"><h2>${bub('plain', 'commit')}Checks on <span class="mono">${esc(sha || (view && view.pr.sha) || D.pr.sha)}</span></h2><span class="tag">GitHub preview</span></div>
      <ul class="gh">
        ${D.ci.map(c => row('ok', c.name, c.note)).join('')}
        ${row(viva, 'viva / decision-check', viva.note, ' data-viva')}
      </ul>
      <p class="gh-sum" data-done="${done}">${done ? `${icon('check', 14)}All checks have passed. The pull request can merge.` : `${icon('lock', 14)}One required check has not passed. Merging waits for it.`}</p>
    </section>`;
  }

  // ---------- side cards ----------
  function reviewHtml(view) {
    const r = view.review || { status: 'pending' };
    if (r.status === 'decided') {
      const ok = r.verdict === 'genuine';
      return `<section class="card review" id="review-card" data-status="decided" data-verdict="${ok ? 'genuine' : 'followup'}">
        <div class="card-h"><h2>${bub('lemon', 'user')}Senior review</h2><span class="badge"${ok ? ' data-tone="mint"' : ''}>${ok ? 'Confirmed' : 'Follow-up'}</span></div>
        ${person()}
        <p class="review-line">${ok ? 'Confirmed that this looks like your own work.' : 'Would like a short follow-up conversation about this change.'}</p>
        ${r.note ? `<blockquote class="review-note">${esc(r.note)}</blockquote>` : ''}
        ${r.at ? `<p class="card-foot">Decided at ${V.fmtClock(Number(r.at))}</p>` : ''}
      </section>`;
    }
    if (r.status === 'not_requested') {
      return `<section class="card review" id="review-card" data-status="retake">
        <div class="card-h"><h2>${bub('lilac', 'refresh')}Second attempt</h2><span class="tag">Attempt ${Number(view.attempt)} of ${Number(view.max_attempts)}</span></div>
        <p class="review-line">This attempt did not pass, so nothing goes to a senior yet. Read the marked answers, then try once more with different questions.</p>
        <button class="btn btn-primary btn-sm" type="button" data-retake>Try again with new questions ${arrow}</button>
      </section>`;
    }
    return `<section class="card review" id="review-card" data-status="pending">
      <div class="card-h"><h2>${bub('lemon', 'user')}Senior review</h2><span class="badge" data-tone="lemon"><i class="dot" data-live></i>Waiting</span></div>
      ${person()}
      <p class="review-line">Watches your recording and reads these answers${view.attempt > 1 ? ', starting with your second attempt' : ''}. This page updates when a decision is saved.</p>
    </section>`;
  }
  function logHtml(view) {
    const rows = view.access_log.filter(e => e.action !== 'sign' || e.media_id);
    return `<section class="card log" id="log-card">
      <div class="card-h"><h2>${bub('sky', 'eye')}Who watched your recording</h2><span class="meta">${rows.length ? `${rows.length} ${rows.length === 1 ? 'entry' : 'entries'}` : ''}</span></div>
      ${rows.length
        ? `<ul class="log-list">${rows.map(e => `<li><span class="av" data-tone="ink" style="--s:20px">${esc(e.actor === 'learner' ? V.initials(D.me.name) : V.initials(D.reviewer.name))}</span><span><b>${esc(who(e.actor))}</b> ${ACT[e.action] || 'opened'}${e.media_id ? ` the question ${Number(e.turn)} recording${e.attempt > 1 ? ` from attempt ${Number(e.attempt)}` : ''}` : ''}.</span><time class="mono num">${V.fmtClock(Number(e.at))}</time></li>`).join('')}</ul>`
        : '<p class="muted small">Nobody has opened it yet.</p>'}
      <p class="card-foot">Visible only to you. Links expire after 5 minutes and every open is logged.</p>
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
          return `<div class="pts-cell" role="cell" data-pt="${i + 1} point${i ? 's' : ''}"${on ? ' data-hit' : ''}><span>${esc(t)}</span>${on && why ? `<em>${icon('check', 13)}<span>${esc(why[r.key])}</span></em>` : ''}</div>`;
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

  // one factor of Risk x Novelty x Gap: its level as three dots, the number, and why
  const factor = (name, v, why, tone, op) => `<span class="pts-f" data-tone="${tone}" title="${esc(why)}"><span class="pts-f-h"><b>${name}</b><span class="pts-dots">${[1, 2, 3].map(i => `<i data-on="${i <= v}"></i>`).join('')}</span></span><span class="pts-f-v num">${Number(v)}</span><i class="pts-op" aria-hidden="true">${op}</i></span>`;

  function pointsHtml(view) {
    const sc = view.scoring, st = sc.status, c = sc.concept, nx = sc.next, nxBand = sc.bands.find(b => b.key === nx.band), moved = c.after !== c.before;
    const note = {
      pending: `A senior reviews your final attempt. When they confirm it is your own work, +${sc.s} points go to your portfolio.`,
      retake: `Nothing is at stake until your final attempt. When a senior confirms it, +${sc.s} points go to your portfolio.`,
      earned: `+${sc.s} points were added to your portfolio.`,
      declined: 'A senior asked for a follow-up conversation, so no points were added.'
    }[st] || '';
    const small = sc.s < 18 ? ' A small change like this adds fewer points than a first-time change in a risky area, which can add up to 27.' : '';
    // folded by default: the header shows the sum, the table and the rest open on a click
    return `<details class="card pts fold" id="points-card" data-status="${esc(st)}" data-reveal>
      <summary>
        <span class="card-h"><h2>${bub('mint', 'award')}Portfolio points</h2><span class="fold-sum"><span class="badge pts-chip" data-status="${esc(st)}"${st === 'earned' ? ' data-tone="mint"' : st === 'pending' ? ' data-tone="lemon"' : ''}>${POINTS[st] || ''}</span><span class="fold-i">${icon('chevron', 14)}</span></span></span>
        <span class="pts-sum">
          <span class="pts-eq" role="img" aria-label="${sc.r} times ${sc.n} times ${sc.g} equals ${sc.s} points">
            ${factor('Risk', sc.r, sc.why.r, 'lilac', '×')}${factor('Novelty', sc.n, sc.why.n, 'sky', '×')}${factor('Gap', sc.g, sc.why.g, 'lemon', '=')}
            <span class="pts-coin" data-status="${esc(st)}"><b class="num" data-pts>${Number(sc.s)}</b><em>points</em><span class="pts-stamp">${st === 'earned' ? 'Added' : st === 'declined' ? 'Not added' : 'If confirmed'}</span></span>
          </span>
          ${scaleHtml(sc.bands, sc.s, sc.band, sc.floor)}
        </span>
      </summary>
      <p class="pts-lede">A confirmed review adds Risk × Novelty × Gap points. Each factor scores 1 to 3, so one change is worth 1 to ${Number(sc.max)}.</p>
      ${rubricHtml(sc.rubric, { r: sc.r, n: sc.n, g: sc.g }, sc.why)}
      <p class="pts-note">${esc(note)}${small}</p>
      <dl class="pts-facts">
        <div><dt>Concept level</dt><dd><b>${esc(c.name)}</b> ${moved ? `level ${Number(c.before)} to ${Number(c.after)}. ${esc(c.reason || '')}` : `level ${Number(c.before)} of 3. ${esc(c.reason || 'A first failure leaves the level alone.')}`}</dd></div>
        <div><dt>Next similar change</dt><dd><b class="num">${Number(nx.r)} × ${Number(nx.n)} × ${Number(nx.g)} = ${Number(nx.s)}</b>, ${esc(nxBand.name)} check. ${esc(nxBand.note)}</dd></div>
      </dl>
      <a class="btn btn-secondary btn-sm pts-link" href="portfolio.html">View portfolio ${arrow}</a>
    </details>`;
  }

  // ---------- the page ----------
  function html(view) {
    const a = view.assessment, pr = view.pr, retake = view.can_retake, second = view.attempt > 1, first = view.previous[0];
    const dims = a.dims.map(d => `<li class="dim" title="${esc(d.note)}">
        <div class="dim-top"><b>${esc(d.label)}</b><span class="dim-val num" data-dim="${Number(d.value)}"></span></div>
        <span class="dim-line" aria-hidden="true"><i style="--w:${(Number(d.value) / 100).toFixed(2)}"></i></span>
      </li>`).join('');
    const qs = a.questions.map(q => `<article class="rq">
        <header><span class="rq-n num">${Number(q.turn)}</span><span class="tag" data-tone="lilac">${esc(q.label)}</span><span class="tag">${MODE[q.mode] || 'Answered'}</span>${q.source === 'follow-up' ? '<span class="tag" data-tone="lemon">Follow-up</span>' : ''}</header>
        <p class="rq-q">${esc(q.question)}</p>
        <blockquote class="rq-a">${marks(q.segments)}</blockquote>
        <ul class="rq-notes">${q.notes.map(n => `<li data-tone="${n.tone === 'good' ? 'good' : 'warn'}">${icon(n.tone === 'good' ? 'check' : 'flag', 14)}<span>${esc(n.text)}</span></li>`).join('')}</ul>
      </article>`).join('');
    const lede = retake
      ? 'This attempt did not pass. Read the marked answers below, then try once more with different questions.'
      : `${second && first ? `This is your second attempt. The first scored ${Number(first.score)}. ` : ''}The score reads your words only. A senior reviewer also watches your recording.`;
    return `
      <header class="ph" data-enter>
        <div class="ph-main">
          <p class="ph-eyebrow">${icon('pr', 15)}<span class="mono">${esc(pr.repo)}</span><span>Pull request #${Number(pr.number)}</span></p>
          <h1 class="ph-title">${esc(pr.title)}</h1>
          <div class="ph-meta">
            ${badge(status(view))}
            <span>${icon('commit', 14)}<span class="mono">${esc(pr.sha)}</span></span>
            <span>${icon('refresh', 14)}Attempt ${Number(view.attempt)} of ${Number(view.max_attempts)}</span>
            ${view.finished ? `<span>${icon('clock', 14)}Finished at ${V.fmtClock(Number(view.finished))}</span>` : ''}
          </div>
        </div>
        ${retake ? `<div class="ph-actions"><button class="btn btn-primary" type="button" data-retake>Try again with new questions ${arrow}</button></div>` : ''}
      </header>

      <section class="card flow-card" data-enter>${flowHtml(view)}</section>

      <div class="cols">
        <div class="stack">
          <section class="card score-card" data-enter data-verdict="${esc(a.verdict)}">
            <div class="score-face" data-mood="${MOOD[a.verdict] || 'unsure'}">${V.mascot('buddy')}</div>
            <div class="score-top">
              <div class="score" role="img" aria-label="Understanding score ${Number(a.score)} out of 100">
                <svg class="ring" viewBox="0 0 120 120" aria-hidden="true">
                  <defs><linearGradient id="ring-grad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--accent)"/><stop offset="1" style="stop-color:var(--blue)"/></linearGradient></defs>
                  <circle class="ring-bg" cx="60" cy="60" r="52"/><circle class="ring-fg" cx="60" cy="60" r="52" pathLength="1"/>
                </svg>
                <div class="score-num"><span class="odo-host" data-score></span><span class="score-of">of 100</span></div>
              </div>
              <div class="score-copy">
                <p class="label">Understanding score</p>
                <h2 class="score-head">${esc(a.headline)}</h2>
                ${retake || second ? `<p class="muted">${lede}</p>` : ''}
                <div class="score-tags"><span class="badge res-verdict" data-verdict="${esc(a.verdict)}"${a.verdict === 'genuine' ? ' data-tone="accent"' : a.verdict === 'unclear' ? ' data-tone="blue"' : ''}>${VERDICT[a.verdict] || ''}</span>${a.simulated ? '<span class="tag">Simulated assessment</span>' : ''}</div>
              </div>
            </div>
            <ul class="dims">${dims}</ul>
          </section>

          <details class="card answers fold" data-reveal>
            <summary class="card-h"><h2>${bub('lilac', 'chat')}Your answers</h2><span class="fold-sum"><span>${a.questions.length} answers, with the phrases the score looked at</span><span class="fold-i">${icon('chevron', 14)}</span></span></summary>
            <ul class="legend"><li><mark data-kind="specific" class="on">Concrete detail</mark></li><li><mark data-kind="reason" class="on">Reasoning</mark></li><li><mark data-kind="own" class="on">Your decision</mark></li><li><mark data-kind="generic" class="on">Generic phrasing</mark></li></ul>
            ${qs}
          </details>

          ${pointsHtml(view)}
        </div>

        <aside class="stack" id="side">
          ${reviewHtml(view)}
          ${ghHtml(view)}
          ${logHtml(view)}
        </aside>
      </div>`;
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
      hits.forEach((h, i) => setTimeout(() => h.classList.add('on'), 150 + i * 200));
      // the three factors pop in one by one and fill their dots, then the badge flips over and the number rolls
      $$('.pts-f', card).forEach((f, i) => {
        f.animate([{ opacity: 0, transform: 'translateY(12px) scale(.85) rotate(-4deg)' }, { opacity: 1, transform: 'none' }], { duration: V.SPRING.bounce.duration, delay: i * 140, easing: V.SPRING.bounce.easing, fill: 'backwards' });
        $$('.pts-dots i[data-on="true"]', f).forEach((d, j) => d.animate([{ transform: 'scale(0)' }, { transform: 'scale(1)' }], { duration: V.SPRING.bounce.duration, delay: 220 + i * 140 + j * 90, easing: V.SPRING.bounce.easing, fill: 'backwards' }));
      });
      $$('.pts-op', card).forEach((o, i) => o.animate([{ opacity: 0, transform: 'scale(.4)' }, { opacity: 1, transform: 'none' }], { duration: 420, delay: 100 + i * 140, easing: V.EASE.out, fill: 'backwards' }));
      $('.pts-coin', card).animate([{ opacity: 0, transform: 'perspective(400px) rotateY(100deg) scale(.7)' }, { opacity: 1, transform: 'none' }], { duration: V.SPRING.bounce.duration + 200, delay: 480, easing: V.SPRING.bounce.easing, fill: 'backwards' });
      setTimeout(() => odo.set(n, { duration: 900, stagger: 70 }), 600);
      setTimeout(() => card.classList.add('run'), 850);
      mark.animate([{ opacity: 0, transform: 'translate(-50%, -10px)' }, { opacity: 1, transform: 'translate(-50%, 0)' }], { duration: V.SPRING.snap.duration, delay: 850, easing: V.SPRING.snap.easing, fill: 'backwards' });
    }, { threshold: 0.2, rootMargin: '0px 0px -6% 0px' }).observe($('.pts-sum', card));
  }

  function mount(root, view) {
    const a = view.assessment, reduced = V.reduced();
    playFlow(root, view, { from: 'todo' });
    // score ring and number
    const fg = $('.ring-fg', root), num = V.odometer($('[data-score]', root), '0'.repeat(String(a.score).length));
    const target = 1 - a.score / 100;
    if (reduced) { fg.style.strokeDashoffset = target; num.set(String(a.score), { duration: 0 }); } else {
      fg.style.strokeDashoffset = 1;
      const run = fg.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: target }], { duration: 1400, delay: 350, easing: V.EASE.out, fill: 'both' });
      run.finished.then(() => { fg.style.strokeDashoffset = target; run.cancel(); }).catch(() => {});
      setTimeout(() => num.set(String(a.score), { duration: 1200, stagger: 80 }), 450);
    }
    // the four signals roll and draw together, after the score
    $$('.dim', root).forEach((li, i) => {
      const el = $('.dim-val', li), v = String(Number(el.dataset.dim)), line = $('.dim-line i', li);
      const o = V.odometer(el, '0'.repeat(v.length));
      if (reduced) { o.set(v, { duration: 0 }); return; }
      setTimeout(() => o.set(v, { duration: 1000, stagger: 60 }), 700 + i * 90);
      line.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 1000, delay: 700 + i * 90, easing: V.EASE.out, fill: 'backwards' });
    });
    // highlighter sweep over the phrases the score looked at
    $$('.rq', root).forEach(card => {
      const ms = $$('mark', card);
      if (reduced) { ms.forEach(m => m.classList.add('on')); return; }
      new IntersectionObserver((es, io) => {
        if (!es[0].isIntersecting) return;
        io.disconnect();
        ms.forEach((m, i) => setTimeout(() => m.classList.add('on'), 200 + i * 70));
      }, { threshold: 0.35 }).observe(card);
    });
    mountPoints(root, view);
  }

  V.results = { html, mount, status, badge, flowHtml, playFlow, ghHtml, reviewHtml, logHtml, pointsHtml, mountPoints, rubricHtml, scaleHtml };
  window.VivaResults = V.results;
})();
