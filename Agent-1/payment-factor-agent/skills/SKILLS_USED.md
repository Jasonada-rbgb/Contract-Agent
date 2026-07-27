# Skills & Subagents Used To Build The Payment-Factor Agent

This documents the CLI-side skills and subagents that were used while building
and verifying the payment-factor agent (rule extraction, claims evaluation,
methodology reproduction). It is provided to help the GitHub Copilot team
understand *how the information was built up*.

The skills were used from the **Codex CLI** (skills live in `~/.codex/skills/`
and workspace `.agents/skills/`; subagents in `.codex/agents/*.toml`). Copilot
does not consume these files directly, but the SKILL.md content captures the
reusable patterns and can be adapted into Copilot instructions/prompts.

## How skills work (Codex CLI)

- A skill is a folder with a `SKILL.md` (YAML front-matter `name` + `description`,
  then a Markdown body of procedural guidance).
- Skills are auto-discovered; a matching `description` triggers implicit use, or
  the user invokes explicitly with `$skill-name` (e.g. `$dev-up`).
- Subagents are role definitions (`.toml`) invoked via `agents.spawn` or the IDE
  subagent picker to run planning/build/review/verify steps.

## Skills included in this package (`skills/`)

| Skill | Role in building the payment-factor agent |
| --- | --- |
| `warranty-agent` | **Core domain skill.** Agent architecture (OpenAI Agents SDK), hybrid BM25+vector retrieval with LLM rerank, claims evaluation pipeline, decision schema, claim routing, and the ContractDecisionPayload handoff. This is the backbone of how the agent evaluates contracts and claims. |
| `databricks-pipeline` | Unity Catalog, UC Volumes, Delta tables, and Databricks Apps patterns — used for the STAR/DMYA enrichment, ruleset storage, and running the audit/rebuild jobs. |
| `python-patterns` | Pythonic idioms, type hints, and error handling for the agent and audit scripts. |
| `search-first` | Research-before-coding: check existing tools/patterns before writing custom logic (used when deriving rule extraction rather than hardcoding). |
| `security-review` | Secrets/input-validation checklist — applied so no VINs/credentials leak into rules, provenance, or committed artifacts. |
| `verification-loop` | Build/type/test/secret checks after changes — used to verify rule reproduction was exact (1:1) and safe. |
| `continuous-learning` | Pattern extraction from long sessions — used to consolidate the rule-building methodology into reusable form. |
| `dev-up` | Connect to Databricks and prepare the environment (auth, pull app code) — the standard entry point for every working session. |

## Subagents included (`skills/subagents/`)

| Subagent | Role |
| --- | --- |
| `planner` | Expand a request into a structured plan + contract (acceptance criteria, affected files, risk). |
| `backend-builder` | Implement backend/agent code changes to the plan. |
| `reviewer` | Review changes for correctness, security, and evidence completeness. |
| `verifier` | Independently verify the change against required evidence. |

## Sessions where these were used

Traced from Codex session logs (`~/.codex/sessions/…rollout-*.jsonl`) over the
payment-factor build-up window (BMW ruleset compiled 2026-06-15 → 2026-07-20
re-verification). All sessions consistently referenced the core skill set
(`warranty-agent`, `databricks-pipeline`, `python-patterns`, `search-first`,
`security-review`, `verification-loop`, `continuous-learning`) and the
`planner` / `backend_builder` / `reviewer` / `verifier` subagents:

- 2026-06-08, 2026-06-10, 2026-06-12
- 2026-06-18, 2026-06-25 (x2), 2026-06-29
- 2026-07-08 (x2), 2026-07-16
- 2026-07-20 (x3 — the reverify/methodology sessions)

`dev-up` appeared as the session bootstrap; `portal-recon` and `aspire-weekly`
appeared in a few sessions for unrelated side-tasks and are not part of the
payment-factor build path.

## Adapting for GitHub Copilot

Each `SKILL.md` body is self-contained guidance. To reuse in Copilot:
- Paste the relevant SKILL.md body into a Copilot custom instruction / prompt
  file (e.g. `.github/copilot-instructions.md`), or
- Reference the `warranty-agent` architecture + `databricks-pipeline` patterns
  as the primary context when asking Copilot to extend the agent.
