"""
audit_integrity.py — HMAC-SHA256 signing for generated audit results, so a
saved report can be independently checked for tampering later instead of
being trusted blindly ("chain of custody" for an automated audit finding).

Keyed by AUDIT_SIGNING_KEY (set it in .env — see .env.example). If it isn't
set, signing still works using a random key generated for this process only,
which means anything signed before a restart can no longer be verified after
one: fine for exercising the feature, not for real chain-of-custody use.
Set AUDIT_SIGNING_KEY in .env for signatures that need to stay verifiable.
"""

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

_KEY_ENV = "AUDIT_SIGNING_KEY"
_fallback_key: str | None = None


def _get_key() -> bytes:
    global _fallback_key
    key = os.environ.get(_KEY_ENV)
    if key:
        return key.encode("utf-8")
    if _fallback_key is None:
        _fallback_key = secrets.token_hex(32)
        print(f"WARNING: {_KEY_ENV} not set in .env — signing with an ephemeral "
              f"key for this process only. Reports signed now cannot be verified "
              f"after a restart. Set {_KEY_ENV} in .env for durable signatures.")
    return _fallback_key.encode("utf-8")


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(payload: dict) -> dict:
    """Return an integrity block ({"hmac", "generated_at", "algorithm"}) for `payload`."""
    generated_at = datetime.now(timezone.utc).isoformat()
    digest = hmac.new(_get_key(), _canonical({**payload, "_generated_at": generated_at}),
                       hashlib.sha256).hexdigest()
    return {"hmac": digest, "generated_at": generated_at, "algorithm": "HMAC-SHA256"}


def verify(payload: dict, integrity: dict) -> bool:
    """Recompute the HMAC for `payload` and check it against `integrity["hmac"]`."""
    expected = hmac.new(
        _get_key(),
        _canonical({**payload, "_generated_at": integrity["generated_at"]}),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, integrity["hmac"])
