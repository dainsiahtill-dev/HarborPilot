import json
import unittest
from pathlib import Path
import importlib.util


def _load_prompt_loader():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "harborpilot" / "modules" / "harborpilot-loop" / "prompt_loader.py"
    spec = importlib.util.spec_from_file_location("prompt_loader", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load prompt_loader.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REQUIRED_TEMPLATES = {
    "pm_prompt",
    "planner_prompt",
    "tool_planner_prompt",
    "patch_planner_prompt",
    "qa_prompt",
    "reviewer_prompt",
    "ollama_prompt",
}


class TestPromptTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prompt_loader = _load_prompt_loader()

    def test_profiles_have_required_templates(self):
        repo_root = Path(__file__).resolve().parents[2]
        prompts_dir = repo_root / "harborpilot" / "prompts"
        for path in [prompts_dir / "demo_ming_armada.json", prompts_dir / "generic.json"]:
            data = json.loads(path.read_text(encoding="utf-8"))
            templates = data.get("templates")
            self.assertIsInstance(templates, dict)
            for key in REQUIRED_TEMPLATES:
                self.assertIn(key, templates)
            self.assertIn("plan_template", data)

    def test_patch_planner_prompt_contains_plan_act(self):
        repo_root = Path(__file__).resolve().parents[2]
        prompts_dir = repo_root / "harborpilot" / "prompts"
        data = json.loads((prompts_dir / "demo_ming_armada.json").read_text(encoding="utf-8"))
        prompt = data["templates"]["patch_planner_prompt"]
        self.assertIn("\"plan\"", prompt)
        self.assertIn("\"act\"", prompt)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
