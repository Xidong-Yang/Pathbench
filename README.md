<h1 align="center">PATH-Bench</h1>
<p align="center"><strong>Path-Dependent Evaluation of Lifelong Agents</strong></p>
<p align="center">
  <a href="#repository-map">Repository map</a> ·
  <a href="#read-a-transfer-matrix">Transfer matrices</a> ·
  <a href="#sample-paths">Path sampling</a> ·
  <a href="#evaluate-your-agent">Agent evaluation</a>
</p>

**Does solving one task help an agent solve the next one?** PATH-Bench asks an agent to solve the same task several times, with other tasks in between. That recurring task is the **probe**. Its changing score shows how the intervening experience helps or interferes with the agent.

Use the **200 fixed paths** to compare agents on the task orders from the paper. Use the **transfer matrices** to design a different experiment. Each dataset has 50 positive-dominant and 50 negative-dominant paths.

![PATH-Bench paper overview showing task selection, directed transfer estimates, paths built around a recurring probe, and agent evaluation](docs/assets/pathbench-overview.png)

| Dataset | What the agent does | Paper paths | Transfer data |
| --- | --- | --- | --- |
| BigCodeBench · 120 tasks | Writes Python code that must pass the task's tests | [100 coding paths](paths/bigcodebench.jsonl) | [Gain and voting matrices](transfer/bigcodebench) |
| WildToolBench · 120 scenarios | Chooses tools and arguments across four English dialogue turns | [100 tool-use paths](paths/wildtoolbench.jsonl) | [Gain and voting matrices](transfer/wildtoolbench) |

## Repository map

Start with [paths/](paths) for the exact task orders used in the paper, or [transfer/](transfer) to choose tasks for a new path. A task ID refers to the same task in the path, the matrix and the task pool.

```text
Pathbench/
├── paths/                           Fixed paths, one JSON object per line
│   ├── bigcodebench.jsonl           100 coding paths with ordered task IDs and probe positions
│   └── wildtoolbench.jsonl          100 tool-use paths in the same format
├── transfer/
│   ├── bigcodebench/                Four directed matrices for the coding tasks
│   │   ├── DeepSeek-V4-Flash.csv    Gains measured with DeepSeek-V4-Flash
│   │   ├── GLM-5.csv                Gains measured with GLM-5
│   │   ├── gpt-5.4-mini.csv         Gains measured with gpt-5.4-mini
│   │   └── vote.csv                 Transfer sign chosen by the three models' votes
│   ├── wildtoolbench/               The same four CSV files for the tool-use scenarios
│   ├── vote.py                      Rebuild vote.csv from the three model CSVs
│   └── sample.py                    Sample new paths using the paper's sampling rules
└── tasks/
    ├── bigcodebench/
    │   ├── ids.json                 IDs of the 120 selected tasks
    │   ├── tasks.jsonl              Task prompts, reference code and tests
    │   ├── prepare.py               Rebuild the bundled subset from pinned upstream data
    │   └── LICENSE                  License for the upstream tasks
    └── wildtoolbench/
        ├── ids.json                 IDs of the 120 selected scenarios
        └── prepare.py               Create tasks.jsonl locally from the pinned scenarios
```

<details>
<summary><strong>Evaluation code, examples and repository files</strong></summary>

```text
Pathbench/
├── evaluation/
│   ├── run.py                       Run an agent on paths and write per-step scores
│   ├── domains.py                   Present tasks to the agent and score its responses
│   ├── bcb_worker.py                Execute BigCodeBench tests in the evaluator
│   ├── protocol.py                  Read path and score files, validate probe positions
│   ├── score.py                     Aggregate step scores into AP, FWT, BWT and FGT
│   ├── verify.py                    Check release hashes, task IDs, votes and paper paths
│   ├── test_run.py                  Check agent lifecycle, batch learning and probe behavior
│   ├── requirements-wtb.txt         Dependencies for the WildToolBench evaluator
│   └── examples/
│       ├── chat_agent.py            Adapter for a Chat Completions compatible endpoint
│       ├── memory_agent.py          Adapter that remembers one successful example
│       ├── paths.jsonl              Two short paths for trying the runner or scorer
│       ├── scores.csv               Synthetic step scores for those paths
│       └── expected.csv             Expected summary from scoring the synthetic data
├── docs/assets/pathbench-overview.png   Paper overview shown above
├── README.md                        Guide to the release and agent evaluation
├── NOTICE.md                        Data sources, pinned revisions and citations
├── LICENSE                          Apache License 2.0 for PATH-Bench components
├── SHA256SUMS                       Checksums for the release files
├── .gitattributes                   Git rules for text and binary files
└── .gitignore                       Local data, runs and environments excluded from Git
```

