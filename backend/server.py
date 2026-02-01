import argparse
import uvicorn
import json
import os
import sys

# Ensure backend dir is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Settings, SettingsUpdate
from app.state import AppState, Auth
from app.main import create_app
from app.utils import enforce_utf8, ensure_loop_modules, validate_workspace, load_persisted_settings

def pick_free_port() -> int:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("", 0))
        return s.getsockname()[1]
    finally:
        s.close()

def main() -> int:
    enforce_utf8()
    ensure_loop_modules()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--cors-origins", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--workspace", default="")
    parser.add_argument("--ramdisk-root", default="")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    persisted = load_persisted_settings()
    settings = Settings()
    if persisted:
        settings.apply_update(SettingsUpdate(**persisted))
    
    if args.workspace:
        settings.workspace = validate_workspace(args.workspace)
    if args.ramdisk_root:
        settings.ramdisk_root = args.ramdisk_root

    auth = Auth(args.token or os.environ.get("HARBORPILOT_TOKEN", ""))
    cors_origins = [origin.strip() for origin in (args.cors_origins or os.environ.get("HARBORPILOT_CORS_ORIGINS", "")).split(",") if origin.strip()]

    state = AppState(settings=settings)
    app = create_app(state, auth, cors_origins)
    
    port = args.port if args.port else pick_free_port()
    
    # Print startup event for Electron/Wrapper to check
    print(json.dumps({"event": "backend_started", "port": port}), flush=True)

    log_level = args.log_level or os.environ.get("HARBORPILOT_LOG_LEVEL", "info")
    uvicorn.run(app, host=args.host, port=port, log_level=log_level.lower())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
