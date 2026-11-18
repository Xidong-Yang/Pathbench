"""Verify release checksums, task relationships, official paths."""
import hashlib
import json
import sys
from collections import Counter

from protocol import DATASETS, ROOT, load_paths

sys.path.insert(0, str(ROOT / "transfer"))
from vote import compute, read_matrix


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_paths(paths):
    for ds in DATASETS:
        ids = json.loads((ROOT / "tasks" / ds / "ids.json").read_text())
        require(len(ids) == len(set(ids)) == 120, f"Invalid {ds} pool")
        folder = ROOT / "transfer" / ds
        columns, matrix = read_matrix(folder / "vote.csv")
        require(set(ids) == set(columns) and compute(folder) == (columns, matrix), f"{ds} vote differs")
        for condition, sign in (("positive", 1), ("negative", -1)):
            selected = [p for (d, c, _), p in paths.items() if (d, c) == (ds, condition)]
            expected = range(1, 51) if ds == "bigcodebench" else range(3, 151, 3)
            require({p["sequence_id"] for p in selected} == set(expected), f"Wrong {ds} path IDs")
            for path in selected:
                probe = path["probe_id"]
                tasks = path["task_ids"]
                col = columns.index(probe)
                positions = path["probe_steps"]
                require(positions[:2] == [1, 7], "Invalid warm-up positions")
                require(all(matrix[t][col] == 1 for t in tasks[1:6]), "Warm-up contains another relation")
                gains = Counter(matrix[t][col] for t in tasks[7:] if t != probe)
                require(sum(gains.values()) == 100 and gains[sign] == 70 and 2 not in gains,
                        f"Incorrect transfer mix in {ds}/{condition}/{path['sequence_id']}")
                gaps = [y-x-1 for x,y in zip(positions[1:], positions[2:])]
                require(all(6 <= gap <= 12 for gap in gaps[:-1]) and 1 <= gaps[-1] <= 12,
                        "Invalid probe intervals")


if __name__ == "__main__":
    for line in (ROOT / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f"Checksum mismatch for {name}")
    paths = load_paths()
    verify_paths(paths)
    print("Verified 240 task IDs, 200 published paths and both voting matrices.")

