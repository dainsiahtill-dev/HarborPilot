from __future__ import annotations

import os
import re
import sys
import time
from typing import List, Optional

import requests


ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_OSC_RE = re.compile(r"\x1b\][^\x1b\x07]*(?:\x07|\x1b\\)")
ANSI_OTHER_RE = re.compile(r"\x1b[@-_][0-?]*[ -/]*[@-~]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPINNER_ONLY_RE = re.compile(r"^[\s\u2800-\u28ff]+$")


def _enforce_utf8() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("LANG", "en_US.UTF-8")
    os.environ.setdefault("LC_ALL", "en_US.UTF-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


_enforce_utf8()


def clean_terminal_output(text: str) -> str:
    if not text:
        return text
    cleaned = text.replace("\r", "\n")
    cleaned = ANSI_OSC_RE.sub("", cleaned)
    cleaned = ANSI_CSI_RE.sub("", cleaned)
    cleaned = ANSI_OTHER_RE.sub("", cleaned)
    cleaned = CONTROL_RE.sub("", cleaned)
    return cleaned


def is_spinner_only(text: str) -> bool:
    if not text:
        return True
    return SPINNER_ONLY_RE.match(text.strip()) is not None


try:
    from .usage import UsageContext, TokenUsage, track_usage
except ImportError:
    from usage import UsageContext, TokenUsage, track_usage


def invoke_ollama(
    prompt: str,
    model: str,
    workspace: str,
    show_output: bool,
    timeout: int,
    usage_ctx: Optional[UsageContext] = None,
    events_path: str = "",
) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    url = f"{host}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": -1
        },
    }

    start_time = time.time()
    try:
        if show_output:
            # Streaming output is not enabled here; keep non-streaming for consistent usage tracking.
            pass

        response = requests.post(url, json=payload, timeout=timeout if timeout > 0 else None)
        response.raise_for_status()
        data = response.json()

        content = data.get("response", "")
        duration_ms = int((time.time() - start_time) * 1000)

        if usage_ctx and events_path:
            p_tokens = data.get("prompt_eval_count", 0)
            c_tokens = data.get("eval_count", 0)
            usage = TokenUsage(
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=p_tokens + c_tokens,
                estimated=False,
                prompt_chars=len(prompt),
                completion_chars=len(content),
            )
            track_usage(events_path, usage_ctx, model, "ollama", usage, duration_ms, ok=True)

        if show_output:
            print(content)

        return content
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        if usage_ctx and events_path:
            usage = TokenUsage(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                estimated=True,
                prompt_chars=len(prompt),
                completion_chars=0,
            )
            track_usage(events_path, usage_ctx, model, "ollama", usage, duration_ms, ok=False, error=str(exc))
        return ""


def get_embedding(text: str, model: str, timeout: int = 30) -> List[float]:
    """
    Get vector embedding for text using Ollama API.
    """
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    url = f"{host}/api/embeddings"

    payload = {
        "model": model,
        "prompt": text,
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", [])
    except Exception:
        return []
