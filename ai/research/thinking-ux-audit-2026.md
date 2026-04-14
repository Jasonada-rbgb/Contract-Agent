# AI Chat Thinking/Reasoning UX Audit (April 2026)

Research across the top 10+ AI models to inform the Warranty Contract Agent's thinking UI upgrade.

---

## Executive Summary

Every major AI chat interface has converged on a similar pattern for displaying model reasoning:

1. **Collapsed by default** -- thinking is hidden behind a toggle
2. **Duration indicator** -- "Thought for X seconds" or token count shown
3. **Expandable on click** -- full reasoning text available on demand
4. **Visually distinct** -- dimmed text, different background, or indented block
5. **Auto-close on completion** -- panel collapses when the final answer arrives
6. **Live streaming** -- thinking text streams in real time while the model reasons

The current Streamlit `st.status` implementation in the Warranty Contract Agent is **functional but not polished** compared to these patterns. The main issues:
- No live thinking text is streamed (just a static "Thinking..." indicator)
- The answer was previously hidden under the Done/status container (fixed, but the visual treatment is still basic)
- No duration indicator or token count
- No smooth animation or visual distinction for the thinking phase

---

## Model-by-Model Analysis

### 1. ChatGPT (GPT-5.4 / o3)
**URL**: https://chatgpt.com  
**Free tier**: Yes (limited)

**Thinking UX**:
- **Collapsed toggle**: Shows "Thought for X seconds" as a clickable accordion
- **Expandable**: Click reveals the full chain-of-thought reasoning
- **Summarized reasoning**: Displays a cleaned-up summary of the reasoning steps, not raw tokens
- **Three-tier model selector**: Instant (fast) / Thinking (deep) / Pro (max)
- **Mid-response steering**: Users can add instructions while thinking is in progress
- **Upfront plan display**: GPT-5.4 Thinking surfaces an adjustable plan before generating
- **Animation**: Subtle typing animation with staggered word appearance and blur transitions between words
- **Cursor**: Blinking cursor during generation, probabilistic pauses between words to feel "human"

**Key takeaway**: The "Thought for X seconds" collapsed summary is the gold standard for thinking disclosure. Clean, minimal, informative.

### 2. Claude (Opus 4.6)
**URL**: https://claude.ai  
**Free tier**: Yes (limited)

**Thinking UX**:
- **Extended thinking blocks**: Generates `thinking` content blocks before the response
- **Collapsed by default**: Thinking blocks are hidden in production; users can expand to view
- **Adaptive thinking**: Model decides its own reasoning duration (no fixed budget)
- **Display field**: API supports `display: "omitted"` to strip thinking content while preserving multi-turn continuity
- **Visual distinction**: When visible, thinking text appears dimmed/grayed out to separate from the final answer
- **Redact-thinking header**: UI-level control to hide raw thinking entirely

**Key takeaway**: Claude's approach prioritizes the final answer experience. Thinking is available but deliberately de-emphasized. The `display: "omitted"` pattern for streaming performance is clever.

### 3. Gemini (3.1 Pro / Deep Think)
**URL**: https://gemini.google.com  
**Free tier**: Yes

**Thinking UX**:
- **Three-tier thinking budget**: Low / Medium / High reasoning depth
- **"Deep Think" mode**: Activated via prompt bar button for complex problems
- **Thinking tokens visible**: Reasoning process generates visible thinking tokens separate from response tokens
- **Notification on completion**: For long reasoning tasks, users get a notification when ready
- **Pro vs Flash**: Users choose between Flash (fast thinking) and Pro (deep reasoning)

**Key takeaway**: Gemini's three-tier budget system gives users explicit control over thinking depth. The notification pattern for long tasks is useful for heavy contract analysis.

### 4. Grok (4.1)
**URL**: https://grok.com  
**Free tier**: Limited via X

**Thinking UX**:
- **"Think" button**: Dedicated button to activate transparent reasoning mode
- **Step-by-step visibility**: Displays chain-of-thought processing as the model works
- **Thinking tokens**: Internal reasoning tokens generated before the final response
- **Two modes**: Grok 4.1 Thinking (slower, higher quality) vs non-thinking (fast, no reasoning trace)
- **DeepSearch integration**: Search steps shown as part of the thinking process
- **Think-aloud design**: The model "thinks aloud" so users can follow the reasoning

**Key takeaway**: Grok's approach is the most transparent -- it shows reasoning as it happens, not just after. The "Think" button toggle is a clean UX pattern.

### 5. DeepSeek (R1)
**URL**: https://chat.deepseek.com  
**Free tier**: Yes

**Thinking UX**:
- **`<think>` tags**: Reasoning wrapped in `<think>...</think>` tags in the response
- **Collapsible by default**: Thinking blocks collapsed with "[+] Reasoning available" indicator
- **Real-time streaming**: Thinking text streams in real time as the model reasons
- **Visual distinction**: Shaded background, borders, or indented boxes for thinking blocks
- **Time + token count**: Elapsed time and token count shown alongside collapsed toggle
- **Copy support**: Users can copy thinking content when expanded

**Key takeaway**: DeepSeek's implementation is the closest to what we should build in Streamlit. The `<think>` tag pattern with collapsible display, real-time streaming, and elapsed time indicator is excellent.

### 6. Mistral (Le Chat / Magistral)
**URL**: https://chat.mistral.ai  
**Free tier**: Yes

**Thinking UX**:
- **Think Mode**: Powered by Magistral reasoning model
- **Canvas**: Side panel for collaborative content creation
- **Flash Answers**: ~1000 words/sec for rapid responses (no thinking visible)
- **Deep Research**: Structured research mode with visible planning steps
- **Projects**: Organize related chats with shared context

