# Numeric Tool Interfaces As Behavioral Interventions

Difficulty: **Easy-Medium**

Compute Budget: **Low** for local 8B-12B models; **Low-Medium** with frontier-model replication.

## Overview

Structured tools are often treated as neutral interfaces: the user states an intent, the model selects a tool, and the schema records the action. This experiment tests a narrower possibility: the schema and surrounding numeric context may themselves change the action.

The target behavior is a numeric tool-call argument, `c_output`, emitted in response to requests such as:

```text
Current values: a=0.31, b=0.23, c=0.36. Only change c. Slightly increase c.
```

The experiment varies the tool interface while holding the task small enough to interpret:

- whether a total rule is present,
- where that rule is written,
- whether prompt-visible values or schema ranges imply the relevant floor,
- whether parameter order changes outputs,
- whether required sibling parameters cause unwanted edits to `a` or `b`,
- whether schema defaults pull outputs toward a default state,
- whether vague words move the output beyond a no-word baseline.

Core question:

> When an LLM emits a numeric tool-call argument, how much of that number comes from the user instruction, and how much comes from the tool interface?

## Concrete Examples

### Example 1: Tool-Order Sensitivity

Same prompt, same fields, different schema order:

```text
Condition A schema order: a, b, c
Condition B schema order: c, a, b
Prompt: Current values are a=.31, b=.23, c=.36. Only change c. Slightly increase c.
```

Measurement:

- Does `c_output` shift under `a,b,c` vs another order such as `c,a,b` or `c,b,a`?
- Does the model touch `a` or `b` more often under one order?
- Does the first or last field act like an implicit anchor?

Relevant committed file:

```text
results/summary/extended/experiment_i_parameter_order_control_v1_summary.csv
```

The copied pilot includes `abc`, `bac`, and `cab`. A `cba` condition can be added by listing `['c', 'b', 'a']` in a config.

### Example 2: Constraint Location

Same mathematical rule, different text location:

```text
Rule absent
Rule in user prompt only
Rule in tool description only
Rule in both places
```

The rule is:

```text
a+b+c >= 1.0
```

Measurement:

- Does the model increase `c` enough to satisfy the rule?
- Is a rule in tool metadata as effective as a rule in the user prompt?
- Does duplicating the rule in both places strengthen the effect?

Relevant committed files:

```text
results/summary/clean_core_threshold_boundary_v2_summary.csv
results/summary/clean_core_rule_location_v2_summary.csv
results/summary/extended/experiment_h_prompt_placement_ablation_v1_summary.csv
```

### Example 3: Prompt State vs Schema State

Prompt-visible values and schema bounds can imply different minimum feasible values for `c`:

```text
Prompt-visible values: a=.24, b=.16, c=.36
Prompt-implied floor: c >= .60

Schema bounds: a<=.43, b<=.18
Schema-implied floor: c >= .39
```

Measurement:

- Outputs near `.60` suggest prompt-state arithmetic.
- Outputs near `.39` suggest schema-bound behavior.
- Outputs near the no-rule baseline suggest the constraint is not controlling the call.

Relevant committed files:

```text
results/summary/clean_core_mechanism_split_v2_summary.csv
results/summary/clean_core_schema_only_v2_summary.csv
results/summary/extended/experiment_f_schema_bound_threshold_v1_summary.csv
results/summary/extended/mechanism_identification_v1_light_summary.csv
```

### Example 4: Schema Defaults And Sibling Parameters

A tool schema can expose defaults or require sibling fields even when the instruction says only `c` should change.

```text
Prompt: Only change c. Increase c.
Tool requires: a, b, c
Schema defaults: a=.31, b=.23, c=.36
```

Measurement:

- Does the model preserve `a` and `b`?
- Do defaults pull the output toward a baseline even when the prompt implies a different value?
- Does requiring all three fields increase sibling-parameter leakage?

Relevant committed files:

```text
results/summary/extended/confounder_state_representation_v1_summary.csv
results/summary/extended/confounder_bare_knob_bridge_v1_summary.csv
results/summary/extended/experiment_g_conservation_stress_v1_summary.csv
results/summary/extended/experiment_l_full_baseline_grid_v1_summary.csv
```

### Example 5: Words Over No-Word Baselines

A no-word baseline is needed because models may increase `c` by default even without modifiers.

```text
No-word: Increase c.
Vague-word: Slightly increase c.
Vague-word: Moderately increase c.
Vague-word: Substantially increase c.
```

Measurement:

