I will implement atomic file writing and improve JSONL appending with run-based directory bucketing to enhance system stability and data integrity.

1. **Refactor** **`io_utils.py`**:

   * Review `write_text_atomic` and `write_json_atomic` to ensure they correctly use the write-temp-then-rename pattern, which is already present but needs verification for Windows compatibility (using `os.replace` which is atomic on POSIX and mostly atomic on Windows Python 3.3+).

   * Enhance `resolve_artifact_path` or introduce a new `resolve_run_path(run_id, filename)` helper to support the `state/runs/<run_id>/` directory structure.

   * Update `append_jsonl_atomic` (and the buffered version) to support writing to run-specific paths while maintaining the global `.harborpilot/ollama/events.jsonl` as a symlink or a "latest" copy if needed, OR fully migrate to run-specific event logs. Given the "Truth Stream" invariant, splitting `events.jsonl` by run is cleaner. I will modify it to write to `state/runs/<run_id>/events.jsonl`.

2. **Update Loop Logic to Use Run Buckets**:

   * Modify `loop-director.py` and `loop-pm.py` to utilize the new run-specific paths for `events.jsonl`, `DIRECTOR_RESULT.json`, and other artifacts.

   * Ensure that when a new run starts, it creates the directory `state/runs/<run_id>/`.

3. **Maintain "Latest" Pointer**:

   * In `io_utils.py`, add a function `update_latest_link(run_id)` that creates or updates a symlink (or a `latest_run.json` file containing the path on Windows where symlinks might require admin privileges) pointing to the current run directory. This allows the Dashboard to easily find the latest active session.

4. **Verify JSONL Locking**:

   * `io_utils.py` already has file locking (`_acquire_lock`). I will double-check its robustness for the run-specific files, although contention should be lower there.

5. **Dashboard Compatibility (Note)**:

   * The Dashboard currently reads from fixed paths like `.harborpilot/ollama/events.jsonl`. I will need to ensure backward compatibility or update the Dashboard's reading logic (which is out of scope for this CLI-focused plan, but I will ensure the *old* paths are still updated or symlinked if possible, or provide a clear migration path). *Correction*: I will implement the "latest pointer" strategy so the Dashboard can eventually be updated to follow it, but for now, I might keep writing to the central file *or* purely rely on the split. The user's prompt suggests "Directory按 run\_id 分桶" is the goal. I will proceed with splitting.

6. **Refinement**:

   * `write_json_atomic` is already good.

   * `append_jsonl` needs to ensure the `seq` number is strictly increasing within a run. I'll check `events_schema.py` or the writer to ensure `seq` is managed correctly (likely state-held).

**Plan Execution Steps**:

1. Modify `io_utils.py`: Add `resolve_run_dir(run_id)`, `update_latest_pointer(run_id)`, and ensure atomic writes are robust.
2. Update `loop-director.py` & `loop-pm.py`: Use run-specific paths for artifacts.
3. Update `director_trajectory.py` etc.: Ensure they write to the correct run bucket.

