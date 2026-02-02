import time
import uuid
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, asdict

# Assuming io_utils is in the same package
try:
    from .io_utils import emit_event
except ImportError:
    from io_utils import emit_event

@dataclass
class UsageContext:
    run_id: str
    task_id: str
    phase: str
    mode: str
    actor: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated: bool = False
    prompt_chars: int = 0
    completion_chars: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def track_usage(
    events_path: str,
    context: UsageContext,
    model: str,
    provider: str,
    usage: TokenUsage,
    duration_ms: int,
    ok: bool = True,
    error: Optional[str] = None
) -> None:
    """
    Emit an 'llm_invoke' event to the events log with usage stats.
    """
    if not events_path:
        return

    observation = {
        "ok": ok,
        "duration_ms": duration_ms,
        "model": model,
        "provider": provider,
        "usage": usage.to_dict()
    }
    
    if error:
        observation["error"] = error

    emit_event(
        events_path,
        kind="observation",
        actor=context.actor,
        name="llm_invoke",
        refs=context.to_dict(),
        summary=f"LLM Invoke ({model}) - {usage.total_tokens} tokens",
        output=observation
    )
