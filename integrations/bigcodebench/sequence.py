"""Sequential BigCodeBench generation using native prompts and per-task evaluation."""
import argparse
import importlib
import json
import random
from collections import Counter
from pathlib import Path


def run(args):
    from openai import OpenAI
    from bigcodebench.provider.utility import make_raw_chat_prompt
    from bigcodebench.sanitize import sanitize
    from bigcodebench.eval_single_task import evaluate_single_task

    random.seed(args.seed)
    tasks = [json.loads(line) for line in args.tasks_file.read_text().splitlines() if line.strip()]
    if not tasks:
        raise ValueError("The sequence must contain at least one task")
    counts = Counter()
    for task in tasks:
        tid = task["task_id"]
        task["task_id"] = f"{tid}_{counts[tid]}" if counts[tid] else tid
        counts[tid] += 1
    if len({t["task_id"] for t in tasks}) != len(tasks):
        raise ValueError("Task occurrence IDs collide. Export a path with canonical task IDs.")
    args.root.mkdir(parents=True, exist_ok=True)
    samples_path = args.root / "samples.jsonl"
    scores_path = args.root / "samples_per_task_eval.jsonl"
    if samples_path.exists() or scores_path.exists():
        raise FileExistsError("Choose a fresh --root for each sequence and seed")
    agent = None
    if args.agent_type:
        module, name = args.agent_type.split(":", 1)
        options = json.loads(args.agent_config.read_text()) if args.agent_config else {}
        agent = getattr(importlib.import_module(module), name)(**options)
        agent.set_target_task_id(tasks[0]["task_id"].split("_")[0])
    client = OpenAI(base_url=args.base_url)
    try:
        with samples_path.open("x") as samples, scores_path.open("x") as scores:
            for task in tasks:
                tid = task["task_id"]
                augmentation = (agent.prepare_task(tid, task) or {}) if agent else {}
                if isinstance(augmentation, str):
                    augmentation = {"prefix": augmentation}
                prompt = augmentation.get("prefix", "") + "\nYour task:\n" + task["instruct_prompt"]
                formatted = make_raw_chat_prompt(
                    task_prompt=prompt, subset="full", split="instruct",
                    instruction_prefix="Please provide a self-contained Python script that solves the following problem in a markdown code block:",
                    response_prefix="Below is a Python script with a self-contained function that solves the problem and passes corresponding tests:",
                    tokenizer=None,
                )
                messages = [{"role": "user", "content": formatted}]
                if augmentation.get("system_prompt"):
                    messages.insert(0, {"role": "system", "content": augmentation["system_prompt"]})
                reply = client.chat.completions.create(
                    model=args.model, messages=messages, temperature=args.temperature,
                    seed=args.seed, max_tokens=args.max_new_tokens,
                )
                completion = reply.choices[0].message.content
                if not isinstance(completion, str):
                    raise ValueError(f"Missing code response for {tid}")
                sample = {"task_id": tid, "solution": sanitize(completion, task["entry_point"]),
                          "raw_solution": completion}
                samples.write(json.dumps(sample) + "\n")
                samples.flush()
                result = evaluate_single_task(
                    sample=sample, task_data=task, eval_cwd=str(args.eval_cwd.resolve()),
                    split="instruct", subset="full", root=str(args.root.resolve()),
                    timeout_retries=1,
                )
                if result is None:
                    raise RuntimeError(f"Evaluator failed for {tid}. See the native evaluator output.")
                scores.write(json.dumps(result) + "\n")
                scores.flush()
                if agent:
                    agent.on_task_complete(task_id=tid, task=task, sample=sample, eval_result=result)
    finally:
        client.close()
        if agent and callable(getattr(agent, "finalize", None)):
            agent.finalize()
    print(f"Native per-task results: {scores_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks_file", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base_url", default=None, help="Defaults to OPENAI_BASE_URL")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max_new_tokens", type=int, default=1280)
    parser.add_argument("--eval_cwd", type=Path, default=Path.cwd())
    parser.add_argument("--agent_type", help="Native agent class as package.module:Class")
    parser.add_argument("--agent_config", type=Path, help="JSON object of native agent constructor options")
    run(parser.parse_args())
