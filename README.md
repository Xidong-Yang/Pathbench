# PATH-Bench

PATH-Bench measures how earlier tasks affect a lifelong agent's performance on a recurring probe. This release provides **the 200 fixed paths evaluated in the paper** and **the directed transfer matrices** for 120 BigCodeBench coding tasks and 120 WildToolBench tool-use scenarios. Use the fixed paths to compare agents under the paper's conditions. Use the matrices to write your own sampler when your research question calls for a different task history.

| Directory | Contents |
| --- | --- |
| [paths](paths) | Task order and probe positions for the paper's 50 paths per dataset and history condition |
| [transfer](transfer) | Three model-specific gain matrices and one voting matrix per dataset, voting code, and the paper's example sampling scheme |
| [tasks](tasks) | Selected task IDs, exact BigCodeBench inputs, and scripts to reconstruct both pools from pinned upstream snapshots |
| [evaluation](evaluation) | Agent interface, coding and tool-use environments, scorer, and a short offline example |

Run the commands below from the repository root with Python 3.10 or newer.

## Use the paths from the paper

The two JSONL manifests preserve the exact task order used in the experiments, including repeated tasks. Each path opens with a cold probe, five positive-transfer warm-up tasks and a second probe. Of the next 100 intervening tasks, 70 come from the dominant relation (positive or negative). The probe recurs after gaps of 6–12 intervening tasks and once at the end, where the last gap can be shorter. Each dataset has 50 paths per condition. BigCodeBench uses IDs 1–50, and WildToolBench retains the original mixed-interval IDs 3, 6, …, 150. [BigCodeBench paths](paths/bigcodebench.jsonl) · [WildToolBench paths](paths/wildtoolbench.jsonl)

## Design paths for your own scenario

The bundled sampler implements one design used in the paper. You can write an independent sampler that reads the released CSVs directly. For a probe task `T`, read **column `T`** to see how each earlier task affects that probe. For example, to study recovery after interference, draw the first history block from negative rows in that column, switch to positive rows, and evaluate the same probe after each block. You can choose the probe, path length, block order, transfer mix and probe intervals to match your setting.

The model-specific matrices contain the change in target performance from zero-shot to one-shot conditioning on the source task. They let you sample by gain magnitude. The voting matrix summarizes the signs from DeepSeek-V4-Flash, GLM-5 and gpt-5.4-mini. Values `1`, `0` and `-1` indicate a positive, neutral or negative majority. The value `2` means the three models disagree. The paper's sampler excludes those pairs. [BigCodeBench matrices](transfer/bigcodebench) · [WildToolBench matrices](transfer/wildtoolbench)

**To use the bundled evaluator**, write one path per line of a JSONL file. Give each path a unique `(dataset, condition, sequence_id)` and use IDs from that dataset's task pool. List every execution in `task_ids`. The scorer expects one recurring `probe_id` with at least three appearances, including the first and last steps. Record all of its positions in `probe_steps`, counting from one. Put the positions between the first and second probes in `warmup_steps`. The second probe supplies the reference for BWT and FGT.

This example places a negative-transfer task before the second probe and a positive-transfer task before the third. After setting up the agent and BigCodeBench evaluator described below, create the `runs/` directory and save this line as `runs/recovery.jsonl`.

```json
{"dataset":"bigcodebench","condition":"recovery","sequence_id":1,"probe_id":"BigCodeBench/7","task_ids":["BigCodeBench/7","BigCodeBench/845","BigCodeBench/7","BigCodeBench/209","BigCodeBench/7"],"probe_steps":[1,3,5],"warmup_steps":[2]}
```

```sh
python evaluation/run.py --paths runs/recovery.jsonl --dataset bigcodebench --condition recovery \
  --seeds 42 --agent evaluation/examples/chat_agent.py --name my-agent --output runs/recovery-scores.csv
python evaluation/score.py runs/recovery-scores.csv --paths runs/recovery.jsonl
```

To adapt the paper's sampler, you can change its parameters directly. This example draws three negative-dominant paths with a 90% dominant share and probe gaps of 4–8 tasks. You can also rebuild a voting matrix from its three model-specific CSVs.

```sh
python transfer/sample.py --dataset bigcodebench --condition negative --count 3 \
  --ratio 0.9 --intervals 4 8 --seed 101 --output runs/new-paths.jsonl
python transfer/vote.py transfer/wildtoolbench runs/wtb-vote.csv
```

## Check the scoring offline

The example uses prefixes of two published paths and synthetic step scores to illustrate the four metrics. You can check the scorer and the release using only the Python standard library.

```sh
python evaluation/score.py evaluation/examples/scores.csv --paths evaluation/examples/paths.jsonl
cat evaluation/examples/expected.csv
python evaluation/verify.py
```

## Run an agent

