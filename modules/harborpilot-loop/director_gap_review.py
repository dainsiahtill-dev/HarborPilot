import os
from typing import Any, Dict, List

from io_utils import ensure_parent_dir, read_file_safe, write_text_atomic
from ollama_utils import invoke_ollama
from shared import strip_ansi
import json


def _append_log(log_path: str, text: str) -> None:
    if not log_path:
        return
    ensure_parent_dir(log_path)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(text)


def _write_text(path: str, text: str) -> None:
    write_text_atomic(path, text or "")


def extract_headings(text: str, max_count: int) -> List[str]:
    if not text or max_count <= 0:
        return []
    headings: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append(stripped)
            if len(headings) >= max_count:
                break
    return headings


def collect_doc_files(workspace: str) -> List[str]:
    targets: List[str] = []
    core_spec = os.path.join(workspace, "MMO_CORE_SPEC.md")
    if os.path.isfile(core_spec):
        targets.append(core_spec)
    docs_root = os.path.join(workspace, "docs")
    if os.path.isdir(docs_root):
        for root, _, files in os.walk(docs_root):
            for name in files:
                if name.endswith(".md"):
                    targets.append(os.path.join(root, name))
    return sorted(set(targets))


def build_doc_outline(workspace: str, max_headings: int) -> str:
    headings_left = max_headings
    blocks: List[str] = []
    for path in collect_doc_files(workspace):
        if headings_left <= 0:
            break
        rel = os.path.relpath(path, workspace)
        text = read_file_safe(path)
        headings = extract_headings(text, headings_left)
        if not headings:
            continue
        blocks.append(f"FILE: {rel}")
        blocks.extend(headings)
        blocks.append("")
        headings_left -= len(headings)
    return "\n".join(blocks).strip()


def build_repo_index(workspace: str, max_files: int) -> str:
    roots = [
        os.path.join(workspace, "apps", "server", "src"),
        os.path.join(workspace, "apps", "game-client", "src"),
        os.path.join(workspace, "apps", "physics-lab", "src"),
        os.path.join(workspace, "packages", "realtime-client", "src"),
        os.path.join(workspace, "packages", "physics-core", "src"),
        os.path.join(workspace, "packages", "shared", "src"),
    ]
    allowed_ext = (".ts", ".tsx", ".js", ".mjs", ".svelte")
    files: List[str] = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                if not name.endswith(allowed_ext):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, workspace)
                files.append(rel)
                if len(files) >= max_files:
                    break
            if len(files) >= max_files:
                break
        if len(files) >= max_files:
            break
    return "\n".join(files)


def build_gap_review_prompt(doc_outline: str, repo_index: str) -> str:
    return f"""You are a product gap analyst for a game repo.
Compare the documentation outline with the code inventory.
Identify likely missing or not-yet-implemented features.
Be conservative: if uncertain, mark confidence as low.
Output a single JSON object (no markdown, no code fences).

Required JSON keys:
- \"missing\": array of objects {{ \"feature\": string, \"evidence\": string, \"confidence\": \"low|med|high\" }}
- \"notes\": short guidance or caveats

Documentation outline:
{doc_outline}

Code inventory (paths):
{repo_index}
"""


def run_gap_review(state: Any, log_path: str) -> str:
    outline = build_doc_outline(state.workspace_full, state.gap_max_headings)
    repo_index = build_repo_index(state.workspace_full, state.gap_max_files)
    if not outline:
        _append_log(log_path, "[WARN] Gap review skipped: no doc outline found.\n")
        return ""
    if not repo_index:
        _append_log(log_path, "[WARN] Gap review skipped: no code inventory found.\n")
        return ""
    prompt = build_gap_review_prompt(outline, repo_index)
    output = invoke_ollama(prompt, state.model, state.workspace_full, state.show_output, state.timeout)
    _write_text(state.gap_report_full, output)
    _append_log(log_path, "[GAP_REVIEW]\n" + strip_ansi(output) + "\n")
    return output


def _parse_json_payload(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`").strip()
    try:
        payload = json.loads(candidate)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            payload = json.loads(candidate[start : end + 1])
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
    return {}


def render_gap_report(output: str) -> str:
    payload = _parse_json_payload(output)
    if isinstance(payload, dict) and isinstance(payload.get("missing"), list):
        lines: List[str] = []
        missing = payload.get("missing") or []
        if not missing:
            lines.append("- None detected.")
        else:
            for item in missing:
                if not isinstance(item, dict):
                    continue
                feature = str(item.get("feature") or "").strip()
                evidence = str(item.get("evidence") or "").strip()
                confidence = str(item.get("confidence") or "").strip()
                if not feature:
                    continue
                conf_tag = f" ({confidence})" if confidence else ""
                if evidence:
                    lines.append(f"- {feature}{conf_tag} — {evidence}")
                else:
                    lines.append(f"- {feature}{conf_tag}")
        return "\n".join(lines)
    return ""


def update_plan_with_gap_report(plan_path: str, report_body: str) -> None:
    if not report_body:
        return
    begin_tag = "<!-- GAP_REPORT:BEGIN -->"
    end_tag = "<!-- GAP_REPORT:END -->"
    snippet = f"{begin_tag}\n{report_body}\n{end_tag}"
    content = ""
    if os.path.isfile(plan_path):
        with open(plan_path, "r", encoding="utf-8") as handle:
            content = handle.read()
    if begin_tag in content and end_tag in content:
        before = content.split(begin_tag)[0]
        after = content.split(end_tag)[-1]
        updated = before + snippet + after
    else:
        updated = content.rstrip() + "\n\n" + snippet + "\n"
    _write_text(plan_path, updated)
