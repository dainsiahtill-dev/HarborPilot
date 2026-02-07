from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp
import requests

from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage
from .base_provider import BaseProvider, ProviderInfo, ValidationResult
from .http_utils import join_url, merge_headers, normalize_base_url

DEFAULT_MODELS_PATH = "/v1/models"
DEFAULT_CHAT_PATH = "/v1/chat/completions"


def _inject_api_key(config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, Any]:
    if not api_key:
        return config
    merged = dict(config)
    merged["api_key"] = api_key
    return merged


def _headers(config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, str]:
    headers = merge_headers({"Content-Type": "application/json"}, config.get("headers"))
    header_name = str(config.get("api_key_header") or "").strip()
    if api_key:
        if header_name:
            headers[header_name] = str(api_key)
        else:
            headers["Authorization"] = f"Bearer {api_key}"
    return headers


class OpenAICompatProvider(BaseProvider):
    """OpenAI-compatible API provider"""

    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="OpenAI Compatible Provider",
            type="openai_compat",
            description="OpenAI-compatible REST API provider",
            version="1.0.0",
            author="HarborPilot Team",
            documentation_url="https://platform.openai.com/docs/api-reference",
            supported_features=[
                "health_check",
                "model_listing",
                "chat_completions",
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
            "base_url": "https://api.example.com/v1",
            "api_path": DEFAULT_CHAT_PATH,
            "timeout": 60,
            "retries": 0,
            "temperature": 0.2,
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
        """Health check using chat completion API instead of /models endpoint"""
        base = normalize_base_url(str(config.get("base_url") or ""))
        api_path = str(config.get("api_path") or DEFAULT_CHAT_PATH).strip()
        url = join_url(base, api_path, strip_prefixes=["/v1"])
        timeout = int(config.get("timeout") or 30)
        api_key = config.get("api_key")
        
        # Use a simple test message for health check
        test_payload = {
            "model": config.get("model") or "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 10,
            "stream": False,
        }
        
        start = time.time()
        try:
            response = requests.post(
                url,
                headers=_headers(config, api_key),
                json=test_payload,
                timeout=timeout if timeout > 0 else None,
            )
            latency_ms = int((time.time() - start) * 1000)
            
            if response.status_code == 401:
                return HealthResult(ok=False, latency_ms=latency_ms, error="Authentication failed: please check your API key")
            elif response.status_code == 404:
                return HealthResult(ok=False, latency_ms=latency_ms, error="API endpoint not found: please check api_path configuration")
            
            response.raise_for_status()
            
            # Validate response format (OpenAI compatible)
            data = response.json()
            if isinstance(data, dict) and "choices" in data:
                return HealthResult(ok=True, latency_ms=latency_ms)
            
            return HealthResult(ok=True, latency_ms=latency_ms)
        except requests.exceptions.ConnectionError:
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=False, latency_ms=latency_ms, error="Network connection failed: please check your network and base_url")
        except requests.exceptions.Timeout:
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=False, latency_ms=latency_ms, error="Request timeout: the server took too long to respond")
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=False, latency_ms=latency_ms, error=str(exc))

    def list_models(self, config: Dict[str, Any]) -> ModelListResult:
        base = normalize_base_url(str(config.get("base_url") or ""))
        models_path = str(config.get("models_path") or DEFAULT_MODELS_PATH).strip()
        if "/v1/" not in base and models_path.startswith("/models"):
            models_path = DEFAULT_MODELS_PATH
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
        api_path = str(config.get("api_path") or DEFAULT_CHAT_PATH).strip()
        url = join_url(base, api_path, strip_prefixes=["/v1"])
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature") or 0.2),
        }
        max_tokens = config.get("max_tokens")
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
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

    async def invoke_stream(
        self, prompt: str, model: str, config: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        True streaming invoke for OpenAI-compatible API.
        
        Sends request with stream=True and yields tokens as they arrive.
        """
        base = normalize_base_url(str(config.get("base_url") or ""))
        timeout = int(config.get("timeout") or 60)
        api_path = str(config.get("api_path") or DEFAULT_CHAT_PATH).strip()
        url = join_url(base, api_path, strip_prefixes=["/v1"])
        
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature") or 0.2),
            "stream": True,  # Enable streaming
        }
        
        max_tokens = config.get("max_tokens")
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        
        api_key = config.get("api_key")
        headers = _headers(config, api_key)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        yield f"Error: HTTP {response.status} - {error_text}"
                        return
                    
                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if not line:
                            continue
                        
                        # SSE format: data: {...}
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix
                            
                            if data == "[DONE]":
                                break
                            
                            try:
                                json_data = json.loads(data)
                                choices = json_data.get("choices", [])
                                if choices and isinstance(choices, list):
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
                            except Exception:
                                continue
                                
        except asyncio.TimeoutError:
            yield "Error: Request timeout"
        except aiohttp.ClientError as exc:
            yield f"Error: Connection failed - {str(exc)}"
        except Exception as exc:
            yield f"Error: {str(exc)}"


_provider = OpenAICompatProvider()


def health(config: Dict[str, Any], api_key: Optional[str]) -> HealthResult:
    return _provider.health(_inject_api_key(config, api_key))


def list_models(config: Dict[str, Any], api_key: Optional[str]) -> ModelListResult:
    return _provider.list_models(_inject_api_key(config, api_key))


def invoke(prompt: str, model: str, config: Dict[str, Any], api_key: Optional[str]) -> InvokeResult:
    return _provider.invoke(prompt, model, _inject_api_key(config, api_key))


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
