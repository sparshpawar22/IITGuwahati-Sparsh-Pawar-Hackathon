import json
from pathlib import Path
from typing import Iterator

DATA_DIR = Path("data")
RAW_PATH = DATA_DIR / "raw_items.jsonl"     # ingesters write here
SIGNALS_PATH = DATA_DIR / "signals.jsonl"   # engine writes here

def append(path: Path, model) -> None:
    """Append one record as a single JSON line. Accepts pydantic models OR dicts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = model.model_dump_json() if hasattr(model, "model_dump_json") \
        else json.dumps(model, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def read_all(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line := line.strip():
                yield json.loads(line)