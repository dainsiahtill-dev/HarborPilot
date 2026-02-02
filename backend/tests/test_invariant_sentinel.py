import json
import os
import sys


MODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core", "harborpilot_loop"))
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

from invariant_sentinel import compute_contract_fingerprint, run_invariant_sentinel  # noqa: E402


def _write_events(path: str, seqs):
    with open(path, "w", encoding="utf-8") as handle:
        for seq in seqs:
            handle.write(json.dumps({"seq": seq}) + "\n")


def test_invariant_sentinel_contract_violation(tmp_path):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("", encoding="utf-8")
    pm_task_path = tmp_path / "PM_TASKS.json"
    payload_a = {"overall_goal": "A", "tasks": [{"id": "t1", "goal": "G1", "acceptance": ["x"]}]}
    pm_task_path.write_text(json.dumps(payload_a), encoding="utf-8")
    fingerprint = compute_contract_fingerprint(payload_a)
    payload_b = {"overall_goal": "B", "tasks": [{"id": "t1", "goal": "G1", "acceptance": ["x"]}]}
    pm_task_path.write_text(json.dumps(payload_b), encoding="utf-8")

    result = run_invariant_sentinel(
        events_path=str(events_path),
        run_id="run-1",
        step=1,
        pm_task_path=str(pm_task_path),
        contract_fingerprint=fingerprint,
        events_seq_start=0,
        events_size_start=0,
        memory_path="",
    )
    codes = [v.get("code") for v in result.get("violations", [])]
    assert "CONTRACT_IMMUTABLE" in codes


def test_invariant_sentinel_events_violation(tmp_path):
    events_path = tmp_path / "events.jsonl"
    _write_events(str(events_path), [1, 2])
    result = run_invariant_sentinel(
        events_path=str(events_path),
        run_id="run-2",
        step=1,
        pm_task_path="",
        contract_fingerprint="",
        events_seq_start=5,
        events_size_start=999,
        memory_path="",
    )
    codes = [v.get("code") for v in result.get("violations", [])]
    assert "EVENTS_APPEND_ONLY" in codes


def test_invariant_sentinel_memory_refs(tmp_path):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("", encoding="utf-8")
    memory_path = tmp_path / "MEMORY.jsonl"
    memory_path.write_text(
        json.dumps({"id": "mem-1", "context": {"run_id": "run-3"}}) + "\n",
        encoding="utf-8",
    )
    result = run_invariant_sentinel(
        events_path=str(events_path),
        run_id="run-3",
        step=1,
        pm_task_path="",
        contract_fingerprint="",
        events_seq_start=0,
        events_size_start=0,
        memory_path=str(memory_path),
    )
    codes = [v.get("code") for v in result.get("violations", [])]
    assert "MEMORY_REFS" in codes
