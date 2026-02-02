from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

from io_utils import (
    build_cache_root,
    emit_event,
    read_file_safe,
    resolve_artifact_path,
    resolve_ramdisk_root,
    resolve_run_dir,
    write_text_atomic,
)
from anthropomorphic.memory_store import MemoryStore, _has_refs
from repo_map import build_repo_map


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_text(text: str) -> str:
    hasher = hashlib.sha1()
    hasher.update((text or "").encode("utf-8", errors="ignore"))
    return hasher.hexdigest()


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "{}"


def _read_tail_lines(path: str, max_lines: int = 200) -> List[str]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            pos = handle.tell()
            block = 4096
            data = b""
            while pos > 0 and data.count(b"\n") <= max_lines:
                read_size = block if pos >= block else pos
                pos -= read_size
                handle.seek(pos)
                data = handle.read(read_size) + data
    except Exception:
        return []
    text = data.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    if max_lines > 0 and len(lines) > max_lines:
        return lines[-max_lines:]
    return lines


def _read_slice_spec(path: str, spec: Dict[str, Any]) -> Tuple[str, List[int], str]:
    content = read_file_safe(path)
    if not content:
        return "", [0, 0], ""
    file_hash = _hash_text(content)
    lines = content.splitlines()
    start_line = 1
    end_line = len(lines)
    around = spec.get("around")
    radius = spec.get("radius")
    if isinstance(around, int):
        rad = int(radius or 80)
        start_line = max(1, around - rad)
        end_line = min(len(lines), around + rad)
    else:
        start_line = int(spec.get("start_line") or spec.get("line_start") or 1)
        end_line = int(spec.get("end_line") or spec.get("line_end") or len(lines))
        start_line = max(1, start_line)
        end_line = min(len(lines), end_line)
    sliced = lines[start_line - 1 : end_line]
    return "\n".join(sliced), [start_line, end_line], file_hash


class ContextBudget(BaseModel):
    max_tokens: int = 0
    max_chars: int = 0
    cost_class: str = "LOCAL"


class ContextRequest(BaseModel):
    run_id: str
    step: int
    role: str
    mode: str
    task_id: Optional[str] = None
    query: str
    budget: ContextBudget
    sources_enabled: List[str] = Field(default_factory=list)
    policy: Dict[str, Any] = Field(default_factory=dict)
    events_path: Optional[str] = None


class ContextItem(BaseModel):
    id: str = Field(default_factory=lambda: f"ctx_{uuid4()}")
    kind: str
    content_or_pointer: str
    refs: Dict[str, Any] = Field(default_factory=dict)
    size_est: int = 0
    priority: int = 5
    reason: str = ""
    provider: str = ""


class ContextPack(BaseModel):
    request_hash: str
    items: List[ContextItem] = Field(default_factory=list)
    compression_log: List[Dict[str, Any]] = Field(default_factory=list)
    rendered_prompt: str = ""
    rendered_messages: List[Dict[str, Any]] = Field(default_factory=list)
    total_tokens: int = 0
    total_chars: int = 0
    build_timestamp: datetime = Field(default_factory=_utc_now)
    snapshot_path: str = ""
    snapshot_hash: str = ""


class ContextCache:
    def __init__(self) -> None:
        self._pack_cache: Dict[str, ContextPack] = {}

    def get_cached_pack(self, request_hash: str) -> Optional[ContextPack]:
        return self._pack_cache.get(request_hash)

    def cache_pack(self, pack: ContextPack) -> None:
        if pack and pack.request_hash:
            self._pack_cache[pack.request_hash] = pack


class BaseProvider(ABC):
    name: str = "base"

    def __init__(self, project_root: str) -> None:
        self.project_root = project_root

    @abstractmethod
    def collect_items(self, request: ContextRequest) -> List[ContextItem]:
        raise NotImplementedError

    def estimate_size(self, item: ContextItem) -> int:
        return _estimate_tokens(item.content_or_pointer)


class DocsProvider(BaseProvider):
    name = "docs"

    def collect_items(self, request: ContextRequest) -> List[ContextItem]:
        policy = request.policy or {}
        paths = policy.get("docs_paths") or [
            "docs/agent/README.md",
            "docs/product/requirements.md",
            "docs/product/product_spec.md",
            "docs/agent/architecture.md",
            "docs/agent/invariants.md",
        ]
        max_chars = int(policy.get("docs_max_chars", 2000) or 2000)
        items: List[ContextItem] = []
        for rel_path in paths:
            full_path = os.path.join(self.project_root, rel_path)
            if not os.path.exists(full_path):
                continue
            raw = read_file_safe(full_path)
            if not raw:
                continue
            content = raw[:max_chars] if max_chars > 0 else raw
            refs = {
                "path": rel_path,
                "file_hash": _hash_text(raw),
                "char_range": [0, len(content)],
            }
            item = ContextItem(
                kind="docs",
                content_or_pointer=content,
                refs=refs,
                size_est=_estimate_tokens(content),
                priority=int(policy.get("docs_priority", 7) or 7),
                reason=f"Core docs: {os.path.basename(rel_path)}",
                provider=self.name,
            )
            items.append(item)
        return items


