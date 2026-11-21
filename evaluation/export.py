"""Export one PATH-Bench path for a native benchmark sequence run."""
import argparse
import json
from pathlib import Path

from protocol import DATASETS, ROOT, atomic_text, load_paths


def export_path(path, destination):
    destination = Path(destination)
    files = {"path.jsonl": json.dumps(path) + "\n"}
    if path["dataset"] == "bigcodebench":
        with (ROOT / "tasks/bigcodebench/tasks.jsonl").open() as handle:
            tasks = {task["task_id"]: task for line in handle for task in [json.loads(line)]}
        files["tasks.jsonl"] = "".join(json.dumps(tasks[tid]) + "\n" for tid in path["task_ids"])
    else:
        files["run_ids.json"] = json.dumps(path["task_ids"], indent=2) + "\n"
    for name, content in files.items():
        with atomic_text(destination / name) as handle:
            handle.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--sequence", required=True, type=int)
    parser.add_argument("--paths", type=Path, help="Custom path manifest")
    parser.add_argument("--output", type=Path, required=True, help="Directory for one exported path")
    args = parser.parse_args()
    paths = load_paths([args.paths] if args.paths else None)
    key = (args.dataset, args.condition, args.sequence)
    if key not in paths:
        parser.error(f"Path does not exist: {key}")
    export_path(paths[key], args.output)
    print(f"Exported {len(paths[key]['task_ids'])} task occurrences to {args.output}")


if __name__ == "__main__":
    main()
