from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from .base_provider import (
    BaseProvider, ProviderInfo, ModelInfo, HealthResult, ModelListResult, 
    InvokeResult, ValidationResult, ThinkingInfo, WorkingDirConfig
)
from ..types import estimate_usage
from ...utils import build_utf8_env


def _normalize_command(command: str) -> List[str]:
    """Normalize command for different platforms"""
    ext = os.path.splitext(command)[1].lower()
    if ext == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", command]
    if ext in (".cmd", ".bat"):
        return ["cmd.exe", "/c", command]
    return [command]


def _resolve_command(command: str) -> Optional[str]:
    """Resolve command path"""
    if not command:
        return None
    if os.path.isabs(command) or os.path.exists(command):
        return command
    return shutil.which(command)


def _build_codex_exec_args(model: str, config: Dict[str, Any]) -> List[str]:
    """Build Codex CLI exec arguments based on official documentation
    
    Reference: https://docs.openai.com/codex/cli/non-interactive
    
    Args:
        model: Model name to use
        config: Provider configuration
        
    Returns:
        List of command line arguments for codex exec
    """
    opts = config.get('codex_exec') or {}
    if not isinstance(opts, dict):
        # Default args for Codex CLI with JSON mode (read-only for safety)
        return [
            'exec',
            '--skip-git-repo-check',
            '--model', model,
            '--sandbox', 'read-only',  # Safer default
            '--json'
        ]
    
    args: List[str] = ['exec']
    
    # Working directory (--cd, -C)
    cd = str(opts.get('cd') or '').strip()
    if cd:
        args += ['--cd', cd]
    
    # Color control (--color) - disable for JSON mode
    color = str(opts.get('color') or '').strip()
    if color and color.lower() in ('always', 'never', 'auto'):
        args += ['--color', color.lower()]
    else:
        args += ['--color', 'never']  # Default for JSON mode
    
    # Git repo check (--skip-git-repo-check)
    if bool(opts.get('skip_git_repo_check', True)):
        args.append('--skip-git-repo-check')
    
    # Sandbox strategy (--sandbox, -s)
    # Default to read-only for safety unless explicitly specified
    sandbox = str(opts.get('sandbox') or '').strip()
    if sandbox:
        valid_sandboxes = ['read-only', 'workspace-write', 'danger-full-access']
        if sandbox.lower() in valid_sandboxes:
            args += ['--sandbox', sandbox.lower()]
        else:
            args += ['--sandbox', 'read-only']  # Safe default
    else:
        args += ['--sandbox', 'read-only']  # Safe default
    
    # Model selection (--model, -m)
    if model:
        args += ['--model', model]
    
    # JSON mode (--json, --experimental-json)
    json_mode = opts.get('json')
    if json_mode is not False:  # Default to True unless explicitly disabled
        if json_mode == 'experimental':
            args.append('--experimental-json')
        else:
            args.append('--json')
    
    # Approval control was removed from recent codex exec CLI; skip to avoid errors.
    
    # OSS provider (--oss)
    if bool(opts.get('oss')):
        args.append('--oss')
    
    # Additional directories (--add-dir)
    add_dirs = opts.get('add_dirs') or []
    if isinstance(add_dirs, (list, tuple)):
        for entry in add_dirs:
            path_value = str(entry or '').strip()
            if path_value:
                args += ['--add-dir', path_value]
    
    # Images (--image, -i)
    images = opts.get('images') or []
    if isinstance(images, (list, tuple)):
        for entry in images:
            image_value = str(entry or '').strip()
            if image_value:
                args += ['--image', image_value]
    
    # Output schema (--output-schema)
    output_schema = str(opts.get('output_schema') or '').strip()
    if output_schema:
        args += ['--output-schema', output_schema]
    
    # Output last message (--output-last-message, -o)
    output_last = str(opts.get('output_last_message') or opts.get('output') or '').strip()
    if output_last:
        args += ['--output-last-message', output_last]
    
    # Profile selection (--profile, -p)
    profile = str(opts.get('profile') or '').strip()
    if profile:
        args += ['--profile', profile]
    
    # Config overrides (--config, -c)
    config_overrides = opts.get('config') or opts.get('config_overrides') or []
    if isinstance(config_overrides, (list, tuple)):
        for entry in config_overrides:
            kv = str(entry or '').strip()
            if kv and '=' in kv:
                key, value = kv.split('=', 1)
                args += ['--config', f'{key.strip()}={value.strip()}']
    
    # Special automation flags (mutually exclusive in most cases)
    
    # YOLO mode (--yolo) - most permissive
    if bool(opts.get('yolo')):
        args.append('--yolo')
        # YOLO implies no need for other safety flags
    else:
        # Full auto mode (--full-auto) - automation preset
        if bool(opts.get('full_auto')):
            args.append('--full-auto')
    
    # Prompt placeholder
    args.append('{prompt}')
    
    return args


