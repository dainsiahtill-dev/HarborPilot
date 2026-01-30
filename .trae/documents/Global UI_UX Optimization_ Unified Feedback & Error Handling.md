I will implement a global UI/UX optimization plan focusing on unified feedback and error handling.

**1. Unified Notification System (Toast Integration)**
I will modify `desktop/frontend/src/app/App.tsx` to replace or augment disparate error handling with `sonner` Toasts:
*   **Workspace Operations**: Add `toast.error` to `handlePickWorkspace` and `handleOpenWorkspace` to replace silent console errors.
*   **Settings**: Add `toast.success("Settings saved")` to `saveSettings` and `toast.error` for failures.
*   **Ollama Control**: Add `toast.success` / `toast.error` to `stopOllamaModels`.
*   **PM/Director Actions**: Add `toast.error` for immediate feedback on start/stop failures, while keeping the detailed logs/banners for deep debugging.

**2. Optimize Blocking Alerts**
*   **LanceDB/Agents Checks**: Refactor `togglePm` and `toggleDirector` to use `toast.warning` instead of the heavy `AlertDialog` for missing dependencies, as the `ControlPanel` already provides visual cues (disabled buttons/tooltips). This reduces interruptive popups.

**3. Error Content Refinement**
*   **Director Start Failure**: Simplify the `AlertDialog` content to show a user-friendly summary, moving the raw log tail to the Logs modal (which is already being opened).

**4. Verification**
*   The plan involves editing `App.tsx` to insert these `toast` calls and refactor the `setErrorDialogTitle` logic.

This consolidates the user experience, ensuring that every action has a clear, non-blocking visual response.