class ContractProvider(BaseProvider):
    name = "contract"

    def collect_items(self, request: ContextRequest) -> List[ContextItem]:
        policy = request.policy or {}
        paths = policy.get("contract_paths") or [
            ".harborpilot/runtime/PM_TASKS.json",
            ".harborpilot/runtime/PLAN.md",
        ]
        max_chars = int(policy.get("contract_max_chars", 4000) or 4000)
        cache_root = build_cache_root(resolve_ramdisk_root(None), self.project_root)
        items: List[ContextItem] = []
        for rel_path in paths:
            try:
                full_path = resolve_artifact_path(
                    self.project_root,
                    cache_root,
                    rel_path,
                    run_id=request.run_id,
                )
            except Exception:
                full_path = os.path.join(self.project_root, rel_path)
            if not os.path.exists(full_path):
                continue
            raw = read_file_safe(full_path)
            if not raw:
                continue
            content = raw[:max_chars] if max_chars > 0 else raw
            refs = {
                "path": rel_path,
                "file_hash": _hash_text(raw),
                "char_range": [0, len(content)],
            }
            item = ContextItem(
                kind="contract",
                content_or_pointer=content,
                refs=refs,
                size_est=_estimate_tokens(content),
                priority=int(policy.get("contract_priority", 9) or 9),
                reason=f"Contract input: {os.path.basename(rel_path)}",
                provider=self.name,
            )
            items.append(item)
        return items


class MemoryProvider(BaseProvider):
    name = "memory"

    def __init__(self, project_root: str) -> None:
        super().__init__(project_root)
        memory_path = os.path.join(project_root, ".harborpilot", "brain", "MEMORY.jsonl")
        self.store = MemoryStore(memory_path)

    def collect_items(self, request: ContextRequest) -> List[ContextItem]:
        policy = request.policy or {}
        top_k = int(policy.get("memory_top_k", 5) or 5)
        max_chars = int(policy.get("memory_max_chars", 400) or 400)
        if not request.query or top_k <= 0:
            return []
        results = self.store.retrieve(request.query, request.step, top_k=top_k, return_scores=True)
        items: List[ContextItem] = []
        for mem, score in results:
            has_refs = _has_refs(mem.context)
            if not has_refs and policy.get("memory_refs_required", False):
                continue
            text = mem.text or ""
            content = text[:max_chars] if max_chars > 0 else text
            refs = dict(mem.context or {})
            refs.update({"mem_id": mem.id, "source_event_id": mem.source_event_id})
            if not has_refs:
                refs["refs_missing"] = True
            reason = f"Retrieved memory (score={score:.3f})"
            kind = "memory" if has_refs else "note"
            priority = int(policy.get("memory_priority", 4) or 4)
            if not has_refs:
                priority = min(priority, 1)
                reason = reason + "; missing refs (downgraded)"
            items.append(
                ContextItem(
                    kind=kind,
                    content_or_pointer=content,
                    refs=refs,
                    size_est=_estimate_tokens(content),
                    priority=priority,
                    reason=reason,
                    provider=self.name,
                )
            )
        return items


class EventsProvider(BaseProvider):
    name = "events"

    def collect_items(self, request: ContextRequest) -> List[ContextItem]:
        events_path = request.events_path or ""
        if not events_path or not os.path.exists(events_path):
            return []
        policy = request.policy or {}
        tail_lines = int(policy.get("events_tail_lines", 120) or 120)
        max_chars = int(policy.get("events_max_chars", 2000) or 2000)
        lines = _read_tail_lines(events_path, tail_lines)
        if not lines:
            return []
        content = "\n".join(lines)
        if max_chars > 0 and len(content) > max_chars:
            content = content[-max_chars:]
        refs = {"path": events_path, "tail_lines": tail_lines}
        item = ContextItem(
            kind="events",
            content_or_pointer=content,
            refs=refs,
            size_est=_estimate_tokens(content),
            priority=int(policy.get("events_priority", 6) or 6),
            reason="Recent events tail",
            provider=self.name,
        )
        return [item]


