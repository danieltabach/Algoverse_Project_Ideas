# AlgoVerse Project Ideas

Two candidate research projects for agent safety and tool-use evaluation. The repository includes one runnable experiment package with preliminary results, plus one benchmark specification that is ready for implementation.

## Project A: Numeric Tool Interfaces As Behavioral Interventions

Difficulty: **Easy-Medium**

Compute Budget: **Low** for local open-weight models; **Low-Medium** with frontier-model replication.

Language-model agents increasingly act through structured tools. This project asks whether the design of a numeric tool interface changes the action emitted by the model. Holding the user request fixed, we vary where state appears, whether a relational rule is written in the tool schema or prompt, whether sibling parameters are required, and whether vague words move the model away from its no-word default.

Core question:

> When an LLM emits a numeric tool-call argument, how much of that number comes from the user instruction, and how much comes from the tool interface?

Current status:

- Runnable Python harness.
- Clean-core configs for five mechanism tests.
- Summary CSVs from existing local runs.
- Summary-analysis notebook that works from committed CSVs.
- Docker support for reproducible Python setup.

Folder:

```text
experiments/numeric-tool-interface/
```

## Project B: Infeasibility Discovery And Disclosure

Difficulty: **Medium**

Compute Budget: **Low-Medium**.

Many impossible-task evaluations test whether a model complies with an impossible request in a single prompt. This project instead treats infeasibility as an agentic discovery problem. The model receives a limited budget of solver/tool calls, explores candidate configurations, and must decide when the stakeholder requirements are jointly infeasible. The safety question is whether it faithfully reports the negative result after observing evidence, especially under stakeholder pressure.

Core question:

> When an agent discovers through tool use that no configuration satisfies all requirements, does it disclose the tradeoff or hide it in the final recommendation?

Current status:

- Research design/specification only.
- Implementation not started.
- Key design variables identified: tool-call budget, context preservation, stopping behavior, pressure, and disclosure conditional on evidence.

Folder:

```text
experiments/infeasibility-disclosure/
```

## Repository Layout

| Folder | Contents |
| --- | --- |
| `experiments/numeric-tool-interface/` | Runnable tool-interface experiment, configs, summary results, notebook, Docker files. |
| `experiments/infeasibility-disclosure/` | Benchmark design for active infeasibility discovery and disclosure. |

## Quick Start: Numeric Tool-Interface Experiment

Standard Python:

```powershell
cd experiments\numeric-tool-interface
pip install -r requirements.txt
python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --dry-run --model qwen3-8b --runs 1
```

Docker:

```powershell
cd experiments\numeric-tool-interface
docker compose build
docker compose run --rm experiment python src\clean_layer2.py --config configs\clean_core\clean_core_threshold_boundary_v2.json --dry-run --model qwen3-8b --runs 1
```

Inspect committed summary results:

```powershell
cd experiments\numeric-tool-interface
jupyter notebook notebooks\clean_core_summary_analysis.ipynb
```

Live model runs expect an OpenAI-compatible Ollama endpoint. By default, non-Docker runs use:

```text
http://localhost:11434/v1
```

Docker runs use `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` so the container can call Ollama on the host machine.

## Data Policy

This repo commits compact summary CSVs for review. It intentionally excludes:

- raw JSONL model outputs,
- run logs,
- caches,
- scratch notes,
- unpublished drafts,
- personal planning files.

Raw outputs should be archived separately for a paper submission, for example through a release artifact, Git LFS, OSF, or Zenodo.