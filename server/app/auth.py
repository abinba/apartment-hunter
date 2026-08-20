"""Firebase ID token verification without the admin SDK.

Deliberately no service-account JSON anywhere in this stack. Google publishes
the public certificates that sign ID tokens; verifying against those gives the
same guarantee with nothing secret to leak, lose or accidentally commit.
"""
from __future__ import annotations

import time
import threading
import logging

import httpx
from jose import jwt
from jose.utils import base64url_decode  # noqa: F401  (import validates the backend)
from fastapi import HTTPException, Request

log = logging.getLogger("auth")

CERT_URL = ("https://www.googleapis.com/robot/v1/metadata/x509/"
            "securetoken@system.gserviceaccount.com")

_certs: dict[str, str] = {}
_certs_at: float = 0.0
_lock = threading.Lock()


def _get_certs() -> dict[str, str]:
    global _certs, _certs_at
    with _lock:
        if _certs and time.time() - _certs_at < 3600:
            return _certs
        r = httpx.get(CERT_URL, timeout=10)
        r.raise_for_status()
        _certs = r.json()
        _certs_at = time.time()
        return _certs


def verify_token(token: str, project_id: str) -> dict:
    """Return the token claims, or raise HTTPException(401)."""
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        certs = _get_certs()
        cert = certs.get(kid)
        if not cert:                       # key rotated since we cached
            _certs.clear()
            cert = _get_certs().get(kid)
        if not cert:
            raise ValueError("unknown signing key")

        claims = jwt.decode(
            token, cert, algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            options={"verify_at_hash": False},
        )
    except Exception as e:                 # noqa: BLE001 - all failures are 401
        log.info("token rejected: %s", e)
        raise HTTPException(status_code=401, detail="invalid or expired sign-in") from e

    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="token has no subject")
    return claims


async def require_user(request: Request) -> dict:
    """FastAPI dependency: verified, allow-listed caller or 401/403."""
    cfg = request.app.state.cfg
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="sign in first")
    claims = verify_token(header[7:].strip(), cfg.firebase_project_id)

    allowed = cfg.allowed_emails
    email = (claims.get("email") or "").lower()
    if allowed and email not in allowed:
        log.warning("blocked non-allow-listed caller: %s", email or claims.get("sub"))
        raise HTTPException(status_code=403,
                            detail="this account may not use the scraper")
    return claims
