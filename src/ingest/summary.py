from collections import Counter
from src.common.store import RAW_PATH, read_all

def main():
    rows = list(read_all(RAW_PATH))
    print(f"total items: {len(rows)}")
    print("by source:       ", dict(Counter(r["source"] for r in rows)))
    print("by source_detail:", dict(Counter(r["source_detail"] for r in rows)))
    if rows:
        print("\nlatest item:", rows[-1]["text"][:100])

if __name__ == "__main__":
    main()