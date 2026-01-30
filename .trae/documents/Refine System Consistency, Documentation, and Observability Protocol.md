I will implement the requested improvements to enhance system consistency and executability.

### 1. Unified Path Truth
- **Update Documentation**: In `README.md` and `docs/reference.md`, explicitly define `<workspace>/state/ollama/` as the single source of truth for all run artifacts.
- **Visual Structure**: Add the directory tree diagram to `docs/reference.md` as requested.

### 2. Append-Only vs. Atomic Write
- **Clarify Boundaries**: In `docs/architecture.md`, strictly categorize files into:
  - **Append-only**: `events.jsonl`, `DIALOGUE.jsonl`.
  - **Atomic Replace**: `PM_TASKS.json`, `DIRECTOR_RESULT.json`, `trajectory.json`, `last_state.json`.
  - **Derived Views**: `RUNLOG.md`, `PM_REPORT.md` (rebuildable).

### 3. Director Multi-Role Constraints
- **Update Architecture**: In `docs/architecture.md`, clarify that multi-role simulation is "sequential perspective switching" within a single process, not concurrent agents, ensuring serializability and replayability.

### 4. Smart Dashboard Protocol
- **Define Protocol**: In `docs/architecture.md`, document the "Smart View Protocol":
  - **Card Model**: `status` (open/closed/errored), `confidence` (partial/parsed/heuristic), `parse_error`.
  - **UI Behavior**: Loading states vs. structured views.
  - **Closing Strategies**: Sentinel preemption, Timeouts (2s/5s), Max length protection (4000 lines).
  - **JSON Parsing**: Two-stage (Capture -> Tolerant Parse).
  - **Truncation**: Align UI warning with `truncated=true` field.

### 5. Structured Sentinels in Logs
- **Update Code**: Modify `director_exec.py` to emit structured sentinel lines in `RUNLOG.md` (e.g., `@@phase: TOOL_PLANNER begin`). This makes parsing robust.

### 6. JSON Schemas
- **Create Schema Files**: Create `schemas/` directory and add minimal schemas for:
  - `schemas/events.schema.json`
  - `schemas/pm_tasks.schema.json`
  - `schemas/dialogue.schema.json`
  - (Reuse existing `director_result.schema.json`)

### 7. Env Vars & Troubleshooting
- **Update Reference**: In `docs/reference.md`:
  - Add the requested Environment Variables table.
  - Add the Troubleshooting section (Dashboard tailing, RAMDISK paths, Port conflicts).

### 8. Sharpened Selling Point
- **Update README**: Add the "Contract-Driven Dual-Loop Agent" summary line at the top.

### Execution Order
1.  Update `README.md` (Selling point, path unification).
2.  Update `docs/architecture.md` (Write semantics, Multi-role, Smart View Protocol).
3.  Update `docs/reference.md` (Path structure, Env Vars, Troubleshooting).
4.  Create `schemas/*.json`.
5.  Update `director_exec.py` (Structured sentinels).