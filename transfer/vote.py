"""Vote on directed gains from the three reference models."""
import argparse
import csv
import math
from collections import Counter
from pathlib import Path

MODELS = ("DeepSeek-V4-Flash", "GLM-5", "gpt-5.4-mini")


def read_matrix(path):
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        _, *targets = next(reader)
        rows = {}
        for source, *values in reader:
            if source in rows or len(values) != len(targets):
                raise ValueError(f"Invalid row {source} in {path}")
            rows[source] = [float(v) for v in values]
    if set(rows) != set(targets) or len(rows) != len(targets):
        raise ValueError(f"Matrix must have matching unique task axes in {path}")
    if not all(math.isfinite(v) for values in rows.values() for v in values):
        raise ValueError(f"Nonfinite gain in {path}")
    return targets, rows


def compute(folder):
    columns, first = read_matrix(folder / (MODELS[0] + ".csv"))
    models = [first]
    for name in MODELS[1:]:
        labels, rows = read_matrix(folder / (name + ".csv"))
        if labels != columns or rows.keys() != first.keys():
            raise ValueError(f"Incompatible axes for {name}")
        models.append(rows)
    result = {}
    for source in first:
        votes = []
        for gains in zip(*(m[source] for m in models)):
            sign, count = Counter((x > 0) - (x < 0) for x in gains).most_common(1)[0]
            votes.append(float(sign if count >= 2 else 2))
        result[source] = votes
    return columns, result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    labels, result = compute(args.folder)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["source_task", *labels])
        writer.writerows([task, *values] for task, values in result.items())

