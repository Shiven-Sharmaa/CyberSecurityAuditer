"""
evaluate.py — Precision/recall/F1 evaluation of the scorer against the 9
labeled synthetic documents (the same dataset smoke_test.py uses), instead of
just a pass/fail threshold check.

Usage:
    python scripts/evaluate.py            # LF-only (fast, free, deterministic)
    python scripts/evaluate.py --llm      # also exercise the LLM ensemble

Note: with only 9 labeled documents (3 per control x 3 classes), this is a
small evaluation set — good enough to catch regressions and report a
reproducible number, not a substitute for a large labeled compliance corpus.
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "nciipc-prep" / "build"))

from smoke_test import TEST_DOCS, EXPECTED_LABELS, CONTROL_FOR_DOC, score_to_label_scorer
from scorer import score_documents

LABELS = ("COMPLIANT", "PARTIAL", "NON_COMPLIANT")


def confusion_matrix(y_true: list[str], y_pred: list[str]) -> dict[str, dict[str, int]]:
    matrix = {t: {p: 0 for p in LABELS} for t in LABELS}
    for t, p in zip(y_true, y_pred):
        matrix[t][p] += 1
    return matrix


def precision_recall_f1(matrix: dict[str, dict[str, int]]) -> dict[str, dict[str, float]]:
    metrics = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in LABELS if other != label)
        fn = sum(matrix[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        metrics[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true",
                        help="Also run LLM ensemble voting (slower, uses your OpenRouter quota). "
                             "Default is LF-only: fast, free, fully deterministic.")
    args = parser.parse_args()

    y_true: list[str] = []
    y_pred: list[str] = []
    rows = []

    for doc_name, expected in EXPECTED_LABELS.items():
        control = CONTROL_FOR_DOC[doc_name]
        text = TEST_DOCS[doc_name]

        result = score_documents([text], use_llm=args.llm)
        score = result[control]["score"]
        predicted = score_to_label_scorer(score)

        y_true.append(expected)
        y_pred.append(predicted)
        rows.append((doc_name, control, score, expected, predicted))

    print(f"\n{'Doc':<22} {'Ctrl':<5} {'Score':>6}  {'Expected':<14} {'Predicted':<14}")
    print(f"{'-'*22} {'-'*5} {'-'*6}  {'-'*14} {'-'*14}")
    for doc_name, control, score, expected, predicted in rows:
        marker = "" if expected == predicted else "  <-- MISS"
        print(f"{doc_name:<22} {control:<5} {score:>6.1f}  {expected:<14} {predicted:<14}{marker}")

    matrix = confusion_matrix(y_true, y_pred)
    metrics = precision_recall_f1(matrix)

    print(f"\n{'Label':<14} {'Precision':>9} {'Recall':>9} {'F1':>9} {'Support':>9}")
    print(f"{'-'*14} {'-'*9} {'-'*9} {'-'*9} {'-'*9}")
    for label in LABELS:
        m = metrics[label]
        print(f"{label:<14} {m['precision']:>9.2f} {m['recall']:>9.2f} {m['f1']:>9.2f} {m['support']:>9}")

    macro_f1 = sum(m["f1"] for m in metrics.values()) / len(LABELS)
    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    print(f"\nAccuracy: {accuracy:.2%}   Macro F1: {macro_f1:.2f}")
    print(f"Mode: {'LLM ensemble + LF fallback' if args.llm else 'LF-only (offline)'}")

    out = {
        "mode": "llm" if args.llm else "lf_only",
        "n": len(y_true),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_label": {k: {kk: round(vv, 4) if isinstance(vv, float) else vv
                          for kk, vv in v.items()} for k, v in metrics.items()},
        "confusion_matrix": matrix,
    }
    out_path = _ROOT / "data" / "processed" / "eval_metrics.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nMetrics saved -> {out_path}")


if __name__ == "__main__":
    main()