Run `python evaluation/verify.py` to check the release. The BigCodeBench subset includes the paper's prompt correction for `BigCodeBench/656`. Rebuilding it with `prepare.py` requires `pyarrow`. Both datasets' preparation scripts check the source and subset hashes. Upstream materials retain their respective licenses. [Attribution and citations](NOTICE.md)

</details>

## Read a transfer matrix

Each dataset has **three gain matrices and one voting matrix**, each with 120 source tasks (rows) and 120 target tasks (columns). The first CSV field, `source_task`, names the row. To find tasks that might help or interfere with a particular probe, **find the probe in the header and read down its column**. [BigCodeBench matrices](transfer/bigcodebench) · [WildToolBench matrices](transfer/wildtoolbench)

In a model CSV, a cell measures transfer with the model weights held fixed. Row A, column B answers “How did the model’s average score on B change when it saw a worked example of A first?”

**Gain(A → B) = average score on B with an example of A − average score on B with no example.**

A positive gain means the model did better, zero means its average score stayed the same, and a negative gain means it did worse. A gain of `+0.20` is a rise of 20 percentage points. BigCodeBench scores each attempt as pass or fail. WildToolBench scores the fraction of turns with correct tool names and arguments.

In `vote.csv`, each model casts one vote using the **sign** of its gain. Two or three matching signs give the label `1` (positive), `0` (neutral) or `-1` (negative). When one model votes positive, one neutral and one negative, the label is `2` (mixed). Use the model CSVs when the **size** of the gain matters.

Here are three entries from the BigCodeBench CSVs.

| Source task (row) | Target probe (column) | DeepSeek-V4-Flash gain | GLM-5 gain | gpt-5.4-mini gain | Vote |
| --- | --- | ---: | ---: | ---: | --- |
| `BigCodeBench/845` | `BigCodeBench/7` | −0.2 | −0.2 | −0.2 | −1 · negative |
| `BigCodeBench/7` | `BigCodeBench/845` | −0.4 | +0.6 | +0.2 | +1 · positive |
| `BigCodeBench/209` | `BigCodeBench/7` | +0.8 | +0.6 | 0.0 | +1 · positive |

The first two rows show why order matters. Showing task 845 before probe 7 lowered scores for all three models. In the reverse direction, two models improved. If you keep probe 7 fixed, tasks 845 and 209 give you two different histories to try.

To rebuild the vote from the three gain matrices, run `python transfer/vote.py transfer/bigcodebench runs/bcb-vote.csv`.

## Sample paths

For a comparison on the paper's exact paths, read the files in `paths/`. To generate new paths with the paper's design, use the example sampler. Its default settings work as follows. [Sampler source](transfer/sample.py)

1. **Choose a probe.** Read its column in `vote.csv` and group the other tasks by sign. The sampler considers probes with more sources of the requested sign first and tries unused probes before reusing one. Each eligible probe needs a positive source for warm-up and a source in each group the main history will draw from.
2. **Place the first two checks.** Start with the probe, draw five positive warm-up tasks with replacement, then insert the probe again. Both positive- and negative-dominant paths start this way.
3. **Draw the main history.** Sample 100 task occurrences with replacement. Exactly 70 have the requested sign, and 30 come from the combined pool of neutral and opposite-sign tasks. Shuffle the history. The sampler skips mixed pairs, rejects identical neighbors in this history and rejects a history already used for the same probe. It relaxes repeat limits in stages while trying to fill the requested path count.
4. **Insert probe checks.** Draw a block length uniformly from 6 to 12, take that many tasks from the front of the shuffled history, append the probe and repeat until the history is exhausted. The last block can be shorter. The 100 occurrences count only the main history. Warm-up tasks and probe checks add extra steps.

