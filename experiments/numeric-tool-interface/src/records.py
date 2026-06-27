"""Matrix expansion, prompt construction, and tool-schema construction."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any

from config_loader import resolve_models, resolve_words
from registry import (
    CONDITIONS,
    MODELS,
    PARAMETER_DESCRIPTION_VARIANTS,
    PARAMETER_NAME_VARIANTS,
    PROMPT_TEMPLATES,
    RULE_WORDING_VARIANTS,
    STATE_VARIANTS,
    TOOL_NAME_VARIANTS,
    VALID_RULE_LOCATIONS,
    WORD_LEVELS,
)

TOLERANCE = 0.005
CANONICAL_FIELDS = ["a", "b", "c"]
DEFAULT_FIELD_NAME_MAP = {"a": "a", "b": "b", "c": "c"}


@dataclass
class ExpandedCell:
    batch_index: int
    cell_id: str
    batch_id: str
    condition_id: str
    state_variant: str
    context_id: str
    model_key: str
    word: str
    word_level: int | None
    baseline_a: float | None
    baseline_b: float | None
    baseline_c: float | None
    prompt_text: str
    tool_schema: dict[str, Any]
    metadata: dict[str, Any]


@dataclass
class SkippedCell:
    condition_id: str
    state_variant: str
    context_id: str
    model_key: str
    word: str
    baseline_c: float | None
    reason: str


@dataclass
class ExpansionResult:
    config: dict[str, Any]
    config_hash: str
    models: list[str]
    words: list[str]
    cells: list[ExpandedCell] = field(default_factory=list)
    skipped: list[SkippedCell] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_calls(self) -> int:
        return len(self.cells) * int(self.config["n_runs"])


def expand_config(
    config: dict[str, Any],
    config_hash: str,
    model_override: str | None = None,
    runs_override: int | None = None,
) -> ExpansionResult:
    config = normalize_config_defaults(copy.deepcopy(config))
    if runs_override is not None:
        config["n_runs"] = runs_override
    models = resolve_models([model_override] if model_override else config["models"])
    words = resolve_words(config)
    result = ExpansionResult(config=config, config_hash=config_hash, models=models, words=words)

    validate_registry_refs(config, result)

    batch_index = 0
    default_c_values = list(config.get("c_grid", [])) or [None]
    factors = []
    for condition_id in config["conditions"]:
        for state_variant_id in config["state_variants"]:
            for context in config["contexts"]:
                allowed_state_variants = context.get("allowed_state_variants")
                if allowed_state_variants and state_variant_id not in allowed_state_variants:
                    continue
                context_c_values = list(context.get("c_grid", default_c_values)) or [None]
                first_c_value = context_c_values[0]
                for c_value in context_c_values:
                    for prompt_template_id in config["prompt_templates"]:
                        for rule_location in config["rule_locations"]:
                            for parameter_order in config["parameter_orders"]:
                                for tool_name_variant in config["tool_name_variants"]:
                                    for parameter_name_variant in config["parameter_name_variants"]:
                                        for parameter_description_variant in config["parameter_description_variants"]:
                                            for rule_wording_variant in config["rule_wording_variants"]:
                                                for word in words:
                                                    for model_key in models:
                                                        factors.append((
                                                            condition_id,
                                                            state_variant_id,
                                                            context,
                                                            c_value,
                                                            first_c_value,
                                                            prompt_template_id,
                                                            rule_location,
                                                            list(parameter_order),
                                                            tool_name_variant,
                                                            parameter_name_variant,
                                                            parameter_description_variant,
                                                            rule_wording_variant,
                                                            word,
                                                            model_key,
                                                        ))

    prompt_schema_counts: dict[str, int] = {}
    for (
        condition_id,
        state_variant_id,
        context,
        c_value,
        first_c_value,
        prompt_template_id,
        rule_location,
        parameter_order,
        tool_name_variant,
        parameter_name_variant,
        parameter_description_variant,
        rule_wording_variant,
        word,
        model_key,
    ) in factors:
        condition = CONDITIONS[condition_id]
        state_variant = STATE_VARIANTS[state_variant_id]
        field_name_map = PARAMETER_NAME_VARIANTS[parameter_name_variant]
        state_values_exposed = exposes_state_values(state_variant)
        raw_a = as_float_or_none(context.get("a"))
        raw_b = as_float_or_none(context.get("b"))
        raw_c = as_float_or_none(c_value if c_value is not None else context.get("c"))
        baseline_a = raw_a if state_values_exposed else None
        baseline_b = raw_b if state_values_exposed else None
        baseline_c = raw_c if state_values_exposed else None
        context_id = context.get("context_id", "context")

        invalid_reason = invalid_cell_reason(
            prompt_template_id=prompt_template_id,
            state_variant_id=state_variant_id,
            raw_a=raw_a,
            raw_b=raw_b,
            raw_c=raw_c,
            state_values_exposed=state_values_exposed,
            duplicate_unexposed_c=(not state_values_exposed and c_value != first_c_value),
        )
        if invalid_reason:
            result.skipped.append(SkippedCell(
                condition_id=condition_id,
                state_variant=state_variant_id,
                context_id=context_id,
                model_key=model_key,
                word=word,
                baseline_c=baseline_c,
                reason=invalid_reason,
            ))
            continue

        prompt_text = build_prompt(
            template_id=prompt_template_id,
            word=word,
            condition=condition,
            state_variant=state_variant,
            rule_location=rule_location,
            rule_wording_variant=rule_wording_variant,
            field_name_map=field_name_map,
            baseline_a=baseline_a,
            baseline_b=baseline_b,
            baseline_c=baseline_c,
        )
        tool_schema = build_tool_schema(
            condition=condition,
            state_variant=state_variant,
            context=context,
            baseline_a=baseline_a,
            baseline_b=baseline_b,
            baseline_c=baseline_c,
            parameter_order=parameter_order,
            rule_location=rule_location,
            rule_wording_variant=rule_wording_variant,
            tool_name_variant=tool_name_variant,
            parameter_name_variant=parameter_name_variant,
            parameter_description_variant=parameter_description_variant,
        )
        metadata = build_cell_metadata(
            config=config,
            config_hash=config_hash,
            condition_id=condition_id,
            state_variant_id=state_variant_id,
            context=context,
            baseline_a=baseline_a,
            baseline_b=baseline_b,
            baseline_c=baseline_c,
            word=word,
            model_key=model_key,
            tool_schema=tool_schema,
            prompt_template_id=prompt_template_id,
            rule_location=rule_location,
            parameter_order=parameter_order,
            tool_name_variant=tool_name_variant,
            parameter_name_variant=parameter_name_variant,
            parameter_description_variant=parameter_description_variant,
            rule_wording_variant=rule_wording_variant,
        )
        batch_index += 1
        cell_id = make_cell_id(
            condition_id=condition_id,
            state_variant_id=state_variant_id,
            context_id=context_id,
            prompt_template_id=prompt_template_id,
            rule_location=rule_location,
            parameter_order_id=metadata["parameter_order_id"],
            tool_name_variant=tool_name_variant,
            parameter_name_variant=parameter_name_variant,
            parameter_description_variant=parameter_description_variant,
            rule_wording_variant=rule_wording_variant,
            baseline_c=baseline_c,
            word=word,
            model_key=model_key,
        )
        cell = ExpandedCell(
            batch_index=batch_index,
            cell_id=cell_id,
            batch_id=config["batch_id"],
            condition_id=condition_id,
            state_variant=state_variant_id,
            context_id=context_id,
            model_key=model_key,
            word=word,
            word_level=WORD_LEVELS.get(word),
            baseline_a=baseline_a,
            baseline_b=baseline_b,
            baseline_c=baseline_c,
            prompt_text=prompt_text,
            tool_schema=tool_schema,
            metadata=metadata,
        )
        result.cells.append(cell)

        prompt_schema_key = json.dumps({"prompt": prompt_text, "schema": tool_schema}, sort_keys=True, separators=(",", ":"))
        prompt_schema_counts[prompt_schema_key] = prompt_schema_counts.get(prompt_schema_key, 0) + 1

    expected_model_repeats = max(1, len(models))
    repeated = [count for count in prompt_schema_counts.values() if count > expected_model_repeats]
    if repeated:
        result.warnings.append(
            "Duplicate prompt/schema patterns detected across expanded cells "
            f"beyond cross-model duplication (patterns={len(repeated)}, max_repeat={max(repeated)}). "
            "Check no-state/schema-only grids or inert variants."
        )
    return result


def normalize_config_defaults(config: dict[str, Any]) -> dict[str, Any]:
    config["prompt_templates"] = list(config.get("prompt_templates", [config["prompt_template"]]))
    config["rule_locations"] = list(config.get("rule_locations", [config["rule_location"]]))
    config["parameter_orders"] = [list(order) for order in config.get("parameter_orders", [config["parameter_order"]])]
    config["tool_name_variants"] = list(config.get("tool_name_variants", [config.get("tool_name_variant", "neutral")]))
    config["parameter_name_variants"] = list(config.get("parameter_name_variants", [config.get("parameter_name_variant", "canonical_abc")]))
    config["parameter_description_variants"] = list(config.get("parameter_description_variants", [config.get("parameter_description_variant", "none")]))
    config["rule_wording_variants"] = list(config.get("rule_wording_variants", [config.get("rule_wording_variant", "default")]))
    config["run_order"] = config.get("run_order", "as_expanded")
    return config


def validate_registry_refs(config: dict[str, Any], result: ExpansionResult) -> None:
    for prompt_template in config["prompt_templates"]:
        if prompt_template not in PROMPT_TEMPLATES:
            raise ValueError(f"Unknown prompt_template: {prompt_template}")
    for rule_location in config["rule_locations"]:
        if rule_location not in VALID_RULE_LOCATIONS:
            raise ValueError(f"Unknown rule_location: {rule_location}")
    for condition_id in config["conditions"]:
        if condition_id not in CONDITIONS:
            raise ValueError(f"Unknown condition: {condition_id}")
    for state_variant in config["state_variants"]:
        if state_variant not in STATE_VARIANTS:
            raise ValueError(f"Unknown state_variant: {state_variant}")
    for tool_name_variant in config["tool_name_variants"]:
        if tool_name_variant not in TOOL_NAME_VARIANTS:
            raise ValueError(f"Unknown tool_name_variant: {tool_name_variant}")
    for parameter_name_variant in config["parameter_name_variants"]:
        if parameter_name_variant not in PARAMETER_NAME_VARIANTS:
            raise ValueError(f"Unknown parameter_name_variant: {parameter_name_variant}")
    for parameter_description_variant in config["parameter_description_variants"]:
        if parameter_description_variant not in PARAMETER_DESCRIPTION_VARIANTS:
            raise ValueError(f"Unknown parameter_description_variant: {parameter_description_variant}")
    for rule_wording_variant in config["rule_wording_variants"]:
        if rule_wording_variant not in RULE_WORDING_VARIANTS:
            raise ValueError(f"Unknown rule_wording_variant: {rule_wording_variant}")
    if config["run_order"] not in {"as_expanded", "randomized"}:
        raise ValueError(f"Unknown run_order: {config['run_order']}")
    for order in config["parameter_orders"]:
        unknown = [field for field in order if field not in CANONICAL_FIELDS]
        if unknown:
            raise ValueError(f"parameter_order contains unknown field(s): {', '.join(unknown)}")
    for word in result.words:
        if word not in WORD_LEVELS:
            result.warnings.append(f"Word has no registered level and will record null: {word!r}")


def invalid_cell_reason(
    prompt_template_id: str,
    state_variant_id: str,
    raw_a: float | None,
    raw_b: float | None,
    raw_c: float | None,
    state_values_exposed: bool,
    duplicate_unexposed_c: bool,
) -> str | None:
    if duplicate_unexposed_c:
        return "state variant exposes no current c; duplicate c_grid value skipped"
    template = PROMPT_TEMPLATES[prompt_template_id]
    state_variant = STATE_VARIANTS[state_variant_id]
    prompt_needs_state = template["include_current_state"] and state_variant["prompt_contains_state"]
    if prompt_needs_state:
        missing = [name for name, value in (("a", raw_a), ("b", raw_b), ("c", raw_c)) if value is None]
        if missing:
            return "prompt state requested but missing current value(s): " + ", ".join(missing)
    if template["instruction"] in {"exact_delta_c", "exact_set_c"} and not state_values_exposed:
        return "exact instruction template requires an exposed current state"
    return None


def build_prompt(
    template_id: str,
    word: str,
    condition: dict[str, Any],
    state_variant: dict[str, Any],
    rule_location: str,
    rule_wording_variant: str,
    field_name_map: dict[str, str],
    baseline_a: float | None,
    baseline_b: float | None,
    baseline_c: float | None,
) -> str:
    template = PROMPT_TEMPLATES[template_id]
    parts: list[str] = []
    if template["include_current_state"] and state_variant["prompt_contains_state"]:
        parts.append(
            "Current values: "
            f"{field_name_map['a']}={format_number(baseline_a)}, "
            f"{field_name_map['b']}={format_number(baseline_b)}, "
            f"{field_name_map['c']}={format_number(baseline_c)}."
        )
    if rule_location in {"user_prompt", "both"}:
        rule_text = render_rule_text(condition, rule_wording_variant, field_name_map)
        if rule_text:
            parts.append(rule_text)
    if template["only_change_c"]:
        parts.append(f"Only change {field_name_map['c']}.")
    elif template_id == "no_baseline":
        parts.append("Set the values.")

    instruction = template["instruction"]
    if instruction == "word_increase":
        parts.append(build_word_sentence(word, field_name_map["c"]))
    elif instruction == "exact_delta_c":
        parts.append(f"Increase {field_name_map['c']} by exactly {format_number(template['delta_c'])}.")
    elif instruction == "exact_set_c":
        parts.append(f"Set {field_name_map['c']} to exactly {format_number(template['target_c'])}.")
    return " ".join(parts)


def build_word_sentence(word: str, c_name: str) -> str:
    if word:
        return f"{word.capitalize()} increase {c_name}."
    return f"Increase {c_name}."


def build_tool_schema(
    condition: dict[str, Any],
    state_variant: dict[str, Any],
    context: dict[str, Any],
    baseline_a: float | None,
    baseline_b: float | None,
    baseline_c: float | None,
    parameter_order: list[str],
    rule_location: str,
    rule_wording_variant: str,
    tool_name_variant: str,
    parameter_name_variant: str,
    parameter_description_variant: str,
) -> dict[str, Any]:
    field_name_map = PARAMETER_NAME_VARIANTS[parameter_name_variant]
    properties: dict[str, Any] = {}
    source_parameters = condition["parameters"]
    baseline_values = {"a": baseline_a, "b": baseline_b, "c": baseline_c}
    for canonical_name in parameter_order:
        if canonical_name not in source_parameters:
            raise ValueError(f"parameter_order contains field not used by condition: {canonical_name}")
        visible_name = field_name_map[canonical_name]
        field_schema = copy.deepcopy(source_parameters[canonical_name])
        apply_context_schema_overrides(field_schema, context, canonical_name)
        if state_variant["schema_defaults"] and baseline_values[canonical_name] is not None:
            field_schema["default"] = baseline_values[canonical_name]
        apply_parameter_description(
            field_schema=field_schema,
            variant=parameter_description_variant,
            visible_name=visible_name,
            value=baseline_values[canonical_name],
        )
        properties[visible_name] = field_schema

    description = render_text_template(condition["base_tool_description"], field_name_map)
    if rule_location in {"tool_description", "both"}:
        rule_text = render_rule_text(condition, rule_wording_variant, field_name_map)
        if rule_text:
            description = f"{description} {rule_text}"

    required_fields = [
        field_name_map[canonical_name]
        for canonical_name in parameter_order
        if canonical_name in state_variant["required_fields"]
    ]
    return {
        "type": "function",
        "function": {
            "name": resolve_tool_name(condition, tool_name_variant),
            "description": description,
            "parameters": {
                "type": "object",
                "required": required_fields,
                "properties": properties,
            },
        },
    }


def apply_context_schema_overrides(field_schema: dict[str, Any], context: dict[str, Any], field_name: str) -> None:
    min_key = f"schema_{field_name}_min"
    max_key = f"schema_{field_name}_max"
    if context.get(min_key) is not None:
        field_schema["minimum"] = context[min_key]
    if context.get(max_key) is not None:
        field_schema["maximum"] = context[max_key]


def apply_parameter_description(field_schema: dict[str, Any], variant: str, visible_name: str, value: float | None) -> None:
    template = PARAMETER_DESCRIPTION_VARIANTS[variant]
    if not template:
        return
    value_text = "not provided" if value is None else format_number(value)
    field_schema["description"] = template.format(field=visible_name, value=value_text)


def build_cell_metadata(
    config: dict[str, Any],
    config_hash: str,
    condition_id: str,
    state_variant_id: str,
    context: dict[str, Any],
    baseline_a: float | None,
    baseline_b: float | None,
    baseline_c: float | None,
    word: str,
    model_key: str,
    tool_schema: dict[str, Any],
    prompt_template_id: str,
    rule_location: str,
    parameter_order: list[str],
    tool_name_variant: str,
    parameter_name_variant: str,
    parameter_description_variant: str,
    rule_wording_variant: str,
) -> dict[str, Any]:
    condition = CONDITIONS[condition_id]
    state_variant = STATE_VARIANTS[state_variant_id]
    model = MODELS[model_key]
    field_name_map = PARAMETER_NAME_VARIANTS[parameter_name_variant]
    schema_bounds = extract_schema_bounds(tool_schema, field_name_map)
    c_required_context = required_context_floor(baseline_a, baseline_b)
    c_required_schema_bound = required_schema_floor(schema_bounds)
    mechanism_gap = nullable_abs_diff(c_required_context, c_required_schema_bound)
    parameter_order_id = "".join(parameter_order)
    return {
        "config_hash": config_hash,
        "description": config.get("description"),
        "condition_id": condition_id,
        "layer": condition["layer"],
        "relation": condition["relation"],
        "state_variant": state_variant_id,
        "rule_location": rule_location,
        "rule_wording_variant": rule_wording_variant,
        "rendered_rule_text": render_rule_text(condition, rule_wording_variant, field_name_map),
        "required_fields": canonical_required_fields(tool_schema, field_name_map),
        "required_visible_fields": tool_schema["function"]["parameters"]["required"],
        "schema_defaults_enabled": state_variant["schema_defaults"],
        "state_values_exposed": exposes_state_values(state_variant),
        "state_value_source": state_value_source(state_variant),
        "parameter_order": parameter_order,
        "parameter_order_id": parameter_order_id,
        "visible_parameter_order": [field_name_map[name] for name in parameter_order],
        "parameter_name_variant": parameter_name_variant,
        "field_name_map": field_name_map,
        "parameter_description_variant": parameter_description_variant,
        "prompt_template": prompt_template_id,
        "tool_name_variant": tool_name_variant,
        "tool_name": tool_schema["function"]["name"],
        "model_key": model_key,
        "model_id": model.model_id,
        "model_name": model.display_name,
        "provider": model.provider,
        "temperature": config["temperature"],
        "word": word,
        "word_level": WORD_LEVELS.get(word),
        "context_id": context.get("context_id"),
        "baseline_a": baseline_a,
        "baseline_b": baseline_b,
        "baseline_c": baseline_c,
        "schema_a_min": schema_bounds["a"].get("minimum"),
        "schema_a_max": schema_bounds["a"].get("maximum"),
        "schema_a_default": schema_bounds["a"].get("default"),
        "schema_b_min": schema_bounds["b"].get("minimum"),
        "schema_b_max": schema_bounds["b"].get("maximum"),
        "schema_b_default": schema_bounds["b"].get("default"),
        "schema_c_min": schema_bounds["c"].get("minimum"),
        "schema_c_max": schema_bounds["c"].get("maximum"),
        "schema_c_default": schema_bounds["c"].get("default"),
        "c_required_context": c_required_context,
        "c_floor_gap_context": None,
        "c_required_schema_bound": c_required_schema_bound,
        "c_floor_gap_schema_bound": None,
        "mechanism_prediction_gap": mechanism_gap,
        "mechanism_identifiable": is_mechanism_identifiable(
            condition=condition,
            state_variant=state_variant,
            mechanism_gap=mechanism_gap,
            c_required_schema_bound=c_required_schema_bound,
        ),
        "run_order": config.get("run_order", "as_expanded"),
        "random_seed": config.get("random_seed"),
    }


def canonical_required_fields(tool_schema: dict[str, Any], field_name_map: dict[str, str]) -> list[str]:
    required_visible = set(tool_schema["function"]["parameters"]["required"])
    return [canonical for canonical, visible in field_name_map.items() if visible in required_visible]


def extract_schema_bounds(tool_schema: dict[str, Any], field_name_map: dict[str, str]) -> dict[str, dict[str, Any]]:
    props = tool_schema["function"]["parameters"]["properties"]
    bounds: dict[str, dict[str, Any]] = {}
    for canonical_name in CANONICAL_FIELDS:
        visible_name = field_name_map.get(canonical_name, canonical_name)
        field = props.get(visible_name, {})
        bounds[canonical_name] = {
            "minimum": field.get("minimum"),
            "maximum": field.get("maximum"),
            "default": field.get("default"),
        }
    return bounds


def required_context_floor(baseline_a: float | None, baseline_b: float | None) -> float | None:
    if baseline_a is None or baseline_b is None:
        return None
    return round(max(0.0, 1.0 - baseline_a - baseline_b), 4)


def required_schema_floor(schema_bounds: dict[str, dict[str, Any]]) -> float | None:
    a_max = schema_bounds["a"].get("maximum")
    b_max = schema_bounds["b"].get("maximum")
    if a_max is None or b_max is None:
        return None
    return round(max(0.0, 1.0 - float(a_max) - float(b_max)), 4)


def nullable_abs_diff(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(abs(left - right), 4)


def exposes_state_values(state_variant: dict[str, Any]) -> bool:
    return bool(state_variant["prompt_contains_state"] or state_variant["schema_defaults"])


def state_value_source(state_variant: dict[str, Any]) -> str:
    sources = []
    if state_variant["prompt_contains_state"]:
        sources.append("prompt")
    if state_variant["schema_defaults"]:
        sources.append("schema_defaults")
    return "+".join(sources) if sources else "none"


def is_mechanism_identifiable(
    condition: dict[str, Any],
    state_variant: dict[str, Any],
    mechanism_gap: float | None,
    c_required_schema_bound: float | None,
) -> bool:
    if condition["relation"] == "none":
        return False
    if mechanism_gap is not None and mechanism_gap > TOLERANCE:
        return True
    schema_only_positive_floor = (
        not exposes_state_values(state_variant)
        and c_required_schema_bound is not None
        and c_required_schema_bound > TOLERANCE
    )
    return schema_only_positive_floor


def render_rule_text(condition: dict[str, Any], rule_wording_variant: str, field_name_map: dict[str, str]) -> str | None:
    if condition["relation"] == "none":
        return None
    template = RULE_WORDING_VARIANTS[rule_wording_variant].get(condition["relation"], condition.get("rule_text"))
    if not template:
        return None
    return render_text_template(template, field_name_map)


def render_text_template(template: str, field_name_map: dict[str, str]) -> str:
    return template.format(**field_name_map)


def resolve_tool_name(condition: dict[str, Any], tool_name_variant: str) -> str:
    return TOOL_NAME_VARIANTS[tool_name_variant] or condition["tool_name"]


def as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def format_number(value: float | None) -> str:
    if value is None:
        raise ValueError("Cannot format null numeric value")
    return f"{value:.2f}"


def make_cell_id(
    condition_id: str,
    state_variant_id: str,
    context_id: str,
    prompt_template_id: str,
    rule_location: str,
    parameter_order_id: str,
    tool_name_variant: str,
    parameter_name_variant: str,
    parameter_description_variant: str,
    rule_wording_variant: str,
    baseline_c: float | None,
    word: str,
    model_key: str,
) -> str:
    word_label = word or "no_word"
    c_label = "none" if baseline_c is None else str(baseline_c).replace(".", "p")
    parts = [
        condition_id,
        state_variant_id,
        context_id,
        prompt_template_id,
        rule_location,
        f"order_{parameter_order_id}",
        f"tool_{tool_name_variant}",
        f"names_{parameter_name_variant}",
        f"desc_{parameter_description_variant}",
        f"wording_{rule_wording_variant}",
        f"c_{c_label}",
        word_label,
        model_key,
    ]
    return "__".join(safe_id(part) for part in parts)


def safe_id(value: Any) -> str:
    text = str(value)
    safe_chars = []
    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    return "".join(safe_chars)


def make_resume_key(cell: ExpandedCell, run_number: int) -> str:
    payload = {
        "config_hash": cell.metadata["config_hash"],
        "batch_id": cell.batch_id,
        "condition_id": cell.condition_id,
        "state_variant": cell.state_variant,
        "rule_location": cell.metadata["rule_location"],
        "rule_wording_variant": cell.metadata["rule_wording_variant"],
        "parameter_order": cell.metadata["parameter_order"],
        "parameter_name_variant": cell.metadata["parameter_name_variant"],
        "parameter_description_variant": cell.metadata["parameter_description_variant"],
        "prompt_template": cell.metadata["prompt_template"],
        "tool_name_variant": cell.metadata["tool_name_variant"],
        "context_id": cell.context_id,
        "baseline_c": cell.baseline_c,
        "word": cell.word,
        "model_key": cell.model_key,
        "temperature": cell.metadata["temperature"],
        "run_number": run_number,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def make_legacy_resume_key(cell: ExpandedCell, run_number: int) -> str:
    payload = {
        "config_hash": cell.metadata["config_hash"],
        "batch_id": cell.batch_id,
        "condition_id": cell.condition_id,
        "state_variant": cell.state_variant,
        "rule_location": cell.metadata["rule_location"],
        "parameter_order": cell.metadata["parameter_order"],
        "prompt_template": cell.metadata["prompt_template"],
        "context_id": cell.context_id,
        "baseline_c": cell.baseline_c,
        "word": cell.word,
        "model_key": cell.model_key,
        "temperature": cell.metadata["temperature"],
        "run_number": run_number,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_run_record(
    cell: ExpandedCell,
    config_path: str,
    run_number: int,
    response: Any | None,
    latency_ms: float | None,
    error: str | None = None,
) -> dict[str, Any]:
    tool_call = response.tool_calls[0] if response and response.tool_calls else None
    tool_input = dict(tool_call.input) if tool_call else {}
    canonical_tool_input, field_sources = canonicalize_tool_input(
        tool_input=tool_input,
        field_name_map=cell.metadata.get("field_name_map", DEFAULT_FIELD_NAME_MAP),
    )
    raw_tool_input = dict(tool_call.raw_input) if tool_call and tool_call.raw_input is not None else None
    required_fields = list(cell.metadata["required_fields"])

    field_a_present = "a" in canonical_tool_input
    field_b_present = "b" in canonical_tool_input
    field_c_present = "c" in canonical_tool_input
    a_output = numeric_or_none(canonical_tool_input.get("a"))
    b_output = numeric_or_none(canonical_tool_input.get("b"))
    c_output = numeric_or_none(canonical_tool_input.get("c"))
    missing_fields = [field for field in required_fields if field not in canonical_tool_input]
    expected_visible = set(cell.tool_schema["function"]["parameters"]["properties"])
    expected_canonical = set(cell.metadata.get("field_name_map", DEFAULT_FIELD_NAME_MAP))
    extra_fields = sorted(field for field in tool_input if field not in expected_visible and field not in expected_canonical)
    fallback_fields = sorted(
        canonical
        for canonical, source in field_sources.items()
        if source == canonical and cell.metadata["field_name_map"].get(canonical) != canonical
    )

    diagnostics = compute_output_diagnostics(
        metadata=cell.metadata,
        a_output=a_output,
        b_output=b_output,
        c_output=c_output,
        field_a_present=field_a_present,
        field_b_present=field_b_present,
        field_c_present=field_c_present,
        missing_fields=missing_fields,
    )

    record: dict[str, Any] = {
        "run_id": str(uuid.uuid4())[:8],
        "resume_key": make_resume_key(cell, run_number),
        "batch_id": cell.batch_id,
        "cell_id": cell.cell_id,
        "batch_index": cell.batch_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_path": config_path,
        "config_hash": cell.metadata["config_hash"],
        "run_number": run_number,
        "prompt_text": cell.prompt_text,
        "tool_schema": cell.tool_schema,
        "tool_call_source": tool_call.source if tool_call else None,
        "tool_call_name": tool_call.name if tool_call else None,
        "tool_call_input": tool_input if tool_call else None,
        "canonical_tool_call_input": canonical_tool_input if tool_call else None,
        "tool_call_raw_input": raw_tool_input,
        "content": response.content if response else None,
        "abstained": bool(response and not response.tool_calls and error is None),
        "error": error,
        "input_tokens": response.usage.get("input_tokens", 0) if response else 0,
        "output_tokens": response.usage.get("output_tokens", 0) if response else 0,
        "latency_ms": latency_ms,
        "field_a_present": field_a_present,
        "field_b_present": field_b_present,
        "field_c_present": field_c_present,
        "field_sources": field_sources,
        "field_name_fallback_fields": fallback_fields,
        "a_output": a_output,
        "b_output": b_output,
        "c_output": c_output,
        "extra_fields": extra_fields,
        "missing_fields": missing_fields,
        "normalization_applied": bool(tool_call and tool_call.normalization_applied),
    }
    record.update(cell.metadata)
    record.update(diagnostics)
    return record


def canonicalize_tool_input(tool_input: dict[str, Any], field_name_map: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    canonical: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for canonical_name, visible_name in field_name_map.items():
        if visible_name in tool_input:
            canonical[canonical_name] = tool_input[visible_name]
            sources[canonical_name] = visible_name
        elif canonical_name in tool_input:
            canonical[canonical_name] = tool_input[canonical_name]
            sources[canonical_name] = canonical_name
    return canonical, sources


def numeric_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def compute_output_diagnostics(
    metadata: dict[str, Any],
    a_output: float | None,
    b_output: float | None,
    c_output: float | None,
    field_a_present: bool,
    field_b_present: bool,
    field_c_present: bool,
    missing_fields: list[str],
) -> dict[str, Any]:
    raw_sum = nullable_sum(a_output, b_output, c_output)
    delta_a = nullable_diff(a_output, metadata["baseline_a"])
    delta_b = nullable_diff(b_output, metadata["baseline_b"])
    delta_c = nullable_diff(c_output, metadata["baseline_c"])
    schema_valid_a = schema_valid(a_output, metadata["schema_a_min"], metadata["schema_a_max"], field_a_present)
    schema_valid_b = schema_valid(b_output, metadata["schema_b_min"], metadata["schema_b_max"], field_b_present)
    schema_valid_c = schema_valid(c_output, metadata["schema_c_min"], metadata["schema_c_max"], field_c_present)
    schema_valid_all = all_schema_valid(
        values=[schema_valid_a, schema_valid_b, schema_valid_c],
        missing_fields=missing_fields,
    )
    strict_only_c = compute_strict_only_c(
        delta_a=delta_a,
        delta_b=delta_b,
        field_a_present=field_a_present,
        field_b_present=field_b_present,
        required_fields=metadata["required_fields"],
    )
    sibling_change_l1 = round(abs(delta_a) + abs(delta_b), 6) if delta_a is not None and delta_b is not None else None
    return {
        "raw_sum": raw_sum,
        "threshold_valid": raw_sum >= 1.0 - TOLERANCE if raw_sum is not None else None,
        "equality_valid": abs(raw_sum - 1.0) <= TOLERANCE if raw_sum is not None else None,
        "schema_valid_a": schema_valid_a,
        "schema_valid_b": schema_valid_b,
        "schema_valid_c": schema_valid_c,
        "schema_valid_all": schema_valid_all,
        "delta_a": delta_a,
        "delta_b": delta_b,
        "delta_c": delta_c,
        "strict_only_c": strict_only_c,
        "sibling_change_l1": sibling_change_l1,
        "c_floor_gap_context": nullable_diff(c_output, metadata["c_required_context"]),
        "c_floor_gap_schema_bound": nullable_diff(c_output, metadata["c_required_schema_bound"]),
    }


def nullable_sum(a_value: float | None, b_value: float | None, c_value: float | None) -> float | None:
    if a_value is None or b_value is None or c_value is None:
        return None
    return round(a_value + b_value + c_value, 6)


def nullable_diff(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(left - right, 6)


def schema_valid(value: float | None, minimum: float | None, maximum: float | None, present: bool) -> bool | None:
    if not present:
        return None
    if value is None:
        return False
    lower_ok = minimum is None or value >= float(minimum) - TOLERANCE
    upper_ok = maximum is None or value <= float(maximum) + TOLERANCE
    return lower_ok and upper_ok


def all_schema_valid(values: list[bool | None], missing_fields: list[str]) -> bool:
    if missing_fields:
        return False
    return all(value is not False for value in values)


def compute_strict_only_c(
    delta_a: float | None,
    delta_b: float | None,
    field_a_present: bool,
    field_b_present: bool,
    required_fields: list[str],
) -> bool | None:
    required_a_or_b = "a" in required_fields or "b" in required_fields
    if not field_a_present and not field_b_present and not required_a_or_b:
        return True
    if delta_a is None or delta_b is None:
        return None
    return abs(delta_a) <= TOLERANCE and abs(delta_b) <= TOLERANCE
