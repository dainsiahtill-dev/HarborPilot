
import os
import sys
import json
import argparse
import hashlib
from datetime import datetime

# Setup path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
CORE_DIR = os.path.join(BACKEND_DIR, "core", "harborpilot_loop")
sys.path.insert(0, CORE_DIR)

def _load_anthro_modules(core_dir: str):
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    from anthropomorphic.integration import init_anthropomorphic_modules, _MEMORY_STORE
    from anthropomorphic.schema import MemoryItem
    return init_anthropomorphic_modules, _MEMORY_STORE, MemoryItem

def generate_memory_from_event(event: dict) -> dict:
    """
    Maps an event dictionary to memory fields.
    Returns None if event is not suitable for memory.
    """
    kind = str(event.get("kind") or "").lower()
    text = str(event.get("summary") or event.get("text") or "").strip()
    
    if not text or len(text) < 10:
        return None

    mem_kind = "info"
    importance = 3
    
    if kind == "error":
        mem_kind = "error"
        importance = 8
    elif kind == "observation":
        mem_kind = "observation"
        importance = 5
    elif kind == "summary":
        mem_kind = "info"
        importance = 3
    elif kind in ("warning", "risk"):
        mem_kind = "warning"
        importance = 6
    else:
        # Skip other low-level events
        return None
        
    # Create deterministic hash
    content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    
    # Handle timestamp
    ts = event.get("timestamp")
    if not ts:
        ts = datetime.now()
    elif isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            ts = datetime.now()
            
    return {
        "id": f"mem-bf-{content_hash[:8]}",
        "source_event_id": str(event.get("id") or ""),
        "step": int(event.get("step") or 0),
        "timestamp": ts,
        "role": str(event.get("actor") or "system").lower(),
        "type": mem_kind,
        "kind": mem_kind,
        "text": text,
        "importance": importance,
        "keywords": [], # Keyword extraction is expensive/complex here; rely on text
        "hash": content_hash
    }

def main():
    parser = argparse.ArgumentParser(description="Backfill memories from events.jsonl")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--events-path", default=".harborpilot/runtime/events.jsonl")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    workspace = os.path.abspath(args.workspace)
    events_path = args.events_path
    if not os.path.isabs(events_path):
        events_path = os.path.join(workspace, events_path)
        
    if not os.path.exists(events_path):
        print(f"Events file not found: {events_path}")
        return 1
        
    print(f"Initializing modules in {workspace}...")
    init_anthropomorphic_modules, memory_store, MemoryItem = _load_anthro_modules(CORE_DIR)
    init_anthropomorphic_modules(workspace)
    
    # Load existing source IDs
    existing_ids = set()
    if memory_store.memories:
        for m in memory_store.memories:
            if m.source_event_id:
                existing_ids.add(m.source_event_id)
    
    print(f"Found {len(existing_ids)} existing memories from events.")
    
    new_count = 0
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                evt_id = str(event.get("id") or "")
                
                # If event has no ID, we can't reliably dedup against it, 
                # unless we hash the content. But let's require ID or skip if strict.
                # If we backfill old events without IDs, we might duplicate on re-run.
                # We'll skip empty IDs for safety.
                if not evt_id or evt_id in existing_ids:
                    continue
                
                mem_data = generate_memory_from_event(event)
                if mem_data:
                    item = MemoryItem(**mem_data)
                    if not args.dry_run:
                        memory_store.append(item)
                    new_count += 1
                    # Update local set to prevent duplicate within same file run
                    existing_ids.add(evt_id)
                    
            except Exception as exc:
                print(f"Skipping line due to error: {exc}")
                continue
                
    if args.dry_run:
        print(f"[Dry Run] Would generate {new_count} new memories.")
    else:
        print(f"Successfully generated {new_count} new memories.")

if __name__ == "__main__":
    sys.exit(main())
