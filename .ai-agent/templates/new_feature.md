# HarborPilot New Feature Template

## 0. Guardrails
- Preserve invariants (see `docs/agent/invariants.md`).
- UI remains read-only for execution decisions.

## 1. Definition
- Feature name:
- User-facing outcome:
- Acceptance criteria:

## 2. Impacted Areas
- Backend routes/services:
- Core loop / invariants:
- Schemas:
- UI components:

## 3. Data Contracts
- Update schema files if new fields are introduced.
- Add descriptions/examples to new schema fields.

## 4. Implementation Steps
1. Backend API + data model
2. Service layer integration
3. UI wiring + display
4. Telemetry/events (if needed)

## 5. Validation
- Targeted tests (backend + frontend)
- Manual sanity checks
- Invariant check if runtime artifacts touched

## 6. Docs
- Update `docs/agent/reference.md` if new artifacts added.
