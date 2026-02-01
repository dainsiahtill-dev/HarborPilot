import os
import re
import subprocess
import sys
import requests
import json


ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_OSC_RE = re.compile(r"\x1b\][^\x1b\x07]*(?:\x07|\x1b\\)")
from typing import List, Dict, Any, Optional

ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
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


def _build_utf8_env() -> dict:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    return env


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


def invoke_ollama(prompt: str, model: str, workspace: str, show_output: bool, timeout: int) -> str:
    cmd = ["ollama", "run", model]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            capture_output=True,
            timeout=timeout if timeout > 0 else None,
            env=_build_utf8_env(),
        )
    except subprocess.TimeoutExpired:
        return ""
    if show_output:
        stdout_text = clean_terminal_output(result.stdout or "")
        stderr_text = clean_terminal_output(result.stderr or "")
        if stdout_text:
            sys.stdout.write(stdout_text)
        if stderr_text and not is_spinner_only(stderr_text):
            sys.stdout.write(stderr_text)
    return result.stdout or ""


def get_embedding(text: str, model: str, timeout: int = 30) -> List[float]:
    """
    Get vector embedding for text using Ollama API.
    """
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    url = f"{host}/api/embeddings"
    
    # Handle mbedding models specifically if needed, but usually same model works if it supports it
    # Often 'nomic-embed-text' or similar is used. 
    # If the main model is qwen, it might not support embeddings well or be slow.
    # We'll use the passed model for now.
    
    payload = {
        "model": model,
        "prompt": text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", [])
    except Exception as e:
        # Fallback or log?
        # For now, return empty list which implies no vector support
        return []
