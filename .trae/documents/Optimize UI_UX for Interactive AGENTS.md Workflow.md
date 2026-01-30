I will optimize the frontend UI/UX for the interactive AGENTS.md generation workflow.

**1. Enhance** **`App.tsx`**
I will modify `desktop/frontend/src/app/App.tsx` to:

* Import `toast` from `sonner` and the `Toaster` component.

* Add the `<Toaster />` component to the application layout to enable toast notifications.

* Update `saveAgentsFeedback` to show a toast notification ("Feedback submitted, regenerating...") when the user saves feedback. This provides immediate visual confirmation before the dialog closes.

* Update the `AlertDialog` for AGENTS.md review:

  * Increase the preview area height from `max-h-64` to `h-[60vh]` to make reading the draft easier.

  * Update the "Save Feedback" button text to "提交反馈 (将重生成)" (Submit Feedback (Will Regenerate)) to clarify the action.

  * Update the dialog description to explicitly state that the window will close and re-open after regeneration.

**2. Verify Workflow**
The optimized flow will be:

1. Dialog appears with draft.
2. User enters feedback and clicks "Submit Feedback".
3. Toast appears: "Feedback submitted...".
4. Dialog closes (preventing interaction during regeneration).
5. Backend regenerates draft.
6. Frontend detects new draft (via `mtime` change) and re-opens the dialog automatically.

