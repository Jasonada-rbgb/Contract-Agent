# Agent Feedback Log

This file is automatically populated by user feedback from the Warranty Contract Agent app.
Cursor reads this file to identify issues, plan fixes, and verify corrections.

---

### FB-20260326-chat-history
- **Status**: OPEN
- **Category**: Feature Request
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-26 11:15 UTC

**Description**:
The chat history should function like a standard LLM interface (ChatGPT, Claude, Gemini). Users need the ability to browse previous chat sessions, reopen them, and rename them for version control purposes. Currently conversations are lost when the session ends or the page is refreshed without clear navigation.

**Expected Behavior**:
- Sidebar or panel listing previous chat sessions by date/name
- Ability to click into any past session and view the full conversation
- Ability to rename sessions (e.g., "BMW warranty period check" instead of a UUID)
- Sessions persist across browser closes

**Actual Behavior**:
- Most recent session auto-restores but there is no way to browse or manage multiple past sessions
- No renaming capability
- No visible session list

---

### FB-20260326-inline-feedback
- **Status**: OPEN
- **Category**: UI Issue
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-26 11:15 UTC

**Description**:
The Feedback section is a separate mode in the sidebar, which is unintuitive. Users should be able to rate responses directly within the Contract Q&A page. After each AI response, users should see a rating mechanism and an optional text field to explain why they rated it that way. The separate Feedback page can remain for longer-form feedback, but the primary feedback path should be inline.

**Expected Behavior**:
- After each AI response in Q&A, show thumbs up/down plus an optional "Why?" text input
- When the user submits a rating with a comment, it gets logged with the full context (question, response, contract, user)
- The separate Feedback mode remains available for general suggestions

**Actual Behavior**:
- Thumbs up/down buttons exist but there is no way to add a comment explaining the rating
- The Feedback mode is a separate page that feels disconnected from the Q&A experience

---

### FB-20260326-thinking-process
- **Status**: OPEN
- **Category**: Feature Request
- **Severity**: Medium
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-26 11:15 UTC

**Description**:
When the Contract Q&A is processing a question, there is a pause while the AI thinks. This is expected and acceptable for accuracy. However, users should be able to see the AI's thinking process in real-time, similar to how thinking/reasoning models work on consumer LLM interfaces (Gemini, Claude, ChatGPT). This would let users verify that the retrieval and reasoning steps make sense and build trust in the output.

**Expected Behavior**:
- During the "Thinking..." phase, show a collapsible/expandable panel displaying the agent's step-by-step process
- Show which tools are being called (e.g., "Retrieving contract profile...", "Searching for relevant passages...", "Reranking results...")
- Show intermediate reasoning or retrieved passages as they come in
- Once the final answer is ready, the thinking panel collapses and the answer displays normally

**Actual Behavior**:
- A simple "Thinking..." spinner is shown with no visibility into what the agent is doing
- Tool calls are only visible after the response completes, inside expanders

---

