from transformers import pipeline

pipe = pipeline("text-classification", model="ProsusAI/finbert", top_k=None)

def flatten(raw):
    """Different transformers versions return [ {...} ] or [ [ {...} ] ].
    Normalize to a flat list — the same guard lives in src/engine/sentiment.py."""
    if raw and isinstance(raw[0], list):
        raw = raw[0]
    return raw

tests = [
    "Quarterly results beat expectations, revenue up 20 percent year on year",
    "Company files for bankruptcy after failing to refinance its debt",
    "The company will report earnings next Tuesday after market close",
]
for t in tests:
    print("\nTEXT:", t)
    for r in sorted(flatten(pipe(t)), key=lambda x: -x["score"]):
        print(f"  {r['label']:>8}: {r['score']:.3f}")