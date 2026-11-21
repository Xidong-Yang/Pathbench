"""Regression checks for native path export, repeated tasks and score conversion."""
import copy
import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from convert import convert
from export import export_path
from protocol import ROOT, load_paths


class NativeResultsTests(unittest.TestCase):
    def setUp(self):
        self.path = dict(dataset="bigcodebench", condition="recovery", sequence_id=1,
                         probe_id="BigCodeBench/7", probe_steps=[1, 3, 5], warmup_steps=[2],
                         task_ids=["BigCodeBench/7", "BigCodeBench/845", "BigCodeBench/7",
                                   "BigCodeBench/209", "BigCodeBench/7"])
        self.records = [dict(task_id=tid, status=status) for tid, status in zip(
            ["BigCodeBench/7", "BigCodeBench/845", "BigCodeBench/7_1", "BigCodeBench/209", "BigCodeBench/7_2"],
            ["fail", "pass", "pass", "timeout", "pass"])]

    def test_bcb_occurrences_survive_export_and_conversion(self):
        with tempfile.TemporaryDirectory() as folder:
            export_path(self.path, folder)
            tasks = [json.loads(line) for line in (Path(folder) / "tasks.jsonl").read_text().splitlines()]
            self.assertEqual([t["task_id"] for t in tasks], self.path["task_ids"])
            self.assertEqual(list(load_paths([Path(folder) / "path.jsonl"]).values()), [self.path])
        rows = convert(list(reversed(self.records)), self.path, "agent", 42)
        self.assertEqual([r["task_id"] for r in rows], self.path["task_ids"])
        self.assertEqual([r["step"] for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual([r["score"] for r in rows], [0, 1, 1, 0, 1])
        self.assertEqual({r["seed"] for r in rows}, {42})

    def test_bcb_incomplete_duplicate_and_unknown_verdicts_rejected(self):
        variants = [self.records[:-1], self.records + [self.records[0]],
                    [{**self.records[0], "status": "worker_crashed"}] + self.records[1:],
                    [{**self.records[0], "task_id": "BigCodeBench/999"}] + self.records[1:]]
        for records in variants:
            with self.subTest(records=records), self.assertRaises(ValueError):
                convert(records, self.path, "agent", 42)

    def wtb_path_and_records(self):
        path = {**self.path, "dataset": "wildtoolbench", "probe_id": "wild_tool_bench_42",
                "task_ids": ["wild_tool_bench_42", "wild_tool_bench_63", "wild_tool_bench_42",
                             "wild_tool_bench_81", "wild_tool_bench_42"]}
        records = [dict(id=tid, sequence_index=index,
                        results=[{"label": "correct"}] * index + [{"label": "error"}] * (4-index))
                   for index, tid in enumerate(path["task_ids"])]
        return path, records

    def test_wtb_positions_preserve_repeated_scenarios(self):
        path, records = self.wtb_path_and_records()
        with tempfile.TemporaryDirectory() as folder:
            export_path(path, folder)
            self.assertEqual(json.loads((Path(folder) / "run_ids.json").read_text()), path["task_ids"])
        rows = convert(list(reversed(records)), path, "agent", 77)
        self.assertEqual([r["score"] for r in rows], [0, .25, .5, .75, 1])
        self.assertEqual([r["task_id"] for r in rows], path["task_ids"])

    def test_wtb_malformed_or_incomplete_subtasks_rejected(self):
        path, records = self.wtb_path_and_records()
        for replacement in ({"sequence_index": True}, {"sequence_index": 99},
                            {"id": "wrong"}, {"results": [{"label": "correct"}]},
                            {"results": [{"label": "unknown"}] * 4}):
            changed = copy.deepcopy(records)
            changed[0].update(replacement)
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                convert(changed, path, "agent", 42)

    def test_installer_preserves_native_entry_and_is_idempotent(self):
        spec = importlib.util.spec_from_file_location("native_install", ROOT / "integrations/install.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        source = 'def main():\n    return "original"\n'
        updated = installer.dispatch(source, "fake_sequence", "--tasks_file", "main", True)
        namespace = {}
        exec(compile(updated, "entry.py", "exec"), namespace)
        self.assertEqual(namespace["main"](), "original")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / "bigcodebench"
            package.mkdir()
            entry = package / "generate.py"
            entry.write_text(source)
            source_hash = hashlib.sha256(entry.read_bytes()).hexdigest()
            config = root / "config"
            (config / "bigcodebench").mkdir(parents=True)
            (config / "bigcodebench/sequence.py").write_text("# extension\n")
            (config / "sources.json").write_text(json.dumps({"bigcodebench": {
                "revision": "test", "entries": [{"path": "bigcodebench/generate.py",
                "sha256": source_hash, "module": "fake_sequence", "flag": "--tasks_file",
                "function": "main", "wrap_main": True}],
                "files": {"sequence.py": "bigcodebench/pathbench_sequence.py"}}}))
            installer.HERE = config
            installer.install("bigcodebench", root)
            installer.install("bigcodebench", root)
            self.assertEqual(entry.read_text(), updated)
            entry.write_text(updated + "# user edit\n")
            with self.assertRaisesRegex(ValueError, "edited"):
                installer.install("bigcodebench", root)
            self.assertTrue(entry.read_text().endswith("# user edit\n"))


if __name__ == "__main__":
    unittest.main()
