import re
from functools import lru_cache

EVENT_TYPES = ["Geopolitical", "Macroeconomic", "Credit Event",
               "Merger/Acquisition", "Product Launch", "Earnings/Results", "Other"]

STRESSABLE = {"Geopolitical", "Macroeconomic", "Credit Event"}  

RULES: dict[str, list[str]] = {
    "Credit Event": [
        r"default\w*", r"bankrupt\w*", r"downgrade\w*", r"insolvenc\w*",
        r"credit rating", r"debt crisis", r"fraud\w*", r"redemption\w*",
        r"restructur\w*", r"credit losses", r"loan losses", r"impairment",
        r"write-?down\w*", r"covenant"],
    "Geopolitical": [
        r"war\b", r"conflict\w*", r"sanction\w*", r"tariff\w*", r"invasion",
        r"missile\w*", r"military", r"geopolitic\w*", r"escalat\w*",
        r"blockade", r"red sea", r"airspace", r"nuclear", r"export (?:ban|curb\w*|control\w*)"],
    "Macroeconomic": [
        r"inflation", r"\bcpi\b", r"interest rate\w*", r"rate hike", r"rate cut",
        r"central bank\w*", r"\bfed\b", r"federal reserve", r"\becb\b",
        r"bank of japan", r"\bgdp\b", r"recession", r"unemployment",
        r"jobs report", r"payroll\w*", r"\bpmi\b", r"monetary policy",
        r"hawkish", r"dovish", r"stimulus", r"deflation"],
    "Merger/Acquisition": [
        r"acquisition\w*", r"acquir\w*", r"merger", r"merges?",
        r"takeover", r"buyout", r"stake in"],
    "Product Launch": [
        r"launch\w*", r"unveil\w*", r"rolls out", r"debut\w*", r"introduces"],
    "Earnings/Results": [
        r"earnings", r"quarterly results", r"beats? estimates", r"misses? estimates",
        r"guidance", r"\brevenue\b", r"\beps\b", r"dividend", r"\bq[1-4]\b",
        r"price target", r"upgrade\w*"],
}

@lru_cache(maxsize=1)
def _rule_patterns() -> dict[str, re.Pattern]:
    return {cat: re.compile(r"\b(?:" + "|".join(kws) + r")\b", re.IGNORECASE)
            for cat, kws in RULES.items()}

@lru_cache(maxsize=1)
def _zs_pipe():
    """Zero-shot fallback. Lazy + optional: if the model can't download
    (campus proxy), we degrade to rules-only instead of crashing."""
    try:
        from transformers import pipeline
        return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    except Exception as e:
        print(f"[events] zero-shot unavailable ({str(e)[:80]}) — rules-only mode")
        return None

def classify(text: str, allow_zero_shot: bool = True) -> tuple[str, float]:
    """Returns (event_type, confidence 0..1)."""
    hits = {cat: len(p.findall(text)) for cat, p in _rule_patterns().items()}
    best = max(hits, key=hits.get)          # max() returns FIRST max => tie-break = dict order
    if hits[best] > 0:
        return best, min(0.95, 0.75 + 0.10 * hits[best])   # more hits -> more confident
    if allow_zero_shot:
        return _zero_shot(text)
    return "Other", 0.30                    # rules-only mode: honest low confidence

def _zero_shot(text: str) -> tuple[str, float]:
    pipe = _zs_pipe()
    if pipe is None:
        return "Other", 0.30
    out = pipe(text[:256], candidate_labels=EVENT_TYPES[:-1], multi_label=False)
    return out["labels"][0], round(float(out["scores"][0]), 2)