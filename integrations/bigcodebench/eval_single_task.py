import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_EVAL_PYTHON = "/opt/conda/envs/bigcodebench_eval/bin/python"
LOCAL_EVAL_ENV_NAMES = (
    "bigcodebench_eval",
    "bcb-eval-py310",
    "bcb-eval",
)
EVAL_WALL_TIMEOUT_SECONDS = 300
EVAL_PROCESS_GROUP_GRACE_SECONDS = 0.5


def _eval_python() -> str:
    configured = os.environ.get("BIGCODEBENCH_EVAL_PYTHON")
    if configured:
        return configured
    if os.path.exists(DEFAULT_EVAL_PYTHON):
        return DEFAULT_EVAL_PYTHON

    home = Path.home()
    conda_roots = [
        Path(os.environ.get("CONDA_PREFIX", "")).parent if os.environ.get("CONDA_PREFIX") else None,
        home / "miniconda3" / "envs",
        home / "anaconda3" / "envs",
        home / "mambaforge" / "envs",
        home / "miniforge3" / "envs",
    ]
    for root in conda_roots:
        if root is None:
            continue
        for env_name in LOCAL_EVAL_ENV_NAMES:
            candidate = root / env_name / "bin" / "python"
            if candidate.exists():
                return str(candidate)
    return DEFAULT_EVAL_PYTHON


def _ensure_eval_python_exists(eval_python: str) -> None:
    if os.path.exists(eval_python):
        return
    raise FileNotFoundError(
        f"BigCodeBench eval python not found: {eval_python}. "
        "Set BIGCODEBENCH_EVAL_PYTHON to an existing evaluator Python, "
        "or create/install a local eval env such as "
        "~/miniconda3/envs/bcb-eval-py310."
    )


def _process_group_exists(pgid: int) -> bool:
    if not hasattr(os, "killpg"):
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_process_group(pgid: int) -> None:
    if not hasattr(os, "killpg"):
        return

    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        return

    deadline = time.monotonic() + EVAL_PROCESS_GROUP_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not _process_group_exists(pgid):
            return
        time.sleep(0.05)

    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        return


def _run_eval_command(
    cmd: List[str],
    cwd: str,
    check: bool,
    env: Optional[Dict[str, str]] = None,
    timeout: float = EVAL_WALL_TIMEOUT_SECONDS,
) -> None:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        start_new_session=hasattr(os, "setsid"),
    )
    pgid = proc.pid

    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_group(pgid)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        raise
    finally:
        # The evaluator uses multiprocessing internally. If a worker survives
        # after the evaluator process returns, it can keep the outer runner stuck.
        _terminate_process_group(pgid)

    if check and returncode != 0:
        raise subprocess.CalledProcessError(returncode, cmd)


def evaluate_single_task(
    sample: dict,
    task_data: dict,
    eval_cwd: str,
    split: str,
    subset: str,
    root: str,
    timeout_retries: int = 1,
) -> Optional[dict]:
    """
    Run BigCodeBench local evaluation for one generated sample.

    A temporary one-task dataset file is created to satisfy the evaluator's
    dataset-size checks.
    """
    task_id = sample["task_id"]
    safe_id = task_id.replace("/", "_")

    temp_dir = root
    os.makedirs(temp_dir, exist_ok=True)

    temp_sample_jsonl = os.path.join(temp_dir, f"_eval_temp_{safe_id}.jsonl")
    temp_dataset_jsonl = os.path.join(temp_dir, f"_eval_temp_{safe_id}_dataset.jsonl")

    with open(temp_sample_jsonl, "w") as f:
        f.write(json.dumps(sample) + "\n")

    with open(temp_dataset_jsonl, "w") as f:
        f.write(json.dumps(task_data) + "\n")

    rel_sample_path = os.path.relpath(temp_sample_jsonl, eval_cwd)

    eval_python = _eval_python()
    _ensure_eval_python_exists(eval_python)
    cmd = [
        eval_python,
        "-m",
        "bigcodebench.evaluate",
        "--execution",
        "local",
        "--split",
        split,
        "--subset",
        subset,
        "--samples",
        rel_sample_path,
        "--no_gt",
    ]

    eval_env = os.environ.copy()
    eval_python_dir = os.path.dirname(eval_python)
    if eval_python_dir:
        eval_env["PATH"] = eval_python_dir + os.pathsep + eval_env.get("PATH", "")
    eval_env["BIGCODEBENCH_OVERRIDE_PATH"] = os.path.abspath(temp_dataset_jsonl)
    eval_env.setdefault("MPLBACKEND", "Agg")
    eval_env.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

    result_json_path = temp_sample_jsonl.replace(".jsonl", "_eval_results.json")
    side_paths = [
        result_json_path,
        temp_sample_jsonl.replace(".jsonl", "_pass_at_k.json"),
        temp_sample_jsonl.replace(".jsonl", "_task_status_report.csv"),
    ]

    def cleanup_eval_side_files() -> None:
        for side_file in side_paths:
            if os.path.exists(side_file):
                os.remove(side_file)

    eval_result = None
    attempts = max(1, int(timeout_retries) + 1)
    for attempt in range(1, attempts + 1):
        cleanup_eval_side_files()
        try:
            _run_eval_command(
                cmd,
                cwd=eval_cwd,
                check=True,
                env=eval_env,
                timeout=EVAL_WALL_TIMEOUT_SECONDS,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"[evaluate_single_task] 本地评测失败: {e}")
            cleanup_eval_side_files()
            for path in (temp_sample_jsonl, temp_dataset_jsonl):
                if os.path.exists(path):
                    os.remove(path)
            return None

        eval_result = None
        if os.path.exists(result_json_path):
            with open(result_json_path) as f:
                eval_data = json.load(f)
            task_results = eval_data.get("eval", {}).get(task_id, [])
            if task_results:
                first_result = task_results[0]
                status = first_result.get("status", "unknown")
                eval_result = {
                    "task_id": task_id,
                    "status": status,
                    "detail": first_result,
                    "eval_attempts": attempt,
                }

        status = (eval_result or {}).get("status")
        if status != "timeout" or attempt == attempts:
            break

        print(
            f"[evaluate_single_task] {task_id}: timeout on attempt {attempt}/{attempts}, retrying..."
        )

    cleanup_eval_side_files()

    for path in (temp_sample_jsonl, temp_dataset_jsonl):
        if os.path.exists(path):
            os.remove(path)

    return eval_result
