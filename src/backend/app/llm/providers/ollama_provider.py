from __future__ import annotations

import time
from typing import Any, Dict, List

import requests

from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage
from .base_provider import BaseProvider, ProviderInfo, ValidationResult
from .http_utils import join_url, normalize_base_url

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TAGS_PATH = "/api/tags"
DEFAULT_CHAT_PATH = "/api/chat"
DEFAULT_GENERATE_PATH = "/api/generate"


class OllamaProvider(BaseProvider):
    """Ollama local provider"""

    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="Ollama Provider",
            type="ollama",
            description="Local Ollama provider",
            version="1.0.0",
            author="HarborPilot Team",
            documentation_url="https://github.com/ollama/ollama/blob/main/docs/api.md",
            supported_features=[
                "health_check",
                "model_listing",
                "local_inference",
                "chat",
                "generate",
            ],
            cost_class="LOCAL",
            provider_category="LLM",
            autonomous_file_access=False,
            requires_file_interfaces=True,
            model_listing_method="API",
        )

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "base_url": DEFAULT_BASE_URL,
            "timeout": 60,
            "api_path": "",
            "use_chat": False,
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        normalized = dict(config)

        base_url = normalize_base_url(str(config.get("base_url") or DEFAULT_BASE_URL))
        if not base_url:
            errors.append("base_url is required")
        else:
            normalized["base_url"] = base_url

        timeout = config.get("timeout", 60)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            warnings.append("Invalid timeout, using default 60")
            normalized["timeout"] = 60

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_config=normalized,
        )

    def _base_url(self, config: Dict[str, Any]) -> str:
        return normalize_base_url(str(config.get("base_url") or DEFAULT_BASE_URL))

    def health(self, config: Dict[str, Any]) -> HealthResult:
        url = join_url(self._base_url(config), DEFAULT_TAGS_PATH)
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

    def list_models(self, config: Dict[str, Any]) -> ModelListResult:
        url = join_url(self._base_url(config), DEFAULT_TAGS_PATH)
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

    def invoke(self, prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
        base = self._base_url(config)
        timeout = int(config.get("timeout") or 60)
        api_path = str(config.get("api_path") or "").strip()
        use_chat = api_path.endswith(DEFAULT_CHAT_PATH) or config.get("use_chat") is True
        if not api_path:
            api_path = DEFAULT_CHAT_PATH if use_chat else DEFAULT_GENERATE_PATH
        url = join_url(base, api_path)
        start = time.time()
        try:
            payload: Dict[str, Any]
            if DEFAULT_CHAT_PATH in api_path:
                messages = [{"role": "user", "content": prompt}]
                system_prompt = config.get("system_prompt") or config.get("system")
                if system_prompt:
                    messages.insert(0, {"role": "system", "content": str(system_prompt)})
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                }
            else:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                }
                system_prompt = config.get("system_prompt") or config.get("system")
                if system_prompt:
                    payload["system"] = str(system_prompt)

            if config.get("options") is not None:
                payload["options"] = config.get("options")
            if config.get("keep_alive") is not None:
                payload["keep_alive"] = config.get("keep_alive")
            if config.get("format") is not None:
                payload["format"] = config.get("format")
            overrides = config.get("request_overrides")
            if isinstance(overrides, dict):
                payload.update(overrides)

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


_provider = OllamaProvider()


def health(config: Dict[str, Any]) -> HealthResult:
    return _provider.health(config)


def list_models(config: Dict[str, Any]) -> ModelListResult:
    return _provider.list_models(config)


def invoke(prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
    return _provider.invoke(prompt, model, config)


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
