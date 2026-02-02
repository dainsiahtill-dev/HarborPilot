from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from ...utils import build_utf8_env
from ..types import HealthResult, InvokeResult, ModelInfo, ModelListResult, Usage, estimate_usage


def _normalize_command(command: str) -> List[str]:
    ext = os.path.splitext(command)[1].lower()
    if ext == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", command]
    if ext in (".cmd", ".bat"):
        return ["cmd.exe", "/c", command]
    return [command]


def _resolve_command(command: str) -> Optional[str]:
    if not command:
        return None
    if os.path.isabs(command) or os.path.exists(command):
        return command
    return shutil.which(command)


def _run_cli(
    command: str,
    args: List[str],
    cwd: str,
    env: Optional[Dict[str, str]],
    timeout: int,
    input_text: Optional[str],
) -> Tuple[int, str, str, int]:
    cmd = _normalize_command(command) + args
    start = time.time()
    result = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd or None,
        env=build_utf8_env(env),
        timeout=timeout if timeout > 0 else None,
    )
    latency_ms = int((time.time() - start) * 1000)
    return result.returncode, result.stdout or "", result.stderr or "", latency_ms


def health(config: Dict[str, Any]) -> HealthResult:
    command = str(config.get("command") or "").strip()
    resolved = _resolve_command(command)
    if not resolved:
        return HealthResult(ok=False, latency_ms=0, error="cli command not found")
    health_args = config.get("health_args") or []
    if not health_args:
        return HealthResult(ok=True, latency_ms=0)
    try:
        code, stdout, stderr, latency_ms = _run_cli(
            resolved,
            list(map(str, health_args)),
            str(config.get("working_dir") or ""),
            config.get("env") or {},
            int(config.get("timeout") or 15),
            None,
        )
        if code != 0:
            message = (stderr or stdout or "health check failed").strip()
            return HealthResult(ok=False, latency_ms=latency_ms, error=message)
        return HealthResult(ok=True, latency_ms=latency_ms)
    except Exception as exc:
        return HealthResult(ok=False, latency_ms=0, error=str(exc))


def list_models(config: Dict[str, Any]) -> ModelListResult:
    command = str(config.get("command") or "").strip()
    resolved = _resolve_command(command)
    if not resolved:
        return ModelListResult(ok=False, supported=False, models=[], error="cli command not found")
    list_args = config.get("list_args") or config.get("models_args") or []
    if not list_args:
        return ModelListResult(ok=True, supported=False, models=[], error="model listing not supported")
    try:
        code, stdout, stderr, _ = _run_cli(
            resolved,
            list(map(str, list_args)),
            str(config.get("working_dir") or ""),
            config.get("env") or {},
            int(config.get("timeout") or 15),
            None,
        )
        if code != 0:
            message = (stderr or stdout or "model listing failed").strip()
            return ModelListResult(ok=False, supported=True, models=[], error=message)
        models = _parse_model_output(stdout)
        return ModelListResult(ok=True, supported=True, models=models)
    except Exception as exc:
        return ModelListResult(ok=False, supported=True, models=[], error=str(exc))


def invoke(prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
    command = str(config.get("command") or "").strip()
    resolved = _resolve_command(command)
    if not resolved:
        usage = estimate_usage(prompt, "")
        return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error="cli command not found")
    args = list(map(str, config.get("args") or []))
    output_path = _resolve_output_path(config)
    if output_path:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        except Exception:
            pass
    rendered_args, send_prompt = _render_args(args, prompt, model, output_path)
    timeout = int(config.get("timeout") or 60)
    try:
        code, stdout, stderr, latency_ms = _run_cli(
            resolved,
            rendered_args,
            str(config.get("working_dir") or ""),
            config.get("env") or {},
            timeout,
            prompt if send_prompt else None,
        )
        output = stdout.strip() if stdout else ""
        if not output and output_path and os.path.isfile(output_path):
            try:
                with open(output_path, "r", encoding="utf-8", errors="replace") as handle:
                    output = handle.read().strip()
            except Exception:
                pass
        usage = estimate_usage(prompt, output)
        if code != 0:
            message = (stderr or stdout or "cli invoke failed").strip()
            return InvokeResult(ok=False, output=output, latency_ms=latency_ms, usage=usage, error=message)
        return InvokeResult(ok=True, output=output, latency_ms=latency_ms, usage=usage)
    except subprocess.TimeoutExpired:
        usage = estimate_usage(prompt, "")
        return InvokeResult(ok=False, output="", latency_ms=timeout * 1000, usage=usage, error="timeout")
    except Exception as exc:
        usage = estimate_usage(prompt, "")
        return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error=str(exc))


def _render_args(args: List[str], prompt: str, model: str, output_path: Optional[str]) -> Tuple[List[str], bool]:
    rendered: List[str] = []
    send_prompt = True
    for item in args:
        value = item.replace("{model}", model)
        if "{prompt}" in value:
            value = value.replace("{prompt}", prompt)
            send_prompt = False
        if output_path and "{output}" in value:
            value = value.replace("{output}", output_path)
        rendered.append(value)
    return rendered, send_prompt


def _parse_model_output(output: str) -> List[ModelInfo]:
    text = (output or "").strip()
    if not text:
        return []
    models: List[ModelInfo] = []
    # Try JSON first.
    if text.startswith("{") or text.startswith("["):
        try:
            import json

            payload = json.loads(text)
            if isinstance(payload, dict):
                payload = payload.get("models") or payload.get("data") or payload.get("items") or []
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        model_id = str(item.get("id") or item.get("name") or "").strip()
                        if model_id:
                            models.append(ModelInfo(id=model_id, raw=item))
                    elif isinstance(item, str):
                        models.append(ModelInfo(id=item.strip()))
                return models
        except Exception:
            models = []
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        # Use the first token as model id.
        model_id = candidate.split()[0].strip()
        if model_id:
            models.append(ModelInfo(id=model_id, label=candidate))
    return models


def _resolve_output_path(config: Dict[str, Any]) -> Optional[str]:
    raw = str(config.get("output_path") or "").strip()
    if not raw:
        return None
    if os.path.isabs(raw):
        return raw
    base = str(config.get("working_dir") or "").strip()
    if base:
        return os.path.join(base, raw)
    return os.path.abspath(raw)