class RepoEvidenceProvider(BaseProvider):
    name = "repo_evidence"

    def collect_items(self, request: ContextRequest) -> List[ContextItem]:
        policy = request.policy or {}
        evidence_specs = policy.get("repo_evidence") or []
        max_chars = int(policy.get("repo_evidence_max_chars", 1200) or 1200)
        items: List[ContextItem] = []
        if not isinstance(evidence_specs, list):
            return items
        for spec in evidence_specs:
            if not isinstance(spec, dict):
                continue
            rel_path = str(spec.get("path") or "").strip()
            if not rel_path:
                continue
            full_path = os.path.join(self.project_root, rel_path)
            if not os.path.exists(full_path):
                continue
            content, line_range, file_hash = _read_slice_spec(full_path, spec)
            if not content:
                continue
            if max_chars > 0 and len(content) > max_chars:
                content = content[:max_chars] + "...[truncated]"
            refs = {
                "path": rel_path,
                "line_range": line_range,
                "file_hash": file_hash,
            }
            reason = str(spec.get("reason") or "Repo evidence slice").strip()
            items.append(
                ContextItem(
                    kind="evidence",
                    content_or_pointer=content,
                    refs=refs,
                    size_est=_estimate_tokens(content),
                    priority=int(spec.get("priority", 8) or 8),
                    reason=reason,
                    provider=self.name,
                )
            )
        return items


class RepoMapProvider(BaseProvider):
    name = "repo_map"

    def collect_items(self, request: ContextRequest) -> List[ContextItem]:
        policy = request.policy or {}
        languages = policy.get("repo_map_languages")
        if isinstance(languages, str):
            languages = [part.strip() for part in languages.split(",") if part.strip()]
        max_files = int(policy.get("repo_map_max_files", 200) or 200)
        max_lines = int(policy.get("repo_map_max_lines", 200) or 200)
        per_file_lines = int(policy.get("repo_map_per_file_lines", 12) or 12)
        include_glob = policy.get("repo_map_include")
        exclude_glob = policy.get("repo_map_exclude")
        max_chars = int(policy.get("repo_map_max_chars", 0) or 0)
        repo_map = build_repo_map(
            self.project_root,
            languages=languages if isinstance(languages, list) else None,
            max_files=max_files,
            max_lines=max_lines,
            per_file_lines=per_file_lines,
            include_glob=include_glob if isinstance(include_glob, str) else None,
            exclude_glob=exclude_glob if isinstance(exclude_glob, str) else None,
        )
        text = repo_map.get("text") or ""
        if not text:
            return []
        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars] + "...[truncated]"
        refs = dict(repo_map.get("stats") or {})
        refs.update(
            {
                "path": "<repo_map>",
                "languages": repo_map.get("languages"),
                "truncated": repo_map.get("truncated", False),
            }
        )
        item = ContextItem(
            kind="repo_map",
            content_or_pointer=text,
            refs=refs,
            size_est=_estimate_tokens(text),
            priority=int(policy.get("repo_map_priority", 8) or 8),
            reason="Repository skeleton map",
            provider=self.name,
        )
        return [item]


