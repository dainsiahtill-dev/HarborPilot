from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from context_engine import ContextBudget, ContextEngine, ContextPack, ContextRequest
from sniper_mode import merge_policy, resolve_cost_class, route_by_cost_model


def build_context_window(
    project_root: str,
    role: str,
    query: str,
    step: int,
    run_id: str,
    mode: str,
    *,
    events_path: str = "",
    cost_model: Optional[str] = None,
    sources_enabled: Optional[List[str]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Tuple[ContextPack, Dict[str, Any], ContextBudget, List[str]]:
    policy = dict(policy or {})
    cost_class = resolve_cost_class(cost_model or policy.get("cost_class"))
    strategy = route_by_cost_model(cost_class, role)
    merged_policy = merge_policy(strategy.policy, policy)
    merged_policy["cost_class"] = cost_class

    max_tokens = _coerce_int(merged_policy.get("max_tokens"), strategy.budget.get("max_tokens", 0))
    max_chars = _coerce_int(merged_policy.get("max_chars"), strategy.budget.get("max_chars", 0))
    budget = ContextBudget(max_tokens=max_tokens, max_chars=max_chars, cost_class=cost_class)

    if not sources_enabled:
        if isinstance(merged_policy.get("sources_enabled"), list):
            sources_enabled = list(merged_policy["sources_enabled"])
        else:
            sources_enabled = list(strategy.sources_enabled)

    request = ContextRequest(
        run_id=run_id,
        step=step,
        role=role,
        mode=mode,
        query=query,
        budget=budget,
        sources_enabled=sources_enabled,
        policy=merged_policy,
        events_path=events_path or "",
    )
    engine = ContextEngine(project_root)
    pack = engine.build_context(request)
    return pack, merged_policy, budget, sources_enabled


def _coerce_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return int(default)
    return parsed
