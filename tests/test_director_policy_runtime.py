import os
import sys
import unittest
from pathlib import Path
import importlib.util
from types import SimpleNamespace


def _load_runtime_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_dir = repo_root / "harborpilot" / "modules" / "harborpilot-loop"
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    module_path = repo_root / "harborpilot" / "modules" / "harborpilot-loop" / "director_policy_runtime.py"
    spec = importlib.util.spec_from_file_location("director_policy_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load director_policy_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDirectorPolicyRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = _load_runtime_module()

    def test_apply_policy_to_state_updates_context(self):
        state = SimpleNamespace(
            auto_repair=True,
            repair_rounds=1,
            reviewer_enabled=True,
            reviewer_rounds=1,
            rollback_on_fail=True,
            risk_block_threshold=0,
            rollback_on_block=True,
            evidence_verbosity="summary",
            evidence_write_enabled=True,
            rag_topk=5,
            memory_enabled=True,
            memory_backend="lancedb",
            memory_store_enabled=True,
            memory_store_every=1,
            memory_store_on_accept=False,
            memory_dir_full="",
            memory_snapshot=None,
            memory_snapshot_path="",
            budget_max_rounds=6,
            budget_max_lines=1200,
            default_tools_enabled=True,
            context_pm_tasks_max_chars=8000,
            context_known_files_max_chars=2000,
            context_last_result_max_chars=2000,
            context_tool_output_max_chars=9000,
            context_planner_output_max_chars=6000,
            context_ollama_output_max_chars=6000,
        )
        policy = {
            "repair": {"auto_repair": False, "max_attempts": 2},
            "rag": {"topk": 3},
            "context": {"pm_tasks_max_chars": 123},
        }
        env_key = "HARBORPILOT_RAG_TOPK"
        original_env = os.environ.get(env_key)
        try:
            self.runtime.apply_policy_to_state(state, policy)
            self.assertEqual(state.auto_repair, False)
            self.assertEqual(state.repair_rounds, 2)
            self.assertEqual(state.rag_topk, 3)
            self.assertEqual(state.context_pm_tasks_max_chars, 123)
            self.assertEqual(os.environ.get(env_key), "3")
        finally:
            if original_env is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original_env


if __name__ == "__main__":
    raise SystemExit(unittest.main())
