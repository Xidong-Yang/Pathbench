"""Single-task worker executed inside the BigCodeBench evaluator."""
import json
import sys

from bigcodebench.eval import untrusted_check
from bigcodebench.sanitize import sanitize


if __name__ == "__main__":
    item = json.load(sys.stdin)
    task = item["task"]
    solution = task["code_prompt"] + "\n    pass\n" + sanitize(item["completion"], task["entry_point"])
    status, _ = untrusted_check(solution, task["test"], task["entry_point"],
                                30 * 1024, 30 * 1024, 10, 1, 20)
    if status not in ("pass", "fail", "timeout"):
        raise RuntimeError(f"Unexpected BigCodeBench verdict {status!r}")
    print(json.dumps({"status": status}))

