
import os
import sys
import tempfile
import json
from datetime import datetime

# Add Loop modules to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR) # backend/
CORE_DIR = os.path.join(BACKEND_DIR, "core", "harborpilot_loop")
def _load_anthro_modules(core_dir: str):
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    from anthropomorphic.integration import get_anthropomorphic_context, init_anthropomorphic_modules
    return get_anthropomorphic_context, init_anthropomorphic_modules

def test_integration():
    with tempfile.TemporaryDirectory() as temp_root:
        # Setup structure
        brain_dir = os.path.join(temp_root, ".harborpilot", "brain")
        os.makedirs(brain_dir)
        prompts_dir = os.path.join(temp_root, "prompts")
        os.makedirs(prompts_dir)
        
        # Create role_persona.yaml
        persona_yaml = """
feature_flags:
  anthro_enabled: true
roles:
  director:
    style: "Test Director Style"
    quirks: ["Test Quirk 1"]
    taboo: ["Test Taboo 1"]
"""
        with open(os.path.join(prompts_dir, "role_persona.yaml"), "w", encoding="utf-8") as f:
            f.write(persona_yaml.strip())
            
        # Create Memory Item directly in jsonl
        mem_item = {
            "id": "mem-1",
            "source_event_id": "evt-1",
            "step": 5,
            "timestamp": datetime.now().isoformat(),
            "role": "director",
            "type": "observation",
            "kind": "error",
            "text": "Previously, the build failed due to missing dependency.",
            "importance": 5,
            "keywords": ["build", "dependency"],
            "hash": "abc"
        }
        with open(os.path.join(brain_dir, "MEMORY.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps(mem_item) + "\n")

        # Run Test
        print("Initializing modules...")
        get_anthropomorphic_context, init_anthropomorphic_modules = _load_anthro_modules(CORE_DIR)
        init_anthropomorphic_modules(temp_root)
        
        # manually reload memory store to pick up the file (if init was cached globally)
        # Actually init_anthropomorphic_modules is global. 
        # But since we run this in a fresh process, it should be fine.
        # Wait, if I import integration, the globals are None.
        
        print("Calling get_anthropomorphic_context...")
        result = get_anthropomorphic_context(
            temp_root, 
            "director", 
            "Fix query", 
            step=10, 
            run_id="run-1", 
            phase="test"
        )
        
        print("\n--- Persona Instruction ---")
        print(result["persona_instruction"])
        
        print("\n--- Anthropomorphic Context ---")
        print(result["anthropomorphic_context"])
        
        print("\n--- Prompt Context Object ---")
        context_obj = result["prompt_context_obj"]
        print(f"RunID: {context_obj.run_id}")
        print(f"Step: {context_obj.step}")
        print(f"Retrieved IDs: {context_obj.retrieved_mem_ids}")
        
        # Assertions
        assert "Test Director Style" in result["persona_instruction"], "Persona style missing"
        assert "Previously, the build failed" in result["anthropomorphic_context"], "Memory missing"
        assert context_obj.run_id == "run-1"
        assert "mem-1" in context_obj.retrieved_mem_ids
        
        print("\nTEST PASSED successfully.")

if __name__ == "__main__":
    test_integration()
