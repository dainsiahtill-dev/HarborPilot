import json
import sys
import pytest
from pathlib import Path
import importlib.util


def _load_loop_director():
    repo_root = Path(__file__).resolve().parents[3]
    module_dir = repo_root / "harborpilot" / "modules" / "harborpilot-loop"
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    module_path = repo_root / "harborpilot" / "loops" / "loop-director.py"
    spec = importlib.util.spec_from_file_location("loop_director", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load loop-director.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_invoke_ollama(prompt: str, model: str, workspace: str, show_output: bool, timeout: int) -> str:
    if "Director-PatchPlanner" in prompt:
        payload = {
            "fsm_state": "ACTION",
            "need_more_context": False,
            "plan": {
                "summary": "Update example module",
                "steps": [
                    {
                        "purpose": "Edit example file",
                        "files": ["src/example.py"],
                        "expected": "Adds greeting function",
                        "checks": [],
                    }
                ],
                "acceptance": ["Example file updated"],
            },
            "act": {
                "brief": "Add greeting function",
                "files": ["src/example.py"],
                "commands": [],
                "tool_commands": [],
            },
        }
        return json.dumps(payload, ensure_ascii=False)
    if "code-writing assistant for a local repo" in prompt:
        return "FILE: src/example.py\n" \
               "def greet(name: str) -> str:\n" \
               "    return f'Hello, {name}!'\n" \
               "\n" \
               "END FILE"
    if "QA / acceptance reviewer" in prompt:
        return json.dumps({"acceptance": "PASS", "summary": "ok", "next": "done"})
    if "Reviewer / critic" in prompt:
        return json.dumps({"summary": "ok", "issues": []})
    if "Director-ToolPlanner" in prompt:
        return json.dumps({
            "fsm_state": "CONTEXT_READY",
            "reason": "required evidence provided",
            "tool_plan": [],
            "budget": {"max_rounds": 1, "max_total_lines": 200}
        })
    return "{}"


def test_director_end_to_end(tmp_path, monkeypatch):
    loop_director = _load_loop_director()
    import director_exec

    workspace = tmp_path / "workspace"
    (workspace / "docs").mkdir(parents=True, exist_ok=True)
    (workspace / "src").mkdir(parents=True, exist_ok=True)
    (workspace / "src" / "example.py").write_text("# placeholder\n", encoding="utf-8")

    state_dir = workspace / "state" / "ollama"
    state_dir.mkdir(parents=True, exist_ok=True)

    plan_path = state_dir / "PLAN.md"
    plan_path.write_text("# Plan\n", encoding="utf-8")

    pm_task_path = state_dir / "PM_TASKS.json"
    pm_payload = {
        "pm_iteration": 1,
        "timestamp": "2024-01-01 00:00:00",
        "overall_goal": "Test",
        "focus": "Update example",
        "tasks": [
            {
                "id": "PM-TEST",
                "priority": 1,
                "title": "Update example",
                "goal": "Add greeting",
                "target_files": ["src/example.py"],
                "acceptance": ["Example file updated"],
                "required_evidence": {
                    "must_read": [{"file": "src/example.py", "start": 1, "end": 3}],
                },
            }
        ],
    }
    pm_task_path.write_text(json.dumps(pm_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(loop_director, "invoke_ollama", _fake_invoke_ollama)
    monkeypatch.setattr(director_exec, "invoke_ollama", _fake_invoke_ollama)
    monkeypatch.setattr(loop_director, "stop_requested", lambda _: False)

    log_path = state_dir / "RUNLOG.md"
    planner_path = state_dir / "PLANNER_RESPONSE.md"
    ollama_path = state_dir / "OLLAMA_RESPONSE.md"
    qa_path = state_dir / "QA_RESPONSE.md"
    reviewer_path = state_dir / "REVIEW_RESPONSE.md"
    director_result_path = state_dir / "DIRECTOR_RESULT.json"
    dialogue_path = state_dir / "DIALOGUE.jsonl"
    events_path = state_dir / "events.jsonl"
    gap_report_path = state_dir / "GAP_REPORT.md"

    state = loop_director.State(
        workspace_full=str(workspace),
        cache_root_full=str(workspace),
        plan_full=str(plan_path),
        log_full=str(log_path),
        planner_full=str(planner_path),
        ollama_full=str(ollama_path),
        qa_full=str(qa_path),
        reviewer_full=str(reviewer_path),
        delay_seconds=0,
        repair_rounds=1,
        auto_repair=False,
        continue_on_error=False,
        show_output=False,
        model="fake",
        timeout=0,
        auto_pick_target=False,
        memory_backend="none",
        memory_enabled=False,
        memory_dir_full=str(state_dir / "memory"),
        memory_snapshot_path=str(state_dir / "memory" / "last_state.json"),
        memory_snapshot=None,
        memory_max_chars=2000,
        memory_store_enabled=False,
        memory_store_every=1,
        memory_store_on_accept=False,
        run_npm_commands=False,
        npm_timeout=0,
        gap_review_enabled=False,
        gap_report_full=str(gap_report_path),
        gap_max_headings=10,
        gap_max_files=10,
        gap_review_done=True,
        gap_write_plan=False,
        pm_task_path=str(pm_task_path),
        director_result_full=str(director_result_path),
        dialogue_full=str(dialogue_path),
        events_full=str(events_path),
        default_tools_enabled=False,
        reviewer_enabled=False,
        reviewer_rounds=0,
        rollback_on_fail=True,
        risk_block_threshold=0,
        evidence_verbosity="summary",
        evidence_write_enabled=True,
        rag_topk=5,
        rollback_on_block=False,
        budget_max_rounds=2,
        budget_max_lines=200,
        context_pm_tasks_max_chars=2000,
        context_known_files_max_chars=1000,
        context_last_result_max_chars=1000,
        context_tool_output_max_chars=2000,
        context_planner_output_max_chars=2000,
        context_ollama_output_max_chars=2000,
        policy_base={
            "repair": {
                "auto_repair": False,
                "reviewer_enabled": False,
                "reviewer_rounds": 0,
                "rollback_on_fail": True,
                "max_attempts": 1,
            },
            "qa": {"default_tools": False},
            "memory": {"enabled": False, "backend": "none", "store_enabled": False},
            "rag": {"enabled": False, "topk": 0},
            "io": {"jsonl_buffered": False, "flush_interval_sec": 0.0, "flush_batch": 1, "max_buffer": 1},
        },
        policy_sources={},
        policy_cli_overrides={},
        policy_path="",
    )

    result = loop_director.invoke_iteration(state, 1, True)
    assert result["ok"] is True

    payload = json.loads(Path(director_result_path).read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload.get("patch_plan")
    assert payload.get("patch_act")
    assert payload.get("changed_files") == ["src/example.py"]
    assert Path(payload.get("evidence_path")).is_file()

    file_text = (workspace / "src" / "example.py").read_text(encoding="utf-8")
    assert "def greet" in file_text

    events = Path(events_path).read_text(encoding="utf-8").splitlines()
    assert any("patch_plan" in line for line in events)
    assert any("patch_act" in line for line in events)
