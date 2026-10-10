"""Source 1 (news, live): GDELT 2.0 DOC API — free, no key, refreshes every 15 min."""
import argparse, time
import requests
from datetime import datetime, timezone
from src.common.schemas import RawItem
from src.common.store import RAW_PATH, append

API = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_QUERY = ('(inflation OR "interest rate" OR "central bank" OR sanctions '
                 'OR default OR downgrade OR merger OR earnings OR recession) '
                 'sourcelang:english')

def fetch(query: str = DEFAULT_QUERY, timespan: str = "1h",
          maxrecords: int = 75, retries: int = 3) -> list[RawItem]:
    params = {"query": query, "mode": "ArtList", "maxrecords": maxrecords,
              "timespan": timespan, "format": "json", "sort": "datedesc"}
    for attempt in range(retries):
        try:
            r = requests.get(API, params=params, timeout=15)
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == retries - 1:
                return []
            time.sleep(2 ** attempt)

    items = []
    for art in r.json().get("articles", []):
        text = (art.get("title") or "").strip()
        if len(text) < 20:
            continue
        items.append(RawItem(
            source="news", source_detail="gdelt", text=text, title=text,
            published_at=_parse_gdelt_date(art.get("seendate", "")),
            url=art.get("url"),
        ))
    return items

def _parse_gdelt_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=900)
    ap.add_argument("--query", default=DEFAULT_QUERY)
    args = ap.parse_args()

    seen: set[str] = set()
    while True:
        new = [i for i in fetch(args.query) if i.url and i.url not in seen]
        for item in new:
            append(RAW_PATH, item)
            seen.add(item.url)
        print(f"[gdelt] +{len(new)} new items (total seen: {len(seen)})")
        if args.once:
            break
        time.sleep(args.interval)

if __name__ == "__main__":
    main()