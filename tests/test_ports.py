import unittest
from pathlib import Path
import importlib.util
from unittest.mock import patch


def _load_ports_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "harborpilot" / "modules" / "harborpilot-loop" / "ports.py"
    spec = importlib.util.spec_from_file_location("ports", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load ports.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPorts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ports = _load_ports_module()

    def test_plan_port_policy_switch(self):
        def is_free_stub(port):
            return False if port == 3181 else True

        with patch.object(self.ports, "is_port_free", side_effect=is_free_stub):
            with patch.object(self.ports, "find_free_port", return_value=3191):
                plan = self.ports.plan_port_policy("auto")
                self.assertIn("PHYSICS_PORT", plan["overrides"])
                self.assertIn("VITE_PHYSICS_WS", plan["overrides"])

    def test_get_port_summary(self):
        with patch.object(self.ports, "get_port_status", return_value="free"):
            summary = self.ports.get_port_summary()
            self.assertIn("3180", summary)
            self.assertIn("free", summary)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
