import os
from typing import Any, Dict, List

from prompt_loader import get_template, render_template
from shared import normalize_path, unique_preserve
from io_utils import ensure_parent_dir, read_file_safe, emit_event
from anthropomorphic.integration import get_anthropomorphic_context, get_anthropomorphic_context_v2




PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _use_context_engine_v2() -> bool:
    value = str(os.environ.get("HARBORPILOT_CONTEXT_ENGINE", "")).strip().lower()
    return value in ("v2", "context_v2", "engine_v2", "context-engine-v2")


def _get_context_bundle(
    role: str,
    query: str,
    step: int,
    run_id: str,
    phase: str,
    events_path: str = "",
) -> Dict[str, Any]:
    if _use_context_engine_v2():
        return get_anthropomorphic_context_v2(
            PROJECT_ROOT,
            role,
            query,
            step,
            run_id,
            phase,
            events_path=events_path or "",
        )
    return get_anthropomorphic_context(PROJECT_ROOT, role, query, step, run_id, phase)

def build_project_prompt(
    plan_text: str,
    memory_summary: str,
    target_note: str,
    step: int = 0,
    run_id: str = "",
    events_path: str = "",
) -> str:
    template = get_template("project_prompt")
    
    anthro = _get_context_bundle("pm", plan_text, step, run_id, "pm.planning", events_path)
    
    if events_path:
        output = anthro["prompt_context_obj"].model_dump()
        context_pack = anthro.get("context_pack")
        if context_pack is not None:
            output["context_hash"] = getattr(context_pack, "request_hash", "")
            output["context_snapshot"] = getattr(context_pack, "snapshot_path", "")
        emit_event(
            events_path,
            kind="observation",
            actor="PM",
            name="prompt_context",
            refs={"run_id": run_id, "step": step},
            summary="Prompt Context Injection",
            output=output
        )
    
    return render_template(
        template,
        {
            "plan_text": plan_text,
            "memory_summary": memory_summary,
            "target_note": target_note,
            "persona_instruction": anthro["persona_instruction"],
            "anthropomorphic_context": anthro["anthropomorphic_context"],
        },
    )


def build_continuation_prompt(
    plan_text: str,
    last_response: str,
    decision_number: int,
    memory_summary: str,
    target_note: str,
) -> str:
    template = get_template("continuation_prompt")
    return render_template(
        template,
        {
            "plan_text": plan_text,
            "last_response": last_response,
            "decision_number": decision_number,
            "memory_summary": memory_summary,
            "target_note": target_note,
        },
    )


def build_repair_prompt(plan_text: str, last_response: str, reason: str) -> str:
    template = get_template("repair_prompt")
    return render_template(
        template,
        {
            "plan_text": plan_text,
            "last_response": last_response,
            "reason": reason,
        },
    )


def build_planner_prompt(
    plan_text: str,
    memory_summary: str,
    target_note: str,
    step: int = 0,
    run_id: str = "",
    events_path: str = "",
) -> str:
    template = get_template("planner_prompt")
    
    anthro = _get_context_bundle("director", plan_text, step, run_id, "director.planning", events_path)

    if events_path:
        output = anthro["prompt_context_obj"].model_dump()
        context_pack = anthro.get("context_pack")
        if context_pack is not None:
            output["context_hash"] = getattr(context_pack, "request_hash", "")
            output["context_snapshot"] = getattr(context_pack, "snapshot_path", "")
        emit_event(
            events_path,
            kind="observation",
            actor="Director",
            name="prompt_context",
            refs={"run_id": run_id, "step": step},
            summary="Prompt Context Injection",
            output=output
        )

    return render_template(
        template,
        {
            "plan_text": plan_text,
            "memory_summary": memory_summary,
            "target_note": target_note,
            "persona_instruction": anthro["persona_instruction"],
            "anthropomorphic_context": anthro["anthropomorphic_context"],
        },
    )


def build_tool_planner_prompt(pm_tasks_json: str, known_files: str, last_result: str) -> str:
    template = get_template("tool_planner_prompt")
    return render_template(
        template,
        {
            "pm_tasks_json": pm_tasks_json,
            "known_files": known_files,
            "last_result": last_result,
        },
    )


def build_patch_planner_prompt(tool_output_json: str, pm_tasks_json: str) -> str:
    template = get_template("patch_planner_prompt")
    return render_template(
        template,
        {
            "tool_output_json": tool_output_json,
            "pm_tasks_json": pm_tasks_json,
        },
    )


