"""
embeddings.py — lightweight local text embeddings for hybrid BM25+embedding
retrieval. Uses fastembed (ONNX runtime, no PyTorch) so it stays cheap to
install rather than pulling in a multi-GB torch/sentence-transformers stack.

If fastembed isn't installed or the model fails to load, embed() returns
None and callers fall back to BM25-only ranking — same graceful-degradation
pattern used everywhere else in this pipeline (LLM -> LF, OpenRouter -> Ollama).
"""

import numpy as np

_MODEL_NAME = "BAAI/bge-small-en-v1.5"

_model = None
_unavailable = False


def _get_model():
    global _model, _unavailable
    if _unavailable:
        return None
    if _model is None:
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name=_MODEL_NAME)
        except Exception:
            _unavailable = True
            return None
    return _model


def embed(texts: list[str]) -> list[np.ndarray] | None:
    """Return one embedding vector per input text, or None if unavailable."""
    model = _get_model()
    if model is None:
        return None
    try:
        return list(model.embed(texts))
    except Exception:
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0
