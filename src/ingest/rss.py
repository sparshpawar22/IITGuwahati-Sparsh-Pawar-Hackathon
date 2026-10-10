"""Plan B news source: RSS feeds (Yahoo Finance, CNBC, MarketWatch).
Free, no API key, no rate-limit issues. Feeds are swappable in FEEDS below."""
import argparse, time
import feedparser
from datetime import datetime, timezone
from src.common.schemas import RawItem
from src.common.store import RAW_PATH, append

FEEDS = {
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "cnbc_top":      "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "marketwatch":   "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}

def fetch(name: str, url: str, limit: int = 30) -> list[RawItem]:
    d = feedparser.parse(url)
    items = []
    for e in d.entries[:limit]:
        title = (e.get("title") or "").strip()
        summary = (e.get("summary") or "").strip()
        text = f"{title}. {summary}"[:500]           # headline + summary
        if len(title) < 20:
            continue
        published = None
        for key in ("published_parsed", "updated_parsed"):
            if e.get(key):
                published = datetime(*e[key][:6], tzinfo=timezone.utc)
                break
        items.append(RawItem(
            source="news", source_detail=f"rss_{name}",
            text=text, title=title,
            published_at=published or datetime.now(timezone.utc),
            url=e.get("link"),
        ))
    return items

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=900)
    args = ap.parse_args()

    seen: set[str] = set()
    while True:
        total_new = 0
        for name, url in FEEDS.items():
            try:
                new = [i for i in fetch(name, url) if i.url and i.url not in seen]
            except Exception as e:
                print(f"[rss] {name} failed -> {str(e)[:150]}")
                continue
            for item in new:
                append(RAW_PATH, item)
                seen.add(item.url)
            total_new += len(new)
            time.sleep(2)                            # polite gap between feeds
        print(f"[rss] +{total_new} new items (total seen: {len(seen)})")
        if args.once:
            break
        time.sleep(args.interval)

if __name__ == "__main__":
    main()