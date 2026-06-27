# Numeric Tool-Interface Experiment Menu

This is the dense reference for the numeric tool-interface project. It lists the experiment families that have been tested so far, where their configs live, where committed summary results live, and how each experiment should be interpreted.

The short version: start with the clean-core v2 menu for the main research story, then use the legacy and confounder menu for continuity, robustness checks, and expansion evidence.

## How The Testbed Works

Each experiment asks a model to emit a structured tool call with numeric fields such as `a`, `b`, and `c`. The apparent user task is usually simple:

```text
Current values: a=0.31, b=0.23, c=0.36. Only change c. Slightly increase c.
```

The experiment changes the interface around that task:

- the tool description,
- the presence or absence of a rule such as `a+b+c >= 1.0`,
- where that rule appears,
- schema bounds and defaults,
- field requiredness,
- parameter order,
- parameter names,
- parameter descriptions,
- prompt wording,
- baseline `c` values.

The dependent variable is the emitted tool-call behavior: `c_output`, whether `a` and `b` are preserved, whether the total satisfies the rule, whether the model abstains, and whether outputs track prompt-visible values or schema-implied values.

## Where Things Live

| Item | Path |
| --- | --- |
| Main runner | `src/clean_layer2.py` |
| Model registry, words, condition definitions, schema variants | `src/registry.py` |
| Experiment expansion and per-run diagnostics | `src/records.py` |
| Summary export | `src/analysis.py` |
| Primary clean-core configs | `configs/clean_core/` |
| Historical and extended configs | `configs/legacy/` |
| Clean-core summaries | `results/summary/` |
| Historical and extended summaries | `results/summary/extended/` |
| Analysis notebook | `notebooks/clean_core_summary_analysis.ipynb` |

Run any config with:

```powershell
python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --dry-run --model qwen3-8b --runs 1
```

For a historical config:

```powershell
python src\clean_layer2.py --config configs\legacy\experiment_i_parameter_order_control_v1.json --dry-run --model qwen3-8b --runs 1
```

## Recommended Reading Order

1. **Clean-core v2:** the five primary configs in `configs/clean_core/`. These are the clearest first-readout experiments.
2. **Legacy mechanism and threshold checks:** `mechanism_identification_v1_light`, `threshold_boundary_v1_light`, and experiments B-F.
3. **Conflict and confounders:** equality stress, rule location, field order, names, descriptions, wording, and bare-c bridge.
4. **Expansion sweeps:** exact instruction, full word scale, and full baseline grid.

The legacy `.50/.15 -> .35` cells are useful for continuity, but they should not be the first mechanism readout because prompt arithmetic and schema-bound propagation can both predict `.35` there. Clean-core v2 avoids that ambiguity.

## Clean-Core V2 Menu

These are the primary experiments to explain first.

| Order | Batch ID | Question | Main Manipulation | Config | Summary |
| ---: | --- | --- | --- | --- | --- |
| 1 | `clean_core_threshold_boundary_v2` | Does adding `a+b+c >= 1.0` change `c` relative to the same prompt without the rule? | `no_rule` vs `threshold_gte_1` across floors `.31`, `.46`, `.61` | `configs/clean_core/clean_core_threshold_boundary_v2.json` | `results/summary/clean_core_threshold_boundary_v2_summary.csv` |
| 2 | `clean_core_floor_gradient_v2` | Does `c_output` rise as the required minimum `c` rises? | Threshold rule only; floor moves `.31 -> .46 -> .61` | `configs/clean_core/clean_core_floor_gradient_v2.json` | `results/summary/clean_core_floor_gradient_v2_summary.csv` |
| 3 | `clean_core_mechanism_split_v2` | When prompt values and schema ranges imply different floors, which source does the model follow? | Prompt floor `.60` vs schema floor `.39` | `configs/clean_core/clean_core_mechanism_split_v2.json` | `results/summary/clean_core_mechanism_split_v2_summary.csv` |
| 4 | `clean_core_schema_only_v2` | Without prompt-visible state, can schema ranges plus the rule create a visible `c` floor? | Open schema, tight schema only, tight schema plus rule | `configs/clean_core/clean_core_schema_only_v2.json` | `results/summary/clean_core_schema_only_v2_summary.csv` |
| 5 | `clean_core_rule_location_v2` | Does rule placement matter? | Rule in tool description, user prompt, both, or neither | `configs/clean_core/clean_core_rule_location_v2.json` | `results/summary/clean_core_rule_location_v2_summary.csv` |

