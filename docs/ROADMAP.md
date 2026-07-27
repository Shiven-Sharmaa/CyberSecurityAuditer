# Roadmap

Planned follow-on work, grouped by theme. Phases 1–3 are implemented; the rest are designed but not yet built, tracked here so the plan isn't lost between sessions.

## Phase 1 — Evidence & credibility (done)

- Real Results section in the README (smoke test + evaluation harness numbers, not placeholders)
- `scripts/evaluate.py` — precision/recall/F1 against the labeled synthetic dataset, not just pass/fail
- `scripts/benchmark_bm25.py` — reproducible C++ vs. pure-Python timing comparison
- `scripts/generate_report_docx.py` surfaced in the README instead of being an orphaned script

## Phase 2 — Retrieval & LLM robustness (done)

- **Hybrid retrieval (BM25 + embeddings)**: `scorer._hybrid_rerank()` reranks each field's BM25 shortlist (top `CANDIDATE_K=15`) by blending normalized BM25 score with embedding cosine similarity, then keeps the top 5. Uses `fastembed` (ONNX runtime, `BAAI/bge-small-en-v1.5`) rather than torch/sentence-transformers to keep the dependency footprint small — no GPU, no multi-GB install. Falls back to plain BM25 ranking if `embeddings.embed()` returns `None`.
- **LLM ensemble confidence scoring**: `vote_chunk()` now returns `{"votes": [...], "confidence": ...}` — `confidence = 1 - (max(votes) - min(votes))`, `None` when fewer than 2 votes were collected. `scorer.py` aggregates this per field and per control as `confidence` / `needs_review` (flagged when confidence < `CONFIDENCE_THRESHOLD = 0.5`), surfaced in the API response and as a "⚠ Needs review" badge in the web UI.
- **Cache LLM votes**: `llm_cache.py` (sqlite, stdlib-only) keys each vote by `sha256(model + field + chunk_text)`, checked in `vote_chunk()` before each model call. Only successful votes are cached, so a transient failure doesn't block a later retry. Stored at `data/processed/llm_vote_cache.sqlite` (already git-ignored).

## Phase 3 — Security features (done)

- **Prompt-injection detection** (`scripts/prompt_injection.py`): a regex/heuristic scanner (same style as `labeling_functions.py`) checks every retrieved chunk for instruction-like phrases ("ignore previous instructions", "you are now", "new system prompt", etc.), independent of whether that chunk is scored by the LLM or the LF fallback. A match sets `prompt_injection_suspected` and `needs_review` on the field. Every LLM prompt in `explain.py` also explicitly frames document text as untrusted data to evaluate, never as instructions — defense in depth regardless of whether the heuristic fires. Verified end-to-end with a crafted malicious document.
- **Sensitive-data redaction before LLM calls** (`scripts/redaction.py`): regex-based redaction (emails, phone numbers, IPs, key-like strings) applied to chunk/evidence text immediately before it's sent to OpenRouter in `vote_chunk`/`explain_control` — only the outbound payload is redacted, not the locally stored/displayed evidence, and redaction counts are logged alongside the existing `_log_call` entries.
- **Tamper-evident audit trail** (`scripts/audit_integrity.py`, `scripts/verify_report.py`): HMAC-SHA256 (keyed by `AUDIT_SIGNING_KEY` in `.env`) over the canonical JSON of each result, added as `result["integrity"]`. Signed on both the `/score` response and the CLI's `audit_report.json`. `verify_report.py` independently re-derives and checks the signature — verified to correctly pass on untampered reports, fail on a tampered field, and fail (rather than silently pass) when checked with the wrong key.

## Phase 4 — Product depth

- **Gap-analysis / remediation suggestions**: extend the `explain_control()` prompt to also ask for 2-3 concrete remediation actions per weak field, surfaced as `result[control]["remediation"]` and rendered in the web UI under each control card.
- **OCR support for scanned PDFs**: detect near-empty `pdfplumber` extraction (heuristic: extracted characters per page below a threshold) and fall back to `pdf2image` + `pytesseract`. Requires the system `tesseract-ocr` binary — document as an optional prerequisite, not a hard requirement, since it can't be installed via pip alone.

## Also considered, deferred

- **Section-aware chunking** (split on detected headings instead of a blind token window) — a real quality improvement, but a C++ change with a smaller payoff than the items above; revisit if retrieval quality becomes a bottleneck after hybrid retrieval ships.
- **Larger evaluation set** — the current eval harness (`scripts/evaluate.py`) uses the same 9 labeled synthetic documents as the smoke test (N=9, 3 per control). Expanding this to a larger labeled set would make the precision/recall/F1 numbers statistically meaningful rather than just a regression check.
