from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests
import re

from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage
from .base_provider import BaseProvider, ProviderInfo, ValidationResult


class MiniMaxProvider(BaseProvider):
    """MiniMax API provider with thinking extraction"""

    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="MiniMax Provider",
            type="minimax",
            description="MiniMax API provider for M2 model",
            version="1.0.0",
            author="HarborPilot Team",
            documentation_url="https://platform.minimaxi.com/docs/api-reference/text-chat",
            supported_features=[
                "thinking_extraction",
                "model_listing",
                "health_check",
                "chinese_support",
                "context_window",
                "streaming"
            ],
            cost_class="METERED",
            provider_category="LLM",
            autonomous_file_access=False,
            requires_file_interfaces=False,
            model_listing_method="API"
        )

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "type": "minimax",
            "name": "MiniMax",
            "base_url": "https://api.minimaxi.com/v1",
            "api_path": "/text/chatcompletion_v2",
            "models_path": "/v1/models",
            "timeout": 60,
            "retries": 3,
            "temperature": 0.7,
            "max_tokens": 196608
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        normalized = dict(config)

        base_url = str(config.get("base_url") or "").strip()
        if not base_url:
            errors.append("Base URL is required")
        else:
            normalized["base_url"] = base_url.rstrip("/")

        api_key = config.get("api_key", "")
        if not api_key:
            errors.append("API key is required")

        api_path = str(config.get("api_path") or "/text/chatcompletion_pro").strip()
        if not api_path:
            errors.append("API path is required")
        else:
            normalized["api_path"] = api_path

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
        base = str(config.get("base_url") or "").strip()
        return base.rstrip("/")

    def _headers(self, config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _extract_thinking(self, content: str) -> Optional[str]:
        pattern = r'<think[^>]*>(.*?)</think>'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        return '\n'.join(matches) if matches else None

    def _clean_content(self, content: str) -> str:
        return re.sub(r'<think[^>]*>.*?<\/think>', '', content, flags=re.DOTALL | re.IGNORECASE).strip()

    def health(self, config: Dict[str, Any]) -> HealthResult:
        base = self._base_url(config)
        api_path = str(config.get("api_path", "/text/chatcompletion_v2")).strip()
        url = f"{base}{api_path}"
        timeout = int(config.get("timeout") or 60)

        api_key = config.get("api_key")
        if not api_key:
            return HealthResult(ok=False, latency_ms=0, error="API key is required")

        start = time.time()
        try:
            test_payload = {
                "model": config.get("model", "MiniMax-M2.1"),
                "messages": [{"role": "user", "content": "1+1="}],
                "max_tokens": 5
            }

            response = requests.post(
                url,
                headers=self._headers(config, api_key),
                json=test_payload,
                timeout=timeout if timeout > 0 else None,
            )
            latency_ms = int((time.time() - start) * 1000)

            if response.status_code != 200:
                return HealthResult(ok=False, latency_ms=latency_ms, error=f"HTTP {response.status_code}: {response.text[:100]}")

            return HealthResult(ok=True, latency_ms=latency_ms)

        except requests.exceptions.ConnectionError:
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=False, latency_ms=latency_ms, error="Cannot connect to MiniMax API")
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=False, latency_ms=latency_ms, error=str(exc))

    def list_models(self, config: Dict[str, Any]) -> ModelListResult:
        return ModelListResult(
            ok=True,
            supported=True,
            models=self._get_fallback_models()
        )

    def _get_fallback_models(self) -> List[ModelInfo]:
        return [
            ModelInfo(id="MiniMax-M2.1", label="MiniMax-M2.1"),
            ModelInfo(id="MiniMax-M2.1-lightning", label="MiniMax-M2.1-lightning"),
            ModelInfo(id="MiniMax-M2", label="MiniMax-M2")
        ]

    def invoke(self, prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
        base = self._base_url(config)
        timeout = int(config.get("timeout") or 60)
        retries = int(config.get("retries") or 0)
        api_path = str(config.get("api_path", "/text/chatcompletion_v2")).strip()
        url = f"{base}{api_path}"

        api_key = config.get("api_key")
        if not api_key:
            usage = estimate_usage(prompt, "")
            return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error="API key is required")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature") or 0.7),
            "max_tokens": int(config.get("max_tokens") or 204800),
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
                latency_ms = int((time.time() - start) * 1000)

                if response.status_code != 200:
                    return InvokeResult(
                        ok=False,
                        output="",
                        latency_ms=latency_ms,
                        usage=estimate_usage(prompt, ""),
                        error=f"HTTP {response.status_code}: {response.text[:500]}"
                    )

                is_streaming = payload.get("stream", False)

                if is_streaming:
                    output_parts = []
                    full_response = []

                    for line in response.iter_lines():
                        if not line:
                            continue
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]
                            if data_str.strip() == '[DONE]':
                                break
                            try:
                                chunk_data = json.loads(data_str)
                                full_response.append(chunk_data)
                                choices = chunk_data.get("choices", [])
                                if choices and isinstance(choices, list) and len(choices) > 0:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        output_parts.append(content)
                            except json.JSONDecodeError:
                                continue

                    output = self._clean_content(''.join(output_parts))
                    if output:
                        return InvokeResult(
                            ok=True,
                            output=output,
                            latency_ms=latency_ms,
                            usage=estimate_usage(prompt, output),
                            raw={"chunks": full_response}
                        )
                    else:
                        return InvokeResult(
                            ok=False,
                            output="",
                            latency_ms=latency_ms,
                            usage=estimate_usage(prompt, ""),
                            error="Empty streaming response from MiniMax API"
                        )

                try:
                    data = response.json()
                except Exception as json_err:
                    return InvokeResult(
                        ok=False,
                        output="",
                        latency_ms=latency_ms,
                        usage=estimate_usage(prompt, ""),
                        error=f"JSON parse error: {str(json_err)}, raw: {response.text[:500]}"
                    )

                print(f"[MiniMax] Response data: {json.dumps(data, ensure_ascii=False)[:500]}")

                base_resp = data.get("base_resp", {})
                if isinstance(base_resp, dict) and base_resp.get("status_code") != 0:
                    return InvokeResult(
                        ok=False,
                        output="",
                        latency_ms=latency_ms,
                        usage=estimate_usage(prompt, ""),
                        error=f"MiniMax API Error {base_resp.get('status_code')}: {base_resp.get('status_msg', 'Unknown error')}"
                    )

                output = ""
                if isinstance(data, dict):
                    choices = data.get("choices")
                    if choices and isinstance(choices, list) and len(choices) > 0:
                        first_choice = choices[0]
                        if isinstance(first_choice, dict):
                            message = first_choice.get("message", {})
                            content = message.get("content", "")
                            output = self._clean_content(content)

                if not output:
                    return InvokeResult(
                        ok=False,
                        output="",
                        latency_ms=latency_ms,
                        usage=estimate_usage(prompt, ""),
                        error="Empty response from MiniMax API"
                    )

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
                    return InvokeResult(ok=False, output="", latency_ms=latency_ms, usage=usage, error=str(exc))
                time.sleep(0.5)

    def _usage_from_response(self, prompt: str, output: str, response: Dict[str, Any]) -> Usage:
        usage_data = response.get("usage", {}) if isinstance(response, dict) else {}

        if usage_data:
            return Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

        return estimate_usage(prompt, output)
