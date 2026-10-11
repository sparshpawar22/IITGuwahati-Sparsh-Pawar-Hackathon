import argparse, json, time
from datetime import datetime, timezone
from pathlib import Path
from src.common.store import SIGNALS_PATH, read_all, append
from src.module_b.stress import run_stress

RESULTS_PATH = Path("data") / "stress_results.jsonl"
PORTFOLIO_PATH = Path("data") / "portfolio.json"
STRESSABLE = ("Geopolitical", "Macroeconomic", "Credit Event")

def load_portfolio() -> list[dict]:
    return json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))

def processed_signal_ids() -> set[str]:
    return {r["trigger"]["signal_id"] for r in read_all(RESULTS_PATH) if "trigger" in r}

def evaluate(signal: dict, portfolio: list[dict], run_id: str) -> dict:
    r = run_stress(portfolio, signal["event_type"], signal["impact_score"],
                   signal.get("sentiment_score", 0.0))
    return {"run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trigger": {"signal_id": signal["signal_id"],
                        "event_type": signal["event_type"],
                        "impact_score": signal["impact_score"],
                        "sentiment_score": signal.get("sentiment_score", 0.0),
                        "text": signal["text"][:160]},
            **r}

def candidates() -> list[dict]:
    done = processed_signal_ids()
    return [s for s in read_all(SIGNALS_PATH)
            if s["signal_id"] not in done
            and s["event_type"] in STRESSABLE and s["impact_score"] >= 7.0]

def _print(r: dict) -> None:
    if not r.get("triggered"):
        print(f"[stress-worker] {r['run_id']}: NOT triggered ({r.get('reason')})")
        return
    print(f"[stress-worker] {r['run_id']} FIRED: {r['trigger']['event_type']} "
          f"imp={r['trigger']['impact_score']} tier={r['tier']} x{r['shock_multiplier']}")
    print(f"  portfolio: ${r['portfolio_value_before']:,.1f}M -> "
          f"${r['portfolio_value_after']:,.1f}M   ({r['pct_loss']:+.2f}%)")
    print(f"  by class: {r['by_asset_class']}")
    if r["concentration_flags"]:
        print(f"  flags: {r['concentration_flags']}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--simulate", nargs=3, metavar=("EVENT", "IMPACT", "SENTIMENT"),
                    help="e.g. --simulate Geopolitical 8.5 -0.85")
    args = ap.parse_args()

    portfolio = load_portfolio()
    print(f"[stress-worker] portfolio loaded: {len(portfolio)} positions")

    if args.simulate:
        ev, imp, sent = args.simulate[0], float(args.simulate[1]), float(args.simulate[2])
        sig = {"signal_id": f"sim-{int(time.time())}", "event_type": ev,
               "impact_score": imp, "sentiment_score": sent,
               "text": f"MANUAL SIMULATION: {ev}"}
        result = evaluate(sig, portfolio,
                          f"ST-{len(list(read_all(RESULTS_PATH))) + 1:04d}")
        append(RESULTS_PATH, result)
        _print(result)
        return

    while True:
        for sig in candidates():
            result = evaluate(sig, portfolio,
                              f"ST-{len(list(read_all(RESULTS_PATH))) + 1:04d}")
            append(RESULTS_PATH, result)
            _print(result)
        if args.once:
            break
        time.sleep(args.interval)

if __name__ == "__main__":
    main()