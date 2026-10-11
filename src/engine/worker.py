import argparse, time
from src.common.store import RAW_PATH, SIGNALS_PATH, read_all, append
from src.engine.analyze import analyze_item

def pending_items(allow_zero_shot: bool = True):
    done = {r["item_id"] for r in read_all(SIGNALS_PATH)}
    for raw in read_all(RAW_PATH):
        if raw["item_id"] not in done:
            yield raw, allow_zero_shot

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--rules-only", action="store_true",
                    help="skip the zero-shot fallback (fast bulk backfill)")
    args = ap.parse_args()

    az = not args.rules_only
    while True:
        n = 0
        for raw, az_flag in pending_items(az):
            sig = analyze_item(raw, allow_zero_shot=az_flag)
            append(SIGNALS_PATH, sig)
            n += 1
            print(f"[worker] {sig.event_type:<18} imp={sig.impact_score:<4} "
                  f"sent={sig.sentiment_score:+.2f} {sig.text[:50]!r}")
            if n % 25 == 0:
                print(f"[worker] ... {n} processed this cycle")
        if n:
            print(f"[worker] cycle done: {n} new signals")
        if args.once:
            break
        time.sleep(args.interval)

if __name__ == "__main__":
    main()