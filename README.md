# AlgoVerse Project Ideas

This repository packages two research directions for team review. It is a cleaned, open-source version of local research folders, with work-in-progress notes, personal session handoffs, raw logs, and large raw model outputs intentionally excluded.

## Contents

| Experiment | Status | Folder |
| --- | --- | --- |
| Numeric tool-interface semantics | Implemented harness, clean-core configs, and summary results are included. | `experiments/numeric-tool-interface/` |
| Infeasibility disclosure benchmark | Research design/specification is included; implementation is not started. | `experiments/infeasibility-disclosure/` |

## What Was Kept

- Reusable source code for the numeric tool-call runner.
- Clean-core experiment configs.
- Scripts needed to run the clean-core experiments and progress snapshots.
- Curated summary CSVs for the clean-core runs.
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

Live runs expect an OpenAI-compatible local model endpoint, typically Ollama at:

```text
http://localhost:11434/v1
```

The default local model keys are defined in `experiments/numeric-tool-interface/src/registry.py`.

## Repository Safety Notes

This repository is intended for AlgoVerse team collaboration. The package avoids private data and external API keys. It contains synthetic prompts, synthetic model-output summaries, reusable code, and research documentation.

Before using this for a public paper submission, create a stable data artifact for full raw outputs and cite the exact commit hash or release tag used for experiments.

