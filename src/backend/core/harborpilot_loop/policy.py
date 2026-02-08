import json
import os
from copy import deepcopy
from typing import Any, Dict, Tuple


DEFAULT_POLICY: Dict[str, Any] = {
    "version": 1,
    "repair": {
        "auto_repair": True,
        "max_attempts": 1,
        "reviewer_enabled": True,
        "reviewer_rounds": 1,
        "rollback_on_fail": True,
    },
    "risk": {
        "block_threshold": 0,
        "rollback_on_block": True,
    },
    "evidence": {
        "verbosity": "summary",
        "write_enabled": True,
    },
    "rag": {
        "enabled": True,
        "topk": 5,
    },
    "memory": {
        "enabled": True,
        "backend": "lancedb",
        "store_enabled": True,
        "store_every": 1,
        "store_on_accept": False,
    },
    "io": {
        "jsonl_buffered": True,
        "flush_interval_sec": 1.0,
        "flush_batch": 50,
        "max_buffer": 2000,
    },
    "budgets": {
        "max_tool_rounds": 6,
        "max_total_lines_read": 1200,
    },
    "qa": {
        "enabled": True,
        "default_tools": True,
    },
    "context": {
        "pm_tasks_max_chars": 8000,
        "known_files_max_chars": 2000,
        "last_result_max_chars": 2000,
        "tool_output_max_chars": 9000,
        "planner_output_max_chars": 6000,
        "ollama_output_max_chars": 6000,
    },
}


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off"):
            return False
    return default


