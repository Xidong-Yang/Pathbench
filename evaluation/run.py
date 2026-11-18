"""Run one or more paths with a user-supplied PATH-Bench agent."""
import argparse
import copy
import csv
import importlib.util
import json
import random
import sys
from pathlib import Path

import domains
from protocol import DATASETS, FIELDS, ROOT, SEEDS, atomic_text, load_paths


def evaluate(path, seed, agent, tasks, args, writer):
    random.seed(seed)
    memory = {}
    for step, tid in enumerate(path["task_ids"], 1):
        transcript = []
        def respond(messages, tools):
            reply = agent.respond(copy.deepcopy(messages), copy.deepcopy(tools), copy.deepcopy(memory), seed)
            if not isinstance(reply, dict) or not ("content" in reply or "tool_calls" in reply):
                raise ValueError("respond() must return a chat completion message")
            transcript.append({"messages": copy.deepcopy(messages), "response": copy.deepcopy(reply)})
            return reply
        solve = getattr(domains, path["dataset"])
        score = solve(tasks[tid], respond, args)
        if tid != path["probe_id"] and hasattr(agent, "learn"):
            memory = agent.learn(memory, {"task_id": tid, "transcript": transcript, "score": score}, seed)
        writer.writerow([path["dataset"], path["condition"], path["sequence_id"], args.name,
                         seed, step, tid, score])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--condition", required=True, help="Condition label in the selected path manifest")
    parser.add_argument("--sequence", type=int, nargs="+", help="Sequence IDs, defaults to all in the condition")
    parser.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    parser.add_argument("--agent", type=Path, required=True, help="Python module exposing respond and optional learn")
    parser.add_argument("--name", required=True, help="Agent identifier used in score files")
    parser.add_argument("--output", type=Path, required=True, help="Destination .csv")
    parser.add_argument("--paths", type=Path, help="Custom path manifest")
    parser.add_argument("--wtb-root", type=Path, default=ROOT / ".deps" / "WildToolBench",
                        help="Root of the pinned upstream WildToolBench checkout")
    parser.add_argument("--bcb-image", default=domains.BCB_IMAGE)
    parser.add_argument("--bcb-python", help="Use a prepared, isolated BigCodeBench evaluation interpreter")
    args = parser.parse_args()
    if args.output.suffix != ".csv":
        parser.error("Choose a .csv output filename")
    if len(args.seeds) != len(set(args.seeds)):
        parser.error("Duplicate run seeds")
    paths = load_paths([args.paths] if args.paths else None)
    selected = {n: p for (ds, cond, n), p in paths.items() if (ds, cond) == (args.dataset, args.condition)}
    if not selected:
        conditions = sorted({c for ds, c, _ in paths if ds == args.dataset})
        parser.error(f"No paths for {args.dataset}/{args.condition}. Available conditions: {conditions}")
    numbers = args.sequence or sorted(selected)
    if not numbers or len(numbers) != len(set(numbers)) or set(numbers) - selected.keys():
        parser.error("Unknown, empty or duplicate sequence selection")
    source = ROOT / "tasks" / args.dataset / "tasks.jsonl"
    if not source.exists():
        parser.error("Prepare the selected task pool first (see README)")
    if args.dataset == "wildtoolbench":
        upstream = args.wtb_root / "wild-tool-bench"
        if not (upstream / "wtb/eval_runner.py").is_file():
            parser.error("Pass the upstream checkout via --wtb-root (see README)")
        sys.path.insert(0, str(upstream.resolve()))
    with source.open(encoding="utf-8") as f:
        tasks = [json.loads(line) for line in f if line.strip()]
    tasks = {t.get("task_id", t.get("id")): t for t in tasks}
    spec = importlib.util.spec_from_file_location("user_agent", args.agent)
    if spec is None or spec.loader is None:
        parser.error("Pass a Python agent module")
    sys.path.insert(0, str(args.agent.resolve().parent))
    with atomic_text(args.output) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FIELDS)
        for n in numbers:
            for seed in args.seeds:
                # A new module instance and external memory for every independent run.
                agent = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = agent
                spec.loader.exec_module(agent)
                evaluate(selected[n], seed, agent, tasks, args, writer)


if __name__ == "__main__":
    main()

