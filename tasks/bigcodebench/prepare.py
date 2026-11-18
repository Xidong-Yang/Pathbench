"""Rebuild the bundled BigCodeBench task file from the upstream v0.1.4 Parquet."""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
from urllib.request import urlopen

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "evaluation"))
from protocol import atomic_text

REVISION = "b74c0d0bf70d2c0bc459be537895cca163007f1a"
URL = (f"https://huggingface.co/datasets/bigcode/bigcodebench/resolve/{REVISION}/"
       "data/v0.1.4-00000-of-00001.parquet")
SOURCE_SHA256 = "d9a4965821c9507ebdfb551c288656b2d5fe553234f5183044333ca8a4018267"
SUBSET_SHA256 = "1c22b3d6a3f5f3f8e41c1148e130f03ea5dc59123ff8d2209a1d3a05ec849052"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Local copy of the pinned Parquet")
    parser.add_argument("--output", type=Path, default=HERE / "tasks.jsonl")
    args = parser.parse_args()
    if args.source:
        raw = args.source.read_bytes()
    else:
        with urlopen(URL, timeout=60) as response:
            raw = response.read()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Unexpected upstream BigCodeBench checksum")
    tasks = {r["task_id"]: r for r in pq.read_table(io.BytesIO(raw)).to_pylist()}
    task = tasks["BigCodeBench/656"]
    task["code_prompt"] = task["code_prompt"].replace("nltk.download('vader_lexicon')\n", "")
    ids = json.loads((HERE / "ids.json").read_text())
    subset = "".join(json.dumps(tasks[i], ensure_ascii=False, separators=(",", ":")) + "\n" for i in ids)
    if hashlib.sha256(subset.encode()).hexdigest() != SUBSET_SHA256:
        raise ValueError("Unexpected checksum for the selected task pool")
    with atomic_text(args.output) as f:
        f.write(subset)
    print(f"Prepared {len(ids)} tasks at {args.output}")


if __name__ == "__main__":
    main()

