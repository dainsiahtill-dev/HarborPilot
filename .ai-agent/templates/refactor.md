# HarborPilot Refactor Template

## 0. Guardrails
- Preserve invariants (see `docs/agent/invariants.md`).
- No direct edits to runtime artifacts.

## 1. Intent
- Why refactor? (perf / maintainability / safety / clarity)
- What is the expected behavioral delta? (ideally none)

## 2. Map
- Identify entry points, call graph, and data contracts.
- Note any schema dependencies.

## 3. Plan
- List steps in small, reversible increments.
- Define rollback points.

## 4. Implement
- Apply refactor step-by-step.
- Add/adjust tests if behavior is affected.

## 5. Verify
- Run targeted tests.
- Recheck invariants if artifacts or state IO touched.

## 6. Document
- Update docs if module boundaries or APIs changed.
