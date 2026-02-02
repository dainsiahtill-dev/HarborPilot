# HarborPilot AI Context

This file is the human-friendly companion to `.ai-agent/context.json`. It is designed
to give a fast, accurate mental model before editing.

## What HarborPilot Is
- A local-first, fixed-cost, unattended automation programming command center.
- Two main loops: PM (plans/contracts) -> Director (executes/validates) -> QA -> UI.
- Mission Control UI is read-only for execution decisions (observability first).

## Golden Invariants (Do Not Break)
1. Contract immutable: `PM_TASKS.json` goal/acceptance_criteria cannot be modified by execution; only evidence appended.
2. Events append-only: `events.jsonl` must never be rewritten or truncated.
3. Run id globally unique across artifacts and references.
4. UI read-only for execution decisions.
5. Replayable: events + trajectory + artifacts reconstruct runs.
6. Failure traceable (3 hops): Phase -> Evidence -> Tool Output.
7. Atomic writes for critical state files (tmp + rename).
8. Memory/reflection must be evidence-backed (refs).

Full details: `docs/agent/invariants.md`.

## High-Level Flow
- PM Loop creates contract: `backend/scripts/loop-pm.py` -> `.harborpilot/runtime/PM_TASKS.json`
- Director Loop executes contract: `backend/scripts/loop-director.py`
- QA + results: `.harborpilot/runtime/QA_RESPONSE.md`, `.harborpilot/runtime/DIRECTOR_RESULT.json`
- Events + replay: `.harborpilot/runtime/events.jsonl` + `trajectory.json`

## Entry Points
- Backend API: `backend/app/main.py`
- Frontend UI: `frontend/src/app/App.tsx`
- Electron shell: `electron/main.cjs`

## Schemas (Source of Truth)
- `schema/pm_tasks.schema.json`
- `schema/director_result.schema.json`
- `schema/event.schema.json`
- `schema/trajectory.schema.json`
- `schema/interventions.schema.json`

## Preferred Docs
- Agent overview: `docs/agent/README.md`
- Architecture map: `docs/agent/architecture.md`
- Reference index: `docs/agent/reference.md`
- Human docs: `docs/human/README.md`

## Practical Guidance For AI Changes
- Preserve invariants. If a change touches runtime artifacts, re-check invariants.
- Avoid editing `PM_TASKS.json`, `events.jsonl`, or other runtime artifacts directly.
- Prefer atomic write helpers (tmp + rename) for state files.
- Keep errors traceable: if you catch exceptions, log/emit evidence with phase + tool output.
- UI is for observability; do not add write paths that bypass loops.

## Suggested Validation
- Backend: `pytest` (see `TESTING.md`)
- Frontend: `npm run test` (vitest)
