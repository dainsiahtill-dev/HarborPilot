import os
import yaml
from typing import Dict, Any, List, Optional
from functools import lru_cache

from .schema import PromptContext, MemoryItem
from .memory_store import MemoryStore
from .reflection import ReflectionStore, ReflectionScheduler, ReflectionGenerator
from io_utils import emit_event

# Singleton stores
_MEMORY_STORE: Optional[MemoryStore] = None
_REFLECTION_STORE: Optional[ReflectionStore] = None
_REFLECTION_SCHEDULER: Optional[ReflectionScheduler] = None
_PERSONA_CONFIG: Optional[Dict[str, Any]] = None

def get_brain_path(base_dir: str, filename: str) -> str:
    """Returns path to brain files (memory/reflection jsonl)."""
    # Assuming .harborpilot/brain/ relative to repo root, or passed via env?
    # For now, store in .harborpilot/brain/
    brain_dir = os.path.join(base_dir, ".harborpilot", "brain")
    return os.path.join(brain_dir, filename)

def get_memory_store() -> Optional[MemoryStore]:
    return _MEMORY_STORE

def get_reflection_store() -> Optional[ReflectionStore]:
    return _REFLECTION_STORE

def init_anthropomorphic_modules(project_root: str):
    global _MEMORY_STORE, _REFLECTION_STORE, _PERSONA_CONFIG, _REFLECTION_SCHEDULER
    
    if _MEMORY_STORE is None:
        mem_file = get_brain_path(project_root, "MEMORY.jsonl")
        _MEMORY_STORE = MemoryStore(mem_file)
        
    if _REFLECTION_STORE is None:
        ref_file = get_brain_path(project_root, "REFLECTIONS.jsonl")
        _REFLECTION_STORE = ReflectionStore(ref_file)
        
    if _REFLECTION_SCHEDULER is None:
        _REFLECTION_SCHEDULER = ReflectionScheduler()
        
    if _PERSONA_CONFIG is None:
        persona_path = os.path.join(project_root, "prompts", "role_persona.yaml")
        if os.path.exists(persona_path):
            with open(persona_path, "r", encoding="utf-8") as f:
                _PERSONA_CONFIG = yaml.safe_load(f)
        else:
            _PERSONA_CONFIG = {"feature_flags": {"anthro_enabled": False}}

@lru_cache(maxsize=4)
def get_persona_text(role: str) -> str:
    if not _PERSONA_CONFIG or not _PERSONA_CONFIG.get("feature_flags", {}).get("anthro_enabled", False):
        return ""
    
    role_key = role.lower()
    role_data = _PERSONA_CONFIG.get("roles", {}).get(role_key)
    if not role_data:
        return ""
    
    style = role_data.get("style", "")
    quirks = "\n- ".join(role_data.get("quirks", []))
    taboos = "\n- ".join(role_data.get("taboo", []))
    
    return f"""
PERSONALITY INJECTION:
You are acting as the {role.upper()}.
Style: {style}
Quirks:
- {quirks}
Taboos (NEVER do this):
- {taboos}
""".strip()

