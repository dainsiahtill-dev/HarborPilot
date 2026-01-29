import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

PORTS = [3180, 3181, 3182, 3183, 6379]


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


def _build_utf8_env() -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    return env


_enforce_utf8()


def get_port_status(port: int) -> str:
    pid = None
    pname = ""
    try:
        import psutil  # type: ignore

        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == port:
                pid = conn.pid
                break
        if pid:
            try:
                pname = psutil.Process(pid).name()
            except Exception:
                pname = ""
    except Exception:
        pid = None

    if pid:
        if pname:
            return f"in use by {pname} (PID {pid})"
        return f"in use (PID {pid})"

    try:
        output = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="ignore",
            env=_build_utf8_env(),
        )
        for line in output.splitlines():
            line = line.strip()
            if not line.startswith("TCP"):
                continue
            parts = re.split(r"\s+", line)
            if len(parts) < 5:
                continue
            local_addr = parts[1]
            if local_addr.endswith(f":{port}"):
                pid = parts[4]
                return f"in use (PID {pid})"
    except Exception:
        pass

    return "free"


def get_port_summary() -> str:
    lines = [f"- {port}: {get_port_status(port)}" for port in PORTS]
    return "\n".join(lines)


def is_port_free(port: int) -> bool:
    return get_port_status(port).startswith("free")


def find_free_port(start_port: int, max_offset: int = 50) -> Optional[int]:
    for offset in range(1, max_offset + 1):
        candidate = start_port + offset
        if is_port_free(candidate):
            return candidate
    return None


def plan_port_policy(policy: str) -> Dict[str, Any]:
    normalized = (policy or "auto").strip().lower()
    in_use = {port for port in PORTS if not is_port_free(port)}
    overrides: Dict[str, str] = {}
    notes: List[str] = []
    skips: List[int] = []

    if not in_use or normalized in ("none", "off", "disabled", "false", "0"):
        return {"policy": normalized, "overrides": overrides, "notes": notes, "skips": skips}

    def maybe_switch(port: int, label: str) -> Optional[int]:
        alt = find_free_port(port + 9)
        if alt:
            notes.append(f"- {label} port {port} in use -> suggest {alt}")
        return alt

    for port in (3181,):
        if port not in in_use:
            continue
        if normalized in ("switch", "auto"):
            alt = maybe_switch(port, "Server")
            if alt:
                overrides["PHYSICS_PORT"] = str(alt)
                overrides["VITE_PHYSICS_WS"] = f"ws://localhost:{alt}"
                notes.append(
                    f"- Env overrides: PHYSICS_PORT={alt}, VITE_PHYSICS_WS=ws://localhost:{alt}"
                )
                continue
        skips.append(port)

    for port in (3180, 3182, 3183):
        if port not in in_use:
            continue
        if normalized in ("switch", "auto"):
            alt = maybe_switch(port, "Client")
            if alt:
                notes.append(
                    f"- For dev server on {port}, use `-- --port {alt}` (CLI overrides config)"
                )
                continue
        skips.append(port)

    if skips:
        notes.append(f"- Skip starting dev servers on ports: {', '.join(str(p) for p in skips)}")

    return {"policy": normalized, "overrides": overrides, "notes": notes, "skips": skips}


def stop_port_process(port: int) -> bool:
    pid = None
    try:
        import psutil  # type: ignore

        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == port:
                pid = conn.pid
                break
        if pid and pid != os.getpid():
            try:
                psutil.Process(pid).kill()
                return True
            except Exception:
                return False
    except Exception:
        pid = None

    try:
        output = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="ignore",
            env=_build_utf8_env(),
        )
        for line in output.splitlines():
            line = line.strip()
            if not line.startswith("TCP"):
                continue
            parts = re.split(r"\s+", line)
            if len(parts) < 5:
                continue
            local_addr = parts[1]
            if local_addr.endswith(f":{port}"):
                pid = parts[4]
                break
    except Exception:
        pid = None

    if pid and pid != str(os.getpid()):
        try:
            subprocess.check_call(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_build_utf8_env(),
            )
            return True
        except Exception:
            return False
    return False
