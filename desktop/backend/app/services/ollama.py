import os
import shutil
import subprocess
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from ..config import PROJECT_ROOT
from ..utils import build_utf8_env

def list_ollama_models() -> List[str]:
    if not shutil.which("ollama"):
        raise HTTPException(status_code=500, detail="ollama command not found in PATH.")
    timeout_sec = 0
    try:
        timeout_sec = int(str(os.environ.get("HARBORPILOT_OLLAMA_CLI_TIMEOUT", "15")).strip())
    except Exception:
        timeout_sec = 15
    timeout_val = timeout_sec if timeout_sec and timeout_sec > 0 else None
    try:
        result = subprocess.run(
            ["ollama", "ps"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=build_utf8_env(),
            timeout=timeout_val,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="ollama ps timeout")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ollama ps failed: {exc}")
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "ollama ps failed").strip()
        raise HTTPException(status_code=500, detail=msg)
    lines = result.stdout.splitlines()
    models: List[str] = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        name = line.split()[0].strip()
        if name and name.lower() != "name":
            models.append(name)
    return models

def ollama_stop() -> Dict[str, Any]:
    models = list_ollama_models()
    if not models:
        return {"ok": True, "stopped": [], "failed": [], "models": []}
    timeout_sec = 0
    try:
        timeout_sec = int(str(os.environ.get("HARBORPILOT_OLLAMA_CLI_TIMEOUT", "15")).strip())
    except Exception:
        timeout_sec = 15
    timeout_val = timeout_sec if timeout_sec and timeout_sec > 0 else None
    stopped: List[str] = []
    failed: List[Dict[str, str]] = []
    for name in models:
        try:
            result = subprocess.run(
                ["ollama", "stop", name],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=build_utf8_env(),
                timeout=timeout_val,
            )
        except subprocess.TimeoutExpired:
            failed.append({"model": name, "error": "timeout"})
            continue
        except Exception as exc:
            failed.append({"model": name, "error": str(exc)})
            continue
        if result.returncode == 0:
            stopped.append(name)
        else:
            msg = (result.stderr or result.stdout or "ollama stop failed").strip()
            failed.append({"model": name, "error": msg})
    return {"ok": True, "stopped": stopped, "failed": failed, "models": models}
