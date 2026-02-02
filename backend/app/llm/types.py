from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = False
    prompt_chars: int = 0
    completion_chars: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InvokeResult:
    ok: bool
    output: str
    latency_ms: int
    usage: Usage
    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
    streaming: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "ok": self.ok,
            "output": self.output,
            "latency_ms": self.latency_ms,
            "usage": self.usage.to_dict(),
            "streaming": self.streaming,
        }
        if self.error:
            payload["error"] = self.error
        if self.raw is not None:
            payload["raw"] = self.raw
        return payload


@dataclass
class HealthResult:
    ok: bool
    latency_ms: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {"ok": self.ok, "latency_ms": self.latency_ms}
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass
class ModelInfo:
    id: str
    label: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {"id": self.id}
        if self.label:
            payload["label"] = self.label
        if self.raw is not None:
            payload["raw"] = self.raw
        return payload


@dataclass
class ModelListResult:
    ok: bool
    models: List[ModelInfo]
    supported: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "ok": self.ok,
            "supported": self.supported,
            "models": [m.to_dict() for m in self.models],
        }
        if self.error:
            payload["error"] = self.error
        return payload


def estimate_usage(prompt: str, output: str) -> Usage:
    prompt_chars = len(prompt or "")
    completion_chars = len(output or "")
    prompt_tokens = max(1, prompt_chars // 4) if prompt_chars else 0
    completion_tokens = max(1, completion_chars // 4) if completion_chars else 0
    total_tokens = prompt_tokens + completion_tokens
    return Usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated=True,
        prompt_chars=prompt_chars,
        completion_chars=completion_chars,
    )
