"""Sign-in. Real use signs in with GitHub (OAuth web flow; the GitHub App's client id and secret work), so the person
taking a check is the GitHub author of the pull request. Demo mode, or VIVA_DEV_LOGIN=1, also offers a plain sign-in by
GitHub login, without a password, for local use only.

A login is a random token in an HttpOnly, SameSite=Lax cookie; the database keeps only its SHA-256.
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .engine import fail

log = logging.getLogger("viva.auth")

COOKIE = "viva_login"
STATE_COOKIE = "viva_oauth"
TTL = 30 * 24 * 3600
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")  # GitHub's login rule


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def safe_next(path):
    """Only a path on this site: never another host (//evil.example, /\\evil.example) or a scheme."""
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or "\\" in path or "\n" in path:
        return "/"
    return path[:500]


def public_user(u):
    return {"id": u["id"], "login": u["login"], "name": u["name"] or u["login"], "avatar_url": u["avatar_url"]}


class Auth:
    def __init__(self, store, demo=False, dev=None, http=None):
        self.store = store
        self.dev = demo or os.environ.get("VIVA_DEV_LOGIN") == "1" if dev is None else dev
        self.client_id = os.environ.get("GITHUB_CLIENT_ID")
        self.client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
        self.web = os.environ.get("GITHUB_WEB", "https://github.com").rstrip("/")
        self.api = os.environ.get("GITHUB_API", "https://api.github.com").rstrip("/")
        self.public_url = (os.environ.get("VIVA_PUBLIC_URL") or "").rstrip("/")
        self.http = http or httpx.Client(timeout=15, headers={"User-Agent": "viva"})

    @property
    def github(self):
        return bool(self.client_id and self.client_secret)

    def status(self):
        return {"github": self.github, "dev": self.dev}

    # ----- the signed-in person -----
    def user(self, request: Request):
        token = request.cookies.get(COOKIE)
        if not token:
            return None
        with self.store.tx():
            return self.store.login_user(token_hash(token), time.time())

    def require(self, request: Request):
        return self.user(request) or fail(401, "Sign in first.")

    @staticmethod
    def secure(request):
        return request.url.scheme == "https"

    def sign_in(self, request, response, user):
        token, at = secrets.token_urlsafe(32), time.time()
        with self.store.tx():
            self.store.add_login(token_hash(token), user["id"], at, at + TTL)
        response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, samesite="lax", secure=self.secure(request), path="/")
        return response

    # ----- OAuth state: a random value in a short-lived cookie, signed with the server secret -----
    def _sign(self, value):
        return hmac.new(self.store.setting("secret").encode(), value.encode(), hashlib.sha256).hexdigest()

    def callback_url(self, request):
        base = self.public_url or str(request.base_url).rstrip("/")
        return base + "/api/auth/github/callback"

    def router(self):
        r = APIRouter()

        @r.get("/api/me")
        def me(request: Request):
            return {"user": public_user(self.require(request)), "auth": self.status()}

        @r.post("/api/auth/dev")
        def dev_login(request: Request, body: dict = Body(default={})):
            if not self.dev:
                fail(404, "Not found")
            login = str(body.get("login") or "").strip()
            if not LOGIN_RE.match(login):
                fail(422, "Use a GitHub login: letters, digits and single hyphens, up to 39 characters.")
            name = str(body.get("name") or "").strip()[:80] or None
            with self.store.tx():
                user = self.store.upsert_user(login, name=name)
            return self.sign_in(request, JSONResponse({"user": public_user(user)}), user)

        @r.post("/api/auth/logout")
        def logout(request: Request):
            token = request.cookies.get(COOKIE)
            if token:
                with self.store.tx():
                    self.store.delete_login(token_hash(token))
            out = JSONResponse({"signed_out": True})
            out.delete_cookie(COOKIE, path="/")
            return out

        @r.get("/api/auth/github")
        def github_start(request: Request, next: str = "/"):
            if not self.github:
                fail(404, "Sign-in with GitHub is not set up on this server.")
            state = secrets.token_urlsafe(24)
            value = f"{state}|{safe_next(next)}"
            query = urlencode({"client_id": self.client_id, "redirect_uri": self.callback_url(request), "state": state,
                               "allow_signup": "false"})
            out = RedirectResponse(f"{self.web}/login/oauth/authorize?{query}", status_code=302)
            out.set_cookie(STATE_COOKIE, f"{value}|{self._sign(value)}", max_age=600, httponly=True, samesite="lax",
                           secure=self.secure(request), path="/api/auth/github")
            return out

        @r.get("/api/auth/github/callback")
        def github_callback(request: Request, code: str = "", state: str = ""):
            if not self.github:
                fail(404, "Sign-in with GitHub is not set up on this server.")
            parts = (request.cookies.get(STATE_COOKIE) or "").split("|")
            if len(parts) != 3 or not code or not state:
                fail(400, "This sign-in link is not valid. Start again.")
            saved, nxt, sig = parts
            if not hmac.compare_digest(sig, self._sign(f"{saved}|{nxt}")) or not hmac.compare_digest(saved, state):
                fail(400, "This sign-in link is not valid. Start again.")
            try:
                tok = self.http.post(f"{self.web}/login/oauth/access_token", headers={"Accept": "application/json"},
                                     data={"client_id": self.client_id, "client_secret": self.client_secret, "code": code,
                                           "redirect_uri": self.callback_url(request)})
                access = tok.json().get("access_token") if tok.status_code == 200 else None
                if not access:
                    fail(400, "GitHub did not accept this sign-in. Start again.")
                got = self.http.get(f"{self.api}/user", headers={"Authorization": f"Bearer {access}",
                                                                "Accept": "application/vnd.github+json"})
                got.raise_for_status()
                gh = got.json()
            except httpx.HTTPError as e:
                log.warning("GitHub sign-in failed: %s", e)
                fail(502, "GitHub could not be reached. Try again.")
            with self.store.tx():
                user = self.store.upsert_user(gh["login"], name=gh.get("name"), avatar_url=gh.get("avatar_url"), github_id=int(gh["id"]))
            out = self.sign_in(request, RedirectResponse(safe_next(nxt), status_code=302), user)
            out.delete_cookie(STATE_COOKIE, path="/api/auth/github")
            return out

        return r
