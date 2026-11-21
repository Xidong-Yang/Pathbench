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
│   ├── export.py                    Export a path as native BCB tasks or WTB run IDs
│   ├── convert.py                   Convert native evaluation files to step scores
│   ├── protocol.py                  Read path and score files, validate probe positions
│   ├── score.py                     Aggregate step scores into AP, FWT, BWT and FGT
│   ├── verify.py                    Check release hashes, task IDs, votes and paper paths
│   ├── test_native.py               Check occurrence mapping and native result conversion
│   └── examples/
│       ├── paths.jsonl              Two short paths for checking native runs or scoring
│       ├── scores.csv               Synthetic step scores for those paths
│       └── expected.csv             Expected summary from scoring the synthetic data
├── integrations/
│   ├── install.py                   Add sequence support to pinned upstream checkouts
│   ├── sources.json                 Upstream revisions and entry-point checksums
│   ├── bigcodebench/
│   │   ├── sequence.py              Ordered generation using BCB prompts and agent hooks
│   │   └── eval_single_task.py      Original per-task BCB evaluation helper
│   └── wildtoolbench/
│       └── sequence.py              Ordered scenarios, native subtask hooks and scoring
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

Each dataset includes **120 × 120 directed transfer matrices** for DeepSeek-V4-Flash, GLM-5 and gpt-5.4-mini. Rows represent source tasks and columns represent target tasks. [BigCodeBench matrices](transfer/bigcodebench) · [WildToolBench matrices](transfer/wildtoolbench)

Each cell stores the change in the target's average score when a source-task example is provided, compared with no example. Positive values indicate improvement, negative values indicate interference, and zero indicates no change.

`vote.csv` combines the three models' gain signs by majority vote. Its labels are `1` for positive transfer, `0` for neutral, `-1` for negative transfer and `2` for a three-way disagreement.

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

To export and score a custom path with the bundled tools, write **one JSON object per line**. Choose a `condition` label for your experiment and a unique `sequence_id` within that dataset and condition. List every task occurrence in `task_ids`, using IDs from that dataset's pool. Record all positions of `probe_id` in `probe_steps`, counting from 1. The metrics use at least three probe checks, including the first and last steps of the path. Set `warmup_steps` to the positions strictly between the first two checks.

For a five-step recovery test, use probe 7, introduce task 845, check the probe, introduce task 209, then check it again. This lets you measure what happens after interference and after a potentially helpful task. To run the example below, create the `runs/` directory and save this line as `runs/recovery.jsonl`.

```json
{"dataset":"bigcodebench","condition":"recovery","sequence_id":1,"probe_id":"BigCodeBench/7","task_ids":["BigCodeBench/7","BigCodeBench/845","BigCodeBench/7","BigCodeBench/209","BigCodeBench/7"],"probe_steps":[1,3,5],"warmup_steps":[2]}
```

## Evaluate your agent

Run your agent through the **BigCodeBench or WildToolBench entry point**, using the same generation and evaluation flow as the original experiments. PATH-Bench supplies the ordered tasks and calculates the path metrics from the native evaluation results.

```text
Choose or sample a path → Export native input → Run BCB / WTB → Convert native scores → Compute path metrics
```

The bundled extensions add ordered execution and a distinct record for every task occurrence. BigCodeBench labels repeated tasks with `_1`, `_2`, and so on. WildToolBench records a zero-based `sequence_index` and a `sequence_run_id`. These identifiers let the scorer find every appearance of the probe.

If your existing experiment checkout already supports `--tasks_file` for BCB or `--run-ids` for WTB, feed it the exported inputs using its existing agent options. The setup below provides those sequence extensions for clean upstream checkouts.

### Prepare a native benchmark checkout

Use Python 3.10 or later. From the PATH-Bench root, set its absolute location for the commands below.