To sample three negative-dominant paths with 90% negative tasks and a probe every 4–8 tasks, run the command below. Other controls include `--length` (tasks after warm-up), `--count` (number of paths) and `--seed` (sampler randomness).

```sh
python transfer/sample.py --dataset bigcodebench --condition negative --count 3 \
  --ratio 0.9 --intervals 4 8 --seed 101 --output runs/new-paths.jsonl
```

### Design a path for your own question

**The paper's sampler is one example. You can write your own sampling code for any path property you want to test.** For example, to test whether order matters, draw one set of positive and negative tasks for a probe. Put the negative tasks first on one path and last on another. To test the strength of transfer, use the gain values in a model CSV to choose stronger or weaker examples. You can also vary the spacing of probe checks or how often a particular task repeats.

To use a custom path with the bundled runner and scorer, write **one JSON object per line**. Choose a `condition` label for your experiment and a unique `sequence_id` within that dataset and condition. List every task occurrence in `task_ids`, using IDs from that dataset's pool. Record all positions of `probe_id` in `probe_steps`, counting from 1. The metrics use at least three probe checks, including the first and last steps of the path. Set `warmup_steps` to the positions strictly between the first two checks.

For a five-step recovery test, use probe 7, introduce task 845, check the probe, introduce task 209, then check it again. This lets you measure what happens after interference and after a potentially helpful task. To run the example below, create the `runs/` directory and save this line as `runs/recovery.jsonl`.

```json
{"dataset":"bigcodebench","condition":"recovery","sequence_id":1,"probe_id":"BigCodeBench/7","task_ids":["BigCodeBench/7","BigCodeBench/845","BigCodeBench/7","BigCodeBench/209","BigCodeBench/7"],"probe_steps":[1,3,5],"warmup_steps":[2]}
```

## Evaluate your agent

Run the commands below from the repository root with Python 3.10 or later.

### Connect your agent

PATH-Bench runs tasks in path order and scores the answers. Your agent owns its memory, experience buffer and learning schedule. Put an adapter in a Python file and pass its path to `--agent`.

| Interface | When the runner calls it | Your adapter's responsibility |
| --- | --- | --- |
| `create_agent(context)` | Once at the start of each path and seed | Return a fresh agent object with its initial state. |
| `agent.respond(messages, tools, context)` | Whenever the environment needs an answer, including during probes | Return an assistant message dictionary with `content` and/or `tool_calls`. |
| `agent.observe(episode)` · optional | Once after a complete ordinary task, including warm-up | Receive the experience and decide whether to store it or learn from it. |
| `agent.close()` · optional | At the end of the run, including when task execution fails | Release connections and stop background workers belonging to this run. |

The runner calls these methods synchronously and waits for each call to finish before continuing.

The factory's `context` contains `run_id`, `dataset`, `condition`, `sequence_id` and `seed`. Each run gets a unique `run_id`, which you can use for an isolated external memory store. Every `respond` call also receives `step` (counted from 1), `task_id` and `is_probe`. Use `(run_id, step)` to identify one task occurrence, including when a task appears again later in the path. All calls within that occurrence share the same context values.

`messages` contains the current conversation. `tools` is `None` for BigCodeBench and the available tool schemas for WildToolBench. Return Python code in `content` for a coding task. For a tool action, use Chat Completions `tool_calls`, with function arguments encoded as a JSON string. Convert any SDK response object to an assistant message dictionary in your adapter.

**An episode covers one complete task.** A BigCodeBench episode usually has one request and one answer. A WildToolBench episode includes all model calls across the scenario's dialogue turns. The runner scores the task before calling `observe`.

