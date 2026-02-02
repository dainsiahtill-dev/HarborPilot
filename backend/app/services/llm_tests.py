from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..config import Settings
from ..llm import config as llm_config
from ..llm.providers import (
    cli_health,
    cli_list_models,
    cli_invoke,
    ollama_health,
    ollama_list_models,
    ollama_invoke,
    openai_health,
    openai_list_models,
    openai_invoke,
    anthropic_health,
    anthropic_list_models,
    anthropic_invoke,
)
from ..llm.types import InvokeResult, ModelListResult, estimate_usage
from ..utils import _extract_json_block, build_cache_root, resolve_artifact_path, write_text_atomic, ensure_loop_modules


def run_llm_tests(
    settings: Settings,
    role: str,
    provider_id: str,
    model: str,
    suites: List[str],
    test_level: str,
    api_key: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    config = llm_config.load_llm_config(workspace, cache_root, settings=settings)
    provider_cfg = _resolve_provider(config, provider_id)
    if not api_key and provider_cfg.get("api_key"):
        api_key = str(provider_cfg.get("api_key") or "")
    if extra_headers:
        provider_cfg = {**provider_cfg, "headers": {**(provider_cfg.get("headers") or {}), **extra_headers}}
    run_id = _new_test_run_id()
    timestamp = _utc_now()
    report: Dict[str, Any] = {
        "schema_version": 1,
        "test_run_id": run_id,
        "timestamp": timestamp,
        "target": {"role": role, "provider_id": provider_id, "model": model},
        "suites": {},
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated": False},
        "final": {"ready": False, "grade": "FAIL", "next_action": "adjust_profile_or_model"},
    }

    events_path = _events_path(settings, workspace, cache_root)
    _emit_event(events_path, "llm_test.start", role, run_id, {"role": role, "provider_id": provider_id, "model": model})

    suite_results: Dict[str, Any] = {}
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated": False}
    transcript_entries: List[str] = []

    for suite in suites:
        suite = suite.strip().lower()
        if suite == "connectivity":
            result = _run_connectivity_suite(provider_cfg, model, api_key)
        elif suite == "response":
            result = _run_response_suite(provider_cfg, model, api_key, role, events_path, run_id)
        elif suite == "qualification":
            result = _run_qualification_suite(provider_cfg, model, api_key, role, test_level, events_path, run_id)
        else:
            result = {"ok": False, "details": {"error": f"unknown suite: {suite}"}}
        suite_results[suite] = result
        _emit_event(events_path, "llm_test.suite_result", role, run_id, {"suite": suite, "result": result})
        _update_usage(usage_total, result)
        transcript_entries.extend(_suite_transcript(suite, result))

    required = config.get("policies", {}).get("test_required_suites") or ["connectivity", "response", "qualification"]
    ready = all(bool(suite_results.get(name, {}).get("ok")) for name in required)
    report["suites"] = suite_results
    report["usage"] = usage_total
    report["final"] = {
        "ready": ready,
        "grade": "PASS" if ready else "FAIL",
        "next_action": "ready" if ready else "adjust_profile_or_model",
    }

    _write_report(settings, cache_root, run_id, report, transcript_entries)
    _update_index(settings, cache_root, role, report)
    _emit_event(events_path, "llm_test.complete", role, run_id, report["final"])
    return report


def _resolve_provider(config: Dict[str, Any], provider_id: str) -> Dict[str, Any]:
    providers = config.get("providers") or {}
    provider_cfg = providers.get(provider_id)
    if not isinstance(provider_cfg, dict):
        raise ValueError(f"provider not found: {provider_id}")
    return provider_cfg


def _run_connectivity_suite(provider_cfg: Dict[str, Any], model: str, api_key: Optional[str]) -> Dict[str, Any]:
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    health = _provider_health(provider_type, provider_cfg, api_key)
    model_available = {"ok": True, "supported": False, "models": []}
    if health.get("ok"):
        listing = _provider_list_models(provider_type, provider_cfg, api_key)
        model_available = listing.to_dict()
        if listing.supported and listing.ok:
            model_available["has_model"] = any(m.id == model for m in listing.models)
        elif listing.supported:
            model_available["has_model"] = False
    ok = bool(health.get("ok")) and (not model_available.get("supported") or model_available.get("has_model", False))
    return {
        "ok": ok,
        "details": {
            "health": health,
            "model_available": model_available,
        },
    }


def _run_response_suite(
    provider_cfg: Dict[str, Any],
    model: str,
    api_key: Optional[str],
    role: str,
    events_path: str,
    run_id: str,
) -> Dict[str, Any]:
    prompt = "Reply with the single word OK."
    result = _provider_invoke(
        provider_cfg,
        model,
        prompt,
        api_key,
        role=role,
        suite="response",
        events_path=events_path,
        run_id=run_id,
    )
    output = result.output.strip()
    ok = result.ok and ("ok" in output.lower())
    return {
        "ok": ok,
        "details": {
            "prompt": prompt,
            "output": _truncate(output, 800),
            "latency_ms": result.latency_ms,
            "usage": result.usage.to_dict(),
        },
    }


def _run_qualification_suite(
    provider_cfg: Dict[str, Any],
    model: str,
    api_key: Optional[str],
    role: str,
    test_level: str,
    events_path: str,
    run_id: str,
) -> Dict[str, Any]:
    cases = _qualification_cases(role, test_level)
    results: List[Dict[str, Any]] = []
    ok_all = True
    for case in cases:
        result = _provider_invoke(
            provider_cfg,
            model,
            case["prompt"],
            api_key,
            role=role,
            suite="qualification",
            events_path=events_path,
            run_id=run_id,
        )
        ok, reason = case["validator"](result.output)
        if not result.ok:
            ok = False
            reason = result.error or "invoke failed"
        ok_all = ok_all and ok
        results.append(
            {
                "id": case["id"],
                "ok": ok,
                "reason": reason,
                "prompt": case["prompt"],
                "output": _truncate(result.output, 1200),
                "usage": result.usage.to_dict(),
                "latency_ms": result.latency_ms,
            }
        )
    return {"ok": ok_all, "cases": results}


def _provider_health(provider_type: str, provider_cfg: Dict[str, Any], api_key: Optional[str]) -> Dict[str, Any]:
    if provider_type == "cli":
        return cli_health(provider_cfg).to_dict()
    if provider_type == "ollama":
        return ollama_health(provider_cfg).to_dict()
    if provider_type == "openai_compat":
        return openai_health(provider_cfg, api_key).to_dict()
    if provider_type == "anthropic_compat":
        return anthropic_health(provider_cfg, api_key).to_dict()
    return {"ok": False, "latency_ms": 0, "error": f"unsupported provider type: {provider_type}"}


def _provider_list_models(provider_type: str, provider_cfg: Dict[str, Any], api_key: Optional[str]) -> ModelListResult:
    if provider_type == "cli":
        return cli_list_models(provider_cfg)
    if provider_type == "ollama":
        return ollama_list_models(provider_cfg)
    if provider_type == "openai_compat":
        return openai_list_models(provider_cfg, api_key)
    if provider_type == "anthropic_compat":
        return anthropic_list_models(provider_cfg, api_key)
    return ModelListResult(ok=False, supported=False, models=[], error="unsupported provider type")


def _provider_invoke(
    provider_cfg: Dict[str, Any],
    model: str,
    prompt: str,
    api_key: Optional[str],
    *,
    role: str,
    suite: str,
    events_path: str,
    run_id: str,
) -> InvokeResult:
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    result: InvokeResult
    if provider_type == "cli":
        result = cli_invoke(prompt, model, provider_cfg)
    elif provider_type == "ollama":
        result = ollama_invoke(prompt, model, provider_cfg)
    elif provider_type == "openai_compat":
        result = openai_invoke(prompt, model, provider_cfg, api_key)
    elif provider_type == "anthropic_compat":
        result = anthropic_invoke(prompt, model, provider_cfg, api_key)
    else:
        result = InvokeResult(ok=False, output="", latency_ms=0, usage=estimate_usage(prompt, ""), error="unsupported provider")
    _track_usage_event(result, model, provider_type, role, suite, events_path, run_id)
    return result


def _track_usage_event(
    result: InvokeResult,
    model: str,
    provider_type: str,
    role: str,
    suite: str,
    events_path: str,
    run_id: str,
) -> None:
    ensure_loop_modules()
    try:
        from usage import UsageContext, TokenUsage, track_usage  # type: ignore
    except Exception:
        return
    try:
        context = UsageContext(
            run_id=run_id,
            task_id=f"{role}:{suite}",
            phase="llm_test",
            mode="setup",
            actor=role,
        )
        usage_obj = TokenUsage(
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
            estimated=result.usage.estimated,
            prompt_chars=result.usage.prompt_chars,
            completion_chars=result.usage.completion_chars,
        )
        if events_path:
            track_usage(events_path, context, model, provider_type, usage_obj, result.latency_ms, ok=result.ok, error=result.error)
    except Exception:
        return


def _qualification_cases(role: str, test_level: str) -> List[Dict[str, Any]]:
    role = role.strip().lower()
    quick = test_level.strip().lower() == "quick"
    if role == "pm":
        cases = [
            {
                "id": "pm-plan-json",
                "prompt": (
                    "You are a PM. Return JSON only.\n"
                    "Requirement: Add a settings page that shows build version.\n"
                    "Return keys: overall_goal (string), tasks (array 1-3), acceptance_criteria (array >=2).\n"
                ),
                "validator": _validate_pm_plan_json,
            },
            {
                "id": "pm-no-hallucination",
                "prompt": (
                    "You can only reference files from this list:\n"
                    "- docs/agent/README.md\n- src/app.ts\n- tests/test_basic.py\n"
                    "List files you would inspect. Do not mention any other paths."
                ),
                "validator": _validate_no_hallucinated_paths,
            },
        ]
    elif role == "director":
        cases = [
            {
                "id": "dir-evidence-first",
                "prompt": (
                    "Before acting, list evidence you must read. Do NOT propose code changes.\n"
                    "Provide an evidence checklist only."
                ),
                "validator": _validate_director_evidence,
            },
            {
                "id": "dir-safe-scope",
                "prompt": (
                    "Policy: Never modify docs/ or scripts/. "
                    "Provide a safe execution plan without forbidden paths."
                ),
                "validator": _validate_director_safe_scope,
            },
        ]
    elif role == "qa":
        cases = [
            {
                "id": "qa-passfail",
                "prompt": (
                    "Test output:\n"
                    "FAIL: test_user_flow\n"
                    "AssertionError: expected 200 got 500\n"
                    "Summarize with PASS or FAIL and cite the failing line."
                ),
                "validator": _validate_qa_passfail,
            },
            {
                "id": "qa-json-acceptance",
                "prompt": (
                    "Return JSON only: {\"pass\": boolean, \"reasons\": string[], \"evidence_refs\": string[]}.\n"
                    "Input: One test failed due to timeout."
                ),
                "validator": _validate_qa_json,
            },
        ]
    else:
        cases = [
            {
                "id": "docs-template",
                "prompt": (
                    "Fill the template. Do not add new headings.\n"
                    "## Overview\n- TBD\n\n"
                    "## Steps\n1. TBD\n"
                ),
                "validator": _validate_docs_template,
            },
        ]
    return cases[:1] if quick else cases


def _validate_pm_plan_json(output: str) -> Tuple[bool, str]:
    data = _extract_json_block(output or "")
    if not isinstance(data, dict):
        return False, "invalid JSON"
    if not isinstance(data.get("overall_goal"), str):
        return False, "missing overall_goal"
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not (1 <= len(tasks) <= 3):
        return False, "tasks must be 1-3 items"
    ac = data.get("acceptance_criteria")
    if not isinstance(ac, list) or len(ac) < 2:
        return False, "acceptance_criteria must have >=2 items"
    return True, "ok"


def _validate_no_hallucinated_paths(output: str) -> Tuple[bool, str]:
    allowed = {"docs/agent/README.md", "src/app.ts", "tests/test_basic.py"}
    paths = _extract_paths(output)
    extra = [p for p in paths if p not in allowed]
    if extra:
        return False, f"hallucinated paths: {', '.join(extra)}"
    return True, "ok"


def _validate_director_evidence(output: str) -> Tuple[bool, str]:
    lowered = (output or "").lower()
    if "evidence" not in lowered and "file" not in lowered:
        return False, "missing evidence list"
    if re.search(r"\b(diff|patch|apply|modify)\b", lowered):
        return False, "contains action directives"
    if not _extract_paths(output):
        return False, "no file evidence listed"
    return True, "ok"


def _validate_director_safe_scope(output: str) -> Tuple[bool, str]:
    lowered = (output or "").lower()
    if "docs/" in lowered or "scripts/" in lowered:
        return False, "forbidden path mentioned"
    return True, "ok"


def _validate_qa_passfail(output: str) -> Tuple[bool, str]:
    lowered = (output or "").lower()
    if "fail" not in lowered:
        return False, "missing FAIL verdict"
    if "test_user_flow" not in output:
        return False, "missing failure evidence"
    return True, "ok"


def _validate_qa_json(output: str) -> Tuple[bool, str]:
    data = _extract_json_block(output or "")
    if not isinstance(data, dict):
        return False, "invalid JSON"
    if not isinstance(data.get("pass"), bool):
        return False, "pass must be boolean"
    if not isinstance(data.get("reasons"), list):
        return False, "reasons must be array"
    if not isinstance(data.get("evidence_refs"), list):
        return False, "evidence_refs must be array"
    return True, "ok"


def _validate_docs_template(output: str) -> Tuple[bool, str]:
    headings = re.findall(r"^##\s+(.+)$", output or "", flags=re.MULTILINE)
    required = {"Overview", "Steps"}
    if not required.issubset(set(headings)):
        return False, "missing required headings"
    if set(headings) != required:
        return False, "added extra headings"
    return True, "ok"


def _extract_paths(text: str) -> List[str]:
    pattern = re.compile(r"\b[\w./-]+\.(?:md|py|ts|js|json|yaml|yml|txt)\b")
    return list(dict.fromkeys(pattern.findall(text or "")))


def _update_usage(total: Dict[str, Any], suite_result: Dict[str, Any]) -> None:
    if not isinstance(suite_result, dict):
        return
    details = suite_result.get("details") or {}
    if "usage" in details:
        _merge_usage(total, details.get("usage"))
    for case in suite_result.get("cases") or []:
        if isinstance(case, dict) and "usage" in case:
            _merge_usage(total, case.get("usage"))


def _merge_usage(total: Dict[str, Any], usage: Any) -> None:
    if not isinstance(usage, dict):
        return
    total["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
    total["completion_tokens"] += int(usage.get("completion_tokens") or 0)
    total["total_tokens"] += int(usage.get("total_tokens") or 0)
    if usage.get("estimated"):
        total["estimated"] = True


def _suite_transcript(suite: str, result: Dict[str, Any]) -> List[str]:
    entries: List[str] = [f"## {suite.title()} Suite"]
    if suite == "qualification":
        for case in result.get("cases") or []:
            entries.append(f"### Case {case.get('id')}")
            entries.append("Prompt:")
            entries.append(_indent(case.get("prompt", "")))
            entries.append("Response:")
            entries.append(_indent(case.get("output", "")))
            entries.append(f"Result: {'PASS' if case.get('ok') else 'FAIL'} - {case.get('reason')}")
    else:
        details = result.get("details") or {}
        if details.get("prompt"):
            entries.append("Prompt:")
            entries.append(_indent(details.get("prompt", "")))
        if details.get("output"):
            entries.append("Response:")
            entries.append(_indent(details.get("output", "")))
    entries.append("")
    return entries


def _indent(text: str) -> str:
    return "\n".join([f"> {line}" for line in (text or "").splitlines()]) or "> (empty)"


def _write_report(settings: Settings, cache_root: str, run_id: str, report: Dict[str, Any], transcript: List[str]) -> None:
    workspace = settings.workspace
    root = resolve_artifact_path(workspace, cache_root, f".harborpilot/runtime/llm_tests/{run_id}")
    os.makedirs(root, exist_ok=True)
    report_path = os.path.join(root, "LLM_TEST_REPORT.json")
    transcript_path = os.path.join(root, "LLM_TEST_TRANSCRIPT.md")
    _write_json(report_path, report)
    write_text_atomic(transcript_path, "\n".join(transcript))


def _update_index(settings: Settings, cache_root: str, role: str, report: Dict[str, Any]) -> None:
    workspace = settings.workspace
    index_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/llm_tests/index.json")
    data: Dict[str, Any] = {}
    if os.path.isfile(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    roles = data.get("roles")
    if not isinstance(roles, dict):
        roles = {}
    roles[role] = {
        "last_run_id": report.get("test_run_id"),
        "ready": report.get("final", {}).get("ready"),
        "grade": report.get("final", {}).get("grade"),
        "timestamp": report.get("timestamp"),
        "suites": report.get("suites"),
    }
    data["schema_version"] = 1
    data["updated_at"] = _utc_now()
    data["roles"] = roles
    _write_json(index_path, data)


def load_llm_test_index(settings: Settings) -> Dict[str, Any]:
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    index_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/llm_tests/index.json")
    if not os.path.isfile(index_path):
        return {"schema_version": 1, "roles": {}}
    try:
        with open(index_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {"schema_version": 1, "roles": {}}
    except Exception:
        return {"schema_version": 1, "roles": {}}


def reset_llm_test_index(settings: Settings) -> None:
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    index_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/llm_tests/index.json")
    try:
        if os.path.isfile(index_path):
            os.remove(index_path)
    except Exception:
        pass


def _events_path(settings: Settings, workspace: str, cache_root: str) -> str:
    try:
        return resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/events.jsonl")
    except Exception:
        return os.path.join(workspace, ".harborpilot", "runtime", "events.jsonl")


def _emit_event(events_path: str, name: str, role: str, run_id: str, output: Dict[str, Any]) -> None:
    if not events_path:
        return
    ensure_loop_modules()
    try:
        from io_utils import emit_event  # type: ignore
    except Exception:
        return
    try:
        emit_event(
            events_path,
            kind="observation",
            actor=role,
            name=name,
            refs={"run_id": run_id, "role": role},
            summary=f"{name} ({role})",
            output=output,
        )
    except Exception:
        return


def _new_test_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = str(uuid.uuid4())[:4]
    return f"setup-{stamp}-{suffix}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."
