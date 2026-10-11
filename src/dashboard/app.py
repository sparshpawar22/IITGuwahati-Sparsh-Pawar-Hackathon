import json, os, random
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
API = os.getenv("RISK_API", "http://127.0.0.1:8000")
STRESSABLE = {"Geopolitical", "Macroeconomic", "Credit Event"}
AMBER, RED, GREEN, DIM = "#f7b733", "#ff4b4b", "#2ecc71", "#7a8794"

st.set_page_config(page_title="RISK WAR ROOM", page_icon="🛡", layout="wide")

# THE LOOK (terminal CSS) 
st.markdown(f"""
<style>
  #MainMenu {{visibility:hidden}} footer {{visibility:hidden}}
  html, body, [class*="css"] {{font-family: 'Segoe UI', sans-serif;}}
  .mono {{font-family: 'Consolas', monospace;}}

  .wr-head {{display:flex; align-items:center; gap:14px; padding:4px 0 2px 0;}}
  .wr-title {{font-size:1.9rem; font-weight:800; letter-spacing:2px; color:{AMBER};
              font-family:'Consolas',monospace;}}
  .livedot {{width:11px; height:11px; border-radius:50%; background:{GREEN};
             display:inline-block; animation:blink 1.4s infinite;}}
  @keyframes blink {{50% {{opacity:.15;}}}}
  .wr-tag {{color:{DIM}; font-size:.85rem; letter-spacing:1px; text-transform:uppercase;}}

  .tickerwrap {{overflow:hidden; border-top:1px solid #1d2835; border-bottom:1px solid #1d2835;
                background:#0d131b; margin:6px 0 14px 0;}}
  .ticker {{display:inline-flex; white-space:nowrap; padding:7px 0;
            animation:tickmove 32s linear infinite; font-family:'Consolas',monospace;
            font-size:.86rem; color:#cfd6dd;}}
  .ticker span {{margin-right:38px;}}
  .up {{color:{GREEN};}} .dn {{color:{RED}}} .imp {{color:{AMBER}; margin-left:8px;}}
  @keyframes tickmove {{from {{transform:translateX(0);}} to {{transform:translateX(-50%);}}}}

  .vital {{background:#121a24; border:1px solid #1d2835; border-radius:10px;
           padding:14px 18px; height:100%;}}
  .vital .lbl {{color:{DIM}; font-size:.72rem; letter-spacing:2px; text-transform:uppercase;}}
  .vital .val {{font-family:'Consolas',monospace; font-size:1.7rem; font-weight:700;
                color:#e8e2d9; margin-top:4px;}}
  .vital .sub {{color:{DIM}; font-size:.78rem; margin-top:4px;}}

  .alert {{border:2px solid {RED}; background:rgba(255,75,75,.08); border-radius:12px;
           padding:16px 20px; animation:pulse 1.6s infinite;}}
  @keyframes pulse {{0% {{box-shadow:0 0 0 0 rgba(255,75,75,.45);}}
                     70% {{box-shadow:0 0 0 16px rgba(255,75,75,0);}}
                     100% {{box-shadow:0 0 0 0 rgba(255,75,75,0);}}}}
  .calm {{border:1px solid #1d2835; background:#101720; border-radius:12px; padding:14px 20px;
          color:#cfd6dd;}}

  .badge {{display:inline-block; padding:3px 12px; border-radius:999px; font-weight:800;
           font-size:.75rem; letter-spacing:2px; font-family:'Consolas',monospace;}}
  .b-yellow {{background:rgba(247,183,51,.15); color:{AMBER}; border:1px solid {AMBER};}}
  .b-orange {{background:rgba(255,138,76,.15); color:#ff8a4c; border:1px solid #ff8a4c;}}
  .b-red    {{background:rgba(255,75,75,.15); color:{RED}; border:1px solid {RED};}}

  .stTabs [data-baseweb="tab-list"] {{gap:6px; border-bottom:1px solid #1d2835;}}
  .stTabs [data-baseweb="tab"] {{padding:10px 18px; letter-spacing:1px; color:{DIM};}}
  .stTabs [aria-selected="true"] {{color:{AMBER} !important; border-bottom:2px solid {AMBER};}}

  .wr-footer {{color:{DIM}; font-size:.75rem; font-family:'Consolas',monospace;
               border-top:1px solid #1d2835; padding-top:10px; margin-top:24px;}}
</style>""", unsafe_allow_html=True)

# data access (API first, file fallback) 
def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out

