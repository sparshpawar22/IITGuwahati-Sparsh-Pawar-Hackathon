from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
from src.common.schemas import RawItem
from src.common.store import RAW_PATH, SIGNALS_PATH, read_all, append
from src.engine.analyze import analyze_text
from src.common.store import STRESS_RESULTS_PATH

app = FastAPI(title="NLP Risk Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

class TextIn(BaseModel):
    text: str
    source: str = "news"
    source_detail: str = "manual"

@app.get("/health")
def health():
    return {"status": "ok", "service": "nlp-risk-engine"}

@app.post("/analyze")
def analyze(inp: TextIn):
    """Instant analysis, NOT persisted — for demos and tests."""
    return analyze_text(inp.text, inp.source, inp.source_detail)

@app.post("/ingest")
def ingest(inp: TextIn):
    """Full pipeline path: writes a RawItem; the running worker converts it
    to a Signal within seconds. THIS is the end-to-end demo route."""
    raw = RawItem(source=inp.source, source_detail=inp.source_detail,
                  text=inp.text, published_at=datetime.now(timezone.utc))
    append(RAW_PATH, raw)
    return {"ingested": True, "item_id": raw.item_id,
            "note": "worker will emit the signal within ~10s"}

@app.get("/signals")
def signals(entity: str | None = None, event_type: str | None = None,
            min_impact: float = 0.0, limit: int = Query(50, le=500)):
    rows = list(read_all(SIGNALS_PATH))
    rows = [r for r in rows
            if (entity is None or any(e["ticker"] == entity for e in r["entities"]))
            and (event_type is None or r["event_type"] == event_type)
            and r["impact_score"] >= min_impact]
    return list(reversed(rows))[:limit]    

@app.get("/stress")
def stress(limit: int = Query(50, le=200)):
    """Stress-test run history (Module B results)."""
    rows = list(read_all(STRESS_RESULTS_PATH))
    return list(reversed(rows))[:limit]       