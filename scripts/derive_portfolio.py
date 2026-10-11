import argparse, json, pathlib, random, sys
from collections import defaultdict
import pandas as pd

TOTAL_BOOK = 1500.0        
FIN_ANCHOR = 0.28          
N_POSITIONS = 40
SEED = 42

CATEGORY_SECTOR = {
    "gas_transport": "Energy", "travel": "Industrials", "home": "Industrials",
    "shopping_net": "Technology", "misc_net": "Technology",
    "electronics": "Technology", "computers": "Technology",
    "shopping_pos": "Consumer", "grocery_pos": "Consumer", "grocery_net": "Consumer",
    "food_dining": "Consumer", "personal_care": "Consumer", "kids_pets": "Consumer",
    "entertainment": "Consumer", "misc_pos": "Consumer",
    "apparel": "Consumer", "kids": "Consumer", "sport": "Consumer", "auto": "Consumer",
    "health_fitness": "Healthcare",
    "payment": "Consumer", "transfer": "Financials", "cash_out": "Financials",
    "cash_in": "Financials", "debit": "Consumer",
}
ASSET_MIX = [("loan_fixed", .30), ("loan_floating", .12), ("bond_ig", .18),
             ("bond_hy", .10), ("irs", .15), ("fx_forward", .08), ("equity", .07)]
RATING_SPREAD = {"AA": .045, "A": .055, "BBB": .070, "BB": .095, "B": .115}
RATINGS = {"bond_ig": ["AA", "A", "BBB"], "bond_hy": ["BB", "B"],
           "loan_fixed": ["A", "BBB", "BB"], "loan_floating": ["A", "BBB", "BB"]}

