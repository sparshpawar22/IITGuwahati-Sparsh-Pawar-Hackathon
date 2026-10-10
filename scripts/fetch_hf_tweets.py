from pathlib import Path
import pandas as pd
import requests

BASE = "https://datasets-server.huggingface.co/parquet"
DATASET = "zeroshot/twitter-financial-news-sentiment"
OUT_CSV = Path("data/raw/hf_tweets.csv")
RAW_DIR = Path("data/raw")

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    r = requests.get(BASE, params={"dataset": DATASET}, timeout=30)
    r.raise_for_status()
    train_files = [f for f in r.json()["parquet_files"] if f["split"] == "train"]
    print(f"train parquet files found: {len(train_files)}")

    dfs = []
    for f in train_files:
        local = RAW_DIR / Path(f["filename"]).name
        print(f"downloading {local.name} ({f['size'] / 1e6:.1f} MB)...")
        pr = requests.get(f["url"], timeout=180)
        pr.raise_for_status()
        local.write_bytes(pr.content)
        dfs.append(pd.read_parquet(local))

    # 3. combine + save
    df = pd.concat(dfs, ignore_index=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"saved {len(df)} rows -> {OUT_CSV}")
    print("labels: 0=bearish, 1=bullish, 2=neutral")

if __name__ == "__main__":
    main()