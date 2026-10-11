from collections import defaultdict

TRIGGER_THRESHOLD = 7.0
STRESSABLE = {"Geopolitical", "Macroeconomic", "Credit Event"}

SHOCK_MATRIX = {
    "Geopolitical":  {"ig_bps": 100, "hy_bps": 250, "rate_bps": 0,   "fx": 0.03,  "equity": -0.10},
    "Credit Event":  {"ig_bps": 50,  "hy_bps": 200, "rate_bps": 0,   "fx": 0.01,  "equity": -0.06},
    "Macroeconomic": {"ig_bps": 25,  "hy_bps": 75,  "rate_bps": 150, "fx": 0.02,  "equity": -0.05},
}

def tier_for(impact: float) -> tuple[str, float]:
    if impact < 8.0:
        return "Moderate", 0.6
    if impact < 9.0:
        return "Severe", 1.0
    return "Extreme", 1.3

RATING_HAIRCUT = {"BBB": 0.03, "BB": 0.08, "B": 0.12}   # on Geo/Credit only
SENTIMENT_AMPLIFIER = 0.15
CONCENTRATION_THRESHOLD = 0.25
CONCENTRATION_PENALTY = 1.2

def _position_pnl(pos: dict, sh: dict, event_type: str) -> float:
    """P&L ($M) for one position under the (already scaled) shock dict."""
    ac = pos["asset_class"]
    rate = sh["rate_bps"] / 10000

    if ac in ("bond_ig", "bond_hy"):
        dy = (sh["ig_bps"] if ac == "bond_ig" else sh["hy_bps"]) / 10000 + rate
        pnl = -pos["duration"] * dy * pos["mtm_value"]          # dP = -D * dy * P
        hc = RATING_HAIRCUT.get(pos["rating"], 0.0) if event_type in ("Geopolitical", "Credit Event") else 0.0
        return pnl - hc * pos["mtm_value"]

    if ac == "loan_fixed":
        dy = 0.5 * sh["ig_bps"] / 10000 + rate                  # loans reprice slower
        pnl = -pos["duration"] * dy * pos["mtm_value"]
        hc = RATING_HAIRCUT.get(pos["rating"], 0.0) if event_type in ("Geopolitical", "Credit Event") else 0.0
        return pnl - hc * pos["mtm_value"]

    if ac == "loan_floating":
        gain = pos["notional"] * rate * 0.5                     # income rises with rates
        pain = pos["notional"] * 0.3 * sh["hy_bps"] / 10000     # credit deterioration
        return gain - pain

    if ac == "irs":
        sign = 1.0 if pos["direction"] == "pay_fixed" else -1.0
        return sign * pos["duration"] * rate * pos["notional"]

    if ac == "fx_forward":
        sign = 1.0 if pos["direction"] == "long_usd" else -1.0
        return sign * pos["notional"] * sh["fx"]

    if ac == "equity":
        return pos["mtm_value"] * sh["equity"]

    return 0.0

def run_stress(portfolio: list[dict], event_type: str, impact_score: float,
               sentiment: float = 0.0) -> dict:
    """(portfolio, event) -> full stress result. Always returns 'triggered' key."""
    if event_type not in STRESSABLE:
        return {"triggered": False,
                "reason": f"{event_type} is firm-specific, not systemic — no portfolio stress"}
    if impact_score < TRIGGER_THRESHOLD:
        return {"triggered": False,
                "reason": f"impact {impact_score} < threshold {TRIGGER_THRESHOLD}"}

    tier, tier_mult = tier_for(impact_score)
    sent_mult = 1 + SENTIMENT_AMPLIFIER * max(0.0, -sentiment)
    combined = round(tier_mult * sent_mult, 3)

    base = SHOCK_MATRIX[event_type]
    sh = {k: round(v * combined, 4) for k, v in base.items()}

    total_value = sum(p["mtm_value"] for p in portfolio)
    sector_value = defaultdict(float)
    for p in portfolio:
        sector_value[p["sector"]] += p["mtm_value"]
    heavy = {s for s, v in sector_value.items() if v / total_value > CONCENTRATION_THRESHOLD}

    positions_pnl, by_class, by_sector = [], defaultdict(float), defaultdict(float)
    for p in portfolio:
        pnl = _position_pnl(p, sh, event_type)
        if p["sector"] in heavy and pnl < 0:
            pnl *= CONCENTRATION_PENALTY
        positions_pnl.append({"position_id": p["position_id"], "counterparty": p["counterparty"],
                              "asset_class": p["asset_class"], "sector": p["sector"],
                              "rating": p["rating"], "pnl": round(pnl, 2)})
        by_class[p["asset_class"]] += pnl
        by_sector[p["sector"]] += pnl

    total_pnl = sum(r["pnl"] for r in positions_pnl)
    return {
        "triggered": True, "tier": tier, "shock_multiplier": combined,
        "effective_shocks": sh,
        "portfolio_value_before": round(total_value, 1),
        "portfolio_value_after": round(total_value + total_pnl, 1),
        "total_pnl": round(total_pnl, 1),
        "pct_loss": round(100 * total_pnl / total_value, 2),
        "by_asset_class": {k: round(v, 1) for k, v in sorted(by_class.items())},
        "by_sector": {k: round(v, 1) for k, v in sorted(by_sector.items())},
        "concentration_flags": [f"{s} >25% of book -> losses x{CONCENTRATION_PENALTY}"
                                for s in sorted(heavy)],
        "top_losers": sorted(positions_pnl, key=lambda r: r["pnl"])[:5],
        "positions_pnl": positions_pnl,
    }