- Does each word move `c_output` relative to the no-word baseline?
- Are word effects stable across models?
- Do word effects survive when schema bounds or total constraints are present?

Relevant committed files:

```text
results/summary/extended/experiment_b_independent_baseline_v1_summary.csv
results/summary/extended/experiment_k_full_word_scale_v1_summary.csv
results/summary/extended/experiment_j_exact_instruction_control_v1_summary.csv
```

## Hypotheses

1. Adding a written relational rule such as `a+b+c >= 1.0` changes `c_output` relative to a matched no-rule interface.
2. If the required minimum for `c` moves, model outputs move with it.
3. Prompt-visible current values and tool-schema ranges can compete as sources of numeric behavior.
4. Rule placement matters: a rule in the user prompt may not behave the same as a rule in the tool description.
5. Parameter order, defaults, and required sibling fields can shift outputs even when the apparent task is unchanged.
6. No-word baselines are necessary because models may have default increase policies even without vague modifiers.

## Package Contents

| Path | Purpose |
| --- | --- |
| `src/clean_layer2.py` | Main runner. Expands configs, calls models, records raw tool arguments, and exports summaries. |
| `src/registry.py` | Model keys, word sets, conditions, prompt templates, schema variants, and tool metadata. |
| `src/records.py` | Experiment-matrix expansion and per-run diagnostic record construction. |
| `src/llm_client.py` | OpenAI-compatible client wrapper for local Ollama model calls. |
| `src/analysis.py` | CSV and grouped summary export. |
| `configs/clean_core/` | Five clean-core experiment configs plus manifest. |
| `results/summary/` | Clean-core summary CSVs from local runs. |
| `results/summary/extended/` | Additional summary CSVs from earlier experiment families. |
| `notebooks/clean_core_summary_analysis.ipynb` | Notebook for inspecting committed clean-core summary CSVs without raw JSONL outputs. |
| `scripts/run_clean_core_v2.ps1` | Runs all clean-core configs across selected models. |
| `Dockerfile`, `docker-compose.yml` | Reproducible Python environment for running the package. |

Raw JSONL outputs and logs are intentionally not committed.

## Clean-Core Experiments

### 1. Total Requirement Changes C

Config: `configs/clean_core/clean_core_threshold_boundary_v2.json`

Question:

> Does adding `a+b+c >= 1.0` change `c` relative to a matched no-rule condition?

Example:

```text
a=0.31, b=0.23, c=0.36
minimum c for a+b+c >= 1.0 is 0.46
```

A threshold-sensitive model should move `c` toward or above `.46` while preserving `a` and `b`.

### 2. Required C Minimum Moves

Config: `configs/clean_core/clean_core_floor_gradient_v2.json`

Question:

> Does `c_output` rise as the required floor moves from `.31` to `.46` to `.61`?

This tests whether the model follows the boundary `c_required = 1-a-b`, rather than emitting the same habitual value regardless of context.

### 3. Prompt Values vs Tool Schema

Config: `configs/clean_core/clean_core_mechanism_split_v2.json`

Question:

> When prompt-visible values and schema ranges imply different floors, which source does the model follow?

Clean split:

```text
Prompt-visible values: a=.24, b=.16 -> prompt floor=.60
Schema ranges: a<=.43, b<=.18 -> schema floor=.39
```

Outputs near `.60` suggest prompt-state arithmetic. Outputs near `.39` suggest schema-bound behavior.

### 4. Tool Schema Alone

Config: `configs/clean_core/clean_core_schema_only_v2.json`

Question:

> Without prompt-visible current values, can schema ranges plus the total rule create a visible `c` floor?

The main signal is `.39` appearing primarily when tight schema ranges and the total rule are both present.

### 5. Rule Location

Config: `configs/clean_core/clean_core_rule_location_v2.json`

Question:

> Does behavior change when the same rule is written in the tool description, the user prompt, both places, or neither place?

This separates tool-metadata effects from ordinary prompt instruction following.

## Current Evidence

The high-level readout is:

```text
results/summary/clean_core_signal_summary.csv
```

Current summary:

- The moving-floor effect appears across the three primary local models.
- The total-rule effect is model-dependent.
- Schema-only behavior is model-specific and should not be overgeneralized.
- Rule-location cells include abstentions for some models, so tool-call rate must be interpreted alongside numeric outputs.
- Extended summaries preserve additional evidence on parameter order, schema defaults, prompt placement, sibling-parameter leakage, wording, and confounder checks.
- The copied parameter-order pilot shows small model-specific shifts in median `c_output`; this is pilot evidence rather than a complete permutation claim.
- The conservation-stress summary shows strict-only-`c` rates below 1.0 in several model/condition groups, so sibling-parameter leakage is an observed measurement target.