_REASONING_EFFORT_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "xhigh": 4,
}


def _pick_reasoning_effort_fallback(error_text: str) -> Optional[str]:
    """Pick a safe reasoning.effort fallback based on CLI error details."""
    if not error_text:
        return None
    if "reasoning.effort" not in error_text and "reasoning effort" not in error_text:
        return None

    supported: List[str] = []
    match = re.search(r"Supported values are:(.*)$", error_text, re.IGNORECASE | re.DOTALL)
    if match:
        supported = [
            value.lower()
            for value in re.findall(r"'([a-zA-Z0-9_-]+)'", match.group(1))
            if value.lower() in _REASONING_EFFORT_RANK
        ]
    if supported:
        return max(supported, key=lambda effort: _REASONING_EFFORT_RANK[effort])

    mentions = [
        value.lower()
        for value in re.findall(r"'([a-zA-Z0-9_-]+)'", error_text)
        if value.lower() in _REASONING_EFFORT_RANK
    ]
    if "xhigh" in mentions:
        return "high"
    if "high" in mentions:
        return "medium"
    if "medium" in mentions:
        return "low"
    return None


def _set_codex_config_override(args: List[str], key: str, value: str) -> List[str]:
    """Insert or replace a --config key=value override for codex exec."""
    updated: List[str] = []
    replaced = False
    idx = 0
    while idx < len(args):
        item = args[idx]
        if item == "--config" and idx + 1 < len(args):
            kv = str(args[idx + 1])
            if kv.split("=", 1)[0].strip() == key:
                updated.extend(["--config", f"{key}={value}"])
                idx += 2
                replaced = True
                continue
        updated.append(item)
        idx += 1

    if not replaced:
        inserted = False
        for pos, item in enumerate(updated):
            if item == "{prompt}":
                updated = updated[:pos] + ["--config", f"{key}={value}"] + updated[pos:]
                inserted = True
                break
        if not inserted:
            updated.extend(["--config", f"{key}={value}"])

    return updated


def _extract_cli_error_message(output: str) -> Optional[str]:
    """Extract error text from parsed Codex CLI JSON output."""
    if not output:
        return None
    first_line = output.strip().splitlines()[0].strip()
    lowered = first_line.lower()
    if lowered.startswith("error:") or lowered.startswith("turn failed:"):
        return first_line
    return None


def _run_cli(
    command: str,
    args: List[str],
    cwd: str,
    env: Optional[Dict[str, str]],
    timeout: int,
    input_text: Optional[str],
) -> Tuple[int, str, str, int]:
    """Execute CLI command"""
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