```sh
export PATHBENCH_ROOT="$PWD"
export OPENAI_API_KEY='your-api-key'
export OPENAI_BASE_URL='https://your-provider.example/v1'
export MODEL='your-model-id'
```

The included sequence extensions use a Chat Completions compatible API and the benchmarks' native prompts, simulator and checkers. Install the upstream runtime dependencies for your selected benchmark. The installer checks the pinned entry-point files before adding sequence support and saves the originals beside them as `.pathbench-original`. [Pinned sources](integrations/sources.json)

<details open>
<summary><strong>BigCodeBench</strong></summary>

```sh
git clone https://github.com/bigcode-project/bigcodebench.git .deps/BigCodeBench
git -C .deps/BigCodeBench checkout --detach 09dd993f46c3fbf3a799465bb96d524edcb0b199
python integrations/install.py bigcodebench --repo .deps/BigCodeBench
python -m pip install -e .deps/BigCodeBench
```

Follow the upstream instructions to install the generation dependencies and prepare an isolated Python environment containing BigCodeBench and its task dependencies for code execution. The per-task helper runs `python -m bigcodebench.evaluate --execution local` with the exact task record being tested. Set `BIGCODEBENCH_EVAL_PYTHON` to that evaluator's Python executable. [BigCodeBench installation](https://github.com/bigcode-project/bigcodebench/tree/09dd993f46c3fbf3a799465bb96d524edcb0b199)

```sh
export BIGCODEBENCH_EVAL_PYTHON='/absolute/path/to/evaluator/bin/python'
```

Export one short example path, then generate and evaluate each task in sequence.

```sh
python evaluation/export.py --dataset bigcodebench --condition positive --sequence 1 \
  --paths evaluation/examples/paths.jsonl --output runs/bcb-input

cd "$PATHBENCH_ROOT/.deps/BigCodeBench"
python -m bigcodebench.generate --tasks_file "$PATHBENCH_ROOT/runs/bcb-input/tasks.jsonl" \
  --model "$MODEL" --seed 42 --root "$PATHBENCH_ROOT/runs/bcb-native"

cd "$PATHBENCH_ROOT"
python evaluation/convert.py runs/bcb-native/samples_per_task_eval.jsonl \
  --paths runs/bcb-input/path.jsonl --agent my-agent --seed 42 --output runs/bcb-scores.csv
python evaluation/score.py runs/bcb-scores.csv --paths runs/bcb-input/path.jsonl
```

</details>

<details>
<summary><strong>WildToolBench</strong></summary>

```sh
git clone https://github.com/yupeijei1997/WildToolBench.git .deps/WildToolBench
git -C .deps/WildToolBench checkout --detach 69647d60b990b169267598573d91fdc00ba69bfb
python integrations/install.py wildtoolbench --repo .deps/WildToolBench
python -m pip install -r .deps/WildToolBench/requirements.txt
python tasks/wildtoolbench/prepare.py --source .deps/WildToolBench/wild-tool-bench/data/Wild-Tool-Bench.jsonl
```

Export the ordered scenario IDs, run the native inference entry point, then score its output with the native checker. Each scenario's score is the fraction of subtasks with correct tool names and arguments.

```sh
python evaluation/export.py --dataset wildtoolbench --condition positive --sequence 3 \
  --paths evaluation/examples/paths.jsonl --output runs/wtb-input

cd "$PATHBENCH_ROOT/.deps/WildToolBench/wild-tool-bench"
python -m wtb.openfunctions_evaluation --run-ids "$PATHBENCH_ROOT/runs/wtb-input/run_ids.json" \
  --tasks-file "$PATHBENCH_ROOT/tasks/wildtoolbench/tasks.jsonl" \
  --model "$MODEL" --seed 42 --result-dir "$PATHBENCH_ROOT/runs/wtb-native"
python -m wtb.eval_runner \
  --sequence-results "$PATHBENCH_ROOT/runs/wtb-native/Wild-Tool-Bench_result.jsonl" \
  --sequence-scores "$PATHBENCH_ROOT/runs/wtb-native/Wild-Tool-Bench_score.jsonl"

cd "$PATHBENCH_ROOT"
python evaluation/convert.py runs/wtb-native/Wild-Tool-Bench_score.jsonl \
  --paths runs/wtb-input/path.jsonl --agent my-agent --seed 42 --output runs/wtb-scores.csv
python evaluation/score.py runs/wtb-scores.csv --paths runs/wtb-input/path.jsonl
```

