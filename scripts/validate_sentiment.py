import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # repo-root shim

import argparse
import pandas as pd

CLASSES = ["negative", "neutral", "positive"]
HF_MAP = {0: "negative", 1: "positive", 2: "neutral"}   # bearish/bullish/neutral

def load_domain(name: str) -> pd.DataFrame:
    if name == "phrasebank_news":
        df = pd.read_csv("data/phrasebank.csv")
        return df.rename(columns={"sentence": "text"})[["text", "label"]]
    df = pd.read_csv("data/raw/hf_tweets.csv").dropna(subset=["text"])
    df["label"] = df["label"].map(HF_MAP)
    return df.dropna(subset=["label"])[["text", "label"]]

def to_label(score: float, t: float) -> str:
    return "positive" if score >= t else "negative" if score <= -t else "neutral"

def accuracy(scores, gts, t):
    return sum(to_label(s, t) == g for s, g in zip(scores, gts)) / len(gts)

def per_class_f1(preds, gts) -> dict:
    out = {}
    for c in CLASSES:
        tp = sum(p == c and g == c for p, g in zip(preds, gts))
        fp = sum(p == c and g != c for p, g in zip(preds, gts))
        fn = sum(p != c and g == c for p, g in zip(preds, gts))
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        out[c] = round(2 * pr * rc / (pr + rc), 3) if pr + rc else 0.0
    return out

def confusion_chart(gts, preds, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    M = [[sum(g == gc and p == pc for g, p in zip(gts, preds)) for pc in CLASSES]
         for gc in CLASSES]
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ax.imshow(M, cmap="Blues")
    ax.set_xticks(range(3), CLASSES, rotation=30)
    ax.set_yticks(range(3), CLASSES)
    mx = max(max(r) for r in M) or 1
    for i in range(3):
        for j in range(3):
            ax.text(j, i, M[i][j], ha="center", va="center",
                    color="white" if M[i][j] > mx * 0.5 else "black")
    ax.set_xlabel("predicted"); ax.set_ylabel("actual"); ax.set_title(title)
    fig.tight_layout(); fig.savefig(path, dpi=150)
    print(f"chart saved -> {path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=500, help="per domain (FinBERT on CPU)")
    args = ap.parse_args()

    from src.engine.sentiment import sentiment
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    vader = SentimentIntensityAnalyzer()

    domains = {}
    for name in ["phrasebank_news", "hf_tweets_social"]:
        df = load_domain(name)
        if len(df) > args.sample:
            df = df.sample(args.sample, random_state=42).reset_index(drop=True)
        print(f"\n[{name}] scoring {len(df)} texts (FinBERT on CPU: a few minutes)...")
        gts, ours, vad = [], [], []
        for i, r in df.iterrows():
            gts.append(r["label"])
            ours.append(sentiment(r["text"])["score"])
            vad.append(vader.polarity_scores(r["text"])["compound"])
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(df)}")
        domains[name] = {"gts": gts, "ours": ours, "vader": vad, "n": len(gts)}

    # per-domain threshold sweeps, then ONE shared threshold (avg accuracy across domains)
    sweeps = {n: {t: round(accuracy(d["ours"], d["gts"], t), 3)
                  for t in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]}
              for n, d in domains.items()}
    shared_t = max(sweeps["phrasebank_news"],
                   key=lambda t: (sweeps["phrasebank_news"][t] + sweeps["hf_tweets_social"][t]) / 2)

    metrics = {
        "shared_threshold": shared_t,
        "threshold_sweeps": sweeps,
        "note": ("phrasebank is IN-distribution for FinBERT (Araci 2019 fine-tuned on FPB) "
                 "-> treat as upper bound; hf_tweets is out-of-distribution robustness."),
        "domains": {},
    }
    for name, d in domains.items():
        ours_preds = [to_label(s, shared_t) for s in d["ours"]]
        vad_preds = [to_label(s, shared_t) for s in d["vader"]]
        metrics["domains"][name] = {
            "n": d["n"],
            "accuracy_finbert": round(accuracy(d["ours"], d["gts"], shared_t), 3),
            "accuracy_vader_baseline": round(accuracy(d["vader"], d["gts"], shared_t), 3),
            "f1_finbert_per_class": per_class_f1(ours_preds, d["gts"]),
        }
        confusion_chart(d["gts"], ours_preds,
                        f"{name} | acc={metrics['domains'][name]['accuracy_finbert']} (t={shared_t})",
                        f"results/confusion_{name}.png")

    pathlib.Path("results").mkdir(exist_ok=True)
    (pathlib.Path("results") / "metrics_sentiment.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({k: v for k, v in metrics.items() if k != "threshold_sweeps"}, indent=2))

if __name__ == "__main__":
    main()