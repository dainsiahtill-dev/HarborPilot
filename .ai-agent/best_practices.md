# HarborPilot AI Best Practices

This file captures AI-specific do's and don'ts. Follow it when editing.

## Do
- Treat `PM_TASKS.json` as immutable contract (goal/AC never modified by execution).
- Keep `events.jsonl` append-only. Add new events; never rewrite history.
- Maintain 3-hops traceability: Phase -> Evidence -> Tool Output.
- Use atomic writes for critical state files (tmp file then rename).
- Prefer schema-backed changes; update schemas when data shape changes.
- Keep UI read-only for execution decisions; loops perform execution.
- When handling exceptions, preserve evidence and emit or log an error event.

## Do Not
- Do not edit runtime artifacts directly (`.harborpilot/runtime/*`) except via code paths.
- Do not modify `PM_TASKS.json` goal/acceptance_criteria in Director or UI.
- Do not truncate or rewrite `events.jsonl`.
- Do not remove run_id linkage between artifacts and events.
- Do not bypass the loops by writing execution results directly in UI.

## When Debugging (3 Hops)
1. Identify phase (PM / Director / QA / Docs).
2. Locate evidence (artifact, event, or log).
3. Pinpoint tool output (stderr / exception / command output).

## Code Navigation Hints
- PM loop: `backend/scripts/loop-pm.py`
- Director loop: `backend/scripts/loop-director.py`
- Invariants: `backend/core/harborpilot_loop/invariant_sentinel.py`
- IO + artifacts: `backend/core/harborpilot_loop/io_utils.py`
- UI main: `frontend/src/app/App.tsx`
