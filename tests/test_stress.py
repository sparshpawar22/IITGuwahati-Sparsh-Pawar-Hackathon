import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  

from src.module_b.stress import run_stress, tier_for

def mk(**kw):
    base = {"position_id": "T-1", "counterparty": "X", "sector": "Tech",
            "asset_class": "bond_ig", "rating": "A", "notional": 40.0,
            "duration": 5.0, "mtm_value": 40.0}
    base.update(kw)
    return base

def test_tier_boundaries():
    assert tier_for(7.0) == ("Moderate", 0.6)
    assert tier_for(8.5) == ("Severe", 1.0)
    assert tier_for(9.5) == ("Extreme", 1.3)

def test_bond_duration_formula_exact():
    target = mk()                                                  
    filler = mk(position_id="T-9", sector="Fin", notional=120.0, mtm_value=120.0)
    r = run_stress([target, filler], "Geopolitical", 8.5, sentiment=0.0)
    tp = next(p for p in r["positions_pnl"] if p["position_id"] == "T-1")
    assert abs(tp["pnl"] - (-2.0)) < 0.01        # -D*dy*P = -5 * 0.01 * 40

def test_irs_directionality():
    # Macro: rate +150bp. pay_fixed GAINS: +4.0*0.015*100 = +6.0
    # receive_fixed LOSES: -4.2*0.015*90 = -5.67. Diluters keep Fin <25%.
    pay = mk(asset_class="irs", rating=None, direction="pay_fixed",
             notional=100.0, duration=4.0, mtm_value=1.5, sector="Fin")
    rec = mk(position_id="T-2", asset_class="irs", rating=None, direction="receive_fixed",
             notional=90.0, duration=4.2, mtm_value=1.3, sector="Fin")
    d1 = mk(position_id="T-3", asset_class="equity", rating=None,
            sector="Tech", notional=30.0, mtm_value=30.0)
    d2 = mk(position_id="T-4", asset_class="equity", rating=None,
            sector="Health", notional=30.0, mtm_value=30.0)
    r = run_stress([pay, rec, d1, d2], "Macroeconomic", 8.5, sentiment=0.0)
    pnls = {p["position_id"]: p["pnl"] for p in r["positions_pnl"]}
    assert abs(pnls["T-1"] - 6.0) < 0.01
    assert abs(pnls["T-2"] - (-5.67)) < 0.01

def test_sentiment_amplifies_shocks():
    calm = run_stress([mk()], "Geopolitical", 8.5, sentiment=0.0)
    panic = run_stress([mk()], "Geopolitical", 8.5, sentiment=-0.80)
    assert panic["shock_multiplier"] > calm["shock_multiplier"]
    assert panic["total_pnl"] < calm["total_pnl"]

def test_firm_specific_events_never_trigger():
    for ev in ("Merger/Acquisition", "Product Launch", "Earnings/Results"):
        assert run_stress([mk()], ev, 9.9)["triggered"] is False

def test_low_impact_never_triggers():
    assert run_stress([mk()], "Geopolitical", 6.9)["triggered"] is False

def test_concentration_penalty_applies():
    # Fin 40/50 = 80% (>25 -> heavy); Health 10/50 = 20% (<25 -> light).
    heavy = mk(sector="Fin")
    light = mk(position_id="T-2", sector="Health", notional=10.0, mtm_value=10.0)
    r = run_stress([heavy, light], "Geopolitical", 8.5, sentiment=0.0)
    assert r["concentration_flags"], "Fin >25% must be flagged"
    p = {x["position_id"]: x for x in r["positions_pnl"]}
    per_heavy = p["T-1"]["pnl"] / heavy["mtm_value"]
    per_light = p["T-2"]["pnl"] / light["mtm_value"]
    assert abs(per_heavy / per_light - 1.2) < 0.01   # per-$ loss ratio == penalty