The sample agent uses a Chat Completions compatible endpoint. Set `PATHBENCH_BASE_URL` to the provider's API base URL, `PATHBENCH_API_KEY` to your credential and `PATHBENCH_MODEL` to your model identifier. The sample sends temperature zero and the run seed. Adapt its request fields if your provider uses different sampling controls.

**BigCodeBench.** The selected tasks and tests are bundled. Install Docker and pull the pinned BigCodeBench evaluator image once. The judge runs generated code in a network-disabled container for each task. For an existing isolated evaluator with BigCodeBench, its sanitizer, and task dependencies installed, pass its interpreter via `--bcb-python`. The upstream image is about 9.3 GB compressed.

```sh
docker pull bigcodebench/bigcodebench-evaluate@sha256:a3cd34ec3840a49d6b7afb240f4bdd47c350bc5991043fd0a91773830f7cd405
python evaluation/run.py --dataset bigcodebench --condition positive --sequence 1 --seeds 42 \
  --paths evaluation/examples/paths.jsonl --agent evaluation/examples/chat_agent.py \
  --name my-agent --output runs/bcb-example.csv
python evaluation/score.py runs/bcb-example.csv --paths evaluation/examples/paths.jsonl
```

**WildToolBench.** Fetch the pinned tool-use environment and select the 120 scenarios. Each session runs the four English turns through the upstream tool simulator and checks tool names and arguments. Its score is the fraction of correct turns.

```sh
git clone https://github.com/yupeijei1997/WildToolBench.git .deps/WildToolBench
git -C .deps/WildToolBench checkout --detach 69647d60b990b169267598573d91fdc00ba69bfb
python -m pip install -r evaluation/requirements-wtb.txt
python tasks/wildtoolbench/prepare.py --source .deps/WildToolBench/wild-tool-bench/data/Wild-Tool-Bench.jsonl
python evaluation/run.py --dataset wildtoolbench --condition positive --sequence 3 --seeds 42 \
  --paths evaluation/examples/paths.jsonl --agent evaluation/examples/chat_agent.py \
  --name my-agent --output runs/wtb-example.csv
python evaluation/score.py runs/wtb-example.csv --paths evaluation/examples/paths.jsonl
```

For a paper-scale comparison, omit `--paths`, `--sequence` and `--seeds` in the runner. This evaluates 50 official paths with seeds 42, 77, 117, 97 and 177 for the chosen dataset and condition. Run positive and negative separately, with distinct output files. You can split by sequence or seed and pass the resulting files together to the scorer. The `--official` check requires every official sequence and all five seeds for each supplied dataset/condition/agent group.

```sh
python evaluation/run.py --dataset bigcodebench --condition positive --agent evaluation/examples/chat_agent.py \
  --name my-agent --output runs/bcb-positive.csv
python evaluation/score.py --official runs/bcb-positive.csv
```

### Agent interface

Pass a Python file to `--agent`. It defines `respond(messages, tools, memory, seed)` and returns a message dictionary with `content` and, for tool calls, standard Chat Completions `tool_calls`. Only the environment receives tests, reference answers and the current tool graph. The sample implementation is [chat_agent.py](evaluation/examples/chat_agent.py).

Optionally implement `learn(memory, episode, seed)` to return updated memory. An episode contains the task ID, model-visible conversation and responses, and the task score. Each path/seed starts with an empty memory dictionary. The runner passes a copy to `respond` and calls `learn` only after intervening tasks, including warm-up tasks. Keep persistent learning state in `memory`. Agents with an external memory service must isolate their storage per independent run and apply writes only inside `learn`. The runner publishes a score file once the requested runs finish successfully.

## Metrics

A BigCodeBench step scores 0 or 1. WildToolBench scores correct subtasks divided by total subtasks in a scenario. AP averages scores over **all steps** within a path and then averages paths with equal weight. For the other metrics, first average the score of each probe appearance over seeds within a path. Let A1 be the cold probe, A2 the warm probe and Ai a later probe. Average each expression over i ≥ 3 within the path, then average over paths.

| Metric | Per-measurement contribution |
| --- | --- |
| FWT | Ai − A1 |
| BWT | max(0, Ai − A2) |
| FGT | max(0, A2 − Ai) |

The runner writes one CSV row per executed step, with columns `dataset, condition, sequence_id, agent, seed, step, task_id, score`. All metrics are fractions. Multiply by 100 to report AP in percent and transfer/forgetting in percentage points.

## Task sources and license

The bundled BCB JSONL matches the main-experiment prompts, including the `BigCodeBench/656` correction. To rebuild it independently, install `pyarrow` and run `python tasks/bigcodebench/prepare.py`. The WTB preparation script accepts the pinned checkout shown above or downloads the upstream JSONL when called without arguments. Both scripts verify source and subset checksums.

PATH-Bench components use Apache License 2.0. Upstream task and evaluator terms apply to their respective materials. [License](LICENSE) · [Attribution, modifications and citations](NOTICE.md)
