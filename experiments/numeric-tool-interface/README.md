# Numeric Tool-Interface Semantics

Difficulty: **Easy-Medium**

Compute Budget: **Low** for local 8B-12B models; **Low-Medium** if adding frontier model replications.

## Pitch

Tool schemas may not be neutral wrappers around model intent. When an agent is asked to "slightly increase c," the numeric argument it emits may depend on the current values shown in the prompt, the schema bounds on sibling parameters, whether a relational rule is written in the tool description or user prompt, and whether sibling parameters are required. This project treats numeric tool arguments as behavioral measurements: if the same request produces different `c` values under different interface designs, then tool design is part of the agent's action policy, not just an implementation detail.

Concrete experiments:

- Test whether adding a written rule such as `a+b+c >= 1.0` changes `c_output` relative to a matched no-rule interface.
- Move the required minimum for `c` by changing current `a,b` values and test whether model outputs track the moving floor.
- Create disagreement between prompt-visible current values and schema-implied ranges to see which source the model follows.
- Remove prompt-visible state and test whether schema metadata alone can create a numeric floor.
- Move the rule between tool description, user prompt, both, and neither to separate tool-metadata effects from ordinary prompt instruction following.
- Compare no-word baselines to vague-word prompts to ask whether words add signal beyond the interface-induced default.

## What This Is And Is Not

This is a tool-use evaluation paper, not a claim that tools mechanically enforce constraints.

Correct framing:

> Do tool-interface choices change the numeric actions emitted by LLM tool calls?

Your proposed framing is mostly right, with two corrections:

- **Prompt vs schema alignment:** yes, the experiments ask whether the prompt, schema, or both are more behaviorally active. But the current results are model-specific; do not claim that schema always wins.
- **Defaults and sibling parameters:** yes, the broader harness supports defaults, required sibling fields, parameter names, and order. The packaged clean-core focuses on the strongest five mechanism tests; the wider local project has more confounder runs.
- **Baseline/no-word vs words:** yes. The no-word condition is important because it tells us whether a vague word actually moves the model away from its default increase behavior.
- **Downstream impacts:** the clean-core experiment measures immediate numeric tool-call outputs. Downstream impact is a motivation and paper implication, not directly measured here unless we add a downstream simulator.

## Current Status

Included:

- Config-driven Python runner.
- Clean-core experiment configs.
- PowerShell launch script.
- Progress snapshot script.
- Summary CSVs from local clean-core runs.
- A summary-results notebook that works from committed summary CSVs.

Not included:

- Raw JSONL records.
- Logs.
- Old exploratory config menu.
- Old docs, session handoffs, and draft paper notes.

## Code Map

| Path | Purpose |
| --- | --- |
| `src/clean_layer2.py` | Main experiment runner. Expands a config, calls models, records raw tool arguments, and exports CSV/summary files. |
| `src/config_loader.py` | Loads JSON configs and computes config hashes. |
| `src/registry.py` | Defines model keys, word sets, conditions, prompt templates, state variants, schema variants, and tool metadata. |
| `src/records.py` | Expands experiment matrices and builds per-run records with diagnostic fields. |
| `src/llm_client.py` | OpenAI-compatible client wrapper used for local Ollama model calls. |
| `src/analysis.py` | Exports flat CSVs and grouped summary CSVs from JSONL outputs. |
| `scripts/run_clean_core_v2.ps1` | Runs the five clean-core configs across selected models. |
| `scripts/progress_snapshot.py` | Computes resume-aware progress for the packaged clean-core manifest. |
| `configs/clean_core/manifest_v2.json` | Defines the clean-core launch/read order. |
| `results/summary/` | Curated summary CSVs committed for review. |
| `notebooks/clean_core_summary_analysis.ipynb` | Lightweight notebook that reads summary CSVs only. |

## Experiment Design

Each run gives the model a prompt and a tool schema. The model emits a tool call with numeric arguments, usually `a`, `b`, and `c`. The harness records raw arguments and computes diagnostics afterward.

Important design rule:

> The runner does not repair outputs. It does not clip values, enforce feasibility, or fill missing fields. Invalid outputs are data.

The target argument is `c`. The surrounding interface may include:

- current values for `a`, `b`, and `c`,
- a written threshold rule, `a + b + c >= 1.0`,
- schema ranges such as `a <= .43` and `b <= .18`,
- different rule locations, such as tool description versus user prompt.

## Clean-Core Experiment Types

The clean-core package preserves five experiment types. Each has one config file and one result summary file.

### 1. Total Requirement Changes C

Config: `configs/clean_core/clean_core_threshold_boundary_v2.json`

