# Agent Feedback Log

This file is automatically populated by user feedback from the Warranty Contract Agent app.
Cursor reads this file to identify issues, plan fixes, and verify corrections.

## Orchestrator Lifecycle Model

Canonical statuses:
- `OPEN`
- `IN_PROGRESS`
- `IMPLEMENTED_PENDING_DEPLOY`
- `VERIFIED`
- `BLOCKED_CODE`
- `BLOCKED_ENV`
- `BLOCKED_SPEC`
- `BLOCKED_HUMAN`

Machine fields used by the harness:
- `Last Attempt Run ID`
- `Last Decision`
- `Blocker Classification`
- `Retry Count`
- `Evidence`
- `Last Updated`

Transition rules:
- Use `IN_PROGRESS` when an item is actively claimed for a remediation cycle.
- Use `IMPLEMENTED_PENDING_DEPLOY` when code changes are complete but fresh deploy-backed verification is still outstanding.
- Use `VERIFIED` only after deploy-backed evidence or the required non-live evidence is complete.
- Use `BLOCKED_CODE` only for code-fixable blockers that may be retried later.
- Use `BLOCKED_ENV`, `BLOCKED_SPEC`, or `BLOCKED_HUMAN` for blockers that should halt automated retries.

Legacy status mapping:
- `IMPLEMENTED (pending deploy + QA)` -> `IMPLEMENTED_PENDING_DEPLOY`
- `FIXED (pending deploy)` -> `IMPLEMENTED_PENDING_DEPLOY`
- `IMPLEMENTED (deployed)` -> `VERIFIED`
- `FIXED` -> `VERIFIED`

---

### FB-20260330-thinking-trace-visibility
- **Status**: VERIFIED
- **Category**: UX / Transparency
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-30 14:05 UTC

**Description**:
When querying contracts in Contract Q&A, users still cannot clearly follow the model's live thinking process. Compared to consumer LLM interfaces (for example Grok), the reasoning stream is not visible enough for users to understand the step-by-step process while generation is in progress.

**Steps to Reproduce**:
1. Open Contract Q&A mode
2. Select a contract and ask a question
3. Observe the UI during the "Thinking..." phase

**Expected Behavior**:
- A clear live thinking panel shows step-by-step tool/reasoning progress during generation
- The panel remains easy to follow in real time
- Final answer appears in chat without requiring users to inspect hidden UI state

**Actual Behavior**:
- Thinking details are not visible as a first-class live reasoning view
- Users cannot clearly follow the process while waiting for completion

**Suggested Fix**:
- Add a dedicated live "Thinking" stream panel/expander with progressive updates
- Keep this panel separate from final answer rendering

---

### FB-20260330-answer-hidden-under-done
- **Status**: VERIFIED
- **Category**: UI Bug
- **Severity**: Critical
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-30 14:05 UTC
- **Last Attempt Run ID**: feedback-cycle-20260408
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 1
- **Evidence**: C:\Users\ADJ1DE\Documents\Agent Workflow\ai\orchestrator\runs\feedback-cycle-20260408\deploy-provenance.json
- **Last Updated**: 2026-04-08T12:55:00+00:00

**Description**:
After asking a question, the answer appears tied to the status container ("Done") and requires dropdown interaction. This is counter-intuitive. The answer should auto-appear directly in the prompt/chat output area, while dropdown behavior should be reserved for live thinking details only.

**Steps to Reproduce**:
1. Ask any question in Contract Q&A
2. Wait until the status shows "Done"
3. Observe that answer visibility requires interaction with the status/dropdown area

**Expected Behavior**:
- Final answer auto-renders directly in the chat output
- "Done" / status area is only for process/thinking trace, not for primary answer visibility

**Actual Behavior**:
- Answer is effectively hidden behind Done/status interaction
- User must click/expand to reliably view response
- Confirmed HTML structure causing this (as of 2026-03-27):
  ```html
  <div class="st-emotion-cache-11fa8fd ewmru5c3">
    <div data-testid="stMarkdownContainer" class="st-emotion-cache-1rsqh2s ey36t7e0">
      <p>Done</p>
    </div>
  </div>
  ```
  The entire answer is inside this collapsed container; user must click "Done" to reveal it.

