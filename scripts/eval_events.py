import sys, json, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # repo-root shim

from collections import Counter, defaultdict

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules-only", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in
            pathlib.Path("data/golden_events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"golden set: {len(rows)} items "
          f"({sum(1 for r in rows if r.get('origin') == 'blind')} blind / "
          f"{sum(1 for r in rows if r.get('origin') == 'curated')} curated)\n")

    from src.engine.events import classify
    preds, gts, per_origin = [], [], defaultdict(list)
    for r in rows:
        pred, _ = classify(r["text"], allow_zero_shot=not args.rules_only)
        preds.append(pred); gts.append(r["label"])
        per_origin[r.get("origin", "curated")].append(pred == r["label"])

    acc = sum(p == g for p, g in zip(preds, gts)) / len(gts)
    print(f"OVERALL accuracy: {acc:.3f}")
    for origin, hits in per_origin.items():
        print(f"  {origin:>8} subset accuracy: {sum(hits) / len(hits):.3f} (n={len(hits)})")

    print("\nper-class F1:")
    for c in sorted(set(gts)):
        tp = sum(p == c and g == c for p, g in zip(preds, gts))
        fp = sum(p == c and g != c for p, g in zip(preds, gts))
        fn = sum(p != c and g == c for p, g in zip(preds, gts))
        pr = tp / (tp + fp) if tp + fp else 0
        rc = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0
        print(f"  {c:<18} precision={pr:.2f} recall={rc:.2f} f1={f1:.2f}")

    stress = ["Geopolitical", "Macroeconomic", "Credit Event"]
    g_s = [(g, p) for g, p in zip(gts, preds) if g in stress]
    recall = sum(p == g for g, p in g_s) / len(g_s)
    print(f"\nSTRESSABLE recall (Module B trigger coverage): {recall:.3f}")

    pathlib.Path("results").mkdir(exist_ok=True)
    pathlib.Path("results/metrics_events.json").write_text(json.dumps({
        "n": len(gts), "accuracy": round(acc, 3),
        "stressable_recall": round(recall, 3),
        "rules_only": args.rules_only,
        "confusion": {g: dict(Counter(p for gg, p in zip(gts, preds) if gg == g))
                      for g in sorted(set(gts))}}, indent=2))
    print("saved -> results/metrics_events.json")

if __name__ == "__main__":
    main()