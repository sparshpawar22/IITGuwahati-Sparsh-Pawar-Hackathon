import sys, json, random, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # repo-root shim

CODES = {"1": "Geopolitical", "2": "Macroeconomic", "3": "Credit Event",
         "4": "Merger/Acquisition", "5": "Product Launch",
         "6": "Earnings/Results", "7": "Other"}
GOLDEN = pathlib.Path("data/golden_events.jsonl")
SIGNALS = pathlib.Path("data/signals.jsonl")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()

    existing = {json.loads(l)["text"] for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()}
    pool = [r["text"] for r in map(json.loads, SIGNALS.read_text(encoding="utf-8").splitlines())
            if r["text"] not in existing]
    random.seed(7)
    random.shuffle(pool)
    print(f"{len(existing)} already labeled, {len(pool)} candidates available\n")

    with GOLDEN.open("a", encoding="utf-8") as f:
        for i, text in enumerate(pool[: args.n]):
            print(f"[{i + 1}/{args.n}] {text[:160]}")
            c = input("  code: ").strip().lower()
            if c == "q":
                break
            if c == "s":
                continue
            if c in CODES:
                f.write(json.dumps({"text": text, "label": CODES[c],
                                    "origin": "blind"}) + "\n")
                f.flush()
    print("done -> data/golden_events.jsonl")

if __name__ == "__main__":
    main()