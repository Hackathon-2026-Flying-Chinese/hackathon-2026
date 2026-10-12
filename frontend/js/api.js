/* window.Viva.api: the server when one answers at api/health, otherwise the simulator in this browser (a static host,
   or a plain file server). Decided once per page; every method waits for that decision. */
(() => {
  'use strict';
  const V = (window.Viva = window.Viva || {});
  let pick = null;
  const backend = () => {
    if (!pick) {
      pick = fetch('api/health', { cache: 'no-store' })
        .then(r => (r.ok ? r.json() : null))
        .then(h => (h && h.service === 'viva' ? V.httpApi : V.simApi))
        .catch(() => V.simApi);
    }
    return pick;
  };
  V.api = new Proxy({}, { get: (_, name) => async (...args) => (await backend())[name](...args) });
})();
