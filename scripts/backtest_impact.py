import sys, json, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # repo-root shim

import pandas as pd

EVENTS = [
    {"id": "svb_collapse", "date": "2023-03-10", "type": "Credit Event", "tickers": ["KRE", "SPY"],
     "headlines": [
         "Silicon Valley Bank collapses in largest US bank failure since 2008, regulators seize deposits",
         "SVB shutdown sparks contagion fears, regional bank stocks plunge as clients rush to withdraw",
         "Regulators announce emergency measures to backstop deposits after SVB failure",
         "Startups scramble as venture-focused lender Silicon Valley Bank fails"]},
    {"id": "hot_cpi", "date": "2022-09-13", "type": "Macroeconomic", "tickers": ["SPY", "QQQ"],
     "headlines": [
         "August CPI comes in hotter than expected at 8.3 percent, core inflation accelerates",
         "Stock futures tumble after hot inflation print keeps Fed on aggressive hiking path",
         "Hot CPI report sinks hopes for a dovish Fed pivot, rate hike expectations surge"]},
    {"id": "ukraine_invasion", "date": "2022-02-24", "type": "Geopolitical", "tickers": ["SPY", "XOM", "GLD"],
     "headlines": [
         "Russia launches full-scale invasion of Ukraine, markets around the world plunge",
         "Oil surges above 100 dollars as sanctions talk intensifies after Ukraine invasion",
         "Gold jumps as investors flee to safety amid largest European conflict in decades"]},
    {"id": "nvda_ai_beat", "date": "2023-05-24", "type": "Earnings/Results", "tickers": ["NVDA"],
     "headlines": [
         "Nvidia guides revenue far above consensus on AI chip demand, shares explode after hours",
         "Nvidia's blowout AI forecast adds hundreds of billions in market value overnight"]},
    {"id": "election_rally", "date": "2024-11-05", "type": "Geopolitical", "tickers": ["SPY", "IWM"],
     "headlines": [
         "Markets rally as election results point to decisive outcome, small caps surge",
         "Futures spike overnight as election outcome clears policy uncertainty, banks lead gains"]},
]

def realized_move(ticker: str, date: str):
    import yfinance as yf
    d = pd.Timestamp(date)
    h = yf.download(ticker, start=d - pd.Timedelta(days=7), end=d + pd.Timedelta(days=5),
                    progress=False, auto_adjust=True)["Close"].squeeze()
    prev = h[h.index < d].iloc[-1]
    nxt = h[h.index > d].iloc[0]          # first trading close AFTER the event
    return round(float(nxt / prev - 1) * 100, 2)

def main():
    from src.engine.analyze import analyze_text
    out = []
    for ev in EVENTS:
        scores = [analyze_text(h, source="news") for h in ev["headlines"]]
        avg_impact = round(sum(s.impact_score for s in scores) / len(scores), 1)
        types = [s.event_type for s in scores]
        moves = {}
        for t in ev["tickers"]:
            try:
                moves[t] = realized_move(t, ev["date"])
                time.sleep(1)
            except Exception as e:
                moves[t] = None
                print(f"  yfinance failed for {t}: {str(e)[:80]}")
        out.append({"id": ev["id"], "event_date": ev["date"],
                    "expected_type": ev["type"],
                    "predicted_types": sorted(set(types)),
                    "predicted_impact_avg": avg_impact,
                    "realized_move_pct": moves})
        print(f"{ev['id']:<18} impact={avg_impact:<5} predicted={sorted(set(types))} realized={moves}")

    pathlib.Path("results").mkdir(exist_ok=True)
    (pathlib.Path("results") / "backtest.json").write_text(
        json.dumps({"events": out,
                    "note": "impact score measures SYSTEMIC severity, not single-stock magnitude"},
                   indent=2))
    print("saved -> results/backtest.json")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = range(len(out))
    impacts = [e["predicted_impact_avg"] for e in out]
    moves = [max((abs(v) for v in e["realized_move_pct"].values() if v is not None), default=0)
             for e in out]
    fig, ax1 = plt.subplots(figsize=(9, 4))
    ax1.bar([i - 0.2 for i in x], impacts, width=0.4, label="engine impact (1-10)")
    ax1.set_ylabel("predicted impact (1-10)"); ax1.set_ylim(0, 10)
    ax2 = ax1.twinx()
    ax2.bar([i + 0.2 for i in x], moves, width=0.4, color="orange", label="realized |move| (%)")
    ax2.set_ylabel("realized |move| (%)")
    ax1.set_xticks(list(x), [e["id"] for e in out], rotation=20)
    fig.suptitle("Predicted impact vs realized market reaction (n=5 events)")
    fig.tight_layout(); fig.savefig("results/backtest.png", dpi=150)
    print("chart saved -> results/backtest.png")

if __name__ == "__main__":
    main()