Summary: `results/summary/clean_core_threshold_boundary_v2_summary.csv`

Question:

> Does adding the written total-at-least-1.0 requirement change `c` compared with the same prompt without that requirement?

Example:

```text
Current values: a=0.31, b=0.23, c=0.36. Only change c. Slightly increase c.
```

Since `1.0 - .31 - .23 = .46`, a threshold-aware output should move `c` to at least `.46`, while keeping `a` and `b` unchanged.

Primary metrics:

- `c_output`
- `threshold_valid_rate`
- `strict_only_c_rate`
- `c_floor_gap_context`

### 2. Required C Minimum Moves

Config: `configs/clean_core/clean_core_floor_gradient_v2.json`

Summary: `results/summary/clean_core_floor_gradient_v2_summary.csv`

Question:

> When the minimum required `c` changes from `.31` to `.46` to `.61`, does the model's chosen `c` move with it?

The current `a` and `b` values change:

```text
a=.41, b=.28 -> minimum c=.31
a=.31, b=.23 -> minimum c=.46
a=.22, b=.17 -> minimum c=.61
```

The strongest evidence is monotonic movement in median `c_output` as the floor rises.

### 3. Prompt Values vs Tool Schema

Config: `configs/clean_core/clean_core_mechanism_split_v2.json`

Summary: `results/summary/clean_core_mechanism_split_v2_summary.csv`

Question:

> If prompt-visible current values and tool schema ranges imply different `c` floors, which source does the model follow?

Clean split:

```text
Prompt-visible current values: a=.24, b=.16 -> prompt floor=.60
Tool schema ranges: a<=.43, b<=.18 -> schema floor=.39
```

Outputs near `.60` suggest prompt-visible arithmetic. Outputs near `.39` suggest schema-bound behavior. Outputs elsewhere mean the mechanism is unclear.

### 4. Tool Schema Alone

Config: `configs/clean_core/clean_core_schema_only_v2.json`

Summary: `results/summary/clean_core_schema_only_v2_summary.csv`

Question:

> Without prompt-visible current values, can schema ranges plus the written total rule create a visible `c` floor?

The clean schema-floor signal is `.39` appearing mainly when tight ranges and the total rule are both present.

### 5. Rule Location

Config: `configs/clean_core/clean_core_rule_location_v2.json`

Summary: `results/summary/clean_core_rule_location_v2_summary.csv`

Question:

> Does the model behave differently when the total rule is written in the tool description, the user prompt, both places, or neither place?

Interpretation:

- Tool-description-only works: evidence that tool metadata affects numeric action.
- User-prompt-only works: evidence mostly ordinary prompt instruction following.
- Both works best: salience or repetition may matter.
- Neither works: likely numeric anchoring or baseline behavior.

## Existing Results

The high-level readout file is:

```text
results/summary/clean_core_signal_summary.csv
```

Current summary:

- The moving-floor effect is visible across the three primary local models.
- Schema-only effects are model-specific and should be framed cautiously.
- Rule-location behavior includes abstentions in some cells, so those cells need careful interpretation.

A safe current claim is:

> Numeric interface structure changes tool-call arguments, but the source of the effect differs by model and condition.

Do not overclaim that all models use schema ranges.

## Inspecting Results

Open the summary notebook:

```powershell
cd experiments\numeric-tool-interface
jupyter notebook notebooks\clean_core_summary_analysis.ipynb
```

The notebook reads committed files under `results/summary/` and does not require raw JSONL outputs.

## Running The Experiments

Install dependencies:

```powershell
cd experiments\numeric-tool-interface
pip install -r requirements.txt
```

Dry run one config:

```powershell
python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --dry-run --model qwen3-8b --runs 1
```

Run one config:

```powershell
python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --model qwen3-8b --runs 1
```

Run the clean-core menu:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_clean_core_v2.ps1 -Models qwen3-8b,llama3-8b,gemma4-12b -Runs 1
```

Generate a progress snapshot:

```powershell
python scripts\progress_snapshot.py
```

## Model Requirements

The default model keys assume a local OpenAI-compatible Ollama endpoint:

```text
http://localhost:11434/v1
```

Default model keys are defined in `src/registry.py`, including:

- `qwen3-8b`
- `llama3-8b`
- `gemma4-12b`

If your local model names differ, edit `MODELS` in `src/registry.py`.

## Limitations

- The experiments are synthetic micro-tasks.
- Ollama-style tool calling is soft schema exposure, not hard constrained decoding.
- Small open-weight models may not match frontier model behavior.
- Current summaries are preliminary local readouts, not a final frozen paper artifact.
- Full raw outputs are not committed to this repository.
- Downstream impacts are not directly simulated in this clean-core package.