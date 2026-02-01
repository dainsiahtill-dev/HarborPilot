import json
import sys
from types import SimpleNamespace
from pathlib import Path
import importlib.util


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


def _fake_invoke_ollama(prompt: str, model: str, workspace: str, show_output: bool, timeout: int) -> str:
    payload = {
        "overall_goal": "Functional test",
        "focus": "Create tasks",
        "tasks": [
            {
                "id": "PM-FUNC",
                "priority": 1,
                "title": "Sample task",
                "goal": "Ensure PM loop works",
                "target_files": ["README.md"],
                "acceptance": ["PM_TASKS.json written"],
            }
        ],
        "notes": "ok",
    }
    return json.dumps(payload, ensure_ascii=False)


def test_pm_loop_writes_outputs(tmp_path, monkeypatch):
    loop_pm = _load_loop_pm()

    workspace = tmp_path / "workspace"
    (workspace / "docs").mkdir(parents=True, exist_ok=True)
    (workspace / ".harborpilot" / "runtime").mkdir(parents=True, exist_ok=True)

    (workspace / "docs" / "product").mkdir(parents=True, exist_ok=True)
    (workspace / "docs" / "product" / "requirements.md").write_text("# reqs\n", encoding="utf-8")

    args = SimpleNamespace(
        pm_backend="ollama",
        workspace=str(workspace),
        model="fake",
        timeout=0,
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

    monkeypatch.setattr(loop_pm, "invoke_ollama", _fake_invoke_ollama)
    monkeypatch.setattr(loop_pm, "ensure_ollama_available", lambda: "ollama")

    code = loop_pm.run_once(args, iteration=1)
    assert code == 0

    pm_tasks_path = workspace / ".harborpilot" / "runtime" / "PM_TASKS.json"
    assert pm_tasks_path.is_file()
    payload = json.loads(pm_tasks_path.read_text(encoding="utf-8"))
    assert payload["tasks"][0]["id"] == "PM-FUNC"

    pm_report_path = workspace / ".harborpilot" / "runtime" / "PM_REPORT.md"
    assert pm_report_path.is_file()
