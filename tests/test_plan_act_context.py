import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load_loop_director():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "harborpilot" / "loops" / "loop-director.py"
    spec = importlib.util.spec_from_file_location("loop_director", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load loop-director.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPlanActAndContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop_director = _load_loop_director()

    def test_parse_planner_payload_plan_act(self):
        payload = {
            "fsm_state": "ACTION",
            "need_more_context": False,
            "plan": {
                "summary": "Plan summary",
                "steps": [
                    {
                        "purpose": "Update logic",
                        "files": ["a.py", "b.py"],
                        "expected": "Behavior fixed",
                        "checks": ["npm test"],
                    }
                ],
                "acceptance": ["tests pass"],
            },
            "act": {
                "brief": "Apply changes",
                "files": ["a.py", "b.py"],
                "commands": ["npm test"],
                "tool_commands": ["python tools.py repo_rg -- foo"],
            },
            "qa": "run tests",
        }
        text = json.dumps(payload, ensure_ascii=False)
        parsed = self.loop_director.parse_planner_payload(text)
        self.assertEqual(parsed.get("brief"), "Apply changes")
        self.assertEqual(parsed.get("files"), ["a.py", "b.py"])
        self.assertEqual(parsed.get("commands"), ["npm test"])
        self.assertEqual(parsed.get("tool_commands"), ["python tools.py repo_rg -- foo"])
        self.assertIn("plan", parsed)
        self.assertIsInstance(parsed.get("plan"), dict)
        self.assertIn("act", parsed)
        self.assertIsInstance(parsed.get("act"), dict)

    def test_compact_pm_payload_respects_max_chars(self):
        pm_payload = {
            "overall_goal": "G" * 500,
            "focus": "F" * 400,
            "notes": "N" * 400,
            "tasks": [
                {
                    "id": f"PM-{idx}",
                    "title": "T" * 200,
                    "goal": "G" * 200,
                    "target_files": [f"file_{i}.py" for i in range(20)],
                    "context_files": [f"ctx_{i}.py" for i in range(20)],
                    "constraints": ["C" * 80 for _ in range(10)],
                    "acceptance": ["A" * 80 for _ in range(10)],
                }
                for idx in range(5)
            ],
        }
        max_chars = 140
        compact = self.loop_director._compact_pm_payload(pm_payload, max_chars)
        serialized = json.dumps(compact, ensure_ascii=False)
        # Allow small overhead for truncation suffix
        self.assertLessEqual(len(serialized), max_chars + 20)

    def test_compact_tool_output_bundle_limits_size(self):
        tool_outputs = [
            {
                "tool": "repo_read_around",
                "file": "a.py",
                "start_line": 1,
                "end_line": 200,
                "truncated": True,
                "content": [{"n": i, "t": "line" * 10} for i in range(1, 60)],
            },
            {
                "tool": "repo_rg",
                "pattern": "foo",
                "paths": ["."],
                "hits": [{"file": "a.py", "line": 10, "col": 1, "text": "foo"}],
            },
        ]
        bundle = self.loop_director._compact_tool_output_bundle(
            tool_outputs, tool_rounds=2, total_lines_read=120, max_chars=300, verbosity="summary"
        )
        serialized = json.dumps(bundle, ensure_ascii=False)
        self.assertLessEqual(len(serialized), 300 + 20)
        self.assertIn("results", bundle)

    def test_truncate_for_review_adds_suffix(self):
        state = SimpleNamespace(
            context_planner_output_max_chars=10,
            context_ollama_output_max_chars=8,
        )
        planner_text = "P" * 50
        ollama_text = "O" * 50
        planner_out, ollama_out = self.loop_director._truncate_for_review(state, planner_text, ollama_text)
        self.assertIn("...[truncated]", planner_out)
        self.assertIn("...[truncated]", ollama_out)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