def _coerce_int(value: Any, default: int, min_value: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed >= min_value else default


def _coerce_float(value: Any, default: float, min_value: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if parsed >= min_value else default


def _coerce_enum(value: Any, default: str, options: Tuple[str, ...]) -> str:
    if isinstance(value, str) and value in options:
        return value
    return default


def _sanitize_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    clean = deepcopy(DEFAULT_POLICY)
    _merge_policy(clean, policy)
    clean["version"] = 1

    repair = clean["repair"]
    repair["auto_repair"] = _coerce_bool(repair.get("auto_repair"), True)
    repair["max_attempts"] = _coerce_int(repair.get("max_attempts"), 1, 0)
    repair["reviewer_enabled"] = _coerce_bool(repair.get("reviewer_enabled"), True)
    repair["reviewer_rounds"] = _coerce_int(repair.get("reviewer_rounds"), 1, 0)
    repair["rollback_on_fail"] = _coerce_bool(repair.get("rollback_on_fail"), True)

    risk = clean["risk"]
    risk["block_threshold"] = _coerce_int(risk.get("block_threshold"), 0, 0)
    risk["rollback_on_block"] = _coerce_bool(risk.get("rollback_on_block"), True)
    if not isinstance(risk.get("relaxed_repos"), list):
        risk["relaxed_repos"] = []

    evidence = clean["evidence"]
    evidence["verbosity"] = _coerce_enum(evidence.get("verbosity"), "summary", ("summary", "full"))
    evidence["write_enabled"] = _coerce_bool(evidence.get("write_enabled"), True)

    rag = clean["rag"]
    rag["enabled"] = _coerce_bool(rag.get("enabled"), True)
    rag["topk"] = _coerce_int(rag.get("topk"), 5, 0)

    memory = clean["memory"]
    memory["enabled"] = _coerce_bool(memory.get("enabled"), True)
    memory["backend"] = _coerce_enum(
        memory.get("backend"),
        "lancedb",
        ("lancedb", "file", "both", "none"),
    )
    memory["store_enabled"] = _coerce_bool(memory.get("store_enabled"), True)
    memory["store_every"] = _coerce_int(memory.get("store_every"), 1, 1)
    memory["store_on_accept"] = _coerce_bool(memory.get("store_on_accept"), False)
    if not memory.get("enabled"):
        memory["backend"] = "none"

    io_cfg = clean["io"]
    io_cfg["jsonl_buffered"] = _coerce_bool(io_cfg.get("jsonl_buffered"), True)
    io_cfg["flush_interval_sec"] = _coerce_float(io_cfg.get("flush_interval_sec"), 1.0, 0.1)
    io_cfg["flush_batch"] = _coerce_int(io_cfg.get("flush_batch"), 50, 1)
    io_cfg["max_buffer"] = _coerce_int(io_cfg.get("max_buffer"), 2000, 10)

    budgets = clean["budgets"]
    budgets["max_tool_rounds"] = _coerce_int(budgets.get("max_tool_rounds"), 6, 1)
    budgets["max_total_lines_read"] = _coerce_int(budgets.get("max_total_lines_read"), 1200, 200)

    qa = clean["qa"]
    qa["enabled"] = _coerce_bool(qa.get("enabled"), True)
    qa["default_tools"] = _coerce_bool(qa.get("default_tools"), True)

    context = clean["context"]
    context["pm_tasks_max_chars"] = _coerce_int(context.get("pm_tasks_max_chars"), 8000, 0)
    context["known_files_max_chars"] = _coerce_int(context.get("known_files_max_chars"), 2000, 0)
    context["last_result_max_chars"] = _coerce_int(context.get("last_result_max_chars"), 2000, 0)
    context["tool_output_max_chars"] = _coerce_int(context.get("tool_output_max_chars"), 9000, 0)
    context["planner_output_max_chars"] = _coerce_int(context.get("planner_output_max_chars"), 6000, 0)
    context["ollama_output_max_chars"] = _coerce_int(context.get("ollama_output_max_chars"), 6000, 0)

    return clean


def _merge_policy(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    if not isinstance(override, dict):
        return
    for key, value in override.items():
        if key not in base:
            continue
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            _merge_policy(base[key], value)
        else:
            if value is None:
                continue
            base[key] = value


def _build_source_map(policy: Dict[str, Any], source: str, prefix: str = "") -> Dict[str, str]:
    sources: Dict[str, str] = {}
    for key, value in policy.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            sources.update(_build_source_map(value, source, path + "."))
        else:
            sources[path] = source
    return sources


def _merge_with_sources(
    base: Dict[str, Any],
    override: Dict[str, Any],
    sources: Dict[str, str],
    source: str,
    prefix: str = "",
) -> None:
    if not isinstance(override, dict):
        return
    for key, value in override.items():
        if key not in base:
            continue
        path = f"{prefix}{key}"
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            _merge_with_sources(base[key], value, sources, source, path + ".")
        else:
            if value is None:
                continue
            base[key] = value
            sources[path] = source


def load_policy_file(path: str) -> Dict[str, Any]:
    if not path:
        return {}
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def build_env_overrides() -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    io_cfg: Dict[str, Any] = {}
    if "HARBORPILOT_JSONL_BUFFERED" in os.environ:
        io_cfg["jsonl_buffered"] = os.environ.get("HARBORPILOT_JSONL_BUFFERED")
    if "HARBORPILOT_JSONL_FLUSH_INTERVAL" in os.environ:
        io_cfg["flush_interval_sec"] = os.environ.get("HARBORPILOT_JSONL_FLUSH_INTERVAL")
    if "HARBORPILOT_JSONL_FLUSH_BATCH" in os.environ:
        io_cfg["flush_batch"] = os.environ.get("HARBORPILOT_JSONL_FLUSH_BATCH")
    if "HARBORPILOT_JSONL_MAX_BUFFER" in os.environ:
        io_cfg["max_buffer"] = os.environ.get("HARBORPILOT_JSONL_MAX_BUFFER")
    if io_cfg:
        overrides["io"] = io_cfg
    if "HARBORPILOT_RAG_TOPK" in os.environ:
        overrides.setdefault("rag", {})["topk"] = os.environ.get("HARBORPILOT_RAG_TOPK")
    if "HARBORPILOT_MEMORY_ENABLED" in os.environ:
        overrides.setdefault("memory", {})["enabled"] = os.environ.get("HARBORPILOT_MEMORY_ENABLED")
    if "HARBORPILOT_MEMORY_BACKEND" in os.environ:
        overrides.setdefault("memory", {})["backend"] = os.environ.get("HARBORPILOT_MEMORY_BACKEND")
    if "HARBORPILOT_MEMORY_STORE_ENABLED" in os.environ:
        overrides.setdefault("memory", {})["store_enabled"] = os.environ.get("HARBORPILOT_MEMORY_STORE_ENABLED")
    if "HARBORPILOT_MEMORY_STORE_EVERY" in os.environ:
        overrides.setdefault("memory", {})["store_every"] = os.environ.get("HARBORPILOT_MEMORY_STORE_EVERY")
    if "HARBORPILOT_MEMORY_STORE_ON_ACCEPT" in os.environ:
        overrides.setdefault("memory", {})["store_on_accept"] = os.environ.get("HARBORPILOT_MEMORY_STORE_ON_ACCEPT")
    if "HARBORPILOT_QA_ENABLED" in os.environ:
        overrides.setdefault("qa", {})["enabled"] = os.environ.get("HARBORPILOT_QA_ENABLED")
    return overrides


def extract_task_policy_overrides(pm_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(pm_payload, dict):
        return {}
    override = pm_payload.get("policy_overrides")
    if isinstance(override, dict):
        return override
    tasks = pm_payload.get("tasks")
    if isinstance(tasks, list) and tasks:
        first = tasks[0]
        if isinstance(first, dict) and isinstance(first.get("policy_overrides"), dict):
            return first.get("policy_overrides")
    return {}


def build_cli_overrides(argv: list[str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    bool_map = {
        "--auto-repair": ("repair", "auto_repair", True),
        "--no-auto-repair": ("repair", "auto_repair", False),
        "--reviewer": ("repair", "reviewer_enabled", True),
        "--no-reviewer": ("repair", "reviewer_enabled", False),
        "--rollback-on-fail": ("repair", "rollback_on_fail", True),
        "--no-rollback-on-fail": ("repair", "rollback_on_fail", False),
        "--qa": ("qa", "enabled", True),
        "--no-qa": ("qa", "enabled", False),
        "--default-tools": ("qa", "default_tools", True),
        "--no-default-tools": ("qa", "default_tools", False),
    }
    value_map = {
        "--repair-rounds": ("repair", "max_attempts"),
        "--max-repair-attempts": ("repair", "max_attempts"),
        "--reviewer-rounds": ("repair", "reviewer_rounds"),
        "--risk-block-threshold": ("risk", "block_threshold"),
        "--evidence-verbosity": ("evidence", "verbosity"),
        "--rag-topk": ("rag", "topk"),
        "--memory-backend": ("memory", "backend"),
    }
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in bool_map:
            group, key, value = bool_map[token]
            overrides.setdefault(group, {})[key] = value
            i += 1
            continue
        if token in value_map:
            group, key = value_map[token]
            value = None
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                value = argv[i + 1]
                i += 2
            else:
                i += 1
            if value is not None:
                overrides.setdefault(group, {})[key] = value
            continue
        if token.startswith("--") and "=" in token:
            flag, raw = token.split("=", 1)
            if flag in value_map:
                group, key = value_map[flag]
                overrides.setdefault(group, {})[key] = raw
        i += 1
    return overrides


def build_base_policy(policy_path: str, cli_overrides: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    policy = deepcopy(DEFAULT_POLICY)
    sources = _build_source_map(policy, "default")
    env_overrides = build_env_overrides()
    _merge_with_sources(policy, env_overrides, sources, "env")
    file_overrides = load_policy_file(policy_path)
    _merge_with_sources(policy, file_overrides, sources, "policy_file")
    _merge_with_sources(policy, cli_overrides, sources, "cli")
    policy = _sanitize_policy(policy)
    return policy, sources


def apply_overrides(
    base_policy: Dict[str, Any],
    base_sources: Dict[str, str],
    overrides: Dict[str, Any],
    source_label: str,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    policy = deepcopy(base_policy)
    sources = dict(base_sources)
    _merge_with_sources(policy, overrides, sources, source_label)
    policy = _sanitize_policy(policy)
    return policy, sources


def apply_task_overrides(
    base_policy: Dict[str, Any],
    base_sources: Dict[str, str],
    task_overrides: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    return apply_overrides(base_policy, base_sources, task_overrides, "task_override")
