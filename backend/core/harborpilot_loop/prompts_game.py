import os
import re
from typing import Dict, List

from io_utils import ensure_parent_dir, read_file_safe
from shared import normalize_path, unique_preserve


def build_project_prompt(
    plan_text: str,
    memory_summary: str,
    target_note: str,
) -> str:
    return f"""You are a collaborative team:
- Creative Director / Producer (vision, scope, milestone ownership)
- Game Designer (systems, economy, progression)
- UI Designer (flows, HUD, panels)
- Game Engineer (architecture, code constraints)

Workflow for each iteration:
1) Brief role notes (1-3 bullets each).
2) Agree on doc changes and apply them in the repo (prefer docs/).
3) Director decision: confirm scope and priorities for this round.
4) End with a short Next Step.

Format:
- End with two lines:
  Summary: ...
  Next Step: ...

Constraints:
- Keep scope small and incremental.
- Use concrete headings and consistent terminology.
- Avoid exposing chain-of-thought; be concise.
- Physics-lab is a browser client (Vite). Do NOT add Node server logic or process.env/require usage in client code.

Encoding guardrail (HARD RULE):
- Any PowerShell read/write of text MUST include UTF-8.
- Use: `Get-Content -Encoding utf8` (or `-Raw -Encoding utf8`) and `Set-Content -Encoding utf8`.
- If you forgot, re-run immediately with the UTF-8 flags.
- Do NOT set global PowerShell defaults; include `-Encoding utf8` on each command instead.

Context references (must read before changes):
- docs/README.md
- docs/product/requirements.md
- docs/product/vision.md
- docs/systems/
- docs/ux/ui-ux.md
- docs/engineering/engineering-notes.md
- MMO_CORE_SPEC.md
- README.md

Memory summary (previous run):
{memory_summary}

Plan:
{plan_text}

Round target (auto-selected):
{target_note}
"""


def build_continuation_prompt(
    plan_text: str,
    last_response: str,
    decision_number: int,
    memory_summary: str,
    target_note: str,
) -> str:
    return f"""You are a collaborative team:
- Creative Director / Producer (vision, scope, milestone ownership)
- Game Designer (systems, economy, progression)
- UI Designer (flows, HUD, panels)
- Game Engineer (architecture, code constraints)

Workflow for each iteration:
1) Brief role notes (1-3 bullets each).
2) Agree on doc changes and apply them in the repo (prefer docs/).
3) Director decision: confirm scope and priorities for this round.
4) End with a short Next Step.

Format:
- End with two lines:
  Summary: ...
  Next Step: ...

Constraints:
- Physics-lab is a browser client (Vite). Do NOT add Node server logic or process.env/require usage in client code.

Encoding guardrail (HARD RULE):
- Any PowerShell read/write of text MUST include UTF-8.
- Use: `Get-Content -Encoding utf8` (or `-Raw -Encoding utf8`) and `Set-Content -Encoding utf8`.
- If you forgot, re-run immediately with the UTF-8 flags.
- Do NOT set global PowerShell defaults; include `-Encoding utf8` on each command instead.

Context references (must read before changes):
- docs/README.md
- docs/product/requirements.md
- docs/product/vision.md
- docs/systems/
- docs/ux/ui-ux.md
- docs/engineering/engineering-notes.md
- MMO_CORE_SPEC.md
- README.md

Memory summary (previous run):
{memory_summary}

Plan:
{plan_text}

Round target (auto-selected):
{target_note}

Previous assistant response:
<<<
{last_response}
>>>

User decision: {decision_number}

Continue with the selected option. If more choices are required, ask again using a numbered list.
"""


def build_repair_prompt(plan_text: str, last_response: str, reason: str) -> str:
    return f"""You are a repair-only helper.
The last run hit an error and must be fixed automatically.

Reason:
{reason}

Plan:
{plan_text}

Last assistant response:
<<<
{last_response}
>>>

Instructions:
- Diagnose the error.
- Apply minimal fixes in the repo.
- Run any necessary checks if they are cheap.
- Do not ask questions unless blocked.
- Summarize changes briefly at the end.
"""


def build_planner_prompt(
    plan_text: str,
    memory_summary: str,
    target_note: str,
) -> str:
    return f"""You are a planning-only coordinator.
Do NOT modify files or run commands. Produce an implementation brief for a coding model.

Output format:
- Return a single JSON object (no markdown, no code fences).
- Required keys:
  - "brief": concise, step-by-step instructions for a coding model.
  - "files": array of repo-relative paths to edit.
- Optional keys:
  - "qa": what to verify.
  - "notes": extra constraints or context.
  - "commands": array of npm commands to run (optional).
Example:
{{"brief":"...","files":["path/a.ts","path/b.ts"],"qa":"...","notes":"...","commands":["npm run test"]}}

Constraints:
- Keep scope small and incremental.
- Use concrete headings and consistent terminology.
- Avoid chain-of-thought.
- Physics-lab is a browser client (Vite). Do NOT add Node server logic or process.env/require usage in client code.

Context references (must read before changes):
- docs/README.md
- docs/product/requirements.md
- docs/product/vision.md
- docs/systems/
- docs/ux/ui-ux.md
- docs/engineering/engineering-notes.md
- MMO_CORE_SPEC.md
- README.md

Memory summary (previous run):
{memory_summary}

Plan:
{plan_text}

Round target (auto-selected):
{target_note}
"""


def build_qa_prompt(
    plan_text: str,
    memory_summary: str,
    target_note: str,
    changed_files: List[str],
    planner_output: str,
    ollama_output: str,
) -> str:
    files = "\n".join(f"- {path}" for path in changed_files) if changed_files else "- (none)"
    return f"""You are the QA / acceptance reviewer.
Do NOT implement new changes unless tests or errors force it.
Review the OLLAMA changes, run minimal checks if needed, and give guidance.

Changed files:
{files}

Planner output:
<<<
{planner_output}
>>>

OLLAMA output (raw):
<<<
{ollama_output}
>>>

Plan:
{plan_text}

Memory summary (previous run):
{memory_summary}

Output format:
- Return a single JSON object (no markdown, no code fences).
- Required keys:
  - "acceptance": "PASS" or "FAIL"
  - "summary": short summary
  - "next": next step
- Optional keys:
  - "findings": array of strings (bugs/risks/tests)
Example:
{{"acceptance":"PASS","summary":"...","next":"...","findings":["..."]}}
"""


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


def build_ollama_prompt(brief: str, file_context: str) -> str:
    return f"""You are a code-writing assistant for a local repo.
Follow the Implementation Brief and update ONLY the specified files.
Return full file contents using this exact format:
FILE: path/to/file.ext
<full file content>
END FILE

Hard constraints:
- Physics-lab is a browser client (Vite). Do NOT add Node server logic or process.env/require usage in client code.

If no changes are needed, output exactly: NO_CHANGES

Implementation Brief:
{brief}

Current file contents:
{file_context}
"""


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


