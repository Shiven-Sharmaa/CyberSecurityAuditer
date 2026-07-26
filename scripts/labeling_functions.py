"""labeling_functions.py — Regex-based compliance signal detectors. Called by scorer.py."""

import re

COMPLIANT     = 1.0
PARTIAL       = 0.5
NON_COMPLIANT = 0.0
ABSTAIN       = None


# ---------------------------------------------------------------------------
# PC1 — CII Identification
# ---------------------------------------------------------------------------

def lf_pc1_register_exists(text: str) -> float | None:
    return COMPLIANT if re.search(
        r"cii\s+(asset\s+)?register|critical.*infrastructure.*list", text, re.I
    ) else ABSTAIN


def lf_pc1_six_criteria(text: str) -> float | None:
    criteria = [
        "functionality",
        r"criticality|critical\s+scale",
        "complementar",
        r"pess|political.*economic.*social.*security",
        r"strategic\s+(value|importance)",
        r"time\s+duration|duration\s+of\s+(disruption|impact)",
    ]
    hits = sum(1 for c in criteria if re.search(c, text, re.I))
    if hits >= 5:
        return COMPLIANT
    if hits >= 3:
        return PARTIAL
    return ABSTAIN


def lf_pc1_no_register(text: str) -> float | None:
    return NON_COMPLIANT if re.search(
        r"(no|without|lack).{0,40}(cii register|asset register)", text, re.I
    ) else ABSTAIN


def lf_pc1_review_exists(text: str) -> float | None:
    return COMPLIANT if re.search(
        r"(periodic|annual|semi.annual).{0,40}review.{0,40}(cii|critical infra)", text, re.I
    ) else ABSTAIN


def lf_pc1_scada_excluded(text: str) -> float | None:
    return NON_COMPLIANT if re.search(
        r"(scada|ot system|operational tech).{0,60}(excluded|not included|exempt)", text, re.I
    ) else ABSTAIN


def lf_pc1_ad_hoc(text: str) -> float | None:
    return NON_COMPLIANT if (
        re.search(r"ad.hoc|no.{0,20}formal process|undocumented", text, re.I)
        and re.search(r"(cii|critical infrastructure)", text, re.I)
    ) else ABSTAIN


LFS_PC1 = [
    lf_pc1_register_exists,
    lf_pc1_six_criteria,
    lf_pc1_no_register,
    lf_pc1_review_exists,
    lf_pc1_scada_excluded,
    lf_pc1_ad_hoc,
]


# ---------------------------------------------------------------------------
# PC2 — Interdependency Mapping
# ---------------------------------------------------------------------------

def lf_pc2_both_maps(text: str) -> float | None:
    has_v = bool(re.search(r"vertical.{0,60}interdepend", text, re.I))
    has_h = bool(re.search(r"horizontal.{0,60}interdepend", text, re.I))
    if has_v and has_h:
        return COMPLIANT
    if has_v or has_h:
        return PARTIAL
    return ABSTAIN


def lf_pc2_matrix_exists(text: str) -> float | None:
    return COMPLIANT if re.search(
        r"dependency matrix|interdependency matrix", text, re.I
    ) else ABSTAIN


def lf_pc2_inbound_outbound(text: str) -> float | None:
    has_in  = bool(re.search(r"in.?bound",  text, re.I))
    has_out = bool(re.search(r"out.?bound", text, re.I))
    if has_in and has_out:
        return COMPLIANT
    return ABSTAIN


def lf_pc2_no_mapping(text: str) -> float | None:
    return NON_COMPLIANT if re.search(
        r"no.{0,40}(interdependency|dependency).{0,20}(map|matrix|document)", text, re.I
    ) else ABSTAIN


def lf_pc2_grid_dependency(text: str) -> float | None:
    return COMPLIANT if re.search(
        r"(grid|transmission|generation).{0,80}(interdepend|depend)", text, re.I
    ) else ABSTAIN


def lf_pc2_not_updated(text: str) -> float | None:
    return NON_COMPLIANT if re.search(
        r"(not updated|outdated|stale).{0,60}(map|matrix|interdependency)", text, re.I
    ) else ABSTAIN


LFS_PC2 = [
    lf_pc2_both_maps,
    lf_pc2_matrix_exists,
    lf_pc2_inbound_outbound,
    lf_pc2_no_mapping,
    lf_pc2_grid_dependency,
    lf_pc2_not_updated,
]


# ---------------------------------------------------------------------------
# PC3 — Cybersecurity Governance
# ---------------------------------------------------------------------------

def lf_pc3_ciso_reports_head(text: str) -> float | None:
    return COMPLIANT if re.search(
        r"ciso.{0,80}reports?\s+(directly\s+)?to.{0,40}(head|chairman|ceo|md|board)", text, re.I
    ) else ABSTAIN


def lf_pc3_ciso_wrong_report(text: str) -> float | None:
    return NON_COMPLIANT if re.search(
        r"ciso.{0,60}reports?.{0,20}(cto|it head|it director)", text, re.I
    ) else ABSTAIN


def lf_pc3_isd_exists(text: str) -> float | None:
    return COMPLIANT if re.search(
        r"information security department|isd.{0,20}(established|formed)", text, re.I
    ) else ABSTAIN


def lf_pc3_no_isd(text: str) -> float | None:
    return NON_COMPLIANT if re.search(
        r"(no|without|lack).{0,30}(isd|information security department)", text, re.I
    ) else ABSTAIN


def lf_pc3_soc_24x7(text: str) -> float | None:
    # Don't fire if the text negates SOC existence — let lf_pc3_no_soc handle that
    if re.search(r"(no|without|lack).{0,30}(soc|security operation)", text, re.I):
        return ABSTAIN
    has_soc  = bool(re.search(r"(soc|security operation)", text, re.I))
    has_24x7 = bool(re.search(r"(24.?7|round.the.clock|continuous monitoring)", text, re.I))
    if has_soc and has_24x7:
        return COMPLIANT
    if has_soc:
        return PARTIAL
    return ABSTAIN


def lf_pc3_no_soc(text: str) -> float | None:
    return NON_COMPLIANT if re.search(
        r"(no|without|lack).{0,30}(soc|security operation)", text, re.I
    ) else ABSTAIN


def lf_pc3_audit_independent(text: str) -> float | None:
    return COMPLIANT if re.search(
        r"audit.{0,60}(independent|separate).{0,60}(ciso|isd)", text, re.I
    ) else ABSTAIN


def lf_pc3_four_functions(text: str) -> float | None:
    funcs = ["planning", "development", "management", "oversight"]
    hits = sum(1 for f in funcs if re.search(f, text, re.I))
    if hits >= 3:
        return COMPLIANT
    if hits >= 2:
        return PARTIAL
    return ABSTAIN


LFS_PC3 = [
    lf_pc3_ciso_reports_head,
    lf_pc3_ciso_wrong_report,
    lf_pc3_isd_exists,
    lf_pc3_no_isd,
    lf_pc3_soc_24x7,
    lf_pc3_no_soc,
    lf_pc3_audit_independent,
    lf_pc3_four_functions,
]


# ---------------------------------------------------------------------------
# Aggregation helper
# ---------------------------------------------------------------------------

def score_chunk(text: str, lfs: list) -> float:
    """
    Run all LFs on text. Average the non-None results.
    If all abstain, return 0.0 — absence of evidence is not partial compliance.
    """
    votes = [lf(text) for lf in lfs]
    votes = [v for v in votes if v is not None]
    if not votes:
        return 0.0
    return sum(votes) / len(votes)

