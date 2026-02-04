import json
import os
from typing import List

from pydantic import ValidationError

from .schema import ReflectionNode, MemoryItem
from ollama_utils import invoke_ollama
from prompt_loader import get_template, render_template

def parse_json_garbage(text: str):
    """Robust JSON parser for LLM output."""
    import re
    text = text.strip()
    # Try to find JSON array
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


class ReflectionStore:
    def __init__(self, reflection_file: str):
        self.reflection_file = reflection_file
        self.reflections: List[ReflectionNode] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.reflection_file):
            return
            
        with open(self.reflection_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    self.reflections.append(ReflectionNode(**data))
                except (json.JSONDecodeError, ValidationError):
                    continue

    def append(self, node: ReflectionNode):
        self.reflections.append(node)
        os.makedirs(os.path.dirname(self.reflection_file), exist_ok=True)
        with open(self.reflection_file, 'a', encoding='utf-8') as f:
            f.write(node.model_dump_json() + "\n")
            
    def retrieve_active(self, current_step: int) -> List[ReflectionNode]:
        """Returns valid reflections that haven't expired."""
        active = []
        for ref in self.reflections:
            age = current_step - ref.created_step
            if age <= ref.expiry_steps:
                active.append(ref)
        return active

    def get_last_reflection_step(self) -> int:
        """Returns the step of the last created reflection."""
        if not self.reflections:
            return 0
        # Assuming append-only, last one is latest. 
        # But to be safe, max of created_step
        return max(r.created_step for r in self.reflections)

class ReflectionScheduler:
    def should_reflect(self, current_step: int, last_reflection_step: int, recent_error_count: int) -> bool:
        """
        Reflect if:
        1. > 50 steps since last reflection
        2. > 3 errors recently
        """
        if current_step - last_reflection_step > 50:
            return True
        if recent_error_count >= 3:
            return True
        return False

# Generator would interface with LLM, kept as placeholder for now
class ReflectionGenerator:
    def __init__(self, model: str, workspace_root: str):
        self.model = model
        self.workspace_root = workspace_root

    def generate(self, memories: List[MemoryItem], current_step: int) -> List[ReflectionNode]:
        if not memories:
            return []
            
        # Format memories for prompt
        mem_text = "\n".join([f"- [{m.kind.upper()}] {m.text}" for m in memories])
        
        try:
            # Usually strict JSON templates are stored under "templates" key in JSON file
            # prompt_loader logic handles simple strings or dicts. 
            # If get_template returns the full dict, we might need to drill down. 
            # Looking at prompt_loader.py: get_template returns string if key matches directly 
            # OR if it's in "templates". 
            # My created JSON has "templates": { "reflection_generator": ... }
            # So name should be "reflection_generator"
            
            # Re-reading prompt_loader logic:
            # get_template(name) -> data = load_profile(..)
            # if name == "plan_template" -> return data.get("plan_template")
            # templates = data.get("templates")
            # return templates.get(name)
            
            # So I should request "reflection_generator"
            template_str = get_template("reflection_generator") 
        except Exception:
            # Fallback if specific template not found
            template_str = get_template("reflection_prompt", profile="reflection_prompt") # This might be tricky with prompt_loader
            # Simpler: just use hardcoded constraint if loader fails, but let's try standard way
            # If standard loader fails, we return empty
            return []

        prompt = render_template(template_str, {"memories_text": mem_text})
        
        output = invoke_ollama(
            prompt, 
            self.model, 
            self.workspace_root, 
            show_output=False, 
            timeout=120
        )
        
        data = parse_json_garbage(output)
        
        reflections = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                reflections.append(ReflectionNode(
                    created_step=current_step,
                    scope=item.get("scope", ["general"]),
                    text=item.get("text", ""),
                    confidence=float(item.get("confidence", 0.5)),
                    expiry_steps=int(item.get("expiry_steps", 100)),
                    type="heuristic",
                    evidence_mem_ids=[m.id for m in memories], # Attribute to all input memories for now
                    importance=5
                ))
            except ValidationError:
                continue
                
        return reflections
