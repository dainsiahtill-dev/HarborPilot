import os
import json
import tempfile
import unittest
from pathlib import Path
import importlib.util


def _load_policy_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "harborpilot" / "modules" / "harborpilot-loop" / "policy.py"
    spec = importlib.util.spec_from_file_location("policy", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPolicyMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = _load_policy_module()

    def test_build_cli_overrides(self):
        overrides = self.policy.build_cli_overrides([
            "--auto-repair",
            "--risk-block-threshold", "5",
            "--rag-topk=3",
            "--memory-backend", "file",
        ])
        self.assertEqual(overrides["repair"]["auto_repair"], True)
        self.assertEqual(overrides["risk"]["block_threshold"], "5")
        self.assertEqual(overrides["rag"]["topk"], "3")
        self.assertEqual(overrides["memory"]["backend"], "file")

    def test_build_env_overrides(self):
        env_keys = [
            "HARBORPILOT_JSONL_BUFFERED",
            "HARBORPILOT_JSONL_FLUSH_INTERVAL",
            "HARBORPILOT_RAG_TOPK",
        ]
        originals = {key: os.environ.get(key) for key in env_keys}
        try:
            os.environ["HARBORPILOT_JSONL_BUFFERED"] = "0"
            os.environ["HARBORPILOT_JSONL_FLUSH_INTERVAL"] = "0.5"
            os.environ["HARBORPILOT_RAG_TOPK"] = "4"
            overrides = self.policy.build_env_overrides()
            self.assertEqual(overrides["io"]["jsonl_buffered"], "0")
            self.assertEqual(overrides["io"]["flush_interval_sec"], "0.5")
            self.assertEqual(overrides["rag"]["topk"], "4")
        finally:
            for key, value in originals.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_build_base_policy_with_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            policy_path.write_text(json.dumps({
                "memory": {"enabled": False, "backend": "lancedb"},
                "budgets": {"max_total_lines_read": 50}
            }, ensure_ascii=False), encoding="utf-8")
            policy, sources = self.policy.build_base_policy(str(policy_path), {})
            self.assertEqual(policy["memory"]["enabled"], False)
            self.assertEqual(policy["memory"]["backend"], "none")
            self.assertEqual(policy["budgets"]["max_total_lines_read"], 1200)
            self.assertTrue("memory.enabled" in sources)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