**Suggested Fix**:
- Decouple final answer rendering from `st.status` container lifecycle
- Always render final answer in assistant message region immediately on completion
- The `st.status` container should only wrap the thinking/progress trace, never the final answer

---
### FB-20260330-history-autosave-clarity
- **Status**: VERIFIED
- **Category**: UX
- **Severity**: Medium
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-30 14:05 UTC

**Description**:
Conversation history exists but the save/retrieval behavior is unclear to users. There is no explicit confidence that chats are being auto-saved, and users do not have clear guidance on how entries appear in history.

**Steps to Reproduce**:
1. Ask multiple questions in a session
2. Navigate to Chat History
3. Try to confirm whether the current chat is saved and how to retrieve/manage it

**Expected Behavior**:
- Auto-save is explicit and visible (for example "Auto-saved" indicator)
- Current session appears clearly in history list without ambiguity
- Retrieval flow is straightforward and discoverable

**Actual Behavior**:
- Save behavior is unclear
- Retrieval/discoverability feels inconsistent from user perspective

**Suggested Fix**:
- Add explicit auto-save status indicator in the chat UI
- Improve history UX labels/actions for load/rename/current-session state

---

### FB-20260326-chat-history
- **Status**: VERIFIED
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
- **Status**: VERIFIED
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
- **Status**: VERIFIED
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

### FB-20260327-thinking-not-streaming-live
- **Status**: VERIFIED
- **Category**: UX / Transparency
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-27 14:45 UTC

**Description**:
When a prompt is submitted in Contract Q&A, the thinking/reasoning process is not streamed as live visible text. Other thinking AI interfaces (Claude, ChatGPT, Gemini, Grok) display the model's reasoning as a real-time text stream so the user can read along while the model works. The Warranty Contract Agent does not do this -- the user sees no live text during the thinking phase, only a static indicator.

**Steps to Reproduce**:
1. Open Contract Q&A, select a contract
2. Submit a question
3. Watch the UI during the thinking/processing phase

**Expected Behavior**:
- The thinking panel streams live text showing the model's reasoning steps as they are generated
- Users can read the thinking text in real time, similar to consumer LLM interfaces
- This gives the user confidence the system is working and lets them follow the logic

**Actual Behavior**:
- No live text is streamed during the thinking phase
- The user sees a static "Thinking..." indicator with no readable content until the response completes

**Suggested Fix**:
- Stream `thinking` / `reasoning` content from the model response in real time into the thinking expander
- Use `st.write_stream` or incremental markdown rendering to display reasoning tokens as they arrive
- Keep thinking text inside a collapsible expander so it doesn't overwhelm the final answer

---

### FB-20260327-thinking-tokens-in-response
- **Status**: VERIFIED
- **Category**: UI Bug
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-27 14:45 UTC

**Description**:
The model's internal "thinking" content (reasoning tokens / chain-of-thought) is appearing in the final user-facing response output. This internal reasoning should never be shown in the answer area -- it should only appear in the dedicated thinking/reasoning panel. The final answer should contain only the clean, user-facing response text with citations and evidence.

**Steps to Reproduce**:
1. Ask any question in Contract Q&A
2. Wait for the response to complete
3. Observe that thinking/reasoning content from the model is visible in the answer output

**Expected Behavior**:
- The final answer contains only the clean response: answer text, citations, and evidence excerpts
- Model thinking/reasoning tokens are filtered out of the answer and only shown in the thinking panel
- No raw chain-of-thought or internal reasoning appears in the user-facing answer

**Actual Behavior**:
- Thinking/reasoning content from the model leaks into the final response area
- Users see internal model reasoning mixed with the actual answer

**Suggested Fix**:
- Filter `thinking` / `reasoning` content blocks from the final response before rendering
- Route thinking tokens exclusively to the thinking expander panel
- Ensure only `text` type content blocks are rendered in the assistant answer area

---

### FB-20260327-tool-calls-in-response
- **Status**: VERIFIED
- **Category**: UI Bug
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-03-27 14:45 UTC

**Description**:
Tool call details (function names, parameters, raw tool outputs) are appearing in the user-facing response. Internal tool orchestration should be completely invisible to the end user in the final answer. Tool activity can optionally be shown in the thinking/progress panel, but must never appear in the answer area.

