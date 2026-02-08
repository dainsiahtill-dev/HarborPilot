from __future__ import annotations

import asyncio
import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config import Settings
from ..llm import config as llm_config
from ..llm.providers import (
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

THINKING_INDICATORS = [
    "<thinking>",
    "<reasoning>",
    "let me think",
    "step by step",
    "my reasoning",
    "i need to consider",
    "thought process",
    "analysis:",
    "reasoning:",
]

ROLE_REQUIREMENTS = {
    "pm": {
        "requires_thinking": True,
        "min_confidence": 0.7,
        "error_message": "PM 岗位需要具备深度思考能力的模型",
    },
    "director": {
        "requires_thinking": True,
        "min_confidence": 0.7,
        "error_message": "Director 岗位需要具备推理能力的模型",
    },
    "qa": {
        "requires_thinking": False,
        "min_confidence": 0.5,
        "error_message": "QA 岗位建议使用具备思考能力的模型",
    },
    "docs": {
        "requires_thinking": False,
        "min_confidence": 0.5,
        "error_message": "Docs 岗位建议使用具备思考能力的模型",
    },
}

INTERVIEW_QUESTIONS = {
    "pm": [
        {
            "id": "pm-plan",
            "question": "请分析这个项目需求并制定实施计划。",
            "expects_thinking": True,
            "evaluation_criteria": ["分析深度", "计划完整性", "风险评估"],
        },
        {
            "id": "pm-conflict",
            "question": "如何协调开发团队中的技术分歧？",
            "expects_thinking": True,
            "evaluation_criteria": ["思考过程", "解决方案", "沟通策略"],
        },
    ],
    "director": [
        {
            "id": "director-review",
            "question": "审查这段代码并提出改进建议。",
            "expects_thinking": True,
            "evaluation_criteria": ["技术分析", "问题识别", "改进方案"],
        }
    ],
    "qa": [
        {
            "id": "qa-failure",
            "question": "分析测试失败原因。",
            "expects_thinking": False,
            "evaluation_criteria": ["问题定位", "根因分析", "解决建议"],
        }
    ],
    "docs": [
        {
            "id": "docs-guide",
            "question": "为这个功能编写使用文档。",
            "expects_thinking": False,
            "evaluation_criteria": ["文档完整性", "表达清晰度", "示例准确性"],
        }
    ],
}

CRITERIA_KEYWORDS = {
    "分析深度": [
        "分析", "影响", "权衡", "trade", "impact", "scope", "risk", "依赖",
        "评估", "背景", "现状", "目标", "约束", "范围", "取舍", "假设",
        "限制", "成本", "收益", "优先级", "可行性", "复杂度",
    ],
    "计划完整性": [
        "计划", "规划", "步骤", "里程碑", "timeline", "阶段", "deliverable", "路线图",
        "安排", "时间表", "节点", "目标", "执行", "落地", "分工", "资源", "验收",
        "拆解", "优先级", "排期",
    ],
    "风险评估": [
        "风险", "风险点", "缓解", "mitigation", "假设", "依赖", "contingency",
        "预案", "应对", "预防", "阻塞", "fallback", "备选", "兜底", "回滚",
    ],
    "思考过程": ["思考", "reasoning", "考虑", "首先", "其次", "最后", "因为", "因此", "所以", "推理", "分析"],
    "解决方案": ["方案", "解决", "建议", "approach", "fix", "实现", "策略", "措施", "动作", "改造", "优化", "落地", "实施"],
    "沟通策略": ["沟通", "协调", "对齐", "stakeholder", "共识", "反馈", "同步", "会议", "跟进", "汇报", "决策", "澄清", "分歧"],
    "技术分析": ["性能", "架构", "复杂度", "bug", "refactor", "测试", "瓶颈", "兼容", "依赖", "技术债", "稳定性", "可维护", "扩展"],
    "问题识别": ["问题", "缺陷", "风险", "issue", "bug", "异常", "不足", "痛点", "瓶颈"],
    "改进方案": ["改进", "优化", "方案", "refactor", "重构", "改造", "提升", "治理"],
    "问题定位": ["定位", "复现", "log", "trace", "日志", "排查", "监控", "报警", "指标"],
    "根因分析": ["根因", "原因", "because", "root cause", "本质", "触发", "链路", "机制"],
    "解决建议": ["建议", "修复", "fix", "缓解", "解决", "方案", "行动", "措施"],
    "文档完整性": ["安装", "使用", "参数", "示例", "步骤", "说明", "配置", "注意事项", "FAQ", "限制", "依赖"],
    "表达清晰度": ["步骤", "明确", "简洁", "清晰", "结构", "分点", "条理", "层次", "重点"],
    "示例准确性": ["示例", "example", "code", "样例", "片段", "命令", "输入", "输出"],
}

def _env_flag(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


INTERVIEW_SEMANTIC_ENABLED = _env_flag("HARBORPILOT_INTERVIEW_SEMANTIC", True)
INTERVIEW_SEMANTIC_THRESHOLD = _env_float("HARBORPILOT_INTERVIEW_SEMANTIC_THRESHOLD", 0.78)
INTERVIEW_SEMANTIC_MIN_CHARS = _env_int("HARBORPILOT_INTERVIEW_SEMANTIC_MIN_CHARS", 80)
INTERVIEW_SEMANTIC_MAX_CHARS = _env_int("HARBORPILOT_INTERVIEW_SEMANTIC_MAX_CHARS", 2000)
INTERVIEW_SEMANTIC_TIMEOUT = _env_float("HARBORPILOT_INTERVIEW_SEMANTIC_TIMEOUT", 3.0)
INTERVIEW_EMBEDDING_MODEL = os.environ.get(
    "HARBORPILOT_INTERVIEW_EMBEDDING_MODEL",
    os.environ.get("HARBORPILOT_EMBEDDING_MODEL", "nomic-embed-text"),
)
_EMBEDDING_CACHE: Dict[Tuple[str, str], List[float]] = {}
_EMBEDDING_DISABLED = False


def run_llm_tests(
    settings: Settings,
    role: str,
    provider_id: str,
    model: str,
    suites: List[str],
    test_level: str,
    evaluation_mode: Optional[str] = None,
    api_key: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    env_overrides: Optional[Dict[str, str]] = None,
    prompt_override: Optional[str] = None,
) -> Dict[str, Any]:
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    config = llm_config.load_llm_config(workspace, cache_root, settings=settings)
    role = role.strip().lower()
    suites = _normalize_suites(list(suites or []), role, config)
    provider_cfg = _resolve_provider(config, provider_id)
    if not api_key and provider_cfg.get("api_key"):
        api_key = str(provider_cfg.get("api_key") or "")
    if extra_headers:
        provider_cfg = {**provider_cfg, "headers": {**(provider_cfg.get("headers") or {}), **extra_headers}}
    if env_overrides:
        provider_cfg = {**provider_cfg, "env": {**(provider_cfg.get("env") or {}), **env_overrides}}
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
    thinking_snapshot: Optional[Dict[str, Any]] = None

    for suite in suites:
        suite = suite.strip().lower()
        if suite == "connectivity":
            result = _run_connectivity_suite(provider_cfg, model, api_key, None)
        elif suite == "response":
            result = _run_response_suite(
                provider_cfg,
                model,
                api_key,
                role,
                events_path,
                run_id,
                prompt_override,
            )
        elif suite == "qualification":
            result = _run_qualification_suite(provider_cfg, model, api_key, role, test_level, events_path, run_id)
        elif suite == "thinking":
            result = _run_thinking_suite(provider_cfg, model, api_key, role, events_path, run_id)
            thinking_snapshot = _extract_thinking_snapshot(result)
        elif suite == "interview":
            result = _run_interview_suite(
                provider_cfg,
                model,
                api_key,
                role,
                test_level,
                events_path,
                run_id,
                thinking_snapshot,
                config,
            )
        else:
            result = {"ok": False, "details": {"error": f"unknown suite: {suite}"}}
        suite_results[suite] = result
        _emit_event(events_path, "llm_test.suite_result", role, run_id, {"suite": suite, "result": result})
        _update_usage(usage_total, result)
        transcript_entries.extend(_suite_transcript(suite, result))

    evaluation_mode = (evaluation_mode or "").strip().lower()
    if evaluation_mode in ("provider", "run_suites"):
        required = _dedupe([suite for suite in suites if suite != "interview"])
    else:
        required = _required_suites_for_role(config, role)
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


async def run_llm_tests_streaming(
    settings: Settings,
    role: str,
    provider_id: str,
    model: str,
    suites: List[str],
    test_level: str,
    evaluation_mode: Optional[str] = None,
    api_key: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    env_overrides: Optional[Dict[str, str]] = None,
    prompt_override: Optional[str] = None,
    output_queue: Optional[asyncio.Queue] = None,
) -> Dict[str, Any]:
    """Run LLM tests with real-time streaming output
    
    This function runs test suites and streams progress events as each suite completes,
    allowing clients to see real-time results without waiting for all suites to finish.
    
    Args:
        settings: Application settings
        role: Test role
        provider_id: Provider identifier
        model: Model name
        suites: List of test suites to run
        test_level: Test level (quick, full)
        evaluation_mode: Evaluation mode
        api_key: Optional API key
        extra_headers: Optional extra headers
        env_overrides: Optional environment overrides
        prompt_override: Optional prompt override
        output_queue: Optional async queue for streaming events
        
    Returns:
        Final test report dictionary
    """
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    config = llm_config.load_llm_config(workspace, cache_root, settings=settings)
    role = role.strip().lower()
    suites = _normalize_suites(list(suites or []), role, config)
    provider_cfg = _resolve_provider(config, provider_id)
    
    if not api_key and provider_cfg.get("api_key"):
        api_key = str(provider_cfg.get("api_key") or "")
    if extra_headers:
        provider_cfg = {**provider_cfg, "headers": {**(provider_cfg.get("headers") or {}), **extra_headers}}
    if env_overrides:
        provider_cfg = {**provider_cfg, "env": {**(provider_cfg.get("env") or {}), **env_overrides}}
    
    run_id = _new_test_run_id()
    timestamp = _utc_now()
    
    def emit(event_type: str, data: Any):
        event = {"type": event_type, "data": data}
        if output_queue:
            asyncio.create_task(output_queue.put(event))
        else:
            print(f"[STREAM] {event_type}: {json.dumps(data, ensure_ascii=False)[:200]}")
    
    emit("start", {"run_id": run_id, "role": role, "provider_id": provider_id, "model": model, "suites": suites})
    
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
    thinking_snapshot: Optional[Dict[str, Any]] = None
    
    for suite in suites:
        suite = suite.strip().lower()
        emit("suite_start", {"suite": suite})
        
        try:
            if suite == "connectivity":
                result = _run_connectivity_suite(provider_cfg, model, api_key, emit)
            elif suite == "response":
                result = _run_response_suite(
                    provider_cfg,
                    model,
                    api_key,
                    role,
                    events_path,
                    run_id,
                    prompt_override,
                )
            elif suite == "qualification":
                result = _run_qualification_suite(provider_cfg, model, api_key, role, test_level, events_path, run_id)
            elif suite == "thinking":
                result = _run_thinking_suite(provider_cfg, model, api_key, role, events_path, run_id)
                thinking_snapshot = _extract_thinking_snapshot(result)
            elif suite == "interview":
                result = _run_interview_suite(
                    provider_cfg,
                    model,
                    api_key,
                    role,
                    test_level,
                    events_path,
                    run_id,
                    thinking_snapshot,
                    config,
                )
            else:
                result = {"ok": False, "details": {"error": f"unknown suite: {suite}"}}
            
            suite_results[suite] = result
            _emit_event(events_path, "llm_test.suite_result", role, run_id, {"suite": suite, "result": result})
            _update_usage(usage_total, result)
            transcript_entries.extend(_suite_transcript(suite, result))
            
            emit("suite_complete", {"suite": suite, "result": result})
            
        except Exception as exc:
            error_result = {"ok": False, "details": {"error": str(exc)}}
            suite_results[suite] = error_result
            emit("suite_error", {"suite": suite, "error": str(exc)})
    
    evaluation_mode = (evaluation_mode or "").strip().lower()
    if evaluation_mode in ("provider", "run_suites"):
        required = _dedupe([suite for suite in suites if suite != "interview"])
    else:
        required = _required_suites_for_role(config, role)
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
    
    emit("complete", report)
    return report


def _resolve_provider(config: Dict[str, Any], provider_id: str) -> Dict[str, Any]:
    providers = config.get("providers") or {}
    provider_cfg = providers.get(provider_id)
    if not isinstance(provider_cfg, dict):
        raise ValueError(f"provider not found: {provider_id}")
    return provider_cfg


def _normalize_suites(suites: List[str], role: str, config: Dict[str, Any]) -> List[str]:
    cleaned = [s.strip().lower() for s in suites if isinstance(s, str) and s.strip()]
    if not cleaned:
        defaults = config.get("policies", {}).get("test_required_suites") or [
            "connectivity",
            "response",
            "qualification",
        ]
        cleaned = [str(s).strip().lower() for s in defaults if str(s).strip()]
    role_req = _role_requirements(config, role)
    if role_req.get("requires_thinking") and "thinking" not in cleaned:
        cleaned.append("thinking")
    return _dedupe(cleaned)


def _required_suites_for_role(config: Dict[str, Any], role: str) -> List[str]:
    defaults = config.get("policies", {}).get("test_required_suites") or [
        "connectivity",
        "response",
        "qualification",
    ]
    required = [str(s).strip().lower() for s in defaults if str(s).strip()]
    role_req = _role_requirements(config, role)
    if role_req.get("requires_thinking"):
        if "thinking" not in required:
            required.append("thinking")
    else:
        required = [suite for suite in required if suite != "thinking"]
    # Interview reports are informative by default, not gating readiness.
    required = [suite for suite in required if suite != "interview"]
    return _dedupe(required)


def _role_requirements(config: Dict[str, Any], role: str) -> Dict[str, Any]:
    role = role.strip().lower()
    base = ROLE_REQUIREMENTS.get(role, {}).copy()
    policies = config.get("policies", {}) if isinstance(config.get("policies"), dict) else {}
    policy_roles = policies.get("role_requirements") if isinstance(policies, dict) else None
    if isinstance(policy_roles, dict):
        override = policy_roles.get(role)
        if isinstance(override, dict):
            base.update(override)
    return base


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _extract_thinking_snapshot(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict):
        return None
    details = result.get("details")
    if not isinstance(details, dict):
        return None
    thinking = details.get("thinking")
    return thinking if isinstance(thinking, dict) else None


def _run_connectivity_suite(
    provider_cfg: Dict[str, Any], 
    model: str, 
    api_key: Optional[str],
    emit: Optional[Callable[[str, Any], None]] = None,
) -> Dict[str, Any]:
    """Run connectivity suite with simplified health check using chat completion API
    
    This simplified approach directly tests the chat completion API endpoint
    instead of relying on /models endpoint which may not be available for all providers.
    """
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    
    # 发送调试信息
    def _emit_debug(message: str, details: Optional[Dict] = None):
        if emit:
            emit("debug", {"message": message, "details": details or {}})
    
    _emit_debug(f"🔍 开始连通性测试 - 提供商类型: {provider_type}")
    _emit_debug(f"📋 配置信息: base_url={provider_cfg.get('base_url')}, model={model}")
    
    # 执行健康检查（使用对话接口而非/models端点）
    health = _provider_health_with_logging(provider_type, provider_cfg, api_key, model, _emit_debug)
    
    ok = bool(health.get("ok"))
    _emit_debug(f"{'✅' if ok else '❌'} 连通性测试结果: {'通过' if ok else '失败'}")
    
    return {
        "ok": ok,
        "details": {
            "health": health,
        },
    }


def _provider_health_with_logging(
    provider_type: str, 
    provider_cfg: Dict[str, Any], 
    api_key: Optional[str],
    model: str,
    emit_debug: Callable[[str], None],
) -> Dict[str, Any]:
    """Provider health check using chat completion API instead of /models endpoint
    
    This simplified approach sends a minimal test message to verify API connectivity,
    which works for all providers regardless of whether they support /models endpoint.
    """
    import requests
    import time
    
    # 获取配置
    base_url = str(provider_cfg.get("base_url") or "").strip().rstrip(",").rstrip("/")
    api_path = str(provider_cfg.get("api_path") or "/v1/chat/completions").strip()
    
    # 清理 base_url 末尾的非法字符（如逗号、空格等）
    base_url = base_url.rstrip(" ,;。")
    timeout = int(provider_cfg.get("timeout") or 30)
    
    # 构建完整URL（使用对话API路径）
    url = base_url.rstrip("/") + (api_path if api_path.startswith("/") else "/" + api_path)
    
    emit_debug(f"🌐 健康检查请求: POST {url}")
    emit_debug(f"📋 使用模型: {model}")
    
    # 构建 headers
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    emit_debug(f"📤 Request Headers: {json.dumps(headers, ensure_ascii=False)}")
    
    # 构建测试用的最小payload（根据提供商类型调整）
    test_payload = _get_health_check_payload(provider_type, provider_cfg, model)
    emit_debug(f"📤 Request Payload: {json.dumps(test_payload, ensure_ascii=False)}")
    
    start = time.time()
    try:
        response = requests.post(
            url,
            headers=headers,
            json=test_payload,
            timeout=timeout if timeout > 0 else None,
        )
        latency_ms = int((time.time() - start) * 1000)
        
        emit_debug(f"📥 Response Status: {response.status_code}")
        emit_debug(f"📥 Response Headers: {json.dumps(dict(response.headers), ensure_ascii=False)}")
        emit_debug(f"📥 Response Body (前500字符): {response.text[:500]}")
        emit_debug(f"⏱️ 延迟: {latency_ms}ms")
        
        # 检查HTTP状态码
        if response.status_code == 401:
            emit_debug("❌ 认证失败: 请检查API密钥是否正确")
            return {"ok": False, "latency_ms": latency_ms, "error": "Authentication failed: please check your API key"}
        elif response.status_code == 404:
            emit_debug("❌ API路径不存在: 请检查api_path配置")
            return {"ok": False, "latency_ms": latency_ms, "error": "API endpoint not found: please check api_path configuration"}
        elif response.status_code >= 500:
            emit_debug(f"❌ 服务器错误: {response.status_code}")
            return {"ok": False, "latency_ms": latency_ms, "error": f"Server error: {response.status_code}"}
        
        response.raise_for_status()
        
        # 验证响应格式
        try:
            data = response.json()
            # 检查关键字段
            if isinstance(data, dict):
                if "choices" in data or "output" in data or "message" in data or "content" in data:
                    emit_debug("✅ 响应格式验证通过")
                    return {"ok": True, "latency_ms": latency_ms}
                elif "base_resp" in data:  # MiniMax format
                    base_resp = data.get("base_resp", {})
                    if isinstance(base_resp, dict) and base_resp.get("status_code") == 0:
                        emit_debug("✅ MiniMax响应格式验证通过")
                        return {"ok": True, "latency_ms": latency_ms}
                    else:
                        error_msg = base_resp.get("status_msg", "Unknown MiniMax error")
                        emit_debug(f"❌ MiniMax API错误: {error_msg}")
                        return {"ok": False, "latency_ms": latency_ms, "error": error_msg}
        except json.JSONDecodeError:
            emit_debug("⚠️ 响应不是JSON格式，但HTTP状态正常")
            # 非JSON响应但HTTP 200，仍然认为连接成功
            return {"ok": True, "latency_ms": latency_ms}
        
        emit_debug("✅ 健康检查通过")
        return {"ok": True, "latency_ms": latency_ms}
        
    except requests.exceptions.ConnectionError as exc:
        latency_ms = int((time.time() - start) * 1000)
        emit_debug(f"❌ 网络连接失败: {str(exc)}")
        return {"ok": False, "latency_ms": latency_ms, "error": "Network connection failed: please check your network and base_url"}
    except requests.exceptions.Timeout as exc:
        latency_ms = int((time.time() - start) * 1000)
        emit_debug(f"❌ 请求超时: {str(exc)}")
        return {"ok": False, "latency_ms": latency_ms, "error": "Request timeout: the server took too long to respond"}
    except Exception as exc:
        latency_ms = int((time.time() - start) * 1000)
        emit_debug(f"❌ 请求失败: {str(exc)}")
        return {"ok": False, "latency_ms": latency_ms, "error": str(exc)}


def _get_health_check_payload(provider_type: str, provider_cfg: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Get health check payload based on provider type
    
    Different providers may have slightly different requirements for the test payload.
    """
    # 默认使用简单的测试消息
    base_payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
        "max_tokens": 10,
    }
    
    # 根据提供商类型调整
    provider_type = provider_type.lower()
    
    if provider_type == "minimax":
        # MiniMax uses a slightly different format
        return {
            "model": model or "MiniMax-M2.1",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 10,
        }
    elif provider_type == "kimi":
        # Kimi is OpenAI compatible
        return {
            "model": model or "moonshot-v1-8k",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "max_tokens": 10,
        }
    elif provider_type == "ollama":
        # Ollama uses a different format
        return {
            "model": model,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        }
    
    return base_payload


def _provider_list_models_with_logging(
    provider_type: str, 
    provider_cfg: Dict[str, Any], 
    api_key: Optional[str],
    emit_debug: Callable[[str], None],
):
    """Provider list models with detailed HTTP logging
    
    DEPRECATED: This function is kept for backward compatibility but is no longer
    used in the simplified connectivity test. Model listing is now optional.
    """
    import requests
    import time
    from dataclasses import dataclass
    from typing import List
    
    @dataclass
    class ModelInfo:
        id: str
        raw: Dict[str, Any]
    
    @dataclass
    class ModelListResult:
        ok: bool
        supported: bool
        models: List[ModelInfo]
        error: str = ""
        
        def to_dict(self):
            return {
                "ok": self.ok,
                "supported": self.supported,
                "models": [{"id": m.id, "raw": m.raw} for m in self.models],
                "error": self.error,
            }
    
    emit_debug("⚠️ 模型列表获取已弃用，仅保留向后兼容")
    
    # 返回空结果（不再尝试获取模型列表）
    return ModelListResult(ok=True, supported=False, models=[], error="Model listing is deprecated")


def _run_response_suite(
    provider_cfg: Dict[str, Any],
    model: str,
    api_key: Optional[str],
    role: str,
    events_path: str,
    run_id: str,
    prompt_override: Optional[str] = None,
) -> Dict[str, Any]:
    prompt = prompt_override or "Reply with the single word OK."
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
    if prompt_override:
        ok = result.ok and bool(output)
    else:
        ok = result.ok and ("ok" in output.lower())
    details = {
        "prompt": prompt,
        "output": _truncate(output, 800),
        "latency_ms": result.latency_ms,
        "usage": result.usage.to_dict(),
    }
    if result.error:
        details["error"] = result.error
    return {
        "ok": ok,
        "details": details,
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


def _run_thinking_suite(
    provider_cfg: Dict[str, Any],
    model: str,
    api_key: Optional[str],
    role: str,
    events_path: str,
    run_id: str,
) -> Dict[str, Any]:
    prompt = (
        "Interview mode check. Respond with:\n"
        "<thinking>brief reasoning summary</thinking>\n"
        "<final>final answer</final>\n"
        "Question: 2 + 2 = ?"
    )
    result = _provider_invoke(
        provider_cfg,
        model,
        prompt,
        api_key,
        role=role,
        suite="thinking",
        events_path=events_path,
        run_id=run_id,
    )
    thinking = _analyze_thinking_output(result.output)
    ok = bool(result.ok and thinking.get("supports_thinking"))
    details = {
        "prompt": prompt,
        "output": _truncate(result.output, 1200),
        "thinking": thinking,
        "latency_ms": result.latency_ms,
        "usage": result.usage.to_dict(),
    }
    if result.error:
        details["error"] = result.error
    return {"ok": ok, "details": details}


def _run_interview_suite(
    provider_cfg: Dict[str, Any],
    model: str,
    api_key: Optional[str],
    role: str,
    test_level: str,
    events_path: str,
    run_id: str,
    thinking_snapshot: Optional[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    role_req = _role_requirements(config, role)
    requires_thinking = bool(role_req.get("requires_thinking"))
    min_confidence = float(role_req.get("min_confidence") or 0.5)
    questions = _interview_questions(role, test_level)
    cases: List[Dict[str, Any]] = []
    raw_outputs: List[str] = []
    for idx, question in enumerate(questions, start=1):
        prompt = _build_interview_prompt(role, question)
        result = _provider_invoke(
            provider_cfg,
            model,
            prompt,
            api_key,
            role=role,
            suite="interview",
            events_path=events_path,
            run_id=run_id,
        )
        raw_outputs.append(result.output)
        thinking_text, answer_text, fmt = _split_thinking_output(result.output)
        criteria = question.get("evaluation_criteria")
        if not isinstance(criteria, list):
            criteria = []
        evaluation = _evaluate_interview_answer(
            answer_text or result.output,
            thinking_text,
            criteria,
            bool(question.get("expects_thinking")),
        )
        cases.append(
            {
                "id": question.get("id") or f"q{idx}",
                "question": question.get("question") or "",
                "expects_thinking": bool(question.get("expects_thinking")),
                "output": _truncate(result.output, 1600),
                "thinking": _truncate(thinking_text, 800),
                "answer": _truncate(answer_text, 1200),
                "thinking_format": fmt,
                "score": evaluation["score"],
                "criteria_hits": evaluation["criteria_hits"],
                "missing_criteria": evaluation["missing_criteria"],
                "notes": evaluation["notes"],
                "usage": result.usage.to_dict(),
                "latency_ms": result.latency_ms,
            }
        )
    avg_score = sum(case["score"] for case in cases) / len(cases) if cases else 0.0
    thinking_eval = thinking_snapshot or _analyze_thinking_output("\n".join(raw_outputs))
    thinking_conf = float(thinking_eval.get("confidence") or 0.0)
    status = "PASSED"
    ok = True
    reason = ""
    final_score = avg_score
    if requires_thinking and thinking_conf < min_confidence:
        status = "REJECTED"
        ok = False
        final_score = 0.0
        reason = str(role_req.get("error_message") or "Thinking capability required.")
    else:
        if avg_score < min_confidence:
            status = "FAILED"
            ok = False
    recommendation = _interview_recommendation(status, final_score, role)
    return {
        "ok": ok,
        "status": status,
        "final_score": round(final_score, 3),
        "thinking": thinking_eval,
        "cases": cases,
        "details": {
            "role": role,
            "threshold": min_confidence,
            "requires_thinking": requires_thinking,
            "reason": reason,
            "recommendation": recommendation,
        },
    }


def _provider_health(provider_type: str, provider_cfg: Dict[str, Any], api_key: Optional[str]) -> Dict[str, Any]:
    from ..llm.providers.provider_registry import provider_manager
    
    merged_cfg = {**provider_cfg, "api_key": api_key} if api_key else provider_cfg
    provider_instance = provider_manager.get_provider_instance(provider_type)
    if provider_instance:
        return provider_instance.health(merged_cfg).to_dict()
    
    # Fallback to function-based providers
    if provider_type == "ollama":
        return ollama_health(provider_cfg).to_dict()
    if provider_type == "openai_compat":
        return openai_health(provider_cfg, api_key).to_dict()
    if provider_type == "anthropic_compat":
        return anthropic_health(provider_cfg, api_key).to_dict()
    
    return {"ok": False, "error": f"Unknown provider type: {provider_type}"}


def _provider_list_models(provider_type: str, provider_cfg: Dict[str, Any], api_key: Optional[str]) -> ModelListResult:
    from ..llm.providers.provider_registry import provider_manager
    
    merged_cfg = {**provider_cfg, "api_key": api_key} if api_key else provider_cfg
    provider_instance = provider_manager.get_provider_instance(provider_type)
    if provider_instance:
        return provider_instance.list_models(merged_cfg)
    
    # Fallback to function-based providers
    if provider_type == "ollama":
        return ollama_list_models(provider_cfg)
    if provider_type == "openai_compat":
        return openai_list_models(provider_cfg, api_key)
    if provider_type == "anthropic_compat":
        return anthropic_list_models(provider_cfg, api_key)
    
    return ModelListResult(ok=False, supported=False, models=[], error=f"Unknown provider type: {provider_type}")


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
    from ..llm.providers.provider_registry import provider_manager
    
    merged_cfg = {**provider_cfg, "api_key": api_key} if api_key else provider_cfg
    provider_instance = provider_manager.get_provider_instance(provider_type)
    if provider_instance:
        return provider_instance.invoke(prompt, model, merged_cfg)
    
    # Fallback to function-based providers
    if provider_type == "ollama":
        result = ollama_invoke(prompt, model, provider_cfg)
    elif provider_type == "openai_compat":
        result = openai_invoke(prompt, model, provider_cfg, api_key)
    elif provider_type == "anthropic_compat":
        result = anthropic_invoke(prompt, model, provider_cfg, api_key)
    else:
        result = InvokeResult(
            ok=False,
            output="",
            latency_ms=0,
            usage=estimate_usage(prompt, ""),
            error=f"Unknown provider type: {provider_type}"
        )
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


def _build_interview_prompt(role: str, question: Dict[str, Any]) -> str:
    role_label = role.strip().upper() or "ROLE"
    expects_thinking = bool(question.get("expects_thinking"))
    criteria = question.get("evaluation_criteria") or []
    criteria_text = " / ".join([str(item) for item in criteria if str(item).strip()])
    thinking_instruction = (
        "Include a brief reasoning summary in <thinking> tags.\n"
        if expects_thinking
        else "If helpful, include a brief <thinking> summary; otherwise answer directly.\n"
    )
    return (
        f"You are a candidate interviewing for the {role_label} role.\n"
        "IMPORTANT: You are the interviewee, not the interviewer.\n"
        "Answer the question directly and completely. Do NOT ask follow-up questions or request more context.\n"
        "Use clear sections or bullet points where appropriate.\n"
        + (f"Evaluation criteria to address explicitly: {criteria_text}\n" if criteria_text else "")
        + "Reply in the same language as the question.\n"
        + f"{thinking_instruction}"
        + "Return the final answer in <answer>...</answer>.\n"
        + f"Question: {question.get('question') or ''}"
    )


def _interview_questions(role: str, test_level: str) -> List[Dict[str, Any]]:
    role = role.strip().lower()
    questions = INTERVIEW_QUESTIONS.get(role, INTERVIEW_QUESTIONS.get("docs", []))
    if test_level.strip().lower() == "quick":
        return questions[:1]
    return questions


def _looks_like_structured_steps(answer: str) -> bool:
    if not answer:
        return False
    return bool(re.search(r"(^|\n)\s*(\d+[\.\)]|[-•*]\s|一、|二、|三、|四、)", answer))


def _looks_like_deflection(answer: str) -> bool:
    if not answer:
        return False
    lowered = answer.lower()
    hints = [
        "would you like", "let me know", "can you", "do you want", "i can",
        "interview prep", "need more context", "need more information",
    ]
    if any(hint in lowered for hint in hints):
        return True
    if any(token in answer for token in ["你想", "需要更多信息", "请提供", "是否需要", "要不要", "可以帮你"]):
        return True
    if ("?" in answer or "？" in answer) and len(answer) < 200:
        return True
    return False


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    size = min(len(vec_a), len(vec_b))
    if size == 0:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for idx in range(size):
        a = float(vec_a[idx])
        b = float(vec_b[idx])
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _get_embedding_vector(text: str) -> List[float]:
    global _EMBEDDING_DISABLED
    if not INTERVIEW_SEMANTIC_ENABLED or _EMBEDDING_DISABLED:
        return []
    if not text:
        return []
    trimmed = _truncate(text, INTERVIEW_SEMANTIC_MAX_CHARS)
    if not trimmed:
        return []
    cache_key = (INTERVIEW_EMBEDDING_MODEL, trimmed)
    if cache_key in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[cache_key]
    ensure_loop_modules()
    try:
        from ollama_utils import get_embedding  # type: ignore
    except Exception:
        _EMBEDDING_DISABLED = True
        return []
    vec = get_embedding(trimmed, INTERVIEW_EMBEDDING_MODEL, timeout=INTERVIEW_SEMANTIC_TIMEOUT)
    if not vec:
        _EMBEDDING_DISABLED = True
        return []
    _EMBEDDING_CACHE[cache_key] = vec
    return vec


def _semantic_criteria_hits(answer: str, criteria: List[str], existing: List[str]) -> List[str]:
    if not INTERVIEW_SEMANTIC_ENABLED:
        return []
    if not criteria:
        return []
    if len(answer) < INTERVIEW_SEMANTIC_MIN_CHARS:
        return []
    answer_vec = _get_embedding_vector(answer)
    if not answer_vec:
        return []
    hits: List[str] = []
    for criterion in criteria:
        if criterion in existing:
            continue
        keywords = CRITERIA_KEYWORDS.get(criterion, [])
        criteria_text = f"{criterion}: " + " ".join([str(item) for item in keywords if str(item).strip()])
        criteria_vec = _get_embedding_vector(criteria_text)
        if not criteria_vec:
            continue
        similarity = _cosine_similarity(answer_vec, criteria_vec)
        if similarity >= INTERVIEW_SEMANTIC_THRESHOLD:
            hits.append(criterion)
    return hits


def _evaluate_interview_answer(
    answer: str,
    thinking: str,
    criteria: List[str],
    expects_thinking: bool,
) -> Dict[str, Any]:
    answer = answer or ""
    lowered = answer.lower()
    criteria_hits: List[str] = []
    missing: List[str] = []
    for criterion in criteria:
        keywords = CRITERIA_KEYWORDS.get(criterion, [])
        if any(keyword.lower() in lowered for keyword in keywords):
            criteria_hits.append(criterion)
        else:
            missing.append(criterion)
    if "计划完整性" in missing and _looks_like_structured_steps(answer):
        criteria_hits.append("计划完整性")
        missing = [item for item in missing if item != "计划完整性"]
    semantic_hits = _semantic_criteria_hits(answer, criteria, criteria_hits)
    if semantic_hits:
        for criterion in semantic_hits:
            if criterion not in criteria_hits:
                criteria_hits.append(criterion)
        missing = [item for item in missing if item not in semantic_hits]
    length_score = 0.2 if len(answer) >= 60 else 0.1 if len(answer) >= 20 else 0.0
    criteria_score = (len(criteria_hits) / len(criteria)) if criteria else 0.0
    score = 0.2 + (0.6 * criteria_score) + length_score
    if expects_thinking:
        score += 0.2 if thinking else -0.2
    if _looks_like_deflection(answer) and len(criteria_hits) < max(1, len(criteria) // 2):
        score -= 0.2
    score = max(0.0, min(1.0, score))
    notes = f"Matched {len(criteria_hits)}/{len(criteria)} criteria."
    if expects_thinking and not thinking:
        notes += " Missing thinking summary."
    if _looks_like_deflection(answer):
        notes += " Detected deflection."
    if semantic_hits:
        notes += f" Semantic matches: {', '.join(semantic_hits)}."
    return {
        "score": round(score, 3),
        "criteria_hits": criteria_hits,
        "missing_criteria": missing,
        "notes": notes,
    }


def _interview_recommendation(status: str, score: float, role: str) -> str:
    role_label = role.strip().upper() or "ROLE"
    if status == "REJECTED":
        return f"{role_label} interview rejected: missing required thinking capability."
    if status == "FAILED":
        return f"{role_label} interview needs improvement before approval."
    if score >= 0.85:
        return f"{role_label} strong hire recommendation."
    if score >= 0.7:
        return f"{role_label} hire recommendation."
    return f"{role_label} borderline pass; consider follow-up."


def _analyze_thinking_output(output: str) -> Dict[str, Any]:
    thinking_text, answer_text, fmt = _split_thinking_output(output)
    lowered = (output or "").lower()
    indicators = [indicator for indicator in THINKING_INDICATORS if indicator in lowered]
    if thinking_text:
        confidence = 0.9 if len(thinking_text) >= 40 else 0.75
        supports = True
        fmt = fmt or "tagged"
    elif indicators:
        confidence = 0.55
        supports = True
        fmt = "implicit"
    else:
        confidence = 0.0
        supports = False
        fmt = "none"
    return {
        "supports_thinking": supports,
        "confidence": round(confidence, 3),
        "format": fmt,
        "indicators": indicators,
        "thinking_text": _truncate(thinking_text, 800),
        "answer_text": _truncate(answer_text, 800),
    }


def _split_thinking_output(output: str) -> Tuple[str, str, str]:
    output = output or ""
    thinking_tags = ["thinking", "reasoning", "analysis", "think"]
    answer_tags = ["final", "answer", "response"]
    thinking_text = _extract_tagged_block(output, thinking_tags)
    answer_text = _extract_tagged_block(output, answer_tags)
    fmt = "tagged" if (thinking_text or answer_text) else ""
    if not answer_text:
        stripped = _strip_tagged_blocks(output, [*thinking_tags, *answer_tags])
        answer_text = stripped.strip()
    return thinking_text.strip(), answer_text.strip(), fmt


def _extract_tagged_block(text: str, tag: Any) -> str:
    if not text or not tag:
        return ""
    if isinstance(tag, (list, tuple)):
        for item in tag:
            found = _extract_tagged_block(text, item)
            if found:
                return found
        return ""
    pattern = re.compile(rf"<{tag}[^>]*>(.*?)</{tag}>", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _strip_tagged_blocks(text: str, tags: List[str]) -> str:
    cleaned = text or ""
    for tag in tags:
        cleaned = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned


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
    elif suite == "interview":
        for case in result.get("cases") or []:
            entries.append(f"### Question {case.get('id')}")
            entries.append("Question:")
            entries.append(_indent(case.get("question", "")))
            entries.append("Response:")
            entries.append(_indent(case.get("output", "")))
            if case.get("thinking"):
                entries.append("Thinking:")
                entries.append(_indent(case.get("thinking", "")))
            entries.append(f"Score: {case.get('score')}")
        details = result.get("details") or {}
        if details.get("recommendation"):
            entries.append(f"Recommendation: {details.get('recommendation')}")
    else:
        details = result.get("details") or {}
        if details.get("prompt"):
            entries.append("Prompt:")
            entries.append(_indent(details.get("prompt", "")))
        if details.get("output"):
            entries.append("Response:")
            entries.append(_indent(details.get("output", "")))
        if suite == "thinking":
            thinking = details.get("thinking") if isinstance(details, dict) else None
            if isinstance(thinking, dict):
                entries.append(f"Thinking Support: {thinking.get('supports_thinking')}")
                entries.append(f"Confidence: {thinking.get('confidence')}")
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
    providers = data.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    target = report.get("target") if isinstance(report.get("target"), dict) else {}
    provider_id = target.get("provider_id") if isinstance(target, dict) else None
    if provider_id:
        provider_key = str(provider_id)
        existing = providers.get(provider_key) if isinstance(providers.get(provider_key), dict) else {}
        new_suites = report.get("suites")
        merged_suites = new_suites
        if isinstance(new_suites, dict) and isinstance(existing.get("suites"), dict):
            if "connectivity" not in new_suites and "connectivity" in existing["suites"]:
                merged_suites = {**new_suites, "connectivity": existing["suites"]["connectivity"]}
        elif not new_suites and isinstance(existing.get("suites"), dict):
            merged_suites = existing["suites"]
        providers[provider_key] = {
            "last_run_id": report.get("test_run_id"),
            "ready": report.get("final", {}).get("ready"),
            "grade": report.get("final", {}).get("grade"),
            "timestamp": report.get("timestamp"),
            "suites": merged_suites,
            "model": target.get("model") if isinstance(target, dict) else None,
            "role": target.get("role") if isinstance(target, dict) else None,
        }
    data["schema_version"] = 1
    data["updated_at"] = _utc_now()
    data["roles"] = roles
    data["providers"] = providers
    _write_json(index_path, data)


def load_llm_test_index(settings: Settings) -> Dict[str, Any]:
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    index_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/llm_tests/index.json")
    if not os.path.isfile(index_path):
        return {"schema_version": 1, "roles": {}, "providers": {}}
    try:
        with open(index_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {"schema_version": 1, "roles": {}, "providers": {}}
    except Exception:
        return {"schema_version": 1, "roles": {}, "providers": {}}


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
