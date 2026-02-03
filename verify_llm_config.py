import sys
import os
import json

# Add backend to path
sys.path.append(os.path.abspath("backend"))

from app.llm.config import normalize_llm_config, build_default_config

def test_config_normalization():
    # 1. Get default config
    defaults = build_default_config(None)
    default_providers = defaults["providers"]
    print(f"Default providers keys: {list(default_providers.keys())}")
    
    # 2. Simulate user deleting a provider
    # User config only has 'ollama' (Simulating they deleted 'codex_cli')
    user_payload = {
        "providers": {
            "ollama": default_providers.get("ollama", {})
        }
    }
    
    # 3. Normalize
    normalized = normalize_llm_config(user_payload, None)
    normalized_providers = normalized["providers"]
    
    print(f"Normalized providers keys: {list(normalized_providers.keys())}")
    
    # 4. Verify 'codex_cli' is GONE
    if "codex_cli" in normalized_providers:
        print("FAIL: codex_cli still exists in normalized config!")
        sys.exit(1)
    
    if "ollama" not in normalized_providers:
        print("FAIL: ollama missing from normalized config!")
        sys.exit(1)
        
    print("SUCCESS: Default provider was successfully removed.")

if __name__ == "__main__":
    test_config_normalization()
