import os
import json
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any, Tuple
from ..config import Settings, ARTIFACT_ROOT, ARTIFACT_NAMESPACE
from ..utils import ensure_loop_modules, _extract_json_block, _normalize_list

ensure_loop_modules()
try:
    from codex_utils import load_llm_clients
except ImportError:
    def load_llm_clients() -> Tuple[Any, Any]:
        return None, None

def _build_docs_ai_prompt(fields: Dict[str, str]) -> str:
    goal = fields.get("goal") or ""
    in_scope = fields.get("in_scope") or ""
    out_scope = fields.get("out_of_scope") or ""
    constraints = fields.get("constraints") or ""
    definition_of_done = fields.get("definition_of_done") or ""
    backlog = fields.get("backlog") or ""
    return (
        "You are helping draft initial project documentation. "
        "Return ONLY a JSON object with keys: goal, in_scope, out_of_scope, constraints, definition_of_done, backlog. "
        "Each value must be an array of short strings. Do not include markdown or extra text.\n\n"
        f"Goal: {goal}\n"
        f"In Scope: {in_scope}\n"
        f"Out of Scope: {out_scope}\n"
        f"Constraints: {constraints}\n"
        f"Definition of Done: {definition_of_done}\n"
        f"Backlog: {backlog}\n"
    )

def _invoke_custom_llm(prompt: str, settings: Settings) -> str:
    base_url = (settings.docs_init_base_url or "").strip().rstrip("/")
    if not base_url:
        return ""
    path = settings.docs_init_api_path or "/v1/chat/completions"
    if not path.startswith("/"):
        path = "/" + path
    url = base_url + path
    payload = {
        "model": settings.docs_init_model,
        "messages": [
            {"role": "system", "content": "You output strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }
    api_key = (settings.docs_init_api_key or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=max(1, settings.docs_init_timeout or 300)) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return body
    except Exception:
        return ""
    try:
        payload = json.loads(body)
        choices = payload.get("choices") or []
        if choices and isinstance(choices, list):
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    except Exception:
        pass
    return body

def generate_docs_ai_fields(workspace: str, settings: Settings, fields: Dict[str, str]) -> Optional[Dict[str, List[str]]]:
    provider = (settings.docs_init_provider or "").strip().lower()
    model = (settings.docs_init_model or "").strip()
    if not provider:
        return None
    prompt = _build_docs_ai_prompt(fields)
    invoke_codex, invoke_ollama = load_llm_clients()
    output = ""
    if provider == "codex":
        if invoke_codex is None:
            return None
        output = invoke_codex(
            prompt=prompt,
            output_file=os.path.join(workspace, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "DOCS_INIT_AI.md"),
            workspace=workspace,
            show_output=False,
            full_auto=True,
            dangerous=False,
            profile="",
            timeout=max(1, settings.docs_init_timeout or 300),
        )
    elif provider == "ollama":
        if invoke_ollama is None or not model:
            return None
        output = invoke_ollama(
            prompt=prompt,
            model=model,
            workspace=workspace,
            show_output=False,
            timeout=max(1, settings.docs_init_timeout or 300),
        )
    elif provider == "custom":
        if not model:
            return None
        output = _invoke_custom_llm(prompt, settings)
    if not output:
        return None
    data = _extract_json_block(output)
    if not data:
        return None
    return {
        "goal": _normalize_list(data.get("goal")),
        "in_scope": _normalize_list(data.get("in_scope")),
        "out_of_scope": _normalize_list(data.get("out_of_scope")),
        "constraints": _normalize_list(data.get("constraints")),
        "definition_of_done": _normalize_list(data.get("definition_of_done")),
        "backlog": _normalize_list(data.get("backlog")),
    }
