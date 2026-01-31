I will reorganize the documentation to improve accessibility and maintainability, following the "facade" approach.

### 1. Simplify `README.md`
- **Goal**: Create a 10-minute onboarding guide.
- **Content**:
  - **Introduction**: 1 sentence + ASCII link diagram (PM -> Director -> QA).
  - **Quick Start**: Dashboard command and CLI commands.
  - **Artifacts**: Where to find results (`.harborpilot/runtime/`) and what they are.
  - **System Invariants**: Keep the 6 key invariants (high value).
  - **Links**: Clear pointers to Architecture, Reference, etc.
- **Action**: Move detailed sections (Architecture details, full CLI args, tools list) to `docs/`.

### 2. Update `docs/architecture.md`
- **Goal**: Deep dive for engineers.
- **Content**:
  - **State Machines**: PM Loop & Director Loop flows.
  - **Event Model**: Truth (Events) vs Projection (Dialogue/Logs).
  - **Concurrency**: Atomic writes, RAMDISK rationale.
  - **Smart View**: Streaming parser details (Sentinels, State Machine).
- **Action**: Ensure existing content is structured under these headers.

### 3. Update `docs/reference.md`
- **Goal**: Comprehensive dictionary.
- **Content**:
  - **Directory Structure**: Full tree layout.
  - **CLI Arguments**: Complete tables for PM and Director.
  - **Tools List**: Full list of `tools.py` capabilities.
  - **Artifacts**: Detailed schema descriptions (including `DIRECTOR_RESULT.json` failure codes).
  - **FAQ**: RAMDISK, Match Mode, Policy Sources.
- **Action**: Consolidate technical details here.

### Execution Steps
1.  **Refactor `README.md`**: Cut heavily, keeping only the "Facade" content.
2.  **Verify `docs/architecture.md`**: Ensure moved content is present and well-structured.
3.  **Verify `docs/reference.md`**: Ensure all technical references are complete.
4.  **Check Links**: Verify all relative links between documents are correct.