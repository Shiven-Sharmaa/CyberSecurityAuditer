# NCIIPC Compliance Scoring Pipeline

An automated cybersecurity compliance auditor for organisations operating Critical Information Infrastructure (CII) in India. It ingests policy/audit documents (PDF, DOCX, TXT, or a URL), retrieves the passages relevant to each compliance requirement with a custom BM25+ engine, scores them with an LLM ensemble (regex-based rules as a fallback), and returns per-control scores, maturity levels, and natural-language audit findings through a web UI.

Built to evaluate compliance against three NCIIPC controls:

| Control | Name                     | Checks |
|---------|--------------------------|--------|
| PC1     | CII Identification       | Asset register, the 6 required classification criteria, periodic review |
| PC2     | Interdependency Mapping  | Vertical and horizontal mapping of dependencies between critical systems |
| PC3     | Cybersecurity Governance | CISO reporting line, dedicated ISD, 24/7 SOC, independent audit function |

Full technical write-up (pipeline internals, algorithms, file-by-file breakdown, worked example): **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## How it works

```
Upload (PDF/DOCX/TXT/URL)
        │
        ▼
  Text extraction  (pdfplumber / python-docx / trafilatura)
        │
        ▼
  Sliding-window chunking  (C++, 512-token window / 384 stride)
        │
        ▼
  BM25+ inverted index + retrieval  (C++, custom implementation)
        │
        ▼
  Per-chunk compliance voting  (LLM ensemble via OpenRouter, regex fallback)
        │
        ▼
  Score aggregation → per-control scores → maturity level (L1–L5)
        │
        ▼
  LLM-generated audit findings + JSON response → web UI
```

The retrieval and chunking layer is implemented in C++ (exposed to Python via pybind11) since it's the part of the pipeline that runs on every request; everything else is Python.

## Tech stack

Python 3.10+ · Flask · C++17 (pybind11) · OpenRouter (LLM ensemble voting, with a local Ollama fallback) · pdfplumber / python-docx / trafilatura for extraction

## Getting started

### Prerequisites

- Python 3.10+
- CMake 3.16+
- A C++17 compiler (gcc/clang on Linux/macOS, MinGW-w64 or MSVC on Windows)

### Setup

```bash
git clone <this-repo-url>
cd nciipc

python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\Activate.ps1 on Windows

pip install -r requirements.txt

cp .env.example .env             # then add your OpenRouter API key
```

### Build the C++ module

```bash
cd nciipc-prep
mkdir build && cd build
cmake .. -DPYBIND11_FINDPYTHON=ON
cmake --build . --config Release
```

This produces `nciipc_cpp` (a `.so` on Linux/macOS, a `.pyd` on Windows) which `scripts/scorer.py` imports directly.

### Run

```bash
python app.py                    # web UI at http://localhost:5000

python scripts/pipeline.py path/to/report.pdf   # single-document CLI

python scripts/smoke_test.py     # end-to-end check against synthetic docs, no API key required
```

## Environment variables

See [.env.example](.env.example). Only `OPENROUTER_API_KEY` is required — everything else has a sensible default. Full behavior is documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#environment-variables).

## Project structure

```
app.py                      Flask web server (main entry point)
requirements.txt            Python dependencies
.env.example                Template for local .env

scripts/
  pipeline.py                Text extraction + CLI runner
  scorer.py                  BM25 retrieval + LLM voting + score aggregation
  explain.py                 LLM voting calls + audit finding generation
  labeling_functions.py      Regex-based compliance signal detectors (fallback)
  smoke_test.py               End-to-end validation with synthetic documents

nciipc-prep/                 C++ performance module (chunking + BM25+)
  CMakeLists.txt
  include/                    chunker.h, bm25.h
  src/                        chunker.cpp, bm25.cpp, bindings.cpp (pybind11)

web/
  index.html                  Single-page frontend (no build step)
```

`data/`, `logs/`, and `archive/` are runtime output directories (scores, LLM call logs, sample corpora) and are git-ignored — they aren't part of the source tree.

## Design notes

- **Hybrid scoring**: every chunk is voted on by 3 LLM models; if all of them fail (rate limits, network errors), the pipeline falls back to a set of Snorkel-style regex labeling functions so the tool degrades gracefully instead of failing outright.
- **BM25+ from scratch**: the retrieval index (inverted index, IDF, BM25+ scoring with the `delta` lower-bound term) is a from-scratch C++ implementation rather than a library, since it's the hot path and needed to be fast enough to rebuild per-request.
- **Absence of evidence is evidence of non-compliance**: fields with no matching chunks above the BM25 threshold score 0 rather than being skipped, which is the correct behavior for a compliance auditor.
