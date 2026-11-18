"""Sample new paths using the paper's positive- or negative-dominant history design."""
import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from vote import read_matrix

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))
from protocol import DATASETS, ROOT, atomic_text


def build_path(rng, dataset, condition, number, probe, positive, queue, intervals):
    warmup = rng.choices(positive, k=5)
    ids = [probe, *warmup, probe]
    offset = 0
    while offset < len(queue):
        gap = rng.randint(*intervals)
        block = queue[offset:offset + gap]
        ids.extend(block)
        ids.append(probe)
        offset += len(block)
    steps = [i for i, task in enumerate(ids, 1) if task == probe]
    return dict(dataset=dataset, condition=condition, sequence_id=number, probe_id=probe,
                probe_steps=steps, warmup_steps=list(range(2, 7)), task_ids=ids)


def sample(args):
    rng = random.Random(args.seed)
    targets, rows = read_matrix(ROOT / "transfer" / args.dataset / "vote.csv")
    dominant = 1 if args.condition == "positive" else -1
    pools = {}
    for col, target in enumerate(targets):
        by_sign = defaultdict(list)
        for source, values in rows.items():
            if source != target:
                by_sign[values[col]].append(source)
        pools[target] = by_sign
    n_major = int(args.length * args.ratio)
    n_other = args.length - n_major
    eligible = [t for t in targets if pools[t][1] and (not n_major or pools[t][dominant])
                and (not n_other or pools[t][0] or pools[t][-dominant])]
    eligible.sort(key=lambda t: -len(pools[t][dominant]))
    paths = []
    used = defaultdict(set)

    def try_target(t, dup_cap, occurrence_cap):
        pool = pools[t]
        for _ in range(args.attempts):
            queue = rng.choices(pool[dominant], k=n_major) + rng.choices(pool[0] + pool[-dominant], k=n_other)
            rng.shuffle(queue)
            counts = Counter(queue)
            if (max(counts.values()) > occurrence_cap or sum(n > 1 for n in counts.values()) > dup_cap
                    or any(a == b for a, b in zip(queue, queue[1:])) or tuple(queue) in used[t]):
                continue
            used[t].add(tuple(queue))
            paths.append(build_path(rng, args.dataset, args.condition, len(paths)+1,
                                    t, pool[1], queue, args.intervals))
            return

    dup_caps = sorted({int(args.length * ratio) for ratio in (0.1, 0.15, 0.2, 0.25)})
    for dup_cap, occ_cap in [(d, 5) for d in dup_caps] + [(dup_caps[-1], n) for n in (6, 7, 8, 10)]:
        for t in eligible:
            if not used[t]:
                try_target(t, dup_cap, occ_cap)
            if len(paths) == args.count:
                return paths
    for cap in (6, 7, 8, 10):
        for t in sorted(eligible, key=lambda t: len(used[t])):
            try_target(t, dup_caps[-1], cap)
            if len(paths) == args.count:
                return paths
    raise ValueError(f"Only {len(paths)} paths met the requested constraints (requested {args.count})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--condition", required=True, choices=["positive", "negative"])
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--length", type=int, default=100, help="Intervening tasks after warm-up")
    parser.add_argument("--intervals", type=int, nargs=2, default=(6, 12), metavar=("MIN", "MAX"))
    parser.add_argument("--ratio", type=float, default=0.7)
    parser.add_argument("--attempts", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.count, args.length, args.attempts, args.intervals[0]) < 1 or args.intervals[0] > args.intervals[1] or not 0 <= args.ratio <= 1:
        parser.error("Invalid size, interval bounds or dominant ratio")
    paths = sample(args)
    with atomic_text(args.output) as f:
        for path in paths:
            f.write(json.dumps(path) + "\n")

