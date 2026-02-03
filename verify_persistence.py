import sys
import os
import json
import tempfile
import shutil

# Add backend to path
sys.path.append(os.path.abspath("backend"))

from app.llm.config import normalize_llm_config, build_default_config, save_llm_config, load_llm_config
from app.utils import build_cache_root

# Mock Settings object
class MockSettings:
    def __init__(self, workspace, ramdisk_root=None):
        self.workspace = workspace
        self.ramdisk_root = ramdisk_root or os.path.join(workspace, "cache") # Provide a default!
        self.pm_backend = "ollama"  # Minimal default
        self.pm_model = "llama3"
        self.director_model = "llama3"
        self.docs_init_provider = "ollama"
        self.docs_init_model = "llama3"
        self.docs_init_base_url = ""

def test_config_persistence():
    # 1. Setup a temp workspace
    temp_dir = tempfile.mkdtemp()
    workspace = os.path.join(temp_dir, "test_workspace")
    cache_root = os.path.join(temp_dir, "cache_root")
    os.makedirs(workspace)
    os.makedirs(cache_root) # Make sure it exists!
    settings = MockSettings(workspace, ramdisk_root=cache_root)
    
    print(f"Testing in workspace: {workspace}")
    
    # 2. Emulate first load (should create defaults)
    # Note: load_llm_config calls build_cache_root using settings.ramdisk_root
    # We must pass cache_root derived from build_cache_root to calls if we were doing it manually,
    # but load_llm_config calls config.llm_config_path -> utils.resolve_artifact_path.
    
    # Wait, load_llm_config second arg IS cache_root! I was passing ""!
    # I need to compute cache_root for the test.
    real_cache_root = build_cache_root(cache_root, workspace)
    print(f"Computed cache root: {real_cache_root}")
    
    config = load_llm_config(workspace, real_cache_root, settings)
    providers = config["providers"]
    print(f"Initial providers count: {len(providers)}")
    
    if len(providers) < 5:
        print("FAIL: Initial load did not include default providers.")
        shutil.rmtree(temp_dir)
        sys.exit(1)

    # 3. Simulate Frontend Payload: User deletes ALL providers
    # Frontend sends llmConfig with providers: {}
    frontend_payload = {
        "schema_version": 1,
        "providers": {},  # Empty!
        "roles": config["roles"],
        "policies": config["policies"]
    }
    
    # 4. Save
    print("Saving config with EMPTY providers...")
    saved_config = save_llm_config(workspace, real_cache_root, frontend_payload, settings)
    
    print(f"Saved providers keys: {list(saved_config['providers'].keys())}")
    
    if len(saved_config["providers"]) > 0:
        print("FAIL: Saved config restored providers!")
        print("Expected: []")
        print(f"Actual: {list(saved_config['providers'].keys())}")
        
    # 5. Reload (verify persistence)
    reloaded_config = load_llm_config(workspace, real_cache_root, settings)
    print(f"Reloaded providers keys: {list(reloaded_config['providers'].keys())}")
    
    if len(reloaded_config["providers"]) > 0:
        print("FAIL: Reloaded config restored providers from file!")
        
    shutil.rmtree(temp_dir)
    print("Persistence Test Complete.")

if __name__ == "__main__":
    test_config_persistence()
