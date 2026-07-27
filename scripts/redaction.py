"""
redaction.py — regex-based redaction of likely-sensitive data before text is
sent to a third-party LLM API (OpenRouter).

Compliance documents routinely contain personal and infrastructure details
(names' emails, phone numbers, internal IP addresses) that don't need to
leave your own infrastructure just to get a COMPLIANT/PARTIAL/NON_COMPLIANT
vote. redact() is applied only to the outbound API payload in explain.py —
the original chunk text is preserved everywhere else (scoring, best_chunk
evidence display, logs) since that never leaves the local process.

This is regex-based pattern matching, not a full PII/NER system — same
tradeoff as labeling_functions.py elsewhere in this codebase: good enough to
catch the common, clearly-structured cases, not a guarantee of zero leakage.
"""

import re

_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "phone": re.compile(r"\b\+?\d{1,3}[-.\s]\d{3,4}[-.\s]\d{3,4}\b"),
    "api_key": re.compile(r"\b(?:sk|pk|api|key|token)[-_][A-Za-z0-9]{16,}\b", re.I),
}


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Return (redacted_text, counts) where counts maps pattern name -> occurrences redacted."""
    counts: dict[str, int] = {}
    for name, pattern in _PATTERNS.items():
        text, n = pattern.subn(f"[REDACTED_{name.upper()}]", text)
        if n:
            counts[name] = n
    return text, counts
