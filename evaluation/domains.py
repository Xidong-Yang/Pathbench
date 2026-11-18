"""Task environments. Only model-visible messages and tools reach the agent."""
import json
import subprocess
from pathlib import Path

WORKER = Path(__file__).with_name("bcb_worker.py")
BCB_IMAGE = "bigcodebench/bigcodebench-evaluate@sha256:a3cd34ec3840a49d6b7afb240f4bdd47c350bc5991043fd0a91773830f7cd405"


def bigcodebench(task, respond, options):
    prompt = ("Please provide a self-contained Python script that solves the following "
              "problem in a markdown code block:\nYour task:\n" + task["instruct_prompt"].strip() + "\n")
    answer = respond([{"role": "user", "content": prompt}], None)
    completion = answer.get("content") or ""
    if options.bcb_python:
        command = [options.bcb_python, str(WORKER)]
    else:
        command = ["docker", "run", "--rm", "-i", "--network=none", "--cap-drop=ALL",
                   "--security-opt=no-new-privileges", "--pids-limit=256", "--entrypoint=python3",
                   options.bcb_image, "-c", WORKER.read_text()]
    payload = json.dumps({"task": {k: task[k] for k in ("code_prompt", "test", "entry_point")},
                          "completion": completion})
    for _ in range(2):
        result = subprocess.run(command, input=payload, capture_output=True, text=True,
                                timeout=300)
        if result.returncode:
            raise RuntimeError(f"BigCodeBench evaluator failed (exit {result.returncode}):\n{result.stderr[-2500:]}")
        status = json.loads(result.stdout.strip().splitlines()[-1])["status"]
        if status != "timeout":
            break
    return int(status == "pass")


def wildtoolbench(task, respond, options):
    from wtb.eval_runner import params_checker
    from wtb.model_handler.base_handler import BaseHandler

    class Handler(BaseHandler):
        def _request_tool_call(self, context):
            reply = respond(context["messages"], context["tools"])
            return reply, 0.0

        def _parse_api_response(self, reply):
            return {"reasoning_content": None, "content": reply.get("content"),
                    "tool_calls": reply.get("tool_calls"), "input_token": 0, "output_token": 0}

    # The pinned upstream handler uses English scenarios and simulates tool observations.
    turns = Handler("pathbench", 0).inference(task)
    if len(turns) != len(task["english_tasks"]) or not turns:
        raise ValueError(f"Incomplete WildToolBench scenario {task['id']}")
    correct = 0
    for turn in turns:
        if isinstance(turn, str) or turn["action_name_label"] == "error":
            continue
        if any("inference_answer" not in data for key, data in turn["inference_log"].items()
               if key.startswith("step_")):
            continue
        name, arguments = params_checker(turn)
        correct += name == "correct" and arguments == "correct"
    return correct / len(turns)