@st.cache_data(ttl=15)
def api_mode() -> bool:
    try:
        return requests.get(f"{API}/health", timeout=1.5).status_code == 200
    except requests.RequestException:
        return False

@st.cache_data(ttl=5)
def get_signals() -> list[dict]:
    if api_mode():
        try:
            r = requests.get(f"{API}/signals", params={"limit": 200}, timeout=3)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
    return list(reversed(read_jsonl(DATA / "signals.jsonl")))[:200]

@st.cache_data(ttl=5)
def get_stress_runs() -> list[dict]:
    if api_mode():
        try:
            r = requests.get(f"{API}/stress", params={"limit": 100}, timeout=3)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
    return list(reversed(read_jsonl(DATA / "stress_results.jsonl")))[:100]

def load_json(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

PORTFOLIO = load_json(DATA / "portfolio.json", [])
DERIVATION = load_json(DATA / "portfolio_derivation.json", {})

try:
    from streamlit_autorefresh import st_autorefresh
    AUTO_OK = True
except ImportError:
    AUTO_OK = False

# small components with personality 
def vital(label, value, sub=""):
    return (f'<div class="vital"><div class="lbl">{label}</div>'
            f'<div class="val">{value}</div><div class="sub">{sub}</div></div>')

def tier_badge(tier: str) -> str:
    cls = {"Moderate": "b-yellow", "Severe": "b-orange"}.get(tier, "b-red")
    label = {"Moderate": "YELLOW", "Severe": "ORANGE"}.get(tier, "RED ALERT")
    return f'<span class="badge {cls}">{label}</span>'

def tier_sentence(tier: str) -> str:
    return {"Moderate": "Noticeable bruise, not a crisis. Log it, watch it.",
            "Severe": "Material drawdown — the risk committee will want this waterfall.",
            "Extreme": "This is the scenario the ALCO meeting gets called for."}[tier]

def mood_gauge(sent: float) -> str:
    sent = max(-1.0, min(1.0, sent))
    pct = (sent + 1) / 2 * 100
    label, color = (("<b>GREED MODE</b> 🤑", GREEN) if sent >= .3 else
                    ("Constructive", GREEN) if sent >= .1 else
                    ("Sideways / sleepy", DIM) if sent > -.1 else
                    ("Nervous 😬", AMBER) if sent > -.3 else ("<b>PANIC</b> 🩸", RED))
    return (f'<div class="vital"><div class="lbl">MARKET MOOD (rolling 20 signals)</div>'
            f'<div class="val" style="color:{color}">{label}</div>'
            f'<div style="height:8px;border-radius:6px;margin-top:8px;'
            f'background:linear-gradient(90deg,{RED},{AMBER},{GREEN});position:relative;">'
            f'<div style="position:absolute;left:calc({pct}% - 6px);top:-3px;width:12px;height:14px;'
            f'background:#fff;border-radius:3px;"></div></div>'
            f'<div class="sub">avg sentiment {sent:+.2f} over last 20 signals</div></div>')

IDLE_QUIPS = ["All quiet on the markets front. The wire is calm.",
              "No fires. Analyst is refilling coffee ☕",
              "Scanning wires… nothing worth waking the risk committee for.",
              "Nothing systemic. The book sleeps easy tonight.",
              "Muted screens, steady hands. Carry on."]

# header + ticker 
signals = get_signals()
runs_all = get_stress_runs()
fired_runs = [r for r in runs_all if r.get("triggered")]

st.markdown(
    f'<div class="wr-head"><span class="livedot"></span>'
    f'<span class="wr-title">RISK WAR ROOM</span>'
    f'<span class="wr-tag">text goes in · priced risk comes out · '
    f'{"API LIVE" if api_mode() else "FILE FALLBACK"}</span></div>',
    unsafe_allow_html=True)

if signals:
    ticks = []
    for s in signals[:10]:
        sent = s.get("sentiment_score", 0) or 0
        tk = next((e.get("ticker") for e in s.get("entities", [])), "MKT")
        cls = "up" if sent >= 0 else "dn"
        arr = "▲" if sent >= 0 else "▼"
        ticks.append(f'<span>{tk} <span class="{cls}">{sent:+.2f} {arr}</span>'
                     f'<span class="imp">IMP {s.get("impact_score", 0)}</span></span>')
    content = " ".join(ticks)
    st.markdown(f'<div class="tickerwrap"><div class="ticker">{content} {content}</div></div>',
                unsafe_allow_html=True)

st.markdown(
    f'<div class="wr-tag">Unstructured wire → structured risk signals → event-driven portfolio '
    f'stress testing · built for the S&P Global &amp; Crisil Campus Hackathon</div>',
    unsafe_allow_html=True)

# sidebar: control room 
with st.sidebar:
    st.markdown(f'<div class="wr-title" style="font-size:1.25rem">🎛 CONTROL ROOM</div>',
                unsafe_allow_html=True)
    st.caption("🟢 API connected" if api_mode() else "🟡 file fallback — engine API offline")
    st.caption(f"Signals chewed: **{len(signals)}** · Shocks simulated: **{len(fired_runs)}**")
    if AUTO_OK:
        if st.checkbox("Auto-refresh (5s)", value=True):
            st_autorefresh(interval=5000, key="auto")
    else:
        st.button("🔄 Refresh")
    with st.expander("🎬 Demo lever"):
        st.markdown("1. open `http://127.0.0.1:8000/docs`\n"
                    "2. `POST /ingest` a nasty headline\n"
                    "3. watch **The Wire**, then **Damage Report**")

# guards 
if not PORTFOLIO:
    st.warning("`data/portfolio.json` not found — run `python scripts/derive_portfolio.py` first.")
    st.stop()
if not signals:
    st.info("The wire is empty. Backfill: `python -m src.engine.worker --once --rules-only`, "
            "or inject via POST /ingest.")
    st.stop()

portfolio_value = sum(p["mtm_value"] for p in PORTFOLIO)
sec_vals = pd.Series({s: sum(p["mtm_value"] for p in PORTFOLIO if p["sector"] == s)
                      for s in {p["sector"] for p in PORTFOLIO}})
heavy = sec_vals[sec_vals / portfolio_value > 0.25]
recent_sent = pd.Series([s.get("sentiment_score", 0) or 0 for s in signals[:20]]).mean()

# vitals row
c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.6])
c1.markdown(vital("BOOK VALUE", f"${portfolio_value:,.0f}M", f"{len(PORTFOLIO)} positions · {sec_vals.size} sectors"),
            unsafe_allow_html=True)
