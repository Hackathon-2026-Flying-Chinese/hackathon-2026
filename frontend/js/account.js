/* window.Viva.account: who is signed in. On a server every check, level and point belongs to one GitHub login: the
   header avatar shows whose, the portfolio signs out, and with nobody signed in index.html and portfolio.html show the
   sign-in screen instead (review.html needs none: the reviewer link's token is the key). The simulator always signs in
   the demo person from data.js, and has nothing to sign out of. */
(() => {
  'use strict';
  const V = window.Viva, api = V.api, D = V.data;
  const { $, $$, esc, icon } = V;
  const arrow = `<span class="arrow">${icon('arrow', 14)}</span>`;

  // The signed-in person, or null; and how this server lets people sign in ({github, dev} or {local} in the simulator).
  const account = { user: null, auth: {}, load, header, signIn, signOut };

  async function load() {
    try {
      const r = await api.me();
      account.user = r.user; account.auth = r.auth || {};
    } catch (e) {
      if (e.status !== 401) throw e;
      account.user = null;
      account.auth = (await api.status().catch(() => ({}))).auth || {};
    }
    header(account.user);
    return account.user;
  }

  // The avatar at the top right: the person's picture (or their initial), and their name for the tooltip and the label.
  function header(user) {
    const av = $('.avatar');
    if (!av) return;
    av.hidden = !user;
    if (!user) return;
    const name = user.name || user.login, src = V.photo(user);
    av.dataset.initial = V.initials(name).charAt(0);
    av.innerHTML = src ? `<img src="${esc(src)}" alt="" width="30" height="30" data-av>` : '';
    av.setAttribute('aria-label', `${name}: your portfolio`);
    av.title = `Signed in as ${name}${user.login && user.login !== name ? ` (@${user.login})` : ''}. Open your portfolio.`;
  }

  // The sign-in screen. GitHub sends the person back to this exact address, so a check link (the pull request in the
  // query, the session in the hash) survives the trip. eyebrow: optional HTML naming what they were about to open.
  async function signIn(root, { presenter = false, eyebrow = '' } = {}) {
    const auth = account.auth;
    const gh = auth.github ? await api.githubUrl(location.pathname + location.search + location.hash) : null;
    document.title = 'Sign in | Viva';
    document.body.dataset.stage = 'signin';
    header(null);
    root.innerHTML = `
      <section class="solo" aria-labelledby="si-title">
        <div class="card solo-card" data-enter>
          <div class="solo-art">${V.mascot('talk')}</div>
          ${eyebrow ? `<p class="ph-eyebrow">${eyebrow}</p>` : ''}
          <h1 class="h1" id="si-title">Sign in to Viva</h1>
          <p class="muted">Your checks, levels and points are yours alone.</p>
          ${gh ? `<a class="btn btn-primary btn-lg" href="${esc(gh)}">Sign in with GitHub ${arrow}</a>` : ''}
          ${auth.dev ? `<form class="si-dev" id="si-dev" novalidate>
            ${gh ? '<p class="si-or"><span>or</span></p>' : ''}
            <h2 class="si-h">Sign in by GitHub login</h2>
            <div class="si-fields">
              <div class="field"><label for="si-login">GitHub login</label><input class="input" id="si-login" required maxlength="39" autocomplete="username" autocapitalize="none" spellcheck="false" value="${presenter ? esc(D.me.login) : ''}"></div>
              <div class="field"><label for="si-name">Name <span class="muted">(optional)</span></label><input class="input" id="si-name" maxlength="80" autocomplete="name" value="${presenter ? esc(D.me.name) : ''}"></div>
            </div>
            <p class="error-text" id="si-err" role="alert" hidden></p>
            <div class="si-go"><button class="btn ${gh ? 'btn-secondary' : 'btn-primary'}" type="submit">Sign in ${arrow}</button><span class="hint">No password. This server allows it for demos and local use only.</span></div>
          </form>` : ''}
          ${!gh && !auth.dev ? `<p class="si-none">${icon('info', 14)}<span>Sign-in is not set up on this server. Whoever runs it can turn on sign-in with GitHub (<span class="mono">GITHUB_CLIENT_ID</span> and <span class="mono">GITHUB_CLIENT_SECRET</span>).</span></p>` : ''}
        </div>
      </section>`;
    const form = $('#si-dev', root);
    if (form) {
      const err = $('#si-err', form), btn = $('button[type=submit]', form);
      const say = m => { err.textContent = m || ''; err.hidden = !m; };
      form.addEventListener('input', () => say(''));
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const login = $('#si-login', form).value.trim(), name = $('#si-name', form).value.trim();
        if (!login) { say('Enter a GitHub login.'); return; }
        btn.disabled = true;
        // signed in: load the same address again, so the page carries on where the person was
        try { await api.devLogin({ login, name: name || undefined }); location.reload(); } catch (x) { say(x.message); btn.disabled = false; }
      });
    }
    V.enter($$('[data-enter]', root), { y: 10, dur: 520 });
    if (!V.reduced()) $('.solo-art .mascot', root).animate([{ transform: 'scale(.3) rotate(-18deg)' }, { transform: 'none' }], { duration: V.SPRING.bounce.duration, delay: 160, easing: V.SPRING.bounce.easing, fill: 'backwards' });
  }

  // The session pointer in this browser belongs to the person who signs out, so it goes too.
  async function signOut() {
    await api.logout().catch(() => {});
    try { localStorage.removeItem('viva-session'); } catch { /* storage may be blocked */ }
    location.reload();
  }

  V.account = account;
})();
