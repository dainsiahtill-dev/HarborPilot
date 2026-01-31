import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestDirectorStopPath(unittest.TestCase):
    def _import_io_utils(self):
        repo_root = Path(__file__).resolve().parents[2]
        module_dir = repo_root / "harborpilot" / "modules" / "harborpilot-loop"
        if str(module_dir) not in sys.path:
            sys.path.insert(0, str(module_dir))
        import io_utils  # type: ignore

        return io_utils

    def test_stop_flag_writes_director_result_with_ramdisk(self):
        repo_root = Path(__file__).resolve().parents[2]
        director_script = repo_root / "harborpilot" / "loops" / "loop-director.py"
        self.assertTrue(director_script.is_file())

        io_utils = self._import_io_utils()

        with tempfile.TemporaryDirectory() as workspace_dir, tempfile.TemporaryDirectory() as ramdisk_dir:
            workspace = Path(workspace_dir)
            (workspace / "docs").mkdir(parents=True, exist_ok=True)
            state_dir = workspace / ".harborpilot" / "runtime"
            state_dir.mkdir(parents=True, exist_ok=True)

            (state_dir / "PM_STOP.flag").write_text("stop\n", encoding="utf-8")
            (state_dir / "PLAN.md").write_text("# plan\n", encoding="utf-8")

            result_path = state_dir / "DIRECTOR_RESULT.json"
            cache_root = Path(io_utils.build_cache_root(ramdisk_dir, str(workspace)))
            log_path = cache_root / ".harborpilot" / "runtime" / "RUNLOG.md"
            dialogue_path = cache_root / ".harborpilot" / "runtime" / "DIALOGUE.jsonl"

            cmd = [
                sys.executable,
                str(director_script),
                "--workspace",
                str(workspace),
                "--iterations",
                "1",
                "--plan-path",
                ".harborpilot/runtime/PLAN.md",
                "--director-result-path",
                ".harborpilot/runtime/DIRECTOR_RESULT.json",
                "--ramdisk-root",
                ramdisk_dir,
            ]
            completed = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="ignore")
            self.assertNotEqual(completed.returncode, 0)
            self.assertTrue(result_path.exists())
            self.assertTrue(log_path.exists())
            self.assertTrue(dialogue_path.exists())

            payload = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("error_code"), "STOP_REQUESTED")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