High-level clean-core summary:

```text
results/summary/clean_core_signal_summary.csv
```

## Clean-Core Examples

### Clean 1: Total Requirement Changes C

Matched pair:

```text
No rule:
Current values: a=0.31, b=0.23, c=0.36. Only change c. Slightly increase c.
Tool description: Set numeric values for a, b, and c.

With rule:
Current values: a=0.31, b=0.23, c=0.36. Only change c. Slightly increase c.
Tool description: Set numeric values for a, b, and c. The total of a, b, and c should be greater than or equal to 1.0.
```

For `a=.31,b=.23`, the minimum feasible `c` is `.46`. The key comparison is whether the rule condition moves `c_output` toward or above `.46` more often than the no-rule condition.

### Clean 3: Prompt State vs Schema State

The mechanism split intentionally makes two sources disagree:

```text
Prompt-visible values: a=.24, b=.16 -> prompt floor c>=.60
Schema bounds: a<=.43, b<=.18 -> schema floor c>=.39
```

Outputs near `.60` suggest prompt-state arithmetic. Outputs near `.39` suggest schema-bound behavior. Outputs near neither value mean the mechanism is unclear.

## Historical And Extended Menu

These experiments are preserved in `configs/legacy/`. Their committed summaries are under `results/summary/extended/`.