**Steps to Reproduce**:
1. Ask any question in Contract Q&A
2. Wait for the response to complete
3. Observe that tool call information (e.g., function names, JSON parameters, raw retrieval outputs) appears in the response

**Expected Behavior**:
- The final answer contains only the clean response text with citations and evidence
- Tool call details are completely hidden from the answer area
- Tool activity may optionally be shown in the thinking panel as progress indicators (e.g., "Searching contract..." not raw JSON)

**Actual Behavior**:
- Tool call names, parameters, and/or raw outputs are visible in the final answer area
- Users see internal orchestration details that are irrelevant and confusing

**Suggested Fix**:
- Filter all tool call content (function_call, tool_result, etc.) from the final rendered response
- Only render `text` type content blocks in the assistant answer area
- Optionally surface tool activity as human-readable progress messages in the thinking panel

---

### FB-20260402-markdown-first-output
- **Status**: VERIFIED
- **Category**: Feature / Output Quality
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-02 13:00 UTC

**Description**:
Q&A responses should render as consistently structured GitHub-flavored Markdown so the Streamlit UI displays them as properly formatted documents (headings, tables, bullets, bold) rather than raw prose. The old fixed "Evidence: / Answer:" format should be replaced with a markdown-first output contract.

**Expected Behavior**:
- Responses use ## headings (## Evidence, ## Answer, ## Comparison)
- Comparative questions produce Markdown pipe tables (max 5 columns)
- Wide or nuanced comparisons fall back to labeled bullet sections
- Inline [n] citations are preserved in all formats
- "Not found in provided documents" behavior unchanged

**Implementation Notes**:
- Agent instructions updated in `agent_server/agent.py` (create_agent)
- Centralized `_render_assistant_md()` helper added to `streamlit_app.py`
- All assistant output paths now route through the helper

---

### FB-20260402-model-endpoint-migration
- **Status**: VERIFIED
- **Category**: Infrastructure
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-02 10:00 UTC

