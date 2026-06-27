"""Write a resume-aware progress snapshot for Paper 2 configs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config_loader import load_config
from records import expand_config
from clean_layer2 import build_pending_runs, load_completed_resume_keys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write Paper 2 progress snapshot CSV")
    parser.add_argument("--manifest", default="configs/clean_core/manifest_v2.json")
    parser.add_argument("--output", default="results/summary/progress_snapshot.csv")
    parser.add_argument("--model", help="Optional model override for pilot progress")
    parser.add_argument("--runs", type=int, help="Optional run-count override for pilot progress")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"_decode_error": True})
    return rows


def manifest_config_paths(manifest_path: Path) -> list[Path]:
    paths: list[Path] = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        for key in ["recommended_order", "confounder_configs"]:
            for item in manifest.get(key, []):
                path = ROOT / item
                if path.exists() and path not in paths:
                    paths.append(path)
    for path in sorted((ROOT / "configs").glob("*.json")):
        if path.name == "full_menu_manifest_v1.json":
            continue
        if path not in paths:
            paths.append(path)
    return paths


def progress_row(config_path: Path, model: str | None, runs: int | None) -> dict[str, Any]:
    config, config_hash = load_config(config_path)
    expanded = expand_config(config, config_hash, model_override=model, runs_override=runs)
    result_path = ROOT / expanded.config["result_file"]
    rows = read_jsonl(result_path)
    completed = load_completed_resume_keys(result_path, keep_errors=False)
    pending = build_pending_runs(expanded, completed)
    complete = expanded.total_calls - len(pending)
    records = len(rows)
    return {
        "snapshot_time": datetime.now().isoformat(timespec="seconds"),
        "batch_id": expanded.config["batch_id"],
        "config_path": str(config_path.relative_to(ROOT)),
        "result_file": str(result_path.relative_to(ROOT)),
        "config_hash": config_hash[:12],
        "models": ", ".join(expanded.models),
        "n_runs": expanded.config["n_runs"],
        "total_calls": expanded.total_calls,
        "resume_completed": complete,
        "pending": len(pending),
        "progress_pct": round(100 * complete / expanded.total_calls, 2) if expanded.total_calls else 0,
        "records": records,
        "errors": sum(1 for row in rows if row.get("error")),
        "abstentions": sum(1 for row in rows if row.get("abstained")),
        "tool_calls": sum(1 for row in rows if row.get("tool_call_name")),
        "schema_invalid": sum(1 for row in rows if row.get("schema_valid_all") is False),
        "threshold_invalid": sum(1 for row in rows if row.get("threshold_valid") is False),
        "last_result_update": datetime.fromtimestamp(result_path.stat().st_mtime).isoformat(timespec="seconds") if result_path.exists() else "",
    }


def main() -> int:
    args = parse_args()
    manifest_path = ROOT / args.manifest
    output_path = ROOT / args.output
    rows = [progress_row(path, model=args.model, runs=args.runs) for path in manifest_config_paths(manifest_path)]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    print(f"Wrote {output_path}")
    for row in rows:
        if row["records"] or row["resume_completed"]:
            print(f"{row['batch_id']}: {row['resume_completed']}/{row['total_calls']} complete ({row['progress_pct']}%), pending={row['pending']}, records={row['records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