def get_anthropomorphic_context(
    project_root: str,
    role: str,
    query: str,
    step: int,
    run_id: str,
    phase: str
) -> Dict[str, Any]:
    """
    Retrieves Persona and Memories for prompt injection.
    Returns a dict with contents and a PromptContext structure.
    """
    init_anthropomorphic_modules(project_root)
    
    # 1. Persona
    persona_text = get_persona_text(role)
    
    # 2. Retrieval
    retrieved_memories = []
    retrieved_reflections = []
    
    if _PERSONA_CONFIG and _PERSONA_CONFIG.get("feature_flags", {}).get("anthro_enabled", False):
        # Retrieve Memories
        # Query usually comes from the plan or current objective
        # Retrieve Memories with scores
        # Query usually comes from the plan or current objective
        retrieved_results = _MEMORY_STORE.retrieve(
            query=query, 
            current_step=step, 
            top_k=10,
            return_scores=True
        )
        # Unpack
        retrieved_memories = [item for item, score in retrieved_results]
        retrieved_scores = [score for item, score in retrieved_results]
        
        # Retrieve active Reflections
        if _REFLECTION_STORE:
            retrieved_reflections = _REFLECTION_STORE.retrieve_active(current_step=step)
            # Todo: filtering reflections by relevance if needed

    # 3. Format Memory Block
    # Token Budget: Max 10 items, < 200 chars each (soft enforcement via truncation)
    mem_block_lines = []
    if retrieved_memories or retrieved_reflections:
        mem_block_lines.append("## RELEVANT MEMORIES & INSIGHTS (Retrieval)")
        
        if retrieved_reflections:
            mem_block_lines.append("### Strategic Insights (Reflections):")
            for ref in retrieved_reflections[:3]: # Max 3 reflections
                text = ref.text[:240] + "..." if len(ref.text) > 240 else ref.text
                mem_block_lines.append(f"- [Scope: {','.join(ref.scope)}] {text}")
                
        if retrieved_memories:
            mem_block_lines.append("### Past Experiences:")
            for mem in retrieved_memories:
                delta = step - mem.step
                ago = f"{delta} steps ago" if delta > 0 else "Just now"
                text = mem.text[:200] + "..." if len(mem.text) > 200 else mem.text
                mem_block_lines.append(f"- [{mem.kind.upper()} | {ago}] {text}")

    memory_text = "\n".join(mem_block_lines)

    # 4. Construct PromptContext for event log
    prompt_context = PromptContext(
        run_id=run_id,
        phase=phase,
        step=step,
        persona_id=f"{role}.v1",
        retrieved_mem_ids=[m.id for m in retrieved_memories],
        retrieved_mem_scores=retrieved_scores if 'retrieved_scores' in locals() else [],
        retrieved_ref_ids=[r.id for r in retrieved_reflections],
        token_usage_estimate=len(persona_text)/4 + len(memory_text)/4 # Rough estimate
    )

    return {
        "persona_instruction": persona_text,
        "anthropomorphic_context": memory_text,
        "prompt_context_obj": prompt_context
    }

def run_reflection_cycle(
    project_root: str, 
    current_step: int, 
    run_id: str,
    model: str,
    events_path: str = ""
) -> None:
    """
    Checks if reflection is due and runs generation if so.
    """
    init_anthropomorphic_modules(project_root)
    
    if not _PERSONA_CONFIG or not _PERSONA_CONFIG.get("feature_flags", {}).get("anthro_enabled", False):
        return

    # 1. Check Schedule
    last_step = _REFLECTION_STORE.get_last_reflection_step()
    recent_errors = _MEMORY_STORE.count_recent_errors(last_step)
    
    if not _REFLECTION_SCHEDULER.should_reflect(current_step, last_step, recent_errors):
        return

    # 2. Prepare Data
    memories = _MEMORY_STORE.retrieve_recent(last_step)
    if not memories:
        return
        
    # 3. Generate
    generator = ReflectionGenerator(model, project_root)
    reflections = generator.generate(memories, current_step)
    
    if not reflections:
        return

    # 4. Store
    for ref in reflections:
        _REFLECTION_STORE.append(ref)
        
    # 5. Emit Event
    if events_path:
        emit_event(
            events_path,
            kind="observation",
            actor="System",
            name="reflection",
            refs={"run_id": run_id, "step": current_step},
            summary=f"Generated {len(reflections)} insights",
            output=[r.model_dump() for r in reflections]
        )


def get_anthropomorphic_context_v2(
    project_root: str,
    role: str,
    query: str,
    step: int,
    run_id: str,
    phase: str,
    *,
    events_path: str = "",
    sources_enabled: Optional[List[str]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Context Engine v2 entrypoint (backwards-compatible payload).
    """
    from context_manager import build_context_window

    init_anthropomorphic_modules(project_root)
    policy = policy or {}
    persona_text = get_persona_text(role)
    pack, _, _, _ = build_context_window(
        project_root,
        role,
        query,
        step,
        run_id,
        phase,
        events_path=events_path or "",
        sources_enabled=sources_enabled,
        policy=policy,
    )

    prompt_context = PromptContext(
        run_id=run_id,
        phase=phase,
        step=step,
        persona_id=f"{role}.v1",
        retrieved_mem_ids=[i.id for i in pack.items if i.kind == "memory"],
        retrieved_mem_scores=[],
        retrieved_ref_ids=[i.id for i in pack.items if i.kind == "reflection"],
        token_usage_estimate=pack.total_tokens,
    )

    return {
        "persona_instruction": persona_text,
        "anthropomorphic_context": pack.rendered_prompt,
        "prompt_context_obj": prompt_context,
        "context_pack": pack,
    }