**Key takeaway**: Mistral differentiates between "Think Mode" (deep reasoning) and "Flash" (instant). The Deep Research mode with visible planning is relevant for contract analysis workflows.

### 7. Perplexity
**URL**: https://perplexity.ai  
**Free tier**: Yes

**Thinking UX**:
- **Pro Search steps**: Shows multi-step research process with visible tool orchestration
- **reasoning_steps array**: Structured array of reasoning steps exposed in API
- **Source attribution**: Numbered inline citations linked to expandable source cards
- **Tool execution visibility**: Web search, URL fetch, and analysis steps shown during streaming
- **Step-by-step research chain**: "Shows you the step-by-step process behind its findings"

**Key takeaway**: Perplexity excels at showing the *research* process (which tools were used, what sources were consulted). This is directly relevant to our retrieval pipeline visibility (BM25, vector, rerank steps).

---

## Common Design Patterns (Consensus)

### Pattern 1: Collapsed Thinking Toggle
```
[icon] Thought for 12 seconds                    [chevron]
```
- Collapsed by default after completion
- Shows duration and/or token count
- Click to expand full reasoning
- Auto-expanded during active thinking, auto-collapsed when answer begins

### Pattern 2: Live Thinking Stream
```
[Thinking...]
  > Analyzing contract terms for warranty periods...
  > Cross-referencing market definitions with claim data...
  > Checking exclusion clauses for component coverage...
```
- Dimmed/gray text, smaller font, different background
- Streams token-by-token during reasoning
- Replaces static "Thinking..." spinner with readable progress

### Pattern 3: Step-by-Step Tool Activity
```
[Step 1] Retrieving contract profile...              [done]
[Step 2] Expanding query with synonyms...            [done]
[Step 3] Searching 847 chunks (BM25 + vector)...     [done]
[Step 4] Reranking top 40 candidates...              [done]
[Step 5] Generating answer with citations...         [streaming]
```
- Shows each tool/step as a discrete item
- Progress indicators per step (spinner -> checkmark)
- Duration per step shown inline

### Pattern 4: Answer Separation
```
[Thinking panel -- collapsed]
---
## Answer
[Final response with citations]
```
- Clear visual boundary between thinking and answer
- Thinking never interferes with answer readability
- Answer rendered in full markdown with citations

---

## Streamlit Implementation Opportunities

### Available Components (Current)
- `st.status(label, state, expanded)` -- basic expandable container with spinner/checkmark states
- `st.expander(label, expanded)` -- simple toggle container
- `st.spinner(text)` -- blocking spinner

### New Components (Streamlit 1.46+, available now)
- `st.status(border=False)` -- compact, borderless disclosure toggle (ChatGPT/Claude style)
- `st.expander(border=False)` -- compact, chevron-style toggle

### Upcoming (in PR / development)
- `st.steps()` -- chain-of-thought workflow steps with icons and state transitions (PR #13918)

### Recommended Architecture for Warranty Contract Agent

```
Phase 1: Thinking starts
  -> st.status("Thinking...", state="running", expanded=True)
  -> Inside: stream tool activity labels ("Retrieving contract...", "Searching chunks...")
  -> Inside: optionally stream live reasoning text in dimmed markdown

Phase 2: Answer generation starts
  -> st.status.update(label="Thought for {elapsed}s", state="complete", expanded=False)
  -> Answer rendered OUTSIDE the status container in st.chat_message("assistant")
  -> Full markdown with citations

Phase 3: Complete
  -> Thinking panel stays collapsed, clickable to expand
  -> Answer stays visible with inline feedback buttons below
```

---

## Specific Improvements for the Warranty Contract Agent

| Current Behavior | Target Behavior | Priority |
|-----------------|-----------------|----------|
| Static "Thinking..." text | Live tool activity labels (retrieving, searching, reranking) | High |
| No elapsed time shown | "Thought for Xs" on completion | High |
| Thinking panel uses default st.status styling | Compact/borderless thinking toggle | Medium |
| No live reasoning text | Stream model thinking tokens into dimmed text inside panel | Medium |
| Answer inside st.status lifecycle | Answer clearly outside, in chat message area | Done (already fixed) |
| No step-by-step tool visibility | Show retrieval steps with progress indicators | Medium |
| Basic spinner animation | Subtle typing/pulsing animation | Low |

---

## Sources

- [ChatGPT thinking animation in React](https://matteing.com/writing/creating-a-magical-chatgpt-like-thinking-animation-in-react)
- [Grok Think Mode](https://grokipedia.com/page/Think_Mode_Grok)
- [Claude Extended Thinking API](https://platform.claude.com/docs/en/build-with-claude/extended-thinking/)
- [DeepSeek thinking UI](https://github.com/hao-hoang/deepseek-thinking-ui)
- [Streamlit st.steps() PR](https://github.com/streamlit/streamlit/pull/13918)
- [Streamlit compact st.status](https://github.com/streamlit/streamlit/pull/14054)
- [Streaming Responses UX Patterns](https://www.maisumhashim.com/blog/streaming-responses-ux-patterns-that-work)
- [AI Chat UI Best Practices](https://thefrontkit.com/blogs/ai-chat-ui-best-practices)
- [OpenAI o3 chain of thought](https://www.zdnet.com/article/openais-o3-mini-now-lets-you-see-the-ais-thought-process/)
- [Gemini 3.1 Pro thinking system](https://gemilab.net/en/articles/gemini-basics/gemini-31-pro-guide)
- [Perplexity Pro Search](https://www.perplexity.ai/hub/blog/pro-search-upgraded-for-more-advanced-problem-solving)
- [assistant-ui chain of thought](https://www.assistant-ui.com/docs/guides/chain-of-thought)
