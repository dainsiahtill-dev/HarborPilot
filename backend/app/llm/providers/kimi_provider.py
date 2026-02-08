from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp
import requests

from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage
from .base_provider import BaseProvider, ProviderInfo, ValidationResult

DEFAULT_MODELS_PATH = "/v1/models"
DEFAULT_CHAT_PATH = "/v1/chat/completions"


class KimiProvider(BaseProvider):
    """Moonshot AI (Kimi) API provider - OpenAI compatible"""

    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="Kimi Provider",
            type="kimi",
            description="Moonshot AI Kimi API provider with OpenAI SDK compatibility",
            version="1.0.0",
            author="HarborPilot Team",
            documentation_url="https://platform.moonshot.ai/docs/api/chat",
            supported_features=[
                "health_check",
                "model_listing",
                "chat_completions",
                "streaming",
                "multimodal",
                "chinese_support",
                "context_window",
            ],
            cost_class="METERED",
            provider_category="LLM",
            autonomous_file_access=False,
            requires_file_interfaces=False,
            model_listing_method="API",
        )

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "base_url": "https://api.moonshot.cn/v1",
            "api_key": "",
            "api_key_ref": "keychain:kimi",
            "api_path": DEFAULT_CHAT_PATH,
            "timeout": 60,
            "retries": 3,
            "model": "kimi-k2-thinking-turbo",
            "temperature": 0.7,
            "top_p": 1.0,
            "max_tokens": 2048,
            "streaming": False,
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        normalized = dict(config)

        # Validate base URL
        base_url = str(config.get("base_url") or "").strip()
        if not base_url:
            errors.append("Base URL is required")
        else:
            normalized["base_url"] = base_url.rstrip("/")

        # Validate API key
        api_key = config.get("api_key", "")
        api_key_ref = config.get("api_key_ref", "")
        if not api_key and not api_key_ref:
            errors.append("API key or API key reference is required")

        # Validate API path
        api_path = str(config.get("api_path") or DEFAULT_CHAT_PATH).strip()
        if not api_path:
            errors.append("API path is required")
        else:
            normalized["api_path"] = api_path

        # Validate timeout
        timeout = config.get("timeout", 60)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            warnings.append("Invalid timeout, using default 60")
            normalized["timeout"] = 60

        # Validate retries
        retries = config.get("retries", 3)
        if not isinstance(retries, int) or retries < 0:
            warnings.append("Invalid retries, using default 3")
            normalized["retries"] = 3

        # Validate temperature (0-2 for Kimi)
        temperature = config.get("temperature", 0.7)
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            warnings.append("Invalid temperature, using default 0.7")
            normalized["temperature"] = 0.7

        # Validate top_p (0-1 for Kimi)
        top_p = config.get("top_p", 1.0)
        if not isinstance(top_p, (int, float)) or top_p < 0 or top_p > 1:
            warnings.append("Invalid top_p, using default 1.0")
            normalized["top_p"] = 1.0

        # Validate max_tokens
        max_tokens = config.get("max_tokens", 2048)
        if not isinstance(max_tokens, int) or max_tokens < 1:
            warnings.append("Invalid max_tokens, using default 2048")
            normalized["max_tokens"] = 2048

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_config=normalized,
        )

    def _base_url(self, config: Dict[str, Any]) -> str:
        base = str(config.get("base_url") or "").strip()
        return base.rstrip("/")

    def _headers(self, config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def health(self, config: Dict[str, Any]) -> HealthResult:
        """Health check using chat completion API instead of /models endpoint"""
        base = self._base_url(config)
        api_path = str(config.get("api_path", DEFAULT_CHAT_PATH)).strip()
        url = f"{base}{api_path}"
        timeout = int(config.get("timeout") or 30)
        
        api_key = config.get("api_key")
        if not api_key:
            return HealthResult(ok=False, latency_ms=0, error="API key is required")
        
        # Use a simple test message for health check
        test_payload = {
            "model": config.get("model") or "moonshot-v1-8k",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 10,
            "stream": False,
        }
        
        start = time.time()
        try:
            response = requests.post(
                url,
                headers=self._headers(config, api_key),
                json=test_payload,
                timeout=timeout if timeout > 0 else None,
            )
            latency_ms = int((time.time() - start) * 1000)
            
            if response.status_code == 401:
                return HealthResult(ok=False, latency_ms=latency_ms, error="Authentication failed: please check your API key")
            elif response.status_code == 404:
                return HealthResult(ok=False, latency_ms=latency_ms, error="API endpoint not found: please check api_path configuration")
            
            response.raise_for_status()
            
            # Validate response format
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
        base = self._base_url(config)
        models_path = str(config.get("models_path", DEFAULT_MODELS_PATH)).strip()
        url = f"{base}{models_path}"
        timeout = int(config.get("timeout") or 10)
        
        api_key = config.get("api_key")
        if not api_key:
            return ModelListResult(ok=False, supported=True, models=[], error="API key is required")
        
        try:
            response = requests.get(
                url,
                headers=self._headers(config, api_key),
                timeout=timeout if timeout > 0 else None,
            )
            response.raise_for_status()
            payload = response.json()
            
            models: List[ModelInfo] = []
            
            # OpenAI-compatible response format
            if isinstance(payload, dict):
                model_list = payload.get("data") or payload.get("model_list") or []
                if isinstance(model_list, list):
                    for item in model_list:
                        if isinstance(item, dict):
                            model_id = str(item.get("id") or item.get("model_name") or "").strip()
                            if model_id:
                                context_window = item.get("context_window")
                                label = f"{model_id}"
                                if context_window:
                                    label += f" ({context_window // 1000}K context)"
                                models.append(ModelInfo(id=model_id, label=label, raw=item))
                        elif isinstance(item, str):
                            models.append(ModelInfo(id=item.strip()))
            
            # Fallback to known Kimi models if API doesn't return list
            if not models:
                known_models = [
                    # K2.5 series (latest flagship)
                    ("kimi-k2.5", "256K context"),
                    ("kimi-k2-0905-preview", "256K context"),
                    ("kimi-k2-0711-preview", "128K context"),
                    
                    # K2 Thinking series (reasoning models)
                    ("kimi-k2-thinking", "256K context"),
                    ("kimi-k2-thinking-turbo", "256K context"),
                    
                    # K2 Turbo series (fast response)
                    ("kimi-k2-turbo-preview", "256K context"),
                    ("kimi-k2-turbo", "256K context"),
                    
                    # Moonshot V1 series (classic)
                    ("moonshot-v1-8k", "8K context"),
                    ("moonshot-v1-32k", "32K context"),
                    ("moonshot-v1-128k", "128K context"),
                    
                    # Vision models
                    ("moonshot-v1-8k-vision-preview", "8K context"),
                    ("moonshot-v1-32k-vision-preview", "32K context"),
                    ("moonshot-v1-128k-vision-preview", "128K context"),
                ]
                for model_id, context in known_models:
                    models.append(ModelInfo(id=model_id, label=f"{model_id} ({context})"))
            
            return ModelListResult(ok=True, supported=True, models=models)
        except Exception as exc:
            return ModelListResult(ok=False, supported=True, models=[], error=str(exc))

    def invoke(self, prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
        base = self._base_url(config)
        timeout = int(config.get("timeout") or 60)
        retries = int(config.get("retries") or 0)
        api_path = str(config.get("api_path", DEFAULT_CHAT_PATH)).strip()
        url = f"{base}{api_path}"
        
        api_key = config.get("api_key")
        if not api_key:
            usage = estimate_usage(prompt, "")
            return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error="API key is required")
        
        # Build Kimi API payload (OpenAI compatible)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature") or 0.7),
            "top_p": float(config.get("top_p") or 1.0),
            "max_tokens": int(config.get("max_tokens") or 2048),
            "stream": bool(config.get("streaming", False)),
        }
        
        attempt = 0
        start = time.time()
        
        while True:
            try:
                response = requests.post(
                    url,
                    headers=self._headers(config, api_key),
                    json=payload,
                    timeout=timeout if timeout > 0 else None,
                )
                response.raise_for_status()
                data = response.json()
                latency_ms = int((time.time() - start) * 1000)
                
                # Extract output from OpenAI-compatible response
                output = ""
                if isinstance(data, dict):
                    choices = data.get("choices", [])
                    if choices and len(choices) > 0:
                        first_choice = choices[0]
                        if isinstance(first_choice, dict):
                            message = first_choice.get("message", {})
                            output = message.get("content", "")
                
                usage = self._usage_from_response(prompt, output, data)
                
                return InvokeResult(
                    ok=True,
                    output=output.strip(),
                    latency_ms=latency_ms,
                    usage=usage,
                    raw=data
                )
            except Exception as exc:
                attempt += 1
                if attempt > retries:
                    latency_ms = int((time.time() - start) * 1000)
                    usage = estimate_usage(prompt, "")
                    return InvokeResult(
                        ok=False,
                        output="",
                        latency_ms=latency_ms,
                        usage=usage,
                        error=str(exc)
                    )
                time.sleep(0.5)

    def _usage_from_response(self, prompt: str, output: str, response: Dict[str, Any]) -> Usage:
        """Extract usage information from Kimi API response"""
        usage_data = response.get("usage", {}) if isinstance(response, dict) else {}
        
        if usage_data:
            return Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
        
        # Fallback to estimation
        return estimate_usage(prompt, output)

    async def invoke_stream(
        self, prompt: str, model: str, config: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        True streaming invoke for Kimi API using aiohttp.
        
        Kimi API is OpenAI-compatible, so we use SSE format:
        data: {"choices":[{"delta":{"content":"hello"}}]}
        
        Args:
            prompt: The prompt to send
            model: The model name (e.g., "kimi-k2-turbo-preview")
            config: Provider configuration
            
        Yields:
            Text tokens/chunks from the LLM response
        """
        base = self._base_url(config)
        timeout = int(config.get("timeout") or 60)
        api_path = str(config.get("api_path", DEFAULT_CHAT_PATH)).strip()
        url = f"{base}{api_path}"
        
        api_key = config.get("api_key")
        if not api_key:
            yield "Error: API key is required for Kimi provider"
            return
        
        # Build streaming payload
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature") or 0.7),
            "top_p": float(config.get("top_p") or 1.0),
            "max_tokens": int(config.get("max_tokens") or 2048),
            "stream": True,  # Enable streaming
        }
        
        headers = self._headers(config, api_key)
        # Override for streaming
        headers["Accept"] = "text/event-stream"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout if timeout > 0 else None),
                ) as response:
                    response.raise_for_status()
                    
                    # Process SSE stream
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        
                        if not line_str or not line_str.startswith('data: '):
                            continue
                        
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            
                            if choices and len(choices) > 0:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                
                                if content:
                                    yield content
                                    
                        except json.JSONDecodeError:
                            continue
                        except Exception:
                            continue
                            
        except aiohttp.ClientError as e:
            yield f"Error: Network error - {str(e)}"
        except asyncio.TimeoutError:
            yield "Error: Request timeout"
        except Exception as e:
            yield f"Error: {str(e)}"
