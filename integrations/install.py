"""Install native sequence extensions into a pinned benchmark checkout."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def dispatch(source, module, flag, function, wrap_main=False):
    code = (f"import sys\n"
            f"if any(arg == {flag!r} or arg.startswith({flag + '='!r}) for arg in sys.argv[1:]):\n"
            f"    from {module} import {function} as sequence_entry\n"
            f"    sequence_entry()\n"
            f"    raise SystemExit(0)\n")
    if wrap_main:
        tree = ast.parse(source)
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        lines = source.splitlines(keepends=True)
        lines.insert(main.body[0].lineno - 1, "".join("    " + line + "\n" for line in code.splitlines()))
        return "".join(lines)
    return 'if __name__ == "__main__":\n' + "".join("    " + line + "\n" for line in code.splitlines()) + "\n" + source


def install(dataset, repo):
    specs = json.loads((HERE / "sources.json").read_text())[dataset]
    edits = {}
    for item in specs["entries"]:
        path = repo / item["path"]
        backup = path.with_name(path.name + ".pathbench-original")
        original = backup.read_bytes() if backup.exists() else path.read_bytes()
        if hashlib.sha256(original).hexdigest() != item["sha256"]:
            raise ValueError(f"Unexpected source {path}. Use the pinned revision {specs['revision']}.")
        updated = dispatch(original.decode(), item["module"], item["flag"], item["function"],
                           item.get("wrap_main", False)).encode()
        if backup.exists() and path.read_bytes() != updated:
            raise ValueError(f"Installed entry was edited: {path}. Preserve those edits before reinstalling.")
        edits[path] = updated
        if not backup.exists():
            edits[backup] = original
    for source, destination in specs["files"].items():
        path = repo / destination
        content = (HERE / dataset / source).read_bytes()
        if path.exists() and path.read_bytes() != content:
            raise ValueError(f"Extension destination already contains different code: {path}")
        edits[path] = content
    previous = {path: path.read_bytes() if path.exists() else None for path in edits}
    try:
        for path, content in edits.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    except Exception:
        for path, content in previous.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    print(f"Installed {dataset} sequence extensions in {repo}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("bigcodebench", "wildtoolbench"))
    parser.add_argument("--repo", type=Path, required=True, help="Pinned upstream repository root")
    args = parser.parse_args()
    install(args.dataset, args.repo.resolve())
