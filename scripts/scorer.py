"""scorer.py — BM25 retrieval + LLM voting (LF fallback). Called by pipeline.py."""

import sys
from pathlib import Path
from statistics import mean

# ---------------------------------------------------------------------------
# Bootstrap: make sure nciipc_cpp is importable
# ---------------------------------------------------------------------------
_BUILD_DIR = str(Path(__file__).resolve().parent.parent / "nciipc-prep" / "build")
if _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

from labeling_functions import (
    LFS_PC1, LFS_PC2, LFS_PC3,
    score_chunk,
)
from explain import vote_chunk

# ---------------------------------------------------------------------------
# Query definitions
# ---------------------------------------------------------------------------

FIELD_QUERIES: dict[str, str] = {
    "PC1_register": "CII asset register identification categorization critical infrastructure",
    "PC1_criteria": "six criteria functionality criticality complementarity PESS strategic time duration",
    "PC1_review":   "periodic review update CII identification annual semi-annual",
    "PC1_weakness": "no register excluded SCADA OT ad hoc undocumented informal",
    "PC1_strength": "sign-off submitted NCIIPC formal process documented approved",
    "PC2_vertical": "vertical interdependency sector organisation division group supervision information flow",
    "PC2_horizontal": "horizontal interdependency matrix inbound outbound dependency peer organisation",
    "PC2_weakness": "no map not updated missing outbound no criticality rating",
    "PC2_strength": "SLA failover documented version controlled acknowledged",
    "PC3_ciso":     "CISO chief information security officer reports head organisation",
    "PC3_isd":      "information security department ISD established charter independent",
    "PC3_soc":      "SOC security operations centre 24x7 continuous monitoring",
    "PC3_audit":    "audit pentest team independent separate not report CISO",
    "PC3_functions": "planning development management oversight four functions ISD",
    "PC3_weakness": "no CISO conflict of interest reports CTO no SOC business hours paper only",
}

FIELD_TO_LFS: dict[str, list] = {
    "PC1": LFS_PC1,
    "PC2": LFS_PC2,
    "PC3": LFS_PC3,
}

TOP_K = 5
MIN_BM25_SCORE = 1.0


# ---------------------------------------------------------------------------
# Maturity mapping
# ---------------------------------------------------------------------------

def maturity(score: float) -> str:
    if score >= 80:
        return "L5 Optimising"
    if score >= 65:
        return "L4 Managed"
    if score >= 50:
        return "L3 Defined"
    if score >= 35:
        return "L2 Developing"
    return "L1 Initial"


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def score_documents(doc_texts: list[str], use_llm: bool = True) -> dict:
    """
    Build a BM25 index from doc_texts, score every FIELD_QUERIES entry,
    aggregate per control and for the whole company, and return the results dict.
    """
    import nciipc_cpp  # noqa: PLC0415 — must come after sys.path update

    # 1. Build index
    print("Building BM25 index …")
    nciipc_cpp.build_index(doc_texts)
    chunk_count = nciipc_cpp.get_chunk_count()
    print(f"  Indexed {chunk_count} chunks from {len(doc_texts)} documents.")

    # 2. Score each field (LLM voting with LF fallback)
    field_results: dict[str, dict] = {}

    for field, query in FIELD_QUERIES.items():
        prefix = field.split("_")[0]          # "PC1", "PC2", or "PC3"
        lfs = FIELD_TO_LFS[prefix]

        # BM25 retrieval — filter out low-confidence matches
        raw = nciipc_cpp.query_bm25(query, TOP_K)
        results = [(cid, s) for cid, s in raw if s >= MIN_BM25_SCORE]
        texts   = [nciipc_cpp.get_chunk_text(cid) for cid, _ in results]

        if not texts:
            # No evidence found — absence = non-compliant
            print(f"  [{field}] No qualifying chunks — non-compliant (0.0).")
            field_results[field] = {"score": 0.0, "best_chunk": ""}
            continue

        # Score each retrieved chunk: try LLM voting, fall back to LFs
        chunk_scores = []
        llm_chunks = 0
        lf_chunks  = 0
        for text in texts:
            llm_votes = vote_chunk(field, text) if use_llm else []
            if llm_votes:
                chunk_scores.append(mean(llm_votes))
                llm_chunks += 1
            else:
                chunk_scores.append(score_chunk(text, lfs))
                lf_chunks += 1
                if use_llm:
                    print(f"  [{field}] LLM voting failed for a chunk — used LF fallback.")

        field_score = mean(chunk_scores) * 100.0          # 0-100 scale
        total_chunks = llm_chunks + lf_chunks
        llm_coverage = round(llm_chunks / total_chunks, 2) if total_chunks else 0.0

        # Best chunk = highest score
        best_idx   = chunk_scores.index(max(chunk_scores))
        best_chunk = texts[best_idx]

        field_results[field] = {
            "score": round(field_score, 2),
            "best_chunk": best_chunk,
            "llm_coverage": llm_coverage,
        }
        print(f"  [{field}] score={field_score:.1f}/100  best_chunk_len={len(best_chunk)}")

    # 3. Aggregate per control — all fields now have numeric scores (0.0 if no evidence)
    def control_score(prefix: str) -> float:
        scores = [v["score"] for k, v in field_results.items()
                  if k.startswith(prefix)]
        return round(mean(scores), 2) if scores else 0.0

    def control_has_evidence(prefix: str) -> bool:
        return any(v["best_chunk"] != ""
                   for k, v in field_results.items() if k.startswith(prefix))

    pc1_score = control_score("PC1")
    pc2_score = control_score("PC2")
    pc3_score = control_score("PC3")

    # Weighted company score
    company_score = round(
        (pc1_score * 1.00 + pc2_score * 0.90 + pc3_score * 0.95) / 2.85, 2
    )

    # 4. Build output structure
    def control_fields(prefix: str) -> dict:
        return {k: v for k, v in field_results.items() if k.startswith(prefix)}

    return {
        "company_score": company_score,
        "PC1": {
            "score":        pc1_score,
            "maturity":     maturity(pc1_score),
            "has_evidence": control_has_evidence("PC1"),
            "fields":       control_fields("PC1"),
        },
        "PC2": {
            "score":        pc2_score,
            "maturity":     maturity(pc2_score),
            "has_evidence": control_has_evidence("PC2"),
            "fields":       control_fields("PC2"),
        },
        "PC3": {
            "score":        pc3_score,
            "maturity":     maturity(pc3_score),
            "has_evidence": control_has_evidence("PC3"),
            "fields":       control_fields("PC3"),
        },
    }

