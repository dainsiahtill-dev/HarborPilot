from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import Auth
from ..utils import get_lancedb_status

router = APIRouter()

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/lancedb/status", dependencies=[Depends(require_auth)])
def lancedb_status_endpoint() -> Dict[str, Any]:
    return get_lancedb_status()
