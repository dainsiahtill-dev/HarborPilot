I will implement the refined documentation and protocol changes, incorporating the specific feedback on Windows compatibility, structured sentinels, and parsing robustness.

### 1. Unified Path Truth & Windows Compatibility

* **Documentation**: Define `workspace` as the target repo root.

* **Run Layout**: Document the specific layout with `runs/<run_id>/` and `latest.json` (pointer file, not symlink) to ensure Windows compatibility.

* **Match Mode**: Clarify that `latest` reads `latest.json` to find the run ID.

### 2. Append-Only vs. Atomic Write Semantics

* **Docs**: In `docs/architecture.md`, specify:

  * **Atomic Replace**: Use `write -> flush -> os.replace` pattern.

  * **Append-Only**: Newline-delimited JSON, never rewrite bytes, always end with `\n`.

  * **Invariant**: Only one executor mutates workspace per run (serializable).

### 3. Smart View Protocol (Wire Format)

* **Protocol Definition**: In `docs/architecture.md`, define the `@@hp` JSON sentinel grammar:

  * `@@hp {"kind":"phase", "state":"begin", ...}`

  * `@@hp {"kind":"block", "state":"begin", ...}`

* **Parsing Logic**: Describe the deterministic state machine (Sentinel -> Parse JSON -> Switch State; Else -> Raw Payload).

* **Closing Strategies**: Per-block timeout/max-length, sentinel preemption (mark partial).

### 4. Structured Sentinels Implementation

* **Code Update**: Modify `director_exec.py` to:

  * Emit `@@hp` sentinels in `RUNLOG.md`.

  * Emit corresponding lifecycle events in `events.jsonl` (e.g., `phase` events).

  * Ensure `latest.json` is written instead of (or alongside) symlinks on Windows.

### 5. JSON Schemas

* **Create Schemas**: Add `schemas/` with versioning (`schema_version`) and `additionalProperties: true`.

  * `events.schema.json`: Enforce `seq`, `ts`, `refs.run_id`, `kind`.

  * `pm_tasks.schema.json`

  * `director_result.schema.json`

### 6. Reference & Troubleshooting

* **Env Vars**: Add table.

* **Troubleshooting**: Add "Symptom -> Check -> Fix" format for Dashboard, RAMDISK, Ports.

### 7. Selling Point

* **README**: Update the opening summary with the "Contract-Driven Dual-Loop Agent" definition.

### Execution Order

1. **Update README** (Selling point, path truth).
2. **Update** **`docs/architecture.md`** (Write semantics, Smart View Protocol `@@hp`).
3. **Update** **`docs/reference.md`** (Layout, Env Vars, Troubleshooting).
4. **Create** **`schemas/*.json`**.
5. **Update** **`director_exec.py`** (Implement `@@hp` sentinels and `latest.json` logic).

