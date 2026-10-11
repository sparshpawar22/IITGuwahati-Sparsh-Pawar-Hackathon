from datetime import datetime, timezone
from src.common.schemas import RawItem, Signal, EntityRef
from src.engine.sentiment import sentiment
from src.engine.events import classify
from src.engine.impact import impact_score
from src.engine.entities import link_entities

def analyze_text(text: str, source: str = "news", source_detail: str = "adhoc",
                 published_at: datetime | None = None,
                 item_id: str | None = None,
                 allow_zero_shot: bool = True) -> Signal:
    published_at = published_at or datetime.now(timezone.utc)
    item_id = item_id or "adhoc"

    def _fallback(err: str) -> Signal:
        return Signal(item_id=item_id, source=source, source_detail=source_detail,
                      text=text, published_at=published_at, entities=[],
                      sentiment_score=0.0, sentiment_label="neutral",
                      event_type="Other", event_confidence=0.0,
                      impact_score=1.0, error=err)

    try:
        s = sentiment(text)
        event, conf = classify(text, allow_zero_shot=allow_zero_shot)
        ents = link_entities(text)
        return Signal(
            item_id=item_id, source=source, source_detail=source_detail,
            text=text, published_at=published_at,
            entities=[EntityRef(**e) for e in ents],
            sentiment_score=s["score"], sentiment_label=s["label"],
            event_type=event, event_confidence=conf,
            impact_score=impact_score(event, s["score"], text, source))
    except Exception as e:
        return _fallback(str(e)[:200])

def analyze_item(raw: RawItem | dict, allow_zero_shot: bool = True) -> Signal:
    if isinstance(raw, dict):
        raw = RawItem(**raw)          # pydantic parses ISO date strings back to datetime
    return analyze_text(raw.text, raw.source, raw.source_detail,
                        raw.published_at, raw.item_id, allow_zero_shot)