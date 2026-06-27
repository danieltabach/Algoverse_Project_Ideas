"""Static registries for the Paper 2 configurable testbed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model_id: str
    display_name: str
    api_base: str | None = None


OLLAMA_BASE = "http://localhost:11434/v1"

MODELS = {
    "qwen3-8b": ModelConfig("openai", "qwen3:8b", "Qwen3 8B", OLLAMA_BASE),
    "llama3-8b": ModelConfig("openai", "llama3.1:8b", "Llama 3.1 8B", OLLAMA_BASE),
    "gemma4-12b": ModelConfig("openai", "gemma4:12b", "Gemma 4 12B", OLLAMA_BASE),
    "mistral-7b": ModelConfig(
        "openai",
        "mistral:7b-instruct-v0.3-q4_K_M",
        "Mistral 7B Instruct",
        OLLAMA_BASE,
    ),
    "hermes3-8b": ModelConfig("openai", "hermes3:8b", "Hermes 3 8B", OLLAMA_BASE),
    "deepseek-r1-7b": ModelConfig("openai", "deepseek-r1:7b", "DeepSeek R1 7B", OLLAMA_BASE),
}

MODEL_GROUPS = {
    "primary": ["qwen3-8b", "llama3-8b", "gemma4-12b"],
    "robustness": ["mistral-7b", "hermes3-8b"],
}

WORD_SETS = {
    "calibration": ["", "slightly"],
    "minimal": ["", "slightly", "moderately", "drastically"],
    "full": [
        "slightly",
        "marginally",
        "somewhat",
        "mildly",
        "moderately",
        "considerably",
        "substantially",
        "significantly",
        "drastically",
        "dramatically",
        "",
    ],
}

WORD_LEVELS = {
    "": 0,
    "slightly": 1,
    "marginally": 1,
    "somewhat": 2,
    "mildly": 2,
    "moderately": 3,
    "considerably": 4,
    "substantially": 4,
    "significantly": 5,
    "drastically": 6,
    "dramatically": 6,
}

PROMPT_TEMPLATES = {
    "no_baseline": {
        "include_current_state": False,
        "only_change_c": False,
        "instruction": "word_increase",
    },
    "with_baseline_only_change_c": {
        "include_current_state": True,
        "only_change_c": True,
        "instruction": "word_increase",
    },
    "with_baseline_no_only": {
        "include_current_state": True,
        "only_change_c": False,
        "instruction": "word_increase",
    },
    "exact_increase_c_by_0_10": {
        "include_current_state": True,
        "only_change_c": True,
        "instruction": "exact_delta_c",
        "delta_c": 0.10,
    },
    "exact_set_c_0_40": {
        "include_current_state": True,
        "only_change_c": True,
        "instruction": "exact_set_c",
        "target_c": 0.40,
    },
}

BASE_PARAMETERS = {
    "a": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "b": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "c": {"type": "number", "minimum": 0.0, "maximum": 1.0},
}

TIGHT_PARAMETERS = {
    "a": {"type": "number", "minimum": 0.0, "maximum": 0.5},
    "b": {"type": "number", "minimum": 0.0, "maximum": 0.15},
    "c": {"type": "number", "minimum": 0.0, "maximum": 1.0},
}

CLEAN_43_18_PARAMETERS = {
    "a": {"type": "number", "minimum": 0.0, "maximum": 0.43},
    "b": {"type": "number", "minimum": 0.0, "maximum": 0.18},
    "c": {"type": "number", "minimum": 0.0, "maximum": 1.0},
}

SYMMETRIC_TIGHT_PARAMETERS = {
    "a": {"type": "number", "minimum": 0.0, "maximum": 0.5},
    "b": {"type": "number", "minimum": 0.0, "maximum": 0.5},
    "c": {"type": "number", "minimum": 0.0, "maximum": 0.5},
}

BARE_C_PARAMETERS = {
    "c": {"type": "number", "minimum": 0.0, "maximum": 1.0},
}

THRESHOLD_RULE_TEXT = "The total of {a}, {b}, and {c} should be greater than or equal to 1.0."
EQUALITY_RULE_TEXT = "The total of {a}, {b}, and {c} should equal 1.0."

RULE_WORDING_VARIANTS = {
    "default": {
        "gte_1": THRESHOLD_RULE_TEXT,
        "eq_1": EQUALITY_RULE_TEXT,
    },
    "soft": {
        "gte_1": "Try to keep the total of {a}, {b}, and {c} at least 1.0.",
        "eq_1": "Try to keep the total of {a}, {b}, and {c} equal to 1.0.",
    },
    "must": {
        "gte_1": "The total of {a}, {b}, and {c} must be at least 1.0.",
        "eq_1": "The total of {a}, {b}, and {c} must equal 1.0.",
    },
    "symbolic": {
        "gte_1": "{a} + {b} + {c} >= 1.0.",
        "eq_1": "{a} + {b} + {c} = 1.0.",
    },
}

TOOL_NAME_VARIANTS = {
    "neutral": None,
    "set_values": "set_values",
    "set_parameters": "set_parameters",
    "set_allocation": "set_allocation",
}

PARAMETER_NAME_VARIANTS = {
    "canonical_abc": {"a": "a", "b": "b", "c": "c"},
    "generic_xyz": {"a": "x", "b": "y", "c": "z"},
}

PARAMETER_DESCRIPTION_VARIANTS = {
    "none": None,
    "neutral": "Value for {field}.",
    "default_anchor": "Value for {field}. Current/default value is {value}.",
}

CONDITIONS = {
    "no_rule": {
        "layer": 0,
        "relation": "none",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": None,
        "parameters": BASE_PARAMETERS,
    },
    "threshold_gte_1": {
        "layer": 1,
        "relation": "gte_1",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": THRESHOLD_RULE_TEXT,
        "parameters": BASE_PARAMETERS,
    },
    "schema_open_threshold": {
        "layer": 1,
        "relation": "gte_1",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": THRESHOLD_RULE_TEXT,
        "parameters": BASE_PARAMETERS,
    },
    "equality_eq_1": {
        "layer": 2,
        "relation": "eq_1",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": EQUALITY_RULE_TEXT,
        "parameters": BASE_PARAMETERS,
    },
    "schema_tight_threshold": {
        "layer": 1,
        "relation": "gte_1",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": THRESHOLD_RULE_TEXT,
        "parameters": TIGHT_PARAMETERS,
    },
    "schema_tight_no_rule": {
        "layer": 0,
        "relation": "none",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": None,
        "parameters": TIGHT_PARAMETERS,
    },
    "schema_clean43_18_threshold": {
        "layer": 1,
        "relation": "gte_1",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": THRESHOLD_RULE_TEXT,
        "parameters": CLEAN_43_18_PARAMETERS,
    },
    "schema_clean43_18_no_rule": {
        "layer": 0,
        "relation": "none",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": None,
        "parameters": CLEAN_43_18_PARAMETERS,
    },
    "schema_symmetric_tight_no_rule": {
        "layer": 0,
        "relation": "none",
        "tool_name": "set_values",
        "base_tool_description": "Set numeric values for {a}, {b}, and {c}.",
        "rule_text": None,
        "parameters": SYMMETRIC_TIGHT_PARAMETERS,
    },
    "bare_c_no_rule": {
        "layer": 0,
        "relation": "none",
        "tool_name": "set_c",
        "base_tool_description": "Set a numeric value for {c}.",
        "rule_text": None,
        "parameters": BARE_C_PARAMETERS,
    },
}

STATE_VARIANTS = {
    "prompt_state_required": {
        "prompt_contains_state": True,
        "schema_defaults": False,
        "required_fields": ["a", "b", "c"],
    },
    "schema_default_required": {
        "prompt_contains_state": False,
        "schema_defaults": True,
        "required_fields": ["a", "b", "c"],
    },
    "schema_default_optional": {
        "prompt_contains_state": False,
        "schema_defaults": True,
        "required_fields": ["c"],
    },
    "prompt_state_optional": {
        "prompt_contains_state": True,
        "schema_defaults": False,
        "required_fields": ["c"],
    },
    "no_state_required": {
        "prompt_contains_state": False,
        "schema_defaults": False,
        "required_fields": ["a", "b", "c"],
    },
}

VALID_RULE_LOCATIONS = {"tool_description", "user_prompt", "both", "none"}

