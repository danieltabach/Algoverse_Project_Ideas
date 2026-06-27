"""Config-driven Paper 2 tool-call runner."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis import export_csv, export_summary_csv
from config_loader import load_config
from llm_client import LLMClient
from records import ExpansionResult, build_run_record, expand_config, make_legacy_resume_key, make_resume_key
from registry import MODELS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Paper 2 configurable tool-call runner")
    parser.add_argument("--config", required=True, help="Path to a JSON batch config")
    parser.add_argument("--dry-run", action="store_true", help="Expand matrix and exit")
    parser.add_argument("--model", help="Override config model list with one model key/group")
    parser.add_argument("--runs", type=int, help="Override n_runs from config")
    parser.add_argument("--limit", type=int, help="Run or preview only the first N pending calls")
    parser.add_argument("--examples", type=int, default=3, help="Number of example cells to print")
    parser.add_argument(
        "--keep-errors",
        action="store_true",
        help="Treat recorded error attempts as completed during resume",
    )
    parser.add_argument(
        "--max-consecutive-errors",
        type=int,
        default=5,
        help="Abort after this many consecutive call exceptions",
    )
    parser.add_argument("--no-export", action="store_true", help="Skip CSV/summary export after execution")
    parser.add_argument("--no-fsync", action="store_true", help="Do not fsync after each JSONL append")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    config, config_hash = load_config(config_path)
    result = expand_config(
        config=config,
        config_hash=config_hash,
        model_override=args.model,
        runs_override=args.runs,
    )

    if args.dry_run:
        print_dry_run(result, config_path, examples=args.examples, limit=args.limit)
        return 0

    print_dry_run(result, config_path, examples=args.examples, limit=args.limit)
    print()
    return run_experiment(result=result, config_path=config_path, args=args)


def run_experiment(result: ExpansionResult, config_path: Path, args: argparse.Namespace) -> int:
    output_path = Path(result.config["result_file"])
    completed = load_completed_resume_keys(output_path, keep_errors=args.keep_errors)
    pending_runs = build_pending_runs(result, completed)
    skipped_completed = result.total_calls - len(pending_runs)

    if result.config.get("run_order") == "randomized":
        seed = int(result.config.get("random_seed", 0))
        random.Random(seed).shuffle(pending_runs)

    if args.limit is not None:
        pending_runs = pending_runs[: args.limit]
    pending_total = len(pending_runs)

    print("Execution")
    print(f"  Output JSONL:           {output_path}")
    print(f"  Existing completed:     {len(completed)}")
    print(f"  Pending this launch:    {pending_total}")
    print(f"  Full config call count: {result.total_calls}")
    print(f"  Run order:              {result.config.get('run_order', 'as_expanded')}")
    if result.config.get("run_order") == "randomized":
        print(f"  Random seed:            {result.config.get('random_seed', 0)}")
    print("  Resume policy:          skip non-error records; retry error records" if not args.keep_errors else "  Resume policy:          skip all recorded attempts")
    print()

    if pending_total == 0:
        print("No pending calls. Exporting existing results.")
        if not args.no_export:
            export_outputs(output_path)
        return 0

    clients: dict[str, LLMClient] = {}
    attempted = 0
    consecutive_errors = 0

    try:
        for cell, run_number in pending_runs:
            attempted += 1
            response = None
            error = None
            start = time.time()
            try:
                client = get_client(clients, cell.model_key, result.config["temperature"])
                response = client.call(
                    messages=[{"role": "user", "content": cell.prompt_text}],
                    tools=[cell.tool_schema],
                    system=result.config.get("system_prompt"),
                )
                consecutive_errors = 0
            except Exception as exc:  # Record transport/client errors, then continue or abort on a streak.
                error = f"{type(exc).__name__}: {exc}"
                consecutive_errors += 1
            latency_ms = round((time.time() - start) * 1000, 3)

            record = build_run_record(
                cell=cell,
                config_path=str(config_path),
                run_number=run_number,
                response=response,
                latency_ms=latency_ms,
                error=error,
            )
            append_jsonl(output_path, record, fsync=not args.no_fsync)

            status = format_status(record)
            print(
                f"  [{attempted}/{pending_total}] "
                f"{cell.model_key} | {cell.condition_id} | {cell.state_variant} | "
                f"{cell.context_id} | c={cell.baseline_c} | {cell.word or '(no word)'} | "
                f"r{run_number:02d} | {status}"
            )

            if args.max_consecutive_errors and consecutive_errors >= args.max_consecutive_errors:
                print()
                print(
                    f"Aborting after {consecutive_errors} consecutive call errors. "
                    "Fix the model server/client issue and rerun; completed records will resume."
                )
                if not args.no_export:
                    export_outputs(output_path)
                return 1
    except KeyboardInterrupt:
        print()
        print("Interrupted. JSONL records already written will be skipped on the next launch.")
        if not args.no_export:
            export_outputs(output_path)
        return 130

    print()
    print(f"Executed {attempted} calls; skipped {skipped_completed} already-completed calls.")
    if not args.no_export:
        export_outputs(output_path)
    return 0


def build_pending_runs(result: ExpansionResult, completed: set[str]) -> list[tuple[Any, int]]:
    pending: list[tuple[Any, int]] = []
    for cell in result.cells:
        for run_number in range(1, int(result.config["n_runs"]) + 1):
            if (
                make_resume_key(cell, run_number) not in completed
                and make_legacy_resume_key(cell, run_number) not in completed
            ):
                pending.append((cell, run_number))
    return pending

def get_client(clients: dict[str, LLMClient], model_key: str, temperature: float) -> LLMClient:
    if model_key not in clients:
        model = MODELS[model_key]
        clients[model_key] = LLMClient(
            provider=model.provider,
            model_id=model.model_id,
            temperature=temperature,
            api_base=model.api_base,
        )
    return clients[model_key]


def load_completed_resume_keys(output_path: Path, keep_errors: bool) -> set[str]:
    completed: set[str] = set()
    if not output_path.exists():
        return completed
    with output_path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("error") and not keep_errors:
                continue
            resume_key = record.get("resume_key")
            if resume_key:
                completed.add(resume_key)
    return completed


def count_pending_runs(result: ExpansionResult, completed: set[str]) -> int:
    count = 0
    for cell in result.cells:
        for run_number in range(1, int(result.config["n_runs"]) + 1):
            if (
                make_resume_key(cell, run_number) not in completed
                and make_legacy_resume_key(cell, run_number) not in completed
            ):
                count += 1
    return count


def append_jsonl(output_path: Path, record: dict[str, Any], fsync: bool = True) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        f.flush()
        if fsync:
            os.fsync(f.fileno())


def export_outputs(output_path: Path) -> None:
    csv_path = export_csv(output_path)
    summary_path = export_summary_csv(output_path)
    if csv_path:
        print(f"Exported CSV:     {csv_path}")
    if summary_path:
        print(f"Exported summary: {summary_path}")


def format_status(record: dict[str, Any]) -> str:
    if record.get("error"):
        return "ERROR " + str(record["error"])[:90]
    if record.get("abstained"):
        return "ABSTAIN"
    c_value = record.get("c_output")
    c_text = f"c={c_value}" if c_value is not None else "c=None"
    validity = []
    if record.get("threshold_valid") is not None:
        validity.append(f"thr={record['threshold_valid']}")
    if record.get("schema_valid_all") is not None:
        validity.append(f"schema={record['schema_valid_all']}")
    norm = " normalized" if record.get("normalization_applied") else ""
    return f"{record.get('tool_call_name') or 'no_tool'} | {c_text} | {' '.join(validity)}{norm}"


class LimitReached(Exception):
    pass


def print_dry_run(
    result: ExpansionResult,
    config_path: Path,
    examples: int,
    limit: int | None,
) -> None:
    config = result.config
    n_runs = int(config["n_runs"])
    total_calls = result.total_calls
    limited_calls = min(total_calls, limit) if limit is not None else total_calls

    print("=" * 72)
    print("Paper 2 Testbed Dry Run")
    print("=" * 72)
    print(f"Config:      {config_path}")
    print(f"Batch:       {config['batch_id']}")
    print(f"Hash:        {result.config_hash[:12]}")
    print(f"Output:      {config['result_file']}")
    print(f"Description: {config.get('description', '')}")
    print()

    print("Resolved Factors")
    print(f"  Models ({len(result.models)}):        {', '.join(result.models)}")
    print(f"  Words ({len(result.words)}):         {format_word_list(result.words)}")
    print(f"  Conditions ({len(config['conditions'])}):    {', '.join(config['conditions'])}")
    print(f"  State variants ({len(config['state_variants'])}): {', '.join(config['state_variants'])}")
    print(f"  Prompt templates ({len(config['prompt_templates'])}): {', '.join(config['prompt_templates'])}")
    print(f"  Rule locations ({len(config['rule_locations'])}): {', '.join(config['rule_locations'])}")
    print(f"  Parameter orders ({len(config['parameter_orders'])}): {', '.join(''.join(order) for order in config['parameter_orders'])}")
    print(f"  Tool-name variants ({len(config['tool_name_variants'])}): {', '.join(config['tool_name_variants'])}")
    print(f"  Parameter-name variants ({len(config['parameter_name_variants'])}): {', '.join(config['parameter_name_variants'])}")
    print(f"  Parameter descriptions ({len(config['parameter_description_variants'])}): {', '.join(config['parameter_description_variants'])}")
    print(f"  Rule wordings ({len(config['rule_wording_variants'])}): {', '.join(config['rule_wording_variants'])}")
    print(f"  Contexts ({len(config['contexts'])}):      {', '.join(c.get('context_id', 'context') for c in config['contexts'])}")
    print(f"  C grid ({len(config['c_grid'])}):        {config['c_grid']}")
    print(f"  Run order:           {config.get('run_order', 'as_expanded')}")
    if config.get('run_order') == 'randomized':
        print(f"  Random seed:         {config.get('random_seed', 0)}")
    print(f"  Runs per cell:       {n_runs}")
    print()

    print("Expansion")
    print(f"  Expanded cells:      {len(result.cells)}")
    print(f"  Calls:               {total_calls}")
    if limit is not None:
        print(f"  Calls after --limit: {limited_calls}")
    print(f"  Skipped cells:       {len(result.skipped)}")
    print()

    print_warnings(result)
    print_skipped(result)
    print_examples(result, examples)


def print_warnings(result: ExpansionResult) -> None:
    if not result.warnings:
        print("Warnings")
        print("  None")
        print()
        return
    print("Warnings")
    for warning in result.warnings:
        print(f"  - {warning}")
    print()


def print_skipped(result: ExpansionResult) -> None:
    print("Skipped Cells")
    if not result.skipped:
        print("  None")
        print()
        return

    reason_counts: dict[str, int] = {}
    for item in result.skipped:
        reason_counts[item.reason] = reason_counts.get(item.reason, 0) + 1
    for reason, count in reason_counts.items():
        print(f"  - {count} x {reason}")

    preview_count = min(5, len(result.skipped))
    print(f"  Preview ({preview_count}/{len(result.skipped)}):")
    for item in result.skipped[:preview_count]:
        word_label = item.word or "(no word)"
        print(
            "    "
            f"{item.condition_id} | {item.state_variant} | {item.context_id} | "
            f"c={item.baseline_c} | {word_label} | {item.model_key}"
        )
    print()


def print_examples(result: ExpansionResult, examples: int) -> None:
    if not result.cells:
        print("Examples")
        print("  No valid cells were expanded.")
        return

    count = min(max(0, examples), len(result.cells))
    print(f"Examples ({count}/{len(result.cells)})")
    for idx, cell in enumerate(result.cells[:count], start=1):
        print("-" * 72)
        print(f"Example {idx}: {cell.cell_id}")
        print(f"Batch index: {cell.batch_index}")
        print(
            "Factors: "
            f"model={cell.model_key}, condition={cell.condition_id}, "
            f"state={cell.state_variant}, context={cell.context_id}, "
            f"c={cell.baseline_c}, word={cell.word or '(no word)'}"
        )
        print("Prompt:")
        print(f"  {cell.prompt_text}")
        print("Tool schema:")
        print(indent(json.dumps(cell.tool_schema, indent=2, sort_keys=False), "  "))
        diagnostic_preview = {
            "required_fields": cell.metadata["required_fields"],
            "schema_defaults_enabled": cell.metadata["schema_defaults_enabled"],
            "state_value_source": cell.metadata["state_value_source"],
            "c_required_context": cell.metadata["c_required_context"],
            "c_required_schema_bound": cell.metadata["c_required_schema_bound"],
            "mechanism_prediction_gap": cell.metadata["mechanism_prediction_gap"],
            "mechanism_identifiable": cell.metadata["mechanism_identifiable"],
        }
        print("Diagnostics preview:")
        print(indent(json.dumps(diagnostic_preview, indent=2), "  "))
    print("-" * 72)


def format_word_list(words: list[str]) -> str:
    labels = [word if word else "(no word)" for word in words]
    return ", ".join(labels)


def indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())


if __name__ == "__main__":
    raise SystemExit(main())
