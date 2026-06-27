# Numeric Tool-Interface Semantics

## Research Question

Do numeric tool interfaces change how language models convert vague instructions such as "slightly increase c" into concrete tool-call arguments?

The core claim being tested is:

> Tool schemas are not neutral measurement instruments. Numeric state, sibling fields, schema ranges, and relational rules can change the numeric value emitted by an LLM tool call.

This package contains the clean-core version of the experiment. It is designed to avoid earlier mechanism-confounded setups where prompt-visible values and schema ranges predicted the same output.

## Current Status

Included:

- Config-driven Python runner.
- Clean-core experiment configs.
- PowerShell launch script.
- Progress snapshot script.
- Summary CSVs from local clean-core runs.

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
| `results/summary/` | Curated summary CSVs. These are small enough for GitHub and useful for team review. |

## Experiment Design

Each run gives the model a prompt and a tool schema. The model emits a tool call with numeric arguments, usually `a`, `b`, and `c`. The harness records the raw arguments and computes diagnostics afterward.

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

Config:

```text
configs/clean_core/clean_core_threshold_boundary_v2.json
```

Summary:

```text
results/summary/clean_core_threshold_boundary_v2_summary.csv
```

Question:

> Does adding the written total-at-least-1.0 requirement change `c` compared with the same prompt without that requirement?

Example pair:

```text
Current values: a=0.31, b=0.23, c=0.36. Only change c. Slightly increase c.
```

Without total rule, this is a normal increase request. With the total rule, the model is also told:

```text
The total of a, b, and c should be greater than or equal to 1.0.
```

Since `1.0 - .31 - .23 = .46`, a threshold-aware output should move `c` to at least `.46`, while still keeping `a` and `b` unchanged.

Primary metrics:

- `c_output`
- `threshold_valid_rate`
- `strict_only_c_rate`
- `c_floor_gap_context`

### 2. Required C Minimum Moves

Config:

```text
configs/clean_core/clean_core_floor_gradient_v2.json
```

Summary:

```text
results/summary/clean_core_floor_gradient_v2_summary.csv
```

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

Config:

```text
configs/clean_core/clean_core_mechanism_split_v2.json
```

Summary:

```text
results/summary/clean_core_mechanism_split_v2_summary.csv
```

Question:

> If prompt-visible current values and tool schema ranges imply different `c` floors, which source does the model follow?

This is the clean mechanism split:

```text
Prompt-visible current values: a=.24, b=.16 -> prompt floor=.60
Tool schema ranges: a<=.43, b<=.18 -> schema floor=.39
```

Outputs near `.60` suggest prompt-visible arithmetic. Outputs near `.39` suggest schema-bound behavior. Outputs elsewhere mean the mechanism is unclear.

### 4. Tool Schema Alone

Config:

```text
configs/clean_core/clean_core_schema_only_v2.json
```

Summary:

```text
results/summary/clean_core_schema_only_v2_summary.csv
```

Question:

> Without prompt-visible current values, can schema ranges plus the written total rule create a visible `c` floor?

The three key cases are:

| Case | Tool ranges | Total rule |
| --- | --- | --- |
| Open schema threshold | `a,b,c` in `[0,1]` | Present |
| Tight schema no-rule | `a<=.43`, `b<=.18` | Absent |
| Tight schema threshold | `a<=.43`, `b<=.18` | Present |

The clean schema-floor signal is `.39` appearing mainly when tight ranges and the total rule are both present.

### 5. Rule Location

Config:

```text
configs/clean_core/clean_core_rule_location_v2.json
```

Summary:

```text
results/summary/clean_core_rule_location_v2_summary.csv
```

Question:

> Does the model behave differently when the total rule is written in the tool description, the user prompt, both places, or neither place?

This separates ordinary prompt instruction following from tool-metadata sensitivity.

Interpretation:

- Tool-description-only works: evidence that tool metadata affects numeric action.
- User-prompt-only works: evidence mostly ordinary prompt instruction following.
- Both works best: salience or repetition may matter.
- Neither works: likely numeric anchoring or baseline behavior.

## Summary Readout

The high-level readout file is:

```text
results/summary/clean_core_signal_summary.csv
```

Current local summary:

- The moving-floor effect is visible across the three primary local models.
- Schema-only effects are model-specific and should be framed cautiously.
- Rule-location behavior includes abstentions in some cells, so those cells need careful interpretation.

Do not overclaim that all models use schema ranges. A safer claim is:

> The clean-core results show that numeric interface structure can change tool-call arguments, but the source of the effect differs by model and condition.

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

## Output Files

Live runs write:

```text
results/raw/*.jsonl
results/raw/*.csv
results/summary/*_summary.csv
logs/
```

This repository ignores raw outputs and logs by default. Summary CSVs are kept because they are compact and useful for review.

## Limitations

- The experiments are synthetic micro-tasks.
- Ollama-style tool calling is soft schema exposure, not hard constrained decoding.
- Small open-weight models may not match frontier model behavior.
- Current summaries are preliminary local readouts, not a final frozen paper artifact.
- Full raw outputs are not committed to this repository.

