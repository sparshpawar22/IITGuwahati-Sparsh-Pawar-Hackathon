import json, re
from functools import lru_cache
from pathlib import Path

UNIVERSE_PATH = Path("data/universe.json")
TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b")

@lru_cache(maxsize=1)
def _universe() -> dict:
    """ticker -> {name, sector, aliases, patterns}. Patterns compiled once."""
    raw = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    for t, meta in raw.items():
        names = [meta["name"], *meta.get("aliases", [])]
        meta["patterns"] = [re.compile(r"\b" + re.escape(n.lower()) + r"\b")
                            for n in names]
    return raw

def link_entities(text: str) -> list[dict]:
    u = _universe()
    found: dict[str, dict] = {}

    for m in TICKER_RE.finditer(text):                     # 1. cashtags
        t = m.group(1)
        if t in u:
            found.setdefault(t, {"ticker": t, "name": u[t]["name"],
                                 "sector": u[t]["sector"], "how": "cashtag"})

    low = text.lower()                                     # 2+3. names/aliases
    for t, meta in u.items():
        if t in found:
            continue
        for pat in meta["patterns"]:
            if pat.search(low):
                found[t] = {"ticker": t, "name": meta["name"],
                            "sector": meta["sector"], "how": "name"}
                break
    return list(found.values())