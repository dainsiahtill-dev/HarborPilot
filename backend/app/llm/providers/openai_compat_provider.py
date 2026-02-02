from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage


def _base_url(config: Dict[str, Any]) -> str:
    base = str(config.get("base_url") or "").strip()
    return base.rstrip("/")


def _headers(config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    extra = config.get("headers") or {}
    if isinstance(extra, dict):
        for key, value in extra.items():
            if value is None:
                continue
            headers[str(key)] = str(value)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _join_url(base_url: str, path: str) -> str:
    if not base_url:
        return path
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    # Avoid double /v1 when base_url already includes it.
    if base_url.rstrip("/").endswith("/v1") and path.startswith("/v1/"):
        path = path[len("/v1") :]
    return base_url + path


def health(config: Dict[str, Any], api_key: Optional[str]) -> HealthResult:
    base = _base_url(config)
    models_path = str(config.get("models_path") or "/models").strip()
    if "/v1/" not in base and models_path.startswith("/models"):
        models_path = "/v1/models"
    url = _join_url(base, models_path)
    timeout = int(config.get("timeout") or 10)
    start = time.time()
    try:
        response = requests.get(url, headers=_headers(config, api_key), timeout=timeout if timeout > 0 else None)
        response.raise_for_status()
        latency_ms = int((time.time() - start) * 1000)
        return HealthResult(ok=True, latency_ms=latency_ms)
    except Exception as exc:
        latency_ms = int((time.time() - start) * 1000)
        return HealthResult(ok=False, latency_ms=latency_ms, error=str(exc))


def list_models(config: Dict[str, Any], api_key: Optional[str]) -> ModelListResult:
    base = _base_url(config)
    models_path = str(config.get("models_path") or "/models").strip()
    if "/v1/" not in base and models_path.startswith("/models"):
        models_path = "/v1/models"
    url = _join_url(base, models_path)
    timeout = int(config.get("timeout") or 10)
    try:
        response = requests.get(url, headers=_headers(config, api_key), timeout=timeout if timeout > 0 else None)
        response.raise_for_status()
        payload = response.json()
        models: List[ModelInfo] = []
        items = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    model_id = str(item.get("id") or item.get("name") or "").strip()
                    if model_id:
                        models.append(ModelInfo(id=model_id, raw=item))
        return ModelListResult(ok=True, supported=True, models=models)
    except Exception as exc:
        return ModelListResult(ok=False, supported=True, models=[], error=str(exc))


def invoke(prompt: str, model: str, config: Dict[str, Any], api_key: Optional[str]) -> InvokeResult:
    base = _base_url(config)
    timeout = int(config.get("timeout") or 60)
    retries = int(config.get("retries") or 0)
    api_path = str(config.get("api_path") or "/v1/chat/completions").strip()
    url = _join_url(base, api_path)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(config.get("temperature") or 0.2),
    }
    attempt = 0
    start = time.time()
    while True:
        try:
            response = requests.post(
                url,
                headers=_headers(config, api_key),
                json=payload,
                timeout=timeout if timeout > 0 else None,
            )
            response.raise_for_status()
            data = response.json()
            latency_ms = int((time.time() - start) * 1000)
            output = _extract_output(data)
            usage = _usage_from_response(prompt, output, data)
            return InvokeResult(ok=True, output=output.strip(), latency_ms=latency_ms, usage=usage, raw=data)
        except Exception as exc:
            attempt += 1
            if attempt > retries:
                latency_ms = int((time.time() - start) * 1000)
                usage = estimate_usage(prompt, "")
                return InvokeResult(ok=False, output="", latency_ms=latency_ms, usage=usage, error=str(exc))
            time.sleep(0.5)


def _extract_output(data: Dict[str, Any]) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices:
        return ""
    first = choices[0]
    if isinstance(first, dict):
        message = first.get("message")
        if isinstance(message, dict):
            return str(message.get("content") or "")
        if "text" in first:
            return str(first.get("text") or "")
    return ""


def _usage_from_response(prompt: str, output: str, data: Dict[str, Any]) -> Usage:
    try:
        usage = data.get("usage") if isinstance(data, dict) else None
        if isinstance(usage, dict):
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
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
