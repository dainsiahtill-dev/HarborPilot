import unittest
from pathlib import Path
import importlib.util


def _load_loop_director():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "harborpilot" / "loops" / "loop-director.py"
    spec = importlib.util.spec_from_file_location("loop_director", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load loop-director.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestLoopDirectorEvidencePlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop_director = _load_loop_director()

    def test_build_required_tool_plan(self):
        required = {
            "must_read": [
                {"file": "a.py", "start": 1, "end": 5},
                {"file": "b.py", "around": "MyClass", "radius": 40},
            ],
            "must_find_calls": ["do_work("]
        }
        plan = self.loop_director.build_required_tool_plan(required)
        tools = [step.get("tool") for step in plan]
        self.assertIn("repo_read_slice", tools)
        self.assertIn("repo_rg", tools)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