def _parse_codex_json_output(raw_output: str) -> str:
    """Parse JSON Lines output from Codex CLI exec --json mode
    
    Based on official documentation: https://docs.openai.com/codex/cli/non-interactive
    
    Event types include:
    - thread.started, turn.started, turn.completed, turn.failed
    - item.* (agent_message, reasoning, command_execution, file_change, mcp_tool_call, web_search, plan_update)
    - error
    
    Args:
        raw_output: Raw stdout from codex exec --json command
        
    Returns:
        Parsed output with thinking and agent messages extracted
    """
    lines = (raw_output or '').splitlines()
    reasoning_parts: List[str] = []
    message_parts: List[str] = []
    usage_data: Optional[Dict[str, Any]] = None
    command_executions: List[str] = []
    file_changes: List[str] = []
    errors: List[str] = []
    
    for line in lines:
        trimmed = line.strip()
        if not trimmed or not trimmed.startswith('{'):
            continue
            
        try:
            payload = json.loads(trimmed)
        except Exception:
            continue
            
        if not isinstance(payload, dict):
            continue
            
        event_type = payload.get('type')
        
        # Thread/Turn lifecycle events
        if event_type in ('thread.started', 'turn.started'):
            continue
        elif event_type == 'turn.completed':
            usage_data = payload.get('usage')
            continue
        elif event_type == 'turn.failed':
            error_info = payload.get('error', 'Turn failed')
            if isinstance(error_info, str):
                errors.append(f"Turn failed: {error_info}")
            continue
        elif event_type == 'error':
            error_text = payload.get('error', '')
            if isinstance(error_text, str):
                errors.append(f"Error: {error_text}")
            continue
            
        # Item events (the actual content)
        elif event_type == 'item.started':
            item = payload.get('item')
            if isinstance(item, dict):
                item_type = str(item.get('type') or '')
                item_id = str(item.get('id') or '')
                # Could track item start if needed
            continue
            
        elif event_type == 'item.completed':
            item = payload.get('item')
            if not isinstance(item, dict):
                continue
                
            item_type = str(item.get('type') or '')
            item_id = str(item.get('id') or '')
            text = item.get('text')
            status = item.get('status')
            
            # Extract content based on item type
            if item_type in ('reasoning', 'thinking', 'analysis'):
                if isinstance(text, str) and text.strip():
                    reasoning_parts.append(text.strip())
                    
            elif item_type in ('agent_message', 'message', 'response'):
                if isinstance(text, str) and text.strip():
                    message_parts.append(text.strip())
                    
            elif item_type == 'command_execution':
                if isinstance(text, str) and text.strip():
                    command_executions.append(f"Command: {text.strip()}")
                elif isinstance(item.get('command'), str):
                    command_executions.append(f"Command: {item['command'].strip()}")
                    
            elif item_type == 'file_change':
                if isinstance(text, str) and text.strip():
                    file_changes.append(f"File change: {text.strip()}")
                    
            elif item_type in ('mcp_tool_call', 'web_search', 'plan_update'):
                if isinstance(text, str) and text.strip():
                    reasoning_parts.append(f"[{item_type.replace('_', ' ').title()}]: {text.strip()}")
    
    # Build the final output
    output_chunks: List[str] = []
    
    # Add errors first if any
    if errors:
        output_chunks.append("\n".join(errors))
    
    # Add reasoning/thinking
    if reasoning_parts:
        reasoning_text = '\n\n'.join(reasoning_parts).strip()
        output_chunks.append(f"<thinking>{reasoning_text}</thinking>")
    
    # Add command executions and file changes as context
    if command_executions:
        output_chunks.append("\n".join(command_executions))
    
    if file_changes:
        output_chunks.append("\n".join(file_changes))
    
    # Add the main agent message
    if message_parts:
        message_text = '\n\n'.join(message_parts).strip()
        output_chunks.append(message_text)
    
    # If we couldn't parse any structured content, fall back to raw output
    if not output_chunks:
        return raw_output.strip()
    
    final_output = '\n\n'.join(output_chunks).strip()
    
    # Add usage information as metadata if available
    if usage_data and isinstance(usage_data, dict):
        # This could be used for token tracking
        input_tokens = usage_data.get('input_tokens', 0)
        output_tokens = usage_data.get('output_tokens', 0)
        cached_tokens = usage_data.get('cached_input_tokens', 0)
        
        # Add usage as a comment for debugging
        if input_tokens or output_tokens:
            usage_comment = f"<!-- Usage: {input_tokens} input, {output_tokens} output"
            if cached_tokens:
                usage_comment += f", {cached_tokens} cached"
            usage_comment += " -->"
            final_output += f"\n\n{usage_comment}"
    
    return final_output


def _resolve_output_path(config: Dict[str, Any]) -> Optional[str]:
    """Resolve output file path"""
    raw = str(config.get("output_path") or "").strip()
    if not raw:
        codex_exec = config.get("codex_exec")
        if isinstance(codex_exec, dict):
            raw = str(codex_exec.get("output_last_message") or "").strip()
    if not raw:
        return None
    if os.path.isabs(raw):
        return raw
    base = str(config.get("working_dir") or "").strip()
    if base:
        return os.path.join(base, raw)
    return os.path.abspath(raw)


def _parse_model_output(output: str) -> List[ModelInfo]:
    """Parse model listing output"""
    text = (output or "").strip()
    if not text:
        return []
    models: List[ModelInfo] = []
    
    # Try JSON first
    if text.startswith("{") or text.startswith("["):
        try:
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
    
    # Parse text output (fallback)
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        # Use the first token as model ID
        model_id = candidate.split()[0].strip()
        if model_id:
            models.append(ModelInfo(id=model_id, label=candidate))
    
    return models


