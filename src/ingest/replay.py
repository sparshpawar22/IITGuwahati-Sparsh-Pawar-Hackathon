import argparse, json, random, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from src.common.schemas import RawItem
from src.common.store import RAW_PATH, append

def load_texts(path: Path, text_col: str | None) -> list[str]:
    if path.suffix == ".jsonl":
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line).get("text", ""))
            except json.JSONDecodeError:
                out.append(line)
        return out
    df = pd.read_csv(path, encoding="latin-1")
    col = text_col or df.columns[0]
    return [t for t in df[col].dropna().astype(str) if len(t) >= 20]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--text-col", default=None)
    ap.add_argument("--source", default="social", choices=["news", "social"])
    ap.add_argument("--detail", default="kaggle_tweets")
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between items (0 = bulk)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args()

    texts = load_texts(Path(args.file), args.text_col)
    if args.shuffle:
        random.shuffle(texts)
    if args.limit:
        texts = texts[:args.limit]
    print(f"[replay] {len(texts)} items loaded from {args.file}")

    while True:
        for t in texts:
            append(RAW_PATH, RawItem(source=args.source, source_detail=args.detail,
                                     text=t, published_at=datetime.now(timezone.utc)))
            print(f"[replay] + {t[:60]!r}")
            if args.interval > 0:
                time.sleep(args.interval)
        if not args.loop:
            break

if __name__ == "__main__":
    main()