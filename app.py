"""
app.py — Flask web server for the NCIIPC compliance pipeline.

Usage:
    python app.py
    # Open http://localhost:5000 in a browser

Requires:  OPENROUTER_API_KEY set in a .env file
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

# Add scripts/ and C++ extension to import path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "nciipc-prep" / "build"))

app = Flask(__name__, static_folder="web")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB

_rate_limits: dict = {}
_RATE_WINDOW = 60   # seconds
_RATE_MAX = 10      # max requests per IP per window


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


ALLOWED = {".pdf", ".docx", ".txt", ".text"}

@app.route("/score", methods=["POST"])
def score():
    from pipeline import extract_text
    from scorer import score_documents
    from explain import explain_control
    from audit_integrity import sign as sign_result

    # Rate limit check
    ip = request.remote_addr or "unknown"
    now = time.time()
    recent = [t for t in _rate_limits.get(ip, []) if now - t < _RATE_WINDOW]
    if not recent:
        _rate_limits.pop(ip, None)  # evict idle IPs to prevent memory leak
    else:
        _rate_limits[ip] = recent
    if len(_rate_limits.get(ip, [])) >= _RATE_MAX:
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429
    _rate_limits.setdefault(ip, []).append(now)

    tmp_paths = []
    try:
        sources = []
        texts   = []

        # --- file uploads (pdf / docx / txt) ---
        for f in request.files.getlist("file"):
            if not f.filename:
                continue
            suffix = Path(f.filename).suffix.lower()
            if suffix not in ALLOWED:
                return jsonify({"error": f"Unsupported file type: {suffix}. Use .pdf, .docx, or .txt"}), 400
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp_paths.append(tmp.name)
                f.save(tmp.name)
                texts.append(extract_text(tmp.name))
                sources.append(f.filename)

        # --- URL (single) — accepts JSON body {"url": "..."} or form field url=...  ---
        if not texts:
            url = None
            if request.is_json:
                url = (request.json or {}).get("url")
            if not url:
                url = request.form.get("url")
            if url:
                texts.append(extract_text(url))
                sources.append(url)

        if not texts:
            return jsonify({"error": "Send one or more files (.pdf/.docx/.txt) or a JSON body with a 'url' key"}), 400

        # Score all docs together — single BM25 index across all files
        result = score_documents(texts)
        result["sources"] = sources

        # LLM findings + remediation for the combined result only
        for ctrl in ("PC1", "PC2", "PC3"):
            d = result[ctrl]
            try:
                explanation = explain_control(ctrl, d["score"], d["maturity"], d["fields"])
                result[ctrl]["finding"] = explanation["finding"]
                result[ctrl]["remediation"] = explanation["remediation"]
            except Exception:
                result[ctrl]["finding"] = ""
                result[ctrl]["remediation"] = []

        # Per-document breakdown (when multiple files uploaded)
        if len(texts) > 1:
            per_doc = []
            for i, text in enumerate(texts):
                doc_result = score_documents([text], use_llm=False)
                per_doc.append({
                    "source": sources[i],
                    "company_score": doc_result["company_score"],
                    "PC1": {k: doc_result["PC1"][k] for k in ("score", "maturity", "has_evidence")},
                    "PC2": {k: doc_result["PC2"][k] for k in ("score", "maturity", "has_evidence")},
                    "PC3": {k: doc_result["PC3"][k] for k in ("score", "maturity", "has_evidence")},
                })
            result["per_doc"] = per_doc

        # Sign the result so it can be checked for tampering later — see
        # audit_integrity.py / scripts/verify_report.py
        result["integrity"] = sign_result(result)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        for p in tmp_paths:
            try:
                os.unlink(p)
            except OSError:
                pass


if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=False)
