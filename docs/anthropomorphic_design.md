# Anthropomorphic Architecture Design

This document outlines the integration of cognitive architecture concepts from *Generative Agents* into HarborPilot, strictly adhering to engineering constraints like traceability, replayability, and append-only immutability.

## 1. Core Architecture

### 1.1 Module Mapping & Abstraction

We introduce a dedicated `anthropomorphic` module to encapsulate cognitive features.

| Concept | HarborPilot Impl | Responsibility |
| :--- | :--- | :--- |
| **Truth Source** | `events.jsonl` | Immutable, append-only raw log of all system actions. **MUST** include stable UUIDs. |
| **Memory Stream** | `MEMORY.jsonl` | Derived stream. Enriched/Compressed representation of events with embedding and importance. |
| **Reflection** | `REFLECTIONS.jsonl` | Derived stream. Higher-level insights and heuristics generated from memories. |
| **Reflection Logic**| `reflection_module` | `Scheduler` (When), `Generator` (How), `Store` (Persistence). |
| **Retrieval** | `memory_store` | Complex scoring (Relevance/Recency/Importance) + Diversity Filtering. |

### 1.2 Persistence Strategy (The "Derivation" Rule)
To maintain the "Truth Source" invariant:
1.  **`events.jsonl`**: The **only** source of truth. Every event MUST have a pre-generated, deterministic UUID (`event_id`).
2.  **`MEMORY.jsonl` / `REFLECTIONS.jsonl`**: Strictly derived.
    *   **Online Path (Fast)**: As events occur, they are immediately processed (rule-based keywords/importance) and appended to `MEMORY.jsonl`.
    *   **Offline Path (Rebuild)**: A cleanup utility can delete derived logs and rebuild them purely from `events.jsonl`.
3.  **Embedding Consistency**: Embeddings are computed ONCE at MemoryItem creation. `embedding_id` MUST equal `memory_id` (1:1 mapping). If missing, rebuilds can regenerate them.

## 2. Schema Definitions

### 2.1 Memory Item (`MEMORY.jsonl`)

Enriched representation of an event.

```python
class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: f"mem_{uuid4()}")
    source_event_id: str  # Stable UUID from events.jsonl
    step: int             # Canonical clock: Global Event Sequence (0, 1, 2...)
    timestamp: datetime
    role: str             # PM / Director / QA
    
    type: str             # observation / plan / reflection_summary
    kind: str             # error | info | success | warning | debug (Severity)
    
    text: str             # Natural language content
    importance: int       # 1-10
    keywords: List[str]
    hash: str             # SHA1(text + type + role + context) for deduplication
    
    context: Dict[str, Any] # { "run_id": "...", "phase": "..." }
    # embedding_id is implicitly self.id
```

### 2.2 Reflection Node (`REFLECTIONS.jsonl`)

Heuristics or summaries derived from memories.

```python
class ReflectionNode(BaseModel):
    id: str = Field(default_factory=lambda: f"ref_{uuid4()}")
    created_step: int
    expiry_steps: int     # How long this insight remains valid (Decay)
    
    type: str             # heuristic / summary / preference
    scope: List[str]      # e.g., ["npm", "network"] - limits applicability
    confidence: float     # 0.0 - 1.0
    
    text: str
    evidence_mem_ids: List[str] # Back-links to memories that formed this
    importance: int
```

### 2.3 Prompt Context Event (`events.jsonl`)

Logged *before* every LLM call to ensure observability.

```json
{
  "kind": "observation",
  "type": "prompt_context",
  "content": {
    "run_id": "current_run_123",
    "phase": "director.execution",
    "step": 456, // Global sequence number
    "persona_id": "director.v1",
    "retrieved_mem_ids": ["mem_A", "mem_B"],
    "retrieved_ref_ids": ["ref_X"],
    "strategy": "vector_similarity",
    "token_usage_estimate": 850
  }
}
```

## 3. Interfaces

### 3.1 Reflection Module

```python
class ReflectionScheduler:
    def should_reflect(self, context: Context) -> bool:
        """
        Triggers:
        - Every N steps (e.g., 50)
        - Error rate > Threshold
        - Consecutive failures >= 3
        """
        pass

class ReflectionGenerator:
    def generate(self, memories: List[MemoryItem], objective: str) -> List[ReflectionNode]:
        """Calls LLM to abstract insights."""
        pass
```

## 4. Retrieval Logic

### 4.1 Scoring Formula

$$ Score = w_{rel} \cdot Tier2Rel(q, m) + w_{rec} \cdot e^{\frac{-(current\_step - m.step)}{\tau}} + w_{imp} \cdot \frac{Imp}{10} $$

*   **Step Clock**: Recency uses `global_event_seq`, ensuring all modules share one timeline.
*   **Relevance**: 
    *   *Tier 1 (Vector)*: Cosine Similarity.
    *   *Tier 2 (Keyword)*: Jaccard/BM25 (fallback if vector DB unavailable).

### 4.2 Candidate Pruning & Diversity

1.  **Deduplication**: Filter by `hash` (prevent identical log entries).
2.  **Diversity Rule (Based on `kind`)**:
    *   `error`: Max 5 items
    *   `info`: Max 3 items
    *   `success`: Max 3 items
    *   Others: Max 2 items

## 5. Integration Guardrails

### 5.1 Token Budget (Hard Limits)

To prevent context overflow:

*   **Total Injection Budget**: Max 1200 Tokens
*   **Per-Item Limits**:
    *   Persona: ≤ 120 tokens
    *   Memories (Top-K): ≤ 10 items, each ≤ 200 chars
    *   Reflections: ≤ 3 items, each ≤ 240 chars

### 5.2 Prompt Ordering (MUST)

1.  **System/Persona**: "You are [Role]..."
2.  **Contract (IMMUTABLE)**: "Your Goal is X. Acceptance Criteria are Y."
3.  **Relevant Memories**: "Relevant past experiences (Time relative to step X):..."
4.  **Current State**: "Current step is..."
5.  **Output Format / Invariants**: JSON Schema enforcement.

### 5.3 Fallbacks
*   If Vector DB fails -> Keyword Search.
*   If Persona missing -> Standard Assistant.
