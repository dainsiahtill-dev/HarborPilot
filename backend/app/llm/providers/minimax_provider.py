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


class MiniMaxProvider(BaseProvider):
    """MiniMax API provider with thinking extraction"""
    
    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="MiniMax Provider",
            type="minimax",
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
            "type": "minimax",
            "name": "MiniMax",
            "base_url": "https://api.minimaxi.com/v1",
            "api_path": "/text/chatcompletion_pro",
            "models_path": "/query/model_list",
            "timeout": 60,
            "retries": 3,
            "temperature": 0.7,
            "max_tokens": 2048
        }
    
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with authentication"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        api_key = self.config.get("api_key") or self._get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        return headers
    
    def _extract_thinking(self, content: str) -> Optional[str]:
        """Extract thinking tags from response"""
        pattern = r'<think[^>]*>(.*?)</think>'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        return '\n'.join(matches) if matches else None
    
    def _clean_content(self, content: str) -> str:
        """Remove thinking tags from final content"""
        return re.sub(r'<think[^>]*>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE).strip()
    
    def _extract_usage(self, response: Dict[str, Any]) -> Optional[Usage]:
        """Extract token usage from MiniMax response"""
        try:
            usage_info = response.get("usage", {})
            return estimate_usage(
                prompt_tokens=usage_info.get("prompt_tokens", 0),
                completion_tokens=usage_info.get("completion_tokens", 0),
                total_tokens=usage_info.get("total_tokens", 0)
            )
        except Exception:
            return None
    
    def _extract_thinking_support(self, response: Dict[str, Any]) -> bool:
        """Check if thinking mode is supported"""
        try:
            model = response.get("model", "")
            thinking_models = ["abab6.5s-chat", "abab6.5-chat", "abab6-chat", "MiniMax-M2"]
            return any(m in model for m in thinking_models)
        except Exception:
            return False
    
    def _estimate_thinking_cost(self, thinking: str) -> Optional[Usage]:
        """Estimate cost for thinking tokens"""
        if not thinking:
            return None
        try:
            token_count = len(thinking) // 4
            return estimate_usage(
                prompt_tokens=0,
                completion_tokens=token_count,
                total_tokens=token_count
            )
        except Exception:
            return None
    
    async def health_check(self) -> HealthResult:
        """Check MiniMax API health"""
        start_time = time.time()
        try:
            base_url = self.config.get("base_url", "").rstrip('/')
            api_path = self.config.get("api_path", "/text/chatcompletion_pro")
            url = f"{base_url}{api_path}"
            
            headers = self._get_headers()
            
            test_payload = {
                "model": self.config.get("model", "MiniMax-M2.1"),
                "messages": [{"role": "user", "content": "1+1="}],
                "max_tokens": 5
            }
            
            response = await self._make_request("POST", url, json=test_payload, headers=headers)
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                is_thinking = self._extract_thinking_support(data)
                return HealthResult(
                    status="ready" if response.status_code == 200 else "degraded",
                    latency_ms=latency_ms,
                    message="MiniMax API is healthy" if response.status_code == 200 else f"HTTP {response.status_code}",
                    models_available=True,
                    thinking_support=is_thinking
                )
            else:
                return HealthResult(
                    status="error",
                    latency_ms=latency_ms,
                    message=f"MiniMax API error: {response.status_code}",
                    models_available=False,
                    thinking_support=False
                )
                
        except requests.exceptions.ConnectionError:
            return HealthResult(
                status="error",
                latency_ms=(time.time() - start_time) * 1000,
                message="Cannot connect to MiniMax API",
                models_available=False,
                thinking_support=False
            )
        except Exception as e:
            return HealthResult(
                status="error",
                latency_ms=(time.time() - start_time) * 1000,
                message=f"Health check failed: {str(e)}",
                models_available=False,
                thinking_support=False
            )
    
    async def list_models(self) -> ModelListResult:
        """List available MiniMax models"""
        try:
            base_url = self.config.get("base_url", "").rstrip('/')
            models_path = self.config.get("models_path", "/query/model_list")
            url = f"{base_url}{models_path}"
            
            headers = self._get_headers()
            
            response = await self._make_request("GET", url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("base_resp", {}).get("R_status_code") == "1000":
                    model_list = data.get("data", {}).get("models", [])
                    models = [
                        ModelInfo(
                            id=model.get("model_id", ""),
                            name=model.get("model_name", ""),
                            description=model.get("description", ""),
                            context_length=model.get("context_length", 32768)
                        )
                        for model in model_list
                    ]
                    
                    return ModelListResult(
                        models=models,
                        default="MiniMax-M2.1",
                        message="Success"
                    )
                else:
                    fallback_models = [
                        ModelInfo(
                            id="MiniMax-M2.1",
                            name="MiniMax-M2.1",
                            description="MiniMax M2.1 - Latest model with 200K+ context"
                        ),
                        ModelInfo(
                            id="MiniMax-M2.1-lightning",
                            name="MiniMax-M2.1-lightning",
                            description="MiniMax M2.1 Lightning - Fast variant"
                        ),
                        ModelInfo(
                            id="MiniMax-M2",
                            name="MiniMax-M2",
                            description="MiniMax M2 - Advanced reasoning model"
                        )
                    ]
                    return ModelListResult(
                        models=fallback_models,
                        default="MiniMax-M2.1",
                        message="Using fallback model list"
                    )
            else:
                return ModelListResult(
                    models=[],
                    default="MiniMax-M2.1",
                    error=f"Failed to fetch models: {response.status_code}"
                )
                
        except Exception as e:
            fallback_models = [
                ModelInfo(
                    id="MiniMax-M2.1",
                    name="MiniMax-M2.1",
                    description="MiniMax M2.1 - Latest model with 200K+ context"
                ),
                ModelInfo(
                    id="MiniMax-M2.1-lightning",
                    name="MiniMax-M2.1-lightning",
                    description="MiniMax M2.1 Lightning - Fast variant"
                ),
                ModelInfo(
                    id="MiniMax-M2",
                    name="MiniMax-M2",
                    description="MiniMax M2 - Advanced reasoning model"
                )
            ]
            return ModelListResult(
                models=fallback_models,
                default="MiniMax-M2.1",
                error=str(e)
            )
    
    async def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> InvokeResult:
        """Invoke MiniMax API"""
        start_time = time.time()
        try:
            base_url = self.config.get("base_url", "").rstrip('/')
            api_path = self.config.get("api_path", "/text/chatcompletion_pro")
            url = f"{base_url}{api_path}"
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if context:
                messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{prompt}"})
            else:
                messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.config.get("model", "MiniMax-M2.1"),
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
                "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 2048)),
                "top_p": kwargs.get("top_p", self.config.get("top_p", 0.95)),
                "stream": stream
            }
            
            response = await self._make_request(
                "POST", 
                url, 
                json=payload,
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                
                thinking = self._extract_thinking(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
                raw_usage = self._extract_usage(data)
                thinking_usage = self._estimate_thinking_cost(thinking) if thinking else None
                
                if raw_usage and thinking_usage:
                    final_usage = Usage(
                        prompt_tokens=raw_usage.prompt_tokens,
                        completion_tokens=raw_usage.completion_tokens + thinking_usage.completion_tokens,
                        total_tokens=raw_usage.total_tokens + thinking_usage.total_tokens
                    )
                else:
                    final_usage = raw_usage or thinking_usage
                
                return InvokeResult(
                    status="success",
                    content=self._clean_content(data.get("choices", [{}])[0].get("message", {}).get("content", "")),
                    thinking=thinking,
                    usage=final_usage,
                    model=payload["model"],
                    latency_ms=(time.time() - start_time) * 1000,
                    token_count=final_usage.completion_tokens if final_usage else None
                )
            else:
                return InvokeResult(
                    status="error",
                    content="",
                    error=f"MiniMax API error: {response.status_code} - {response.text}",
                    latency_ms=(time.time() - start_time) * 1000
                )
                
        except Exception as e:
            return InvokeResult(
                status="error",
                content="",
                error=f"Invoke failed: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000
            )
    
    async def validate(self) -> ValidationResult:
        """Validate MiniMax configuration"""
        api_key = self.config.get("api_key") or self._get_api_key()
        if not api_key:
            return ValidationResult(
                valid=False,
                message="Missing API key"
            )
        
        base_url = self.config.get("base_url", "").rstrip('/')
        if not base_url:
            return ValidationResult(
                valid=False,
                message="Missing base URL"
            )
        
        try:
            health = await self.health_check()
            if health.status == "ready":
                return ValidationResult(
                    valid=True,
                    message="MiniMax configuration is valid"
                )
            else:
                return ValidationResult(
                    valid=False,
                    message=f"MiniMax API error: {health.message}"
                )
        except Exception as e:
            return ValidationResult(
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
