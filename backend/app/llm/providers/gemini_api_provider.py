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


class GeminiAPIProvider(BaseProvider):
    """Google Gemini API provider with thinking extraction"""
    
    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="Gemini API Provider",
            type="gemini_api",
            description="Google Gemini API provider",
            version="1.0.0",
            author="HarborPilot Team",
            documentation_url="https://ai.google.dev/",
            supported_features=[
                "thinking_extraction",
                "large_context",
                "model_listing",
                "health_check",
                "file_operations_via_interface",
                "multimodal_support"
            ],
            cost_class="METERED",
            provider_category="LLM",
            autonomous_file_access=False,
            requires_file_interfaces=True,
            model_listing_method="API"
        )
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "base_url": "https://generativelanguage.googleapis.com",
            "api_key": "",
            "api_key_ref": "keychain:gemini",
            "api_path": "/v1beta/models/{model}:generateContent",
            "models_path": "/v1beta/models",
            "timeout": 60,
            "retries": 3,
            "temperature": 0.7,
            "max_tokens": 8192,
            "thinking_extraction": {
                "enabled": True,
                "patterns": [
                    r"<thinking>(.*?)</thinking>",
                    r"```thinking(.*?)```",
                    r"Let me think(.*?)(?:\n\n|\n[A-Z])",
                    r"I need to consider(.*?)(?:\n\n|\n[A-Z])",
                    r"Looking at this(.*?)(?:\n\n|\n[A-Z])",
                    r"Step by step(.*?)(?:\n\n|\n[A-Z])"
                ],
                "confidence_threshold": 0.6
            },
            "model_specific": {
                "gemini-1.5-pro": {
                    "max_tokens": 2097152,
                    "supports_thinking": True,
                    "context_window": 2000000
                },
                "gemini-1.5-flash": {
                    "max_tokens": 1048576,
                    "supports_thinking": True,
                    "context_window": 1000000
                },
                "gemini-1.0-pro": {
                    "max_tokens": 32768,
                    "supports_thinking": False,
                    "context_window": 32768
                }
            }
        }
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        normalized = config.copy()
        
        # Validate base URL
        base_url = str(config.get("base_url", "https://generativelanguage.googleapis.com")).strip()
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
        
        # Validate temperature
        temperature = config.get("temperature", 0.7)
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            warnings.append("Invalid temperature, using default 0.7")
            normalized["temperature"] = 0.7
        
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
            "x-goog-api-key": api_key or ""
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
        models_path = str(config.get("models_path", "/v1beta/models")).strip()
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
        models_path = str(config.get("models_path", "/v1beta/models")).strip()
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
            
            # Gemini API response format
            if isinstance(payload, dict):
                model_list = payload.get("models") or []
                if isinstance(model_list, list):
                    for item in model_list:
                        if isinstance(item, dict):
                            model_id = str(item.get("name") or "").strip()
                            # Extract model name from full path like "models/gemini-1.5-pro"
                            if "/" in model_id:
                                model_id = model_id.split("/")[-1]
                            
                            if model_id:
                                display_name = str(item.get("displayName") or model_id)
                                description = str(item.get("description") or "")
                                label = f"{display_name} - {description}" if description else display_name
                                models.append(ModelInfo(id=model_id, label=label, raw=item))
            
            # Fallback to known Gemini models if API doesn't return list
            if not models:
                known_models = [
                    ("gemini-1.5-pro", "Gemini 1.5 Pro - Advanced multimodal model"),
                    ("gemini-1.5-flash", "Gemini 1.5 Flash - Fast multimodal model"),
                    ("gemini-1.0-pro", "Gemini 1.0 Pro - Legacy text model")
                ]
                for model_id, label in known_models:
                    models.append(ModelInfo(id=model_id, label=label))
            
            return ModelListResult(ok=True, supported=True, models=models)
        except Exception as exc:
            return ModelListResult(ok=False, supported=True, models=[], error=str(exc))
    
    def invoke(self, prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
        base = self._base_url(config)
        timeout = int(config.get("timeout") or 60)
        retries = int(config.get("retries") or 0)
        
        api_key = config.get("api_key")
        if not api_key:
            usage = estimate_usage(prompt, "")
            return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error="API key is required")
        
        # Build Gemini API URL
        api_path = str(config.get("api_path", "/v1beta/models/{model}:generateContent")).strip()
        url = base + api_path.replace("{model}", model)
        
        # Build Gemini API payload
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": float(config.get("temperature") or 0.7),
                "maxOutputTokens": int(config.get("max_tokens") or 8192),
                "candidateCount": 1
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }
        
        # Add model-specific settings
        model_config = config.get("model_specific", {}).get(model, {})
        if model_config:
            if "max_tokens" in model_config:
                payload["generationConfig"]["maxOutputTokens"] = model_config["max_tokens"]
        
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
        """Extract thinking information from Gemini API response"""
        if not isinstance(response, dict) or "output" not in response:
            return ThinkingInfo(
                supports_thinking=False,
                confidence=0.0,
                format=None,
                thinking_text=None,
                extraction_method="gemini_api_default"
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
        
        # Gemini API-specific patterns
        patterns = thinking_config.get("patterns", [
            r"<thinking>(.*?)</thinking>",
            r"```thinking(.*?)```",
            r"Let me think(.*?)(?:\n\n|\n[A-Z])",
            r"I need to consider(.*?)(?:\n\n|\n[A-Z])",
            r"Looking at this(.*?)(?:\n\n|\n[A-Z])",
            r"Step by step(.*?)(?:\n\n|\n[A-Z])",
            r"My reasoning(.*?)(?:\n\n|\n[A-Z])"
        ])
        
        confidence_threshold = thinking_config.get("confidence_threshold", 0.6)
        
        for pattern in patterns:
            try:
                match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
                if match:
                    thinking_text = match.group(1).strip()
                    confidence = cls._calculate_thinking_confidence(thinking_text)
                    
                    if confidence >= confidence_threshold:
                        return ThinkingInfo(
                            supports_thinking=True,
                            confidence=confidence,
                            format="xml" if "<thinking>" in pattern else "markdown",
                            thinking_text=thinking_text,
                            extraction_method="gemini_api_pattern"
                        )
            except re.error:
                continue
        
        # Check for Gemini API-specific reasoning indicators
        reasoning_indicators = [
            "let me analyze", "i should consider", "looking at the context",
            "to approach this", "my reasoning", "step by step",
            "first", "next", "finally", "therefore", "however"
        ]
        
        output_lower = output.lower()
        if any(indicator in output_lower for indicator in reasoning_indicators):
            return ThinkingInfo(
                supports_thinking=True,
                confidence=0.4,
                format="text",
                thinking_text=None,
                extraction_method="gemini_api_keyword"
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
            target_directory=None,  # Gemini API is cloud-based
            auto_create=False,
            cleanup_after=False,
            environment_vars={}
        )
    
    @staticmethod
    def _calculate_thinking_confidence(thinking_text: str) -> float:
        """Calculate confidence score for thinking extraction"""
        if not thinking_text:
            return 0.0
        
        # Gemini API-specific confidence factors
        length_score = min(len(thinking_text) / 400, 1.0)  # Gemini tends to be detailed
        
        reasoning_words = [
            "because", "therefore", "however", "although", "consider", "analyze", 
            "evaluate", "examine", "first", "next", "finally", "step"
        ]
        reasoning_score = sum(0.08 for word in reasoning_words if word in thinking_text.lower())
        
        # Structure indicators
        structure_score = 0.2 if any(punct in thinking_text for punct in [".", "!", "?", ";", ":"]) else 0.0
        
        # Logical flow indicators
        flow_indicators = ["first", "second", "third", "next", "then", "finally"]
        flow_score = 0.15 if any(indicator in thinking_text.lower() for indicator in flow_indicators) else 0.0
        
        return min(length_score + reasoning_score + structure_score + flow_score, 1.0)
    
    @staticmethod
    def _extract_output(data: Dict[str, Any]) -> str:
        """Extract output from Gemini API response"""
        if not isinstance(data, dict):
            return ""
        
        # Gemini API response format
        candidates = data.get("candidates", [])
        if isinstance(candidates, list) and candidates:
            first_candidate = candidates[0]
            if isinstance(first_candidate, dict):
                content = first_candidate.get("content", {})
                if isinstance(content, dict):
                    parts = content.get("parts", [])
                    if isinstance(parts, list) and parts:
                        first_part = parts[0]
                        if isinstance(first_part, dict):
                            return str(first_part.get("text") or "")
        
        return ""
    
    @staticmethod
    def _usage_from_response(prompt: str, output: str, data: Dict[str, Any]) -> Usage:
        """Extract usage information from Gemini API response"""
        try:
            # Gemini API may return usage metadata
            usage_metadata = data.get("usageMetadata") if isinstance(data, dict) else None
            if isinstance(usage_metadata, dict):
                prompt_tokens = int(usage_metadata.get("promptTokenCount") or 0)
                candidates_tokens = int(usage_metadata.get("candidatesTokenCount") or 0)
                total_tokens = int(usage_metadata.get("totalTokenCount") or (prompt_tokens + candidates_tokens))
                
                if total_tokens > 0:
                    return Usage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=candidates_tokens,
                        total_tokens=total_tokens,
                        estimated=False,
                        prompt_chars=len(prompt or ""),
                        completion_chars=len(output or ""),
                    )
        except Exception:
            pass
        
        # Fallback to estimation
        return estimate_usage(prompt, output)