c2.markdown(vital("TRIGGER RATE", f"{(100 * len([s for s in signals if s.get('event_type') in STRESSABLE and s.get('impact_score', 0) >= 7]) / max(len(signals), 1)):.0f}%",
                  "signals ≥ impact 7"), unsafe_allow_html=True)
c3.markdown(vital("CONCENTRATED SECTORS", str(len(heavy)),
                  " · ".join(sorted(heavy.index)) or "none"), unsafe_allow_html=True)
c4.markdown(mood_gauge(0.0 if pd.isna(recent_sent) else float(recent_sent)), unsafe_allow_html=True)

# TABS 
tab_book, tab_wire, tab_damage = st.tabs(["📁 THE BOOK", "📡 THE WIRE", "💥 DAMAGE REPORT"])

# THE BOOK 
with tab_book:
    st.caption("The exposure we're defending. Sector weights derived from real transaction "
               "volumes (Sparkov, 556K txns) — not vibes. Dashed line = the 25% concentration tripwire.")
    left, right = st.columns(2)
    with left:
        ac = pd.Series({a: sum(p["mtm_value"] for p in PORTFOLIO if p["asset_class"] == a)
                        for a in {p["asset_class"] for p in PORTFOLIO}}).sort_values(ascending=False)
        fig = px.pie(names=ac.index, values=ac.values, hole=0.5, title="Book value by asset class")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                          font_color="#e8e2d9")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        gross = pd.Series({a: sum(p["notional"] for p in PORTFOLIO if p["asset_class"] == a)
                           for a in {p["asset_class"] for p in PORTFOLIO}}).sort_values(ascending=False)
        fig = px.bar(x=gross.index, y=gross.values, title="Gross notional exposure ($M)")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                          font_color="#e8e2d9")
        fig.update_traces(marker_color=AMBER)
        st.plotly_chart(fig, use_container_width=True)

    weights = (sec_vals.sort_values(ascending=False) / portfolio_value * 100)
    fig = px.bar(x=weights.index, y=weights.values, title="Sector weights (%) — data-derived",
                 labels={"x": "", "y": "% of book"})
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", font_color="#e8e2d9")
    fig.update_traces(marker_color="#3d6ea5")
    fig.add_hline(y=25, line_dash="dash", line_color=RED,
                  annotation_text="concentration tripwire 25%", annotation_font_color=RED)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("🧾 Every position on the book"):
        st.dataframe(pd.DataFrame([{k: p.get(k) for k in
            ("position_id", "counterparty", "asset_class", "rating", "sector",
             "notional", "mtm_value", "duration", "direction")} for p in PORTFOLIO]),
            use_container_width=True, height=300)
    with st.expander("🔍 Where these numbers came from (provenance)"):
        if DERIVATION:
            st.markdown(f"Source: **{DERIVATION.get('source_dataset', 'n/a')}** · "
                        f"{DERIVATION.get('transactions_used', 0):,} transactions · "
                        f"{DERIVATION.get('license', '')} · seed {DERIVATION.get('seed')}")
            st.json(DERIVATION.get("sector_weights_from_data", {}))

