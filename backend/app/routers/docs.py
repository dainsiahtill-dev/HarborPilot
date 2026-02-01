import os
import json
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import AppState, Auth
from ..config import (
    DEFAULT_WORKSPACE, DocsInitSuggestPayload, DocsInitPreviewPayload, DocsInitApplyPayload
)
from ..utils import (
    workspace_has_docs, detect_project_profile, default_qa_commands, normalize_rel_path,
    select_docs_target_root, is_safe_docs_path, write_text_atomic, build_cache_root,
    resolve_artifact_path, clear_workspace_status, build_docs_templates
)
from ..services.ai import generate_docs_ai_fields

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.post("/docs/init/suggest", dependencies=[Depends(require_auth)])
def docs_init_suggest(request: Request, payload: DocsInitSuggestPayload) -> Dict[str, Any]:
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    fields = {
        "goal": payload.goal or "",
        "in_scope": payload.in_scope or "",
        "out_of_scope": payload.out_of_scope or "",
        "constraints": payload.constraints or "",
        "definition_of_done": payload.definition_of_done or "",
        "backlog": payload.backlog or "",
    }
    ai_fields = generate_docs_ai_fields(workspace, state.settings, fields)
    if not ai_fields:
        raise HTTPException(status_code=400, detail="LLM suggestion unavailable. Check provider/model settings.")
    return {
        "ok": True,
        "fields": {
            "goal": "\n".join(ai_fields.get("goal") or []),
            "in_scope": "\n".join(ai_fields.get("in_scope") or []),
            "out_of_scope": "\n".join(ai_fields.get("out_of_scope") or []),
            "constraints": "\n".join(ai_fields.get("constraints") or []),
            "definition_of_done": "\n".join(ai_fields.get("definition_of_done") or []),
            "backlog": "\n".join(ai_fields.get("backlog") or []),
        },
    }

@router.post("/docs/init/preview", dependencies=[Depends(require_auth)])
def docs_init_preview(request: Request, payload: DocsInitPreviewPayload) -> Dict[str, Any]:
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    mode = str(payload.mode or "minimal").strip().lower()
    if mode not in ("minimal", "import_readme", "ai"):
        mode = "minimal"
    profile = detect_project_profile(workspace)
    qa_commands = default_qa_commands(profile)
    fields = {
        "goal": payload.goal or "",
        "in_scope": payload.in_scope or "",
        "out_of_scope": payload.out_of_scope or "",
        "constraints": payload.constraints or "",
        "definition_of_done": payload.definition_of_done or "",
        "backlog": payload.backlog or "",
    }
    if mode == "ai":
        ai_fields = generate_docs_ai_fields(workspace, state.settings, fields)
        if ai_fields:
            if ai_fields.get("goal"):
                fields["goal"] = "\n".join(ai_fields.get("goal") or [])
            if ai_fields.get("in_scope"):
                fields["in_scope"] = "\n".join(ai_fields.get("in_scope") or [])
            if ai_fields.get("out_of_scope"):
                fields["out_of_scope"] = "\n".join(ai_fields.get("out_of_scope") or [])
            if ai_fields.get("constraints"):
                fields["constraints"] = "\n".join(ai_fields.get("constraints") or [])
            if ai_fields.get("definition_of_done"):
                fields["definition_of_done"] = "\n".join(ai_fields.get("definition_of_done") or [])
            if ai_fields.get("backlog"):
                fields["backlog"] = "\n".join(ai_fields.get("backlog") or [])
    docs_map = build_docs_templates(workspace, mode, fields, qa_commands)
    target_root = select_docs_target_root(workspace)
    files: List[Dict[str, Any]] = []
    for rel_path, content in docs_map.items():
        suffix = rel_path.replace("docs/", "", 1)
        target_path = target_root.rstrip("/") + "/" + suffix if target_root != "docs" else rel_path
        full_path = os.path.join(workspace, normalize_rel_path(target_path))
        files.append(
            {
                "path": target_path.replace("\\", "/"),
                "content": content,
                "exists": os.path.isfile(full_path),
            }
        )
    return {
        "ok": True,
        "mode": mode,
        "target_root": target_root,
        "docs_exists": workspace_has_docs(workspace),
        "project": profile,
        "files": files,
    }

@router.post("/docs/init/apply", dependencies=[Depends(require_auth)])
def docs_init_apply(request: Request, payload: DocsInitApplyPayload) -> Dict[str, Any]:
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    target_root = normalize_rel_path(payload.target_root or "docs")
    if not target_root or not target_root.lower().startswith("docs"):
        raise HTTPException(status_code=400, detail="target_root must be under docs/")
    files = payload.files or []
    if not files:
        raise HTTPException(status_code=400, detail="no files to write")
    created: List[str] = []
    for item in files:
        rel_path = normalize_rel_path(item.path)
        if not is_safe_docs_path(rel_path, target_root):
            raise HTTPException(status_code=400, detail=f"invalid docs path: {item.path}")
        full_path = os.path.abspath(os.path.join(workspace, rel_path))
        if os.path.commonpath([os.path.abspath(workspace), full_path]) != os.path.abspath(workspace):
            raise HTTPException(status_code=400, detail=f"path outside workspace: {item.path}")
        write_text_atomic(full_path, item.content or "")
        created.append(rel_path.replace("\\", "/"))
    # Record init event (best effort)
    try:
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        event_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/events.jsonl")
        os.makedirs(os.path.dirname(event_path), exist_ok=True)
        event_payload = {
            "schema_version": 1,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "ts_epoch": time.time(),
            "seq": 0,
            "event_id": str(uuid.uuid4()),
            "kind": "observation",
            "actor": "System",
            "name": "init_docs",
            "refs": {"run_id": f"init-{int(time.time())}"},
            "summary": "Initialized docs via onboarding wizard",
            "meta": {},
            "ok": True,
            "output": {"artifacts": created},
            "truncation": {"truncated": False},
        }
        with open(event_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event_payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    if workspace_has_docs(workspace):
        clear_workspace_status(workspace)
    return {"ok": True, "files": created}