class CodexCLIProvider(BaseProvider):
    """Enhanced provider for Codex CLI with JSON mode support"""
    
    def get_tui_instructions(self) -> Dict[str, str]:
        """Get TUI mode instructions for Codex CLI
        
        Returns helpful instructions for users who need to interact with Codex CLI TUI
        """
        return {
            "model_discovery": "Run 'codex' then type '/models' to see all available models",
            "status_check": "Run 'codex' then type '/status' to see current session configuration",
            "permissions": "Run 'codex' then type '/permissions' to adjust approval settings",
            "help": "Run 'codex' then type '/help' to see all available commands",
            "exit": "Run 'codex' then type '/quit' or '/exit' to leave the TUI"
        }
    
    def get_session_status_hint(self) -> str:
        """Get hint about checking session status in TUI mode"""
        return "For detailed session status, run 'codex' and type '/status' in the TUI"
    
    def __init__(self):
        pass
    
    def _build_codex_exec_args(self, model: str, config: Dict[str, Any]) -> List[str]:
        """Build Codex CLI exec arguments based on actual CLI usage"""
        return _build_codex_exec_args(model, config)
    
    def _parse_codex_json_output(self, raw_output: str) -> str:
        """Parse JSON output from Codex CLI"""
        return _parse_codex_json_output(raw_output)

    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        return ProviderInfo(
            name="Codex CLI Provider",
            type="codex_cli",
            description="Codex CLI with JSON mode and thinking extraction",
            version="2.0.0",
            author="HarborPilot Team",
            documentation_url="https://docs.codex.ai/cli",
            supported_features=[
                "thinking_extraction",
                "working_directory",
                "health_check",
                "json_mode",
                "real_time_streaming",
                "autonomous_file_operations",
                "sandbox_control"
            ],
            cost_class="FIXED",
            provider_category="AGENT",
            autonomous_file_access=True,
            requires_file_interfaces=False,
            model_listing_method="TUI"
        )
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "type": "codex_cli",
            "name": "Codex CLI",
            "command": "codex",
            "args": [],
            "cli_mode": "headless",
            "codex_exec": {
                "cd": "",
                "color": "never",
                "ask_for_approval": "on-request",
                "sandbox": "read-only",  # Safer default
                "skip_git_repo_check": True,
                "json": True,
                "yolo": False,
                "full_auto": False,
                "oss": False,
                "output_schema": "",
                "output_last_message": "",
                "profile": "",
                "add_dirs": [],
                "images": [],
                "config": []
            },
            "manual_models": [],  # For TUI mode model entry
            "list_args": [],  # Not used for TUI mode
            "health_args": ["version"],
            "timeout": 60,
            "thinking_extraction": {
                "enabled": True,
                "patterns": [
                    r"<thinking>(.*?)</thinking>",
                    r"```thinking(.*?)```",
                    r"Reasoning:(.*?)(?:\n\n|\n[A-Z])"
                ],
                "confidence_threshold": 0.7
            }
        }
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        normalized = config.copy()
        
        # Validate command
        command = str(config.get("command", "codex")).strip()
        if not command:
            command = "codex"
        
        resolved = _resolve_command(command)
        if not resolved:
            errors.append("Codex CLI command not found in PATH")
            warnings.append("Please install Codex CLI: https://docs.codex.ai/cli")
        else:
            normalized["command"] = resolved
        
        # Validate args
        args = config.get("args", [])
        if not isinstance(args, list):
            errors.append("Args must be a list")
            normalized["args"] = []
        
        # Validate timeout
        timeout = config.get("timeout", 60)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            warnings.append("Invalid timeout, using default 60")
            normalized["timeout"] = 60

        # Validate CLI mode
        cli_mode = str(config.get("cli_mode") or "").strip().lower()
        if cli_mode not in ("headless", "tui"):
            normalized["cli_mode"] = "headless"
            warnings.append("Invalid cli_mode, using headless")
        
        # Validate codex_exec config
        codex_exec = config.get("codex_exec", {})
        if not isinstance(codex_exec, dict):
            warnings.append("codex_exec should be a dictionary")
            normalized["codex_exec"] = cls.get_default_config()["codex_exec"]
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_config=normalized
        )

    def __init__(self):
        pass
    
    def health(self, config: Dict[str, Any]) -> HealthResult:
        command = str(config.get("command", "codex")).strip()
        resolved = _resolve_command(command)
        if not resolved:
            return HealthResult(ok=False, latency_ms=0, error="Codex CLI command not found")
        
        health_args = config.get("health_args", ["version"])
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
            
            # Parse version info for extended status
            version_info = stdout.strip() if stdout else ""
            return HealthResult(
                ok=True, 
                latency_ms=latency_ms,
                details={
                    "version": version_info,
                    "command": resolved,
                    "working_dir": str(config.get("working_dir") or ""),
                    "model_listing_method": "TUI",
                    "provider_category": "AGENT"
                }
            )
        except Exception as exc:
            return HealthResult(ok=False, latency_ms=0, error=str(exc))
    
    def list_models(self, config: Dict[str, Any]) -> ModelListResult:
        """List available models for Codex CLI
        
        Note: Codex CLI requires TUI interaction to list models.
        This method provides a manual entry interface for users.
        """
        command = str(config.get("command", "codex")).strip()
        resolved = _resolve_command(command)
        if not resolved:
            return ModelListResult(ok=False, supported=False, models=[], error="Codex CLI command not found")
        
        # Check if user has manually entered models
        manual_models = config.get("manual_models", [])
        if isinstance(manual_models, list) and manual_models:
            models = []
            for model_entry in manual_models:
                if isinstance(model_entry, str) and model_entry.strip():
                    models.append(ModelInfo(id=model_entry.strip(), label=model_entry.strip()))
            return ModelListResult(
                ok=True, 
                supported=True, 
                models=models,
                error="Models manually entered (TUI mode)"
            )
        
        # Return instructions for TUI model discovery
        provider = CodexCLIProvider()
        tui_instructions = provider.get_tui_instructions()
        
        return ModelListResult(
            ok=True,
            supported=True,
            models=[
                ModelInfo(id="gpt-4-codex", label="GPT-4 Codex (Common)"),
                ModelInfo(id="gpt-5.2-codex", label="GPT-5.2 Codex (Latest)"),
                ModelInfo(id="gpt-3.5-turbo", label="GPT-3.5 Turbo (Legacy)"),
            ],
            error=f"TUI_MODE: {tui_instructions['model_discovery']}. Enter models manually above or see TUI instructions."
        )
    
    def invoke(self, prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
        command = str(config.get("command", "codex")).strip()
        resolved = _resolve_command(command)
        if not resolved:
            usage = estimate_usage(prompt, "")
            return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error="Codex CLI command not found")
        
        # Build args using enhanced Codex CLI logic
        args = _build_codex_exec_args(model, config)
        
        output_path = _resolve_output_path(config)
        if output_path:
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
            except Exception:
                pass
        
        rendered_args, send_prompt = self._render_args(args, prompt, model, output_path)
        timeout = int(config.get("timeout") or 60)

        def run_once(selected_args: List[str], use_prompt: bool) -> Tuple[int, str, str, str, int]:
            code, stdout, stderr, latency_ms = _run_cli(
                resolved,
                selected_args,
                str(config.get("working_dir") or ""),
                config.get("env") or {},
                timeout,
                prompt if use_prompt else None,
            )
            output = stdout.strip() if stdout else ""

            # Parse JSON output for structured content
            if output and '--json' in selected_args:
                output = _parse_codex_json_output(output)

            # Check output file if specified
            if not output and output_path and os.path.isfile(output_path):
                try:
                    with open(output_path, "r", encoding="utf-8", errors="replace") as handle:
                        output = handle.read().strip()
                except Exception:
                    pass

            return code, output, stdout or "", stderr or "", latency_ms

        try:
            code, output, stdout_raw, stderr_raw, latency_ms = run_once(rendered_args, send_prompt)
            cli_error = _extract_cli_error_message(output)
            if code != 0 or cli_error:
                message = (stderr_raw or cli_error or stdout_raw or "Codex CLI invoke failed").strip()
                fallback_source = stderr_raw or stdout_raw or output or message
                fallback_effort = _pick_reasoning_effort_fallback(fallback_source)
                if fallback_effort:
                    retry_args = _set_codex_config_override(
                        args,
                        "model_reasoning_effort",
                        f'"{fallback_effort}"'
                    )
                    rendered_retry_args, send_prompt_retry = self._render_args(retry_args, prompt, model, output_path)
                    code, output, stdout_raw, stderr_raw, latency_ms = run_once(
                        rendered_retry_args, send_prompt_retry
                    )
                    cli_error = _extract_cli_error_message(output)
                    if code == 0 and not cli_error:
                        usage = estimate_usage(prompt, output)
                        return InvokeResult(ok=True, output=output, latency_ms=latency_ms, usage=usage)
                    message = (stderr_raw or cli_error or stdout_raw or "Codex CLI invoke failed").strip()
                    if message:
                        message = f"{message}\n(auto-fallback reasoning.effort={fallback_effort} failed)"

                usage = estimate_usage(prompt, output)
                return InvokeResult(ok=False, output=output, latency_ms=latency_ms, usage=usage, error=message)

            usage = estimate_usage(prompt, output)
            return InvokeResult(ok=True, output=output, latency_ms=latency_ms, usage=usage)
        except subprocess.TimeoutExpired:
            usage = estimate_usage(prompt, "")
            return InvokeResult(ok=False, output="", latency_ms=timeout * 1000, usage=usage, error="timeout")
        except Exception as exc:
            usage = estimate_usage(prompt, "")
            return InvokeResult(ok=False, output="", latency_ms=0, usage=usage, error=str(exc))
    
    @classmethod
    def extract_thinking_support(cls, response: Dict[str, Any]) -> ThinkingInfo:
        """Extract thinking information from Codex CLI response"""
        if not isinstance(response, dict) or "output" not in response:
            return ThinkingInfo(
                supports_thinking=False,
                confidence=0.0,
                format=None,
                thinking_text=None,
                extraction_method="codex_default"
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
        
        # Check for thinking tags in the output
        patterns = thinking_config.get("patterns", [
            r"<thinking>(.*?)</thinking>",
            r"```thinking(.*?)```",
            r"Reasoning:(.*?)(?:\n\n|\n[A-Z])"
        ])
        
        confidence_threshold = thinking_config.get("confidence_threshold", 0.7)
        
        for pattern in patterns:
            try:
                match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
                if match:
                    thinking_text = match.group(1).strip()
                    confidence = cls._calculate_thinking_confidence(thinking_text)
                    format_type = "xml" if "<thinking>" in pattern else "markdown"
                    
                    if confidence >= confidence_threshold:
                        return ThinkingInfo(
                            supports_thinking=True,
                            confidence=confidence,
                            format=format_type,
                            thinking_text=thinking_text,
                            extraction_method="codex_pattern"
                        )
                    
                    return ThinkingInfo(
                        supports_thinking=True,
                        confidence=confidence,
                        format=format_type,
                        thinking_text=thinking_text,
                        extraction_method="codex_pattern_low_confidence"
                    )
            except re.error:
                continue
        
        # Check for Codex-specific reasoning indicators
        reasoning_indicators = [
            "reasoning", "analysis", "thought", "considering", "because", "therefore",
            "first", "next", "finally", "step", "approach"
        ]
        
        output_lower = output.lower()
        if any(indicator in output_lower for indicator in reasoning_indicators):
            return ThinkingInfo(
                supports_thinking=True,
                confidence=0.4,
                format="text",
                thinking_text=None,
                extraction_method="codex_keyword"
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
        codex_exec = config.get("codex_exec", {})
        target_dir = codex_exec.get("cd") or config.get("working_dir")
        
        return WorkingDirConfig(
            target_directory=target_dir,
            auto_create=True,
            cleanup_after=False,
            environment_vars=config.get("env", {})
        )
    
    @staticmethod
    def _calculate_thinking_confidence(thinking_text: str) -> float:
        """Calculate confidence score for thinking extraction"""
        if not thinking_text:
            return 0.0
        
        # Factors that increase confidence
        length_score = min(len(thinking_text) / 300, 1.0)  # Codex tends to be concise
        structure_score = 0.3 if any(word in thinking_text.lower() for word in ["because", "therefore", "however", "although"]) else 0.0
        detail_score = min(thinking_text.count(".") / 10, 0.4)  # More sentences = more detail
        
        return min(length_score + structure_score + detail_score, 1.0)
    
    @staticmethod
    def _render_args(args: List[str], prompt: str, model: str, output_path: Optional[str]) -> Tuple[List[str], bool]:
        """Render arguments with placeholder replacement"""
        rendered: List[str] = []
        send_prompt = True
        skip_next = False
        
        for idx, item in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            
            if item == "--model" and idx + 1 < len(args) and "{model}" in args[idx + 1] and not model:
                skip_next = True
                continue
            
            if output_path is None and "{output}" in item:
                continue
            
            value = item.replace("{model}", model)
            if "{prompt}" in value:
                value = value.replace("{prompt}", prompt)
                send_prompt = False
            
            if output_path and "{output}" in value:
                value = value.replace("{output}", output_path)
            
            if value == "":
                continue
            rendered.append(value)
        
        return rendered, send_prompt
