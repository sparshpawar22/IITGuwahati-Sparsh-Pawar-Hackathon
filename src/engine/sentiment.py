"""Sentiment scoring via FinBERT. Score = P(positive) - P(negative) in [-1, +1].
Model loads ONCE (module-level singleton) — never per call."""
from functools import lru_cache

@lru_cache(maxsize=1)
def _get_pipe():
    from transformers import pipeline          # lazy import: fast module import for tests
    return pipeline("text-classification",
                    model="ProsusAI/finbert", top_k=None)

def _probs(raw) -> dict[str, float]:
    """Normalize pipeline output across transformers versions:
    accepts [ {...}, ... ] or [ [ {...}, ... ] ]."""
    if raw and isinstance(raw[0], list):
        raw = raw[0]
    return {d["label"].lower(): float(d["score"]) for d in raw}

def sentiment(text: str) -> dict:
    """Returns {'score': float in [-1,+1], 'label': str, 'probs': dict}."""
    p = _probs(_get_pipe()(text[:512]))        # 512 = BERT's max token window
    score = round(p.get("positive", 0.0) - p.get("negative", 0.0), 3)
    label = max(p, key=p.get)
    return {"score": score, "label": label, "probs": p}