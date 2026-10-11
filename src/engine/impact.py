import re
from functools import lru_cache

EVENT_BASE = {
    "Credit Event": 8.0, "Geopolitical": 7.0, "Macroeconomic": 6.0,
    "Merger/Acquisition": 5.0, "Earnings/Results": 4.0,
    "Product Launch": 3.0, "Other": 3.0,
}

SEVERITY_BOOSTS = {          # regex fragment -> added points
    r"bankrupt\w*": 3.0, r"default\w*": 3.0, r"contagion": 2.5,
    r"crash\w*": 2.5, r"crisis": 2.0, r"sanction\w*": 2.0, r"recession": 2.0,
    r"\bwar\b": 2.0, r"emergency": 2.0, r"freeze\w*": 1.5, r"plunge\w*": 1.5,
    r"layoff\w*": 1.5, r"surge\w*": 1.0, r"record": 1.0,
}

SOURCE_WEIGHT = {"news": 1.10, "social": 0.90}   # news is more credible

@lru_cache(maxsize=1)
def _boost_patterns() -> list[tuple[re.Pattern, float]]:
    return [(re.compile(p, re.IGNORECASE), w) for p, w in SEVERITY_BOOSTS.items()]

def impact_score(event_type: str, sentiment: float,
                 text: str, source: str) -> float:
    base = EVENT_BASE.get(event_type, 3.0)
    intensity = 0.4 + 0.6 * abs(sentiment)     # neutral wording damps, extreme amplifies
    boosts = sum(w for pat, w in _boost_patterns() if pat.search(text))
    score = (base * intensity + boosts) * SOURCE_WEIGHT.get(source, 1.0)
    return round(min(10.0, max(1.0, score)), 1)