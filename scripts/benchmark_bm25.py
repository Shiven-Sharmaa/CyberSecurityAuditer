"""
benchmark_bm25.py — C++ (nciipc_cpp) vs. pure-Python reference implementation
of the same chunking + BM25+ algorithm, timed side by side.

The pure-Python reference below is a line-for-line port of
nciipc-prep/src/chunker.cpp and nciipc-prep/src/bm25.cpp — same window/stride,
same k1/b/delta, same tokenization (whitespace split) — so the comparison
measures the language/runtime, not an algorithmic difference.

Usage:
    python scripts/benchmark_bm25.py [--scale N]

    --scale N   Repeat the synthetic corpus N times to simulate a larger
                multi-document batch (default: 20).
"""

import argparse
import math
import sys
import time
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "nciipc-prep" / "build"))

from smoke_test import TEST_DOCS  # 9 synthetic compliance documents
from scorer import FIELD_QUERIES  # the 15 real BM25 queries the app runs

WINDOW, STRIDE = 512, 384
K1, B, DELTA = 1.5, 0.75, 1.0


# ---------------------------------------------------------------------------
# Pure-Python reference implementation (mirrors the C++ source exactly)
# ---------------------------------------------------------------------------

def py_tokenize(text: str) -> list[str]:
    return text.split()


def py_chunk_document(doc_id: int, text: str, window: int = WINDOW, stride: int = STRIDE):
    tokens = py_tokenize(text)
    n = len(tokens)
    if n == 0:
        return []
    chunks = []
    idx = 0
    start = 0
    while start < n:
        end = min(start + window, n)
        chunks.append((doc_id, idx, start, end, " ".join(tokens[start:end])))
        idx += 1
        if end == n:
            break
        start += stride
    return chunks


class PyIndex:
    __slots__ = ("postings", "doc_lengths", "avg_dl", "N")

    def __init__(self):
        self.postings: dict[str, list[tuple[int, float]]] = {}
        self.doc_lengths: list[int] = []
        self.avg_dl = 0.0
        self.N = 0


def py_build_index(chunks: list[tuple]) -> PyIndex:
    idx = PyIndex()
    idx.N = len(chunks)
    idx.doc_lengths = [0] * idx.N
    total = 0
    for i, chunk in enumerate(chunks):
        toks = py_tokenize(chunk[4])
        dl = len(toks)
        idx.doc_lengths[i] = dl
        total += dl
        for term, freq in Counter(t.lower() for t in toks).items():
            idx.postings.setdefault(term, []).append((i, float(freq)))
    idx.avg_dl = total / idx.N if idx.N else 0.0
    return idx


def py_query_bm25(idx: PyIndex, query: str, k: int = 50) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for qt in py_tokenize(query):
        postings = idx.postings.get(qt.lower())
        if not postings:
            continue
        df = len(postings)
        idf = math.log((idx.N - df + 0.5) / (df + 0.5) + 1.0)
        for cid, tf in postings:
            dl = idx.doc_lengths[cid]
            num = tf * (K1 + 1.0)
            den = tf + K1 * (1.0 - B + B * (dl / idx.avg_dl))
            scores[cid] = scores.get(cid, 0.0) + idf * (num / den + DELTA)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:k]


# ---------------------------------------------------------------------------
# Benchmark harness
# ---------------------------------------------------------------------------

def build_corpus(scale: int) -> list[str]:
    base = list(TEST_DOCS.values())
    return (base * scale)[: scale * len(base)]


def bench_python(doc_texts: list[str]) -> dict[str, float]:
    t0 = time.perf_counter()
    all_chunks = []
    for i, text in enumerate(doc_texts):
        all_chunks.extend(py_chunk_document(i, text))
    t_chunk = time.perf_counter() - t0

    t0 = time.perf_counter()
    idx = py_build_index(all_chunks)
    t_index = time.perf_counter() - t0

    t0 = time.perf_counter()
    for q in FIELD_QUERIES.values():
        py_query_bm25(idx, q, 5)
    t_query = time.perf_counter() - t0

    return {"chunk_s": t_chunk, "index_s": t_index, "query_s": t_query,
            "chunks": len(all_chunks)}


def bench_cpp(doc_texts: list[str]) -> dict[str, float]:
    import nciipc_cpp

    t0 = time.perf_counter()
    nciipc_cpp.build_index(doc_texts)  # chunks + indexes in one call in C++
    t_build = time.perf_counter() - t0
    n_chunks = nciipc_cpp.get_chunk_count()

    t0 = time.perf_counter()
    for q in FIELD_QUERIES.values():
        nciipc_cpp.query_bm25(q, 5)
    t_query = time.perf_counter() - t0

    return {"build_s": t_build, "query_s": t_query, "chunks": n_chunks}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=int, default=20,
                        help="Repeat the 9-document synthetic corpus this many times")
    args = parser.parse_args()

    doc_texts = build_corpus(args.scale)
    total_words = sum(len(t.split()) for t in doc_texts)
    print(f"Corpus: {len(doc_texts)} documents, {total_words:,} words\n")

    py = bench_python(doc_texts)
    py_total = py["chunk_s"] + py["index_s"] + py["query_s"]
    print(f"Pure Python — chunk+index: {py['chunk_s'] + py['index_s']:.4f}s"
          f"  query x{len(FIELD_QUERIES)}: {py['query_s']:.4f}s"
          f"  total: {py_total:.4f}s  ({py['chunks']} chunks)")

    cpp = bench_cpp(doc_texts)
    cpp_total = cpp["build_s"] + cpp["query_s"]
    print(f"C++ (nciipc_cpp)   — chunk+index: {cpp['build_s']:.4f}s"
          f"  query x{len(FIELD_QUERIES)}: {cpp['query_s']:.4f}s"
          f"  total: {cpp_total:.4f}s  ({cpp['chunks']} chunks)")

    print(f"\nSpeedup — chunk+index: {(py['chunk_s'] + py['index_s']) / cpp['build_s']:.1f}x"
          f"   query: {py['query_s'] / cpp['query_s']:.1f}x"
          f"   overall: {py_total / cpp_total:.1f}x")


if __name__ == "__main__":
    main()