| Order | Batch ID | Role | Main Question | Config | Summary |
| ---: | --- | --- | --- | --- | --- |
| A | `phase0_calibration` | Smoke test | Does tool calling, parsing, normalization, and CSV export work? | `configs/legacy/phase0_calibration.json` | `results/summary/extended/phase0_calibration_summary.csv` |
| State | `confounder_state_representation_v1` | State-source diagnostic | Does behavior depend on prompt state, schema defaults, optional fields, or no state? | `configs/legacy/confounder_state_representation_v1.json` | `results/summary/extended/confounder_state_representation_v1_summary.csv` |
| Mechanism | `mechanism_identification_v1_light` | Schema-vs-prompt diagnostic | When prompt arithmetic and schema bounds imply different floors, which source does the model follow? | `configs/legacy/mechanism_identification_v1_light.json` | `results/summary/extended/mechanism_identification_v1_light_summary.csv` |
| C | `threshold_boundary_v1_light` | Boundary calibration | Does adding `a+b+c >= 1.0` change `c` around the required boundary? | `configs/legacy/threshold_boundary_v1_light.json` | `results/summary/extended/threshold_boundary_v1_light_summary.csv` |
| B | `experiment_b_independent_baseline_v1` | No-rule baseline | What does a three-parameter tool do without a relational rule? | `configs/legacy/experiment_b_independent_baseline_v1.json` | `results/summary/extended/experiment_b_independent_baseline_v1_summary.csv` |
| E | `experiment_e_threshold_no_rule_control_v1` | Matched threshold control | Is the threshold rule doing anything beyond showing the same numbers? | `configs/legacy/experiment_e_threshold_no_rule_control_v1.json` | `results/summary/extended/experiment_e_threshold_no_rule_control_v1_summary.csv` |
| D | `experiment_d_threshold_ab_gradient_v1` | Moving-boundary test | Does `c` track `1-a-b` as `a` and `b` change? | `configs/legacy/experiment_d_threshold_ab_gradient_v1.json` | `results/summary/extended/experiment_d_threshold_ab_gradient_v1_summary.csv` |
| F | `experiment_f_schema_bound_threshold_v1` | Schema-bound mechanism | Can tight schema bounds plus the threshold rule create a `.35` floor without prompt state? | `configs/legacy/experiment_f_schema_bound_threshold_v1.json` | `results/summary/extended/experiment_f_schema_bound_threshold_v1_summary.csv` |
| G | `experiment_g_conservation_stress_v1` | Equality conflict | When `a+b+c = 1.0` conflicts with â€œonly change câ€, what does the model sacrifice? | `configs/legacy/experiment_g_conservation_stress_v1.json` | `results/summary/extended/experiment_g_conservation_stress_v1_summary.csv` |
| H | `experiment_h_prompt_placement_ablation_v1` | Rule-location check | Does the rule behave differently in tool metadata, prompt text, both, or neither? | `configs/legacy/experiment_h_prompt_placement_ablation_v1.json` | `results/summary/extended/experiment_h_prompt_placement_ablation_v1_summary.csv` |
| I | `experiment_i_parameter_order_control_v1` | Field-order check | Does field order change `c_output` or sibling movement? | `configs/legacy/experiment_i_parameter_order_control_v1.json` | `results/summary/extended/experiment_i_parameter_order_control_v1_summary.csv` |
| J | `experiment_j_exact_instruction_control_v1` | Exact-instruction control | Do interface effects persist when the instruction is exact instead of vague? | `configs/legacy/experiment_j_exact_instruction_control_v1.json` | `results/summary/extended/experiment_j_exact_instruction_control_v1_summary.csv` |
| K | `experiment_k_full_word_scale_v1` | Word-scale expansion | Does the full vague-word scale interact with no-rule versus threshold contexts? | `configs/legacy/experiment_k_full_word_scale_v1.json` | `results/summary/extended/experiment_k_full_word_scale_v1_summary.csv` |
| L | `experiment_l_full_baseline_grid_v1` | Baseline-grid expansion | Does behavior hold across the original baseline grid rather than selected boundary cells? | `configs/legacy/experiment_l_full_baseline_grid_v1.json` | `results/summary/extended/experiment_l_full_baseline_grid_v1_summary.csv` |
| Name | `confounder_tool_parameter_naming_v1` | Naming confounder | Do tool names or parameter names drive the effect? | `configs/legacy/confounder_tool_parameter_naming_v1.json` | `results/summary/extended/confounder_tool_parameter_naming_v1_summary.csv` |
| Description | `confounder_parameter_descriptions_v1` | Description confounder | Do parameter descriptions smuggle anchors or instructions? | `configs/legacy/confounder_parameter_descriptions_v1.json` | `results/summary/extended/confounder_parameter_descriptions_v1_summary.csv` |
| Wording | `confounder_rule_wording_v1` | Rule-wording confounder | Does stronger, softer, or symbolic wording change compliance? | `configs/legacy/confounder_rule_wording_v1.json` | `results/summary/extended/confounder_rule_wording_v1_summary.csv` |
| Bare-c | `confounder_bare_knob_bridge_v1` | Protocol bridge | How does `set_c(c)` compare with `set_values(a,b,c)`? | `configs/legacy/confounder_bare_knob_bridge_v1.json` | `results/summary/extended/confounder_bare_knob_bridge_v1_summary.csv` |

## What Each Historical Experiment Tested

### A. Calibration

Purpose: verify the machinery before treating outputs as scientific evidence.

Readout: tool-call rate, parse errors, schema validity, missing fields, and whether summaries export correctly.

Guardrail: calibration is not evidence for threshold behavior.

### State Source Diagnostic

Purpose: test whether the model behaves differently when the same conceptual state is shown in the prompt, embedded as schema defaults, made optional, or hidden.

Readout: compare `c_output`, `strict_only_c_rate`, and `mean_sibling_change_l1` across `state_variant`.

Guardrail: this uses older aligned contexts; treat it as state-representation evidence, not the cleanest schema-bound proof.

### Mechanism ID

Purpose: separate prompt-state arithmetic from schema-bound propagation.

Readout: compare outputs when the prompt floor and schema floor disagree.

Guardrail: aligned cells are calibration only. Divergent and schema-only cells carry the mechanism signal.

### B. No-Rule Baseline

Purpose: measure what the model does with a multi-parameter tool when there is no relational constraint.

Readout: baseline `c_output`, `median_delta_c`, and unnecessary sibling movement.

