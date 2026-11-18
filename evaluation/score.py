"""Aggregate validated step scores to per-condition PATH-Bench metrics."""
import argparse
import csv
import math
import sys
from collections import defaultdict
from statistics import mean

from protocol import METRICS, SEEDS, load_paths, load_rows


def summarize(files, paths, official=False):
    runs = {}
    for file in files:
        for row in load_rows(file):
            ds, condition, seq = row["dataset"], row["condition"], int(row["sequence_id"])
            key = (ds, condition, seq)
            path = paths[key]
            step, seed, score = int(row["step"]), int(row["seed"]), float(row["score"])
            ids = path["task_ids"]
            if not 1 <= step <= len(ids) or ids[step-1] != row["task_id"]:
                raise ValueError(f"Task or position differs from path {key}, step {step}")
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError(f"Invalid score {score} at {key}, step {step}")
            if ds == "bigcodebench" and score not in (0, 1):
                raise ValueError("BigCodeBench step scores must be binary")
            run_key = (ds, condition, row["agent"], seq, seed)
            if run_key not in runs:
                runs[run_key] = [None] * len(ids)
            scores = runs[run_key]
            if scores[step-1] is not None:
                raise ValueError(f"Duplicate score at {run_key}, step {step}")
            scores[step-1] = score
    if not runs:
        raise ValueError("No score rows found")

    groups = defaultdict(lambda: defaultdict(dict))
    for (ds, condition, agent, seq, seed), scores in runs.items():
        if None in scores:
            raise ValueError(f"Incomplete run {(ds, condition, agent, seq, seed)}")
        groups[ds, condition, agent][seq][seed] = scores

    summaries = []
    for (ds, condition, agent), sequences in sorted(groups.items()):
        seeds = set(SEEDS) if official else set(next(iter(sequences.values())))
        expected = {seq for d, c, seq in paths if (d, c) == (ds, condition)}
        if official and set(sequences) != expected:
            raise ValueError(f"Incomplete official sequence set for {(ds, condition, agent)}")
        per_path = []
        for seq, trials in sequences.items():
            if set(trials) != seeds:
                raise ValueError(f"Inconsistent seed set at {(ds, condition, agent, seq)}")
            probes = paths[ds, condition, seq]["probe_steps"]
            a = [mean(s[i-1] for s in trials.values()) for i in probes]
            per_path.append((
                mean(mean(s) for s in trials.values()),
                mean(x - a[0] for x in a[2:]),
                mean(max(0, x - a[1]) for x in a[2:]),
                mean(max(0, a[1] - x) for x in a[2:]),
            ))
        metrics = dict(zip(METRICS, map(mean, zip(*per_path))))
        summaries.append(dict(dataset=ds, condition=condition, agent=agent,
                              sequences=len(sequences), seeds=len(seeds), **metrics))
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scores", nargs="+", help="Step score CSV or CSV.GZ files")
    parser.add_argument("--paths", nargs="+", help="Custom path JSONL files")
    parser.add_argument("--official", action="store_true", help="Require all official paths and five seeds per group")
    args = parser.parse_args()
    if args.official and args.paths:
        parser.error("The official comparison uses the packaged path manifests")
    rows = summarize(args.scores, load_paths(args.paths), args.official)
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys(), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, **{m: f"{row[m]:.8f}" for m in METRICS}})


if __name__ == "__main__":
    main()