# THE WIRE
with tab_wire:
    st.caption("The unstructured firehose, scored in real time. In the scatter, top-right is "
               "where portfolios get hurt — that corner is Module B's trigger zone.")
    newest = signals[0]
    if newest.get("event_type") in STRESSABLE and newest.get("impact_score", 0) >= 7:
        st.markdown(
            f'<div class="alert"><b style="color:{RED}">🚨 SHOCK DETECTED</b> — waking the risk '
            f'committee. Newest wire: <b>{newest["event_type"]}</b> · impact '
            f'<span class="mono">{newest["impact_score"]}</span> · sentiment '
            f'<span class="mono">{newest.get("sentiment_score", 0):+.2f}</span>'
            f'<br><span style="color:{DIM}">“{(newest.get("text") or "")[:140]}”</span></div>',
            unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="calm">🟢 {random.choice(IDLE_QUIPS)} '
                    f'Newest wire: {newest.get("event_type")} '
                    f'(impact {newest.get("impact_score")}).</div>', unsafe_allow_html=True)

    f1, f2, f3 = st.columns([2, 2, 2])
    evs = sorted({s.get("event_type", "?") for s in signals})
    pick_evs = f1.multiselect("Event type", evs, default=evs)
    min_imp = f2.slider("Min impact", 0.0, 10.0, 0.0, 0.5)
    ent = f3.text_input("Ticker", "").strip().upper()

    rows = [s for s in signals
            if s.get("event_type") in pick_evs
            and s.get("impact_score", 0) >= min_imp
            and (not ent or any(e.get("ticker") == ent for e in s.get("entities", [])))]

    df = pd.DataFrame([{
        "time": pd.to_datetime(s.get("published_at")).strftime("%H:%M:%S"),
        "event_type": s.get("event_type"),
        "impact": s.get("impact_score"),
        "sentiment": s.get("sentiment_score"),
        "tickers": ", ".join(e.get("ticker", "") for e in s.get("entities", [])) or "—",
        "wire": (s.get("text") or "")[:110],
    } for s in rows])
    st.dataframe(df, use_container_width=True, height=380,
                 column_config={"impact": st.column_config.ProgressColumn(
                     "impact", min_value=0, max_value=10, format="%.1f"),
                     "sentiment": st.column_config.NumberColumn(format="%+.2f")})

    if rows:
        sc = pd.DataFrame([{"event": s["event_type"],
                            "sentiment": s.get("sentiment_score", 0),
                            "impact": s.get("impact_score", 0)} for s in rows])
        fig = px.scatter(sc, x="sentiment", y="impact", color="event", height=380,
                         title="Signal map — sentiment × impact")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                          font_color="#e8e2d9")
        fig.add_hrect(y0=7, y1=10, x0=-1, x1=0, line_width=0,
                      fillcolor="rgba(255,75,75,.10)",
                      annotation_text="trigger zone", annotation_font_color=RED)
        st.plotly_chart(fig, use_container_width=True)