Guardrail: threshold or schema effects need to exceed this baseline to be compelling.

### C/D/E/F. Threshold And Schema Mechanism Tests

Purpose: test threshold behavior from multiple angles.

- C asks whether the threshold changes behavior near a boundary.
- D asks whether the boundary moves with `1-a-b`.
- E compares matched no-rule and threshold conditions.
- F removes prompt state and tests whether schema bounds plus rule text can create a schema-implied floor.

Readout: `threshold_valid_rate`, `median_c_output`, `median_delta_c`, and floor gaps.

Guardrail: C/D/E mostly speak to prompt/current-state threshold behavior. F is closer to schema-bound behavior.

### G. Equality Stress

Purpose: create a conflict between exact equality and â€œonly change câ€.

Readout: `equality_valid_rate`, `strict_only_c_rate`, `mean_sibling_change_l1`, and abstentions.

Guardrail: sibling changes under equality may be constraint repair rather than ordinary leakage.

### H/I. Placement And Order Checks

Purpose: test whether interface layout changes behavior.

- H varies where the same rule appears: tool description, user prompt, both, neither.
- I varies parameter order under threshold and equality conditions.

Readout: compare `median_c_output`, validity rates, and sibling movement by `rule_location` or `parameter_order_id`.

Guardrail: current order pilot includes `abc`, `bac`, and `cab`; `cba` can be added by editing the config with the same runner.

### J/K/L. Instruction And Grid Expansions

Purpose: broaden the behavioral characterization after the core mechanism tests.

- J uses exact numeric instructions instead of vague words.
- K expands the vague-word scale.
- L expands across the original baseline grid.

Readout: compare word-level medians, monotonicity, compression, and baseline dependence.

Guardrail: these are expansion and characterization batches, not the first-pass mechanism proof.

### Naming, Description, Wording, And Bare-c Confounders

Purpose: test whether apparent effects are driven by superficial interface choices.

Readout:

- Names: compare tool and parameter naming variants.
- Descriptions: compare no descriptions, neutral descriptions, and default-anchor descriptions.
- Wording: compare default, soft, must, and symbolic rule wording.
- Bare-c: compare one-parameter `set_c(c)` against multi-parameter `set_values(a,b,c)` baselines.

Guardrail: if a confounder changes behavior, the paper should describe the effect as interface-sensitive rather than only constraint-reasoning-sensitive.

## Diagnostic Columns

| Column | Meaning | Use |
| --- | --- | --- |
| `tool_call_rate` | Share of records where a tool call was emitted | Low rates make numeric comparisons fragile. |
| `c_present_rate` | Share of tool calls with a `c` argument | Checks whether the target field exists. |
| `threshold_valid_rate` | Share satisfying `a+b+c >= 1.0` | Main threshold-rule metric. |
| `equality_valid_rate` | Share satisfying approximate `a+b+c = 1.0` | Main equality-stress metric. |
| `schema_valid_all_rate` | Share satisfying schema min/max and required fields | Detects malformed or out-of-schema calls. |
| `strict_only_c_rate` | Share preserving `a` and `b` while changing `c` | Measures obedience to â€œonly change câ€. |
| `median_c_output` | Median emitted `c` value | Primary numeric outcome. |
| `median_delta_c` | Median change from baseline `c` | Normalized increase magnitude. |
| `mean_sibling_change_l1` | Mean absolute change in `a` plus `b` | Measures sibling-parameter leakage. |

## Core Interpretation Guardrails

- `a+b+c >= 1.0` is an inequality. Outputs above the minimum are valid; exact equality is not required unless the condition is `equality_eq_1`.
- Clean-core v2 should be the first-readout story because it avoids the old `.50/.15 -> .35` ambiguity.
- Tool-call rate and abstention rate are part of the result. Do not interpret medians alone when a condition has many abstentions.
- Schema-bound claims require conditions where prompt-visible values and schema-implied values disagree, or where prompt state is absent.
- Sibling movement is not always a failure. Under equality stress, changing `a` or `b` may be a way to repair the exact sum.
- The current summaries are preliminary local readouts. A paper artifact should archive raw JSONL traces separately.
