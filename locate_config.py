import sys
import os
sys.path.append(os.path.abspath("backend"))

from app.utils import build_cache_root, resolve_artifact_path
from app.config import Settings

# Define workspace based on user context
workspace = "c:\\Users\\dains\\Documents\\Git\\Harborpilot"
ramdisk_root = "X:\\"

def locate():
    cache_root = build_cache_root(ramdisk_root, workspace)
    print(f"Cache Root: {cache_root}")
    
    rel_path = ".harborpilot/runtime/config/llm_config.json"
    full_path = resolve_artifact_path(workspace, cache_root, rel_path)
    print(f"Config Path: {full_path}")
    
    if os.path.isfile(full_path):
        print("File exists!")
        with open(full_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("File does NOT exist.")

if __name__ == "__main__":
    locate()
