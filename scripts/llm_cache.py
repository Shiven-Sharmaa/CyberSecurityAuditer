"""
llm_cache.py — sqlite cache for LLM compliance votes.

vote_chunk() calls the voting models at temperature=0.0, so a given
(model, field, chunk_text) triple always produces the same vote. Caching it
means re-running the pipeline on a document you've already scored doesn't
re-spend API calls or wall-clock time on chunks that were already voted on.

Failures are never cached — only a successful, parsed vote is stored, so a
transient model outage doesn't get "baked in" and prevent a later retry from
succeeding once the model recovers.
"""

import hashlib
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "llm_vote_cache.sqlite"


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS votes (key TEXT PRIMARY KEY, vote REAL NOT NULL)")
    return conn


def _key(model: str, field: str, chunk_text: str) -> str:
    return hashlib.sha256(f"{model}:{field}:{chunk_text}".encode("utf-8")).hexdigest()


def get(model: str, field: str, chunk_text: str) -> float | None:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT vote FROM votes WHERE key = ?", (_key(model, field, chunk_text),)
            ).fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def set(model: str, field: str, chunk_text: str, vote: float) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO votes (key, vote) VALUES (?, ?)",
                (_key(model, field, chunk_text), vote),
            )
    except sqlite3.Error:
        pass