| Episode field | Content |
| --- | --- |
| `task_id`, `step` | The completed task and its position in the path |
| `run_id`, `dataset`, `condition`, `sequence_id`, `seed`, `is_probe` | The task's context. Episodes delivered to `observe` have `is_probe=False`. |
| `transcript` | An ordered list of model calls. Each entry has `messages`, `tools`, `response` and `environment_messages`. |
| `score` | The score for this execution, between 0 and 1 |

Each transcript entry stores the messages and tools supplied to `respond`, followed by its returned response. `environment_messages` records messages the simulator appended after that response, up to the next call in that conversation or its end. It can include the simulator's copy of the assistant reply and tool results, including a final tool result. For BigCodeBench this list is empty. These are snapshots, so the adapter can keep episodes in its own experience buffer.

**Your agent chooses when to learn.** `observe` can store an episode, trigger learning immediately, or wait for more experience. Its return value is ignored. For example, an agent can collect five ordinary episodes, learn once, then start its next batch. Any remaining episodes at the end follow the agent's own policy.

```text
Create agent → Probe → Task A → Probe → Task B → … → Final probe → Close agent
                          ↓                 ↓
                     observe(A)        observe(B)
                   Store or learn    Store or learn
```

**Probes measure the current learned state.** When `context["is_probe"]` is true, the adapter must use that state for answering and keep persistent memory, experience buffers and model parameters unchanged by the probe. Task-local conversation state can evolve across the probe's turns and should be discarded when that task ends. The runner records the probe score and skips `observe` for that task. The adapter enforces this measurement mode inside its own agent and external services. For background learners, hold a consistent learned state for the entire probe and resume updates for subsequent ordinary tasks.

Below is a template for wrapping an existing agent. Replace `YourAgent` and its methods with your project's API. Here, `read_only` must implement the probe behavior just described, and `ready_to_learn()` belongs to your agent's own learning policy.

```python
from my_project import YourAgent


class Adapter:
    def __init__(self, context):
        self.agent = YourAgent(seed=context["seed"], run_id=context["run_id"])

    def respond(self, messages, tools, context):
        return self.agent.chat(
            messages=messages,
            tools=tools,
            episode_id=(context["run_id"], context["step"]),
            read_only=context["is_probe"],
        )

    def observe(self, episode):
        self.agent.add_experience(episode)
        if self.agent.ready_to_learn():
            self.agent.learn()

    def close(self):
        self.agent.close()


def create_agent(context):
    return Adapter(context)
```

**To try the included adapters**, configure a Chat Completions compatible endpoint. The chat adapter answers tasks using the endpoint. The memory adapter stores the first exchange from the most recent fully successful ordinary task in its own object and uses it as an example on subsequent calls. Its memory changes in `observe`. [Chat adapter](evaluation/examples/chat_agent.py) · [Memory adapter](evaluation/examples/memory_agent.py)

```sh
export PATHBENCH_BASE_URL='https://your-provider.example/v1'
export PATHBENCH_MODEL='your-model-id'
export PATHBENCH_API_KEY='your-api-key'
```

The chat adapter appends `/chat/completions` to the base URL and sends temperature zero and the run seed. Adjust those request fields for your provider as needed.

<details>
<summary><strong>Updating an adapter written for the previous interface</strong></summary>

Move initialization into `create_agent(context)` and keep memory on the returned agent object. Change `respond(messages, tools, memory, seed)` to the object's `respond(messages, tools, context)`. Move your `learn(memory, episode, seed)` logic into `observe(episode)`, updating your agent's state directly. Read the seed from the run context. Implement the probe behavior using `context["is_probe"]`.

</details>

### Run an evaluation

Set `AGENT` to your Python adapter, or use the included endpoint adapter as shown here.

```sh
AGENT=evaluation/examples/chat_agent.py
```

Prepare the evaluator for your dataset below. Each example runs one short path with one seed and writes a CSV with one score per step. Pass the same path file to the runner and scorer.

<details open>
<summary><strong>BigCodeBench · run the coding example</strong></summary>

