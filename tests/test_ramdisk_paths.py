import os
import sys
import tempfile
import unittest
from pathlib import Path


def _import_io_utils():
    here = Path(__file__).resolve()
    module_dir = here.parents[1] / "modules" / "harborpilot-loop"
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    import io_utils  # type: ignore

    return io_utils


class TestRamdiskPaths(unittest.TestCase):
    def test_resolve_artifact_path_routes_hot_files_to_cache_root(self):
        io_utils = _import_io_utils()
        with tempfile.TemporaryDirectory() as workspace_dir, tempfile.TemporaryDirectory() as ramdisk_dir:
            workspace = os.path.abspath(workspace_dir)
            cache_root = io_utils.build_cache_root(ramdisk_dir, workspace)
            self.assertTrue(cache_root)

            hot_jsonl = io_utils.resolve_artifact_path(workspace, cache_root, "state/ollama/events.jsonl")
            self.assertTrue(os.path.commonpath([hot_jsonl, cache_root]) == cache_root)

            hot_runlog = io_utils.resolve_artifact_path(workspace, cache_root, "state/ollama/RUNLOG.md")
            self.assertTrue(os.path.commonpath([hot_runlog, cache_root]) == cache_root)

            hot_memory = io_utils.resolve_artifact_path(workspace, cache_root, "state/ollama/memory/last_state.json")
            self.assertTrue(os.path.commonpath([hot_memory, cache_root]) == cache_root)

            cold = io_utils.resolve_artifact_path(workspace, cache_root, "state/ollama/PM_TASKS.json")
            self.assertTrue(os.path.commonpath([cold, workspace]) == workspace)


if __name__ == "__main__":
    raise SystemExit(unittest.main())

