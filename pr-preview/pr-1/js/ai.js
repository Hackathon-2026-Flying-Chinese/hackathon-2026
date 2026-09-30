/* window.Viva.ai: the two model calls of the viva, through the demo server (server.py): one follow-up question, and the
   rubric assessment. The model never sees the answer key of the three code checks. When the server, the key or the
   model is not available, every call resolves to null and the simulator falls back to its own viva, labelled Simulated. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  let statusP = null;

  async function post(path, body, ms) {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), ms);
    try {
      const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal });
      return r.ok ? await r.json() : null;
    } catch { return null; } finally { clearTimeout(timer); }
  }

  V.ai = {
    // { live, model }: a plain static server answers 404 here, which reads as "not live"
    status() {
      if (!statusP) statusP = fetch('api/viva/status').then(r => (r.ok ? r.json() : { live: false })).catch(() => ({ live: false }));
      return statusP;
    },
    async followup(body) { return (await V.ai.status()).live ? post('api/viva/followup', body, 15000) : null; },
    async grade(body) { return (await V.ai.status()).live ? post('api/viva/grade', body, 30000) : null; }
  };
})();
