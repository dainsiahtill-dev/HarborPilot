# HarborPilot Bug Fix Protocol

## 1. Locate (3 Hops)
- Identify phase (PM / Director / QA / Docs).
- Find evidence (artifact/log/event).
- Pinpoint tool output (stderr/exception/command output).

## 2. Reproduce
- Create minimal repro (prefer `tests/repro/`).
- Capture expected vs actual.

## 3. Fix
- Apply change with smallest blast radius.
- Add tests around the regression.

## 4. Verify Invariants
- Did you modify `PM_TASKS.json`? (Forbidden)
- Did you delete lines from `events.jsonl`? (Forbidden)
- Does failure remain traceable in 3 hops?

## 5. Validate
- Run targeted tests.
- Confirm logs/events still align with evidence chain.
