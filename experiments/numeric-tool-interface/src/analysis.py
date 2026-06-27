"""Export helpers for Paper 2 raw JSONL results."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


SUMMARY_GROUP_FIELDS = [
    "batch_id",
    "model_key",
    "condition_id",
    "state_variant",
    "prompt_template",
    "rule_location",
    "rule_wording_variant",
    "parameter_order_id",
    "parameter_name_variant",
    "parameter_description_variant",
    "tool_name_variant",
    "context_id",
    "baseline_c",
    "word",
]


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    path = Path(path)
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def export_csv(jsonl_path: str | Path, csv_path: str | Path | None = None) -> Path | None:
    jsonl_path = Path(jsonl_path)
    records = read_jsonl(jsonl_path)
    if not records:
        return None
    csv_path = Path(csv_path) if csv_path else jsonl_path.with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames: list[str] = []
    flat_records: list[dict[str, Any]] = []
    for record in records:
        flat = flatten_record(record)
        for key in flat:
            if key not in fieldnames:
                fieldnames.append(key)
        flat_records.append(flat)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_records)
    return csv_path


def export_summary_csv(jsonl_path: str | Path, summary_path: str | Path | None = None) -> Path | None:
    jsonl_path = Path(jsonl_path)
    records = read_jsonl(jsonl_path)
    if not records:
        return None
    batch_id = records[0].get("batch_id", jsonl_path.stem)
    if summary_path is None:
        summary_path = Path("results") / "summary" / f"{batch_id}_summary.csv"
    else:
        summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = tuple(record.get(field) for field in SUMMARY_GROUP_FIELDS)
        groups[key].append(record)

    rows = []
    for key, group in sorted(groups.items(), key=lambda item: tuple(str(x) for x in item[0])):
        row = {field: value for field, value in zip(SUMMARY_GROUP_FIELDS, key)}
        row.update(summarize_group(group))
        rows.append(row)

    fieldnames = SUMMARY_GROUP_FIELDS + [
        "records",
        "errors",
        "abstentions",
        "tool_call_rate",
        "c_present_rate",
        "threshold_valid_rate",
        "equality_valid_rate",
        "schema_valid_all_rate",
        "strict_only_c_rate",
        "median_c_output",
        "mean_c_output",
        "median_delta_c",
        "mean_sibling_change_l1",
    ]
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return summary_path


def flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value, sort_keys=True)
        else:
            flat[key] = value
    return flat


def summarize_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "records": len(records),
        "errors": sum(1 for record in records if record.get("error")),
        "abstentions": sum(1 for record in records if record.get("abstained")),
        "tool_call_rate": rate(records, lambda record: bool(record.get("tool_call_name"))),
        "c_present_rate": rate(records, lambda record: bool(record.get("field_c_present"))),
        "threshold_valid_rate": rate(records, lambda record: record.get("threshold_valid") is True),
        "equality_valid_rate": rate(records, lambda record: record.get("equality_valid") is True),
        "schema_valid_all_rate": rate(records, lambda record: record.get("schema_valid_all") is True),
        "strict_only_c_rate": rate(records, lambda record: record.get("strict_only_c") is True),
        "median_c_output": median_or_none([record.get("c_output") for record in records]),
        "mean_c_output": mean_or_none([record.get("c_output") for record in records]),
        "median_delta_c": median_or_none([record.get("delta_c") for record in records]),
        "mean_sibling_change_l1": mean_or_none([record.get("sibling_change_l1") for record in records]),
    }


def rate(records: list[dict[str, Any]], predicate) -> float | None:
    if not records:
        return None
    return round(sum(1 for record in records if predicate(record)) / len(records), 6)


def numeric_values(values: list[Any]) -> list[float]:
    return [float(value) for value in values if isinstance(value, (int, float))]


def median_or_none(values: list[Any]) -> float | None:
    nums = numeric_values(values)
    if not nums:
        return None
    return round(float(median(nums)), 6)


def mean_or_none(values: list[Any]) -> float | None:
    nums = numeric_values(values)
    if not nums:
        return None
    return round(float(mean(nums)), 6)
