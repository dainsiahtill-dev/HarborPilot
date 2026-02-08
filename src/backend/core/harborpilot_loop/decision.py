import re
from typing import Any, Dict, List, Optional


def get_numbered_options(text: str) -> List[Dict[str, Any]]:
    options = []
    if not text:
        return options
    pattern = re.compile(r"^\s*(\d{1,2})[\.\)\]:\-\u3001]\s+(.+)$")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            options.append({"number": int(match.group(1)), "text": match.group(2).strip()})
    return options


def collect_section_lines(plan_text: str, header_prefix: str) -> List[str]:
    if not plan_text:
        return []
    lines = plan_text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().startswith(header_prefix):
            start = idx + 1
            break
    if start is None:
        return []
    section_lines = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
            break
        section_lines.append(line.rstrip())
    return section_lines


def parse_backlog_items(section_lines: List[str]) -> List[str]:
    items = []
    current: List[str] = []
    for line in section_lines:
        match = re.match(r"^\s*(\d+)\)\s+(.+)$", line)
        if match:
            if current:
                items.append("\n".join(current).strip())
            current = [match.group(0).strip()]
            continue
        if current:
            stripped = line.strip()
            if stripped.startswith("-") or line.startswith(" ") or line.startswith("\t"):
                current.append(stripped)
    if current:
        items.append("\n".join(current).strip())
    return items


def select_backlog_target(plan_text: str, last_index: int) -> Dict[str, Any]:
    docs_section = collect_section_lines(plan_text, "## Backlog A:")
    code_section = collect_section_lines(plan_text, "## Backlog B:")
    items = parse_backlog_items(docs_section) + parse_backlog_items(code_section)
    if not items:
        return {"index": last_index, "item": ""}
    next_index = (last_index + 1) % len(items)
    return {"index": next_index, "item": items[next_index]}


def has_decision_cue(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    for word in ["choose", "select", "pick", "option", "reply with", "respond with", "which", "number"]:
        if word in lower:
            return True
    if re.search(r"[\?\uFF1F]", text):
        return True
    for pattern in [
        "\u9009\u62e9",
        "\u9009\u9879",
        "\u56de\u590d",
        "\u7f16\u53f7",
        "\u8bf7\u8f93\u5165",
        "\u8bf7\u9009",
        "\u8fdb\u5165\u54ea\u4e2a",
    ]:
        if re.search(pattern, text):
            return True
    if re.search(r"[\u4e00-\u9fff]", text):
        return True
    return False


def needs_decision(text: str) -> bool:
    options = get_numbered_options(text)
    if len(options) < 2:
        return False
    return has_decision_cue(text)


def build_decision_prompt(last_response: str, options: List[Dict[str, Any]]) -> str:
    option_lines = "\n".join([f"{opt['number']}. {opt['text']}" for opt in options])
    return f"""You are a decision-only helper.
Choose the single best option number to proceed.
Rules:
- Reply with only the number (e.g. 1).
- Do not include any other text.
- Do not modify files or run commands.

Assistant response:
<<<
{last_response}
>>>

Options:
{option_lines}
"""


def parse_decision_number(decision_text: str, options: List[Dict[str, Any]]) -> Optional[int]:
    if not decision_text:
        return None
    match = re.search(r"\d+", decision_text)
    if not match:
        return None
    num = int(match.group(0))
    if any(opt["number"] == num for opt in options):
        return num
    return None
