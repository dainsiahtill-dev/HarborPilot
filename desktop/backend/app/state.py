from dataclasses import dataclass, field
from typing import Optional, Any, Dict, Set
import subprocess
from .config import Settings

@dataclass
class ProcessHandle:
    process: Optional[subprocess.Popen] = None
    log_handle: Optional[Any] = None
    log_path: str = ""
    mode: str = ""
    started_at: Optional[float] = None

@dataclass
class AppState:
    settings: Settings
    pm: ProcessHandle = field(default_factory=ProcessHandle)
    director: ProcessHandle = field(default_factory=ProcessHandle)
    last_pm_payload: Optional[Dict[str, Any]] = None

class Auth:
    def __init__(self, token: str):
        self.token = token or ""

    def check(self, header_value: str) -> bool:
        if not self.token:
            return True
        if not header_value:
            return False
        if not header_value.lower().startswith("bearer "):
            return False
        value = header_value.split(" ", 1)[1].strip()
        return value == self.token

class ConnectionState:
    def __init__(self) -> None:
        self.channels: Set[str] = set()
        self.tail_state: Dict[str, Dict[str, Any]] = {}
        self.last_sizes: Dict[str, int] = {}
        self.want_status: bool = False
