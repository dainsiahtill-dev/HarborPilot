import os
import json
from datetime import datetime
from typing import Dict, Any, List, Set
from ..config import (
    DEFAULT_WORKSPACE, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, LEGACY_ARTIFACT_NAMESPACE,
    LEGACY_ARTIFACT_ROOT
)
from ..utils import (
    build_cache_root, resolve_artifact_path, format_mtime, resolve_safe_path,
    normalize_artifact_rel_path, _strip_artifact_root_prefix, legacy_artifact_rel_path
)

def list_memos(workspace: str, ramdisk_root: str, limit: int = 200) -> Dict[str, Any]:
    workspace = workspace or DEFAULT_WORKSPACE
    cache_root = build_cache_root(ramdisk_root or "", workspace)
    rel_root = os.path.join(ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "memos")
    memos_dir = resolve_artifact_path(workspace, cache_root, rel_root)
    index_path = resolve_artifact_path(workspace, cache_root, os.path.join(rel_root, "index.jsonl"))

    memos_dirs: List[str] = []
    index_paths: List[str] = []

    def _add_path(target: str, container: List[str]) -> None:
        if target and target not in container:
            container.append(target)

    _add_path(memos_dir, memos_dirs)
    _add_path(index_path, index_paths)

    workspace_root = os.path.abspath(workspace)
    cache_root_abs = os.path.abspath(cache_root) if cache_root else ""

    if workspace_root:
        _add_path(os.path.join(workspace_root, rel_root), memos_dirs)
        _add_path(os.path.join(workspace_root, rel_root, "index.jsonl"), index_paths)
        _add_path(os.path.join(workspace_root, ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "memos"), memos_dirs)
        _add_path(os.path.join(workspace_root, ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "memos", "index.jsonl"), index_paths)
        _add_path(os.path.join(workspace_root, LEGACY_ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "memos"), memos_dirs)
        _add_path(os.path.join(workspace_root, LEGACY_ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "memos", "index.jsonl"), index_paths)

    if cache_root_abs:
        _add_path(os.path.join(cache_root_abs, ARTIFACT_NAMESPACE, "memos"), memos_dirs)
        _add_path(os.path.join(cache_root_abs, ARTIFACT_NAMESPACE, "memos", "index.jsonl"), index_paths)
        _add_path(os.path.join(cache_root_abs, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "memos"), memos_dirs)
        _add_path(os.path.join(cache_root_abs, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "memos", "index.jsonl"), index_paths)
        _add_path(os.path.join(cache_root_abs, ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "memos"), memos_dirs)
        _add_path(os.path.join(cache_root_abs, ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "memos", "index.jsonl"), index_paths)
        _add_path(os.path.join(cache_root_abs, LEGACY_ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "memos"), memos_dirs)
        _add_path(os.path.join(cache_root_abs, LEGACY_ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "memos", "index.jsonl"), index_paths)

    records: List[Dict[str, Any]] = []
    seen_keys: Set[str] = set()

    def _record_key(record: Dict[str, Any]) -> str:
        rel = str(record.get("rel_path") or record.get("path") or "").strip()
        if rel:
            return rel
        stamp = str(record.get("timestamp") or "")
        task_id = str(record.get("task_id") or "")
        return f"{stamp}:{task_id}"

    for candidate in index_paths:
        if not candidate or not os.path.isfile(candidate):
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(record, dict):
                        continue
                    key = _record_key(record)
                    if key and key in seen_keys:
                        continue
                    if key:
                        seen_keys.add(key)
                    records.append(record)
        except Exception:
            continue

    def _rel_path_for_entry(entry_path: str) -> str:
        full = os.path.abspath(entry_path)
        if cache_root_abs and full.startswith(cache_root_abs):
            rel = os.path.relpath(full, cache_root_abs).replace("\\", "/")
            if not rel.startswith(f"{ARTIFACT_ROOT}/"):
                return f"{ARTIFACT_ROOT}/" + rel
            return rel
        if workspace_root and full.startswith(workspace_root):
            return os.path.relpath(full, workspace_root).replace("\\", "/")
        return ""

    if not records:
        for candidate in memos_dirs:
            if not candidate or not os.path.isdir(candidate):
                continue
            try:
                for entry in os.scandir(candidate):
                    if not entry.is_file():
                        continue
                    if not entry.name.lower().endswith(".md"):
                        continue
                    if entry.name.lower().startswith("pm_memo_summary"):
                        continue
                    rel_path = _rel_path_for_entry(entry.path)
                    if not rel_path:
                        continue
                    key = rel_path
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    records.append(
                        {
                            "timestamp": format_mtime(entry.path),
                            "rel_path": rel_path,
                            "task_id": "",
                            "task_title": "",
                            "summary": "",
                        }
                    )
            except Exception:
                continue

    def _resolve_memo_path(rel_path: str) -> str:
        if not rel_path:
            return ""
        try:
            return resolve_safe_path(workspace, cache_root, rel_path)
        except Exception:
            normalized = normalize_artifact_rel_path(rel_path)
            candidates: List[str] = []
            if cache_root_abs:
                candidates.append(os.path.join(cache_root_abs, _strip_artifact_root_prefix(normalized)))
                candidates.append(os.path.join(cache_root_abs, normalized))
            if workspace_root:
                candidates.append(os.path.join(workspace_root, normalized))
            legacy_rel = legacy_artifact_rel_path(normalized)
            if legacy_rel:
                if cache_root_abs:
                    candidates.append(os.path.join(cache_root_abs, _strip_artifact_root_prefix(legacy_rel)))
                    candidates.append(os.path.join(cache_root_abs, legacy_rel))
                if workspace_root:
                    candidates.append(os.path.join(workspace_root, legacy_rel))
            for candidate in candidates:
                if candidate and os.path.isfile(candidate):
                    return candidate
        return ""

    def _record_ts(item: Dict[str, Any]) -> float:
        raw = str(item.get("timestamp") or "")
        try:
            return datetime.fromisoformat(raw).timestamp()
        except Exception:
            return 0.0

    records.sort(key=_record_ts, reverse=True)
    trimmed = records[: max(1, limit)]
    items: List[Dict[str, Any]] = []
    for record in trimmed:
        rel_path = str(record.get("rel_path") or "")
        full_path = _resolve_memo_path(rel_path)
        item_path = full_path or rel_path
        items.append(
            {
                "name": os.path.basename(rel_path) if rel_path else os.path.basename(full_path),
                "path": item_path,
                "mtime": format_mtime(full_path) if full_path else "",
                "summary": record.get("summary") or "",
                "task_id": record.get("task_id") or "",
                "task_title": record.get("task_title") or "",
                "status": record.get("status") or "",
                "acceptance": record.get("acceptance"),
                "run_id": record.get("run_id") or "",
                "director_attempt": record.get("director_attempt") or None,
            }
        )
    return {"items": items, "count": len(items)}
