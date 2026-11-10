"""Production license gate + build canary for GridFork (BSL 1.1).

Non-production use (development, testing, evaluation) is free and needs no
key. Production use (``GRIDFORK_ENV=production``) requires a paid license key
issued by the licensor; without a valid key the process refuses to boot.

Honesty note: this source is published, so a determined actor can remove the
check. The gate deters honest users, flags unlicensed use loudly, and makes
circumvention willful (visible in any diff). It is a legal tripwire, not DRM.

Key format: ``GF1.<base64url-json-payload>.<base64url-hmac-sha256>`` with
payload ``{"sub": email, "exp": unix_seconds, "canary": CANARY}``. Keys are
bound to the build canary: strip or rotate the canary and every issued key
stops verifying. The signing secret lives ONLY with the licensor; see
``scripts/issue_license.py``. Deployments verify with the same secret, so a
leaked secret enables key forging until rotated and reissued — guard it like
a password (BSL + this gate are the enforcement, not the math).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time

# Build canary. Unique per lineage; embedded as a functional ingredient, not a
# comment: license keys bind to it, /license/status exposes it, and the
# import-time assertion below fails the whole process if it is mangled or
# removed. A Google Alert on this exact string trips when a public copy, leak,
# or paste containing it gets indexed (public pages only — never private use).
CANARY = "GF-CANARY-edd38bf08e448991e83549147420714b"

_CANARY_RE = re.compile(r"^GF-CANARY-[0-9a-f]{32}$")

if not _CANARY_RE.match(CANARY):  # pragma: no cover - tripwire, not a path
    raise RuntimeError("GridFork build canary missing or mangled; refusing to boot.")

ENV_MODE = "GRIDFORK_ENV"
ENV_KEY = "GRIDFORK_LICENSE_KEY"
ENV_SECRET = "GRIDFORK_LICENSE_SECRET"
PRODUCTION = "production"
KEY_PREFIX = "GF1."


class LicenseError(Exception):
    """Machine-readable license failure; ``code`` is stable for clients."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def is_production(env: dict | os._Environ = os.environ) -> bool:
    return env.get(ENV_MODE, "").strip().lower() == PRODUCTION


def _b64decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def issue_license_key(
    secret: str, subject: str, days_valid: int, *, now: int | None = None
) -> str:
    """Mint a key. Founder-only; ``secret`` never belongs in the repo."""
    if not secret:
        raise LicenseError("missing_secret", "Signing secret is required.")
    subject = subject.strip()
    if not subject or days_valid <= 0:
        raise LicenseError("bad_request", "Subject and positive days_valid are required.")
    at = int(now if now is not None else time.time())
    payload = {"sub": subject, "exp": at + days_valid * 86400, "canary": CANARY}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
    return f"{KEY_PREFIX}{raw}.{base64.urlsafe_b64encode(sig).decode()}"


def verify_license_key(
    key: str, secret: str, *, now: int | None = None
) -> dict:
    """Return the payload dict, or raise LicenseError with a stable code."""
    if not secret:
        raise LicenseError("missing_secret", "Verification secret is not configured.")
    parts = (key or "").strip().split(".")
    if len(parts) != 3 or parts[0] != "GF1" or not parts[1] or not parts[2]:
        raise LicenseError("malformed", "License key format is GF1.<payload>.<sig>.")
    _, raw, given_sig = parts
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
    try:
        given = _b64decode(given_sig)
    except Exception:
        raise LicenseError("malformed", "License signature is not valid base64url.")
    if not hmac.compare_digest(given, expected):
        raise LicenseError("bad_signature", "License signature does not match.")
    try:
        payload = json.loads(_b64decode(raw))
    except Exception:
        raise LicenseError("malformed", "License payload is not valid JSON.")
    if not isinstance(payload, dict):
        raise LicenseError("malformed", "License payload shape is wrong.")
    if payload.get("canary") != CANARY:
        raise LicenseError("canary_mismatch", "License was issued for a different build lineage.")
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise LicenseError("malformed", "License expiry is missing or invalid.")
    at = int(now if now is not None else time.time())
    if at >= exp:
        raise LicenseError("expired", "License has expired.")
    return payload


def license_status(env: dict | os._Environ = os.environ) -> dict:
    """Public status shape for GET /license/status. Never leaks the secret."""
    prod = is_production(env)
    key = (env.get(ENV_KEY) or "").strip()
    secret = env.get(ENV_SECRET) or ""
    if not key:
        return {
            "mode": PRODUCTION if prod else "evaluation",
            "licensed": False,
            "reason": "missing" if prod else "evaluation_no_key_needed",
            "canary": CANARY,
        }
    try:
        payload = verify_license_key(key, secret)
    except LicenseError as exc:
        return {
            "mode": PRODUCTION if prod else "evaluation",
            "licensed": False,
            "reason": exc.code,
            "canary": CANARY,
        }
    return {
        "mode": PRODUCTION if prod else "evaluation",
        "licensed": True,
        "reason": "valid",
        "subject": payload.get("sub"),
        "expires": payload.get("exp"),
        "canary": CANARY,
    }


def enforce_license(env: dict | os._Environ = os.environ) -> dict | None:
    """Fail closed in production without a valid key; free otherwise.

    Call once at startup. Returns the payload (or None in unlicensed
    evaluation) so callers can log who is licensed.
    """
    if not is_production(env):
        key = (env.get(ENV_KEY) or "").strip()
        if not key:
            return None
        try:
            return verify_license_key(key, env.get(ENV_SECRET) or "")
        except LicenseError:
            return None
    key = (env.get(ENV_KEY) or "").strip()
    if not key:
        raise LicenseError(
            "missing",
            "GRIDFORK_ENV=production requires GRIDFORK_LICENSE_KEY. "
            "Contact stunrazor@gmail.com for a paid commercial license.",
        )
    return verify_license_key(key, env.get(ENV_SECRET) or "")
