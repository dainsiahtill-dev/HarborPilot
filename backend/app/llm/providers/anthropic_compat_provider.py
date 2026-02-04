from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage
from .base_provider import BaseProvider, ProviderInfo, ValidationResult
from .http_utils import join_url, merge_headers, normalize_base_url

DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODELS_PATH = "/v1/models"
DEFAULT_MESSAGES_PATH = "/v1/messages"


def _inject_api_key(config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, Any]:
    if not api_key:
        return config
    merged = dict(config)
    merged["api_key"] = api_key
    return merged


def _headers(config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, str]:
    headers = merge_headers({"Content-Type": "application/json"}, config.get("headers"))
    version = config.get("anthropic_version") or headers.get("anthropic-version") or DEFAULT_ANTHROPIC_VERSION
    if version and "anthropic-version" not in headers:
        headers["anthropic-version"] = str(version)
    if api_key:
        header_name = str(config.get("api_key_header") or "x-api-key")
        headers[header_name] = str(api_key)
    return headers


class AnthropicCompatProvider(BaseProvider):
    """Anthropic-compatible API provider"""

    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="Anthropic Compatible Provider",
            type="anthropic_compat",
            description="Anthropic-compatible REST API provider",
            version="1.0.0",
            author="HarborPilot Team",
            documentation_url="https://docs.anthropic.com/claude/reference",
            supported_features=[
                "health_check",
                "model_listing",
                "messages_api",
                "custom_headers",
                "retries",
            ],
            cost_class="METERED",
            provider_category="LLM",
            autonomous_file_access=False,
            requires_file_interfaces=True,
            model_listing_method="API",
        )

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "base_url": "",
            "api_path": DEFAULT_MESSAGES_PATH,
            "models_path": DEFAULT_MODELS_PATH,
            "anthropic_version": DEFAULT_ANTHROPIC_VERSION,
            "timeout": 60,
            "retries": 0,
            "temperature": 0.2,
            "max_tokens": 256,
            "headers": {},
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        normalized = dict(config)

        base_url = normalize_base_url(str(config.get("base_url") or ""))
        if base_url:
            normalized["base_url"] = base_url

        api_path = str(config.get("api_path") or "").strip()
        if not api_path:
            errors.append("api_path is required")
        else:
            normalized["api_path"] = api_path
            if not base_url and not api_path.startswith(("http://", "https://")):
                warnings.append("base_url is empty; api_path should be absolute")

        models_path = str(config.get("models_path") or DEFAULT_MODELS_PATH).strip()
        if not models_path:
            warnings.append("models_path is empty; model listing may fail")
        else:
            normalized["models_path"] = models_path

        timeout = config.get("timeout", 60)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            warnings.append("Invalid timeout, using default 60")
            normalized["timeout"] = 60

        retries = config.get("retries", 0)
        if not isinstance(retries, int) or retries < 0:
            warnings.append("Invalid retries, using default 0")
            normalized["retries"] = 0

        temperature = config.get("temperature", 0.2)
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            warnings.append("Invalid temperature, using default 0.2")
            normalized["temperature"] = 0.2

        max_tokens = config.get("max_tokens", 256)
        if not isinstance(max_tokens, (int, float)) or max_tokens <= 0:
            warnings.append("Invalid max_tokens, using default 256")
            normalized["max_tokens"] = 256

        headers = config.get("headers")
        if headers is not None and not isinstance(headers, dict):
            warnings.append("Headers should be a dictionary")
            normalized["headers"] = {}

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_config=normalized,
        )

    def health(self, config: Dict[str, Any]) -> HealthResult:
        base = normalize_base_url(str(config.get("base_url") or ""))
        models_path = str(config.get("models_path") or DEFAULT_MODELS_PATH).strip()
        url = join_url(base, models_path, strip_prefixes=["/v1"])
        timeout = int(config.get("timeout") or 10)
        api_key = config.get("api_key")
        start = time.time()
        try:
            response = requests.get(
                url,
                headers=_headers(config, api_key),
                timeout=timeout if timeout > 0 else None,
            )
            response.raise_for_status()
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=True, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=False, latency_ms=latency_ms, error=str(exc))

    def list_models(self, config: Dict[str, Any]) -> ModelListResult:
        base = normalize_base_url(str(config.get("base_url") or ""))
        models_path = str(config.get("models_path") or DEFAULT_MODELS_PATH).strip()
        url = join_url(base, models_path, strip_prefixes=["/v1"])
        timeout = int(config.get("timeout") or 10)
        api_key = config.get("api_key")
        try:
            response = requests.get(
                url,
                headers=_headers(config, api_key),
                timeout=timeout if timeout > 0 else None,
            )
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

    def invoke(self, prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
        base = normalize_base_url(str(config.get("base_url") or ""))
        timeout = int(config.get("timeout") or 60)
        retries = int(config.get("retries") or 0)
        api_path = str(config.get("api_path") or DEFAULT_MESSAGES_PATH).strip()
        url = join_url(base, api_path, strip_prefixes=["/v1"])
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": int(config.get("max_tokens") or 256),
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "temperature": float(config.get("temperature") or 0.2),
        }
        system_prompt = config.get("system_prompt") or config.get("system")
        if system_prompt:
            payload["system"] = str(system_prompt)
        overrides = config.get("request_overrides")
        if isinstance(overrides, dict):
            payload.update(overrides)

        api_key = config.get("api_key")
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


_provider = AnthropicCompatProvider()


def health(config: Dict[str, Any], api_key: Optional[str]) -> HealthResult:
    return _provider.health(_inject_api_key(config, api_key))


def list_models(config: Dict[str, Any], api_key: Optional[str]) -> ModelListResult:
    return _provider.list_models(_inject_api_key(config, api_key))


def invoke(prompt: str, model: str, config: Dict[str, Any], api_key: Optional[str]) -> InvokeResult:
    return _provider.invoke(prompt, model, _inject_api_key(config, api_key))


def _extract_output(data: Dict[str, Any]) -> str:
    if not isinstance(data, dict):
        return ""
    content = data.get("content")
    if isinstance(content, list):
        blocks: List[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    blocks.append(str(block.get("text")))
        if blocks:
            return "\n".join(blocks)
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                return str(block.get("text"))
    if isinstance(data.get("text"), str):
        return str(data.get("text"))
    return ""


def _usage_from_response(prompt: str, output: str, data: Dict[str, Any]) -> Usage:
    try:
        usage = data.get("usage") if isinstance(data, dict) else None
        if isinstance(usage, dict):
            prompt_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
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