Current safe claim:

> Numeric interface structure can change emitted tool-call arguments, but the source and strength of the effect vary by model and condition.

## Result Files

Clean-core result files:

```text
results/summary/clean_core_signal_summary.csv
results/summary/clean_core_threshold_boundary_v2_summary.csv
results/summary/clean_core_floor_gradient_v2_summary.csv
results/summary/clean_core_mechanism_split_v2_summary.csv
results/summary/clean_core_schema_only_v2_summary.csv
results/summary/clean_core_rule_location_v2_summary.csv
```

Extended result files:

```text
results/summary/extended/confounder_bare_knob_bridge_v1_summary.csv
results/summary/extended/confounder_parameter_descriptions_v1_summary.csv
results/summary/extended/confounder_rule_wording_v1_summary.csv
results/summary/extended/confounder_state_representation_v1_summary.csv
results/summary/extended/confounder_tool_parameter_naming_v1_summary.csv
results/summary/extended/experiment_b_independent_baseline_v1_summary.csv
results/summary/extended/experiment_d_threshold_ab_gradient_v1_summary.csv
results/summary/extended/experiment_e_threshold_no_rule_control_v1_summary.csv
results/summary/extended/experiment_f_schema_bound_threshold_v1_summary.csv
results/summary/extended/experiment_g_conservation_stress_v1_summary.csv
results/summary/extended/experiment_h_prompt_placement_ablation_v1_summary.csv
results/summary/extended/experiment_i_parameter_order_control_v1_summary.csv
results/summary/extended/experiment_j_exact_instruction_control_v1_summary.csv
results/summary/extended/experiment_k_full_word_scale_v1_summary.csv
results/summary/extended/experiment_l_full_baseline_grid_v1_summary.csv
results/summary/extended/mechanism_identification_v1_light_summary.csv
results/summary/extended/threshold_boundary_v1_light_summary.csv
```

## Inspecting Results

Open the summary notebook:

```powershell
cd experiments\numeric-tool-interface
jupyter notebook notebooks\clean_core_summary_analysis.ipynb
```

The notebook reads committed files under `results/summary/` and does not require raw JSONL outputs.

To inspect CSVs directly:

```powershell
Get-ChildItem results\summary -Recurse -Filter *.csv
Import-Csv results\summary\clean_core_signal_summary.csv | Format-Table
```

## Running Without Docker

Install dependencies:

```powershell
cd experiments\numeric-tool-interface
pip install -r requirements.txt
```

Dry run one config:

```powershell
python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --dry-run --model qwen3-8b --runs 1
```

Run one small live batch:

```powershell
python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --model qwen3-8b --runs 1 --limit 5
```

Run the full clean-core menu for selected models:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_clean_core_v2.ps1 -Models qwen3-8b,llama3-8b,gemma4-12b -Runs 1
```

## Running With Docker

Docker runs the experiment code in a reproducible Python environment. Ollama usually remains outside Docker on the host machine.

Build:

```powershell
cd experiments\numeric-tool-interface
docker compose build
```

Dry run:

```powershell
docker compose run --rm experiment python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --dry-run --model qwen3-8b --runs 1
```

Live run:

```powershell
docker compose run --rm experiment python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --model qwen3-8b --runs 1 --limit 5
```

Before live model calls, make sure Ollama is running on the host and the model exists:

```powershell
ollama pull qwen3:8b
ollama serve
```

### `OLLAMA_BASE_URL`

The model registry reads one environment variable:

```text
OLLAMA_BASE_URL
```

Outside Docker, the default is:

```text
http://localhost:11434/v1
```

Inside Docker, `localhost` means the container. The compose file therefore sets:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
```

This tells the container to call Ollama running on the host machine.

## Reproducibility Boundary

Docker freezes the Python environment, code, configs, and commands. It does not freeze the external model runtime. Live outputs can still vary with:

- Ollama version,
- model tag or quantization,
- hardware,
- nondeterminism in local inference.

For paper artifacts, archive full raw outputs separately and cite a repo commit or release tag.

## Limitations

- The experiments are synthetic micro-tasks.
- Ollama-style tool calling is soft schema exposure, not hard constrained decoding.
- Small open-weight models may not match frontier model behavior.
- Current summaries are preliminary local readouts, not final paper artifacts.
- Downstream impacts are motivation, not directly simulated in this package.
