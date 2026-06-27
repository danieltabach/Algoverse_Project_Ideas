"""Config loading and registry resolution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from registry import MODELS, MODEL_GROUPS, WORD_SETS


REQUIRED_CONFIG_FIELDS = {
    "batch_id",
    "description",
    "models",
    "n_runs",
    "temperature",
    "conditions",
    "state_variants",
    "contexts",
    "c_grid",
    "prompt_template",
    "rule_location",
    "parameter_order",
    "result_file",
}


def load_config(config_path: str | Path) -> tuple[dict[str, Any], str]:
    path = Path(config_path)
    with path.open("r", encoding="utf-8-sig") as f:
        config = json.load(f)
    config_hash = hash_config(config)
    validate_config_shape(config)
    return config, config_hash


def hash_config(config: dict[str, Any]) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_config_shape(config: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_CONFIG_FIELDS - set(config))
    has_word_spec = "word_set" in config or "words" in config
    if not has_word_spec:
        missing.append("word_set or words")
    if missing:
        raise ValueError(f"Config is missing required field(s): {', '.join(missing)}")


def resolve_models(model_specs: list[str]) -> list[str]:
    resolved: list[str] = []
    for spec in model_specs:
        if spec in MODEL_GROUPS:
            for key in MODEL_GROUPS[spec]:
                if key not in resolved:
                    resolved.append(key)
            continue
        if spec not in MODELS:
            raise ValueError(f"Unknown model or model group: {spec}")
        if spec not in resolved:
            resolved.append(spec)
    return resolved


def resolve_words(config: dict[str, Any]) -> list[str]:
    if "words" in config:
        return list(config["words"])
    word_set = config.get("word_set")
    if word_set not in WORD_SETS:
        raise ValueError(f"Unknown word_set: {word_set}")
    return list(WORD_SETS[word_set])