# DAMAGE REPORT 
with tab_damage:
    st.caption("What a shock would actually cost. Every number here traces back to a headline "
               "that crossed the wire — and a formula you can put on a whiteboard.")
    if not fired_runs:
        st.info("No shocks simulated yet. Inject a trigger-level event via POST /ingest, or run "
                "`python -m src.module_b.worker --simulate Geopolitical 8.5 -0.85`.")
        st.stop()

    pick = st.selectbox("Stress run", [r["run_id"] for r in fired_runs],
                        format_func=lambda rid: next(
                            f"{r['run_id']} — {r['trigger']['event_type']} "
                            f"({r.get('pct_loss', 0):+.2f}%)" for r in fired_runs if r["run_id"] == rid))
    r = next(x for x in fired_runs if x["run_id"] == pick)

    head = (f'<div class="alert" style="animation:none;border-color:{AMBER};'
            f'background:rgba(247,183,51,.06);">'
            f'{tier_badge(r["tier"])} &nbsp; <b>{r["run_id"]}</b> — '
            f'{r["trigger"]["event_type"]} · impact {r["trigger"]["impact_score"]} · '
            f'shock ×{r["shock_multiplier"]}'
            f'<br><span style="color:{DIM}">{tier_sentence(r["tier"])}</span></div>')
    if fired_runs[0]["run_id"] == r["run_id"]:
        head = head.replace('style="animation:none;', 'style="')
    st.markdown(head, unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.markdown(vital("VALUE BEFORE", f"${r['portfolio_value_before']:,.1f}M"), unsafe_allow_html=True)
    m2.markdown(vital("VALUE AFTER", f"${r['portfolio_value_after']:,.1f}M",
                      f"P&L {r['total_pnl']:+,.1f}M ({r['pct_loss']:+.2f}%)"), unsafe_allow_html=True)
    sh = r.get("effective_shocks", {})
    recipe = (f"IG +{sh.get('ig_bps', 0):.0f}bp · HY +{sh.get('hy_bps', 0):.0f}bp · "
              f"rates +{sh.get('rate_bps', 0):.0f}bp · USD +{sh.get('fx', 0) * 100:.1f}% · "
              f"equities {sh.get('equity', 0) * 100:+.1f}%")
    m3.markdown(vital("SHOCK RECIPE APPLIED", f"×{r['shock_multiplier']}", recipe), unsafe_allow_html=True)

    wf = go.Figure(go.Waterfall(
        x=list(r["by_asset_class"].keys()) + ["NET"],
        y=list(r["by_asset_class"].values()) + [0],
        measure=["relative"] * len(r["by_asset_class"]) + ["total"],
        increasing=dict(marker=dict(color=GREEN)),
        decreasing=dict(marker=dict(color=RED)),
        text=[f"{v:+.1f}" for v in r["by_asset_class"].values()] + [f"{r['total_pnl']:+.1f}"],
        textposition="outside"))
    wf.update_layout(title=f"P&L waterfall by asset class ($M) — {r['run_id']}",
                     template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                     font_color="#e8e2d9", showlegend=False, height=430)
    st.plotly_chart(wf, use_container_width=True)

    if r.get("concentration_flags"):
        st.warning("⚠️ " + " · ".join(r["concentration_flags"]) +
                   "  — the data-derived weights surfaced these; we didn't hand-pick them.")

    left, right = st.columns(2)
    with left:
        sv = pd.Series(r["by_sector"]).sort_values()
        fig = px.bar(x=sv.values, y=sv.index, orientation="h", title="P&L by sector ($M)")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", font_color="#e8e2d9")
        fig.update_traces(marker_color=["#2ca02c" if v >= 0 else "#d62728" for v in sv.values])
        st.plotly_chart(fig, use_container_width=True)
    with right:
        tl = pd.DataFrame(r["top_losers"])
        fig = px.bar(tl, x="pnl", y="counterparty", orientation="h", title="Top 5 losers ($M)")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", font_color="#e8e2d9")
        fig.update_traces(marker_color=RED)
        st.plotly_chart(fig, use_container_width=True)

    hist = pd.DataFrame([{"run": x["run_id"],
                          "when": pd.to_datetime(x["created_at"]).strftime("%m-%d %H:%M"),
                          "event": x["trigger"]["event_type"], "impact": x["trigger"]["impact_score"],
                          "tier": x["tier"], "pnl_%": x["pct_loss"]} for x in fired_runs])
    st.markdown("**Run history** — every shock leaves a paper trail.")
    st.dataframe(hist, use_container_width=True, height=200,
                 column_config={"impact": st.column_config.ProgressColumn(
                     "impact", min_value=0, max_value=10, format="%.1f"),
                     "pnl_%": st.column_config.NumberColumn(format="%+.2f")})

# footer 
st.markdown(
    f'<div class="wr-footer">⚡ handcrafted during a hackathon · signals chewed {len(signals)} · '
    f'shocks simulated {len(fired_runs)} · '
    f'engine API: {"LIVE" if api_mode() else "offline (file fallback)"} · '
    f'<span class="livedot"></span> live</div>', unsafe_allow_html=True)