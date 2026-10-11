from functools import lru_cache

@lru_cache(maxsize=1)
def _get_pipe():
    from transformers import pipeline          
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
    p = _probs(_get_pipe()(text[:512]))        
    score = round(p.get("positive", 0.0) - p.get("negative", 0.0), 3)
    label = ("positive" if score >= 0.5
             else "negative" if score <= -0.5 else "neutral")
    return {"score": score, "label": label, "probs": p}