"""
smoke_test.py — End-to-end smoke test for the NCIIPC compliance scoring pipeline.

Usage:
    python scripts/smoke_test.py

No real documents needed — all test data is inline.
"""

import sys
import json
import datetime
from pathlib import Path

# Force UTF-8 output so Unicode from OpenRouter / arrow chars don't crash on Windows CP1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Path setup — must happen before any project imports
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
BUILD_DIR   = ROOT / "nciipc-prep" / "build"

for p in (str(SCRIPTS_DIR), str(BUILD_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# STEP 1 — Synthetic test documents
# ---------------------------------------------------------------------------

TEST_DOCS = {

    # -- PC1 COMPLIANT ------------------------------------------------------
    "pc1_compliant": """
Critical Information Infrastructure (CII) Asset Identification — Policy and Register

The organisation maintains a comprehensive CII Asset Register, last reviewed and updated
in March 2024 and formally approved by the Board of Directors. The register covers all 847 IT
and OT/SCADA assets across the transmission and distribution network, classified under six
criteria: functionality in the energy supply chain, criticality scale (impact on 5 million+
consumers), degree of complementarity with adjacent sector systems, PESS values (political,
economic, social, security), strategic value to national energy security, and time duration
of potential disruption.

The identification process follows the NCIIPC guidelines issued in 2023. All CII assets,
including industrial control systems, SCADA platforms, energy management systems, and
supporting IT infrastructure, have been enumerated. A formal sign-off sheet, countersigned
by the CISO and submitted to NCIIPC, accompanies the register. Assets are tagged, version-
controlled, and stored in the enterprise GRC platform.

Periodic reviews are conducted semi-annually. The most recent annual review confirmed no
new assets had been omitted. The register is also updated on an ad-hoc basis whenever
significant infrastructure changes are commissioned. Change requests go through a formal
approval process before CII status is assigned or revoked.

The organisation has documented the review methodology, including criteria weights, scoring
rubrics, and governance sign-off requirements. This formal process ensures that critical
infrastructure identification remains consistent, auditable, and aligned with NCIIPC's
sector-specific guidelines.
""".strip(),

    # -- PC1 PARTIAL --------------------------------------------------------
    "pc1_partial": """
Asset Identification and CII Register — Current Status

The organisation has established a CII register covering its IT infrastructure assets,
including servers, network devices, and enterprise applications. The register was compiled
in 2022 and includes approximately 340 assets. Functionality and criticality scale have been
assessed for each listed asset. These two dimensions were selected by the IT team as the most
readily quantifiable, and the register has been signed off at IT-director level.

However, SCADA platforms and OT assets have been excluded from the current register scope.
Management acknowledged this gap during the audit but noted that those systems are
administered separately by the engineering division without formal CII classification.

Only two of the required classification dimensions have been applied. The remaining four
dimensions have not been addressed and no timeline for doing so has been confirmed. There is
no formal periodic review cycle; the last update was performed in 2022 and no scheduled
review has been planned.

A draft procedure for extending the register to operational technology assets is under
development. The organisation intends to broaden the scope by Q3 of the next financial year
but has not yet obtained Board approval for the revised approach.
""".strip(),

    # -- PC1 NON-COMPLIANT --------------------------------------------------
    "pc1_noncompliant": """
IT Asset Inventory — General Overview

The organisation maintains a general IT asset inventory managed by the IT helpdesk team.
Assets are logged as tickets are raised and are not systematically classified against any
national cybersecurity framework. There is no formal CII register in place. Critical
infrastructure identification is carried out on an ad hoc basis, with no documented
methodology, criteria, or approval chain.

No structured process exists for applying the six-criteria framework or any equivalent
classification standard. Assets have not been assessed for criticality scale, complementarity,
PESS values, or strategic importance. Several SCADA systems and operational technology
platforms are excluded from any inventory, as they are considered engineering assets outside
the IT department's remit.

The organisation has not submitted a CII register to NCIIPC. No sign-off has been obtained
from senior management or the Board. The undocumented and informal nature of current asset
identification means that there is no reliable baseline for incident response, risk
assessment, or regulatory compliance.

There is no formal process for periodic review. Changes to infrastructure are not reflected
in any centralised register. The organisation lacks awareness of the NCIIPC identification
guidelines and has not assigned ownership for CII compliance activities. Immediate
formalisation of the identification process is required.
""".strip(),

    # -- PC2 COMPLIANT ------------------------------------------------------
    "pc2_compliant": """
Interdependency Mapping — Critical Infrastructure Sectors

The organisation has developed and maintains both vertical interdependency and horizontal
interdependency maps for all CII assets in scope. The vertical interdependency map documents
information flow, supervisory control, and dependency chains from the national grid operator
down through transmission, regional distribution, and end-consumer segments. The horizontal
interdependency map captures peer-to-peer relationships with other sector organisations,
including fuel supply, telecommunications, and financial settlement systems.

An interdependency matrix formalises these relationships. Each cell identifies whether the
dependency is inbound (services consumed by the organisation) or outbound (services this
organisation provides to others). The matrix is version-controlled and reviewed semi-annually
by the CISO and the Business Continuity team.

Grid, transmission, and generation interdependencies are explicitly documented, with SLA
agreements and failover procedures referenced for each critical dependency. The organisation
has formally acknowledged all outbound dependencies with counterpart organisations, and
bilateral dependency registers have been exchanged.

The dependency matrix is stored in the enterprise GRC platform, is accessible to senior
management, and was last updated in January 2024 following a periodic review. All changes
are tracked, and the document is submitted to NCIIPC as part of the annual compliance
submission. The mapping process is repeatable, documented, and assigned to a named owner
within the CISO's office.
""".strip(),

    # -- PC2 PARTIAL --------------------------------------------------------
    "pc2_partial": """
Sector Dependency Assessment — Interim Report

The organisation has completed a vertical interdependency analysis covering the internal
hierarchy from corporate IT down to substation-level operational technology. The vertical
interdependency document identifies supervisory control flows, data exchange protocols, and
single points of failure within the organisation's own infrastructure stack. It was formally
approved in November 2023.

Cross-sector mapping with external peer organisations has not been completed. Discussions
have taken place with two telecommunications providers but no formal cross-sector mapping
document or chart has been produced. Dependencies sourced from external parties are partially
noted in a spreadsheet held by the Network Operations team, but services this organisation
provides to other sectors have not been catalogued.

An internal dependency matrix has been compiled for assets within the organisation's own
network boundaries. However, this matrix covers only the internal estate; it does not extend
to external sector relationships. There is a lack of cross-sector dependency document for
organisations outside this entity's perimeter. No criticality rating has been assigned to any
of the identified cross-sector relationships.

The organisation acknowledges the gap and has engaged a consultant to extend the dependency
matrix to cover external linkages. Completion is targeted for Q2 of the next financial year.
Peer organisations have agreed in principle to participate in a joint mapping exercise.
""".strip(),

    # -- PC2 NON-COMPLIANT --------------------------------------------------
    "pc2_noncompliant": """
Network Connectivity Overview

The organisation operates a Wide Area Network connecting its corporate offices, data centres,
and operational sites. Connectivity is overseen by the Network Operations team, which holds
basic topology diagrams for troubleshooting purposes. These diagrams have not been reviewed
since 2020 and have never been assessed from a sector resilience or CII perspective.

No vertical dependency analysis of supervisory control flows has been prepared. No
horizontal cross-sector assessment of relationships with peer organisations or adjacent
sectors has been conducted. No formal sector dependency document has been produced for
submission to NCIIPC, and no budget or ownership has been assigned for such an exercise.

Relationships with telecommunications providers and utility counterparts are governed solely
by commercial contracts. No business continuity or cyber resilience lens has been applied to
these arrangements. The organisation is unaware of NCIIPC requirements in this area and has
not engaged with sector peers on the topic of mutual dependency review.

The absence of any sector dependency documentation represents a significant gap. There is no
process for identifying which organisations this entity relies on for critical services, nor
which services it provides to others that would affect sector resilience. Immediate action is
required to commission a dependency assessment and produce the required documentation.
""".strip(),

    # -- PC3 COMPLIANT ------------------------------------------------------
    "pc3_compliant": """
Cybersecurity Governance Structure — Compliance Report

The organisation has established a robust cybersecurity governance framework aligned with
NCIIPC requirements. The Chief Information Security Officer (CISO) holds a dedicated
executive position and reports directly to the Chairman and Managing Director, ensuring
independence from operational IT functions and direct board-level visibility of cybersecurity
risk.

An Information Security Department (ISD) has been formally established with a written
charter, dedicated headcount, and budget authority. The ISD is structured around four
functions: planning (policy, strategy, and risk), development (security architecture and
project assurance), management (operations, incident response), and oversight (compliance,
audit coordination). This four-function model ensures comprehensive coverage of the
cybersecurity lifecycle.

A 24x7 Security Operations Centre provides continuous monitoring of all BES Cyber Systems
and critical network segments. The SOC uses a SIEM platform with correlation rules tuned to
the energy sector threat landscape and escalates incidents to the CISO within defined SLAs.

The internal audit function conducts annual penetration tests and compliance reviews. The
audit team is independent and separate from the ISD and CISO's office, reporting directly
to the Audit Committee of the Board. This independence ensures objective assessment of the
security posture without conflict of interest. All audit findings are tracked to closure
through the enterprise GRC platform.
""".strip(),

    # -- PC3 PARTIAL --------------------------------------------------------
    "pc3_partial": """
Information Security Function — Current Organisational Arrangements

The organisation appointed a Chief Information Security Officer in 2022. The CISO is
responsible for information security policy, risk management, and incident coordination.
However, the CISO currently reports to the CTO and IT Director rather than to the Head of
the organisation. This reporting line creates a potential conflict of interest, as the CISO's
remit overlaps with the IT division's operational responsibilities.

A dedicated Information Security Department has not been formally established. Security
functions are distributed across the IT team, with two security analysts embedded in the
Network Operations group and one compliance officer in the Risk department. There is no
unified ISD charter or organisational unit, though management has acknowledged the need to
consolidate these functions.

A Security Operations Centre exists and handles alert triage, vulnerability scanning, and
incident response. The SOC currently operates during business hours only (08:00–20:00 IST,
Monday to Friday). Out-of-hours coverage relies on automated alerting to on-call mobile
numbers, without a staffed monitoring capability.

Penetration testing is conducted annually by an external vendor. The testing scope covers
external-facing systems; internal OT networks are excluded. Findings are reported to the
CISO, who reviews and prioritises remediation. There is no formal audit independence
framework, and findings are not independently validated before closure.
""".strip(),

    # -- PC3 NON-COMPLIANT --------------------------------------------------
    "pc3_noncompliant": """
IT Security Arrangements — Observations

The organisation has no appointed CISO. Cybersecurity responsibilities are informally shared
between the IT Manager and the Head of Network Operations. No formal charter, mandate, or
reporting line for a CISO has been defined. Security decisions are made reactively with no
structured governance framework in place.

The organisation operates without a dedicated ISD. Security-related activities such as
patching, access provisioning, and log review are carried out by general IT staff as
secondary duties. No dedicated security headcount exists, and no separate security budget
line has been approved. The lack of ISD means there is no accountable owner for cybersecurity
programmes, risk registers, or audit coordination.

There is no SOC capability of any kind. Alert triage relies on a single network engineer
reviewing firewall summaries once a week. No SIEM platform, no threat intelligence feed, and
no incident response procedure exist. The absence of a SOC leaves the organisation blind to
intrusions outside weekly review windows.

No independent audit or pentest has been conducted in the past three years. Compliance
self-assessment is performed by the same IT staff who build and administer the systems,
with no separation between implementers and reviewers. The CISO role, ISD, and SOC are all
absent, representing a fundamental gap in the cybersecurity governance structure required
under NCIIPC guidelines.
""".strip(),
}

EXPECTED_LABELS = {
    "pc1_compliant":    "COMPLIANT",
    "pc1_partial":      "PARTIAL",
    "pc1_noncompliant": "NON_COMPLIANT",
    "pc2_compliant":    "COMPLIANT",
    "pc2_partial":      "PARTIAL",
    "pc2_noncompliant": "NON_COMPLIANT",
    "pc3_compliant":    "COMPLIANT",
    "pc3_partial":      "PARTIAL",
    "pc3_noncompliant": "NON_COMPLIANT",
}

# Score thresholds (0-1 scale, pre-multiplication)
LF_THRESHOLDS = {
    "COMPLIANT":    lambda s: s >= 0.60,
    "PARTIAL":      lambda s: 0.25 <= s <= 0.75,
    "NON_COMPLIANT": lambda s: s <= 0.45,
}

SCORER_THRESHOLDS = {
    "COMPLIANT":    lambda s: s >= 65,
    "PARTIAL":      lambda s: 35 <= s < 65,
    "NON_COMPLIANT": lambda s: s < 35,
}

CONTROL_FOR_DOC = {
    "pc1_compliant":    "PC1",
    "pc1_partial":      "PC1",
    "pc1_noncompliant": "PC1",
    "pc2_compliant":    "PC2",
    "pc2_partial":      "PC2",
    "pc2_noncompliant": "PC2",
    "pc3_compliant":    "PC3",
    "pc3_partial":      "PC3",
    "pc3_noncompliant": "PC3",
}

def score_to_label_scorer(score: float) -> str:
    if score >= 65:
        return "COMPLIANT"
    if score >= 35:
        return "PARTIAL"
    return "NON_COMPLIANT"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print(f"\n{'-'*60}")
    print(f"  {title}")
    print(f"{'-'*60}")


def main() -> None:
    failures: list[str] = []

    # ---------------------------------------------------------------------------
    # STEP 2 — Labeling functions isolation test
    # ---------------------------------------------------------------------------

    section("STEP 2 — Labeling Functions (isolation test)")

    lf_passes = 0
    lf_total  = 9

    try:
        from labeling_functions import (
            LFS_PC1, LFS_PC2, LFS_PC3,
            score_chunk,
        )
        print("  Import OK: labeling_functions")
    except ImportError as e:
        print(f"  IMPORT ERROR: {e}")
        print("  FIX: ensure scripts/ is in PYTHONPATH or run from repo root")
        sys.exit(1)

    LF_GROUPS = {
        "PC1": LFS_PC1,
        "PC2": LFS_PC2,
        "PC3": LFS_PC3,
    }

    DOC_PREFIX_MAP = {
        "pc1_compliant":    ("PC1", "COMPLIANT"),
        "pc1_partial":      ("PC1", "PARTIAL"),
        "pc1_noncompliant": ("PC1", "NON_COMPLIANT"),
        "pc2_compliant":    ("PC2", "COMPLIANT"),
        "pc2_partial":      ("PC2", "PARTIAL"),
        "pc2_noncompliant": ("PC2", "NON_COMPLIANT"),
        "pc3_compliant":    ("PC3", "COMPLIANT"),
        "pc3_partial":      ("PC3", "PARTIAL"),
        "pc3_noncompliant": ("PC3", "NON_COMPLIANT"),
    }

    print(f"\n  {'Doc':<22} {'Group':<5} {'Score':>6}  {'Expected':<14} {'Result'}")
    print(f"  {'-'*22} {'-'*5} {'-'*6}  {'-'*14} {'-'*6}")

    for doc_name, (group, expected) in DOC_PREFIX_MAP.items():
        text  = TEST_DOCS[doc_name]
        lfs   = LF_GROUPS[group]
        score = score_chunk(text, lfs)
        ok    = LF_THRESHOLDS[expected](score)
        status = "PASS" if ok else "FAIL"
        if ok:
            lf_passes += 1
        else:
            failures.append(
                f"LF [{doc_name}]: expected {expected} (threshold), got score={score:.3f}"
            )
        print(f"  {doc_name:<22} {group:<5} {score:>6.3f}  {expected:<14} {status}")

    print(f"\n  Labeling Functions: {lf_passes}/{lf_total} PASS")

    # ---------------------------------------------------------------------------
    # STEP 3 — BM25 index end-to-end
    # ---------------------------------------------------------------------------

    section("STEP 3 — BM25 Retrieval (end-to-end)")

    bm25_passes = 0
    bm25_total  = 3

    try:
        import nciipc_cpp
        print("  Import OK: nciipc_cpp")
    except ImportError as e:
        print(f"  IMPORT ERROR: {e}")
        print(f"  FIX: ensure {BUILD_DIR} contains nciipc_cpp.pyd")
        sys.exit(1)

    # Build index on all 9 docs
    all_texts = list(TEST_DOCS.values())
    print(f"\n  Building BM25 index on {len(all_texts)} synthetic documents …")
    nciipc_cpp.build_index(all_texts)
    chunk_count = nciipc_cpp.get_chunk_count()
    print(f"  Chunks indexed: {chunk_count}  (expect 9–50)")

    BM25_QUERIES = [
        "CII asset register six criteria SCADA OT identification",
        "vertical horizontal interdependency matrix inbound outbound",
        "CISO reports head organisation ISD SOC 24x7 independent audit",
    ]

    print(f"\n  {'#':<3} {'Query (first 55 chars)':<55} {'Top result (first 100 chars)'}")
    print(f"  {'-'*3} {'-'*55} {'-'*40}")

    for i, query in enumerate(BM25_QUERIES, 1):
        results = nciipc_cpp.query_bm25(query, 3)
        if results and results[0][1] > 0.0:
            top_text = nciipc_cpp.get_chunk_text(results[0][0])[:100].replace("\n", " ")
            print(f"  {i:<3} {query[:55]:<55} \"{top_text}\"")
            bm25_passes += 1
        else:
            print(f"  {i:<3} {query[:55]:<55} NO RESULTS — FAIL")
            failures.append(f"BM25 query {i} returned no results: '{query[:50]}'")

    print(f"\n  BM25 Retrieval: {bm25_passes}/{bm25_total} PASS")

    # ---------------------------------------------------------------------------
    # STEP 4 — scorer.py end-to-end
    # ---------------------------------------------------------------------------

    section("STEP 4 — Scorer (end-to-end, one doc at a time)")

    scorer_passes = 0
    scorer_total  = 9

    try:
        from scorer import score_documents
        print("  Import OK: scorer.score_documents")
    except ImportError as e:
        print(f"  IMPORT ERROR: {e}")
        print("  FIX: ensure scripts/ is in PYTHONPATH or run from repo root")
        sys.exit(1)

    print(f"\n  {'Doc':<22} {'Ctrl':<5} {'Score':>6}  {'Expected':<14} {'Predicted':<14} {'Result'}")
    print(f"  {'-'*22} {'-'*5} {'-'*6}  {'-'*14} {'-'*14} {'-'*6}")

    for doc_name, expected in EXPECTED_LABELS.items():
        control = CONTROL_FOR_DOC[doc_name]
        text    = TEST_DOCS[doc_name]

        result    = score_documents([text])
        score_val = result[control]["score"]
        predicted = score_to_label_scorer(score_val)
        ok        = predicted == expected
        status    = "PASS" if ok else "FAIL"

        if ok:
            scorer_passes += 1
        else:
            failures.append(
                f"Scorer [{doc_name}]: expected {expected}, got {predicted} (score={score_val:.1f})"
            )
        print(f"  {doc_name:<22} {control:<5} {score_val:>6.1f}  {expected:<14} {predicted:<14} {status}")

    print(f"\n  Scorer: {scorer_passes}/{scorer_total} PASS")

    # ---------------------------------------------------------------------------
    # STEP 5 — explain.py (OpenRouter)
    # ---------------------------------------------------------------------------

    section("STEP 5 — Explain (OpenRouter)")

    explain_status = "SKIP"
    explain_detail = "Not attempted"

    try:
        import openai  # noqa: F401 — check availability before importing generate_report
        from explain import generate_report

        print("  Import OK: openai, explain.generate_report")
        print("  Running scorer on all 9 docs combined …")
        combined_result = score_documents(all_texts)

        scores_path = PROCESSED_DIR / "scores.json"
        with open(scores_path, "w", encoding="utf-8") as fh:
            json.dump(combined_result, fh, indent=2)
        print(f"  Scores saved → {scores_path}")

        print("  Calling generate_report() — this may take 30–90 seconds …")
        generate_report(str(scores_path))

        # Verify audit_report.json
        report_path = PROCESSED_DIR / "audit_report.json"
        if not report_path.exists():
            raise FileNotFoundError(f"audit_report.json not created at {report_path}")

        with open(report_path, encoding="utf-8") as fh:
            report = json.load(fh)

        all_findings_ok = True
        for ctrl in ("PC1", "PC2", "PC3"):
            finding = report.get("findings", {}).get(ctrl, "")
            if not finding or len(finding) < 50:
                all_findings_ok = False
                failures.append(
                    f"Explain [{ctrl}]: finding missing or too short ({len(finding)} chars)"
                )

        if all_findings_ok:
            explain_status = "PASS"
            explain_detail = "audit_report.json created; all findings ≥ 50 chars"
        else:
            explain_status = "FAIL"
            explain_detail = "One or more findings are empty or too short"

    except (openai.APIConnectionError, ConnectionError, ConnectionRefusedError, OSError) as e:
        explain_status = "SKIP"
        explain_detail = str(e)
        print(f"  OpenRouter not reachable — skipping explain test.")
        print("  Check your OPENROUTER_API_KEY in .env")
    except openai.AuthenticationError as e:
        explain_status = "SKIP"
        explain_detail = str(e)
        print(f"  OpenRouter authentication failed — skipping explain test.")
        print("  Check your OPENROUTER_API_KEY in .env")
    except RuntimeError as e:
        explain_status = "SKIP"
        explain_detail = str(e)
        print(f"  {e}")
    except Exception as e:
        # Catch API connection errors that may surface as generic exceptions
        err_str = str(e).lower()
        if any(kw in err_str for kw in ("connect", "refused", "api_key", "authentication", "socket", "network")):
            explain_status = "SKIP"
            explain_detail = f"OpenRouter not reachable: {e}"
            print(f"  OpenRouter not reachable — skipping explain test.")
            print("  Check your OPENROUTER_API_KEY in .env")
        else:
            explain_status = "FAIL"
            explain_detail = str(e)
            failures.append(f"Explain: unexpected error — {e}")
            print(f"  FAIL: {e}")

    print(f"\n  Explain (Ollama): {explain_status}")

    # ---------------------------------------------------------------------------
    # STEP 6 — Final report
    # ---------------------------------------------------------------------------

    section("STEP 6 — Smoke Test Summary")

    lf_ok      = lf_passes      == lf_total
    bm25_ok    = bm25_passes    == bm25_total
    scorer_ok  = scorer_passes  == scorer_total
    explain_ok = explain_status in ("PASS", "SKIP")

    overall_pass = lf_ok and bm25_ok and scorer_ok and explain_ok

    print(f"""
    ==========================================
      NCIIPC PIPELINE SMOKE TEST RESULTS
    ==========================================
      Labeling Functions    {lf_passes}/{lf_total}   {'PASS' if lf_ok else 'FAIL'}
      BM25 Retrieval        {bm25_passes}/{bm25_total}   {'PASS' if bm25_ok else 'FAIL'}
      Scorer                {scorer_passes}/{scorer_total}   {'PASS' if scorer_ok else 'FAIL'}
      Explain (Ollama)      -    {explain_status}
    ==========================================
      Overall: {'PASS' if overall_pass else 'FAIL'}
    """)

    if failures:
        print("  Failures:")
        for f in failures:
            print(f"    - {f}")
        print()

    if overall_pass:
        print("  Pipeline is ready for real documents.")
    else:
        print("  Fix the failures above before running on real documents.")

    # ---------------------------------------------------------------------------
    # Save results JSON
    # ---------------------------------------------------------------------------

    results_payload = {
        "timestamp":     datetime.datetime.now().isoformat(),
        "lf_score":      f"{lf_passes}/{lf_total}",
        "bm25_score":    f"{bm25_passes}/{bm25_total}",
        "scorer_score":  f"{scorer_passes}/{scorer_total}",
        "explain_status": explain_status,
        "overall":       "PASS" if overall_pass else "FAIL",
        "failures":      failures,
    }

    results_path = PROCESSED_DIR / "smoke_test_results.json"
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results_payload, fh, indent=2)
    print(f"\n  Full results saved → {results_path}")


if __name__ == "__main__":
    main()
