import json
import os
import re
from functools import lru_cache
from typing import Dict, Optional

PROFILE_ENV = "HARBORPILOT_PROMPT_PROFILE"
DEFAULT_PROFILE = "demo_ming_armada"


def _templates_dir() -> str:
    module_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(module_dir, "..", ".."))
    return os.path.join(project_root, "prompts")


def current_profile() -> str:
    value = os.environ.get(PROFILE_ENV, DEFAULT_PROFILE).strip()
    return value or DEFAULT_PROFILE


@lru_cache(maxsize=8)
def load_profile(profile: Optional[str] = None) -> Dict[str, object]:
    profile_name = (profile or current_profile()).strip()
    templates_dir = _templates_dir()
    candidate = os.path.join(templates_dir, f"{profile_name}.json")
    if not os.path.isfile(candidate):
        fallback = os.path.join(templates_dir, f"{DEFAULT_PROFILE}.json")
        if os.path.isfile(fallback):
            candidate = fallback
    with open(candidate, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_template(name: str, profile: Optional[str] = None) -> str:
    profile_name = (profile or current_profile()).strip()
    data = load_profile(profile_name)
    if name == "plan_template":
        template = data.get("plan_template")
        if isinstance(template, str):
            return template
    templates = data.get("templates")
    if isinstance(templates, dict):
        template = templates.get(name)
        if isinstance(template, str):
            return template
    raise KeyError(f"Prompt template not found: {name}")


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render_template(template: str, values: Dict[str, object]) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        value = values.get(key, "")
        return "" if value is None else str(value)

    return _PLACEHOLDER_RE.sub(replace, template)
