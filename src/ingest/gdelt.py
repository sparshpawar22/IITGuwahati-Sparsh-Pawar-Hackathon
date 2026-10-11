import argparse, time
import requests
from datetime import datetime, timezone
from src.common.schemas import RawItem
from src.common.store import RAW_PATH, append

API = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "nlp-risk-engine/0.1 (hackathon research)"}

MIN_GAP = 6.0           
THROTTLE_BACKOFF = 60   
_last_call = 0.0

def _respect_gap():
    """Global pacing: never let two GDELT requests be closer than MIN_GAP."""
    global _last_call
    wait = MIN_GAP - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()

def _is_throttled(body: str) -> bool:
    b = body.lower()
    return "one every 5 seconds" in b or "limit requests" in b

def fetch(query: str, timespan: str = "24h",
          maxrecords: int = 75, retries: int = 2) -> list[RawItem]:
    """Fetch articles. Failures are loud, pacing is gentle. [] on failure."""
    params = {"query": query, "mode": "ArtList", "maxrecords": maxrecords,
              "timespan": timespan, "format": "json", "sort": "datedesc"}

    for attempt in range(1, retries + 1):
        _respect_gap()
        try:
            r = requests.get(API, params=params, timeout=20, headers=HEADERS)
        except requests.RequestException as e:
            print(f"[gdelt] attempt {attempt}/{retries} network error -> {str(e)[:200]}")
            time.sleep(THROTTLE_BACKOFF)
            continue

        if r.status_code != 200 or _is_throttled(r.text):
            reason = f"HTTP {r.status_code}" if r.status_code != 200 else "GDELT rate-limit message"
            print(f"[gdelt] attempt {attempt}/{retries} blocked ({reason}) "
                  f"-> backing off {THROTTLE_BACKOFF}s")
            time.sleep(THROTTLE_BACKOFF)
            continue

        try:
            data = r.json()
        except ValueError:
            print(f"[gdelt] attempt {attempt}/{retries} non-JSON body -> {r.text[:150]!r}")
            time.sleep(THROTTLE_BACKOFF)
            continue

        return _parse_articles(data)

    print("[gdelt] giving up this cycle — will retry on next poll")
    return []

def _parse_articles(data: dict) -> list[RawItem]:
    items = []
    for art in data.get("articles", []):
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
    ap.add_argument("--timespan", default="24h")
    ap.add_argument("--query", default=(
        '(inflation OR "interest rate" OR "central bank" OR sanctions '
        'OR default OR downgrade OR merger OR earnings OR recession) sourcelang:english'))
    args = ap.parse_args()

    seen: set[str] = set()
    while True:
        new = [i for i in fetch(args.query, timespan=args.timespan)
               if i.url and i.url not in seen]
        for item in new:
            append(RAW_PATH, item)
            seen.add(item.url)
        print(f"[gdelt] +{len(new)} new items (total seen: {len(seen)})")
        if args.once:
            break
        time.sleep(args.interval)

if __name__ == "__main__":
    main()