# AlgoVerse Project Ideas

This repository packages two research directions for team review. It is a cleaned, open-source version of local research folders, with work-in-progress notes, personal session handoffs, raw logs, and large raw model outputs intentionally excluded.

## Project 1: Numeric Tool-Interface Semantics

Difficulty: **Easy-Medium**

Compute Budget: **Low** for local models; **Low-Medium** with frontier replications.

Tool schemas may not be neutral wrappers around model intent. When an agent is asked to "slightly increase c," the number it emits can depend on prompt-visible state, schema bounds, required sibling parameters, and whether a relational rule is written in the tool description or the user prompt. This project treats numeric tool arguments as behavioral measurements and asks whether tool design itself becomes part of the agent's action policy.

Folder:

```text
experiments/numeric-tool-interface/
```

Current package includes runnable code, clean-core configs, summary results, and a summary-analysis notebook.

## Project 2: Infeasibility Discovery And Disclosure

Difficulty: **Medium**

Compute Budget: **Low-Medium**.

Most impossible-task evaluations ask whether a model complies with or hacks around an impossible request in one prompt. This project reframes impossibility as an agentic discovery problem. The model gets a limited budget of solver/tool calls, explores candidate configs, and must decide when the requirements are jointly infeasible. The safety question is whether it faithfully reports that negative result, especially under stakeholder pressure.

Folder:

```text
experiments/infeasibility-disclosure/
```

Current package includes a cleaned research specification. Implementation is not started yet.

## Contents

| Experiment | Status | Folder |
| --- | --- | --- |
| Numeric tool-interface semantics | Implemented harness, clean-core configs, summary results, and summary notebook are included. | `experiments/numeric-tool-interface/` |
| Infeasibility discovery/disclosure benchmark | Research design/specification is included; implementation is not started. | `experiments/infeasibility-disclosure/` |

## What Was Kept

- Reusable source code for the numeric tool-call runner.
- Clean-core experiment configs.
- Scripts needed to run the clean-core experiments and progress snapshots.
- Curated summary CSVs for the clean-core runs.
- A lightweight notebook that reads committed summary CSVs.
- One canonical README per experiment type.

## What Was Excluded

- Raw JSONL/CSV model outputs under `results/raw/`.
- Logs under `logs/`.
- Old design memos, session handoffs, scratch notes, and drafts.
- Personal planning material and unpublished narrative paper drafts.
- Large files that are not appropriate for normal GitHub storage.

Raw outputs are reproducible from the included configs and runner. If the team needs full raw data later, use a release artifact, Git LFS, Zenodo, OSF, or another data archive rather than committing large JSONL files directly.

## Quick Start

The implemented code is in the numeric tool-interface experiment:

```powershell
cd experiments\numeric-tool-interface
pip install -r requirements.txt
python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --dry-run --model qwen3-8b --runs 1
```

Docker is also supported for the runnable experiment; see `experiments/numeric-tool-interface/README.md` for the beginner-friendly Docker commands and `OLLAMA_BASE_URL` explanation.

Inspect committed summary results:

```powershell
cd experiments\numeric-tool-interface
jupyter notebook notebooks\clean_core_summary_analysis.ipynb
```

Live runs expect an OpenAI-compatible local model endpoint, typically Ollama at:

```text
http://localhost:11434/v1
```

The default local model keys are defined in `experiments/numeric-tool-interface/src/registry.py`.

## Repository Safety Notes

This repository is intended for AlgoVerse team collaboration. The package avoids private data and external API keys. It contains synthetic prompts, synthetic model-output summaries, reusable code, and research documentation.

Before using this for a public paper submission, create a stable data artifact for full raw outputs and cite the exact commit hash or release tag used for experiments.