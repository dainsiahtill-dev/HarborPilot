import asyncio
import hashlib
import json
import os
import subprocess
import shutil
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import flet as ft


SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
LOOP_PM_PATH = os.path.join(PROJECT_ROOT, "loops", "loop-pm.py")

DEFAULT_MODEL = "modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest"
DEFAULT_PLAN = "state/ollama/PLAN.md"
DEFAULT_GAP = "state/ollama/GAP_REPORT.md"
DEFAULT_QA = "state/ollama/QA_RESPONSE.md"
DEFAULT_REQUIREMENTS = "docs/product/requirements.md"
DEFAULT_PM_OUT = "state/ollama/PM_TASKS.json"
DEFAULT_PM_REPORT = "state/ollama/PM_REPORT.md"
DEFAULT_PM_LOG = "state/ollama/PM_LOG.jsonl"
DEFAULT_PM_SUBPROCESS_LOG = "state/ollama/PM_SUBPROCESS.log"
DEFAULT_PLANNER = "state/ollama/PLANNER_RESPONSE.md"
DEFAULT_OLLAMA = "state/ollama/OLLAMA_RESPONSE.md"
DEFAULT_RUNLOG = "state/ollama/RUNLOG.md"
DEFAULT_DIALOGUE = "state/ollama/DIALOGUE.jsonl"
DIRECTOR_SCRIPT = "loops/loop-director.py"

def enforce_utf8() -> None:
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


def build_utf8_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    if extra:
        env.update(extra)
    return env


enforce_utf8()


def _default_ramdisk_root() -> str:
    value = os.environ.get("HARBORPILOT_RAMDISK_ROOT", "").strip()
    if value:
        return value
    if os.name == "nt" and os.path.exists("X:\\"):
        return "X:\\"
    return ""


DEFAULT_RAMDISK_ROOT = _default_ramdisk_root()


def find_workspace_root(start: str) -> str:
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, "docs")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start)


DEFAULT_WORKSPACE = find_workspace_root(os.getcwd())
TAIL_STATE: Dict[str, Dict[str, Any]] = {}


def read_file_tail(path: str, max_lines: int = 400, max_chars: int = 20000) -> str:
    if not path or not os.path.isfile(path):
        return ""
    try:
        state = TAIL_STATE.setdefault(path, {"pos": 0, "lines": [], "size": 0})
        try:
            size = os.path.getsize(path)
        except Exception:
            size = 0
        if size < state.get("pos", 0) or size < state.get("size", 0):
            state["pos"] = 0
            state["lines"] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            handle.seek(state.get("pos", 0))
            chunk = handle.read()
            state["pos"] = handle.tell()
        if chunk:
            lines = chunk.splitlines()
            if lines:
                state["lines"].extend(lines)
                if max_lines > 0 and len(state["lines"]) > max_lines:
                    state["lines"] = state["lines"][-max_lines:]
        state["size"] = size
        content = "\n".join(state["lines"])
        if max_chars > 0 and len(content) > max_chars:
            return content[-max_chars:]
        return content
    except Exception:
        return ""


