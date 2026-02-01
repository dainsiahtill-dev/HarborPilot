import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import importlib.util

import pytest


def _load_loop_pm():
    repo_root = Path(__file__).resolve().parents[3]
    module_dir = repo_root / "harborpilot" / "modules" / "harborpilot-loop"
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    module_path = repo_root / "harborpilot" / "loops" / "loop-pm.py"
    spec = importlib.util.spec_from_file_location("loop_pm", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load loop-pm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ollama_model() -> str:
    return os.environ.get("HARBORPILOT_OLLAMA_MODEL", "").strip()


def _ollama_available() -> bool:
    return bool(shutil.which("ollama"))


def _model_installed(model: str) -> bool:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return False
    if result.returncode != 0:
        return False
    base = model.split(":", 1)[0]
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("name"):
            continue
        name = line.split()[0]
        if name == model or name == base or name.startswith(base + ":"):
            return True
    return False


def _require_ollama() -> str:
    model = _ollama_model()
    if not model:
        pytest.skip("Set HARBORPILOT_OLLAMA_MODEL to run real Ollama integration tests.")
    if not _ollama_available():
        pytest.skip("ollama CLI not found in PATH.")
    if not _model_installed(model):
        pytest.skip(f"Ollama model not installed: {model}. Run `ollama pull {model}` first.")
    return model


def test_pm_loop_real_ollama_smoke(tmp_path, monkeypatch):
    model = _require_ollama()
    monkeypatch.setenv("HARBORPILOT_PROMPT_PROFILE", "generic")

    loop_pm = _load_loop_pm()

    workspace = tmp_path / "workspace"
    (workspace / "docs" / "product").mkdir(parents=True, exist_ok=True)
    (workspace / ".harborpilot" / "runtime").mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("# Smoke\n", encoding="utf-8")

    (workspace / "docs" / "product" / "requirements.md").write_text(
        "For this test, output a single JSON object exactly as requested.\n"
        "Include 1 task that targets README.md and includes acceptance criteria.\n",
        encoding="utf-8",
    )
    (workspace / ".harborpilot" / "runtime" / "PLAN.md").write_text(
        "# Plan\n- Provide a single small task for this test.\n",
        encoding="utf-8",
    )

    timeout = int(os.environ.get("HARBORPILOT_OLLAMA_TIMEOUT", "120") or 120)
    args = SimpleNamespace(
        pm_backend="ollama",
        workspace=str(workspace),
        model=model,
        timeout=timeout,
        plan_path=".harborpilot/runtime/PLAN.md",
        gap_report_path=".harborpilot/runtime/GAP_REPORT.md",
        qa_path=".harborpilot/runtime/QA_RESPONSE.md",
        requirements_path="docs/product/requirements.md",
        pm_out=".harborpilot/runtime/PM_TASKS.json",
        pm_report=".harborpilot/runtime/PM_REPORT.md",
        state_path=".harborpilot/runtime/PM_STATE.json",
        task_history_path=".harborpilot/runtime/PM_TASK_HISTORY.jsonl",
        director_result_path=".harborpilot/runtime/DIRECTOR_RESULT.json",
        loop=False,
        interval=1,
        max_iterations=0,
        max_failures=5,
        max_blocked=5,
        max_same_task=3,
        stop_on_failure=True,
        heartbeat=False,
        json_log="",
        run_director=False,
        director_path="loops/loop-director.py",
        director_model="",
        director_timeout=0,
        director_show_output=False,
        director_result_timeout=100,
        dialogue_path=".harborpilot/runtime/DIALOGUE.jsonl",
        prompt_profile="generic",
        pm_last_message_path=".harborpilot/runtime/PM_LAST_RESPONSE.md",
        ramdisk_root="",
        codex_profile="",
        codex_full_auto=True,
        codex_dangerous=False,
    )

    code = loop_pm.run_once(args, iteration=1)
    assert code == 0

    pm_tasks_path = workspace / ".harborpilot" / "runtime" / "PM_TASKS.json"
    assert pm_tasks_path.is_file()
    payload = json.loads(pm_tasks_path.read_text(encoding="utf-8"))
    assert payload.get("tasks"), "Expected at least one task in PM output."
    task = payload["tasks"][0]
    assert task.get("target_files"), "Expected target_files in PM task."
    assert task.get("acceptance"), "Expected acceptance criteria in PM task."

    pm_report_path = workspace / ".harborpilot" / "runtime" / "PM_REPORT.md"
    assert pm_report_path.is_file()
