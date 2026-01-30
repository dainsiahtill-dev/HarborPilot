I will update the documentation to reflect the latest schema changes, specifically:

1.  **Update `docs/architecture.md`**:
    -   **`events.jsonl` Schema**: Add `duration_ms`, `truncated`, and `artifacts` to the observation schema description.
    -   **`DIRECTOR_RESULT.json` Schema**: Add `schema_version`, `failure_code`, and `patch_risk.factors` (files_changed_count, lines_added, etc.) to the description.

2.  **Update `docs/reference.md`**:
    -   Add a new section **"2.1 结果文件详解 (Result Schema)"** under "Run Artifacts" to detail the structure of `DIRECTOR_RESULT.json`, explaining `failure_code` categories (e.g., `QA_FAIL`, `RISK_BLOCKED`) and risk scoring factors.

This ensures the documentation matches the actual code implementation.