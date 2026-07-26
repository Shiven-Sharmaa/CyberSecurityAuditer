# Architecture & Internals

Deep-dive documentation for the NCIIPC compliance scoring pipeline: the full request flow, a worked example, a file-by-file breakdown, the algorithms used, and how to run the smoke test. See [README.md](../README.md) for setup instructions.

## Table of contents

1. [Environment variables](#environment-variables)
2. [End-to-end pipeline flow](#end-to-end-pipeline-flow)
3. [Worked example: 3 documents uploaded](#worked-example-3-documents-uploaded)
4. [File-by-file breakdown](#file-by-file-breakdown)
5. [Algorithms and formulas](#algorithms-and-formulas)
6. [Call graph](#call-graph)
7. [Security measures](#security-measures)
8. [Logging](#logging)
9. [Smoke test](#smoke-test)
10. [Evaluation harness](#evaluation-harness)
11. [Benchmark](#benchmark)

## Environment variables

All environment variables are loaded from a `.env` file in the project root via `python-dotenv`. See [.env.example](../.env.example).

| Variable | Required? | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Yes | — | Your OpenRouter API key |
| `OPENROUTER_MODEL` | No | `google/gemma-3-27b-it:free` | Model used by `explain_control()` for audit findings |
| `OPENROUTER_VOTING_MODELS` | No | see below | Comma-separated model list for `vote_chunk()` |

If `OPENROUTER_VOTING_MODELS` isn't set, three free models are used by default:

1. `meta-llama/llama-3.1-8b-instruct:free`
2. `google/gemma-2-9b-it:free`
3. `mistralai/mistral-small-24b-instruct-2501:free`

**Important**: only use verified free-tier model IDs in `OPENROUTER_VOTING_MODELS`. Setting it to an unavailable or paid-tier model silently causes all LLM voting to fail, forcing the pipeline to fall back to regex rules for every chunk. When in doubt, omit the variable and let the defaults apply.

## End-to-end pipeline flow

```
User uploads file(s) via web UI
        │
        ▼
[1] TEXT EXTRACTION  (pipeline.py)
    PDF  → pdfplumber
    DOCX → python-docx
    TXT  → direct file read
    URL  → trafilatura
        │
        ▼
[2] CHUNKING  (nciipc_cpp C++ module, chunker.cpp)
    Sliding window: 512 tokens wide, 384 stride, 128-token overlap
        │
        ▼
[3] BM25 INDEX  (nciipc_cpp C++ module, bm25.cpp)
    Inverted index with BM25+ scoring
    Parameters: k1=1.5, b=0.75, delta=1.0
        │
        ▼
[4] RETRIEVAL  (scorer.py)
    For each of 16 field queries: retrieve top-5 chunks where BM25 score >= 1.0
        │
        ▼
[5] PER-CHUNK VOTING  (explain.py vote_chunk)
    Each chunk sent to 3 LLM models via OpenRouter
    Each model votes COMPLIANT (1.0) / PARTIAL (0.5) / NON_COMPLIANT (0.0)
    If all LLMs fail → regex labeling functions score the chunk instead
        │
        ▼
[6] AGGREGATION  (scorer.py)
    field_score   = mean(chunk_votes) * 100
    control_score = mean(field_scores for that control)
    company_score = weighted mean: (PC1*1.00 + PC2*0.90 + PC3*0.95) / 2.85
    Maturity label: L1 to L5
        │
        ▼
[7] EXPLANATION  (explain.py explain_control)
    One LLM call per control with weak/medium/strong evidence snippets
    Generates a 3-sentence audit finding
    Fallback: OpenRouter → local Ollama
        │
        ▼
[8] RESULTS returned as JSON to the web UI
    Rendered as score badges, control cards, findings, and a per-document table
```

## Worked example: 3 documents uploaded

A user uploads three files through the web UI: `policy.pdf` (a CII identification policy), `audit_report.docx` (an internal audit report), and `soc_charter.txt` (a SOC charter).

### Phase 1 — browser → Flask

The `analyse()` function in `index.html` reads the selected files, builds a `FormData` object appending each under the key `file`, and POSTs to `/score`. Flask's `score()` handler in `app.py`:

1. **Rate limit check** — looks up the client IP in `_rate_limits`, prunes timestamps older than 60s, and rejects with HTTP 429 if the count is already at 10 in the current window.
2. **File validation** — rejects any extension outside `{.pdf, .docx, .txt, .text}` with HTTP 400.
3. **Temp file creation** — each upload is saved via `tempfile.NamedTemporaryFile(delete=False)`; the path is tracked in `tmp_paths` for cleanup in the `finally` block.

### Phase 2 — text extraction

`pipeline.extract_text(path)` dispatches on file extension:

- **PDF** — `pdfplumber.open(path)`, iterating every page's `extract_text()`. A header/footer dedup pass then removes any line (stripped) that repeats more than 5 times across the document — this strips running headers, footers, and page numbers without touching legitimately repeated content.
- **DOCX** — `python-docx`'s `Document(path)`; collects non-empty paragraph text, then walks every table row and joins non-empty cells with `" | "` so tabular compliance data (checklists, criteria tables) survives extraction.
- **TXT** — `Path(source).read_text(encoding="utf-8", errors="ignore")`.

### Phase 3 — combined scoring

`scorer.score_documents(texts)` is the core of the pipeline:

1. `nciipc_cpp.build_index(texts)` clears the global chunk/index state, then for each document calls `chunk_document(doc_id, text, 512, 384)`:
   - Text is tokenized by whitespace splitting.
   - A sliding window (512 tokens, 384 stride, 128-token overlap) walks the token array, producing a `Chunk{doc_id, chunk_idx, token_start, token_end, text}` per window.
   - Chunks from all documents are concatenated into one global vector, e.g. 12 chunks from doc 0, 7 from doc 1, 3 from doc 2 → 22 chunks total.
2. `build_index()` (bm25.cpp) builds an inverted index over all chunks: tokenizes each chunk, records its length, computes raw term frequencies, and appends `(chunk_id, freq)` postings per term. Also computes `avg_dl` across all chunks.
3. For each of the 16 `FIELD_QUERIES` (e.g. `PC1_register`):
   - **BM25 retrieval**: `query_bm25(query, 5)` tokenizes the query, computes IDF per term, and for every chunk containing at least one query term computes the BM25+ contribution (see [formula](#bm25-scoring-formula) below). Results are partially sorted for the top 5.
   - **Threshold filter**: chunks scoring below `MIN_BM25_SCORE = 1.0` are discarded as low-confidence.
   - **No qualifying chunks** → the field scores 0.0. This encodes "absence of evidence is evidence of non-compliance."
   - **LLM voting**: each qualifying chunk goes to `vote_chunk(field, chunk_text)`, which prompts 3 models (temperature 0.0, `max_tokens=10`) to answer COMPLIANT / PARTIAL / NON_COMPLIANT, with up to 4 retries (exponential backoff) per model. Votes are logged to `logs/llm_calls/`.
   - **LF fallback**: if all 3 models fail, `score_chunk(text, LFS_PCn)` runs the relevant regex labeling functions and averages the non-abstaining votes instead.
   - `field_score = mean(chunk_scores) * 100`; the highest-scoring chunk is kept as `best_chunk` for evidence display.
4. **Aggregation**: `control_score` = mean of that control's field scores; `company_score` = weighted mean `(PC1*1.00 + PC2*0.90 + PC3*0.95) / 2.85`; each control score maps to a maturity label via [`maturity()`](#score-aggregation-and-maturity-mapping).

### Phase 4 — LLM explanations

For each control, `app.py` calls `explain_control(control, score, maturity, fields)`:

1. Fields are split into three bands: weak (`< 50`), medium (`50–64`), strong (`>= 65`).
2. Up to 3 weak + 2 medium + 2 strong `best_chunk` snippets (200 chars each) are concatenated into an evidence block — all three bands contribute evidence, so no score range is silently excluded from the explanation.
3. A prompt asks for a 3-sentence audit finding grounded only in that evidence, sent to OpenRouter at `temperature=0.1`.
4. On repeated failure, falls back to a local Ollama call (`ollama.generate(model="mistral", ...)`).

### Phase 5 — per-document breakdown

When more than one file is uploaded, each document is scored again individually with `score_documents([text], use_llm=False)` — a fresh single-document BM25 index, scored purely by the regex labeling functions (no LLM calls, so it's fast) — to produce a per-source score table alongside the combined result.

### Phase 6 — response → browser

`app.py` assembles the final JSON (`company_score`, per-control scores/maturity/findings/fields, `per_doc`), deletes all temp files in the `finally` block, and returns it. The frontend renders the hero score, per-control cards with findings, and (if multiple documents were uploaded) the per-document table.

## File-by-file breakdown

### `app.py` — Flask web server

HTTP entry point. Serves the web UI at `/` (static files from `web/`) and handles `POST /score`. Key behaviors:

- `MAX_CONTENT_LENGTH = 50 MB` — oversized uploads get HTTP 413 automatically.
- Rate limiting: per-IP sliding window, 10 requests / 60s, HTTP 429 when exceeded. Idle IPs are evicted from the tracking dict once their window empties, to bound memory growth.
- `/score` accepts either multipart file uploads or a JSON/form `url` field, extracts text, scores documents together (one shared BM25 index), generates per-control findings, and — when 2+ documents were submitted — a per-document breakdown.
- Runs with `threaded=False` deliberately: the C++ extension holds global mutable index state (`g_index`, `g_chunks`) with no locking, so concurrent requests would corrupt each other's results.

### `scripts/pipeline.py` — text extraction + CLI runner

`extract_from_pdf`, `extract_from_docx`, `extract_from_url`, and the `extract_text` dispatcher (see [Phase 2](#phase-2--text-extraction) above), plus `run(source)` — an end-to-end CLI pipeline (extract → score → explain) used by the `python scripts/pipeline.py <file-or-url>` entry point.

### `scripts/scorer.py` — retrieval + scoring engine

`FIELD_QUERIES` — 16 BM25 query strings, 5 for PC1, 4 for PC2, 6 unique for PC3 (`PC1_register/criteria/review/weakness/strength`, `PC2_vertical/horizontal/weakness/strength`, `PC3_ciso/isd/soc/audit/functions/weakness`). `FIELD_TO_LFS` maps each control prefix to its labeling-function list for the LLM fallback path. `maturity(score)` maps a 0–100 score to `L1`–`L5`. `score_documents(doc_texts, use_llm=True)` is the central function described in [Phase 3](#phase-3--combined-scoring) above; each field result also reports `llm_coverage` — the fraction of its chunks scored by LLM voting versus regex fallback.

### `scripts/explain.py` — LLM voting + finding generation

`vote_chunk(field, chunk_text)` and `explain_control(control, score, maturity, fields)` (see [Phase 3](#phase-3--combined-scoring) and [Phase 4](#phase-4--llm-explanations)). Both use an OpenRouter client (OpenAI-compatible, `base_url=https://openrouter.ai/api/v1`) with 4-attempt exponential backoff with jitter, and log every call (success or failure) to `logs/llm_calls/YYYY-MM-DD.jsonl` / `.errors.jsonl`. `generate_report(scores_path)` batch-generates findings from a previously saved `scores.json`.

### `scripts/labeling_functions.py` — regex fallback detectors

Snorkel-style weak-supervision labeling functions: each looks for one narrow signal and returns `COMPLIANT` (1.0), `PARTIAL` (0.5), `NON_COMPLIANT` (0.0), or `ABSTAIN` (`None`) if it has no opinion. 6 functions for PC1 (register existence, the six classification criteria, explicit absence of a register, periodic review, SCADA/OT exclusion, ad-hoc process language), 6 for PC2 (vertical/horizontal mapping, dependency matrix, inbound/outbound, explicit absence, grid-specific dependencies, staleness), 8 for PC3 (CISO reporting line — correct and incorrect, ISD existence/absence, 24/7 SOC, audit independence, the four ISD functions). `score_chunk(text, lfs)` runs every LF, filters abstains, and averages the rest — returning `0.0` (not `0.5`) when every LF abstains, so generic text with no compliance signal is scored as non-compliant rather than neutral.

### `scripts/smoke_test.py` — end-to-end validation

9 inline synthetic documents (3 per control × compliant/partial/non-compliant) exercise labeling functions, BM25 retrieval, the full scorer, and (if an API key is present) LLM explanation generation, without needing real compliance documents. See [Smoke test](#smoke-test) below.

### `nciipc-prep/src/chunker.cpp` + `include/chunker.h`

`tokenize(text)` — whitespace tokenization via `istringstream`; intentionally has no stemming or stop-word removal since BM25's IDF already down-weights common terms. `chunk_document(doc_id, text, window=512, stride=384)` — slides the window across the token array, producing a `Chunk{doc_id, chunk_idx, token_start, token_end, text}` per position; the last chunk may be shorter than the window.

### `nciipc-prep/src/bm25.cpp` + `include/bm25.h`

`Index{postings, doc_lengths, avg_dl, N}` — the inverted index structure. `build_index(idx, chunks)` tokenizes every chunk, records lengths and raw term frequencies, and populates `postings[term]`. Note it indexes chunks by their **sequential position** in the combined vector, not `chunk.chunk_idx` (which restarts at 0 per document) — this is what makes multi-document indexing collision-free. `query_bm25(idx, q, k)` implements BM25+ scoring (see [formula](#bm25-scoring-formula)) with a `partial_sort` for the top-k. `save_index(idx, path)` serializes the index to a simple binary format.

### `nciipc-prep/src/bindings.cpp` — pybind11 bindings

Exposes `build_index`, `query_bm25`, `get_chunk_text`, `get_chunk_count`, and `save_index` to Python, backed by global C++ state (`g_index`, `g_chunks`) — hence `app.py` running with `threaded=False`.

### `nciipc-prep/CMakeLists.txt`

Locates `pybind11`'s CMake config from the active Python environment (`python -m pybind11 --cmakedir`, invoked automatically), builds `nciipc_cpp` from `bindings.cpp` + `chunker.cpp` + `bm25.cpp`, and applies `/O2` (MSVC) or `-O3 -march=native` (GCC/Clang).

### `web/index.html` — frontend

Self-contained HTML/CSS/JS, no build step or framework. File upload (multi-file) and URL input, both posting to `/score`; renders the overall score, per-control cards (score badge, maturity badge, finding text), and — when multiple documents were analysed — a per-document score table.

## Algorithms and formulas

### Sliding-window chunking

Window = 512 tokens, stride = 384 tokens, overlap = 128 tokens. The overlap exists so that any span of evidence up to 128 tokens long is guaranteed to appear intact in at least one chunk, even if it straddles what would otherwise be a chunk boundary.

### BM25+ scoring formula

For query `Q` and chunk `D`:

```
score(Q, D) = Σ over each term t in Q of:
  idf(t) * [ tf(t,D)·(k1+1) / (tf(t,D) + k1·(1 - b + b·|D|/avgdl)) + delta ]

idf(t) = ln( (N - df(t) + 0.5) / (df(t) + 0.5) + 1.0 )
```

Parameters: `k1 = 1.5` (term-frequency saturation), `b = 0.75` (length normalization), `delta = 1.0` (BM25+'s lower-bound boost, ensuring a document containing a query term never scores exactly 0 for it regardless of length).

### LLM ensemble voting

Each (field, chunk) pair is sent to 3 models independently; the chunk's score is the mean of the returned votes (`COMPLIANT=1.0`, `PARTIAL=0.5`, `NON_COMPLIANT=0.0`). Averaging across differently-trained models reduces the impact of any single model hallucinating or misreading the text. `temperature=0.0` and `max_tokens=10` keep the vote deterministic and cheap; the prompt explicitly states that no mention of the compliance aspect should be read as non-compliance.

### Score aggregation and maturity mapping

```
chunk score (0–1)   = mean(LLM votes) or mean(LF votes)
field score (0–100) = mean(chunk scores for that field query) * 100
control score        = mean(field scores for that control)
company score         = (PC1*1.00 + PC2*0.90 + PC3*0.95) / 2.85
```

Weights reflect relative importance: PC1 (identification) is foundational to the other two controls, PC3 (governance) underpins operational maturity, PC2 (interdependency mapping) is important but slightly less foundational.

| Score | Maturity |
|---|---|
| ≥ 80 | L5 Optimising |
| ≥ 65 | L4 Managed |
| ≥ 50 | L3 Defined |
| ≥ 35 | L2 Developing |
| < 35 | L1 Initial |

### Exponential backoff retry

LLM API calls retry up to 4 times with jittered exponential backoff: `wait = base * 2^attempt * jitter`, `base = 1.0s`, `jitter ∈ [0.75, 1.25]` — roughly 1s, 2s, 4s, 8s between attempts. Jitter avoids synchronized retries (thundering herd) when multiple requests fail at once.

## Call graph

```
app.py /score endpoint
├─ pipeline.extract_text()
│  ├─ extract_from_pdf()      [pdfplumber]
│  ├─ extract_from_docx()     [python-docx]
│  ├─ extract_from_url()      [trafilatura]
│  └─ read TXT file           [Path.read_text]
│
├─ scorer.score_documents(texts)
│  ├─ nciipc_cpp.build_index(texts)
│  │  ├─ chunker.chunk_document()   [C++, 512-token window, 384 stride]
│  │  └─ bm25.build_index()         [C++, inverted index construction]
│  │
│  └─ for each of 16 FIELD_QUERIES:
│     ├─ nciipc_cpp.query_bm25()    [C++, top-5, min score 1.0]
│     ├─ nciipc_cpp.get_chunk_text()
│     ├─ explain.vote_chunk()       [LLM voting via OpenRouter]
│     │  ├─ _get_voting_models() / _get_client()
│     │  ├─ client.chat.completions.create()
│     │  ├─ _parse_vote()           [text → 0.0/0.5/1.0]
│     │  └─ _log_call() / _log_error()
│     └─ labeling_functions.score_chunk()  [fallback if LLMs fail]
│
├─ explain.explain_control()          [LLM audit finding, one per control]
│  ├─ OpenRouter (4 retries, exponential backoff)
│  └─ Ollama fallback (local mistral)
│
└─ scorer.score_documents(texts, use_llm=False)  [per-doc breakdown, LF-only]
```

## Security measures

1. **Upload size limit** — `MAX_CONTENT_LENGTH = 50 MB`; Flask rejects larger uploads with HTTP 413.
2. **File type validation** — only `.pdf`, `.docx`, `.txt`, `.text` are accepted; anything else is HTTP 400.
3. **Rate limiting** — 10 requests / IP / 60s sliding window (HTTP 429 past that), which also protects the OpenRouter key from being exhausted by a single client.
4. **Temp file cleanup** — every uploaded file is written to a temp path and unlinked in a `finally` block, even on exceptions.
5. **Single-threaded serving** — `threaded=False` prevents concurrent requests from corrupting the C++ extension's shared global index state.
6. **Secret handling** — `OPENROUTER_API_KEY` is only ever read from `.env` (never hardcoded), and `.env` is git-ignored.
7. **`.gitignore` coverage** — excludes `.env`, `.venv/`, `__pycache__/`, C++ build artifacts, `data/`, `logs/`, and `archive/` from version control, so API keys, large binaries, and any uploaded/sample documents never end up in the repo.

## Logging

LLM calls are logged as JSONL under `logs/llm_calls/`:

- **`YYYY-MM-DD.jsonl`** — successful calls: timestamp, control, model, prompt/response lengths, token usage, elapsed time, full prompt and response.
- **`YYYY-MM-DD.errors.jsonl`** — failed calls: timestamp, control, model, prompt length, error type/message, elapsed time.

Useful for debugging failures, monitoring latency, tracking token usage, and auditing which models were consulted for a given finding.

## Smoke test

```bash
python scripts/smoke_test.py
```

Runs against 9 inline synthetic documents (3 per control × compliant/partial/non-compliant) and checks:

| Stage | Expected |
|---|---|
| Labeling functions (isolated) | 9/9 pass |
| BM25 retrieval | 3/3 pass |
| Full scorer (end-to-end) | 9/9 pass (may vary with live LLM voting) |
| Explanation generation | pass, or skipped if no API key is configured |

Results are written to `data/processed/smoke_test_results.json`.

## Evaluation harness

```bash
python scripts/evaluate.py          # LF-only: fast, free, deterministic
python scripts/evaluate.py --llm    # also exercises the LLM ensemble
```

Reuses the same 9 labeled synthetic documents as the smoke test (imported from `smoke_test.TEST_DOCS`/`EXPECTED_LABELS`/`CONTROL_FOR_DOC`), but instead of a threshold pass/fail check, computes a full confusion matrix and per-label precision/recall/F1 plus overall accuracy and macro F1 — a stronger, more standard claim than "N/N pass." Results are written to `data/processed/eval_metrics.json`. See [Results](../README.md#results) in the README for the current numbers.

Note: `smoke_test.py`'s executable steps are wrapped in `if __name__ == "__main__":` specifically so its data (`TEST_DOCS`, `EXPECTED_LABELS`, `CONTROL_FOR_DOC`, `score_to_label_scorer`) can be imported by `evaluate.py` and `benchmark_bm25.py` without re-running the whole smoke test suite as an import side effect.

## Benchmark

```bash
python scripts/benchmark_bm25.py --scale 20
```

`nciipc-prep/src/chunker.cpp` and `bm25.cpp` are mirrored line-for-line in pure Python inside `benchmark_bm25.py` (same tokenization, same window/stride, same BM25+ formula and constants), so the timing comparison isolates the language/runtime rather than an algorithmic difference. `--scale N` repeats the 9-document synthetic corpus N times to simulate a larger multi-document batch. See [Results](../README.md#results) in the README for measured numbers at a few corpus sizes.
