"""Files shared by the runner and the scorer. Path positions start at one."""
import csv
import gzip
import json
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("bigcodebench", "wildtoolbench")
SEEDS = (42, 77, 117, 97, 177)
FIELDS = ("dataset", "condition", "sequence_id", "agent", "seed", "step", "task_id", "score")
METRICS = ("AP", "FWT", "BWT", "FGT")


def load_paths(files=None):
    paths = {}
    for file in files or [ROOT / "paths" / (ds + ".jsonl") for ds in DATASETS]:
        with Path(file).open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                path = json.loads(line)
                key = (path["dataset"], path["condition"], int(path["sequence_id"]))
                steps = [i for i, t in enumerate(path["task_ids"], 1) if t == path["probe_id"]]
                if (key in paths or steps != path["probe_steps"] or len(steps) < 3
                        or steps[0] != 1 or steps[-1] != len(path["task_ids"])
                        or path["warmup_steps"] != list(range(2, steps[1]))):
                    raise ValueError(f"Invalid or duplicate path {key}")
                paths[key] = path
    return paths


def load_rows(file):
    opener = gzip.open if Path(file).suffix == ".gz" else open
    with opener(file, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError(f"Missing score columns in {file}")
        yield from reader


@contextmanager
def atomic_text(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", dir=destination.parent, encoding="utf-8",
                            newline="", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            yield handle
            handle.close()
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()