def read_json(path: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def get_abs_path(workspace: str, path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(workspace, path)


def normalize_ramdisk_root(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) == 2 and raw[1] == ":":
        raw = raw + "\\"
    raw = os.path.abspath(raw)
    raw = raw.rstrip("\\/")
    if len(raw) == 2 and raw[1] == ":":
        raw = raw + "\\"
    return raw


def build_cache_root(ramdisk_root: str, workspace_full: str) -> str:
    root = normalize_ramdisk_root(ramdisk_root)
    if not root:
        return ""
    try:
        exists = os.path.exists(root)
    except Exception:
        exists = False
    if not exists:
        return ""
    ws = os.path.abspath(workspace_full or "").lower()
    digest = hashlib.sha1(ws.encode("utf-8", errors="ignore")).hexdigest()[:12]
    base_name = os.path.basename(root.rstrip("\\/")).lower()
    if base_name == "harborpilot":
        return os.path.join(root, "cache", digest)
    return os.path.join(root, "HarborPilot", "cache", digest)


def is_hot_artifact_path(rel_path: str) -> bool:
    p = (rel_path or "").replace("\\", "/").lstrip("./")
    if not p.startswith("state/ollama/"):
        return False
    if "/runs/" in p or p.startswith("state/ollama/runs/"):
        return True
    if "/memory/" in p or p.startswith("state/ollama/memory/"):
        return True
    lowered = p.lower()
    if lowered.endswith(".jsonl") or lowered.endswith(".log") or lowered.endswith(".lock"):
        return True
    if lowered.endswith("/runlog.md") or lowered.endswith("runlog.md"):
        return True
    return False


def resolve_artifact_path(workspace_full: str, cache_root_full: str, rel_path: str) -> str:
    if not rel_path:
        return ""
    if os.path.isabs(rel_path):
        return rel_path
    base = cache_root_full if (cache_root_full and is_hot_artifact_path(rel_path)) else workspace_full
    return os.path.join(base, rel_path)


def check_tools_available() -> str:
    missing_execs = []
    missing_modules = []
    for name in ("ruff", "pytest", "coverage", "mypy"):
        if not shutil.which(name):
            missing_execs.append(name)
    for module in ("pydantic", "jsonschema", "tree_sitter", "tree_sitter_languages", "rich"):
        try:
            __import__(module)
        except Exception:
            missing_modules.append(module)
    if missing_execs or missing_modules:
        parts = []
        if missing_execs:
            parts.append("missing executables: " + ", ".join(missing_execs))
        if missing_modules:
            parts.append("missing python modules: " + ", ".join(missing_modules))
        return "; ".join(parts)
    return ""


def main(page: ft.Page) -> None:
    page.title = "HarborPilot Dashboard"
    error = check_tools_available()
    if error:
        def close_app(_: ft.ControlEvent) -> None:
            dialog.open = False
            page.update()
            try:
                page.window_close()
            except Exception:
                pass
            raise SystemExit(1)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Startup check failed"),
            content=ft.Text(error),
            actions=[ft.TextButton("Confirm", on_click=close_app)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog = dialog
        dialog.open = True
        page.update()
        return
    page.window_width = 1200
    page.window_height = 900
    page.scroll = "auto"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

    workspace_field = ft.TextField(label="Workspace", value=DEFAULT_WORKSPACE, expand=True)
    pm_backend_field = ft.Dropdown(
        label="PM Backend",
        value="codex",
        options=[
            ft.dropdown.Option("codex"),
            ft.dropdown.Option("ollama"),
        ],
        width=160,
    )
    model_field = ft.TextField(label="Model", value=DEFAULT_MODEL, expand=True)
    interval_field = ft.TextField(label="Interval (seconds)", value="20", width=180)
    timeout_field = ft.TextField(label="Timeout (seconds)", value="0", width=180)
    refresh_interval_field = ft.TextField(label="UI Refresh (seconds)", value="3", width=180)
    auto_refresh_check = ft.Checkbox(label="Auto refresh", value=True)
    show_memory_check = ft.Checkbox(label="Show memory snapshots", value=False)
    prompt_profile_field = ft.TextField(label="Prompt profile", value="demo_ming_armada", width=180)
    ramdisk_root_field = ft.TextField(label="RAMDisk Root", value=DEFAULT_RAMDISK_ROOT, width=180)
    json_log_field = ft.TextField(label="JSONL Log", value=DEFAULT_PM_LOG, expand=True)
    pm_runs_director_check = ft.Checkbox(label="PM runs Director", value=True)
    pm_director_show_output_check = ft.Checkbox(label="Director show output", value=True)
    pm_director_timeout_field = ft.TextField(label="Director result timeout (s)", value="60", width=200)
    pm_max_failures_field = ft.TextField(label="Max failures", value="5", width=140)
    pm_max_blocked_field = ft.TextField(label="Max blocked", value="5", width=140)
    pm_max_same_field = ft.TextField(label="Max same task", value="3", width=140)
    director_iterations_field = ft.TextField(label="Director iterations", value="1", width=180)
    director_forever_check = ft.Checkbox(label="Director forever", value=False)
    director_show_output_check = ft.Checkbox(label="Director show output", value=True)

    status_dot = ft.Container(width=10, height=10, bgcolor="grey", border_radius=5)
    status_text = ft.Text("Idle")
    last_refresh_text = ft.Text("Last refresh: -")
    file_status_column = ft.Column(spacing=2)
    file_paths_column = ft.Column(spacing=2)

    focus_text = ft.Text("-", size=16, weight="bold")
    notes_text = ft.Text("")
    tasks_column = ft.Column(spacing=8)

    pm_report_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    pm_log_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    planner_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    ollama_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    qa_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    runlog_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    director_console = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    dialogue_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    dialogue_state = {"pos": 0, "seen_ids": set(), "seen_order": []}
    last_pm_payload = {"value": None}
    pm_state_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)
    director_state_view = ft.ListView(auto_scroll=True, expand=True, spacing=2)

    loop_running = {"value": False}
    pm_proc = {"process": None, "log_handle": None, "log_path": ""}
    director_proc = {"process": None}

    def set_status(text: str, color: str) -> None:
        status_text.value = text
        status_dot.bgcolor = color
        page.update()

    def build_tasks_view(tasks: List[Dict[str, Any]]) -> None:
        tasks_column.controls.clear()
        if not tasks:
            tasks_column.controls.append(ft.Text("No tasks found."))
            return
        for task in tasks:
            if not isinstance(task, dict):
                continue
            title = str(task.get("title") or "").strip()
            goal = str(task.get("goal") or "").strip()
            acceptance = task.get("acceptance") or []
            lines: List[str] = []
            if title:
                lines.append(f"Title: {title}")
            if goal:
                lines.append(f"Goal: {goal}")
            if isinstance(acceptance, list) and acceptance:
                lines.append("Acceptance:")
                for item in acceptance:
                    if isinstance(item, str) and item.strip():
                        lines.append(f"- {item.strip()}")
            tasks_column.controls.append(
                ft.Container(
                    content=ft.Text("\n".join(lines)),
                    padding=10,
                    border=ft.Border.all(1, "#dddddd"),
                    border_radius=6,
                )
            )

    def read_state() -> Dict[str, Any]:
        workspace = workspace_field.value or DEFAULT_WORKSPACE
        cache_root = build_cache_root(ramdisk_root_field.value or "", workspace)
        pm_out = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_OUT)
        pm_report = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_REPORT)
        pm_log = resolve_artifact_path(workspace, cache_root, json_log_field.value or DEFAULT_PM_LOG)
        pm_subprocess_log = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
        dialogue_path = resolve_artifact_path(workspace, cache_root, DEFAULT_DIALOGUE)
        pm_state_path = resolve_artifact_path(workspace, cache_root, "state/ollama/PM_STATE.json")
        director_state_path = resolve_artifact_path(workspace, cache_root, "state/ollama/memory/last_state.json")

        planner_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PLANNER)
        ollama_path = resolve_artifact_path(workspace, cache_root, DEFAULT_OLLAMA)
        qa_path = resolve_artifact_path(workspace, cache_root, DEFAULT_QA)
        runlog_path = resolve_artifact_path(workspace, cache_root, DEFAULT_RUNLOG)
        file_entries = [
            ("PM_TASKS.json", pm_out),
            ("PM_REPORT.md", pm_report),
            ("PM_LOG.jsonl", pm_log),
            ("PM_SUBPROCESS.log", pm_subprocess_log),
            ("PM_STATE.json", pm_state_path),
            ("last_state.json", director_state_path),
            ("PM_TASK_HISTORY.jsonl", resolve_artifact_path(workspace, cache_root, "state/ollama/PM_TASK_HISTORY.jsonl")),
            ("PLANNER_RESPONSE.md", planner_path),
            ("OLLAMA_RESPONSE.md", ollama_path),
            ("QA_RESPONSE.md", qa_path),
            ("RUNLOG.md", runlog_path),
            ("DIRECTOR_RESULT.json", resolve_artifact_path(workspace, cache_root, "state/ollama/DIRECTOR_RESULT.json")),
            ("DIALOGUE.jsonl", dialogue_path),
        ]
        file_status = build_file_status(file_entries)
        file_paths = [f"{label}: {path}" for label, path in file_entries]

        payload = read_json(pm_out)
        if payload is None:
            payload = last_pm_payload["value"] or {}
        else:
            last_pm_payload["value"] = payload
        tasks = payload.get("tasks") if isinstance(payload, dict) else []
        pm_state_lines = []
        director_state_lines = []
        if show_memory_check.value:
            pm_state_data = read_json(pm_state_path) or {}
            director_state_data = read_json(director_state_path) or {}
            pm_state_lines = format_memory_state(
                pm_state_data,
                [
                    "pm_iteration",
                    "last_director_status",
                    "consecutive_failures",
                    "consecutive_blocked",
                    "same_task_count",
                    "force_switch",
                    "last_task_signature",
                    "last_updated_ts",
                ],
            )
            director_state_lines = format_memory_state(
                director_state_data,
                [
                    "last_run_at",
                    "last_summary",
                    "last_next_step",
                    "last_target",
                    "last_error",
                ],
            )
        else:
            pm_state_lines = ["(disabled)"]
            director_state_lines = ["(disabled)"]

        return {
            "focus": str(payload.get("focus") or "").strip() if isinstance(payload, dict) else "",
            "notes": str(payload.get("notes") or "").strip() if isinstance(payload, dict) else "",
            "tasks": tasks if isinstance(tasks, list) else [],
            "pm_report": read_file_tail(pm_report, 800, 30000),
            "pm_log": read_file_tail(pm_log, 400, 12000),
            "planner": read_file_tail(planner_path, 400, 12000),
            "ollama": read_file_tail(ollama_path, 400, 12000),
            "qa": read_file_tail(qa_path, 400, 12000),
            "runlog": read_file_tail(runlog_path, 400, 12000),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_status": file_status,
            "file_paths": file_paths,
            "dialogue_path": dialogue_path,
            "pm_state_lines": pm_state_lines,
            "director_state_lines": director_state_lines,
        }

    def apply_state(data: Dict[str, Any]) -> None:
        focus_text.value = data.get("focus") or "-"
        notes_text.value = data.get("notes") or ""
        build_tasks_view(data.get("tasks") or [])
        set_list_lines(pm_report_view, data.get("pm_report") or "", 800)
        set_list_lines(pm_log_view, data.get("pm_log") or "", 400)
        set_list_lines(planner_view, data.get("planner") or "", 400)
        set_list_lines(ollama_view, data.get("ollama") or "", 400)
        set_list_lines(qa_view, data.get("qa") or "", 400)
        set_list_lines(runlog_view, data.get("runlog") or "", 400)
        file_status_column.controls = [
            ft.Text(line) for line in data.get("file_status") or []
        ]
        file_paths_column.controls = [
            ft.Text(line) for line in data.get("file_paths") or []
        ]
        set_list_lines(pm_state_view, "\n".join(data.get("pm_state_lines") or []), 80)
        set_list_lines(director_state_view, "\n".join(data.get("director_state_lines") or []), 80)
        last_refresh_text.value = f"Last refresh: {data.get('timestamp')}"
        page.update()

    def refresh_ui() -> None:
        data = read_state()
        apply_state(data)
        update_dialogue(data.get("dialogue_path") or "")

    def show_memory_changed(_: ft.ControlEvent) -> None:
        refresh_ui()

    def set_list_lines(view: ft.ListView, text: str, max_lines: int) -> None:
        lines = text.splitlines()
        if max_lines > 0 and len(lines) > max_lines:
            lines = lines[-max_lines:]
        view.controls = [ft.Text(line if line else " ") for line in lines]

    def format_dialogue_event(event: Dict[str, Any]) -> str:
        ts = str(event.get("ts") or "")
        if "T" in ts:
            ts = ts.split("T", 1)[1].replace("Z", "")
        speaker = str(event.get("speaker") or "System")
        phase = ""
        refs = event.get("refs")
        if isinstance(refs, dict):
            phase_value = refs.get("phase")
            if isinstance(phase_value, str) and phase_value.strip():
                phase = phase_value.strip()
        text = str(event.get("text") or event.get("summary") or "")
        if phase:
            return f"[{ts}] {speaker} [{phase}]: {text}"
        return f"[{ts}] {speaker}: {text}"

    def format_memory_state(data: Dict[str, Any], keys: List[str]) -> List[str]:
        if not isinstance(data, dict) or not data:
            return ["(empty)"]
        lines: List[str] = []
        for key in keys:
            if key in data:
                value = data.get(key)
                if isinstance(value, str) and len(value) > 200:
                    value = value[:200] + "..."
                lines.append(f"{key}: {value}")
        return lines or ["(empty)"]

    def dialogue_sort_key(event: Dict[str, Any]) -> tuple:
        ts = str(event.get("ts") or "")
        seq = event.get("seq")
        try:
            seq_value = int(seq) if seq is not None else 0
        except Exception:
            seq_value = 0
        event_id = str(event.get("event_id") or "")
        return (ts, seq_value, event_id)

    def remember_event_id(event_id: str) -> bool:
        if not event_id:
            return True
        seen_ids = dialogue_state["seen_ids"]
        seen_order = dialogue_state["seen_order"]
        if event_id in seen_ids:
            return False
        seen_ids.add(event_id)
        seen_order.append(event_id)
        if len(seen_order) > 2000:
            old_id = seen_order.pop(0)
            seen_ids.discard(old_id)
        return True

    def update_dialogue(path: str) -> None:
        if not path or not os.path.exists(path):
            return
        try:
            size = os.path.getsize(path)
        except Exception:
            return
        if size < dialogue_state["pos"]:
            dialogue_state["pos"] = 0
            dialogue_state["seen_ids"].clear()
            dialogue_state["seen_order"].clear()
            dialogue_view.controls.clear()
            dialogue_view.controls.append(ft.Text("[system] Dialogue log rotated, restarting from beginning."))
        try:
            with open(path, "r", encoding="utf-8") as handle:
                handle.seek(dialogue_state["pos"])
                lines = handle.readlines()
                dialogue_state["pos"] = handle.tell()
        except Exception:
            return
        if not lines:
            return
        events: List[Dict[str, Any]] = []
        for line in lines:
            try:
                event = json.loads(line)
            except Exception:
                continue
            if not isinstance(event, dict):
                continue
            events.append(event)
        if not events:
            return
        events.sort(key=dialogue_sort_key)
        for event in events:
            event_id = str(event.get("event_id") or "")
            if not remember_event_id(event_id):
                continue
            dialogue_view.controls.append(ft.Text(format_dialogue_event(event)))
        if len(dialogue_view.controls) > 500:
            dialogue_view.controls = dialogue_view.controls[-500:]
        page.update()

    def format_mtime(path: str) -> str:
        if not path or not os.path.exists(path):
            return "missing"
        try:
            ts = os.path.getmtime(path)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "unknown"

    def build_file_status(entries: List[tuple[str, str]]) -> List[str]:
        lines: List[str] = []
        for label, path in entries:
            mtime = format_mtime(path)
            lines.append(f"{label}: {mtime}")
        return lines

    def parse_int(value: str, fallback: int) -> int:
        try:
            return int(value)
        except Exception:
            return fallback

    def pm_command(loop_mode: bool) -> List[str]:
        cmd = [
            sys.executable,
            get_abs_path(PROJECT_ROOT, LOOP_PM_PATH),
            "--workspace",
            workspace_field.value or DEFAULT_WORKSPACE,
            "--pm-backend",
            (pm_backend_field.value or "codex"),
            "--model",
            model_field.value or DEFAULT_MODEL,
            "--timeout",
            str(parse_int(timeout_field.value or "0", 0)),
            "--json-log",
            json_log_field.value or DEFAULT_PM_LOG,
        ]
        profile_value = (prompt_profile_field.value or "").strip()
        if profile_value:
            cmd.extend(["--prompt-profile", profile_value])
        ramdisk_value = (ramdisk_root_field.value or "").strip()
        if ramdisk_value:
            cmd.extend(["--ramdisk-root", ramdisk_value])
        cmd.extend(
            [
                "--max-failures",
                str(parse_int(pm_max_failures_field.value or "5", 5)),
                "--max-blocked",
                str(parse_int(pm_max_blocked_field.value or "5", 5)),
                "--max-same-task",
                str(parse_int(pm_max_same_field.value or "3", 3)),
            ]
        )
        if loop_mode:
            cmd.extend(["--loop", "--interval", str(parse_int(interval_field.value or "20", 20))])
        if pm_runs_director_check.value:
            cmd.append("--run-director")
            if pm_director_show_output_check.value:
                cmd.append("--director-show-output")
            cmd.extend(["--director-result-timeout", str(parse_int(pm_director_timeout_field.value or "60", 60))])
        return cmd

    def start_pm_process(loop_mode: bool) -> None:
        if pm_proc["process"] is not None:
            return
        cmd = pm_command(loop_mode)
        workspace = workspace_field.value or DEFAULT_WORKSPACE
        cache_root = build_cache_root(ramdisk_root_field.value or "", workspace)
        pm_log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
        set_status(f"PM running ({'loop' if loop_mode else 'once'})", "blue")
        try:
            os.makedirs(os.path.dirname(pm_log_path), exist_ok=True)
            log_handle = open(pm_log_path, "a", encoding="utf-8", errors="ignore")
            process = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=build_utf8_env(),
            )
            pm_proc["process"] = process
            pm_proc["log_handle"] = log_handle
            pm_proc["log_path"] = pm_log_path
        except Exception as exc:
            set_status(f"PM start failed: {exc}", "red")
            handle = pm_proc.get("log_handle")
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            pm_proc["log_handle"] = None
            return

        def wait_worker() -> None:
            process.wait()
            handle = pm_proc.get("log_handle")
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            pm_proc["process"] = None
            pm_proc["log_handle"] = None
            loop_running["value"] = False
            set_status("PM stopped", "grey")

        page.run_thread(wait_worker)

    def run_once_clicked(_: ft.ControlEvent) -> None:
        if loop_running["value"] or pm_proc["process"] is not None:
            return

        start_pm_process(False)

    def start_loop_clicked(_: ft.ControlEvent) -> None:
        if loop_running["value"] or pm_proc["process"] is not None:
            return
        loop_running["value"] = True
        start_pm_process(True)

    def stop_loop_clicked(_: ft.ControlEvent) -> None:
        workspace = workspace_field.value or DEFAULT_WORKSPACE
        stop_flag = os.path.join(workspace, "state", "ollama", "PM_STOP.flag")
        try:
            with open(stop_flag, "w", encoding="utf-8") as handle:
                handle.write("stop\n")
        except Exception:
            pass
        process = pm_proc.get("process")
        if process is None:
            loop_running["value"] = False
            set_status("PM stopped", "grey")
            return

        def stop_worker() -> None:
            try:
                try:
                    process.terminate()
                except Exception:
                    pass
                try:
                    process.wait(timeout=3)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                    try:
                        process.wait(timeout=3)
                    except Exception:
                        pass
            finally:
                handle = pm_proc.get("log_handle")
                if handle is not None:
                    try:
                        handle.close()
                    except Exception:
                        pass
                pm_proc["process"] = None
                pm_proc["log_handle"] = None
                loop_running["value"] = False
                set_status("PM stopped", "grey")

        page.run_thread(stop_worker)

    def refresh_clicked(_: ft.ControlEvent) -> None:
        refresh_ui()

    def add_console_line(line: str) -> None:
        if line is None:
            return
        text = line.rstrip("\n")
        if not text:
            return
        director_console.controls.append(ft.Text(text))
        if len(director_console.controls) > 500:
            director_console.controls = director_console.controls[-500:]
        page.update()

    def director_command() -> List[str]:
        iterations = parse_int(director_iterations_field.value or "1", 1)
        cmd = [sys.executable, get_abs_path(PROJECT_ROOT, DIRECTOR_SCRIPT)]
        profile_value = (prompt_profile_field.value or "").strip()
        if profile_value:
            cmd.extend(["--prompt-profile", profile_value])
        ramdisk_value = (ramdisk_root_field.value or "").strip()
        if ramdisk_value:
            cmd.extend(["--ramdisk-root", ramdisk_value])
        if director_forever_check.value:
            cmd.append("--forever")
        else:
            cmd.extend(["--iterations", str(max(iterations, 1))])
        if director_show_output_check.value:
            cmd.append("--show-output")
        return cmd

    def director_worker() -> None:
        if director_proc["process"] is not None:
            return
        cmd = director_command()
        add_console_line(f"[director] starting: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                env=build_utf8_env(),
            )
            director_proc["process"] = process
            if process.stdout:
                for line in process.stdout:
                    add_console_line(line.rstrip("\n"))
            return_code = process.wait()
            add_console_line(f"[director] exited with code {return_code}")
        except Exception as exc:
            add_console_line(f"[director] error: {exc}")
        finally:
            director_proc["process"] = None

    def start_director_clicked(_: ft.ControlEvent) -> None:
        if director_proc["process"] is not None:
            add_console_line("[director] already running")
            return
        page.run_thread(director_worker)

    def stop_director_clicked(_: ft.ControlEvent) -> None:
        process = director_proc.get("process")
        if process is None:
            add_console_line("[director] not running")
            return
        add_console_line("[director] stopping...")
        try:
            process.terminate()
        except Exception as exc:
            add_console_line(f"[director] terminate failed: {exc}")

    def clear_director_clicked(_: ft.ControlEvent) -> None:
        director_console.controls.clear()
        page.update()

    run_once_button = ft.Button("Run Once", on_click=run_once_clicked)
    start_button = ft.Button("Start Loop", on_click=start_loop_clicked)
    stop_button = ft.Button("Stop Loop", on_click=stop_loop_clicked)
    refresh_button = ft.Button("Refresh", on_click=refresh_clicked)
    show_memory_check.on_change = show_memory_changed
    start_director_button = ft.Button("Start Director", on_click=start_director_clicked)
    stop_director_button = ft.Button("Stop Director", on_click=stop_director_clicked)
    clear_director_button = ft.Button("Clear Director", on_click=clear_director_clicked)

    controls_header = ft.Row(
        controls=[
            run_once_button,
            start_button,
            stop_button,
            refresh_button,
            status_dot,
            status_text,
            last_refresh_text,
        ],
        alignment=ft.MainAxisAlignment.START,
        expand=True,
    )

    settings_section = ft.Column(
        controls=[
            ft.Text("Settings", size=16, weight="bold"),
            ft.Row(controls=[workspace_field]),
            ft.Row(controls=[pm_backend_field, model_field, interval_field, timeout_field]),
            ft.Row(controls=[refresh_interval_field, auto_refresh_check, show_memory_check, prompt_profile_field, ramdisk_root_field]),
            ft.Row(controls=[json_log_field]),
            ft.Row(
                controls=[
                    pm_runs_director_check,
                    pm_director_show_output_check,
                    pm_director_timeout_field,
                    pm_max_failures_field,
                    pm_max_blocked_field,
                    pm_max_same_field,
                ]
            ),
            ft.Text("File status (last modified)", size=14, weight="bold"),
            file_status_column,
            ft.Text("File paths (resolved)", size=14, weight="bold"),
            file_paths_column,
        ],
        spacing=8,
        expand=True,
    )

    pm_tasks_section = ft.Column(
        controls=[
            ft.Text("Current Focus", size=16, weight="bold"),
            focus_text,
            ft.Text("Notes", size=16, weight="bold"),
            notes_text,
            ft.Text("Tasks", size=16, weight="bold"),
            tasks_column,
        ],
        spacing=8,
        expand=True,
    )

    pm_report_tab = ft.Column(
        controls=[
            ft.Text("PM Report", size=16, weight="bold"),
            ft.Container(content=pm_report_view, expand=True),
            ft.Text("PM JSONL Log (tail)", size=16, weight="bold"),
            ft.Container(content=pm_log_view, expand=True),
        ],
        spacing=8,
        expand=True,
    )

    dialogue_tab = ft.Column(
        controls=[
            ft.Text("Dialogue (DIALOGUE.jsonl)", size=16, weight="bold"),
            ft.Container(content=dialogue_view, expand=True),
        ],
        spacing=8,
        expand=True,
    )

    memory_tab = ft.Column(
        controls=[
            ft.Text("Memory Snapshots", size=16, weight="bold"),
            ft.Text("PM_STATE.json", size=14, weight="bold"),
            ft.Container(content=pm_state_view, expand=True),
            ft.Text("last_state.json", size=14, weight="bold"),
            ft.Container(content=director_state_view, expand=True),
        ],
        spacing=8,
        expand=True,
    )

    director_live_section = ft.Column(
        controls=[
            ft.Text("Director Output (Live)", size=16, weight="bold"),
            ft.Row(
                controls=[
                    start_director_button,
                    stop_director_button,
                    clear_director_button,
                    director_iterations_field,
                    director_forever_check,
                    director_show_output_check,
                ],
                spacing=8,
                expand=True,
            ),
            ft.Container(
                content=director_console,
                border=ft.Border.all(1, "#dddddd"),
                padding=8,
                expand=True,
                height=240,
            ),
            ft.ExpansionTile(
                title="Planner Output",
                controls=[ft.Container(content=planner_view, expand=True)],
                expanded=True,
            ),
            ft.ExpansionTile(
                title="Ollama Output",
                controls=[ft.Container(content=ollama_view, expand=True)],
            ),
            ft.ExpansionTile(
                title="QA Output",
                controls=[ft.Container(content=qa_view, expand=True)],
            ),
            ft.ExpansionTile(
                title="Run Log (tail)",
                controls=[ft.Container(content=runlog_view, expand=True)],
            ),
        ],
        spacing=8,
        expand=True,
    )

    tab_items = [
        ("PM Tasks", pm_tasks_section),
        ("PM Report", pm_report_tab),
        ("Dialogue", dialogue_tab),
        ("Memory", memory_tab),
    ]
    active_tab = {"value": 0}
    tab_buttons: List[ft.Button] = []
    tab_container = ft.Container(content=pm_tasks_section, expand=True)

    def update_tab_buttons() -> None:
        for index, button in enumerate(tab_buttons):
            if index == active_tab["value"]:
                button.bgcolor = "#dbeafe"
            else:
                button.bgcolor = None

    def switch_tab(index: int) -> None:
        active_tab["value"] = index
        tab_container.content = tab_items[index][1]
        update_tab_buttons()
        page.update()

    for index, (label, _) in enumerate(tab_items):
        tab_buttons.append(ft.Button(label, on_click=lambda e, i=index: switch_tab(i)))

    update_tab_buttons()
    tab_controls = ft.Row(controls=tab_buttons, spacing=8, expand=True)

    async def auto_refresh_task() -> None:
        while True:
            interval = parse_int(refresh_interval_field.value or "3", 3)
            if auto_refresh_check.value:
                refresh_ui()
            await asyncio.sleep(max(interval, 1))

    page.add(
        ft.Column(
            controls=[
                ft.Text("HarborPilot Dashboard", size=20, weight="bold"),
                controls_header,
                settings_section,
                tab_controls,
                tab_container,
                ft.Divider(),
                director_live_section,
            ],
            spacing=12,
            expand=True,
        )
    )

    refresh_ui()
    page.run_task(auto_refresh_task)


if __name__ == "__main__":
    ft.run(main)
