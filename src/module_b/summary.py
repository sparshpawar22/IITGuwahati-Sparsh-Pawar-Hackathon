import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from collections import Counter
from src.common.store import read_all

RESULTS_PATH = pathlib.Path("data") / "stress_results.jsonl"

def main():
    rows = list(read_all(RESULTS_PATH))
    fired = [r for r in rows if r.get("triggered")]
    print(f"stress runs recorded: {len(rows)}  (fired: {len(fired)})")
    if fired:
        print("by tier:", dict(Counter(r["tier"] for r in fired)))
        print(f"avg loss: {sum(r['pct_loss'] for r in fired) / len(fired):+.2f}%")
        worst = min(fired, key=lambda r: r["pct_loss"])
        print(f"worst: {worst['run_id']} {worst['pct_loss']:+.2f}% ({worst['trigger']['event_type']})")
        print(f"last: {fired[-1]['run_id']} on '{fired[-1]['trigger']['text'][:80]}'")

if __name__ == "__main__":
    main()