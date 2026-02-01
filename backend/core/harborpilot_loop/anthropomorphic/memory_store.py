import json
import math
import os
from datetime import datetime
from typing import List, Dict, Optional, Set
from pydantic import ValidationError

from .schema import MemoryItem
try:
    import lancedb
    import common
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False

from ollama_utils import get_embedding

EMBEDDING_MODEL = os.environ.get("HARBORPILOT_EMBEDDING_MODEL", "nomic-embed-text")


class MemoryStore:
    def __init__(self, memory_file: str):
        self.memory_file = memory_file
        self.memories: List[MemoryItem] = []
        self._load()

    def _load(self):
        """Loads memories from JSONL file."""
        if not os.path.exists(self.memory_file):
            return
        
        with open(self.memory_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # Convert timestamp back to datetime if string
                    if isinstance(data.get('timestamp'), str):
                        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                        
                    self.memories.append(MemoryItem(**data))
                    self.memories.append(MemoryItem(**data))
                except (json.JSONDecodeError, ValidationError):
                    # In a real system, we might log this as a warning
                    continue

        if LANCEDB_AVAILABLE:
            db_path = os.path.join(os.path.dirname(self.memory_file), "lancedb")
            self.db = lancedb.connect(db_path)
            # Create table if needed (schema inferred from data, or explicit)
            # We defer creation until first append to ensure we have data, 
            # or we create with a dummy if needed. 
            # For now, we'll check in append/retrieve using open_table with fallback.


    def append(self, item: MemoryItem):
        """Appends a memory item to the store and file."""
        self.memories.append(item)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        
        with open(self.memory_file, 'a', encoding='utf-8') as f:
            # Serialize with isoformat for datetime
            f.write(item.model_dump_json() + '\n')

        # Add to LanceDB
        if LANCEDB_AVAILABLE and item.text:
            vec = get_embedding(item.text, EMBEDDING_MODEL)
            if vec:
                # Prepare record
                record = item.model_dump()
                record["vector"] = vec
                # timestamp to str if datetime
                if isinstance(record.get("timestamp"), datetime):
                    record["timestamp"] = record["timestamp"].isoformat()
                
                try:
                    table = self.db.open_table("memories")
                    table.add([record])
                except Exception:
                    # Table might not exist
                    try:
                        self.db.create_table("memories", data=[record])
                    except Exception as e:
                        print(f"LanceDB error: {e}")


    def retrieve(self, query: str, current_step: int, top_k: int = 10, 
                 weights: Dict[str, float] = None) -> List[MemoryItem]:
        """
        Retrieves relevant memories based on scoring formula:
        Score = w_rel * Relevance + w_rec * Recency + w_imp * Importance
        """
        if not self.memories:
            return []
            
        weights = weights or {"rel": 0.5, "rec": 0.3, "imp": 0.2}
        
        scored_memories = []
        query_terms = set(query.lower().split())
        
        decay_tau = 10.0 # Steps for decay
        
        vector_hits = {}
        if LANCEDB_AVAILABLE:
            vec_query = get_embedding(query, EMBEDDING_MODEL)
            if vec_query:
                try:
                    table = self.db.open_table("memories")
                    results = table.search(vec_query).metric("cosine").limit(top_k * 2).to_list()
                    for r in results:
                        dist = r.get("_distance", 1.0)
                        sim = 1.0 - dist
                        vector_hits[r["id"]] = max(0.0, sim)
                except Exception:
                    pass

        for mem in self.memories:
            # 1. Relevance
            # Default to keyword Jaccard
            text = mem.text or ""
            kw = mem.keywords or []
            mem_terms = set(text.lower().split()) | set(kw)
            
            if not mem_terms:
                keyword_score = 0.0
            else:
                intersection = query_terms.intersection(mem_terms)
                union = query_terms.union(mem_terms)
                keyword_score = len(intersection) / len(union) if union else 0.0
            
            # Apply Vector Score if available
            vector_score = vector_hits.get(mem.id, 0.0)
            
            # Hybrid Score: Max of keyword or vector
            relevance = max(keyword_score, vector_score)
                
            # 2. Recency (Step-based exponential decay)
            delta_step = max(0, current_step - mem.step)
            recency = math.exp(-delta_step / decay_tau)
            
            # 3. Importance (Normalized 0-1)
            # Default to 0.5 importance if None/invalid, max 10
            imp_val = mem.importance
            if not isinstance(imp_val, (int, float)):
                imp_val = 5
            importance = min(max(imp_val, 1), 10) / 10.0
            
            score = (weights["rel"] * relevance) + \
                    (weights["rec"] * recency) + \
                    (weights["imp"] * importance)
            
            scored_memories.append((score, mem))
                
            
        # Sort by score descending
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        # Apply Pruning & Diversity
        return self._prune_candidates([m for s, m in scored_memories], top_k)

    def _prune_candidates(self, candidates: List[MemoryItem], limit: int) -> List[MemoryItem]:
        """
        Applies diversity rules:
        - Max 5 'error' items
        - Max 3 'info' items
        - Max 3 'success' items
        """
        counts = {"error": 0, "info": 0, "success": 0, "warning": 0, "debug": 0}
        limits = {"error": 5, "info": 3, "success": 3, "warning": 2, "debug": 1}
        
        final_list = []
        hashes_seen = set()
        
        for mem in candidates:
            if len(final_list) >= limit:
                break
                
            # Dedup
            if mem.hash in hashes_seen:
                continue
                
            # Diversity check
            kind = mem.kind.lower()
            if kind in limits:
                if counts[kind] >= limits[kind]:
                    continue
                counts[kind] += 1
            else:
                # Default limit for unknown kinds
                if counts.get("other", 0) >= 2: 
                    continue
                counts["other"] = counts.get("other", 0) + 1
                
            hashes_seen.add(mem.hash)
            final_list.append(mem)
            
        return final_list
            
    def retrieve_recent(self, since_step: int) -> List[MemoryItem]:
        """Retrieves memories created after the given step."""
        return [m for m in self.memories if m.step > since_step]

    def count_recent_errors(self, since_step: int) -> int:
        """Counts error memories created after the given step."""
        return sum(1 for m in self.memories if m.step > since_step and m.kind == "error")
