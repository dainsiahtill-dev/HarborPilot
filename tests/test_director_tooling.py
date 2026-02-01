import unittest
from pathlib import Path
import importlib.util
import sys


def _load_tooling_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "harborpilot" / "modules" / "harborpilot-loop" / "director_tooling.py"
    module_dir = module_path.parent
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    spec = importlib.util.spec_from_file_location("director_tooling", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load director_tooling.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDirectorTooling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tooling = _load_tooling_module()

    def test_build_tool_cli_args_repo_rg(self):
        args = self.tooling.build_tool_cli_args("repo_rg", {"pattern": "foo", "paths": ["."], "max_results": 5})
        self.assertEqual(args[:2], ["foo", "."])
        self.assertIn("--max", args)

    def test_normalize_tool_plan_suggests_radius(self):
        plan = [{"tool": "repo_read_around", "args": {"file": "a.py", "line": 10, "radius": 40}}]
        history = {("a.py", 10): {"suggest_radius": 120, "start_line": 1, "end_line": 80}}
        normalized = self.tooling.normalize_tool_plan(plan, history, need_more_context_count=0)
        self.assertEqual(normalized[0]["args"]["radius"], 120)

    def test_annotate_rg_output(self):
        output = {
            "pattern": "foo|bar",
            "hits": [
                {"file": "loops/x.py", "line": 1, "text": "def foo():"},
                {"file": "docs/readme.md", "line": 1, "text": "foo"},
            ],
        }
        self.tooling.annotate_rg_output(output)
        self.assertIn("ranked_hits", output)
        self.assertGreaterEqual(output["ranked_hits"][0]["score"], output["ranked_hits"][1]["score"])

    def test_extract_tool_plan_parses_string_steps(self):
        payload = {
            "tool_plan": [
                "repo_rg -p \"foo\" src --max 5",
                "cat docs/README.md",
            ]
        }
        steps = self.tooling.extract_tool_plan(payload)
        self.assertEqual(steps[0]["tool"], "repo_rg")
        self.assertEqual(steps[0]["args"]["pattern"], "foo")
        self.assertIn("src", steps[0]["args"].get("paths", []))
        self.assertEqual(steps[1]["tool"], "repo_read_head")

    def test_extract_tool_plan_parses_equals_syntax(self):
        payload = {
            "tool_plan": [
                "repo_rg pattern=createServer paths=[src/] --max 5",
                "repo_read_head file=src/index.ts",
            ]
        }
        steps = self.tooling.extract_tool_plan(payload)
        self.assertEqual(steps[0]["tool"], "repo_rg")
        self.assertEqual(steps[0]["args"]["pattern"], "createServer")
        self.assertIn("src/", steps[0]["args"].get("paths", []))
        self.assertEqual(steps[1]["tool"], "repo_read_head")
        self.assertEqual(steps[1]["args"]["file"], "src/index.ts")

    def test_extract_tool_plan_alias_repo_ls(self):
        payload = {"tool_plan": ["repo_ls --recursive --include src/"]}
        steps = self.tooling.extract_tool_plan(payload)
        self.assertEqual(steps[0]["tool"], "repo_tree")
        self.assertEqual(steps[0]["args"]["path"], "src/")
        self.assertEqual(steps[0]["args"].get("depth"), 6)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
