"""
verify_report.py — checks a saved audit_report.json's HMAC signature.

Usage:
    python scripts/verify_report.py data/processed/audit_report.json

Requires AUDIT_SIGNING_KEY in .env to match the key used when the report was
signed (see audit_integrity.py) — without it, "invalid" may just mean the
key differs, not that the report was tampered with.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_integrity import verify


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_report.py <path-to-audit_report.json>")
        sys.exit(1)

    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))

    integrity = data.get("integrity")
    if not integrity:
        print(f"No integrity block found in {path} — this report predates "
              f"signing, or the block was stripped.")
        sys.exit(1)

    payload = {k: v for k, v in data.items() if k != "integrity"}
    ok = verify(payload, integrity)

    print(f"Report:    {path}")
    print(f"Signed at: {integrity['generated_at']}")
    print(f"Algorithm: {integrity['algorithm']}")
    if ok:
        print("Signature: VALID — content matches what was signed.")
    else:
        print("Signature: INVALID — either the report was modified after signing, "
              "or AUDIT_SIGNING_KEY differs from the key used to sign it.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
