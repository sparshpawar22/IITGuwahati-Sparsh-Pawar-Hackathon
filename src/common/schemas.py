from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field

def _now() -> datetime:
    return datetime.now(timezone.utc)

class RawItem(BaseModel):
    """One piece of unstructured text, normalized across ALL sources.
    This is the contract between ingestion and the NLP engine."""
    item_id: str = Field(default_factory=lambda: uuid4().hex)
    source: str                  # "news" | "social"
    source_detail: str           # "gdelt" | "newsapi" | "kaggle_tweets" | ...
    text: str
    title: str | None = None
    published_at: datetime
    ingested_at: datetime = Field(default_factory=_now)
    url: str | None = None
    language: str = "en"

class EntityRef(BaseModel):
    ticker: str
    name: str
    sector: str
    how: str                      # "cashtag" | "name"

class Signal(BaseModel):
    """Structured risk signal — the engine's output contract.
    All three PS-required fields live here: sentiment_score, event_type, impact_score."""
    signal_id: str = Field(default_factory=lambda: uuid4().hex)
    item_id: str                  # traceability back to RawItem; also the worker's dedup key
    source: str
    source_detail: str
    text: str
    published_at: datetime
    analyzed_at: datetime = Field(default_factory=_now)
    entities: list[EntityRef] = Field(default_factory=list)
    sentiment_score: float        # -1.0 .. +1.0
    sentiment_label: str          # "positive" | "negative" | "neutral"
    event_type: str
    event_confidence: float       # 0..1
    impact_score: float           # 1..10
    error: str | None = None      # set if analysis failed — item is never retried silently