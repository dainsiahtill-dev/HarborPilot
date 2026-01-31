I will implement the interactive AGENTS.md generation workflow as requested.

**1. Add `agents_prompt` to Prompt Profiles**
I will add a new template `agents_prompt` to `prompts/generic.json` and `prompts/demo_ming_armada.json`. This prompt will instruct the LLM to generate the `AGENTS.md` content based on project documentation and user feedback.

**2. Modify `loops/loop-pm.py`**
I will update the `loop-pm.py` script to:
*   Update `maybe_generate_agents_draft` to use the LLM (Codex or Ollama) instead of simple text concatenation. It will:
    *   Load the `agents_prompt`.
    *   Render it with `docs_context` (from READMEs) and `feedback`.
    *   Invoke the configured backend (Ollama/Codex) to generate the content.
    *   Write the result to `.harborpilot/ollama/AGENTS.generated.md`.
*   Update `wait_for_agents_confirmation` to pass necessary arguments (backend configuration) to the generation function.
*   Update `run_once` to pass `args` to `wait_for_agents_confirmation`.

**3. Workflow Verification**
The modified workflow will be:
1.  PM starts and calls `wait_for_agents_confirmation`.
2.  If `AGENTS.md` is missing, it calls `maybe_generate_agents_draft`.
3.  The draft is generated using the LLM.
4.  PM emits a dialogue event prompting the user to confirm.
5.  PM waits.
6.  If the user provides feedback (updating `AGENTS.feedback.md`), PM detects the change and regenerates the draft using the LLM + feedback.
7.  Once the user confirms (creating `AGENTS.md`), PM proceeds.
