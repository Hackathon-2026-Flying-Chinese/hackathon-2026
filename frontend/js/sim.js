/* Simulated backend, kept in the browser (localStorage + IndexedDB) so the demo runs offline. The method names and view shapes
   are what the UI reads. To use a real server, replace this file with a fetch-based Viva.api that has the same methods. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  const D = V.data;

  // ---------- helpers ----------
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const nowS = () => Date.now() / 1000;
  const rand = n => crypto.getRandomValues(new Uint8Array(n));
  const hex = a => [...a].map(x => x.toString(16).padStart(2, '0')).join('');
  const b64u = a => btoa(String.fromCharCode(...a)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const round1 = x => Math.round(x * 10) / 10;
  const words = s => (String(s).trim().match(/\S+/g) || []).length;
  const clamp = (x, lo = 6, hi = 97) => Math.max(lo, Math.min(hi, x));
  const fnv = str => { let h = 0x811c9dc5; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; } return h.toString(16).padStart(8, '0'); };

  class HttpError extends Error {
    constructor(status, detail) { super(detail); this.status = status; }
  }
  const fail = (status, detail) => { throw new HttpError(status, detail); };

  // ---------- persistence ----------
  const KEY = 'viva.sim.v5'; // v5: locked predictions, three code checks and a rubric-assessed viva
  const fresh = () => ({ sessions: {}, tokens: {}, media: {}, secret: hex(rand(32)), settings: { cameraRequired: true, voice: 'specific' } });
  let mem = null; // in-memory fallback when localStorage is blocked
  const load = () => {
    if (mem) return mem;
    try { return JSON.parse(localStorage.getItem(KEY)) || fresh(); } catch { return fresh(); }
  };
  const save = db => { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch { mem = db; } };
  function tx(fn) { const db = load(); const out = fn(db); save(db); return out; }
  const getSession = (db, sid) => db.sessions[sid] || fail(404, 'Session not found');

  let idbP = null;
  const idb = () => {
    if (!idbP) {
      idbP = new Promise((res, rej) => {
        const r = indexedDB.open('viva-sim', 1);
        r.onupgradeneeded = () => r.result.createObjectStore('media');
        r.onsuccess = () => res(r.result);
        r.onerror = () => rej(r.error || new Error('Storage is not available.'));
        r.onblocked = () => rej(new Error('Storage is blocked by another tab.'));
      });
    }
    return idbP.catch(e => { idbP = null; throw e; });
  };
  const blobOp = async (mode, run) => {
    const d = await idb();
    return new Promise((res, rej) => {
      let req;
      const t = d.transaction('media', mode);
      t.oncomplete = () => res(req && req.result);
      t.onabort = t.onerror = () => rej(t.error || (req && req.error) || new Error('Storage is not available.'));
      req = run(t.objectStore('media'));
    });
  };
  const blobPut = (id, blob) => blobOp('readwrite', s => s.put(blob, id));
  const blobGet = id => blobOp('readonly', s => s.get(id));
  const blobDel = id => blobOp('readwrite', s => s.delete(id));

  const enc = s => new TextEncoder().encode(s);
  async function hmac(secret, msg) {
    if (!crypto.subtle) return fnv(secret + msg);
    const key = await crypto.subtle.importKey('raw', enc(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    return hex(new Uint8Array(await crypto.subtle.sign('HMAC', key, enc(msg))));
  }

  // ---------- word signals: only used to aim the template follow-up when the model is not available ----------
  const RE = {
    num: /\$?\b\d[\d,]*(?:\.\d+)?%?/g,
    id: /`[^`]+`|\b[a-z]+(?:_[a-z0-9]+)+\b|\b[a-z]+[A-Z][A-Za-z0-9]*\b|\b[\w-]+\.(?:py|js|ts|go|java|rb|rs|sql|json|ya?ml)\b/g,
    reason: /\b(because|so that|therefore|instead of|rather than|otherwise|that way|which means|trade-?offs?|the reason|to avoid|avoids?|in order to|since)\b/gi,
    alt: /\b(considered|alternatives?|another option|other option|could have|other approach|weighed|compared|tiers?|tiered|instead)\b/gi,
    generic: /\b(best practices?|clean and robust|clean(?:er)? code|robust(?:ly)?|scalab(?:le|ility)|seamless(?:ly)?|leverag(?:e|es|ed|ing)|maintainab(?:le|ility)|in conclusion|overall|furthermore|as expected|properly|correctly|efficient(?:ly)?|(?:industry )?standard (?:and )?(?:scalable )?(?:solution|approach)|well-structured)\b/gi
  };
  const uniq = (text, re) => [...new Set((text.match(re) || []).map(m => m.replace(/^\$/, '').toLowerCase()))];
  const count = (text, re) => (text.match(re) || []).length;
  const features = text => ({ words: words(text), nums: uniq(text, RE.num), ids: uniq(text, RE.id), reason: count(text, RE.reason), alt: count(text, RE.alt), generic: uniq(text, RE.generic) });

  const sat = x => 1 - Math.exp(-1.6 * x); // saturating: more evidence helps less and less, and never reaches 1
  function scoreTexts(texts) {
    const n = Math.max(1, texts.length), f = texts.map(features);
    const sum = k => f.reduce((a, x) => a + (Array.isArray(x[k]) ? x[k].length : x[k]), 0);
    const nums = sum('nums'), ids = sum('ids'), reason = sum('reason'), alt = sum('alt'), generic = sum('generic'), w = sum('words');
    const dims = {
      specific: clamp(Math.round(10 + 90 * sat((nums + 1.5 * ids) / (3 * n)) - 3 * generic)),
      reasoning: clamp(Math.round(10 + 90 * sat((reason + 0.6 * alt) / (2.5 * n)) - 2.5 * generic)),
      detail: clamp(Math.round(10 + 90 * sat(w / (45 * n)) - 1.5 * generic))
    };
    const score = Math.round(0.375 * dims.specific + 0.375 * dims.reasoning + 0.25 * dims.detail);
    return { dims, score };
  }

  // ---------- assessment ----------
  // The three checks are decided by the task data: what the code really returns, the rule, the test that covers it.
  // The viva is assessed against the task's fixed rubric: by the model when it is available (every credited point quotes
  // the answer, checked on the server), otherwise on this device from the rubric's patterns, labelled Simulated.
  // Content only: never face, voice tone or expression, and never who wrote the code or how much AI helped.
  const ITEMS = ['behaviour', 'requirement', 'evidence'];
  const CONF = ['low', 'medium', 'high'];
  const CHECK = { behaviour: 'Behaviour', requirement: 'Requirement', evidence: 'Evidence' };
  const HEAD = { shown: 'You predicted what the code does, and explained why.', gaps: 'Part of this is still a guess.', not_shown: 'The code did something you did not expect.' };
  const taskOf = s => setOf(s).task;
  const optText = (item, id) => (item.options.find(o => o.id === id) || {}).text || '';
  const sentences = text => text.replace(/(\d)\.(\d)/g, '$1\u0000$2').split(/(?<=[.!?])\s+/).map(x => x.replace(/\u0000/g, '.').trim()).filter(Boolean);

  function simulatedViva(set, answered) {
    return {
      source: 'simulated', model: null, flagged: false,
      points: set.rubric.map(p => {
        const res = p.sim.map(x => new RegExp(x, 'i'));
        for (const t of answered) {
          const hit = sentences(t.answer_text).find(x => res.every(re => re.test(x)));
          if (hit) return { id: p.id, text: p.text, met: true, quote: hit, turn: t.turn };
        }
        return { id: p.id, text: p.text, met: false, quote: '', turn: 0 };
      })
    };
  }
  function modelViva(set, ai) {
    return {
      source: 'ai', model: ai.model || null, flagged: !!ai.injection_attempt,
      points: set.rubric.map(p => {
        const g = ai.points.find(x => x.id === p.id) || {}, met = !!g.met && !!g.quote;
        return { id: p.id, text: p.text, met, quote: met ? g.quote : '', turn: met ? Number(g.turn) : 0 };
      })
    };
  }
  // The answer split into plain runs and the runs the viva assessment quoted, so the pages can mark them.
  function quoteMarks(text, quotes) {
    const low = text.toLowerCase(), spans = [];
    for (const q of quotes) { const i = low.indexOf(q.toLowerCase()); if (i >= 0) spans.push([i, i + q.length]); }
    spans.sort((a, b) => a[0] - b[0]);
    const out = [];
    let at = 0;
    for (const [a, b] of spans) {
      if (a < at) continue;
      if (a > at) out.push({ text: text.slice(at, a), kind: null });
      out.push({ text: text.slice(a, b), kind: 'quote' });
      at = b;
    }
    if (at < text.length) out.push({ text: text.slice(at), kind: null });
    return out;
  }
  function assess(s, ai) {
    const set = setOf(s), task = set.task, answered = s.interview.turns.filter(t => t.answered);
    const checks = ITEMS.map(key => {
      const it = task.items[key], chosen = s.predict.answers[key];
      return { key, label: CHECK[key], question: it.q, chosen, chosen_text: optText(it, chosen), correct_text: optText(it, it.correct), ok: chosen === it.correct };
    });
    const viva = ai && Array.isArray(ai.points) ? modelViva(set, ai) : simulatedViva(set, answered);
    const right = checks.filter(c => c.ok).length, met = viva.points.filter(p => p.met).length;
    const verdict = right === ITEMS.length && met >= D.vivaPass ? 'shown' : right + met >= 3 ? 'gaps' : 'not_shown';
    return {
      simulated: viva.source !== 'ai', score: Math.round((right / ITEMS.length) * 100), verdict, headline: HEAD[verdict],
      checks, right, confidence: s.predict.confidence, fn: task.fn, rule: task.rule, reveal: task.reveal, viva, met, rubric_size: set.rubric.length,
      questions: answered.map(t => ({
        turn: t.turn, label: t.label, question: t.question, source: t.source, by: t.by || null, mode: t.mode, answer: t.answer_text,
        segments: quoteMarks(t.answer_text, viva.points.filter(p => p.met && p.turn === t.turn).map(p => p.quote))
      }))
    };
  }
  // What the model is sent: the code, the rule and the viva. The follow-up never gets the answer key; the assessment gets
  // the facts of the run, so it can tell a right explanation from a wrong one.
  const vivaTurns = s => s.interview.turns.filter(t => t.answered).map(t => ({ turn: t.turn, question: t.question, answer: t.answer_text }));
  const followupBody = s => { const t = taskOf(s); return { file: t.file, code: t.code, rule: t.rule, turns: vivaTurns(s), leak_terms: t.leak }; };
  const gradeBody = s => { const set = setOf(s), t = set.task; return { file: t.file, code: t.code, rule: t.rule, facts: t.facts, rubric: set.rubric.map(p => ({ id: p.id, text: p.text })), turns: vivaTurns(s) }; };

  // ---------- interview ----------
  function cleanPr(input = {}) {
    const d = D.pr, str = (v, max) => (typeof v === 'string' && v.trim() ? v.trim().slice(0, max) : null);
    const number = Number.isInteger(+input.number) && +input.number > 0 ? +input.number : d.number;
    return { repo: str(input.repo, 80) || d.repo, number, title: str(input.title, 120) || d.title, author: str(input.author, 40) || d.author, branch: str(input.branch, 60) || d.branch, base: str(input.base, 40) || d.base, sha: str(input.sha, 12) || d.sha, files: d.files };
  }
  // Attempt 1 reads the first task and the retake the second (same concept, different code), so no question repeats.
  const setOf = s => D.sets[Math.min(s.attempt, D.sets.length) - 1];
  function makeTurn(s, key, turn, source) {
    const set = setOf(s), spec = key.startsWith('probe:') ? set.probes[key.slice(6)] : set.questions[key];
    return { turn, key, label: spec.label, question: spec.text.replace('{title}', s.pr.title), source, by: source === 'follow-up' ? 'template' : null, answered: false, answer_text: null, mode: null, media_id: null, asked_at: nowS() };
  }
  // The template follow-up aims at the weaker of the two word signals, and is skipped when neither is weak.
  function weakest(s) {
    const { dims } = scoreTexts(s.interview.turns.filter(t => t.answered).map(t => t.answer_text));
    const [dim, v] = ['specific', 'reasoning'].map(k => [k, dims[k]]).sort((a, b) => a[1] - b[1])[0];
    return v < 55 ? dim : null;
  }
  // The two standard questions. The follow-up is decided after the second answer (see interviewAnswer).
  function advance(s) {
    const turns = s.interview.turns, n = turns.length;
    if (n >= D.standardTurns) return null;
    const t = makeTurn(s, n === 0 ? 'implementation' : 'rationale', n + 1, 'standard');
    turns.push(t);
    return t;
  }
  // At most one follow-up: the model's question when it asks one that passed the server's checks; the template when the
  // model is not available or its question was filtered out; none when the model finds the answers need no follow-up.
  const PROBE_LABEL = { concrete: 'Be concrete', reasoning: 'Why this way', consequence: 'What could go wrong' };
  function followUp(s, ai) {
    if (ai && ai.needs_follow_up === false) return null;
    if (ai && ai.question) return { ...makeTurn(s, 'probe:specific', D.standardTurns + 1, 'follow-up'), key: 'probe:ai', label: PROBE_LABEL[ai.target] || 'Follow-up', question: ai.question, by: 'ai' };
    const dim = weakest(s);
    return dim ? makeTurn(s, 'probe:' + dim, D.standardTurns + 1, 'follow-up') : null;
  }

  // Simulated transcriber: speaking is answered with a stand-in text, split into timestamped segments.
  function segmentsFor(text, duration) {
    const guarded = text.replace(/(\d)\.(\d)/g, '$1\u0000$2');
    const raw = (guarded.match(/[^.!?\n]+[.!?]*/g) || [guarded]).map(x => x.replace(/\u0000/g, '.').trim()).filter(Boolean);
    const parts = [];
    for (const sent of raw) {
      if (words(sent) <= 14) { parts.push(sent); continue; }
      const cut = sent.indexOf(',', sent.length / 3);
      if (cut > 0 && cut < sent.length - 8) parts.push(sent.slice(0, cut + 1).trim(), sent.slice(cut + 1).trim()); else parts.push(sent);
    }
    const total = parts.reduce((a, p) => a + words(p), 0) || 1, lead = Math.min(0.6, duration * 0.05), span = Math.max(duration - lead - 0.2, 1);
    let at = lead;
    return parts.map(p => {
      const d = span * words(p) / total, seg = { start: round1(at), end: round1(at + d), text: p };
      at += d;
      return seg;
    });
  }
  const standIn = (s, key, profile) => setOf(s).answers[profile][key.startsWith('probe') ? 'probe' : key];

  // ---------- scoring: what a reviewed check adds to the portfolio ----------
  // Points = Risk x Novelty x Gap (1 to 27). Gap follows the concept level, which a pass raises and a second failure lowers.
  const SC = D.scoring;
  const clampLevel = x => Math.max(0, Math.min(3, x));
  const bandOf = n => SC.bands.find(b => n >= b.from && n <= b.to).key;
  const levelEvents = db => Object.values(db.sessions).flatMap(s => s.level_events.map(e => ({ ...e, title: s.pr.title }))).sort((a, b) => a.at - b.at);
  const levelOf = db => levelEvents(db).reduce((lv, e) => clampLevel(lv + e.delta), SC.concept.start);
  function pointsFor(level) {
    const g = level >= 3 ? 1 : level === 2 ? 2 : 3, n = SC.r * SC.n * g;
    let band = bandOf(n), floor = null;
    if (SC.r === 3 && band === 'skip') { band = 'light'; floor = 'Money flow is never skipped.'; } // the plan's hard rule for the highest risk
    return { r: SC.r, n: SC.n, g, s: n, band, floor, level };
  }
  const canRetake = s => s.stage === 'results' && !!s.assessment && s.assessment.verdict !== 'shown' && s.attempt < D.maxAttempts;
  function scoringView(db, s) {
    const sc = s.scoring, rv = s.review;
    const status = s.stage !== 'results' ? 'none' : !rv || rv.status === 'not_requested' ? 'retake' : rv.status === 'pending' ? 'pending' : rv.verdict === 'correction' ? 'earned' : 'declined';
    const ev = s.level_events[s.level_events.length - 1] || null;
    return {
      ...sc, max: SC.max, status, points: status === 'earned' ? sc.s : 0,
      why: { r: SC.why.r, n: SC.why.n, g: `${SC.concept.name} is at level ${sc.level} of 3.` },
      rubric: SC.rows, bands: SC.bands,
      concept: { name: SC.concept.name, before: sc.level, after: ev ? clampLevel(sc.level + ev.delta) : sc.level, reason: ev ? ev.reason : null },
      next: pointsFor(levelOf(db))
    };
  }

  // ---------- state and views ----------
  const newState = (pr, now, scoring) => ({
    id: b64u(rand(24)), stage: 'interview', version: 0, created: now, pr,
    attempt: 1, attempts: [], scoring, first_score: null, level_events: [], predict: null,
    interview: { turns: [], done: false }, assessment: null, review: null, finished: null,
    reviewer_token: null, access_log: [], media: {}
  });
  const turnView = t => ({ turn: t.turn, key: t.key, label: t.label, question: t.question, source: t.source, by: t.by || null, answered: t.answered, answer_text: t.answer_text, mode: t.mode, media_id: t.media_id });

  function view(db, s, now, opts = {}) {
    return {
      id: s.id, stage: s.stage, version: s.version, created: s.created, finished: s.stage === 'results' ? s.finished || null : null, pr: s.pr,
      attempt: s.attempt, max_attempts: D.maxAttempts, can_retake: canRetake(s),
      previous: s.attempts.map(a => ({ attempt: a.attempt, score: a.assessment.score, verdict: a.assessment.verdict })),
      camera_required: db.settings.cameraRequired !== false,
      predict: s.predict ? { answers: { ...s.predict.answers }, confidence: s.predict.confidence } : null,
      interview: { standard: D.standardTurns, max_turns: D.maxTurns, done: s.interview.done, turns: s.interview.turns.map(turnView) },
      assessment: s.stage === 'results' ? s.assessment : null,
      review: s.stage === 'results' ? s.review : null,
      scoring: scoringView(db, s),
      access_log: s.access_log.map(e => ({ ...e })),
      media: Object.values(s.media).map(m => ({ id: m.id, turn: m.turn, attempt: m.attempt, kind: m.kind, duration: m.duration })),
      reviewer_link: opts.presenter && s.reviewer_token ? `review.html#${s.reviewer_token}` : null
    };
  }
  function checkVersion(s, version) {
    if (s.version !== version) fail(409, 'This interview has already changed. Reload to continue; nothing was overwritten.');
  }
  function logAccess(s, actor, action, mediaId, turn, attempt) {
    s.access_log.push({ actor, action, media_id: mediaId || null, turn: turn || null, attempt: attempt || null, at: nowS() });
  }
  function openTurn(s, turn) {
    const iv = s.interview, cur = iv.turns[iv.turns.length - 1];
    if (s.stage !== 'interview') fail(409, 'The interview is over.');
    if (!cur || cur.turn !== turn || cur.answered) fail(409, 'That question is not open.');
    return cur;
  }

  // ---------- reviewer data ----------
  function reviewView(s, token) {
    return {
      role: 'senior', banner: 'Demo reviewer role. Not SSO.', token_hint: token.slice(0, 6),
      pr: s.pr, assessment: s.assessment, decision: s.review, requested: s.finished || null,
      attempt: s.attempt, max_attempts: D.maxAttempts, previous: s.attempts.map(a => ({ attempt: a.attempt, score: a.assessment.score, verdict: a.assessment.verdict })),
      turns: s.interview.turns.filter(t => t.answered).map(t => {
        const m = t.media_id ? s.media[t.media_id] : null;
        return {
          turn: t.turn, label: t.label, question: t.question, source: t.source, mode: t.mode, answer_text: t.answer_text,
          media: m ? { id: m.id, kind: m.kind, duration: m.duration } : null,
          segments: t.mode === 'voice' && m && m.segments ? m.segments.map(sg => ({ ...sg, flag: count(sg.text, RE.generic) ? 'Generic phrasing.' : null })) : null,
          marks: ((s.assessment.questions.find(q => q.turn === t.turn) || {}).segments) || [{ text: t.answer_text, kind: null }]
        };
      }),
      access_log: s.access_log.filter(e => e.media_id || e.action === 'open_review').map(e => ({ ...e }))
    };
  }

  // ---------- API ----------
  const api = {
    // What the GitHub check links to: the pull request and why it needs a check (Risk x Novelty x Gap at the current level).
    async check({ pr } = {}) {
      await sleep(80);
      const db = load(), sc = pointsFor(levelOf(db));
      return { pr: cleanPr(pr), scoring: { ...sc, max: SC.max, why: { r: SC.why.r, n: SC.why.n, g: `${SC.concept.name} is at level ${sc.level} of 3.` }, rubric: SC.rows, bands: SC.bands, concept: { name: SC.concept.name, level: sc.level } } };
    },

    async start({ pr } = {}) {
      await sleep(120);
      return tx(db => { const now = nowS(), s = newState(cleanPr(pr), now, pointsFor(levelOf(db))); db.sessions[s.id] = s; return view(db, s, now); });
    },

    async session(sid, { presenter = false } = {}) {
      return tx(db => view(db, getSession(db, sid), nowS(), { presenter }));
    },

    // Lock the three checks before the viva: what the code returns, whether it meets the rule, which test backs it.
    // Nothing about the right answers comes back until the results.
    async predict(sid, { version, answers = {}, confidence = null }, { presenter = false } = {}) {
      await sleep(200);
      return tx(db => {
        const s = getSession(db, sid), now = nowS(), task = taskOf(s);
        checkVersion(s, version);
        if (s.stage !== 'interview') fail(409, 'The interview is over.');
        if (s.predict) fail(409, 'Your answers are already locked.');
        const picked = {};
        for (const key of ITEMS) {
          if (!task.items[key].options.some(o => o.id === answers[key])) fail(422, 'Answer all three questions first.');
          picked[key] = answers[key];
        }
        if (!CONF.includes(confidence)) fail(422, 'Say how sure you are about question 1.');
        s.predict = { answers: picked, confidence, at: now };
        return view(db, s, now, { presenter });
      });
    },

    // First question, or the open one after a reload.
    async interviewNext(sid, { version }, { presenter = false } = {}) {
      await sleep(350);
      return tx(db => {
        const s = getSession(db, sid), now = nowS();
        checkVersion(s, version);
        if (s.stage !== 'interview') fail(409, 'The interview is over.');
        if (!s.predict) fail(409, 'Lock your answers to the three questions first.');
        const iv = s.interview, last = iv.turns[iv.turns.length - 1];
        if (iv.done) fail(409, 'The interview is complete.');
        if (last && !last.answered) return { ...turnView(last), view: view(db, s, now, { presenter }) };
        const t = advance(s);
        if (!t) fail(409, 'The interview is complete.');
        return { ...turnView(t), view: view(db, s, now, { presenter }) };
      });
    },

    async interviewAnswer(sid, { version, turn, text = '', media_id = null, mode = 'text' }, { presenter = false } = {}) {
      await sleep(500);
      const recorded = tx(db => {
        const s = getSession(db, sid), now = nowS();
        checkVersion(s, version);
        const cur = openTurn(s, turn);
        const answer = String(text).trim();
        if (answer.length < D.minAnswerChars) fail(422, `Say a little more (at least ${D.minAnswerChars} characters).`);
        if (!['voice', 'text'].includes(mode)) fail(422, 'Unknown answer mode.');
        const m = media_id ? s.media[media_id] : null;
        if (db.settings.cameraRequired !== false && !m) fail(422, 'The camera recording is required for every answer.');
        if (media_id && (!m || m.turn !== turn || m.used)) fail(403, 'That recording does not belong to this question.');
        Object.assign(cur, { answered: true, answer_text: answer, mode, media_id: m ? m.id : null });
        if (m) {
          m.used = true; m.mode = mode;
          m.segments = mode === 'voice' ? segmentsFor(answer, m.duration) : null;
        }
        const n = s.interview.turns.length;
        if (n < D.standardTurns) { const next = advance(s); return { done: false, ...turnView(next), view: view(db, s, now, { presenter }) }; }
        if (n > D.standardTurns) { s.interview.done = true; return { done: true, view: view(db, s, now, { presenter }) }; }
        return null; // after the second answer: decide on the follow-up below
      });
      if (recorded) return recorded;
      const snap = load().sessions[sid];
      const ai = V.ai ? await V.ai.followup(followupBody(snap)) : null;
      return tx(db => {
        const s = getSession(db, sid), now = nowS();
        if (s.stage !== 'interview' || s.interview.done || s.interview.turns.length !== D.standardTurns) fail(409, 'This interview has already changed. Reload to continue; nothing was overwritten.');
        const next = followUp(s, ai);
        if (next) s.interview.turns.push(next); else s.interview.done = true;
        return { done: !next, ...(next ? turnView(next) : {}), view: view(db, s, now, { presenter }) };
      });
    },

    async interviewFinish(sid, { version }, { presenter = false } = {}) {
      await sleep(150);
      const snap = getSession(load(), sid);
      checkVersion(snap, version);
      if (snap.stage !== 'interview') fail(409, 'The interview is over.');
      if (!snap.interview.done || snap.interview.turns.some(t => !t.answered)) fail(409, 'Answer every question first.');
      const ai = V.ai ? await V.ai.grade(gradeBody(snap)) : null;
      return tx(db => {
        const s = getSession(db, sid), now = nowS();
        checkVersion(s, version);
        if (s.stage !== 'interview') fail(409, 'The interview is over.');
        if (!s.interview.done || s.interview.turns.some(t => !t.answered)) fail(409, 'Answer every question first.');
        s.assessment = assess(s, ai);
        const passed = s.assessment.verdict === 'shown', last = s.attempt >= D.maxAttempts;
        if (s.attempt === 1) s.first_score = { score: s.assessment.score, at: now }; // only a first attempt counts toward the trend
        // A first failure is feedback and a second chance: nothing goes to a senior yet. A pass, or a failed retake, does.
        if (passed || last) {
          s.review = { status: 'pending' };
          if (!s.reviewer_token) {
            s.reviewer_token = b64u(rand(18));
            db.tokens[s.reviewer_token] = { sid: s.id, created: now };
          }
        } else s.review = { status: 'not_requested' };
        // The concept level: a pass moves it up, a failed retake moves it down, a first failure leaves it alone.
        if (passed) s.level_events.push({ at: now, delta: 1, attempt: s.attempt, reason: s.attempt === 1 ? 'Passed the interview.' : 'Passed the second attempt.' });
        else if (last) s.level_events.push({ at: now, delta: -1, attempt: s.attempt, reason: 'The second attempt did not pass. It needs more practice or a person to help.' });
        Object.assign(s, { stage: 'results', finished: now, version: s.version + 1 });
        return view(db, s, now, { presenter });
      });
    },

    // Second chance after a failed first attempt: the same change, a different set of questions.
    async retake(sid, { version }, { presenter = false } = {}) {
      await sleep(150);
      return tx(db => {
        const s = getSession(db, sid), now = nowS();
        checkVersion(s, version);
        if (!canRetake(s)) fail(409, 'A second attempt is not available.');
        s.attempts.push({ attempt: s.attempt, assessment: s.assessment, predict: s.predict, turns: s.interview.turns, finished: now });
        Object.assign(s, { attempt: s.attempt + 1, predict: null, interview: { turns: [], done: false }, assessment: null, review: null, finished: null, stage: 'interview', version: s.version + 1 });
        return view(db, s, now, { presenter });
      });
    },

    // Leave: delete the recordings, keep the answers.
    async leave(sid) {
      const ids = tx(db => {
        const s = db.sessions[sid];
        if (!s) return [];
        const list = Object.keys(s.media);
        s.media = {};
        s.interview.turns.forEach(t => { t.media_id = null; });
        list.forEach(id => { delete db.media[id]; });
        return list;
      });
      const results = await Promise.allSettled(ids.map(blobDel));
      return { left: true, media_deleted: ids.length, failed: results.filter(r => r.status === 'rejected').length };
    },

    async remove(sid) {
      const ids = tx(db => {
        const s = db.sessions[sid];
        const list = s ? Object.keys(s.media) : [];
        if (s && s.reviewer_token) delete db.tokens[s.reviewer_token];
        list.forEach(id => { delete db.media[id]; });
        delete db.sessions[sid];
        return list;
      });
      const results = await Promise.allSettled(ids.map(blobDel));
      return { deleted: true, failed: results.filter(r => r.status === 'rejected').length };
    },

    // ----- media -----
    async mediaUpload(sid, { blob, turn, kind = 'video', duration, mode = 'text' }) {
      if (duration > D.clipSeconds + 1) fail(413, `A single recording can be at most ${D.clipSeconds} seconds.`);
      const check = db => { const s = getSession(db, sid); return { s, cur: openTurn(s, turn) }; };
      check(load());
      const id = 'm_' + hex(rand(6));
      await blobPut(id, blob);
      let meta;
      try {
        meta = tx(db => {
          const { s, cur } = check(db);
          const text = mode === 'voice' ? standIn(s, cur.key, db.settings.voice) : null;
          const m = { id, sid, turn, attempt: s.attempt, kind, duration: round1(duration), mode, transcript: text, segments: text ? segmentsFor(text, duration) : null, created: nowS(), used: false };
          s.media[id] = m;
          db.media[id] = { sid };
          return m;
        });
      } catch (e) { await blobDel(id).catch(() => {}); throw e; }
      await sleep(mode === 'voice' ? 1100 : 200);
      return { media_id: id, transcript: meta.transcript, segments: meta.segments, duration: meta.duration, transcriber: meta.transcript ? 'simulated' : null };
    },

    // The learner discarded a recording before submitting (for example "Speak again").
    async mediaDiscard(sid, { media_id }) {
      const ok = tx(db => {
        const s = getSession(db, sid), m = s.media[media_id];
        if (!m) return false;
        if (m.used) fail(409, 'That recording is already part of an answer.');
        delete s.media[media_id]; delete db.media[media_id];
        return true;
      });
      if (ok) await blobDel(media_id).catch(() => {});
      return { discarded: ok };
    },

    async mediaLink(mediaId, { token = null, sid = null }) {
      const exp = Math.floor(nowS() + api.sim.linkTtl);
      const { secret, actor } = tx(db => {
        const meta = db.media[mediaId] || fail(404, 'Recording not found');
        const rt = token ? db.tokens[token] : null;
        const owner = token ? rt && rt.sid === meta.sid : sid === meta.sid;
        if (!owner) fail(403, 'You cannot open this recording.');
        const s = db.sessions[meta.sid], m = s.media[mediaId];
        const who = token ? 'reviewer:' + token.slice(0, 6) : 'learner';
        logAccess(s, who, 'sign', mediaId, m.turn, m.attempt);
        return { secret: db.secret, actor: who };
      });
      const sig = await hmac(secret, `${mediaId}.${exp}.${actor}`);
      return { url: `viva-media:${mediaId}?exp=${exp}&a=${encodeURIComponent(actor)}&sig=${sig}`, expires_at: exp };
    },

    async mediaFetch(url) {
      const m = /^viva-media:([\w-]+)\?exp=(\d+)&a=([^&]+)&sig=(\w+)$/.exec(url) || fail(400, 'Malformed link');
      const [, id, exp, actorEnc, sig] = m, actor = decodeURIComponent(actorEnc);
      const db = load();
      if (sig !== await hmac(db.secret, `${id}.${exp}.${actor}`)) fail(403, 'This link is not valid.');
      if (+exp < nowS()) fail(410, 'This link has expired. Request a new one.');
      const meta = db.media[id] || fail(404, 'Recording not found');
      const blob = await blobGet(id);
      if (!blob) fail(404, 'Recording not found');
      tx(d => { const s = d.sessions[meta.sid], mm = s.media[id]; logAccess(s, actor, 'play', id, mm.turn, mm.attempt); });
      return { objectUrl: URL.createObjectURL(blob), mime: blob.type };
    },

    // ----- reviewer -----
    // silent: refresh the page data without logging another "opened the review page" entry.
    async review(token, { silent = false } = {}) {
      await sleep(silent ? 0 : 150);
      return tx(db => {
        const rt = db.tokens[token] || fail(403, 'This link does not open a review.');
        const s = db.sessions[rt.sid] || fail(404, 'This review is no longer available.');
        if (!silent) logAccess(s, 'reviewer:' + token.slice(0, 6), 'open_review', null);
        return reviewView(s, token);
      });
    },

    // The role comes from the token; a role field in the body is ignored.
    async decide(token, { verdict, note = '' }) {
      await sleep(150);
      return tx(db => {
        const rt = db.tokens[token] || fail(403, 'Only a senior reviewer can decide.');
        const s = db.sessions[rt.sid];
        if (s.stage !== 'results' || !s.review || s.review.status === 'not_requested') fail(409, 'This interview is not waiting for a review.');
        // A senior either passes the check with a one-line correction on the concept, or asks for a follow-up.
        if (!['correction', 'followup'].includes(verdict)) fail(422, 'Choose a decision.');
        const text = String(note).trim().slice(0, 500);
        if (verdict === 'correction' && !text) fail(422, 'Write the one-line correction.');
        s.review = { status: 'decided', verdict, note: text, at: nowS(), reviewer: token.slice(0, 6) };
        return s.review;
      });
    },

    // ----- portfolio (private to the person; a reviewer token cannot read it) -----
    async portfolio() {
      await sleep(120);
      return tx(db => {
        const all = Object.values(db.sessions).sort((a, b) => a.created - b.created);
        const entries = all.filter(s => s.stage === 'results' && s.assessment).reverse().map(s => {
          const v = scoringView(db, s);
          return { sid: s.id, title: s.pr.title, repo: s.pr.repo, number: s.pr.number, at: s.created, attempt: s.attempt, score: s.assessment.score, verdict: s.assessment.verdict, r: s.scoring.r, n: s.scoring.n, g: s.scoring.g, s: s.scoring.s, band: s.scoring.band, status: v.status, points: v.points };
        });
        // Judgment score: the three code checks of first attempts only, the last ten, weighted by risk. Fewer than five shows no score at all.
        const firsts = all.filter(s => s.first_score).map(s => ({ at: s.first_score.at, score: s.first_score.score, w: s.scoring.r }));
        const recent = firsts.slice(-10), need = 5;
        const value = recent.length >= need ? Math.round(recent.reduce((a, p) => a + p.score * p.w, 0) / recent.reduce((a, p) => a + p.w, 0)) : null;
        let lv = SC.concept.start;
        const events = levelEvents(db).map(e => { const from = lv; lv = clampLevel(lv + e.delta); return { at: e.at, from, to: lv, reason: e.reason, title: e.title }; }).reverse();
        return {
          points: { total: entries.reduce((a, e) => a + e.points, 0), max_per_change: SC.max, confirmed: entries.filter(e => e.status === 'earned').length, entries },
          score: { value, n: firsts.length, needed: need, real: firsts.map(p => ({ at: p.at, score: p.score })) },
          concept: { name: SC.concept.name, level: lv, max: 3, events, next: pointsFor(lv) },
          rubric: SC.rows, bands: SC.bands
        };
      });
    },

    // ----- presenter controls (not part of the real API) -----
    sim: {
      linkTtl: 300,
      cameraRequired: () => load().settings.cameraRequired !== false,
      setCameraRequired(on) { tx(db => { db.settings.cameraRequired = !!on; }); },
      voice: () => load().settings.voice,
      setVoice(profile) { tx(db => { db.settings.voice = profile === 'generic' ? 'generic' : 'specific'; }); },
      async reset() {
        const ids = Object.keys(load().media);
        mem = null;
        try { localStorage.removeItem(KEY); } catch { /* storage blocked */ }
        await Promise.allSettled(ids.map(blobDel));
      }
    }
  };

  V.api = api;
  V.simInternals = { scoreTexts, features, simulatedViva, quoteMarks, assess, segmentsFor, weakest, pointsFor, bandOf };
})();
