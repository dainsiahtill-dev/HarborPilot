import os
import json
from app.services.director_logic import (
    parse_acceptance,
    parse_json_payload,
    compact_pm_payload,
    validate_files_to_edit,
    extract_required_evidence
)

def test_parse_json_payload_clean():
    data = {"key": "value"}
    json_str = json.dumps(data)
    assert parse_json_payload(json_str) == data

def test_parse_json_payload_markdown():
    data = {"key": "value"}
    json_str = f"```json\n{json.dumps(data)}\n```"
    assert parse_json_payload(json_str) == data

def test_parse_json_payload_dirty():
    data = {"key": "value"}
    json_str = f"Here is some text: {json.dumps(data)}"
    assert parse_json_payload(json_str) == data

def test_parse_acceptance_json_pass():
    assert parse_acceptance('{"acceptance": "PASS"}') is True
    assert parse_acceptance('{"acceptance": true}') is True

def test_parse_acceptance_json_fail():
    assert parse_acceptance('{"acceptance": "FAIL"}') is False
    assert parse_acceptance('{"acceptance": false}') is False

def test_parse_acceptance_text_marker():
    assert parse_acceptance("Some log...\nACCEPTANCE_DECISION: PASS") is True
    assert parse_acceptance("ACCEPTANCE: FAIL") is False

def test_parse_acceptance_loose_text():
    assert parse_acceptance("The tests pass successfully.") is True
    assert parse_acceptance("The tests failed with errors.") is False

def test_compact_pm_payload():
    payload = {
        "overall_goal": "Build a rocket",
        "tasks": [
            {"id": "1", "title": "Engine", "goal": "Ignition"},
            {"id": "2", "title": "Hull", "goal": "Structure"},
        ]
    }
    # Test strict compaction
    compact = compact_pm_payload(payload, max_chars=100) # strict limit
    assert "summary" in compact
    assert "overall_goal" not in compact # Should fallback to summary mode

    # Test loose compaction
    compact = compact_pm_payload(payload, max_chars=1000)
    assert "tasks" in compact
    assert len(compact["tasks"]) == 2

def test_validate_files_to_edit(mock_workspace):
    # Setup files
    file1 = os.path.join(mock_workspace, "test1.txt")
    with open(file1, "w", encoding="utf-8") as f:
        f.write("content")
    
    # Test valid
    valid, missing, unreadable = validate_files_to_edit(["test1.txt"], mock_workspace)
    assert valid is True
    assert len(missing) == 0

    # Test missing
    valid, missing, unreadable = validate_files_to_edit(["test1.txt", "missing.txt"], mock_workspace)
    assert valid is True # Logic says it's valid to edit (create) missing files, just logs warn
    assert "missing.txt" in missing

def test_extract_required_evidence():
    payload = {
        "tasks": [
            {
                "id": "1",
                "required_evidence": {"must_read": [{"file": "foo.py"}]}
            }
        ]
    }
    evidence = extract_required_evidence(payload)
    assert evidence["must_read"][0]["file"] == "foo.py"

    # Test top-level evidence
    payload2 = {
        "required_evidence": {"must_read": [{"file": "bar.py"}]}
    }
    evidence2 = extract_required_evidence(payload2)
    assert evidence2["must_read"][0]["file"] == "bar.py"
