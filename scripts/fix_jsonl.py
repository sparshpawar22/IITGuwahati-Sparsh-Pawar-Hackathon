import sys, json, pathlib
from json import JSONDecoder

def main():
    target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/golden_events.jsonl")
    if not target.exists():
        sys.exit(f"file not found: {target}")

    text = target.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    dec = JSONDecoder()
    recovered, bad = [], []

    for lineno, line in enumerate(text.split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        idx, ok = 0, True
        while idx < len(line):
            try:
                obj, end = dec.raw_decode(line, idx)   # parse ONE object at position idx
            except json.JSONDecodeError as e:
                bad.append((lineno, line, e.msg))
                ok = False
                break
            recovered.append(obj)
            idx = end
            while idx < len(line) and line[idx] in " \t":   # skip space between glued objects
                idx += 1
            if ok and idx >= len(line):
                break

    print(f"recovered {len(recovered)} objects; {len(bad)} unparseable line(s)")
    for lineno, line, msg in bad[:5]:
        print(f"  line {lineno} ({msg}): {line[:120]!r}")

    # dedupe identical objects (paste accidents can duplicate)
    seen, unique = set(), []
    for r in recovered:
        key = json.dumps(r, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    backup = target.with_suffix(target.suffix + ".bak")
    backup.write_bytes(target.read_bytes())
    with target.open("w", encoding="utf-8") as f:
        for r in unique:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"rewrote {len(unique)} unique objects -> {target}")
    print(f"original backed up -> {backup}")

if __name__ == "__main__":
    main()