"""Regression checks for agent-owned learning, probe isolation and run cleanup."""
import csv
import importlib.util
import io
import random
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import run
from protocol import FIELDS


class BatchAgent:
    def __init__(self, context):
        self.context = dict(context)
        self.random_start = random.random()
        self.episodes = []
        self.pending = []
        self.learned_batches = 0
        self.calls = []
        self.closed = False

    def respond(self, messages, tools, context):
        self.calls.append((dict(context), self.learned_batches, len(self.pending)))
        # Adapter edits must not alter environment inputs or recorded experiences.
        messages[0]["content"] = "adapter-local change"
        tools.clear()
        context["is_probe"] = False
        return {"content": "answer"}

    def observe(self, episode):
        self.episodes.append(episode)
        self.pending.append(episode)
        if len(self.pending) == 2:
            self.learned_batches += 1
            self.pending.clear()
        return "ignored by runner"

    def close(self):
        self.closed = True


class AgentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        adapter = Path(self.temporary.name) / "adapter.py"
        adapter.write_text("from pathbench_test_factory import create_agent\n")
        self.spec = importlib.util.spec_from_file_location("pathbench_test_adapter", adapter)
        self.agents = []
        self.factory_contexts = []
        self.agent_type = BatchAgent

        def create_agent(context):
            self.factory_contexts.append(dict(context))
            agent = self.agent_type(context)
            self.agents.append(agent)
            context["seed"] = -1
            return agent

        factory = types.ModuleType("pathbench_test_factory")
        factory.create_agent = create_agent
        modules = patch.dict(sys.modules, {factory.__name__: factory})
        modules.start()
        self.addCleanup(modules.stop)
        self.path = dict(dataset="wildtoolbench", condition="custom", sequence_id=1,
                         probe_id="probe", task_ids=["probe", "task", "probe", "task", "probe"])
        self.args = types.SimpleNamespace(name="test-agent")
        self.output = io.StringIO()
        self.writer = csv.writer(self.output)
        self.writer.writerow(FIELDS)

    @staticmethod
    def solve(task, respond, args):
        messages = [{"role": "user", "content": "question"}]
        tools = [{"type": "function", "function": {"name": "lookup"}}]
        reply = respond(messages, tools)
        messages.extend([reply, {"role": "tool", "content": "first result"}])
        reply = respond(messages, tools)
        messages.extend([reply, {"role": "tool", "content": "final result"}])
        return 0.5

    def run_path(self, path=None, seed=42):
        path = path or self.path
        tasks = dict.fromkeys(path["task_ids"], {})
        with patch.object(run.domains, "wildtoolbench", self.solve):
            run.run_path(path, seed, self.spec, tasks, self.args, self.writer)

    def test_batch_learning_and_complete_multicall_episode(self):
        self.run_path()
        agent = self.agents[0]
        self.assertEqual([e["step"] for e in agent.episodes], [2, 4])
        self.assertEqual([e["task_id"] for e in agent.episodes], ["task", "task"])
        self.assertTrue(all(not e["is_probe"] for e in agent.episodes))
        probe_calls = [(c["step"], learned, pending) for c, learned, pending in agent.calls if c["is_probe"]]
        self.assertEqual(probe_calls, [(1, 0, 0)] * 2 + [(3, 0, 1)] * 2 + [(5, 1, 0)] * 2)
        first, second = agent.episodes[0]["transcript"]
        self.assertEqual(first["messages"], [{"role": "user", "content": "question"}])
        self.assertEqual(first["tools"][0]["function"]["name"], "lookup")
        self.assertEqual(first["environment_messages"][-1]["content"], "first result")
        self.assertEqual(second["messages"][-1]["content"], "first result")
        self.assertEqual(second["environment_messages"][-1]["content"], "final result")
        self.assertEqual(first["response"], {"content": "answer"})
        self.assertEqual(agent.episodes[0]["score"], 0.5)
        self.assertTrue(agent.closed)
        rows = list(csv.DictReader(io.StringIO(self.output.getvalue())))
        self.assertEqual(len(rows), 5)
        self.assertEqual({r["seed"] for r in rows}, {"42"})

    def test_fresh_agent_per_path_and_seed(self):
        self.run_path()
        other = {**self.path, "sequence_id": 2}
        self.run_path(other)
        self.run_path(other, seed=77)
        self.assertEqual(len({c["run_id"] for c in self.factory_contexts}), 3)
        self.assertEqual([c["seed"] for c in self.factory_contexts], [42, 42, 77])
        self.assertEqual([c["sequence_id"] for c in self.factory_contexts], [1, 2, 2])
        self.assertEqual(self.agents[0].random_start, self.agents[1].random_start)
        for agent in self.agents:
            self.assertEqual(agent.calls[0][1:], (0, 0))
            self.assertTrue(agent.closed)

    def test_response_only_agent(self):
        class ResponseOnly:
            def respond(self, messages, tools, context):
                return {"content": "answer"}

        self.agent_type = lambda context: ResponseOnly()
        self.run_path()
        self.assertEqual(len(list(csv.DictReader(io.StringIO(self.output.getvalue())))), 5)

    def test_close_after_environment_or_observer_error(self):
        with patch.object(run.domains, "wildtoolbench", side_effect=RuntimeError("environment failed")):
            with self.assertRaisesRegex(RuntimeError, "environment failed"):
                run.run_path(self.path, 42, self.spec, dict.fromkeys(self.path["task_ids"]),
                             self.args, self.writer)
        self.assertTrue(self.agents[-1].closed)

        class FailingObserver(BatchAgent):
            def observe(self, episode):
                raise RuntimeError("learning failed")

        self.agent_type = FailingObserver
        with self.assertRaisesRegex(RuntimeError, "learning failed"):
            self.run_path()
        self.assertTrue(self.agents[-1].closed)

    def test_invalid_reply_closes_agent(self):
        class InvalidReply(BatchAgent):
            def respond(self, messages, tools, context):
                return "invalid"

        self.agent_type = InvalidReply
        with self.assertRaisesRegex(ValueError, "chat completion message"):
            self.run_path()
        self.assertTrue(self.agents[-1].closed)


if __name__ == "__main__":
    unittest.main()