def pick_asset_class(frac: float) -> str:
    cum = 0.0
    for ac, share in ASSET_MIX:
        cum += share
        if frac < cum:
            return ac
    return ASSET_MIX[-1][0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/raw/transactions/fraudTest.csv")
    ap.add_argument("--category-col", default=None)
    ap.add_argument("--amount-col", default=None)
    args = ap.parse_args()

    src = pathlib.Path(args.file)
    if not src.exists():
        sys.exit(f"not found: {src}")
    df = None
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(src, encoding=enc, usecols=None)
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        sys.exit("could not decode with utf-8 or latin-1")
    print(f"loaded {len(df):,} transactions from {src}")
    if len(df) < 10_000:
        sys.exit("ABORT: suspiciously small — verify the download")

    ccol = args.category_col or next(
        (c for c in ("category", "category_code", "type") if c in df.columns), None)
    acol = args.amount_col or next(
        (c for c in ("amt", "amount", "price") if c in df.columns), None)
    if not ccol or not acol:
        sys.exit(f"columns not found. Available: {df.columns.tolist()}")
    print(f"using: category={ccol!r}, amount={acol!r}")

    df["_amt"] = pd.to_numeric(df[acol], errors="coerce")
    df = df.dropna(subset=["_amt"])
    unmapped_vols = (df[~df[ccol].isin(CATEGORY_SECTOR)]
                     .groupby(ccol)["_amt"].sum())
    total_vol = float(df["_amt"].sum())
    unmapped_share = float(unmapped_vols.sum() / total_vol) if total_vol else 1.0
    if unmapped_share > 0.30:
        sys.exit(f"ABORT: {unmapped_share:.0%} volume unmapped -> "
                 f"{unmapped_vols.sort_values(ascending=False).head(10).to_dict()}\n"
                 f"Extend CATEGORY_SECTOR or pick another file.")
    if unmapped_share > 0:
        print(f"WARNING: {unmapped_share:.1%} unmapped volume -> bucketed to shopping_pos: "
              f"{unmapped_vols.sort_values(ascending=False).head(5).to_dict()}")

    g = df.groupby(ccol).agg(volume=("_amt", "sum"), txns=("_amt", "size"))
    g["sector"] = g.index.map(lambda c: CATEGORY_SECTOR.get(c, "Consumer"))
    sec_vol = g.groupby("sector")["volume"].sum()
    shares = sec_vol / sec_vol.sum()
    weights = {s: (FIN_ANCHOR if s == "Financials" else v * (1 - FIN_ANCHOR))
               for s, v in shares.items()}
    if "Financials" not in weights:           
        weights["Financials"] = FIN_ANCHOR
        others = sum(v for s, v in weights.items() if s != "Financials")
        weights = {s: (v if s == "Financials" else v * ((1 - FIN_ANCHOR) / others))
                   for s, v in weights.items()}

    u = json.loads(pathlib.Path("data/universe.json").read_text(encoding="utf-8"))
    by_sector = defaultdict(list)
    for t, meta in u.items():
        by_sector[meta["sector"]].append(t)

    rng = random.Random(SEED)
    counts = {s: max(2, round(w * N_POSITIONS)) for s, w in weights.items()}

    P, n = [], 0
    for sector in sorted(counts):
        k = counts[sector]
        tickers = by_sector.get(sector, ["JPM"])
        for i in range(k):
            ac, t = pick_asset_class(i / k), tickers[i % len(tickers)]
            value = weights[sector] * TOTAL_BOOK / k * rng.uniform(0.7, 1.3)   # $M
            pos = {"counterparty": t, "sector": sector, "currency": "USD"}
            if ac in ("irs", "fx_forward"):
                pos.update(asset_class=ac, rating=None,
                           notional=round(value * 20, 1),
                           mtm_value=round(value * 20 * (0.015 if ac == "irs" else 0.01), 2),
                           direction=rng.choices(
                               ["pay_fixed", "receive_fixed"] if ac == "irs"
                               else ["long_usd", "short_usd"], weights=[0.7, 0.3])[0],
                           duration=round(rng.uniform(3.0, 5.0), 1))
            elif ac == "equity":
                pos.update(asset_class=ac, rating=None,
                           notional=round(value, 1), mtm_value=round(value, 1))
            else:
                rating = rng.choice(RATINGS[ac])
                pos.update(asset_class=ac, rating=rating,
                           notional=round(value, 1), mtm_value=round(value, 1),
                           duration=round(rng.uniform(2.0, 6.0), 1),
                           coupon=round(100 * (0.042 + RATING_SPREAD[rating]
                                               + rng.uniform(0, 0.01)), 1))
                if ac == "loan_floating":
                    pos["spread_bps"] = int(10000 * RATING_SPREAD[rating] * rng.uniform(0.8, 1.2))
            n += 1
            pos["position_id"] = f"P-{n:03d}"
            P.append(pos)

    for sector, target in weights.items():                    
        rows = [p for p in P if p["sector"] == sector]
        actual = sum(p["mtm_value"] for p in rows)
        f = target * TOTAL_BOOK / actual
        for p in rows:
            p["mtm_value"] = round(p["mtm_value"] * f, 2)
            if p["asset_class"] in ("irs", "fx_forward"):
                p["notional"] = round(p["notional"] * f, 1)

    pathlib.Path("data").mkdir(exist_ok=True)
    pathlib.Path("data/portfolio.json").write_text(json.dumps(P, indent=2), encoding="utf-8")
    pathlib.Path("data/portfolio_derivation.json").write_text(json.dumps({
        "source_dataset": "kartik2112/credit-card-fraud-detection (fraudTest.csv)",
        "license": "CC0 Public Domain",
        "simulation": "Sparkov Data Generation (Brandon Harris)",
        "transactions_used": int(len(df)),
        "category_col": ccol, "amount_col": acol,
        "unmapped_volume_share": round(unmapped_share, 4),
        "sector_weights_from_data": {s: round(w, 4) for s, w in weights.items()},
        "financials_anchor_assumption": FIN_ANCHOR,
        "total_book_musd": TOTAL_BOOK, "positions": len(P), "seed": SEED,
        "category_volumes": {str(k): {"volume": round(float(r.volume), 0),
                                      "txns": int(r.txns)}
                             for k, r in g.iterrows()},
        "declared_assumptions": ["asset mix ASSET_MIX", "ratings/durations/coupons seeded",
                                 "derivative notional = 20x value",
                                 "counterparties from universe.json"]}, indent=2))

    from collections import Counter
    print(f"\n{len(P)} positions -> data/portfolio.json (+ provenance file)")
    print("asset mix:", dict(Counter(p["asset_class"] for p in P)))
    tot = sum(p["mtm_value"] for p in P)
    sec = Counter()
    for p in P:
        sec[p["sector"]] += p["mtm_value"]
    print("value weights (target vs actual):")
    for s, w in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"  {s:<12} target {w:.0%}  actual {sec[s] / tot:.0%}")

if __name__ == "__main__":
    main()