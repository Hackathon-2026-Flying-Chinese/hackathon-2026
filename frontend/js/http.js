/* window.Viva.httpApi: the same methods as the simulator, over the Viva server (backend/viva/app.py). The server keeps
   the answer key, runs the assessment and asks the model; the browser only sends what the person did. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});

  class HttpError extends Error {
    constructor(status, detail) { super(detail); this.status = status; }
  }
  // Relative paths, so the app also works under a sub-path
  async function call(method, path, body, { query, form, timeout = 60000 } = {}) {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), timeout);
    const qs = query ? '?' + new URLSearchParams(Object.entries(query).filter(([, v]) => v)).toString() : '';
    let r;
    try {
      r = await fetch(path + (qs === '?' ? '' : qs), {
        method, signal: ctl.signal,
        headers: form || body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: form || (body === undefined ? undefined : JSON.stringify(body))
      });
    } catch (e) {
      throw new HttpError(0, e && e.name === 'AbortError' ? 'The server took too long to answer. Try again.' : 'The server could not be reached. Check your connection.');
    } finally { clearTimeout(timer); }
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new HttpError(r.status, (data && typeof data.detail === 'string' && data.detail) || `Request failed (${r.status}).`);
    return data;
  }
  const sess = sid => `api/sessions/${encodeURIComponent(sid)}`;
  const p = presenter => ({ presenter: presenter ? '1' : '' });

  V.httpApi = {
    status: () => call('GET', 'api/health').then(h => ({ ...h, backend: 'server' })),
    check: ({ pr } = {}) => call('POST', 'api/check', { pr }),
    start: ({ pr } = {}) => call('POST', 'api/sessions', { pr }),
    session: (sid, { presenter = false } = {}) => call('GET', sess(sid), undefined, { query: p(presenter) }),
    predict: (sid, body, { presenter = false } = {}) => call('POST', sess(sid) + '/predict', body, { query: p(presenter) }),
    interviewNext: (sid, body, { presenter = false } = {}) => call('POST', sess(sid) + '/next', body, { query: p(presenter) }),
    // the follow-up and the assessment can wait on the model
    interviewAnswer: (sid, body, { presenter = false } = {}) => call('POST', sess(sid) + '/answer', body, { query: p(presenter), timeout: 90000 }),
    interviewFinish: (sid, body, { presenter = false } = {}) => call('POST', sess(sid) + '/finish', body, { query: p(presenter), timeout: 120000 }),
    retake: (sid, body, { presenter = false } = {}) => call('POST', sess(sid) + '/retake', body, { query: p(presenter) }),
    leave: sid => call('POST', sess(sid) + '/leave', {}),
    remove: sid => call('DELETE', sess(sid)),

    // ----- media -----
    mediaUpload(sid, { blob, turn, kind = 'video', duration, mode = 'text' }) {
      const f = new FormData();
      f.append('blob', blob, 'answer');
      f.append('turn', String(turn)); f.append('kind', kind); f.append('duration', String(duration)); f.append('mode', mode);
      return call('POST', sess(sid) + '/media', undefined, { form: f, timeout: 120000 });
    },
    mediaDiscard: (sid, { media_id }) => call('DELETE', `${sess(sid)}/media/${encodeURIComponent(media_id)}`),
    mediaLink: (mediaId, { token = null, sid = null }) => call('POST', `api/media/${encodeURIComponent(mediaId)}/link`, { token, sid }),
    // One request per play, so the server logs one play; the page gets a local object URL like the simulator's.
    async mediaFetch(url) {
      let r;
      try { r = await fetch(url); } catch { throw new HttpError(0, 'The recording could not be loaded.'); }
      if (!r.ok) { const d = await r.json().catch(() => null); throw new HttpError(r.status, (d && d.detail) || 'The recording could not be loaded.'); }
      const blob = await r.blob();
      return { objectUrl: URL.createObjectURL(blob), mime: blob.type };
    },

    // ----- reviewer -----
    review: (token, { silent = false } = {}) => call('GET', `api/reviews/${encodeURIComponent(token)}`, undefined, { query: { silent: silent ? '1' : '' } }),
    decide: (token, body) => call('POST', `api/reviews/${encodeURIComponent(token)}/decision`, body),

    portfolio: () => call('GET', 'api/portfolio'),

    // ----- presenter controls (the server answers only in demo mode) -----
    demo: () => call('GET', 'api/demo'),
    demoSettings: body => call('POST', 'api/demo/settings', body),
    demoReset: () => call('POST', 'api/demo/reset')
  };
})();
