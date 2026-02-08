import os
from typing import Any, Dict

from io_utils import configure_jsonl_buffer, ensure_memory_dir, read_memory_snapshot


def _safe_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def apply_policy_to_state(state: Any, policy: Dict[str, Any]) -> None:
    if not isinstance(policy, dict):
        return
    repair = policy.get("repair", {}) if isinstance(policy.get("repair"), dict) else {}
    risk = policy.get("risk", {}) if isinstance(policy.get("risk"), dict) else {}
    evidence = policy.get("evidence", {}) if isinstance(policy.get("evidence"), dict) else {}
    rag = policy.get("rag", {}) if isinstance(policy.get("rag"), dict) else {}
    memory = policy.get("memory", {}) if isinstance(policy.get("memory"), dict) else {}
    budgets = policy.get("budgets", {}) if isinstance(policy.get("budgets"), dict) else {}
    qa_cfg = policy.get("qa", {}) if isinstance(policy.get("qa"), dict) else {}
    context = policy.get("context", {}) if isinstance(policy.get("context"), dict) else {}
    io_cfg = policy.get("io", {}) if isinstance(policy.get("io"), dict) else {}

    if "auto_repair" in repair:
        state.auto_repair = bool(repair.get("auto_repair"))
    if "max_attempts" in repair:
        state.repair_rounds = _safe_int(repair.get("max_attempts"), state.repair_rounds)
    if "reviewer_enabled" in repair:
        state.reviewer_enabled = bool(repair.get("reviewer_enabled"))
    if "reviewer_rounds" in repair:
        state.reviewer_rounds = _safe_int(repair.get("reviewer_rounds"), state.reviewer_rounds)
    if "rollback_on_fail" in repair:
        state.rollback_on_fail = bool(repair.get("rollback_on_fail"))

    if "block_threshold" in risk:
        state.risk_block_threshold = _safe_int(risk.get("block_threshold"), state.risk_block_threshold)
    if "rollback_on_block" in risk:
        state.rollback_on_block = bool(risk.get("rollback_on_block"))

    if "verbosity" in evidence:
        state.evidence_verbosity = str(evidence.get("verbosity") or state.evidence_verbosity)
    if "write_enabled" in evidence:
        state.evidence_write_enabled = bool(evidence.get("write_enabled"))

    if "topk" in rag:
        state.rag_topk = _safe_int(rag.get("topk"), state.rag_topk)
        if state.rag_topk > 0:
            os.environ["HARBORPILOT_RAG_TOPK"] = str(state.rag_topk)

    if "enabled" in memory:
        state.memory_enabled = bool(memory.get("enabled"))
    if "backend" in memory:
        state.memory_backend = str(memory.get("backend") or state.memory_backend).lower()
        if state.memory_backend in ("none", "off", "disabled", "false", "0"):
            state.memory_enabled = False
    if "store_enabled" in memory:
        state.memory_store_enabled = bool(memory.get("store_enabled"))
    if "store_every" in memory:
        state.memory_store_every = _safe_int(memory.get("store_every"), state.memory_store_every)
    if "store_on_accept" in memory:
        state.memory_store_on_accept = bool(memory.get("store_on_accept"))
    if state.memory_enabled and state.memory_dir_full:
        ensure_memory_dir(state.memory_dir_full)
        if state.memory_snapshot is None:
            state.memory_snapshot = read_memory_snapshot(state.memory_snapshot_path)

    if "max_tool_rounds" in budgets:
        state.budget_max_rounds = _safe_int(budgets.get("max_tool_rounds"), state.budget_max_rounds)
    if "max_total_lines_read" in budgets:
        state.budget_max_lines = _safe_int(budgets.get("max_total_lines_read"), state.budget_max_lines)

    if "default_tools" in qa_cfg:
        state.default_tools_enabled = bool(qa_cfg.get("default_tools"))
    if "enabled" in qa_cfg:
        state.qa_enabled = bool(qa_cfg.get("enabled"))

    if "pm_tasks_max_chars" in context:
        state.context_pm_tasks_max_chars = _safe_int(context.get("pm_tasks_max_chars"), state.context_pm_tasks_max_chars)
    if "known_files_max_chars" in context:
        state.context_known_files_max_chars = _safe_int(context.get("known_files_max_chars"), state.context_known_files_max_chars)
    if "last_result_max_chars" in context:
        state.context_last_result_max_chars = _safe_int(context.get("last_result_max_chars"), state.context_last_result_max_chars)
    if "tool_output_max_chars" in context:
        state.context_tool_output_max_chars = _safe_int(context.get("tool_output_max_chars"), state.context_tool_output_max_chars)
    if "planner_output_max_chars" in context:
        state.context_planner_output_max_chars = _safe_int(context.get("planner_output_max_chars"), state.context_planner_output_max_chars)
    if "ollama_output_max_chars" in context:
        state.context_ollama_output_max_chars = _safe_int(context.get("ollama_output_max_chars"), state.context_ollama_output_max_chars)

    configure_jsonl_buffer(
        buffered=io_cfg.get("jsonl_buffered"),
        flush_interval_sec=io_cfg.get("flush_interval_sec"),
        flush_batch=io_cfg.get("flush_batch"),
        max_buffer=io_cfg.get("max_buffer"),
    )
