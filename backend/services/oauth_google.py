"""
Google OAuth 2.0 — Authorization Code flow.

Flow:
  1. Frontend requests /api/auth/google/url → we generate a state token (CSRF)
     and return the Google consent URL
  2. User authorizes at Google; Google redirects to our configured
     redirect_uri with ?code=... &state=...
  3. Frontend AuthCallback.vue posts code+state to /api/auth/google/callback
  4. We verify state, exchange code → access_token → userinfo
  5. Return a JWT to the frontend

All Google API calls go through the Mihomo proxy (HTTPS_PROXY env var) so
they work on the CN server.
"""
from __future__ import annotations

import os
import secrets
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from services.auth_settings import load_google_config

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = ["openid", "email", "profile"]

# In-memory state store (small, short-lived). For multi-instance deployments
# this should migrate to Redis or a DB table.
_STATE_STORE: Dict[str, float] = {}
_STATE_TTL_SECONDS = 600


def _get_proxy() -> Optional[str]:
    return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


def generate_auth_url(db: Session) -> Tuple[str, str]:
    """Return (authorize_url, state). Caller redirects user to authorize_url."""
    import time

    cfg = load_google_config(db)
    client_id = cfg.get("client_id", "")
    redirect_uri = cfg.get("redirect_uri", "")
    if not client_id or not redirect_uri:
        raise RuntimeError("Google OAuth 未配置 (client_id / redirect_uri 缺失)")

    state = secrets.token_urlsafe(24)
    # Prune expired states opportunistically
    now = time.time()
    for s in list(_STATE_STORE.keys()):
        if _STATE_STORE[s] < now:
            _STATE_STORE.pop(s, None)
    _STATE_STORE[state] = now + _STATE_TTL_SECONDS

    params = {
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         " ".join(SCOPES),
        "access_type":   "online",
        "prompt":        "select_account",
        "state":         state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}", state


def consume_state(state: str) -> bool:
    """Validate and remove a state token. Returns True if valid (pops it)."""
    import time
    expiry = _STATE_STORE.pop(state, None)
    if expiry is None:
        return False
    return time.time() < expiry


async def exchange_code_for_token(db: Session, code: str) -> Dict:
    """Exchange authorization code for Google access token."""
    cfg = load_google_config(db)
    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    redirect_uri = cfg.get("redirect_uri", "")
    if not (client_id and client_secret and redirect_uri):
        raise RuntimeError("Google OAuth 未配置完整")

    data = {
        "code":          code,
        "client_id":     client_id,
        "client_secret": client_secret,
        "redirect_uri":  redirect_uri,
        "grant_type":    "authorization_code",
    }

    async with httpx.AsyncClient(timeout=20, proxy=_get_proxy()) as client:
        r = await client.post(TOKEN_URL, data=data)
        if r.status_code >= 400:
            raise RuntimeError(f"Google token exchange failed [{r.status_code}]: {r.text[:300]}")
        return r.json()


async def fetch_userinfo(access_token: str) -> Dict:
    """Retrieve the Google user profile using an access token."""
    async with httpx.AsyncClient(timeout=15, proxy=_get_proxy()) as client:
        r = await client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Google userinfo failed [{r.status_code}]: {r.text[:200]}")
        return r.json()
