from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import Auth
from ..services.ollama import list_ollama_models, ollama_stop

router = APIRouter()

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/ollama/models", dependencies=[Depends(require_auth)])
def get_ollama_models() -> List[str]:
    return list_ollama_models()

@router.post("/ollama/stop", dependencies=[Depends(require_auth)])
def stop_ollama_models() -> Dict[str, Any]:
    return ollama_stop()
