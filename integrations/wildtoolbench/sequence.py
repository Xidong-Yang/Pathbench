"""Native WildToolBench sequence execution and per-occurrence scoring."""
import argparse
import copy
import importlib
import json
import random
from pathlib import Path


def make_handler(model, temperature, seed, agent):
    from wtb.model_handler.api_inference.oai import OpenAIHandler

    class SequenceHandler(OpenAIHandler):
        def _request_tool_call(self, data):
            return self.generate_with_backoff(messages=data["messages"], tools=data["tools"],
                                             model=self.model_name, temperature=self.temperature, seed=seed)

        def inference(self, task):
            results = []
            session = task["sequence_run_id"]
            tools = self.convert_to_tool(task["english_tools"])
            tasks = task["english_tasks"]
            answers = task["english_answer_list"]
            if len(tasks) != len(answers) or not tasks:
                raise ValueError(f"Incomplete scenario {task['id']}")
            for index, (query, answer) in enumerate(zip(tasks, answers)):
                tid = f"{session}_{index}"
                payload = {
                    "session_id": session, "original_session_id": task["id"], "subtask_id": tid,
                    "task_idx": index, "task_text": query,
                    "env_info": task["english_env_info"], "history_tasks": copy.deepcopy(tasks[:index]),
                    "history_answer_lists": copy.deepcopy(answers[:index]),
                    "task_type": (task.get("english_task_types") or [None] * len(tasks))[index],
                    "tool_names": [t.get("name") or t.get("function", {}).get("name") for t in tools],
                }
                history = []
                for previous, previous_answer in zip(tasks[:index], answers[:index]):
                    history.extend(self._add_action_observation(previous, previous_answer,
                                                                self.consecutive_tool_messages))
                payload["gold_history"] = json.dumps(history + [{"role": "user", "content": query}],
                                                      ensure_ascii=False)
                augmentation = (agent.prepare_task(tid, payload) or {}) if agent else {}
                messages = self._pre_messages_processing(task["english_env_info"], query,
                                                         tasks[:index], answers[:index])
                if augmentation.get("system_prompt"):
                    messages[0] = {"role": "system", "content": augmentation["system_prompt"]}
                prefix = []
                if augmentation.get("prefix"):
                    prefix.append({"role": "user", "content": augmentation["prefix"]})
                prefix.extend(copy.deepcopy(augmentation.get("extra_messages", [])))
                messages[1:1] = prefix
                result = self.inference_and_eval_multi_step({
                    "test_entry_id": task["id"], "task_idx": index, "tools": tools,
                    "messages": messages, "answer_list": answer,
                })
                results.append(result)
                if agent:
                    sample = {"trace_text": json.dumps(result.get("inference_log", {}), ensure_ascii=False),
                              "trace_structured": copy.deepcopy(result.get("inference_log", {})),
                              "result": copy.deepcopy(result)}
                    # Match the original per-subtask callback. Full argument scoring happens in eval_runner.
                    passed = (result["action_name_label"] == "correct"
                              and result.get("action_arguments_label", "correct") == "correct")
                    agent.on_task_complete(tid, payload, sample, {"status": "pass" if passed else "fail"})
            return results

    return SequenceHandler(model, temperature)


def main():
    from wtb.constant import PROMPT_PATH

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-ids", required=True, type=Path)
    parser.add_argument("--tasks-file", default=Path(PROMPT_PATH), type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--temperature", default=0.0, type=float)
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--agent-type", help="Native agent class as package.module:Class")
    parser.add_argument("--agent-config", type=Path)
    args = parser.parse_args()
    random.seed(args.seed)
    ids = json.loads(args.run_ids.read_text())
    if not isinstance(ids, list) or not ids or any(not isinstance(tid, str) for tid in ids):
        parser.error("--run-ids must contain an ordered, nonempty list of task IDs")
    tasks = {t["id"]: t for line in args.tasks_file.read_text().splitlines() if line.strip()
             for t in [json.loads(line)]}
    missing = set(ids) - tasks.keys()
    if missing:
        parser.error(f"Unknown scenario IDs: {sorted(missing)}")
    args.result_dir.mkdir(parents=True, exist_ok=True)
    output = args.result_dir / "Wild-Tool-Bench_result.jsonl"
    if output.exists():
        raise FileExistsError("Choose a fresh --result-dir for each sequence and seed")
    agent = None
    if args.agent_type:
        module, name = args.agent_type.split(":", 1)
        options = json.loads(args.agent_config.read_text()) if args.agent_config else {}
        agent = getattr(importlib.import_module(module), name)(**options)
        agent.set_target_task_id(ids[0])
    handler = make_handler(args.model, args.temperature, args.seed, agent)
    try:
        with output.open("x") as handle:
            for index, tid in enumerate(ids):
                task = copy.deepcopy(tasks[tid])
                task["sequence_index"] = index
                task["sequence_run_id"] = f"{args.run_ids.stem}__pos_{index:06d}__{tid}"
                result = handler.inference(task)
                handle.write(json.dumps({"id": tid, "sequence_index": index,
                                         "sequence_run_id": task["sequence_run_id"],
                                         "result": result}) + "\n")
                handle.flush()
    finally:
        handler.client.close()
        if agent and callable(getattr(agent, "finalize", None)):
            agent.finalize()
    print(f"Native inference results: {output}")


def score_main():
    from wtb.eval_runner import params_checker

    parser = argparse.ArgumentParser(description="Score each occurrence with WildToolBench's native checker")
    parser.add_argument("--sequence-results", required=True, type=Path)
    parser.add_argument("--sequence-scores", required=True, type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.sequence_results.read_text().splitlines() if line.strip()]
    scored = []
    seen = set()
    for record in records:
        index = record["sequence_index"]
        if type(index) is not int or index < 0 or index in seen:
            raise ValueError("Invalid or repeated sequence_index")
        seen.add(index)
        results = record["result"]
        if not isinstance(results, list) or not results:
            raise ValueError(f"Incomplete scenario result at position {index}")
        for result in results:
            if isinstance(result, str):
                raise ValueError(f"Scenario execution failed at position {index}: {result}")
            incomplete = any("inference_answer" not in value for key, value in result["inference_log"].items()
                             if key.startswith("step_"))
            if result["action_name_label"] == "error" or incomplete:
                result["label"] = "error"
            else:
                names, arguments = params_checker(result)
                result["label"] = "correct" if names == arguments == "correct" else "error"
        scored.append({"id": record["id"], "sequence_index": index,
                       "sequence_run_id": record["sequence_run_id"], "results": results})
    args.sequence_scores.parent.mkdir(parents=True, exist_ok=True)
    with args.sequence_scores.open("x") as handle:
        for record in scored:
            handle.write(json.dumps(record) + "\n")
    print(f"Native scores: {args.sequence_scores}")