**Description**:
The primary LLM endpoint was changed from `databricks-claude-opus-4-8` (which is a Databricks-hosted endpoint that cannot be queried from the app's serving path) to a non-Databricks endpoint. After testing multiple alternatives, `openai_gpt5` was selected as the default for `LLM_ENDPOINT` and `RERANK_ENDPOINT`. The `openai` dependency was also updated from `<2.0.0` to `>=2.8.0,<3.0.0` to resolve a `databricks-agents` / `litellm` compatibility conflict. Hardcoded `max_tokens` was removed from the general response path.

**Changes**:
- `app.yaml`: LLM_ENDPOINT and RERANK_ENDPOINT set to `openai_gpt5`
- `agent_server/agent.py`: default fallbacks updated, `_call_llm` no longer hardcodes max_tokens
- `pyproject.toml`: openai dependency updated to `>=2.8.0,<3.0.0`
- `_supports_temperature()` helper added for GPT-5 endpoint compatibility

**Verified**: Deployed and app running (deployment 01f12e933662187e9458f881fa223bac SUCCEEDED)

---

### FB-20260402-hidden-qa-council
- **Status**: VERIFIED
- **Category**: Feature / Accuracy
- **Severity**: Medium
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-02 14:00 UTC

**Description**:
A hidden internal council feature was added to improve Q&A answer quality. When enabled via `COUNCIL_ENABLED=true`, the system runs one shared retrieval pass, then fans out answer synthesis to multiple models (gemini_25_pro, gpt_41, openai_gpt5) in parallel. A chair model (gemini_25_pro) synthesizes the drafts into one final markdown answer, preserving only citation-backed claims and preferring narrower wording when drafts disagree.

**Key Design Decisions**:
- Feature-flagged off by default (COUNCIL_ENABLED env var)
- Shares one retrieval pass -- does NOT duplicate tool calls
- Chair synthesis, not majority voting
- Per-model drafts are never shown to users
- Council run logs saved to /Volumes/mdna_dev/warranty_agent_staging/council_logs/
- Claude endpoints excluded from first release due to Databricks invocation-path incompatibility

**Files**:
- `agent_server/council.py` (new module)
- `streamlit_app.py` (council integration in _run_agent_with_trace)
- `app.yaml` (COUNCIL_ENABLED env var, gemini_25_pro + gpt_41 resources)

---

### FB-20260402-browser-qa-headed-chrome
- **Status**: VERIFIED
- **Category**: DevOps / Testing
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-02 15:00 UTC

**Description**:
The browser-qa subagent was generating ad-hoc headless Playwright scripts that could not complete Databricks SSO authentication. This caused the /warranty-feedback-cycle pipeline to hang and fail silently at the QA stage. Additionally, Chrome 146 rejects the default user data directory for CDP remote debugging, and the previous QA run's `taskkill /F` left Chrome's crash sentinel set, causing a "Restore pages?" dialog on next launch.

**Fixes Applied**:
- `scripts/qa-test.js`: Default CHROME_USER_DATA changed to dedicated QA-Profile directory; crash sentinel cleared before launch; `--disable-session-crashed-bubble` and `--hide-crash-restore-bubble` flags added; response timeout bumped from 240s to 360s
- `.cursor/agents/browser-qa.md`: Mandates using `scripts/qa-test.js` (never custom scripts); documents SSO auth flow; documents QA-Profile requirement; documents result interpretation rules

---

### FB-20260407-qna-critical-path-timeout
- **Status**: VERIFIED
- **Category**: Reliability / Performance
- **Severity**: Critical
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:30 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 1
- **Evidence**: Deploy 01f133eee12217099a4ca0b61d4414a7 SUCCEEDED; Browser QA 31/33 pass, 0 fail, 2 warn; answer_visible_in_chat=PASS; response_completion=PASS; Q&A completed in 202.8s total test duration
- **Last Updated**: 2026-04-09T08:41:00+00:00

**Description**:
The latest production smoke test in `ai/reports/qa-smoke-2026-04-07.md` is blocked by the primary Contract Q&A flow timing out before completion. The app enters the thinking state, but the response does not fully complete within the 360-second QA timeout window. Because Q&A is the main user journey, this is currently a release blocker.

**Expected Behavior**:
- A single-contract Q&A question completes within the smoke-test timeout window
- The final answer renders fully in chat with the expected markdown structure and citations
- Inline feedback becomes available after the response finishes

**Actual Behavior**:
- The Q&A flow remained in the thinking state until the 360-second timeout expired
- The smoke report marked the run `BLOCKED` and did not reach multi-contract Q&A
- Inline feedback could not be validated because the response never fully completed

**Suggested Fix**:
- Add end-to-end timing instrumentation for retrieval, reranking, model call, and final UI render
- Reproduce with the same JLR smoke prompt and inspect app logs to isolate backend latency vs. Streamlit completion issues
- Add a hard failure mode or fallback response so the UI does not remain indefinitely in the thinking state

---

### FB-20260407-claims-row-specific-retrieval
- **Status**: VERIFIED
- **Category**: Accuracy / Claims
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:31 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: claims_batch.py:324-393 _build_claim_retrieval_queries + _retrieve_claim_passages; scope=row_aware when per-row queries exist
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
The Claims Evaluator currently builds one shared contract rule context per `(oem, contract_id)` and reuses it for every claim row in `agent_server/claims_batch.py`. This is efficient, but it increases the risk that row-specific rules, exclusions, component coverage, or market-specific passages are missing from the evidence packet used for an individual claim.

**Expected Behavior**:
- Each claim should be evaluated against context targeted to that row's market, component, mileage, dates, and any relevant exclusions
- The evaluator should retain the speed benefits of shared contract loading while still using row-aware retrieval where needed
- Final claim decisions should be backed by the most relevant contract passages for that specific row

**Actual Behavior**:
- A fixed set of broad rule queries is used once to build a shared context block for the whole batch
- The same contract passages are then reused for all rows, even when row details differ significantly
- Edge-case claims are more likely to fall into `requires_review`, `insufficient_info`, or an overly broad rule application

**Suggested Fix**:
- Keep the shared profile and base contract cache, but add per-row retrieval using mapped claim fields as additional query inputs
- Pull targeted evidence for market definitions, applicable component coverage, mileage limits, and exclusions before adjudicating each row
- Preserve citation references for the row-specific evidence so outputs remain auditable

---

### FB-20260407-profile-grounding-verification
- **Status**: VERIFIED
- **Category**: Accuracy / Retrieval
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:32 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: agent.py:625-698 _ground_contract_profile; citation-text-match verification per high-impact field; resets unsupported fields to defaults
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
The structured contract profile in `agent_server/agent.py` is extracted once by an LLM and then reused for query expansion, market interpretation, and claims evaluation. This improves usability, but if the profile extraction is wrong, incomplete, or stale, the error can propagate through multiple downstream flows.

**Expected Behavior**:
- Profile facts used for reasoning should be explicitly grounded in cited contract passages
- High-impact fields such as market definitions, warranty periods, mileage limits, and exclusions should be verifiable before they are treated as authoritative
- When evidence is weak or conflicting, the system should default to narrower wording rather than overcommitting

**Actual Behavior**:
- The profile is cached and can also be persisted for reuse
- Query expansion and claims adjudication depend on this profile even when there is no strong verification gate on the extracted fields
- A single extraction error can influence both retrieval behavior and final answer quality

**Suggested Fix**:
- Store citation-backed profile fields, not only extracted values
- Add validation or cross-check logic for high-impact fields before using them in claims or answer synthesis
- When profile facts are unsupported or conflict with retrieved passages, prefer direct passage evidence and narrower wording

---

### FB-20260407-evaluation-coverage-gaps
- **Status**: VERIFIED
- **Category**: Testing / Evaluation
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:33 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: eval_test_cases/jlr.json (JLR regression fixtures), eval_test_cases/claims_golden.json (claims golden dataset with expected decisions)
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
Current regression coverage does not yet match the product scope. The structured Q&A regression suite currently contains BMW fixtures, but no equivalent JLR fixture set was found in `eval_test_cases/`. There is also no comparable golden-path regression for Claims Evaluator outputs or contract ingestion, and the latest smoke test only validated Claims UI rendering rather than real claims decisions.

**Expected Behavior**:
- Regression coverage should include all currently supported OEMs, especially BMW and JLR
- Claims Evaluator should have at least one small golden CSV/XLSX fixture with expected output checks
- Ingest should have a sanity test that verifies OCR/chunk/embed output for a representative sample document
- Smoke tests should validate completed Q&A and at least one real claims evaluation path

**Actual Behavior**:
- Only `eval_test_cases/bmw.json` is present for structured Q&A regression
- The latest smoke report is blocked on Q&A and marks claims decisions as `N/A -- not exercised`
- Release confidence depends heavily on manual review and partial smoke coverage

**Suggested Fix**:
- Add JLR regression fixtures alongside BMW
- Add a small claims evaluation golden dataset with expected decisions and references
- Extend smoke coverage so it verifies both Q&A completion and actual claims outputs
- Add stronger assertions for citations and evidence quality, not just substring presence

---

### FB-20260407-chat-history-active-session-clarity
- **Status**: VERIFIED
- **Category**: UX
- **Severity**: Medium
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:34 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: streamlit_app.py:801-862 Active session has ▶ prefix, ✅ Active label, Selected caption, disabled Open when active, labeled rename targeting active chat
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
The chat history sidebar in `streamlit_app.py` can blur the distinction between the currently active session and the session currently highlighted in the dropdown. The rename input follows the active session, while the selectbox can point at a different session until `Load` is clicked. This makes the history flow feel less deterministic than standard LLM chat interfaces.

**Expected Behavior**:
- The active session and selected session should be visually and functionally unambiguous
- `Load`, `New Chat`, and `Rename current chat` should always act on clearly labeled state
- Users should not need to infer whether they are renaming the highlighted session or the already loaded session

**Actual Behavior**:
- The selected session in the dropdown can differ from the loaded session
- The rename field is tied to the current active session rather than the highlighted row
- This creates a small but real risk of confusion in session management

**Suggested Fix**:
- Add an explicit active-session indicator in the history UI
- Disable or relabel rename controls unless they clearly target the active session
- Make the selection/load model behave more like mainstream chat history sidebars

---

### FB-20260407-claims-mode-selection-friction
- **Status**: VERIFIED
- **Category**: UX / Workflow
- **Severity**: Medium
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:35 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: streamlit_app.py:1015-1022 Claims mode uses dedicated single-select dropdown from full contract list; sidebar multi-select only seeds default index
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
The global contract picker allows multiple selected contracts, but Claims Evaluator immediately blocks if more than one is selected. This creates avoidable friction because the user can enter the Claims mode with an invalid selection state and only then discover that they need to go back and manually adjust the sidebar.

**Expected Behavior**:
- Claims Evaluator should guide users into a valid single-contract state automatically or make the constraint explicit before they switch modes
- The mode should feel streamlined rather than error-first

**Actual Behavior**:
- The sidebar supports multi-select globally
- Claims mode stops with a warning when more than one contract is selected
- Users have to manually reconcile the selection after entering the mode

**Suggested Fix**:
- Auto-restrict to one contract when entering Claims mode, or provide a dedicated single-select control for that mode
- Make the active claims contract explicit and reduce the chance of invalid mode entry

---

### FB-20260407-ingest-guidance-validation
- **Status**: VERIFIED
- **Category**: UX / Ingest
- **Severity**: Medium
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:36 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: streamlit_app.py:1120-1203 Regex validation, production/staging existence checks, overwrite confirmation, processing guidance caption, post-success summary with paths
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
The Ingest Contract flow is functional, but it currently provides limited guidance before and after submission. Users are not clearly told what makes a valid Contract ID, whether the target bundle already exists, how long OCR/embedding may take, or what to do if ingestion partially succeeds or fails.

**Expected Behavior**:
- Users should understand required input conventions before uploading PDFs
- The UI should warn about likely duplicates or overwrites before starting ingestion
- The flow should set realistic expectations for processing time and provide a clearer completion summary

**Actual Behavior**:
- The form is minimal and mostly trusts the user to know the required naming and lifecycle rules
- There is little pre-submit validation or duplicate detection feedback
- Post-success feedback is brief and does not summarize what was written or how to verify the result

**Suggested Fix**:
- Add pre-submit validation for OEM and Contract ID fields
- Warn when a contract key already exists in staging or when a manifest entry may be overwritten
- Provide processing-time guidance and a clearer success summary with next verification steps

---

### FB-20260407-claims-api-response-shape
- **Status**: VERIFIED
- **Category**: Backend / API
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:37 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: start_server.py:92-103 Tuple properly unpacked; _serialize_claims_response returns rows and mapping_warnings as separate top-level fields
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
The `/api/evaluate-claims` endpoint in `agent_server/start_server.py` currently assigns the full return value from `evaluate_claims_file()` directly to the `rows` field. However, `evaluate_claims_file()` returns a tuple of `(rows, mapping_warnings)`. This creates an inconsistent API response contract for clients and downstream automation.

**Expected Behavior**:
- The endpoint should return claim rows and mapping warnings as separate top-level fields
- External clients should be able to parse the response without knowing the internal helper return shape
- The API schema should match the actual runtime payload

**Actual Behavior**:
- The `rows` field contains the full tuple returned by the evaluator rather than only the list of evaluated row objects
- Mapping warnings are not exposed as a dedicated top-level field
- This can cause integration bugs for non-UI callers

**Suggested Fix**:
- Unpack `evaluate_claims_file()` inside the endpoint and return `rows` plus `mapping_warnings` separately
- Add a small regression test for the endpoint response schema

---

### FB-20260407-retrieval-traceability-auditability
- **Status**: VERIFIED
- **Category**: Transparency / Observability
- **Severity**: Medium
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:38 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: agent.py:1260-1312 retrieval_trace includes timings_ms, query_count, candidate_count, profile_verification, snippet metadata; _persist_retrieval_trace writes per-session JSON to Volumes
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
The app now exposes a much better thinking trace than before, but answer auditability is still limited. Users and developers can see high-level tool activity and final citations, yet there is not enough structured retrieval metadata to quickly understand why specific snippets were selected, how they were reranked, or how one answer differed from another during debugging.

**Expected Behavior**:
- The system should preserve stable retrieval metadata such as snippet identifiers, retrieval mode, ranking order, and source provenance for internal audit/debug use
- Transparency improvements should help both user trust and debugging without exposing raw tool JSON in the final answer

**Actual Behavior**:
- The UI mainly shows human-readable step labels, optional trace text, and final markdown output
- There is limited durable metadata for auditing retrieval quality or debugging disagreements across runs
- This makes it harder to diagnose subtle answer-quality issues

**Suggested Fix**:
- Persist structured retrieval metadata alongside session logs or trace logs
- Add an internal or admin-friendly evidence audit view showing retrieval mode, selected snippets, and rerank decisions
- Keep user-facing answers clean while improving internal observability

---

### FB-20260407-council-entrypoint-parity
- **Status**: VERIFIED
- **Category**: Architecture / Consistency
- **Severity**: Medium
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 11:39 UTC
- **Last Attempt Run ID**: feedback-cycle-20260409
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: council.py docstring documents intentional UI-only design decision; council adds latency/cost appropriate for interactive Q&A but not API callers; parity path documented for future if needed
- **Last Updated**: 2026-04-09T08:30:00+00:00

**Description**:
The hidden Q&A council feature is integrated into the Streamlit execution path, but the base server `invoke` and `stream` handlers in `agent_server/agent.py` remain single-model. This means answer-generation behavior can differ depending on whether the caller uses the Streamlit app or the agent server/API path.

**Expected Behavior**:
- Advanced answer-synthesis behavior should be consistent across the main entry points, or the difference should be intentional, documented, and tested
- Feature flags such as `COUNCIL_ENABLED` should have a clearly defined contract across clients

**Actual Behavior**:
- Streamlit can apply council synthesis after retrieval when enabled
- The base agent server handlers do not apply the same synthesis step
- Different clients may therefore receive different answer behavior for the same question

**Suggested Fix**:
- Decide whether council should be a first-class backend capability or a UI-only enhancement
- If it is intended to be first-class, move the behavior into the shared execution path
- If it remains UI-only, document the limitation and test both entry points explicitly

---

### FB-20260407-orchestrator-canary-answer-visible
- **Status**: VERIFIED
- **Category**: Harness Canary / UI
- **Severity**: Low
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-07 12:00 UTC
- **Last Attempt Run ID**: feedback-cycle-20260408
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 1
- **Evidence**: C:\Users\ADJ1DE\Documents\Agent Workflow\ai\orchestrator\runs\feedback-cycle-20260408\deploy-provenance.json
- **Last Updated**: 2026-04-08T12:55:00+00:00

**Description**:
Add a small, explicit `Answer` heading above the final assistant response in Contract Q&A so the first orchestration retest has a deterministic, visible UI change to plan, implement, deploy, and verify.

**Steps to Reproduce**:
1. Open Contract Q&A mode
2. Select any contract
3. Ask a question
4. Wait for the response to complete

**Expected Behavior**:
- The final assistant response shows a visible `Answer` heading in the chat output area
- The answer is directly visible in chat
- The answer is not hidden inside a status or `Done` container
- Existing citations remain visible

**Actual Behavior**:
- There is no stable, explicit answer marker intended for a lightweight orchestration canary
- The first harness retest would be more deterministic with a simple visible marker tied to final-answer rendering

**Suggested Fix**:
- Render a small `Answer` label directly above the final assistant response in the assistant message region
- Keep the label outside the thinking/status container
- Preserve existing citations and response formatting

---

### FB-20260414-thinking-ux-upgrade
- **Status**: VERIFIED
- **Category**: UX / Thinking Display
- **Severity**: High
- **Contract**: All
- **Reporter**: adj1de@bosch.com
- **Date**: 2026-04-14 09:45 UTC
- **Last Attempt Run ID**: thinking-ux-20260414
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: Deploy 01f137ec97b9175b9ec19f44999bc2ef SUCCEEDED; Browser QA 30/33 pass, 0 fail, 3 warn; answer_visible_in_chat=PASS; thinking_panel=PASS
- **Last Updated**: 2026-04-14T10:30:00+00:00

**Description**:
The current thinking/reasoning display during Q&A is unprofessional compared to every major AI chat interface (ChatGPT, Claude, Gemini, Grok, DeepSeek, Perplexity). The `st.status` widget shows a basic "Thinking..." label with numbered step labels, then changes to "Done". This needs to match the industry-standard pattern: elapsed time indicator, live reasoning text, compact visual treatment, and clear answer separation.

Research audit completed across 7 top models (see `ai/research/thinking-ux-audit-2026.md`). All have converged on the same core pattern.

**Current Behavior**:
- Static "Thinking..." label during processing
- Steps rendered as "Step 1 -- Retrieving profile...", "Step 2 -- Tool completed." etc.
- Status label changes to "Done" on completion with no elapsed time
- Default `st.status` border styling (bulky, not matching modern AI chat UX)
- Thinking/reasoning token content is captured but only logged as "Thinking update received" -- actual thinking text is NOT streamed to the user
- Elapsed time shown only as a caption under the answer, not on the thinking toggle

**Expected Behavior**:
1. Elapsed time on toggle: Status label shows "Thought for Xs" instead of "Done" when complete
2. Live tool activity labels: Cleaner formatting without "Step N" numbering -- just the label with a progress indicator
3. Live thinking text: When the model produces thinking/reasoning tokens, stream the actual text into the status widget in dimmed/italic markdown so users can follow the reasoning
4. Compact toggle: If Streamlit version supports `border=False` on `st.status`, use it for a cleaner disclosure toggle
5. Auto-collapse on answer: Status panel collapses when answer generation begins (already working)
6. Consistent visual hierarchy: Thinking panel is secondary; answer is primary and always visible outside the panel

**Implementation Scope** (all within `streamlit_app.py`):

Changes to `_run_agent_streaming` (lines 423-663):
- When `kind in ("thinking", "reasoning")` at line 487: append the actual `evt_text` content to `trace_events` with a thinking prefix instead of just "Thinking update received"
- In the polling loop (lines 599-650): render thinking events with dimmed styling vs tool events with bold styling

Changes to the status widget usage (lines 928-940):
- Change completion label from "Done" to "Thought for {elapsed}s"
- Remove "Step N --" prefix from rendered trace events
- If `st.status` supports `border=False`, apply it

Changes to elapsed time display (lines 951-954):
- Remove the separate "Done in Xs" caption since elapsed time is now on the thinking toggle

No backend changes. No agent.py changes. No claims_batch.py changes.

**Reference**: `ai/research/thinking-ux-audit-2026.md`

---

### FB-20260422-guardrail-tripwire-comparison
- **Status**: VERIFIED
- **Category**: Bug / Guardrails
- **Severity**: Critical
- **Contract**: All (multi-contract)
- **Reporter**: user (via adj1de@bosch.com)
- **Date**: 2026-04-22 12:00 UTC
- **Last Attempt Run ID**: guardrail-fix-20260422
- **Last Decision**: APPROVED
- **Blocker Classification**: 
- **Retry Count**: 0
- **Evidence**: Deploy 01f13e47e2e410c99db6c820d93ea0b9 SUCCEEDED; Browser QA 6/6 pass, 0 fail, 0 warn; answer_visible_in_chat=PASS; guardrail_fix_verified=PASS; Q&A completed in 62s with citations and evidence
- **Last Updated**: 2026-04-22T12:39:00+00:00

**Description**:
When a user selects two contracts (e.g. JLR + BMW) and asks a comparison question, the citation output guardrail triggers a tripwire after ~105 seconds of processing, discarding the entire response. The user sees "Error: Guardrail Output: Guardrail triggered tripwire" instead of the comparison answer.

**Root Cause**:
The `citation_guardrail` in `agent_server/guardrails.py` was configured with `tripwire_triggered=True` when `[n]` citation patterns were not found in the output. For multi-contract comparison responses, the output format (tables, structured sections) may not include inline `[n]` citations in every section. Additionally, `str(output)` on the Agents SDK output object may not properly extract the text content, causing false negatives.

**Steps to Reproduce**:
1. Select both JLR and BMW contracts in the sidebar
2. Ask a comparison question (e.g. "Compare the warranty periods")
3. Wait for processing (~105 seconds of tool calls)
4. Observe error: "Error: Guardrail Output: Guardrail triggered tripwire"

**Fixes Applied**:
- `agent_server/guardrails.py`: Added `_extract_output_text()` helper for robust text extraction from various output object types; citation guardrail no longer triggers `tripwire_triggered=True` (changed to warning-only); added bypass for comparison/table-formatted responses
- `streamlit_app.py`: Added graceful guardrail exception handling in `_background()` thread so responses are preserved with a quality warning instead of being discarded

---
