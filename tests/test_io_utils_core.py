import os
import json
import tempfile
import unittest
from pathlib import Path


def _import_io_utils():
    repo_root = Path(__file__).resolve().parents[2]
    module_dir = repo_root / "harborpilot" / "modules" / "harborpilot-loop"
    if str(module_dir) not in os.sys.path:
        os.sys.path.insert(0, str(module_dir))
    import io_utils  # type: ignore

    return io_utils


class TestIoUtilsCore(unittest.TestCase):
    def test_find_workspace_root_uses_docs(self):
        io_utils = _import_io_utils()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs").mkdir()
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            found = io_utils.find_workspace_root(str(nested))
            self.assertEqual(os.path.abspath(found), os.path.abspath(str(root)))

    def test_resolve_workspace_path_raises_without_docs(self):
        io_utils = _import_io_utils()
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                io_utils.resolve_workspace_path(temp_dir, require_docs=True)

    def test_resolve_workspace_path_allows_missing_docs(self):
        io_utils = _import_io_utils()
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = io_utils.resolve_workspace_path(temp_dir, require_docs=False)
            self.assertEqual(os.path.abspath(resolved), os.path.abspath(temp_dir))

    def test_is_hot_artifact_path(self):
        io_utils = _import_io_utils()
        self.assertTrue(io_utils.is_hot_artifact_path(".harborpilot/runtime/events.jsonl"))
        self.assertTrue(io_utils.is_hot_artifact_path(".harborpilot/runtime/RUNLOG.md"))
        self.assertFalse(io_utils.is_hot_artifact_path(".harborpilot/runtime/PM_TASKS.json"))

    def test_resolve_artifact_path_routes_hot_files(self):
        io_utils = _import_io_utils()
        with tempfile.TemporaryDirectory() as workspace_dir, tempfile.TemporaryDirectory() as ramdisk_dir:
            workspace = os.path.abspath(workspace_dir)
            cache_root = io_utils.build_cache_root(ramdisk_dir, workspace)
            self.assertTrue(cache_root)
            hot = io_utils.resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/events.jsonl")
            self.assertTrue(os.path.commonpath([hot, cache_root]) == cache_root)
            cold = io_utils.resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/PM_TASKS.json")
            self.assertTrue(os.path.commonpath([cold, workspace]) == workspace)

    def test_emit_event_and_dialogue(self):
        io_utils = _import_io_utils()
        with tempfile.TemporaryDirectory() as temp_dir:
            dialogue_path = os.path.join(temp_dir, "dialogue.jsonl")
            events_path = os.path.join(temp_dir, "events.jsonl")
            io_utils.emit_dialogue(dialogue_path, speaker="PM", type="say", text="hello")
            io_utils.emit_event(events_path, kind="action", actor="System", name="noop", summary="test")
            io_utils.flush_jsonl_buffers(force=True)

            with open(dialogue_path, "r", encoding="utf-8") as handle:
                dialogue = json.loads(handle.readline())
            with open(events_path, "r", encoding="utf-8") as handle:
                event = json.loads(handle.readline())

            self.assertEqual(dialogue["speaker"], "PM")
            self.assertEqual(event["kind"], "action")
            self.assertIn("event_id", event)

    def test_stop_flag_helpers(self):
        io_utils = _import_io_utils()
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "docs").mkdir()
            stop_path = io_utils.stop_flag_path(str(workspace))
            self.assertFalse(io_utils.stop_requested(str(workspace)))
            Path(stop_path).parent.mkdir(parents=True, exist_ok=True)
            Path(stop_path).write_text("stop", encoding="utf-8")
            self.assertTrue(io_utils.stop_requested(str(workspace)))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
