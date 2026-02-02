from __future__ import annotations

import time
from typing import Any, Dict, List

import requests

from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage


def _base_url(config: Dict[str, Any]) -> str:
    base = str(config.get("base_url") or "http://127.0.0.1:11434").strip()
    return base.rstrip("/")


def health(config: Dict[str, Any]) -> HealthResult:
    url = _base_url(config) + "/api/tags"
    timeout = int(config.get("timeout") or 10)
    start = time.time()
    try:
        response = requests.get(url, timeout=timeout if timeout > 0 else None)
        response.raise_for_status()
        latency_ms = int((time.time() - start) * 1000)
        return HealthResult(ok=True, latency_ms=latency_ms)
    except Exception as exc:
        latency_ms = int((time.time() - start) * 1000)
        return HealthResult(ok=False, latency_ms=latency_ms, error=str(exc))


def list_models(config: Dict[str, Any]) -> ModelListResult:
    url = _base_url(config) + "/api/tags"
    timeout = int(config.get("timeout") or 10)
    try:
        response = requests.get(url, timeout=timeout if timeout > 0 else None)
        response.raise_for_status()
        payload = response.json()
        models: List[ModelInfo] = []
        for item in payload.get("models") or []:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("name") or item.get("model") or "").strip()
            if model_id:
                models.append(ModelInfo(id=model_id, raw=item))
        return ModelListResult(ok=True, supported=True, models=models)
    except Exception as exc:
        return ModelListResult(ok=False, supported=True, models=[], error=str(exc))


def invoke(prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
    base = _base_url(config)
    timeout = int(config.get("timeout") or 60)
    api_path = str(config.get("api_path") or "").strip()
    use_chat = api_path.endswith("/api/chat") or config.get("use_chat") is True
    if not api_path:
        api_path = "/api/chat" if use_chat else "/api/generate"
    url = base + api_path
    start = time.time()
    try:
        if "/api/chat" in api_path:
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            }
        else:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
        response = requests.post(url, json=payload, timeout=timeout if timeout > 0 else None)
        response.raise_for_status()
        data = response.json()
        latency_ms = int((time.time() - start) * 1000)
        output = ""
        if isinstance(data, dict):
            if "response" in data:
                output = str(data.get("response") or "")
            elif "message" in data and isinstance(data.get("message"), dict):
                output = str(data["message"].get("content") or "")
        usage = _usage_from_response(prompt, output, data)
        return InvokeResult(ok=True, output=output.strip(), latency_ms=latency_ms, usage=usage, raw=data)
    except Exception as exc:
        latency_ms = int((time.time() - start) * 1000)
        usage = estimate_usage(prompt, "")
        return InvokeResult(ok=False, output="", latency_ms=latency_ms, usage=usage, error=str(exc))


def _usage_from_response(prompt: str, output: str, data: Dict[str, Any]) -> Usage:
    try:
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens > 0:
            return Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated=False,
                prompt_chars=len(prompt or ""),
                completion_chars=len(output or ""),
            )
    except Exception:
        pass
    return estimate_usage(prompt, output)
