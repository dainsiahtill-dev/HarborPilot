import unittest
from pathlib import Path
import importlib.util


def _load_loop_pm():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "harborpilot" / "loops" / "loop-pm.py"
    spec = importlib.util.spec_from_file_location("loop_pm", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load loop-pm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestLoopPmUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop_pm = _load_loop_pm()

    def test_normalize_tasks_generates_id(self):
        raw = [{"title": "Do thing", "goal": "Do it", "target_files": ["a.py"]}]
        tasks = self.loop_pm.normalize_tasks(raw, iteration=1)
        self.assertTrue(tasks)
        self.assertTrue(tasks[0]["id"].startswith("PM-"))

    def test_normalize_pm_payload_defaults(self):
        payload = {"tasks": []}
        normalized = self.loop_pm.normalize_pm_payload(payload, iteration=2, timestamp="2024-01-01")
        self.assertEqual(normalized["overall_goal"], "Advance global requirements")
        self.assertEqual(normalized["pm_iteration"], 2)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
