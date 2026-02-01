from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from core.harborpilot_loop.anthropomorphic.integration import get_memory_store, get_reflection_store, init_anthropomorphic_modules

router = APIRouter(prefix="/anthropomorphic", tags=["anthropomorphic"])

class AnthroState(BaseModel):
    last_reflection_step: int
    recent_error_count: int
    total_memories: int
    total_reflections: int

@router.get("/state")
async def get_state(request: Request) -> AnthroState:
    # Ensure modules initialized
    ramdisk_root = request.app.state.app_state.settings.ramdisk_root or "."
    init_anthropomorphic_modules(ramdisk_root)
    
    mem_store = get_memory_store()
    ref_store = get_reflection_store()
    
    if not mem_store:
        raise HTTPException(status_code=503, detail="Memory store not initialized")
        
    last_step = 0
    total_reflections = 0
    if ref_store:
        last_step = ref_store.get_last_reflection_step()
        total_reflections = len(ref_store.reflections)
        
    recent_errors = mem_store.count_recent_errors(last_step)
    total_memories = len(mem_store.memories)
    
    return AnthroState(
        last_reflection_step=last_step,
        recent_error_count=recent_errors,
        total_memories=total_memories,
        total_reflections=total_reflections
    )

@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str, request: Request):
    ramdisk_root = request.app.state.app_state.settings.ramdisk_root or "."
    init_anthropomorphic_modules(ramdisk_root)

    mem_store = get_memory_store()
    if not mem_store:
        raise HTTPException(status_code=503, detail="Memory store not initialized")

    success = mem_store.delete(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
        
    return {"status": "deleted", "id": memory_id}
