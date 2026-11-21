"""Convert native per-task evaluation records into PATH-Bench step scores."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from protocol import FIELDS, atomic_text, load_paths


def convert(records, path, agent, seed):
    ids = path["task_ids"]
    counts = Counter()
    positions = {}
    for step, tid in enumerate(ids, 1):
        suffix = f"_{counts[tid]}" if counts[tid] else ""
        positions[tid + suffix] = step
        counts[tid] += 1
    scores = {}
    for record in records:
        if path["dataset"] == "bigcodebench":
            step = positions.get(record["task_id"])
            status = record["status"]
            if status not in ("pass", "fail", "timeout"):
                raise ValueError(f"Unrecognized BigCodeBench verdict: {status}")
            score = int(status == "pass")
        else:
            index = record.get("sequence_index")
            if type(index) is not int or not 0 <= index < len(ids):
                raise ValueError("WildToolBench records need a valid zero-based sequence_index")
            step = index + 1
            if record["id"] != ids[index]:
                raise ValueError(f"Task ID differs from the path at step {step}")
            results = record["results"]
            if not isinstance(results, list) or len(results) != 4:
                raise ValueError(f"Expected four subtask results at step {step}")
            if any(not isinstance(result, dict) or result.get("label") not in ("correct", "error") for result in results):
                raise ValueError(f"Unrecognized WildToolBench verdict at step {step}")
            score = sum(result["label"] == "correct" for result in results) / len(results)
        if step is None or step in scores:
            raise ValueError(f"Unknown or duplicate task occurrence: {record}")
        scores[step] = score
    if set(scores) != set(range(1, len(ids) + 1)):
        raise ValueError("Native results must contain every task occurrence exactly once")
    return [dict(dataset=path["dataset"], condition=path["condition"],
                 sequence_id=path["sequence_id"], agent=agent, seed=seed, step=step,
                 task_id=tid, score=scores[step]) for step, tid in enumerate(ids, 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="BCB per_task_eval.jsonl or WTB score.jsonl")
    parser.add_argument("--paths", required=True, type=Path, help="Exported path.jsonl for this run")
    parser.add_argument("--agent", required=True, help="Agent name for reporting")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = load_paths([args.paths])
    if len(paths) != 1:
        parser.error("Pass the exported manifest containing exactly one path")
    records = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    rows = convert(records, next(iter(paths.values())), args.agent, args.seed)
    with atomic_text(args.output) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Converted {len(rows)} task occurrences to {args.output}")


if __name__ == "__main__":
    main()
