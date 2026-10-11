import re, sys, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # repo-root shim

import pandas as pd

RAW = pathlib.Path("data/raw/phrasebank")
LABELS = {"positive", "negative", "neutral"}

RE_LABEL_FIRST = re.compile(r'^\s*"?(positive|negative|neutral)"?\s*,\s*(.*)$', re.IGNORECASE)
RE_AT_FORMAT   = re.compile(r'^(.*\S)\s*@(positive|negative|neutral)\s*$', re.IGNORECASE)

def strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1].strip()
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None)
    args = ap.parse_args()

    src = pathlib.Path(args.file) if args.file else None
    if src is None:
        cands = list(RAW.rglob("all-data.csv")) + list(RAW.rglob("Sentences_*.txt"))
        if not cands:
            raise SystemExit("No all-data.csv / Sentences_*.txt under data/raw/phrasebank "
                             "(or pass --file). Extract the ZIP first.")
        src = cands[0]

    data = src.read_bytes()
    print(f"file: {src}  |  bytes: {len(data):,}")
    text = data.decode("latin-1")                       # never fails; mojibake is cosmetic
    crlf = text.count("\r\n")
    lone_cr = text.count("\r") - crlf
    print(f"line endings: CRLF={crlf:,}  lone-CR={lone_cr:,}")

    text = text.replace("\r\n", "\n").replace("\r", "\n")   # normalize ALL endings

    rows, skipped = [], []
    for i, line in enumerate(text.split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        m = RE_LABEL_FIRST.match(line)                  # this mirror: label,sentence
        if m:
            rows.append((strip_quotes(m.group(2)), m.group(1).lower()))
            continue
        m = RE_AT_FORMAT.match(line)                    # original FPB: sentence@label
        if m:
            rows.append((strip_quotes(m.group(1)), m.group(2).lower()))
            continue
        skipped.append((i, line))

    print(f"parsed: {len(rows):,}   skipped: {len(skipped):,}")
    if skipped:
        print("skipped samples (first 5):")
        for i, line in skipped[:5]:
            print(f"  line {i}: {line[:120]!r}")

    # --- SANITY GATE: never save a half-parsed dataset silently ---
    total = len(rows) + len(skipped)
    if len(rows) < 0.95 * total:
        sys.exit(f"ABORT: only {len(rows)}/{total} lines parsed — the parse is lossy. "
                 f"Send me the skipped samples above before continuing.")

    df = pd.DataFrame(rows, columns=["sentence", "label"])
    before = len(df)
    df = df.groupby("sentence", as_index=False)["label"].agg(
        lambda s: s.value_counts().idxmax())            # majority vote on conflicts
    print(f"{before:,} rows -> {len(df):,} unique sentences (dedup by majority vote)")
    dist = df["label"].value_counts().to_dict()
    print("label distribution:", dist)

    # --- Advisory checks against documented FPB stats ---
    if len(df) < 4000:
        print("WARNING: <4,000 unique sentences (FPB v1.0 all-data has ~4,840). "
              "Your file may be a truncated mirror — verify the download.")
    if dist.get("positive", 0) < dist.get("neutral", 0):
        print("WARNING: positive is NOT the majority class. Documented FPB is "
              "positive-heavy (~60%) — if this persists the parse is still lossy.")

    pathlib.Path("data").mkdir(exist_ok=True)
    df.to_csv("data/phrasebank.csv", index=False)
    print("saved -> data/phrasebank.csv (commit this file)")

if __name__ == "__main__":
    main()