def build_qa_prompt(
    plan_text: str,
    memory_summary: str,
    target_note: str,
    changed_files: List[str],
    planner_output: str,
    ollama_output: str,
    tool_results: str,
    reviewer_summary: str,
    patch_risk: str,
    step: int = 0,
    run_id: str = "",
    events_path: str = "",
) -> str:
    files_list = "\n".join(f"- {path}" for path in changed_files) if changed_files else "- (none)"
    template = get_template("qa_prompt")
    
    # Context query is related to changes and plan
    query = f"Verify changes in {files_list}. Plan: {plan_text[:200]}"
    anthro = _get_context_bundle("qa", query, step, run_id, "qa.review", events_path)

    if events_path:
        output = anthro["prompt_context_obj"].model_dump()
        context_pack = anthro.get("context_pack")
        if context_pack is not None:
            output["context_hash"] = getattr(context_pack, "request_hash", "")
            output["context_snapshot"] = getattr(context_pack, "snapshot_path", "")
        emit_event(
            events_path,
            kind="observation",
            actor="QA",
            name="prompt_context",
            refs={"run_id": run_id, "step": step},
            summary="Prompt Context Injection",
            output=output
        )

    return render_template(
        template,
        {
            "plan_text": plan_text,
            "memory_summary": memory_summary,
            "target_note": target_note,
            "changed_files_list": files_list,
            "planner_output": planner_output,
            "ollama_output": ollama_output,
            "tool_results": tool_results,
            "reviewer_summary": reviewer_summary,
            "patch_risk": patch_risk,
            "persona_instruction": anthro["persona_instruction"],
            "anthropomorphic_context": anthro["anthropomorphic_context"],
        },
    )


def build_reviewer_prompt(
    plan_text: str,
    memory_summary: str,
    target_note: str,
    changed_files: List[str],
    planner_output: str,
    ollama_output: str,
    tool_results: str,
    patch_risk: str,
) -> str:
    files_list = "\n".join(f"- {path}" for path in changed_files) if changed_files else "- (none)"
    template = get_template("reviewer_prompt")
    return render_template(
        template,
        {
            "plan_text": plan_text,
            "memory_summary": memory_summary,
            "target_note": target_note,
            "changed_files_list": files_list,
            "planner_output": planner_output,
            "ollama_output": ollama_output,
            "tool_results": tool_results,
            "patch_risk": patch_risk,
        },
    )


def build_ollama_prompt(brief: str, file_context: str) -> str:
    template = get_template("ollama_prompt")
    return render_template(template, {"brief": brief, "file_context": file_context})


def extract_between(text: str, start_tag: str, end_tag: str) -> str:
    if not text:
        return ""
    start_idx = text.find(start_tag)
    end_idx = text.find(end_tag)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return ""
    return text[start_idx + len(start_tag) : end_idx].strip()


def parse_files_to_edit(text: str) -> List[str]:
    if not text:
        return []
    lines = text.splitlines()
    in_section = False
    files: List[str] = []
    import re

    header_re = re.compile(r"^\s*(?:\d+[\).\]]\s*)?files to edit\b", re.IGNORECASE)
    next_section_re = re.compile(r"^\s*\d+[\).\]]\s*\S")
    for line in lines:
        stripped = line.strip()
        if not in_section:
            if header_re.match(stripped):
                in_section = True
            continue
        if not stripped:
            continue
        if stripped.startswith("##") or stripped.startswith("[OLLAMA_BEGIN]"):
            break
        if next_section_re.match(stripped):
            break
        match = re.match(r"^\s*[-*]\s+(.+)$", line)
        if match:
            path = normalize_path(match.group(1).strip("`"))
            if path:
                files.append(path)
    return unique_preserve(files)


def build_file_context(files: List[str], workspace: str) -> str:
    blocks: List[str] = []
    for path in files:
        full_path = os.path.join(workspace, path)
        content = read_file_safe(full_path)
        header = f"FILE: {path}"
        blocks.append(header)
        blocks.append(content if content else "<EMPTY OR MISSING>")
        blocks.append("END FILE")
    return "\n".join(blocks)


def parse_file_blocks(text: str) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    if not text:
        return blocks
    if text.strip() == "NO_CHANGES":
        return blocks
    current_path = ""
    current_lines: List[str] = []
    for line in text.splitlines():
        if line.startswith("FILE:"):
            if current_path:
                blocks.append({"path": current_path, "content": "\n".join(current_lines).rstrip("\n") + "\n"})
            current_path = normalize_path(line[len("FILE:") :].strip())
            current_lines = []
            continue
        if line.strip() == "END FILE" and current_path:
            blocks.append({"path": current_path, "content": "\n".join(current_lines).rstrip("\n") + "\n"})
            current_path = ""
            current_lines = []
            continue
        if line.strip().startswith("```"):
            continue
        if current_path:
            current_lines.append(line)
    if current_path:
        blocks.append({"path": current_path, "content": "\n".join(current_lines).rstrip("\n") + "\n"})
    return blocks


def strip_full_content_markers(content: str) -> str:
    if not content:
        return content
    lines = content.splitlines()
    if not lines:
        return content
    start = 0
    end = len(lines) - 1
    while start <= end and not lines[start].strip():
        start += 1
    while end >= start and not lines[end].strip():
        end -= 1
    if start <= end and lines[start].strip().lower() == "<full file content>":
        lines.pop(start)
        end -= 1
    if start <= end and lines[end].strip().lower() in {"</full content>", "</full file content>"}:
        lines.pop(end)
    sanitized = "\n".join(lines)
    if content.endswith("\n"):
        sanitized += "\n"
    return sanitized


def apply_file_blocks(blocks: List[Dict[str, str]], workspace: str) -> List[str]:
    changed: List[str] = []
    for block in blocks:
        path = block.get("path") or ""
        content = block.get("content")
        if not path or content is None:
            continue
        content = strip_full_content_markers(content)
        full_path = os.path.join(workspace, path)
        ensure_parent_dir(full_path)
        with open(full_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        changed.append(path)
    return unique_preserve(changed)
