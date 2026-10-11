import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # repo-root shim

from collections import Counter

R = pathlib.Path("results")
out = {
    "sentiment": json.loads((R / "metrics_sentiment.json").read_text()) if (R / "metrics_sentiment.json").exists() else None,
    "events": json.loads((R / "metrics_events.json").read_text()) if (R / "metrics_events.json").exists() else None,
    "impact_backtest": json.loads((R / "backtest.json").read_text()) if (R / "backtest.json").exists() else None,
}

# trigger audit: what does impact>=7 fire on, across all live signals?
from src.common.store import SIGNALS_PATH, read_all
rows = list(read_all(SIGNALS_PATH))
hi = [r for r in rows if r["impact_score"] >= 7]
out["trigger_audit"] = {
    "total_signals": len(rows),
    "trigger_rate_pct": round(100 * len(hi) / len(rows), 1) if rows else 0,
    "triggered_by_event": dict(Counter(r["event_type"] for r in hi)),
    "tier_distribution": {
        "moderate_7_8": sum(1 for r in hi if 7 <= r["impact_score"] < 8),
        "severe_8_9": sum(1 for r in hi if 8 <= r["impact_score"] < 9),
        "extreme_9_10": sum(1 for r in hi if r["impact_score"] >= 9),
    },
}
(R / "metrics.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out["trigger_audit"], indent=2))
print("consolidated -> results/metrics.json")