from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp
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
            "timeout": 60,
            "retries": 3,
            "temperature": 0.7,
            "max_tokens": 2048
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

        api_path = str(config.get("api_path") or "/text/chatcompletion_v2").strip()
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

    def _headers(self, config: Dict[str, Any], api_key: Optional[str], streaming: bool = False) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        # 根据是否流式设置不同的 Accept 头
        if streaming:
            headers["Accept"] = "text/event-stream"  # 流式响应
        else:
            headers["Accept"] = "application/json"  # 普通响应
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

        # 如果传入的model为空，尝试从配置获取或使用默认值
        if not model:
            model = str(config.get("model") or "MiniMax-M2.1").strip()

        # ===== 调试日志：请求配置 =====
        print(f"\n{'='*60}")
        print("[MiniMax Debug] 请求配置:")
        print(f"  - base_url (from config): {config.get('base_url', 'NOT SET')}")
        print(f"  - api_path (from config): {config.get('api_path', 'NOT SET')}")
        print(f"  - 最终URL: {url}")
        print(f"  - model: {model}")
        print(f"  - streaming (from config): {config.get('streaming', 'NOT SET')}")
        print(f"{'='*60}\n")

        api_key = config.get("api_key")
        if not api_key:
            usage = estimate_usage(prompt, "")
            return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error="API key is required")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature") or 0.7),
            "max_tokens": int(config.get("max_tokens") or 2048),
            "stream": bool(config.get("streaming", False)),
        }

        attempt = 0
        start = time.time()

        while True:
            try:
                is_streaming = bool(config.get("streaming", False))
                headers = self._headers(config, api_key, streaming=is_streaming)
                
                # ===== 调试日志：实际请求 =====
                print(f"\n[MiniMax Debug] 实际请求:")
                print(f"  - URL: {url}")
                print(f"  - Headers: {headers}")
                print(f"  - Payload: {json.dumps(payload, ensure_ascii=False)}")
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=timeout if timeout > 0 else None,
                )
                
                # ===== 调试日志：响应状态 =====
                print(f"\n[MiniMax Debug] 响应状态:")
                print(f"  - Status Code: {response.status_code}")
                print(f"  - Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                if response.status_code != 200:
                    print(f"  - Response Text: {response.text[:500]}")
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
                    thinking_parts = []
                    full_response = []
                    line_count = 0
                    is_json_response = False
                    
                    # ===== 调试日志：开始流式解析 =====
                    print(f"\n[MiniMax Debug] 开始解析流式响应...")
                    
                    # 检查响应类型 - MiniMax可能返回JSON而不是SSE
                    content_type = response.headers.get('Content-Type', '')
                    print(f"[MiniMax Debug] 响应Content-Type: {content_type}")
                    
                    # 如果返回的是JSON，直接解析
                    if 'application/json' in content_type:
                        print(f"[MiniMax Debug] 检测到JSON响应，切换到JSON解析模式")
                        is_json_response = True
                        try:
                            json_data = response.json()
                            print(f"[MiniMax Debug] JSON数据: {json.dumps(json_data, ensure_ascii=False)[:500]}")
                            
                            choices = json_data.get("choices", [])
                            if choices and len(choices) > 0:
                                message = choices[0].get("message", {})
                                content = message.get("content", "")
                                reasoning = message.get("reasoning_content", "")
                                
                                if content:
                                    output_parts.append(content)
                                if reasoning:
                                    thinking_parts.append(reasoning)
                                
                                print(f"[MiniMax Debug] JSON解析成功: content={len(content)}, reasoning={len(reasoning)}")
                                
                                # 将JSON数据也存入full_response用于raw字段
                                full_response.append(json_data)
                        except Exception as e:
                            print(f"[MiniMax Debug] JSON解析失败: {e}")
                    else:
                        # SSE流式解析
                        for line in response.iter_lines():
                            line_count += 1
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
                                    
                                    # Try multiple possible response formats
                                    choices = chunk_data.get("choices", [])
                                    if choices and isinstance(choices, list) and len(choices) > 0:
                                        choice = choices[0]
                                        
                                        # Format 1: OpenAI compatible (delta)
                                        delta = choice.get("delta", {})
                                        if delta:
                                            content = delta.get("content", "")
                                            if content:
                                                output_parts.append(content)
                                            reasoning = delta.get("reasoning_content", "")
                                            if reasoning:
                                                thinking_parts.append(reasoning)
                                        
                                        # Format 2: MiniMax specific (message)
                                        message = choice.get("message", {})
                                        if message:
                                            content = message.get("content", "")
                                            if content:
                                                output_parts.append(content)
                                            reasoning = message.get("reasoning_content", "")
                                            if reasoning:
                                                thinking_parts.append(reasoning)
                                        
                                        # Format 3: Direct text
                                        text = choice.get("text", "")
                                        if text:
                                            output_parts.append(text)
                                except json.JSONDecodeError:
                                    continue
                                except Exception:
                                    continue

                    output = self._clean_content(''.join(output_parts))
                    thinking = self._clean_content(''.join(thinking_parts)) if thinking_parts else None
                    
                    # ===== 调试日志：流式解析完成 =====
                    print(f"\n[MiniMax Debug] 流式解析完成:")
                    if is_json_response:
                        print(f"  - 响应类型: JSON (非流式)")
                    else:
                        print(f"  - 响应类型: SSE流式")
                        print(f"  - 总行数: {line_count}")
                    print(f"  - 内容片段数: {len(output_parts)}")
                    print(f"  - 思考片段数: {len(thinking_parts)}")
                    print(f"  - 输出长度: {len(output)}")
                    print(f"{'='*60}\n")
                    
                    if output:
                        return InvokeResult(
                            ok=True,
                            output=output,
                            latency_ms=latency_ms,
                            usage=estimate_usage(prompt, output),
                            raw={"chunks": full_response},
                            streaming=True,
                            thinking=thinking
                        )
                    else:
                        # If streaming failed but we have raw response, try to extract from it
                        if full_response:
                            print(f"[MiniMax Streaming] Attempting recovery from {len(full_response)} chunks")
                            # Try to extract from the last chunk's message
                            last_chunk = full_response[-1]
                            if isinstance(last_chunk, dict):
                                choices = last_chunk.get("choices", [])
                                if choices and len(choices) > 0:
                                    msg = choices[0].get("message", {})
                                    if msg:
                                        content = msg.get("content", "")
                                        if content:
                                            return InvokeResult(
                                                ok=True,
                                                output=self._clean_content(content),
                                                latency_ms=latency_ms,
                                                usage=estimate_usage(prompt, content),
                                                raw={"chunks": full_response},
                                                streaming=True,
                                                thinking=None
                                            )
                        
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
                thinking = None
                if isinstance(data, dict):
                    choices = data.get("choices")
                    if choices and isinstance(choices, list) and len(choices) > 0:
                        first_choice = choices[0]
                        if isinstance(first_choice, dict):
                            message = first_choice.get("message", {})
                            content = message.get("content", "")
                            output = self._clean_content(content)
                            reasoning = message.get("reasoning_content", "")
                            thinking = self._clean_content(reasoning) if reasoning else None

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
                    raw=data,
                    thinking=thinking
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

    async def invoke_stream(
        self, prompt: str, model: str, config: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Stream invoke the MiniMax LLM with true async streaming.
        
        Uses aiohttp for async HTTP requests and yields tokens as they arrive
        from the MiniMax SSE stream.
        
        Args:
            prompt: The prompt to send
            model: The model name (e.g., "MiniMax-M2.1")
            config: Provider configuration including api_key, base_url, etc.
            
        Yields:
            Text tokens/chunks from the LLM response as they arrive
        """
        base = self._base_url(config)
        timeout = int(config.get("timeout") or 60)
        api_path = str(config.get("api_path", "/text/chatcompletion_v2")).strip()
        url = f"{base}{api_path}"
        
        # If model not provided, use config default
        if not model:
            model = str(config.get("model") or "MiniMax-M2.1").strip()
        
        api_key = config.get("api_key")
        if not api_key:
            yield "Error: API key is required"
            return
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature") or 0.7),
            "max_tokens": int(config.get("max_tokens") or 2048),
            "stream": True,  # Enable streaming
        }
        
        headers = self._headers(config, api_key, streaming=True)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout if timeout > 0 else None),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        yield f"Error: HTTP {response.status}: {error_text[:500]}"
                        return
                    
                    # Process SSE stream
                    content_type = response.headers.get('Content-Type', '')
                    
                    # MiniMax may return JSON instead of SSE in some cases
                    if 'application/json' in content_type:
                        # Non-streaming JSON response - yield all at once
                        json_data = await response.json()
                        choices = json_data.get("choices", [])
                        if choices and len(choices) > 0:
                            message = choices[0].get("message", {})
                            content = message.get("content", "")
                            if content:
                                # Simulate streaming by yielding word by word
                                words = content.split(' ')
                                for word in words:
                                    yield word + ' '
                        return
                    
                    # Process SSE stream line by line
                    buffer = ""
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        
                        if not line_str:
                            continue
                            
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]
                            
                            if data_str.strip() == '[DONE]':
                                break
                            
                            try:
                                chunk_data = json.loads(data_str)
                                choices = chunk_data.get("choices", [])
                                
                                if choices and isinstance(choices, list) and len(choices) > 0:
                                    choice = choices[0]
                                    
                                    # Try delta format (OpenAI compatible)
                                    delta = choice.get("delta", {})
                                    if delta:
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                        continue
                                    
                                    # Try message format (MiniMax specific)
                                    message = choice.get("message", {})
                                    if message:
                                        content = message.get("content", "")
                                        if content and content != buffer:
                                            # Only yield new content
                                            new_content = content[len(buffer):]
                                            if new_content:
                                                yield new_content
                                            buffer = content
                                        continue
                                    
                                    # Try direct text format
                                    text = choice.get("text", "")
                                    if text:
                                        yield text
                                        
                            except json.JSONDecodeError:
                                continue
                            except Exception:
                                continue
                                
        except asyncio.TimeoutError:
            yield "Error: Request timeout"
        except Exception as exc:
            yield f"Error: {str(exc)}"