class ContextEngine:
    def __init__(self, project_root: str, *, cache: Optional[ContextCache] = None) -> None:
        self.project_root = project_root
        self.cache = cache or ContextCache()
        self.providers: Dict[str, BaseProvider] = {
            DocsProvider.name: DocsProvider(project_root),
            ContractProvider.name: ContractProvider(project_root),
            MemoryProvider.name: MemoryProvider(project_root),
            EventsProvider.name: EventsProvider(project_root),
            RepoEvidenceProvider.name: RepoEvidenceProvider(project_root),
            RepoMapProvider.name: RepoMapProvider(project_root),
        }

    def build_context(self, request: ContextRequest) -> ContextPack:
        request_hash = self._hash_request(request)
        cached = self.cache.get_cached_pack(request_hash)
        if cached:
            return cached

        enabled = set(request.sources_enabled or self.providers.keys())
        items: List[ContextItem] = []
        for name, provider in self.providers.items():
            if name not in enabled:
                continue
            items.extend(provider.collect_items(request))

        items = self._apply_role_strategy(items, request)
        items = self._fill_item_sizes(items)
        items, compression_log = self._apply_budget_ladder(items, request.budget)

        rendered_prompt = self._render_prompt(items, request)
        rendered_messages = [{"role": "user", "content": rendered_prompt}]
        total_chars = len(rendered_prompt)
        total_tokens = _estimate_tokens(rendered_prompt)

        pack = ContextPack(
            request_hash=request_hash,
            items=items,
            compression_log=compression_log,
            rendered_prompt=rendered_prompt,
            rendered_messages=rendered_messages,
            total_tokens=total_tokens,
            total_chars=total_chars,
            build_timestamp=_utc_now(),
        )

        snapshot_path, snapshot_hash = self._maybe_snapshot(pack, request)
        if snapshot_path:
            pack.snapshot_path = snapshot_path
        if snapshot_hash:
            pack.snapshot_hash = snapshot_hash

        self.cache.cache_pack(pack)
        self._emit_context_events(pack, request)
        return pack

    def _hash_request(self, request: ContextRequest) -> str:
        payload = request.model_dump()
        payload["budget"] = request.budget.model_dump()
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return _hash_text(raw)

    def _apply_role_strategy(self, items: List[ContextItem], request: ContextRequest) -> List[ContextItem]:
        policy = request.policy or {}
        max_items = int(policy.get("max_items", 0) or 0)
        forbidden = set(policy.get("forbidden_providers", []) or [])
        required = set(policy.get("required_providers", []) or [])
        memory_limit = int(policy.get("memory_limit", 0) or 0)

        filtered = [item for item in items if item.provider not in forbidden]
        if required:
            for provider in required:
                if not any(item.provider == provider for item in filtered):
                    pass

        if memory_limit > 0:
            memory_items = [i for i in filtered if i.provider == "memory"]
            non_memory = [i for i in filtered if i.provider != "memory"]
            memory_items = memory_items[:memory_limit]
            filtered = non_memory + memory_items

        if max_items > 0 and len(filtered) > max_items:
            filtered.sort(key=lambda i: i.priority, reverse=True)
            filtered = filtered[:max_items]
        return filtered

    def _fill_item_sizes(self, items: List[ContextItem]) -> List[ContextItem]:
        for item in items:
            if not item.size_est:
                item.size_est = _estimate_tokens(item.content_or_pointer)
        return items

    def _apply_budget_ladder(
        self, items: List[ContextItem], budget: ContextBudget
    ) -> Tuple[List[ContextItem], List[Dict[str, Any]]]:
        compression_log: List[Dict[str, Any]] = []

        deduped = self._deduplicate(items)
        if len(deduped) < len(items):
            compression_log.append({"action": "deduplicate", "removed": len(items) - len(deduped)})
        items = deduped

        if self._over_budget(items, budget):
            items = self._trim_items(items)
            compression_log.append({"action": "trim_items"})

        if self._over_budget(items, budget):
            items = self._pointerize_items(items)
            compression_log.append({"action": "pointerize"})

        if self._over_budget(items, budget):
            items = self._summarize_items(items)
            compression_log.append({"action": "summarize", "method": "heuristic"})

        if self._over_budget(items, budget):
            items = self._drop_low_priority(items, budget)
            compression_log.append({"action": "drop_low_priority", "remaining": len(items)})

        return items, compression_log

    def _over_budget(self, items: List[ContextItem], budget: ContextBudget) -> bool:
        if not budget:
            return False
        token_limit = int(budget.max_tokens or 0)
        char_limit = int(budget.max_chars or 0)
        tokens = sum(item.size_est for item in items)
        chars = sum(len(item.content_or_pointer or "") for item in items)
        if token_limit > 0 and tokens > token_limit:
            return True
        if char_limit > 0 and chars > char_limit:
            return True
        return False

    def _deduplicate(self, items: List[ContextItem]) -> List[ContextItem]:
        seen: Dict[str, ContextItem] = {}
        for item in items:
            key = self._source_key(item)
            if not key:
                key = item.id
            existing = seen.get(key)
            if not existing or item.priority > existing.priority:
                seen[key] = item
        return list(seen.values())

    def _source_key(self, item: ContextItem) -> str:
        refs = item.refs or {}
        for key in ("path", "file_path", "artifact_path"):
            value = refs.get(key)
            if value:
                return str(value)
        return ""

    def _trim_items(self, items: List[ContextItem], max_chars: int = 600) -> List[ContextItem]:
        trimmed: List[ContextItem] = []
        for item in items:
            content = item.content_or_pointer or ""
            if len(content) > max_chars:
                item.content_or_pointer = content[:max_chars] + "...[trimmed]"
                item.size_est = _estimate_tokens(item.content_or_pointer)
            trimmed.append(item)
        return trimmed

    def _pointerize_items(self, items: List[ContextItem]) -> List[ContextItem]:
        pointerized: List[ContextItem] = []
        for item in items:
            refs = item.refs or {}
            path = refs.get("path") or refs.get("file_path") or refs.get("artifact_path")
            if path:
                pointer = f"[See {path}]"
                item.content_or_pointer = pointer
                item.size_est = _estimate_tokens(pointer)
                item.kind = "pointer"
            pointerized.append(item)
        return pointerized

    def _summarize_items(self, items: List[ContextItem], head_chars: int = 200, tail_chars: int = 200) -> List[ContextItem]:
        summarized: List[ContextItem] = []
        for item in items:
            content = item.content_or_pointer or ""
            if len(content) > head_chars + tail_chars + 16:
                summary = content[:head_chars] + "...[snip]..." + content[-tail_chars:]
                item.content_or_pointer = summary
                item.size_est = _estimate_tokens(summary)
            summarized.append(item)
        return summarized

    def _drop_low_priority(self, items: List[ContextItem], budget: ContextBudget) -> List[ContextItem]:
        if not items:
            return items
        sorted_items = sorted(items, key=lambda i: i.priority, reverse=True)
        kept: List[ContextItem] = []
        for item in sorted_items:
            kept.append(item)
            if not self._over_budget(kept, budget):
                continue
        while self._over_budget(kept, budget) and kept:
            kept.pop()
        return kept

    def _render_prompt(self, items: List[ContextItem], request: ContextRequest) -> str:
        lines = [
            "# Context Pack",
            f"- run_id: {request.run_id}",
            f"- step: {request.step}",
            f"- role: {request.role}",
            f"- mode: {request.mode}",
        ]
        for item in items:
            lines.append("")
            lines.append(f"## {item.kind.upper()} ({item.provider})")
            if item.reason:
                lines.append(f"Reason: {item.reason}")
            if item.refs:
                lines.append(f"Refs: {_safe_json(item.refs)}")
            lines.append(item.content_or_pointer or "")
        return "\n".join(lines).strip() + "\n"

    def _emit_context_events(self, pack: ContextPack, request: ContextRequest) -> None:
        if not request.events_path:
            return
        refs = {"run_id": request.run_id, "step": request.step, "phase": request.mode, "task_id": request.task_id}
        emit_event(
            request.events_path,
            kind="observation",
            actor="System",
            name="context.build",
            refs=refs,
            summary=f"ContextPack built ({len(pack.items)} items)",
            output={
                "request_hash": pack.request_hash,
                "items_count": len(pack.items),
                "providers_used": sorted({i.provider for i in pack.items}),
                "total_tokens": pack.total_tokens,
                "total_chars": pack.total_chars,
                "snapshot_path": pack.snapshot_path,
                "snapshot_hash": pack.snapshot_hash,
                "compression_log": pack.compression_log,
            },
        )
        if pack.snapshot_path:
            emit_event(
                request.events_path,
                kind="observation",
                actor="System",
                name="context.snapshot",
                refs=refs,
                summary="Context snapshot stored",
                output={
                    "request_hash": pack.request_hash,
                    "snapshot_path": pack.snapshot_path,
                    "snapshot_hash": pack.snapshot_hash,
                },
            )
        for item in pack.items:
            emit_event(
                request.events_path,
                kind="observation",
                actor="System",
                name="context.item",
                refs=refs,
                summary=f"{item.kind}:{item.id}",
                output={
                    "item_id": item.id,
                    "kind": item.kind,
                    "provider": item.provider,
                    "size_est": item.size_est,
                    "priority": item.priority,
                    "reason": item.reason,
                    "refs": item.refs,
                },
            )

    def _maybe_snapshot(self, pack: ContextPack, request: ContextRequest) -> Tuple[str, str]:
        policy = request.policy or {}
        enabled = policy.get("snapshot_context")
        if enabled is None:
            enabled = str(os.environ.get("HARBORPILOT_CONTEXT_SNAPSHOT", "1")).strip().lower() not in (
                "0",
                "false",
                "no",
                "off",
            )
        if not enabled:
            return "", ""
        if not request.run_id:
            return "", ""
        cache_root = build_cache_root(resolve_ramdisk_root(None), self.project_root) or ""
        run_dir = resolve_run_dir(self.project_root, cache_root, request.run_id)
        evidence_dir = os.path.join(run_dir, "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        snapshot_name = f"context_snapshot_{pack.request_hash[:8]}.json"
        snapshot_path = os.path.join(evidence_dir, snapshot_name)
        snapshot_payload = {
            "request": request.model_dump(),
            "pack": pack.model_dump(),
            "snapshot_path": snapshot_path,
        }
        text = json.dumps(snapshot_payload, ensure_ascii=False, indent=2, default=str)
        write_text_atomic(snapshot_path, text + "\n")
        return snapshot_path, _hash_text(text)
