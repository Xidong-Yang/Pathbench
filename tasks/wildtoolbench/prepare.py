"""Materialize the PATH-Bench WildToolBench subset from a pinned upstream snapshot."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "evaluation"))
from protocol import atomic_text

REVISION = "69647d60b990b169267598573d91fdc00ba69bfb"
URL = f"https://raw.githubusercontent.com/yupeijei1997/WildToolBench/{REVISION}/wild-tool-bench/data/Wild-Tool-Bench.jsonl"
SOURCE_SHA256 = "d32ad84cea76a0fc0a3c965f60c6f0180e81301e657721d59140dedc33a894ff"
SUBSET_SHA256 = "1f6a706d652355da7f77730a20b7ed2de4ae5e1174487fd89c3d8befdeb0773c"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Pinned upstream JSONL already on disk")
    parser.add_argument("--output", type=Path, default=HERE / "tasks.jsonl")
    args = parser.parse_args()
    if args.source:
        raw = args.source.read_bytes()
    else:
        with urlopen(URL, timeout=60) as response:
            raw = response.read()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Unexpected input checksum. Use the pinned WildToolBench snapshot.")
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    by_id = {r["id"]: r for r in records}
    ids = json.loads((HERE / "ids.json").read_text())
    subset = "".join(json.dumps(by_id[i], ensure_ascii=False, separators=(",", ":")) + "\n" for i in ids)
    if hashlib.sha256(subset.encode()).hexdigest() != SUBSET_SHA256:
        raise ValueError("Unexpected checksum for the selected task pool")
    with atomic_text(args.output) as f:
        f.write(subset)
    print(f"Prepared {len(ids)} scenarios at {args.output}")


if __name__ == "__main__":
    main()

