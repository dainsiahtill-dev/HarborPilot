import os
import json
import datetime
import time
from datetime import timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from ..config import WORKSPACE_STATUS_REL
from ..utils import (
    workspace_status_path, read_readme_title, _split_items, _format_list, normalize_rel_path,
    write_text_atomic
)

def workspace_has_docs(workspace: str) -> bool:
    if not workspace:
        return False
    return os.path.isdir(os.path.join(workspace, "docs"))

def read_workspace_status(workspace: str) -> Optional[Dict[str, Any]]:
    path = workspace_status_path(workspace)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except Exception:
        return None

def write_workspace_status(
    workspace: str,
    *,
    status: str,
    reason: str,
    actions: Optional[List[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if not workspace:
        return
    payload: Dict[str, Any] = {
        "status": status,
        "reason": reason,
        "actions": actions or [],
        "workspace_path": os.path.abspath(workspace),
        "timestamp": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if isinstance(extra, dict):
        payload.update(extra)
    try:
        os.makedirs(os.path.dirname(workspace_status_path(workspace)), exist_ok=True)
        with open(workspace_status_path(workspace), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception:
        pass

def clear_workspace_status(workspace: str) -> None:
    path = workspace_status_path(workspace)
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def ensure_docs_ready_or_raise(workspace: str) -> None:
    if workspace_has_docs(workspace):
        clear_workspace_status(workspace)
        return
    write_workspace_status(
        workspace,
        status="NEEDS_DOCS_INIT",
        reason="docs/ directory not found",
        actions=["INIT_DOCS_WIZARD"],
    )
    raise HTTPException(status_code=409, detail="workspace missing docs/. Run docs init first.")

def is_safe_docs_path(rel_path: str, target_root: str) -> bool:
    norm = normalize_rel_path(rel_path)
    if not norm or norm == "." or norm.startswith(".."):
        return False
    if not norm.lower().startswith("docs/") and norm.lower() != "docs":
        return False
    target_norm = normalize_rel_path(target_root)
    if target_norm and target_norm != "docs" and not norm.lower().startswith(target_norm.lower().rstrip("/") + "/"):
        return False
    return True

def select_docs_target_root(workspace: str) -> str:
    docs_dir = os.path.join(workspace, "docs")
    if os.path.isdir(docs_dir):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        return os.path.join("docs", "_drafts", f"init-{stamp}").replace("\\", "/")
    return "docs"

def build_docs_templates(
    workspace: str,
    mode: str,
    fields: Dict[str, str],
    qa_commands: List[str],
) -> Dict[str, str]:
    goal = fields.get("goal") or ""
    if mode == "import_readme" and not goal:
        goal = read_readme_title(workspace)
    goal_text = goal.strip() or "TBD"
    in_scope_items = _split_items(fields.get("in_scope") or "")
    out_scope_items = _split_items(fields.get("out_of_scope") or "")
    constraints_items = _split_items(fields.get("constraints") or "")
    dod_items = _split_items(fields.get("definition_of_done") or "")
    backlog_items = _split_items(fields.get("backlog") or "")
    readme_note = ""
    if mode == "import_readme":
        readme_note = "\n## README Reference\n- See README.md for additional context.\n"
    docs: Dict[str, str] = {}
    docs["docs/00_overview.md"] = (
        "# Overview\n\n"
        "## Goal\n"
        f"{goal_text}\n\n"
        "## In Scope\n"
        f"{_format_list(in_scope_items)}\n\n"
        "## Out of Scope\n"
        f"{_format_list(out_scope_items)}\n"
        f"{readme_note}"
    )
    docs["docs/10_requirements.md"] = (
        "# Requirements\n\n"
        "## Key Requirements\n"
        f"{_format_list(in_scope_items)}\n\n"
        "## Acceptance Criteria\n"
        f"{_format_list(dod_items)}\n"
    )
    docs["docs/20_constraints.md"] = "# Constraints\n\n" + _format_list(constraints_items) + "\n"
    docs["docs/30_backlog.md"] = "# Backlog\n\n" + _format_list(backlog_items) + "\n"
    docs["docs/40_quality.md"] = (
        "# Quality\n\n"
        "## Definition of Done\n"
        f"{_format_list(dod_items)}\n\n"
        "## Default QA Commands\n"
        f"{_format_list(qa_commands)}\n"
    )
    metadata = {
        "schema_version": 1,
        "created_at": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "docs_mode": mode,
        "requirements_path": "docs/10_requirements.md",
    }
    docs["docs/.harborpilot.json"] = json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    return docs
