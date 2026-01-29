import os
import sys
import unittest
from pathlib import Path
import importlib.util


def _load_exec_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_dir = repo_root / "harborpilot" / "modules" / "harborpilot-loop"
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    module_path = repo_root / "harborpilot" / "modules" / "harborpilot-loop" / "director_exec.py"
    spec = importlib.util.spec_from_file_location("director_exec", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load director_exec.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDirectorExecUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exec_mod = _load_exec_module()

    def test_filter_npm_commands(self):
        commands = ["npm test", "python script.py", "npm run build"]
        filtered = self.exec_mod.filter_npm_commands(commands)
        self.assertEqual(filtered, ["npm test", "npm run build"])

    def test_normalize_tool_command(self):
        cmd = "python tools.py repo_rg -- foo"
        tokens = self.exec_mod.normalize_tool_command(cmd)
        self.assertTrue(tokens)
        self.assertEqual(os.path.basename(tokens[0]).lower(), os.path.basename(sys.executable).lower())
        self.assertTrue(any(token.endswith("tools.py") for token in tokens))

    def test_assess_patch_risk(self):
        changed = [f"file_{i}.py" for i in range(6)]
        snapshot = {path: "old" for path in changed}
        risk = self.exec_mod.assess_patch_risk(changed, snapshot)
        self.assertGreaterEqual(risk["score"], 3)
        self.assertIn("Too many files changed", risk["reasons"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