The task inputs and tests are bundled. Install Docker and pull the pinned evaluator image once (about 9.3 GB compressed). It runs generated code in a network-disabled container. If you already have an isolated BigCodeBench evaluator with its sanitizer and task dependencies installed, you can use its interpreter via `--bcb-python`.

```sh
docker pull bigcodebench/bigcodebench-evaluate@sha256:a3cd34ec3840a49d6b7afb240f4bdd47c350bc5991043fd0a91773830f7cd405
python evaluation/run.py --dataset bigcodebench --condition positive --sequence 1 --seeds 42 \
  --paths evaluation/examples/paths.jsonl --agent "$AGENT" --name my-agent --output runs/bcb-example.csv
python evaluation/score.py runs/bcb-example.csv --paths evaluation/examples/paths.jsonl
```

</details>

<details>
<summary><strong>WildToolBench · run the tool-use example</strong></summary>

Fetch the pinned simulator, install its dependencies and reconstruct the task pool. Each scenario earns the fraction of turns with correct tool names and arguments.

```sh
git clone https://github.com/yupeijei1997/WildToolBench.git .deps/WildToolBench
git -C .deps/WildToolBench checkout --detach 69647d60b990b169267598573d91fdc00ba69bfb
python -m pip install -r evaluation/requirements-wtb.txt
python tasks/wildtoolbench/prepare.py --source .deps/WildToolBench/wild-tool-bench/data/Wild-Tool-Bench.jsonl

python evaluation/run.py --dataset wildtoolbench --condition positive --sequence 3 --seeds 42 \
  --paths evaluation/examples/paths.jsonl --agent "$AGENT" --name my-agent --output runs/wtb-example.csv
python evaluation/score.py runs/wtb-example.csv --paths evaluation/examples/paths.jsonl
```

</details>

<details>
<summary><strong>Run the custom recovery path</strong></summary>

After saving the five-step path from the sampling section as `runs/recovery.jsonl` and preparing the BigCodeBench evaluator, use its `condition` label in the run command.

```sh
python evaluation/run.py --dataset bigcodebench --condition recovery --paths runs/recovery.jsonl \
  --seeds 42 --agent "$AGENT" --name my-agent --output runs/recovery-scores.csv
python evaluation/score.py runs/recovery-scores.csv --paths runs/recovery.jsonl
```

</details>

<details>
<summary><strong>Full paper setting · 50 paths × 5 seeds per condition</strong></summary>

Omit `--paths`, `--sequence` and `--seeds` to run all official paths for one dataset and condition. Run `positive` and `negative` separately with distinct output files. BigCodeBench uses sequence IDs 1–50. WildToolBench uses 3, 6, …, 150. The five seeds are 42, 77, 117, 97 and 177.

```sh
python evaluation/run.py --dataset bigcodebench --condition positive \
  --agent "$AGENT" --name my-agent --output runs/bcb-positive.csv
python evaluation/score.py --official runs/bcb-positive.csv
```

For split runs, pass all CSV files together to the scorer. With `--official`, it checks that each dataset, condition and agent group includes the full set of paths and seeds. Step CSVs contain `dataset, condition, sequence_id, agent, seed, step, task_id, score`.

</details>

### Read the scores

Within each path, **A1** is the cold probe score and **A2** is the score after warm-up. For transfer and forgetting, the scorer averages each probe appearance across seeds first, computes the quantities below over appearances **i ≥ 3**, then gives each path equal weight.

| Metric | What it measures | Calculation within a path |
| --- | --- | --- |
| **AP** · Average performance | How well did the agent perform overall? | Mean step score across the entire path, averaged over seeds |
| **FWT** · Forward transfer | How much better or worse were later probes than at the cold start? | Mean of Ai − A1 |
| **BWT** · Backward transfer | How much did later probes improve above the warm score? | Mean of max(0, Ai − A2) |
| **FGT** · Forgetting | How far did later probes fall below the warm score? | Mean of max(0, A2 − Ai) |

Scores are fractions. Multiply by 100 to report AP as a percentage and the other metrics in percentage points. Lower FGT means less forgetting.
