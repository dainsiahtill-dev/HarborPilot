I will implement the fixes for the high-priority bugs identified in the documentation and confirmed by code analysis.

1.  **Backend Performance Fix (`desktop/backend/server.py`)**:
    *   Rewrite `read_file_tail` to use a list of chunks instead of string concatenation (`data = chunk + data`), which caused memory issues with large files.
    *   Optimize the newline counting to avoid scanning the entire growing buffer repeatedly.

2.  **Frontend Connection Reliability Fix (`desktop/frontend/src/api.ts` & `App.tsx`)**:
    *   Update `connectWebSocket` in `api.ts` to accept a `forceRefresh` parameter.
    *   Export `clearBackendInfoCache` or handle clearing internally when `forceRefresh` is true.
    *   Update `App.tsx` to use `forceRefresh=true` when reconnecting after a WebSocket error, ensuring it picks up new backend ports/tokens if the backend restarted.

3.  **Verification**:
    *   The other bugs mentioned in the documentation (Director start/stop silence, DialoguePanel success rate, FileViewer badge) appear to be already fixed or outdated based on the current code. I will not modify them unless I find specific regressions during implementation.

I will proceed with editing `desktop/backend/server.py`, `desktop/frontend/src/api.ts`, and `desktop/frontend/src/app/App.tsx`.