import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

ANSI_RESET = "\x1b[0m"
ANSI_COLORS = {
    "INFO": "\x1b[36m",
    "TURN": "\x1b[34m",
    "COMMAND": "\x1b[33m",
    "FILE": "\x1b[32m",
    "TOOL": "\x1b[35m",
    "THINKING": "\x1b[90m",
    "ERROR": "\x1b[31m",
    "AGENT": "\x1b[36m",
}
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
ANSI_ENABLED = False
RATE_LIMIT_SECONDS_RE = re.compile(r"resets_in_seconds\\\":(\d+)", re.IGNORECASE)
RATE_LIMIT_EPOCH_RE = re.compile(r"resets_at\\\":(\d+)", re.IGNORECASE)
FILE_BLOCK_RE = re.compile(r'<file path="([^"]+)">\\n(.*?)\\n</file>', re.DOTALL)
TARGET_PATH_RE = re.compile(r"([A-Za-z0-9_./-]+\\.(?:md|ts|tsx|js|jsx|json|yml|yaml|toml))")
IGNORABLE_ERROR_PATTERNS = [
    r"rmcp::transport::worker",
    r"AuthRequired\(AuthRequiredError",
    r"invalid_token",
    r"OAuth token exchange failed",
    r"mcp\.notion\.com/mcp",
    r"mcp\.linear\.app/mcp",
    r"unexpected EOF during handshake",
]


def set_ansi_enabled(enabled: bool) -> None:
    global ANSI_ENABLED
    ANSI_ENABLED = bool(enabled)


def supports_color() -> bool:
    if not ANSI_ENABLED:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def colorize(label: str, text: str, enabled: bool) -> str:
    if not enabled:
        return f"[{label}] {text}"
    color = ANSI_COLORS.get(label, "")
    if color:
        return f"{color}[{label}] {text}{ANSI_RESET}"
    return f"[{label}] {text}"


def safe_truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def strip_ansi(text: str) -> str:
    if not text:
        return text
    return ANSI_ESCAPE_RE.sub("", text)


def extract_rate_limit_seconds(text: str) -> int:
    if not text:
        return 0
    match = RATE_LIMIT_SECONDS_RE.search(text)
    if match:
        try:
            return max(0, int(match.group(1)))
        except ValueError:
            return 0
    match = RATE_LIMIT_EPOCH_RE.search(text)
    if match:
        try:
            reset_at = int(match.group(1))
            now = int(time.time())
            return max(0, reset_at - now)
        except ValueError:
            return 0
    return 0


def is_ignorable_error_line(text: str) -> bool:
    if not text:
        return False
    for pattern in IGNORABLE_ERROR_PATTERNS:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def unique_preserve(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def normalize_path(text: str) -> str:
    if not text:
        return ""
    path = text.strip().strip("'\"")
    path = path.rstrip(").,;")
    return path


def extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        if "text" in content and isinstance(content["text"], str):
            return content["text"].strip()
        if "content" in content and isinstance(content["content"], str):
            return content["content"].strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in ("text", "output_text", "input_text"):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text.strip())
        return " ".join(part for part in parts if part)
    return ""
