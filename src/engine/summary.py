"""Signal health check: what has the engine produced so far?"""
from collections import Counter
from src.common.store import SIGNALS_PATH, read_all

def main():
    rows = list(read_all(SIGNALS_PATH))
    print(f"total signals: {len(rows)}  (errors: {sum(1 for r in rows if r.get('error'))})")
    print("by event_type:", dict(Counter(r["event_type"] for r in rows)))
    ents = Counter(e["ticker"] for r in rows for e in r["entities"])
    print("top entities: ", dict(ents.most_common(8)))
    hi = [r for r in rows if r["impact_score"] >= 7]
    print(f"high-impact (>=7): {len(hi)}")
    for r in hi[:3]:
        print(f"  [{r['impact_score']}] {r['event_type']} :: {r['text'][:70]!r}")

if __name__ == "__main__":
    main()