</details>

### Use your own agent

The commands above use the configured model endpoint. To add your agent's experience management, connect the native BCB or WTB hooks. You provide the agent implementation and its constructor settings. The benchmark supplies each task, generated response and evaluation feedback when it calls your methods.

| Where you put it | What you configure |
| --- | --- |
| `my_agent.py` | Your agent class, its initialization, memory handling and native methods |
| `agent-options.json` | Values for your agent's constructor arguments |
| The benchmark command | Which agent class to load and which JSON configuration to read |

**Write your agent class in a Python file.** For example, keep `my_agent.py` and `agent-options.json` in the same directory.

```text
/absolute/path/to/my-agent/
├── my_agent.py
└── agent-options.json
```

If your agent accepts `memory_dir` and `batch_size`, its constructor could look like the excerpt below. Add the native methods listed later in this section using your agent's implementation.

```python
# my_agent.py — constructor excerpt
class MyAgent:
    def __init__(self, memory_dir, batch_size=5):
        self.memory_dir = memory_dir
        self.batch_size = batch_size
```

**Set constructor values in the JSON file.** For the example above, `agent-options.json` could contain the following object. Choose the memory directory for the current experiment.

```json
{
  "memory_dir": "/absolute/path/to/run-memory",
  "batch_size": 5
}
```

The JSON keys must match the arguments accepted by your class's `__init__`. In this example, `memory_dir` and `batch_size` are settings defined by your agent. You can use any constructor settings your own implementation supports. Passing this file is equivalent to constructing the agent with `MyAgent(memory_dir="/absolute/path/to/run-memory", batch_size=5)`. You can omit the configuration flag when the constructor works with no arguments.

**Make the Python file importable and select it in the run command.** Add the directory containing `my_agent.py` to `PYTHONPATH` so that Python can find it from the benchmark checkout.

```sh
export PATHBENCH_AGENT_DIR='/absolute/path/to/my-agent'
export PYTHONPATH="$PATHBENCH_AGENT_DIR${PYTHONPATH:+:$PYTHONPATH}"
```

`my_agent:MyAgent` means “import the module `my_agent` and instantiate its class `MyAgent`.” For an installed package, the same syntax can be `my_package.bcb_agent:MyAgent` or `my_package.wtb_agent:MyAgent`.

After exporting the example path as described above, run the command for your benchmark. BCB uses underscores in its agent flags, and WTB uses hyphens.

```sh
# BigCodeBench
cd "$PATHBENCH_ROOT/.deps/BigCodeBench"
python -m bigcodebench.generate \
  --tasks_file "$PATHBENCH_ROOT/runs/bcb-input/tasks.jsonl" \
  --model "$MODEL" --seed 42 --root "$PATHBENCH_ROOT/runs/bcb-agent" \
  --agent_type my_agent:MyAgent \
  --agent_config "$PATHBENCH_AGENT_DIR/agent-options.json"
```

```sh
# WildToolBench
cd "$PATHBENCH_ROOT/.deps/WildToolBench/wild-tool-bench"
python -m wtb.openfunctions_evaluation \
  --run-ids "$PATHBENCH_ROOT/runs/wtb-input/run_ids.json" \
  --tasks-file "$PATHBENCH_ROOT/tasks/wildtoolbench/tasks.jsonl" \
  --model "$MODEL" --seed 42 --result-dir "$PATHBENCH_ROOT/runs/wtb-agent" \
  --agent-type my_agent:MyAgent \
  --agent-config "$PATHBENCH_AGENT_DIR/agent-options.json"
```

