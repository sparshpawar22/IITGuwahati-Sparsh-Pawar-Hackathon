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