from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


class SDKUnavailableError(RuntimeError):
    """Raised when a required SDK dependency is missing."""


@dataclass
class SDKConfig:
    """Configuration for SDK clients."""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3
    headers: Optional[Dict[str, str]] = None
    additional_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SDKMessage:
    """Unified message format for SDK calls."""

    role: str
    content: str
    thinking: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SDKResponse:
    """Unified response format for SDK calls."""

    content: str
    thinking: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseLLMSDK(ABC):
    """Base interface for SDK-backed LLM clients."""

    def __init__(self, config: SDKConfig):
        self.config = config

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the SDK is reachable with current credentials."""
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models via SDK."""
        raise NotImplementedError

    @abstractmethod
    def invoke(self, messages: List[SDKMessage], model: str, **kwargs: Any) -> SDKResponse:
        """Invoke the model and return a response."""
        raise NotImplementedError

    @abstractmethod
    def invoke_stream(self, messages: List[SDKMessage], model: str, **kwargs: Any) -> Iterable[str]:
        """Stream model output chunks."""
        raise NotImplementedError

    @abstractmethod
    def supports_feature(self, feature: str) -> bool:
        """Check if a feature is supported by this SDK."""
        raise NotImplementedError
