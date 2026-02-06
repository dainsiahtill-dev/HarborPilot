from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import requests
import re

from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage
from .base_provider import (
    BaseProvider, ProviderInfo, ValidationResult, ThinkingInfo, 
    WorkingDirConfig
)


class MaxminiProvider(BaseProvider):
    """MiniMax API provider with thinking extraction"""
    
    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="MiniMax Provider",
            type="maxmini",
            description="MiniMax API provider for M2-her model",
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
            "base_url": "https://api.minimaxi.com/v1",
            "api_key": "",
            "api_key_ref": "keychain:minimax",
            "api_path": "/text/chatcompletion_v2",
            "models_path": "/query/model_list",
            "timeout": 60,
            "retries": 3,
            "model": "M2-her",
            "temperature": 1.0,
            "top_p": 0.95,
            "max_tokens": 2048,
            "stream": False,
            "thinking_extraction": {
                "enabled": True,
                "patterns": [
                    r"<思考>(.*?)</思考>",
                    r"<thinking>(.*?)</thinking>",
                    r"```思考(.*?)```",
                    r"让我想想(.*?)(?:\n\n|\n[A-Z\u4e00-\u9fff])",
                    r"我需要考虑(.*?)(?:\n\n|\n[A-Z\u4e00-\u9fff])"
                ],
                "confidence_threshold": 0.6
            },
            "model_specific": {
                "M2-her": {
                    "max_tokens": 2048,
                    "supports_thinking": True
                }
            }
        }
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        normalized = config.copy()
        
        # Validate base URL
        base_url = str(config.get("base_url", "https://api.minimax.chat/v1")).strip()
        if not base_url:
            errors.append("Base URL is required")
        else:
            normalized["base_url"] = base_url.rstrip("/")
        
        # Validate API key
        api_key = config.get("api_key", "")
        api_key_ref = config.get("api_key_ref", "")
        if not api_key and not api_key_ref:
            errors.append("API key or API key reference is required")
        
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
        
        # Validate temperature (0-1 for MiniMax M2-her)
        temperature = config.get("temperature", 1.0)
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 1:
            warnings.append("Invalid temperature, using default 1.0")
            normalized["temperature"] = 1.0
        
        # Validate top_p (0-1 for MiniMax M2-her)
        top_p = config.get("top_p", 0.95)
        if not isinstance(top_p, (int, float)) or top_p < 0 or top_p > 1:
            warnings.append("Invalid top_p, using default 0.95")
            normalized["top_p"] = 0.95
        
        # Validate max_tokens (1-2048 for MiniMax M2-her)
        max_tokens = config.get("max_tokens", 2048)
        if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 2048:
            warnings.append("Invalid max_tokens, using default 2048")
            normalized["max_tokens"] = 2048
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_config=normalized
        )

    def __init__(self):
        pass
    
    def _base_url(self, config: Dict[str, Any]) -> str:
        base = str(config.get("base_url") or "").strip()
        return base.rstrip("/")
    
    def _headers(self, config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Add any custom headers
        extra = config.get("headers") or {}
        if isinstance(extra, dict):
            for key, value in extra.items():
                if value is not None:
                    headers[str(key)] = str(value)
        
        return headers
    
    def health(self, config: Dict[str, Any]) -> HealthResult:
        base = self._base_url(config)
        models_path = str(config.get("models_path", "/query/model_list")).strip()
        url = base + models_path
        timeout = int(config.get("timeout") or 10)
        
        api_key = config.get("api_key")
        if not api_key:
            return HealthResult(ok=False, latency_ms=0, error="API key is required")
        
        start = time.time()
        try:
            response = requests.get(
                url, 
                headers=self._headers(config, api_key), 
                timeout=timeout if timeout > 0 else None
            )
            response.raise_for_status()
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=True, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return HealthResult(ok=False, latency_ms=latency_ms, error=str(exc))
    
    def list_models(self, config: Dict[str, Any]) -> ModelListResult:
        base = self._base_url(config)
        models_path = str(config.get("models_path", "/query/model_list")).strip()
        url = base + models_path
        timeout = int(config.get("timeout") or 10)
        
        api_key = config.get("api_key")
        if not api_key:
            return ModelListResult(ok=False, supported=True, models=[], error="API key is required")
        
        try:
            response = requests.get(
                url, 
                headers=self._headers(config, api_key), 
                timeout=timeout if timeout > 0 else None
            )
            response.raise_for_status()
            payload = response.json()
            
            models: List[ModelInfo] = []
            
            # MiniMax API response format
            if isinstance(payload, dict):
                model_list = payload.get("model_list") or payload.get("data") or []
                if isinstance(model_list, list):
                    for item in model_list:
                        if isinstance(item, dict):
                            model_id = str(item.get("model_name") or item.get("id") or "").strip()
                            if model_id:
                                models.append(ModelInfo(id=model_id, raw=item))
                        elif isinstance(item, str):
                            models.append(ModelInfo(id=item.strip()))
            
            # Fallback to known MiniMax models if API doesn't return list
            if not models:
                known_models = ["M2-her"]
                for model_id in known_models:
                    models.append(ModelInfo(id=model_id, label=f"MiniMax {model_id}"))
            
            return ModelListResult(ok=True, supported=True, models=models)
        except Exception as exc:
            return ModelListResult(ok=False, supported=True, models=[], error=str(exc))
    
    def invoke(self, prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
        base = self._base_url(config)
        timeout = int(config.get("timeout") or 60)
        retries = int(config.get("retries") or 0)
        api_path = str(config.get("api_path", "/text/chatcompletion_v2")).strip()
        url = base + api_path
        
        api_key = config.get("api_key")
        if not api_key:
            usage = estimate_usage(prompt, "")
            return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error="API key is required")
        
        # Build MiniMax API payload for v2 endpoint
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature") or 1.0),
            "top_p": float(config.get("top_p") or 0.95),
            "max_tokens": int(config.get("max_tokens") or 2048),
            "stream": bool(config.get("stream", False))
        }
        
        # Add model-specific settings
        model_config = config.get("model_specific", {}).get(model, {})
        if model_config:
            payload.update(model_config)
        
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
                
                output = self._extract_output(data)
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
    
    @classmethod
    def extract_thinking_support(cls, response: Dict[str, Any]) -> ThinkingInfo:
        """Extract thinking information from MiniMax response"""
        if not isinstance(response, dict) or "output" not in response:
            return ThinkingInfo(
                supports_thinking=False,
                confidence=0.0,
                format=None,
                thinking_text=None,
                extraction_method="minimax_default"
            )
        
        output = response.get("output", "")
        config = response.get("config", {})
        thinking_config = config.get("thinking_extraction", {})
        
        if not thinking_config.get("enabled", True):
            return ThinkingInfo(
                supports_thinking=False,
                confidence=0.0,
                format=None,
                thinking_text=None,
                extraction_method="disabled"
            )
        
        # MiniMax-specific patterns (including Chinese)
        patterns = thinking_config.get("patterns", [
            r"<思考>(.*?)</思考>",
            r"<thinking>(.*?)</thinking>",
            r"```思考(.*?)```",
            r"让我想想(.*?)(?:\n\n|\n[A-Z\u4e00-\u9fff])",
            r"我需要考虑(.*?)(?:\n\n|\n[A-Z\u4e00-\u9fff])",
            r"分析一下(.*?)(?:\n\n|\n[A-Z\u4e00-\u9fff])"
        ])
        
        confidence_threshold = thinking_config.get("confidence_threshold", 0.6)
        
        for pattern in patterns:
            try:
                match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
                if match:
                    thinking_text = match.group(1).strip()
                    confidence = cls._calculate_thinking_confidence(thinking_text)
                    format_type = "chinese_xml" if "思考" in pattern else "xml" if "<thinking>" in pattern else "markdown"
                    
                    if confidence >= confidence_threshold:
                        return ThinkingInfo(
                            supports_thinking=True,
                            confidence=confidence,
                            format=format_type,
                            thinking_text=thinking_text,
                            extraction_method="minimax_pattern"
                        )
                    
                    return ThinkingInfo(
                        supports_thinking=True,
                        confidence=confidence,
                        format=format_type,
                        thinking_text=thinking_text,
                        extraction_method="minimax_pattern_low_confidence"
                    )
            except re.error:
                continue
        
        # Check for Chinese reasoning indicators
        chinese_reasoning = [
            "让我分析", "我需要考虑", "从角度来看", "综合分析",
            "首先", "其次", "最后", "因此", "所以", "但是"
        ]
        
        output_lower = output.lower()
        if any(indicator in output_lower for indicator in chinese_reasoning):
            return ThinkingInfo(
                supports_thinking=True,
                confidence=0.4,
                format="chinese_text",
                thinking_text=None,
                extraction_method="minimax_chinese_keyword"
            )
        
        return ThinkingInfo(
            supports_thinking=False,
            confidence=0.0,
            format=None,
            thinking_text=None,
            extraction_method="no_thinking"
        )
    
    @classmethod
    def get_working_directory_config(cls, config: Dict[str, Any]) -> WorkingDirConfig:
        """Get working directory configuration"""
        return WorkingDirConfig(
            target_directory=None,  # MiniMax is cloud-based
            auto_create=False,
            cleanup_after=False,
            environment_vars={}
        )
    
    @staticmethod
    def _calculate_thinking_confidence(thinking_text: str) -> float:
        """Calculate confidence score for thinking extraction"""
        if not thinking_text:
            return 0.0
        
        # MiniMax-specific confidence factors (Chinese language considerations)
        length_score = min(len(thinking_text) / 200, 1.0)  # Chinese tends to be more concise
        
        # Chinese reasoning indicators
        chinese_reasoning_words = ["因为", "所以", "但是", "然而", "首先", "其次", "最后", "因此"]
        reasoning_score = sum(0.12 for word in chinese_reasoning_words if word in thinking_text)
        
        # Structure indicators
        structure_score = 0.2 if any(punct in thinking_text for punct in ["。", "！", "？", "，"]) else 0.0
        
        return min(length_score + reasoning_score + structure_score, 1.0)
    
    @staticmethod
    def _extract_output(data: Dict[str, Any]) -> str:
        """Extract output from MiniMax API response"""
        if not isinstance(data, dict):
            return ""
        
        # MiniMax API response format
        reply = data.get("reply") or data.get("output") or data.get("choices", [])
        if isinstance(reply, str):
            return reply
        elif isinstance(reply, list) and reply:
            first_choice = reply[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message") or first_choice
                if isinstance(message, dict):
                    return str(message.get("content") or "")
                return str(first_choice.get("content") or "")
        
        return ""
    
    @staticmethod
    def _usage_from_response(prompt: str, output: str, data: Dict[str, Any]) -> Usage:
        """Extract usage information from MiniMax API response"""
        try:
            # MiniMax may not return usage info, so we estimate
            usage = data.get("usage") if isinstance(data, dict) else None
            if isinstance(usage, dict):
                prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
                total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
                
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
        
        # Fallback to estimation
        return estimate_usage(prompt, output)
