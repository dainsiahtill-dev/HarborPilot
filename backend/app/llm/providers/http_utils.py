from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


def normalize_base_url(raw: str, default: str = "") -> str:
    base = str(raw or default or "").strip()
    return base.rstrip("/")


def join_url(base_url: str, path: str, strip_prefixes: Optional[Iterable[str]] = None) -> str:
    if not base_url:
        return path
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    if strip_prefixes:
        normalized_base = base_url.rstrip("/")
        for prefix in strip_prefixes:
            if not prefix:
                continue
            normalized_prefix = prefix if prefix.startswith("/") else f"/{prefix}"
            if normalized_base.endswith(normalized_prefix.rstrip("/")) and path.startswith(f"{normalized_prefix}/"):
                path = path[len(normalized_prefix) :]
                break
    return base_url + path


def merge_headers(base: Optional[Dict[str, str]] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    headers: Dict[str, str] = dict(base or {})
    if isinstance(extra, dict):
        for key, value in extra.items():
            if value is None:
                continue
            headers[str(key)] = str(value)
    return headers
