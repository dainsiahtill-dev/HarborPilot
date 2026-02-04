import os
from typing import Optional, List
from pydantic import BaseModel, Field

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

LOOP_PM_PATH = os.path.join(PROJECT_ROOT, "backend", "scripts", "loop-pm.py")
DIRECTOR_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "scripts", "loop-director.py")
LOOP_MODULE_DIR = os.path.join(PROJECT_ROOT, "backend", "core", "harborpilot_loop")

DEFAULT_MODEL = "modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest"
ARTIFACT_ROOT = ".harborpilot"
LEGACY_ARTIFACT_ROOT = "state"
ARTIFACT_NAMESPACE = "runtime"
LEGACY_ARTIFACT_NAMESPACE = "ollama"
DEFAULT_PLAN = ".harborpilot/runtime/PLAN.md"
DEFAULT_GAP = ".harborpilot/runtime/GAP_REPORT.md"
DEFAULT_QA = ".harborpilot/runtime/QA_RESPONSE.md"
DEFAULT_REQUIREMENTS = "docs/product/requirements.md"
DEFAULT_PM_OUT = ".harborpilot/runtime/PM_TASKS.json"
DEFAULT_PM_REPORT = ".harborpilot/runtime/PM_REPORT.md"
DEFAULT_PM_LOG = ".harborpilot/runtime/PM_LOG.jsonl"
DEFAULT_PM_SUBPROCESS_LOG = ".harborpilot/runtime/PM_SUBPROCESS.log"
DEFAULT_DIRECTOR_SUBPROCESS_LOG = ".harborpilot/runtime/DIRECTOR_SUBPROCESS.log"
DEFAULT_DIRECTOR_STATUS = ".harborpilot/runtime/DIRECTOR_STATUS.json"
DEFAULT_PLANNER = ".harborpilot/runtime/PLANNER_RESPONSE.md"
DEFAULT_OLLAMA = ".harborpilot/runtime/OLLAMA_RESPONSE.md"
DEFAULT_RUNLOG = ".harborpilot/runtime/RUNLOG.md"
DEFAULT_DIALOGUE = ".harborpilot/runtime/DIALOGUE.jsonl"
AGENTS_DRAFT_REL = ".harborpilot/runtime/AGENTS.generated.md"
AGENTS_FEEDBACK_REL = ".harborpilot/runtime/AGENTS.feedback.md"
WORKSPACE_STATUS_REL = os.path.join(ARTIFACT_ROOT, "WORKSPACE_STATUS.json")
STATE_TO_RAMDISK_ENV = "HARBORPILOT_STATE_TO_RAMDISK"

CHANNEL_FILES = {
    "pm_report": DEFAULT_PM_REPORT,
    "pm_log": DEFAULT_PM_LOG,
    "pm_subprocess": DEFAULT_PM_SUBPROCESS_LOG,
    "planner": DEFAULT_PLANNER,
    "ollama": DEFAULT_OLLAMA,
    "qa": DEFAULT_QA,
    "runlog": DEFAULT_RUNLOG,
    "dialogue": DEFAULT_DIALOGUE,
    "director_console": DEFAULT_DIRECTOR_SUBPROCESS_LOG,
}

def _default_ramdisk_root() -> str:
    value = os.environ.get("HARBORPILOT_RAMDISK_ROOT", "").strip()
    if value:
        return value
    if os.name == "nt" and os.path.exists("X:\\"):
        return "X:\\"
    return ""

def find_workspace_root(start: str) -> str:
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, "docs")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start)

DEFAULT_WORKSPACE = find_workspace_root(os.getcwd())
DEFAULT_RAMDISK_ROOT = _default_ramdisk_root()

class SettingsUpdate(BaseModel):
    workspace: Optional[str] = None
    pm_backend: Optional[str] = None
    pm_model: Optional[str] = None
    director_model: Optional[str] = None
    model: Optional[str] = None
    interval: Optional[int] = None
    timeout: Optional[int] = None
    refresh_interval: Optional[int] = None
    auto_refresh: Optional[bool] = None
    show_memory: Optional[bool] = None
    io_fsync_mode: Optional[str] = None
    memory_refs_mode: Optional[str] = None
    prompt_profile: Optional[str] = None
    ramdisk_root: Optional[str] = None
    json_log_path: Optional[str] = None
    pm_show_output: Optional[bool] = None
    pm_runs_director: Optional[bool] = None
    pm_director_show_output: Optional[bool] = None
    pm_director_timeout: Optional[int] = None
    pm_director_iterations: Optional[int] = None
    pm_director_match_mode: Optional[str] = None
    pm_max_failures: Optional[int] = None
    pm_max_blocked: Optional[int] = None
    pm_max_same: Optional[int] = None
    director_iterations: Optional[int] = None
    director_forever: Optional[bool] = None
    director_show_output: Optional[bool] = None
    qa_enabled: Optional[bool] = None
    docs_init_model: Optional[str] = None
    docs_init_provider: Optional[str] = None
    docs_init_base_url: Optional[str] = None
    docs_init_api_key: Optional[str] = None
    docs_init_api_path: Optional[str] = None
    docs_init_timeout: Optional[int] = None

class Settings(BaseModel):
    workspace: str = Field(default_factory=lambda: DEFAULT_WORKSPACE)
    pm_backend: str = "codex"
    pm_model: str = DEFAULT_MODEL
    director_model: str = DEFAULT_MODEL
    model: str = DEFAULT_MODEL
    interval: int = 20
    timeout: int = 0
    refresh_interval: int = 3
    auto_refresh: bool = True
    show_memory: bool = False
    io_fsync_mode: str = "strict"
    memory_refs_mode: str = "soft"
    prompt_profile: str = "demo_ming_armada"
    ramdisk_root: str = DEFAULT_RAMDISK_ROOT
    json_log_path: str = DEFAULT_PM_LOG
    pm_show_output: bool = True
    pm_runs_director: bool = True
    pm_director_show_output: bool = True
    pm_director_timeout: int = 600
    pm_director_iterations: int = 1
    pm_director_match_mode: str = "latest"
    pm_max_failures: int = 5
    pm_max_blocked: int = 5
    pm_max_same: int = 3
    director_iterations: int = 1
    director_forever: bool = False
    director_show_output: bool = True
    qa_enabled: bool = True
    docs_init_model: str = DEFAULT_MODEL
    docs_init_provider: str = "ollama"
    docs_init_base_url: str = ""
    docs_init_api_key: str = ""
    docs_init_api_path: str = "/v1/chat/completions"
    docs_init_timeout: int = 300

    def apply_update(self, update: SettingsUpdate) -> None:
        data = update.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(self, key, value)

class AgentsApplyPayload(BaseModel):
    draft_path: Optional[str] = None

class AgentsFeedbackPayload(BaseModel):
    text: str = ""

class DocsInitPreviewPayload(BaseModel):
    mode: str = "minimal"
    goal: str = ""
    in_scope: str = ""
    out_of_scope: str = ""
    constraints: str = ""
    definition_of_done: str = ""
    backlog: str = ""

class DocsInitSuggestPayload(BaseModel):
    goal: str = ""
    in_scope: str = ""
    out_of_scope: str = ""
    constraints: str = ""
    definition_of_done: str = ""
    backlog: str = ""

class DocsInitFile(BaseModel):
    path: str
    content: str

class DocsInitApplyPayload(BaseModel):
    mode: str = "minimal"
    target_root: str = "docs"
    files: List[DocsInitFile] = Field(default_factory=list)