Then use the evaluation, conversion and metric commands from the corresponding walkthrough, pointing them at `runs/bcb-agent` or `runs/wtb-agent`.

**Implement the native methods in your agent class.** The benchmark calls these methods automatically. It fills in `task_id`, `task`, `sample` and `eval_result` from the current run. Your methods receive and use these values.

| Native agent method | BigCodeBench | WildToolBench |
| --- | --- | --- |
| `set_target_task_id(task_id)` | Receives the canonical probe ID before the sequence starts | Receives the probe scenario ID before the sequence starts |
| `prepare_task(task_id, task)` | Called before generating a coding answer. Return a prompt prefix string, or a dictionary with `prefix` and `system_prompt`. | Called before each dialogue subtask. Return a dictionary with `prefix`, `system_prompt` and/or `extra_messages`. |
| `on_task_complete(task_id, task, sample, eval_result)` | Receives generated code and the native test verdict after each coding task | Receives the subtask trace and the native generation-time feedback after each dialogue subtask |
| `finalize()` · optional | Called when the sequence run ends | Called when the sequence run ends |

An agent owns its memory and decides when to learn inside these native hooks. For example, `on_task_complete` can add an experience to a buffer and trigger learning when the agent has enough experience. Configure its probe-learning behavior through `set_target_task_id`, as in the original experiment code. The native hooks are invoked for probe occurrences too, so the agent applies its own target-task rule. Record that rule when reporting results.

WildToolBench retains the original **subtask-level** callbacks. Its generation-time feedback reflects the inference handler's action verdict. The later `wtb.eval_runner` pass checks arguments and supplies the final scores used by PATH-Bench. Use the subtask payload's `original_session_id` to identify the underlying scenario and `session_id` to identify this occurrence in the sequence.

Your native agent may call its own model, memory or learning services from these hooks. The two benchmark environments use their own task prompts, interaction formats and scoring functions.

### Run paper paths or your own paths

To use a paper path, omit `--paths` from `evaluation/export.py` and select the dataset, condition and sequence ID. BigCodeBench uses IDs 1–50 per condition, and WildToolBench uses 3, 6, …, 150. Run each exported path separately for seeds 42, 77, 117, 97 and 177, using a fresh native output directory for every run.

To use a custom path, supply its manifest with `--paths`, for example `--paths runs/recovery.jsonl --condition recovery --sequence 1`. The exported `path.jsonl` records the exact path used for conversion and scoring.

Pass converted CSV files together to compute aggregate metrics. For the paper setting, `--official` checks the complete path and seed set for each dataset, condition and agent group.

```sh
python evaluation/score.py --official runs/paper-scores/*.csv
```

Native result files must contain every task occurrence exactly once. The converter checks their task IDs and positions against the exported path. It writes `dataset, condition, sequence_id, agent, seed, step, task_id, score` for the metric calculator.

### Read the scores

Within each path, **A1** is the cold probe score and **A2** is the score after warm-up. For transfer and forgetting, the scorer averages each probe appearance across seeds first, computes the quantities below over appearances **i ≥ 3**, then gives each path equal weight.

| Metric | What it measures | Calculation within a path |
| --- | --- | --- |
| **AP** · Average performance | How well did the agent perform overall? | Mean step score across the entire path, averaged over seeds |
| **FWT** · Forward transfer | How much better or worse were later probes than at the cold start? | Mean of Ai − A1 |
| **BWT** · Backward transfer | How much did later probes improve above the warm score? | Mean of max(0, Ai − A2) |
| **FGT** · Forgetting | How far did later probes fall below the warm score? | Mean of max(0, A2 − Ai) |

Scores are fractions. Multiply by 100 to report AP as a percentage and the other metrics in percentage points. Lower FGT means less forgetting.
