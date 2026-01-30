I will implement the 8 requested improvements to enhance system robustness and documentation clarity.

### 1. Documentation & Consistency
- **Fix Numbering**: Review and renumber sections in `README.md` and `docs/*.md` to ensure sequential 1..N order, moving any "New" sections to appropriate appendices or logical positions.
- **Clarify `state/ollama`**: Update documentation to emphasize `state/runs/` as the stable access pattern, reducing confusion around the legacy `ollama` backend naming.
- **RAMDISK FAQ**: Add a dedicated entry in `docs/reference.md` explaining the "no fallback" policy (to prevent path pollution) and providing a check command.
- **Match Mode**: Expand `director-match-mode` documentation in `docs/reference.md` to define `latest` (newest run), `run_id` (specific), `any` (first found), and `strict` (exact match only).
- **Policy Sources**: Add a concrete JSON example of `policy_sources` in `docs/reference.md` to demonstrate field-level granularity.

### 2. Schema & Data Structure
- **Schema Versioning**: 
  - Update `loop-director.py` to explicitly inject `"schema_version": 1` into `DIRECTOR_RESULT.json`.
  - (Note: `events` and `trajectory` already have this in their schema/generators).
- **Docs Template**: Create minimal template files `docs/README.md` and `docs/product/requirements.md` in the repository to guide new users.

### 3. Tooling Semantics
- **Standardize `tools.py`**: Refactor tool return values to include unified fields:
  - `duration_ms` (integer milliseconds)
  - `artifacts` (list, e.g., generated files)
  - `truncated` (boolean)
- **Update Event Logging**: Modify `director_exec.py` to capture these new fields from tool execution and record them in `events.jsonl`.

### Execution Order
1.  Update `tools.py` (Standardize outputs).
2.  Update `director_exec.py` (Propagate new tool fields to events).
3.  Update `loop-director.py` (Add schema_version).
4.  Create `docs/` template files.
5.  Update `README.md` and `docs/reference.md` (Numbering, FAQ, Match Mode, Policy Sources).