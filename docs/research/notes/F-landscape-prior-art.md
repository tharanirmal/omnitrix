# F — Landscape & prior art: second-brain / agent-memory products and OSS (for Omnitrix)

Researcher slice F · compiled 2026-09-25 · star counts and dates pulled from the GitHub API on 2026-09-25 unless noted.
Method: GitHub API + READMEs/docs/source/issues (primary), vendor blogs/docs, HN (Algolia API). Reddit was not reachable (HTTP 403), and the web-search quota ran out near the end. Anything I could not confirm from a primary source is listed under **Unverified**.

---

## 0. TL;DR (what matters for the pitch)

1. **GBrain** is Garry Tan's (YC CEO) open-source agent brain: MIT, TypeScript on Bun, created 2026-04-05, about 30.3k stars. The team's note is **partly wrong**. It **does** schedule: cron recipes, an `autopilot` daemon, a nightly "dream cycle", a Minions job queue, quiet hours, and a morning-briefing skill. It also ships an **open-loop engine** that pulls commitments/promises out of Gmail. That overlaps directly with Omnitrix's "extract promises, plan the day". Its storage is local (PGLite/Postgres), but by default its **reasoning is cloud**. The Ollama recipe does embeddings only, and subagent loops are hard-pinned to Anthropic.
2. **Utopia** is DeepLethe's "enterprise world model": Apache-2.0, Rust plus Postgres/pgvector, created 2026-08-07, about 10.2k stars, still v0.1. "Enterprise-scale" is right. "Too heavy" is overstated: it is one binary plus Postgres. The real gap is scope: it ingests documents only (no email/calendar/voice) and takes no actions yet. **Its Sept-2026 governance design is the closest prior art to the System-1/System-2 idea.** A batch LLM adjudicator gives confidence scores. A tool-using "second look" handles unsure cases, then a human queue. Every look lands in an `agent_decisions` row with confidence and status. Human rationales come back as precedents. A "fuse" switches automation off after two reverts in a week. It measured 96.9% agreement on 589 hand-labeled pairs.
3. **Mem0 changed under the team's feet.** OSS v3 (April 2026) is **ADD-only**: no UPDATE/DELETE, so contradictions pile up and only retrieval ranking picks between them. **Graph memory was removed from the OSS** build. **OpenMemory (the local MCP server) was sunset in April 2026 and deleted from the repo on 2026-07-29.**
4. **Evidence of memory-quality pain is strong.** One user audited 10,134 Mem0 entries and found 97.8% junk (mem0#4573). A Graphiti user found its small-model contradiction judge silently retiring true facts: 41% of facts invalidated, and 3 of 4 audited were collateral (graphiti#1728). Notion's Lore pilot kept only 55–60% of stored memory as useful. ChatGPT's June-2026 "Dreaming" memory drew complaints about opacity and loss of control.
5. **Action gating by a cheap model is already shipping**, but only for coding and shell agents:
   - Claude Code auto mode runs a two-stage classifier: a single-token filter first, and chain-of-thought only when the first stage flags.
   - Hermes Agent's "smart approvals" use an auxiliary LLM to approve, deny or escalate, and mine approval history into allowlist suggestions.
   - Meta Muse (2026-09-08) asks for human approval on connector actions and purchases.
   - Apple Watch approval apps exist too (Agent Approve, 2026-07-07), for coding agents only.
6. **Novelty verdict:** the *pieces* have high precedent. Nobody ships the *combination* for a personal assistant: one decision fabric covering memory and actions, a small local model as System 1, **measured** calibration rather than self-reported confidence, a user-visible per-decision ledger, and learning that feeds back into System 1. That is moderately novel and very demo-able **if it is measured**. Cite Utopia, Claude Code and Hermes as validation, and state the delta explicitly.

---

## 1. Organizer-named tools — what "GBrain" and "Utopia" are

### 1.1 GBrain (garrytan/gbrain)
- **What/who:** "Garry's Opinionated OpenClaw/Hermes Agent Brain". Built by Garry Tan (YC President/CEO) to run his own agents. Repo created **2026-04-05**, one day after Karpathy's "llm-wiki" gist (2026-04-04). **MIT**, **TypeScript on Bun ≥1.3.11**. About **30.3k stars / 4.5k forks** and 462 open issues plus PRs. Very fast cadence: v0.57.0.0 released 2026-09-24. A hosted team product now exists at **gbrain.io** ("one brain for the whole team", per-workspace pricing). Its Gmail connector offers Read/Draft/Manage/Full permission levels. https://github.com/garrytan/gbrain · https://gbrain.io
- **Scale claim (self-reported):** his production brain holds 155,795 pages, 24,589 people, 5,340 companies and 66 cron jobs.
- **Storage:** Two engines sit behind one contract:
  - PGLite (Postgres 17 via WASM, the default, up to ~50K pages)
  - Postgres + pgvector (shared or large deployments)

  Markdown pages in a git repo are canonical; the DB holds operational state.
- **Representation:** Typed pages come from schema packs (person, company, deal, meeting, email, project…). Each page has a **"compiled truth"** section that is *rewritten* when evidence changes, plus an **append-only timeline** with sources, where corrections are new entries. On top of that sit typed graph edges and backlinks, and a facts table with provenance. Auto-link extracts edges from `[[wikilinks]]` by pattern matching, with no LLM.
- **Retrieval:** keyword (works keyless) + vector + typed-graph traversal + optional rerank (Voyage by default; a local llama.cpp Qwen3-Reranker recipe exists). `gbrain think` writes a cited synthesis with a **gap analysis** that flags stale pages, uncited claims and pages that contradict each other.
- **Ingestion:** native Gmail/Calendar/Contacts (OAuth "google source"), email/calendar webhooks, meeting sync, **voice calls via Twilio + OpenAI Realtime**, X/Twitter collectors, files and Obsidian/Notion imports, agent writes, and an opt-in "signal detector".
- **Scheduling (contradicts the team's note):**
  - Reference cron schedule: email every 30 min, meeting sync 3×/day, daily morning briefing, weekly maintenance, nightly **dream cycle** (lint, backlinks, extract, sync, embed, synthesize)
  - `gbrain autopilot` daemon and `gbrain jobs`/Minions queue (retries, audit trail)
  - `cron-scheduler`, `briefing` and `daily-task-prep` skills
  - **quiet hours**: notifications are held overnight and merged into the morning briefing
- **Open-loop engine (overlaps directly with Omnitrix):**
  - Detector 1 is a **deterministic, zero-LLM** thread-state machine. It flags "they're waiting on you" after 24h and "you're waiting on them" after 72h, and closes a loop when a reply arrives.
  - Detector 2 is an **LLM commitment extractor** that records who owes what to whom, counterparty, due date and verbatim quote. Guardrails: an all-or-nothing parse barrier and a kill switch. It only reads the last 30 days of mail.
  - Loops close by state transition and are never deleted, which keeps an audit trail. Commitments go stale after 90 days of inactivity.
  - `gbrain waiting` **refuses** to answer when sync is more than 24h old ("stale-but-confident output is worse than none").
  - Detecting that a commitment was **fulfilled by a reply is explicitly future work.**
- **Executive-assistant pattern (docs):** email triage with brain context, meeting prep, post-inbox page updates, scheduling *nudges* (e.g. "you owe X…"). It gives nudges but does not book meetings itself.
- **MCP & sharing:** stdio or HTTP with OAuth 2.1 and scopes (read/write/admin/agent). `gbrain mcp expose` publishes over Tailscale. The company-brain mode has per-source grants, and the README admits there is no universal no-leak guarantee.
- **Local?** Storage and keyless search are local. Embeddings can be local (Ollama, llama.cpp, LM Studio). But:
  - the Ollama recipe has **no chat touchpoint**
  - chat defaults to hosted providers (an OpenAI-compatible base URL can be set)
  - **subagent loops hard-pin to Anthropic-direct**
  - voice uses OpenAI Realtime
  - the README warns that configured cloud providers receive text

  Verdict: **local memory, cloud reasoning by default.**
- **Learning:** `gbrain skillopt` treats SKILL.md files as trainable. It runs a benchmark, proposes edits and keeps only improvements, with a JSONL audit trail (based on SkillOpt, MSR, May 2026). That learns **procedures**, not per-decision gates.
- **Approvals:** owner-approved OAuth clients and "explicit destination approval" for imports. Outbound actions are left to the agent harness; GBrain is not an action executor.
- **Weaknesses:**
  - Very large surface: 140+ engine methods and more than 1k commits.
  - Full value needs a 24/7 server plus raw API tokens (the README calls this the "highest-cost path").
  - Bugs where a command reports success on failure (gbrain#5012, open as of 2026-09-25), and vector search skipping the HNSW index (gbrain#5252, now closed).
  - Competitor critiques call it single-operator and self-hosted only. The Vectorize/Hindsight critique is biased and partly outdated now that gbrain.io exists.
- **Team note check:**
  - "People/company/meeting brain": ✔, but it is much more than that.
  - "TypeScript/Bun": ✔.
  - **"No scheduling": ✘ wrong.**
  - Better one-liner: *"Local-storage agent brain (PGLite/Postgres) with cron/dream-cycle upkeep and a Gmail open-loop/commitment engine. TypeScript/Bun. LLM features default to hosted APIs."*
- **Borrowable:** compiled truth plus append-only timeline, the deterministic-then-LLM loop detector, "refuse when stale", quiet hours and the morning digest. Since Omnitrix already uses Postgres + pgvector, it could consume or produce GBrain-compatible pages over MCP.

### 1.2 Utopia (deeplethe/utopia)
- **What/who:** "World's first open-source enterprise world model" by **DeepLethe** (deeplethe.com; site utopia.bi). Repo created **2026-08-07**. **Apache-2.0**, **Rust** backend with a TypeScript/React UI. About **10.2k stars / 1.1k forks**, default branch `dev`, releases `v0.1.0-rc4…rc6` (Sept 2026). Explicitly **v0.1**: migrations only roll forward, so pin versions. The authors ask not to frame it as "open-source Palantir". https://github.com/deeplethe/utopia
- **Architecture:** "One Rust binary and one Postgres." Tantivy full-text search is embedded, vectors live in pgvector, results are fused with RRF, and the job queue is a table. It ships a web console, graph browser and ontology workbench. The built-in agent harness does agentic RAG, walks the graph (point-in-time and diff queries) and queries mounted SQL databases (Ontology2SQL). Each knowledge base gets an MCP server exposing read-only tools. Deployment is Docker compose.
- **Ingest:** PDF, DOCX, PPTX, XLSX, CSV, Markdown, HTML and text, plus scheduled sync from the web, RSS, GitHub, Jira, Notion, WebDAV and S3, plus an API. **No email, calendar, chat or voice connectors are listed.**
- **Representation:** a **bitemporal KG**: each fact carries when it was true in the world and when the system came to believe it. Edges are reified. Five ontology packs are included (schema.org, W3C Org, PROV-O, FOAF, IOF Core). Forward-chaining derivations are off by default, marked as derived, and lose to asserted facts.
- **Update/contradiction:**
  - A correction closes the old version and links the new one; nothing is overwritten.
  - There are three conflict classes: temporal clash (close old / keep both / reject new), axiom violations, and cardinality breaches.
  - Entity resolution runs in **three stages**: exact name or alias, then embedding similarity, then a **model call on the doubtful pairs**. Every merge is undoable.
  - A review queue collects low-confidence extractions, suspected duplicates and cardinality conflicts.
- **Governance (implemented 2026-09-06…09-14, decision records 0025–0028). The closest prior art to System 1/System 2:**
  - **Batch adjudicator** (12 pairs per call, verdict cache). It auto-decides at confidence ≥0.8 and otherwise escalates, e.g. `escalate_unsure|… 0.55`.
  - **Governor** reads the human ledger as *precedent*. History that contradicts a verdict blocks it; history that agrees lowers the bar from 0.85 to 0.75. With no history, a merge is only proposed, never applied.
  - **Second look with tools** for unsure pairs: at most 6 lookups (facts, source passages, ledger search, namesakes) and a daily budget of 300. It ends with `decide` (a verdict plus one sentence naming its evidence) or `defer` (one question for a person).
  - **`agent_decisions` table**: one row per look, with action, confidence, the model's sentence, the precedents shown, and a status (proposed/applied/accepted/overridden/reverted/superseded).
  - Human decisions carry a **rationale** (`why`), which flows back into later prompts as precedent.
  - **Fuse**: two reverts of agent merges within 7 days turn automation off and log an alert.
  - **Impact gate** (0027): a merge is held for a person if it would reach outside the graph (contradictions, derivations, exports), whatever the confidence.
  - Measured: **96.9% agreement on 589 hand-labeled pairs**, with 4 wrong merges.
  - Limits: it covers **only entity resolution**, uses **one configured chat model** for both tiers (self-reported `confidence`, default 0.5 when missing, no calibration), and the **execution gate for agents' calls is still on the roadmap**, as is "agent memory over MCP".
- **Local?** Yes. Any OpenAI-compatible endpoint works (Ollama, vLLM, DeepSeek, Qwen, GLM), so it can run air-gapped.
- **Team note check:** "enterprise-scale world model" ✔. "Too heavy for a personal secretary" is **half right**. Install weight is modest; the mismatch is **scope**: document-centric, multi-user roles, ontology workbench, no personal channels, no actions. **Do not dismiss it.** Its adjudication and governance are the best public reference for Omnitrix's confidence ledger and escalation design, and should be cited as validation.

### 1.3 Other organizer-named items (details in §2)
- **Obsidian:** 1.12 (2026-02-27) added an official **Obsidian CLI**, useful for letting agents write to the vault.
- **Graphiti, Zep, Mem0, Letta:** see §2.
- **PostgreSQL/pgvector, Ollama, llama.cpp, vLLM:** runtimes, covered by other slices. Note that GBrain, Utopia, Khoj, Honcho, Hindsight and Mem0's server all standardise on Postgres + pgvector.

---

## 2. Open-source second-brain / agent-memory projects

Format: **What** · **Ingest** · **Representation** · **Update/dedup/contradiction/forgetting** · **Local** · **Actions** · **Approval/audit** · **Weaknesses/complaints**.

### 2.1 Mem0 (mem0ai/mem0) — Apache-2.0, Python, ~66k★
- **What:** a memory layer for agents: SDK, self-hosted server, and a cloud platform.
- **Ingest:** conversation messages through `add()`.
- **Representation:** vector memories plus BM25 plus entity links.
- **Update/contradiction:**
  - The 2025 paper (arXiv 2504.19413) had the LLM choose ADD/UPDATE/DELETE/NOOP.
  - The **v3 algorithm (April 2026)** is **single-pass ADD-only**: one LLM call, nothing overwritten. Contradictions coexist and are resolved only by time-aware retrieval ranking.
  - `custom_update_memory_prompt` was removed.
  - **Graph memory was removed from the OSS** build (Platform only).
  - The self-reported LoCoMo score rose from 71.4 to 92.5 on the managed platform.
- **Local:** yes (Ollama and others). Gotcha for Omnitrix: mem0#4695 was a hard-coded 1536-dimension vector store breaking **bge-m3 (1024-d)**. It is closed now, but check your pgvector dimensions.
- **Actions:** none. **Audit:** no confidence ledger.
- **Complaints:**
  - #4573 (2026-03-27): a 32-day production audit of 10,134 memories found **97.8% junk**. Causes: re-extracting system-prompt facts (52.7%), cron/heartbeat noise, architecture dumps, transient tasks, hallucinated profiles with local gemma2:2b, and secrets leaking into the store. The author's conclusion: "the extraction prompt is the bottleneck, not the model"; Sonnet stored accurate but useless material.
  - #4956 and #5867: ADD-only surfaces stale or contradictory facts.
  - #5245: silent memory loss.
  - #5352: a 51-comment workaround thread about time-blindness and missing CRUD.
  - Ask HN (2026-02-04): "Mem0 stores memories, but doesn't learn user patterns". A commenter there says user corrections are the highest-signal, underused data.
- **OpenMemory (the local MCP server plus UI, launched May 2025):**
  - Sunset in April 2026 (#4923).
  - Docs references removed 2026-03-24 (#4520).
  - Code **removed 2026-07-29** (#6530) and archived under `mem0ai/openmemory` → `openmemory-archive/`.
  - The name `mem0ai/openmemory` is now reused for an unrelated coding-session porting CLI.
  - The supported local path is `server/` (FastAPI + Postgres/pgvector).
  - **Implication:** "Mem0 planned" should be re-evaluated. It remains usable as a vector store, but it no longer does write-time contradiction handling in OSS.

### 2.2 Graphiti (getzep/graphiti) + Graphiti MCP server; Zep — Apache-2.0, Python, ~31k★
- **What:** a temporal "context graph" framework and the core of Zep (paper arXiv 2501.13956).
- **Ingest:** episodes (text, messages, JSON).
- **Representation:** entities, **facts as edges with validity windows (bi-temporal)**, episodes for provenance, and communities.
- **Backends:** Neo4j 5.26, FalkorDB (the MCP default), and Neptune. Kuzu is **deprecated**. **There is no Postgres backend**, which clashes with Omnitrix's Postgres-only plan.
- **Update/contradiction:**
  - A new fact that contradicts an old one **invalidates** it (the old fact is kept with `invalid_at`).
  - Node dedup runs semantic candidates, then deterministic similarity, then an LLM for leftovers.
  - **Edge dedup and contradiction resolution go to the configured `small_model`** (`resolve_edge`, `ModelSize.small`). The same slot handles attribute extraction, summaries and timestamps. This is a **static small/large split with no confidence and no escalation.**
- **Local:** possible through OpenAI-compatible Ollama/vLLM. The README warns that small or local models often emit schema-invalid JSON. The MCP server has an Ollama config and a sentence-transformers embedder.
- **Actions:** none. **Audit:** episodes give provenance; there are no decision confidences.
- **Complaints:**
  - **#1728 (2026-08-04):** edge invalidation searches the whole graph, so unrelated facts retire each other. In a production graph of ~3,950 facts, 41% had `invalid_at`, and **3 of 4 audited were collateral** and silent. The reporter's small-model judge was Gemini.
  - #467: about $0.80 in OpenAI cost for ~40 short chats.
  - #1707: `add_memory` returns success while dropping episodes.
  - #963: duplicate entities. #868: the minimal Ollama example fails. #760: hallucinations.
- **Zep:** the managed cloud service. Zep Community Edition is **deprecated** (moved to `legacy/`).

### 2.3 Letta (letta-ai/letta → letta-ai/letta-code) — Apache-2.0
- The **V1 API server is retired** (archive branch). Active development is **Letta Code**: TypeScript, ~3.4k★, created Oct 2025, with CLI, desktop, web and Slack/Telegram/Discord channels.
- **Memory:**
  - Memory blocks plus **MemFS**, a git-backed memory filesystem, so every edit is in git history.
  - **"Dreaming"** (sleep-time compute, arXiv 2504.13171): background subagents consolidate lessons, with an optional "agent reviews before applying" step.
  - `/doctor` audits duplication. Skill learning.
- **Contradiction handling:** none documented.
- **Local:** Letta Cloud is the default; a local backend exists. Local-model support in Letta Code is unverified.
- **Actions:** a full agent harness. **Approvals:** rule-based permission modes (Unrestricted, Standard, AcceptEdits, Strict), not a classifier.

### 2.4 Cognee (topoteretes/cognee) — Apache-2.0, ~31k★
- **API:** `remember`/`recall`/`improve`/`forget`. It builds a KG plus vectors from documents, code and sessions. `improve` applies feedback, and "session distillation" promotes *accepted* lessons into permanent memory.
- **Local:** can run with local extraction and embedding models and no LLM; the default is OpenAI.
- **Storage:** Postgres as a graph store is a "demo feature"; the production version is a licensed product.
- **Positioning:** "Company Brain". There is no action approval layer.

### 2.5 MemOS (MemTensor/MemOS) — Apache-2.0, ~11.6k★ (arXiv 2507.03724)
- **What:** a "memory OS" with an inspectable, editable memory graph, the asynchronous MemScheduler, and **natural-language feedback and correction** of memories.
- **memos-local-plugin 2.0** (May 2026): for Hermes, OpenClaw and DeepSeek Harness. Local SQLite, FTS5 plus vector search, "smart dedup", and tiers (L1 traces → L2 policies → L3 world model → skills).
- **Self-hosting** needs Neo4j and Qdrant. Benchmarks are self-reported.

### 2.6 Supermemory (supermemoryai/supermemory) — MIT, ~30.9k★
- **What:** a memory API with fact extraction and user profiles. It **claims** handling of temporal changes, contradictions and automatic forgetting.
- **"Supermemory local"** (2026): a single binary with an embedded graph engine, local bge-base embeddings, and **Ollama for fully offline** use.
- **Platform-only:** connectors and the MCP server (per the docs summary). Plugins exist for Claude Code, Cursor, Codex, OpenClaw and Hermes.
- Its "#1" benchmark claims are self-reported.

### 2.7 Memobase (memodb-io/memobase) — Apache-2.0, ~2.9k★, last push 2026-01-11 (slowing)
- **Representation:** profile-based memory (topic → sub_topic → content) plus an event timeline.
- **Stack:** FastAPI, Postgres and Redis. Writes are **buffered** rather than done in the hot path; the fixed-3-LLM-calls change cut cost by roughly 40–50%.
- **Other:** Ollama tutorial and MCP. Aimed at chatbots.

### 2.8 Second Me (mindverse/Second-Me) — Apache-2.0, ~15.7k★ (arXiv 2503.08102)
- **What:** an "AI self" trained locally with **Hierarchical Memory Modeling**:
  - L0: raw data
  - L1: natural-language bio, "shades" and topics
  - L2: a **LoRA fine-tune plus DPO** of a Qwen2.5 model, exported to GGUF, with MLX on Macs

  Plus a "Second Me network" of shareable AI selves.
- **Status:** the last substantive code merge was May 2025 (README edit Sept 2025), so it is effectively **dormant**. It shows the "parametric memory" route: heavy, slow to update, and it cannot cite sources.

### 2.9 Khoj (khoj-ai/khoj) — AGPL-3.0, ~37.5k★; spin-off Pipali
- **What:** a self-hostable "AI second brain". It indexes PDFs, Markdown, org-mode, Notion and Word into **Postgres + pgvector**, and chats with local or online LLMs.
- **Agents and access:** custom agents; **automations** (scheduled research emailed to you); access from Obsidian, Emacs and WhatsApp.
- **Memory:** no fact-memory with contradiction handling is documented.
- **Pipali** (khoj-ai/pipali, Apache-2.0, ~300★): a local "AI co-worker" with a sandbox, scheduled routines, and explicit approval for broader access.

### 2.10 Reor (reorproject/reor) — AGPL-3.0, ~8.5k★ — **archived** (last push 2025-05-13)
- **What:** a local-first note app (Ollama, Transformers.js, LanceDB) that auto-links related notes by vector similarity and answers questions over them with RAG.
- **Lesson:** "local by default" alone was not enough to sustain it.

### 2.11 Obsidian Smart Connections (brianpetro/…) — ~5.5k★
- **What:** ships a **local embedding model**, works offline, and surfaces related notes and blocks.
- **License:** "Smart Plugins License", source-available with a non-compete clause (Jobsi, Inc.). **v4** moved advanced features into paid "Pro" plugins.
- No memory updating or contradiction logic.

### 2.12 Copilot for Obsidian (logancyang/obsidian-copilot) — AGPL-3.0, ~7.8k★
- **V4:** brings **agents** (opencode, Claude Code, Codex) into the vault with permissions, Projects, shared skills, BYOK or local models.
- **Paid "Plus":** hosted models and multi-agent. A vault copilot, not a memory manager.

### 2.13 Basic Memory (basicmachines-co/basic-memory) — AGPL-3.0, ~4k★
- **Representation:** MCP-native. Knowledge lives as **plain Markdown plus a local SQLite index**. "Observations" and "relations" (wikilinks) form a graph. FastEmbed hybrid search with a cross-encoder rerank. Schema tools infer, validate and diff structure. An Obsidian-compatible cloud tier also exists.
- **Contradiction handling:** none automatic; the LLM client or the user edits notes.
- **Reasoning** happens in whatever MCP client is used, often a cloud one.

### 2.14 Anthropic/MCP reference "memory" server (modelcontextprotocol/servers → src/memory)
- **Representation:** a knowledge graph of entities, relations and atomic "observations" stored in **one JSONL file**.
- **Tools:** create, delete, search and read_graph.
- **Limits:** the repo calls it a **reference implementation, not production-ready**. Dedup is by entity name only, with no validity times or contradiction handling.

### 2.15 Screenpipe (screenpipe/screenpipe; moved from mediar-ai) — Rust, ~21.7k★, **YC S26** (Launch HN 2026-07-23)
- **Capture:** continuous **local** screen capture (accessibility tree, OCR fallback), audio transcription, keystrokes and app switches, stored in SQLite with optional encryption at rest.
- **Integration:** an MCP server for Claude, Codex and others, plus "pipes" (agents and automations).
- **License:** now a **source-available commercial license**: free for personal or non-commercial use, 7-day evaluation for companies.
- **HN concerns:** "privacy nightmare"; mixing personal and work data. It captures raw history rather than a consolidated memory.

### 2.16 AnythingLLM (Mintplex-Labs/anything-llm) — MIT, ~66k★
- **What:** a local-first desktop or Docker app. LanceDB by default (pgvector optional). Agents, no-code flows, **scheduled tasks** (cron) and MCP.
- **Memories:**
  - Capped at 20 per workspace plus 5 global.
  - Extracted by an **Observer → Reflector** pipeline: the observer proposes up to 3 candidates *with confidence ratings*; the reflector dedups, picks scope, consolidates, and **drops low-confidence items**.
  - Runs every 3h when idle.
  - This is a **confidence-filtered memory write, with a single model and no escalation.** Memory content goes to the LLM provider inside the prompt.

### 2.17 Open WebUI (open-webui/open-webui) — ~153k★, "Open WebUI License" (BSD-3-based plus a branding clause)
- **Memory:** now **model-managed through native tool calls** (add, update, replace, delete, search and list memories, with paths). Plus RAG "Knowledge" collections (9 vector databases) and a SQLite or Postgres backend.
- **Contradiction handling:** no conflict detection beyond the model's own replace or delete. The docs site even has a "Sovereign AI" page.

### 2.18 Onyx (onyx-dot-app/onyx; ex-Danswer) — MIT CE + EE, ~32k★
- **What:** an enterprise context layer. Connectors carry **permissions**; hybrid index; agentic RAG; custom agents with **actions** and MCP; self-hosting with Ollama or vLLM.
- **Enterprise Edition:** RBAC and query-history audit.
- Team search, not personal memory; a heavy stack (Redis, MinIO…).

### 2.19 Honcho (plastic-labs/honcho) — AGPL-3.0, ~7.3k★
- **What:** "reasoning-first memory". A background **deriver** turns messages into *conclusions* (deductive and inductive), peer representations and peer cards, plus "dreaming". Storage is Postgres + pgvector.
- **Model defaults are statically tiered:** Gemini for the deriver, summaries and low-level dialectic; **Anthropic for high-level dialectic and dreaming**. That is fixed tiering, not confidence routing. Managed at api.honcho.dev or self-hosted with those provider keys.

### 2.20 Hindsight (vectorize-io/hindsight) — MIT, ~28.6k★, created Oct 2025
- **Operations:** `retain`/`recall`/`reflect`.
- **Representation:** separates **world facts vs. the agent's own experiences**. Background **observations** are deduplicated beliefs with evidence quotes and a *proof count*, refined rather than overwritten. Also mental models and knowledge pages, and per-bank "disposition" traits.
- **Memory Defense:** redacts or blocks PII and secrets at retain time.
- **Deployment:** Postgres; 25+ providers including Ollama and LM Studio. SOTA claims are self-reported, with an external reproduction mentioned.

### 2.21 memU (NevaMind-AI/memU) — ~14.4k★ (README badge Apache-2.0)
- **What:** mines agent session logs into Markdown **memory and skills**. `MemoryService` makes **no LLM calls**; the host agent does the judging. Storage is SQLite or Postgres/pgvector. Adapters exist for OpenClaw and Hermes.

### 2.22 OpenViking (volcengine/OpenViking) — AGPL-3.0, ~38.7k★, created 2026-01-05 (ByteDance's Volcengine)
- **What:** a "context database" presented as a virtual filesystem (`viking://`) for knowledge, memory and skills. Summaries come in tiers: **L0** (one-line abstract), **L1** (overview), **L2** (full content).
- **Local:** Ollama is supported. Benchmark gains are self-reported.

### 2.23 Notable 2025–2026 entrants (personal agents and memory patterns)
- **OpenClaw** (openclaw/openclaw, ex-Clawdbot/Moltbot):
  - ~390k★, created Nov 2025. A self-hosted assistant reached through WhatsApp, Telegram, iMessage and others. Memory lives in workspace Markdown files (MEMORY.md etc.). Tools run on the host unless sandboxed.
  - **Security crisis:** CVE-2026-25253 (published 2026-02-01) was a one-click token leak and RCE through the `gatewayUrl` query parameter, fixed in 2026.1.29.
  - Koi Security's "ClawHavoc" (Feb 2026) found **341 malicious ClawHub skills out of 2,857**, later 824 out of 10.7k.
  - The cautionary tale for "sovereign agent that acts".
- **Hermes Agent** (NousResearch/hermes-agent) — MIT, ~249k★.
  - **Memory:** tiny curated memory files (MEMORY.md ≈2,200 characters, USER.md ≈1,375) injected as a frozen snapshot, plus FTS5 search over sessions. Pluggable providers: Honcho, OpenViking, Mem0, Holographic, RetainDB, ByteRover, Supermemory, and a community Hindsight provider. Memory writes are **security-scanned**, and `memory.write_approval` can require a human for *every* write.
  - **Smart approvals** (the default): an **auxiliary LLM** rates command risk. It auto-approves low risk, auto-denies dangerous commands, and **escalates uncertain cases to the human**. The approval model is configurable separately (provider, model, base_url) and defaults to the main model.
  - **`hermes approvals suggest`** mines 90 days of approvals into proposed allowlist patterns. It never applies them automatically and excludes destructive classes.
  - Cron scheduler and self-improving skills.
- **Karpathy "llm-wiki" gist** (2026-04-04): raw sources (immutable), an LLM-maintained Markdown wiki, a schema file, and three operations: ingest, query and lint. Lint looks for contradictions and gaps. GBrain's repo was created the next day, and many re-implementations followed. A causal link between the two is only claimed by secondary sources.
- **Notion "Lore"** (makenotion/lore, MIT, created Apr 2026; blog 2026-08-18):
  - Shared agent memory stored in Notion databases (Projects, Topics, Memories, Entities, Facts), accessed over MCP.
  - Relations `supersedes`, `scoped` and `conflicts_with`; **facts expire by default unless reinforced**.
  - Pilot result: **only 55–60% of stored information stayed valuable**.
- **Vestige** (samvallad33/vestige, AGPL-3.0, Rust, ~633★): local MCP memory with FSRS-6 decay, flagged contradictions, reversible forgetting, and an action gate built on signed "receipts" and one-use permits. Niche, with paid tiers.
- **OpenKnowledge** (inkeep/open-knowledge, GPL-3.0, ~4.3k★; Show HN 2026-06-25, 381 points): a local-first AI Markdown IDE and "LLM wiki". An HN commenter noted it cannot use a local LLM.
- **MagenticLite** (microsoft/magentic-ui, MIT, ~10k★): "big tasks, small models". An on-device-friendly orchestrator (MagenticBrain) plus the Fara browser model. It stops for approval before critical actions and runs inside a VM sandbox.
- **Agent Approve** (2026-07-07): an iOS/Apple Watch app for **one-tap approvals across 14+ coding agents** (Claude Code, Codex, OpenClaw, Hermes…). Pattern policies cover more than 250 destructive commands; event history; cloud relay with E2E encryption; $14.99/mo. **Watch approvals exist, but only for coding agents and only pattern-based.**

---

## 3. Commercial references

| Product (date) | Memory model | Local? | Update/contradiction | Actions & approval | Known issues / complaints |
|---|---|---|---|---|---|
| **ChatGPT memory → "Dreaming"** (saved memories + chat history from 2025-04-10; Dreaming 2026-06-04) | Background process synthesises a profile from chats, files and connected apps; one memory toggle plus an editable summary; legacy saved memories still exist | No | Time-aware rewriting ("going to Singapore" → "went to Singapore") | (not re-verified here) | XDA (2026-06-22): the model, not the user, decides what is remembered; the summary doesn't show everything; deletion is hard; shared accounts blend. HN (2026-08): memory "becomes useless due to staleness or mis-application across contexts" |
| **Claude memory** (Team/Ent first, month n/v; free + import tool 2026-03-02; "topics" update 2026-08-25) | Memory as **topic files** users can read, edit and delete; also works in Cowork; project-scoped for Team/Ent | No | Topics added as you chat; sensitive categories excluded by default; incognito chats exist | Cowork agent | Cloud |
| **Gemini Personal Intelligence** (2026-01-14, US AI Pro/Ultra; wider rollout later) | Reasons over Gmail, Photos, YouTube and Search history; opt-in per app | No | User corrects in chat or gives feedback; Google itself **admits "over-personalization"** (the golf-photos example) | — | No direct training on Gmail/Photos (per Google) |
| **Apple Siri AI personal context** (WWDC 2026-06-08; shipped **2026-09-14**, English beta, not EU/China) | Searches messages, email and photos; app actions; semantic-index-style personal context | **Hybrid:** on-device model, with **Private Cloud Compute** for requests needing more compute (a size-based escalation precedent) | Not documented | Cross-app actions | Delayed from iOS 18.4 (2025) and again in the 26.x cycle; India/English-IN not mentioned |
| **Microsoft Recall** (backlash June 2024; opt-in redesign Sept 2024; Copilot+ rollout 2025) | Encrypted local snapshots plus a vector DB inside a VBS enclave; Windows Hello gate | **Yes** | None: raw capture, no consolidation | "Click to Do" | Signal blocks it via a DRM flag (May 2025); **"TotalRecall Reloaded"** (GeekWire, 2026-04-15): malware can copy screenshots from process memory; limited to Insiders |
| **Limitless / Rewind** (Meta acquisition **2025-12-05**) | Rewind: local Mac screen/audio memory; Pendant: cloud | Rewind yes | — | — | **Rewind capture disabled 2025-12-19**; pendant sales stopped; service ended in EU/UK and others. HN users lamented a local-only app being "kneecapped" (the **vendor kill-switch** argument for sovereignty) |
| **Glean** | **Enterprise Graph** (content, people, activity) plus a **Personal Graph** (activity from 100+ sources → tasks and projects); permission-aware answers | Customer-hosted in GCP/AWS | Connector sync plus ACLs | Agents toolkit (LangGraph, ADK…) | Enterprise-only |
| **Notion AI** (Notion 3.0 Agents 2025-09-18; 3.7 agent skills 2026-09-15; Lore 2026-08-18) | An "instructions page" acts as the agent's growing memory; Lore adds fact databases | No | Page edits; Lore uses supersedes/conflicts_with and expiry | Agents act inside Notion | Lore pilot: 40–45% of memory not valuable |
| **Mem 2.0** (2025-10-01) | Cloud notes, offline-first clients, "Heads Up" resurfacing (e.g. meeting history) | No | — | Agentic chat creates and organizes notes | — |
| **Tana** | Outliner KG with supertags; Meeting Agent (bot or botless) extracts action items and decisions and enriches person nodes | No (cloud processing) | — | Tasks created with **no documented review step** | — |
| **Meta Muse** (2026-09-08) | Personal agent on **its own cloud VM**; memory files the user can inspect, edit and download | No | — | **Human approval for connector actions, purchases and high-risk forms**; ensembles of classifiers against prompt injection | Privacy scrutiny at launch |
| **Claude Code auto mode** (eng. post 2026-03-25; default for Pro/Max/Team Aug 2026) | — | No (server-side) | — | **Two-stage transcript classifier (Sonnet 4.6):** a single-token filter biased toward blocking (8.5% FPR), then CoT **only when flagged** (0.4% end-to-end FPR on 10k real actions; 17% FNR on 52 real overeager actions). Blocked → "find a safer path"; **escalates to a human after 3 consecutive or 20 total denials** | No user-visible decision log or learning from overrides is described |
| **GPT-5** (Aug 2025) | — | No | — | A fast model plus a thinking model and a **real-time router trained on user model switches, preferences and measured correctness** (dual-process routing that learns) | Router is opaque to users |
| **Amazon Bedrock Intelligent Prompt Routing** (GA Apr 2025) | — | No | — | Predicts response quality per model within a family and routes to the cheapest adequate one | — |
| **Cleanlab TLM** | — | No | — | A **trust score per LLM output**; low scores (including tool calls) escalate to a human or a fallback | — |

---

## 4. Memory-quality complaints: evidence → implication

| Failure mode | Evidence (source, date) | Implication for Omnitrix |
|---|---|---|
| **Junk writes** | mem0#4573 (2026-03-27): 97.8% of 10,134 memories were junk; restating the system prompt was 52.7% of it; cron noise, transient tasks, hallucinated profiles (gemma2:2b) and **secrets** also appeared. Notion Lore pilot: 55–60% useful | A **System-1 write gate** (noise? already known? transient? sensitive?) is the most defensible S1 use. Use mem0's junk taxonomy as test fixtures |
| **Silent wrong contradictions** | graphiti#1728 (2026-08-04): the small-model judge retired unrelated true facts (41% invalidated; 3 of 4 audited were wrong); mem0#4956/#5867: ADD-only keeps stale facts | Contradiction decisions need **confidence plus escalation plus a visible, reversible record** |
| **Silent failures** | graphiti#1707 (dropped episodes), mem0#5245 (silent loss), gbrain#5012 (success reported on failure) | "Nothing silent": every decision and write gets an outcome row |
| **Opacity / loss of control / creepiness** | XDA on ChatGPT Dreaming (2026-06-22); HN "privacy nightmare" on Screenpipe (2026-07-23); Gemini admits over-personalization | A ledger the user can inspect ("why do you believe this?") and approvals on the watch |
| **Staleness / misapplication** | HN comment 2026-08-31; ChatGPT built Dreaming specifically to fight stale saved memories; GBrain refuses stale output | Bitemporal facts plus "refuse when stale" |
| **Ingestion cost** | graphiti#467 (~$0.80 per 40 short chats); GBrain's 24/7 path "highest-cost"; Memobase and Mem0 both redesigned to cut LLM calls | S1 resolves most decisions locally; show a tokens-avoided meter |
| **Small-model brittleness** | Graphiti README (small models break the JSON schema); mem0#4573 (gemma2:2b hallucinated profiles) | Keep S1 on **narrow classification with constrained output**, never free-form extraction |
| **Acting agents get owned** | OpenClaw CVE-2026-25253; 341→824 malicious skills; Hermes scans memory writes; Muse uses classifier ensembles | Gate every outbound action by impact and confidence; treat inbound content as untrusted; quarantine memory candidates that come from untrusted sources |
| **Vendor kill-switch** | Rewind capture disabled after the Meta deal (2025-12-19); OpenMemory sunset (2026-04) | The "own it" story: OSS, local models, and export of the whole ledger and memory |

---

## 5. Comparison table (project × storage × local × update/contradiction × actions × audit × weaknesses)

| Project | Storage / representation | Local? | Update · dedup · contradiction · forgetting | Actions | Approval / audit | Main weaknesses |
|---|---|---|---|---|---|---|
| **GBrain** | MD pages in git + PGLite/Postgres+pgvector; compiled truth + timeline; typed edges; facts w/ provenance | Storage ✔; LLM features default hosted (Anthropic-pinned subagents; Ollama = embeddings only) | Nightly dream: dedup people, fix citations, salience, **contradiction reports**; correction/withdraw; loops close by state; commitments go stale | Via harness + skills; cron/autopilot | Scoped OAuth MCP; job audit; loops never deleted; **no per-decision confidence** | Complexity, API cost, single-operator bias, silent-success bugs |
| **Utopia** | Postgres+pgvector+Tantivy; bitemporal KG; ontologies | ✔ (OpenAI-compat local) | Versioned facts; 3 conflict classes; 3-stage ER; **confidence-gated adjudication → tool second look → human; precedents; fuse** | Read-only agent/MCP; exec gate = roadmap | **Append-only ledger + `agent_decisions`** | v0.1; enterprise/doc scope; single model, uncalibrated confidence |
| **Mem0 v3 OSS** | Vectors + BM25 + entity links (graph removed) | ✔ | **ADD-only**; recency via ranking | — | — | Junk (97.8% audit); stale facts; OpenMemory sunset |
| **Graphiti / MCP** | Temporal KG on Neo4j/FalkorDB/Neptune | Possible (fragile w/ small models) | Bi-temporal invalidation; small_model judges dedup/contradiction | — | Episode provenance | Collateral invalidation; cost; no Postgres |
| **Zep Cloud** | Managed Graphiti | ✘ (CE deprecated) | As Graphiti | — | — | Cloud only |
| **Letta Code** | Memory blocks + git-backed MemFS | Partial (Cloud default) | Dreaming consolidation; dup audits; no conflict logic | Full agent | Rule-based permissions; git history | V1 retired; cloud default |
| **Cognee 1.0** | KG + vectors (+relational) | ✔ (local extract/embeds) | remember/improve/forget; feedback | Via agents/MCP | — | Prod PG-graph licensed; default OpenAI |
| **MemOS** | Memory graph (Neo4j+Qdrant) / SQLite plugin | ✔ plugin | NL feedback/correction; smart dedup; L1–L3 | Via hosts | Memory viewer | Complex; self-reported benchmarks |
| **Supermemory** | Embedded graph + profiles | ✔ (local binary, Ollama) | Claims contradiction handling + auto-forgetting | — | — | Connectors/MCP platform-only; claims unverified |
| **Memobase** | Profiles + event timeline (PG+Redis) | ✔ | Buffered batch updates | — | — | Chatbot focus; slowing |
| **Second Me** | L0/L1 text + L2 LoRA/DPO model | ✔ (MLX) | Retrain | Network/roleplay | — | Dormant; heavy; no citations |
| **Khoj** | Postgres+pgvector doc index | ✔ | Re-index | Agents; scheduled automations | — | Not fact-memory |
| **Reor** | LanceDB over MD | ✔ | — | — | — | **Archived** |
| **Smart Connections** | Local embeddings over vault | ✔ | — | — | — | Source-available non-compete; Pro gating |
| **Copilot for Obsidian** | Vault + Projects | Partial (BYOK/local) | — | Agents in vault | Permissions | Paid for hosted/multi-agent |
| **Basic Memory** | MD + SQLite; observations/relations | ✔ (reasoning in client) | LLM/user edits; schema validate | Via client | — | No auto conflict handling |
| **MCP memory (ref.)** | JSONL KG | ✔ | Manual tools; no validity | — | — | Reference only |
| **Screenpipe** | SQLite screen/audio/a11y | ✔ | Raw capture | Pipes | — | Commercial source-available; privacy |
| **AnythingLLM** | LanceDB/pgvector; 20+5 memories | ✔ | **Confidence-rated candidates, dedup, low-conf filtered** | Agents, flows, cron | — | Tiny caps; single model |
| **Open WebUI** | SQLite/PG; tool-managed memory; KBs | ✔ | Model add/replace/delete | Tools/pipes | Admin controls | Relies on model judgment |
| **Onyx** | Permissioned hybrid index | ✔ self-host | Connector sync + ACLs | Agents + actions + MCP | EE RBAC, query history | Enterprise, heavy |
| **Honcho** | PG+pgvector; conclusions/representations | Partial (Gemini/Anthropic defaults) | Background deriver + dreams | — | — | Cloud-LLM defaults |
| **Hindsight** | PG; facts/experiences/observations | ✔ (Ollama) | Observations refined w/ proof counts | — | PII/secret redaction | New; self-reported SOTA |
| **memU** | SQLite/pgvector; MD skills | ✔ | Host agent decides | Via host | — | Quality = host agent |
| **OpenViking** | `viking://` FS; L0/L1/L2 | ✔ (Ollama) | "Self-evolving" (details n/v) | Via host | — | AGPL |
| **OpenClaw** | Workspace MD memory | ✔ (models pluggable) | Agent-written | **Full assistant** | DM pairing; host tools unless sandboxed | CVE + malicious skills |
| **Hermes Agent** | Tiny MD memory + FTS5 + providers | ✔ | Consolidate when full; dup block; write scan | **Full agent + cron** | **Aux-LLM approve/deny/escalate; approval mining; optional memory-write approval** | Tiny core memory; no calibration |
| **Notion Lore** | Notion DBs | ✘ | supersedes/conflicts_with; expiry unless reinforced | Via MCP | Notion history | 40–45% junk in pilot |
| **Vestige** | Local Rust store | ✔ | Decay (FSRS-6); contradictions flagged | Action gate w/ receipts | Signed receipts | Niche, paid tiers |
| **ChatGPT (Dreaming)** | Cloud synthesized profile | ✘ | Background, time-aware | Agent | Partial summary | Opacity, control |
| **Claude memory** | Cloud topic files | ✘ | Add-as-you-chat; editable | Cowork | Viewable files | Cloud |
| **Gemini PI** | Cloud over Google apps | ✘ | Feedback corrections | — | Opt-in | Over-personalization |
| **Apple Siri AI** | On-device + PCC | Hybrid | n/d | App actions | — | English beta; delays |
| **MS Recall** | Local encrypted snapshots | ✔ | None | Click to Do | Windows Hello | Security findings |
| **Rewind/Limitless** | Local / cloud | — | — | — | — | Shut down (Meta) |
| **Glean** | Enterprise + personal graph | Customer cloud | Sync + ACLs | Agents | Permission-aware | Enterprise only |
| **Notion AI / Mem / Tana** | Cloud pages / notes / supertag KG | ✘ | Page edits | In-app agents; Tana meeting tasks | Version history | Cloud; no review step (Tana) |
| **Meta Muse** | Cloud VM + memory files | ✘ | n/d | Email, purchases, browser | **HITL for connectors/purchases; classifier ensembles** | Cloud; privacy |

(n/d = not documented; n/v = not verified)

---

## 6. Novelty check (item 5): does anything already combine S1 gating + calibrated escalation + per-decision confidence audit + learning from corrections?

| System | Cheap/small first tier | Escalate to bigger model/agent | Escalate to human | Per-decision confidence log | Learns from corrections | Memory decisions | Action decisions | Fully local |
|---|---|---|---|---|---|---|---|---|
| **Utopia governance** (2026-09) | Partial (batch call, same model) | ✔ (tool "second look") | ✔ | **✔ `agent_decisions`** | **✔ precedents + rationale; history moves threshold; fuse** | ✔ (entity merges only) | Roadmap | ✔ possible |
| **Claude Code auto mode** (2026-03) | ✔ single-token stage | ✔ CoT stage | ✔ after 3/20 denials | Not described | Not described | ✘ | ✔ | ✘ |
| **Hermes smart approvals** | Configurable aux model | ✘ | ✔ uncertain → human | Approvals stored in session DB | ✔ allowlist mining (human-applied) | Binary write-approval only | ✔ shell | ✔ possible |
| **Graphiti** | ✔ static small_model | ✘ | ✘ | ✘ | ✘ | ✔ | ✘ | Possible |
| **AnythingLLM memories** | ✘ (same model) | ✘ | ✘ | ✘ (filters low-conf) | ✘ | ✔ | ✘ | ✔ |
| **GBrain open loops** | ✔ deterministic rules first | LLM extractor | Via harness | Loop state history | skillopt (procedures) | ✔ | Via harness | Partial |
| **Cleanlab TLM** | — | — | ✔ | ✔ trust score/output | ✘ | ✘ | ✔ tool calls | ✘ |
| **GPT-5 router / Bedrock routing** | ✔ fast model | ✔ | ✘ | ✘ (internal) | ✔ (GPT-5: user signals) | ✘ | ✘ | ✘ |
| **Apple on-device → PCC** | ✔ | ✔ (by compute need) | ✘ | ✘ | ✘ | — | App actions | Hybrid |
| Research (other slice): SOFAI (arXiv 2110.01834), SwiftSage (2305.17390), Talker-Reasoner (2410.08328) | Dual-process agent *architectures*, not productized personal memory |

**Verdict.** At the mechanism level, novelty is **low to moderate**. Cascade gating with human escalation now ships in Claude Code, Hermes and Meta Muse. Utopia already has a confidence ledger plus precedent learning for one memory decision type. At the **combination level for a personal, local second brain**, novelty is **moderate to high**; no one found ships all of the following:
- one decision fabric spanning **both memory decisions (write, merge, contradict, retrieve, relevant, grounded) and actions (send, schedule, pay)**;
- a separate **small local System 1** with **measured calibration** (reliability curves, per-decision-type thresholds) rather than self-reported confidence;
- a **user-facing ledger** (tier, confidence, evidence, latency, cost, outcome);
- **learning that feeds back into System 1** (precedent retrieval, threshold recalibration, or adapter fine-tuning) with a visible escalation-rate curve.

For judges: show the delta against Utopia, Claude Code and Hermes explicitly. That turns "someone already did this" into "the pattern is proven, and we're first to bring it to a sovereign personal assistant."

---

## 7. White space for Omnitrix (demo-able)

1. **A write gate that measurably stops junk.** System 1 labels each candidate memory keep, duplicate, transient, noise or sensitive, and shows "memory yield" live against naive LLM extraction. Seed test fixtures from mem0#4573's junk categories; also cite Lore's 55–60%.
2. **Confidence-gated contradiction handling that never retires facts silently.** Replay the Graphiti #1728 failure: S1 is unsure, S2 checks the evidence, and a watch card appears only if it is still unclear. Every retired fact shows who retired it, why and at what confidence, with a one-tap revert.
3. **Decision-conflict check before anything leaves the machine.** Diff each outbound draft against past decisions and promises (price floors, delivery dates, credit terms) and block or explain conflicts. GBrain tracks commitments but does not check drafts against them at send time; it even lists fulfillment detection as future work.
4. **One ledger for every decision type**: memory write, entity merge, contradiction, needs-retrieval, relevance, groundedness, needs-approval and action. Each row records tier (S1/S2/human), confidence, evidence links, latency, tokens and final outcome, and can be exported. The "nothing silent" guarantee answers the silent drops in Graphiti, Mem0 and GBrain.
5. **Calibration you can see.** Show a reliability diagram and ECE for S1 on a small labeled set, with a per-decision-type threshold slider that trades escalation rate against error rate on stage. No one surveyed shows calibrated confidence; Utopia uses the model's self-reported number with fixed 0.8/0.85/0.75 thresholds.
6. **A learning curve on stage.** Replay the same case twice: the first time it escalates; after one human correction (stored with a rationale, as Utopia does), S1 handles it alone. Plot escalation rate falling over the demo. Add a Utopia-style **fuse** that automatically demotes a decision type after repeated human reverts.
7. **Gate by impact, not just confidence.** Anything irreversible or outbound (email/WhatsApp send, payment, calendar invite to externals) goes to a human unless both tiers agree *and* impact is low. Reversible internal operations can run automatically (Utopia 0027; Claude Code biases stage 1 toward blocking).
8. **Watch approvals with evidence.** Existing watch approval apps target coding agents and use pattern rules. Omnitrix's card would show the proposed action, the confidence, *the conflicting past decision or promise*, and "approve / edit / always for this contact". That last button feeds the learning loop, like Hermes' approval mining but confirmed per item.
9. **An airplane-mode demo.** Run every tier, including System 2, on the M5 Pro through Ollama with Wi-Fi off. Contrast with GBrain's hosted chat and Anthropic-pinned subagents, Honcho's Gemini/Anthropic defaults, Graphiti and Cognee's OpenAI defaults, Muse/ChatGPT/Gemini in the cloud, and **Rewind's vendor kill-switch**.
10. **Cost and energy meter.** Show the share of decisions S1 settles and the S2 tokens avoided, against "an LLM call per write" designs (Graphiti cost complaint, GBrain's "highest-cost path").
11. **Memory-poisoning resistance.** Plant an injected email that tries to insert a fake "decision" ("we agreed to 60-day credit"). Its low-trust provenance puts it in quarantine and triggers escalation. OpenClaw's malicious skills and Hermes' write scanning show this threat is real.
12. **"Why do you know this?" on every answer.** Each recalled fact links to its source span and to the decision row that admitted it. This is the direct answer to Dreaming's opacity and Gemini's over-personalization.
13. **Promise lifecycle for an Indian SMB owner.** Cover open → due → fulfilled or broken across email, WhatsApp exports, voice notes and PDF invoices. GBrain's loop engine is Gmail-only; Siri AI launched English-only, and India isn't mentioned.
14. **"What did I believe when I decided?"** A light bitemporal replay: store valid-time and belief-time on facts in Postgres, so any past decision can be replayed against the memory state at that moment. Utopia has decision replay on its roadmap; Graphiti has bi-temporality but no Postgres backend.

---

## 8. The MSRIT hackathon (item 6), brief
- I could **not** find a public page for an MSRIT (Bengaluru) 2026 hackathon with a "Sovereign AI / Sovereign Second Brain" track, nor its sponsors or judges.
- Related events found:
  - YC's **"Own Your Intelligence Hackathon"** (San Francisco, **2026-09-27**), hosted by River AI, **GBrain**, Memorable, QM, Superset and UFO. It shares the "own your intelligence" framing, and GBrain's ecosystem (e.g. Memorable procedural memory) is clearly promoting itself this month.
  - "Build with Gemma: Bengaluru AI Sprint 2026", co-organized with MSRIT's ISE department (different theme).
- If GBrain or DeepLethe people are among the judges, visible interoperability could plausibly earn points: a GBrain-compatible MCP surface, or Utopia-style bitemporal facts plus a decision ledger. **This is unverified; ask the organizers.**

---

## 9. Open questions
1. Can a 1–4B local model make these narrow binary decisions accurately *and* be calibrated with logprob-based confidence? Is verbalized confidence usable? (routing/calibration and model-zoo slices)
2. Memory substrate: keep Mem0 (ADD-only, graph removed, OpenMemory gone), adopt GBrain via MCP (Postgres-compatible, but TypeScript/Bun and cloud-leaning LLM paths), or build lean Postgres tables (facts with valid/belief time plus a `decisions` ledger modelled on Utopia's `agent_decisions`)?
3. Graphiti as a stretch goal needs Neo4j or FalkorDB. Is a second database worth it for a hackathon, or should bitemporal edges be emulated in Postgres?
4. Which learning mechanism fits the time budget and still shows a visible curve: precedent retrieval (few-shot), per-type threshold recalibration, or a nightly LoRA? Second Me's LoRA route looks heavy and stalled.
5. How should "impact" (reversibility, external reach) be scored per action, and should it override confidence? Utopia says yes.
6. How reliable are watch notifications, and what is the round-trip latency for approvals? Are there fallbacks (phone, desktop) when the watch is off?
7. Licensing if the team reuses code: AGPL (Khoj, Basic Memory, Honcho, OpenViking, Vestige), source-available (Screenpipe, Smart Connections), MIT/Apache (GBrain, Utopia, Mem0, Graphiti, Hermes, Hindsight).
8. Indic and code-mixed (Hinglish/Kannada) handling by local S1/S2 models on business email and WhatsApp.
9. Who are the actual sponsors and judges, and do they weight "uses organizer-listed tools"?

---

## 10. Unverified (not confirmed from a primary source, or conflicting)
- ChatGPT "Dreaming" recall figures (82.8% vs 41.5%) and the 2026-09-09 settings-panel wording. These come from secondary sources (XDA, others); OpenAI pages returned 403. The existence and date of Dreaming (2026-06-04) are supported by an openai.com search result. The 2025-04-10 "reference chat history" date is also secondary-sourced.
- The launch month of Claude memory for Team/Enterprise (believed to be Sept 2025). Not re-verified; only the 2026-03-02 free-tier rollout and the 2026-08-25 topics post were checked.
- The claim that malicious ClawHub skills wrote into OpenClaw's MEMORY.md/SOUL.md, and the "135,000 exposed instances" figure. Both come from secondary aggregators; only the CVE and the 341/824 malicious-skill counts were cross-checked across multiple outlets.
- Supermemory's actual contradiction and forgetting mechanisms (README claim only). All benchmark "SOTA/#1" claims (Mem0, Supermemory, Hindsight, OpenViking, Honcho) are self-reported.
- Letta Code local-model (Ollama) support. Khoj long-term fact-memory features.
- Whether GBrain chat features work against Ollama via `OPENAI_BASE_URL` (plausible, untested).
- Whether a small local model performs well as Hermes' approval auxiliary (the default is the main model).
- Claude Code auto mode: whether classifier decisions are logged for users or used for learning. Not described in the 2026-03-25 post.
- Glean Personal Graph GA date and deployment details. Tana multi-model support date: a secondary source said "December 2026", which is impossible, so it was ignored.
- Mem 2.0 date: the primary blog says 2025-10-01; some reviews say "early 2026".
- The Slite GBrain review ($4–15/user/month; "no fact-checking") and the Vectorize critique. Both are competitor-authored, and the "self-hosted only" claim is outdated given gbrain.io.
- Apple Siri AI availability in India/English (IN).
- MSRIT event details (see §8).
- The OpenWebUI, Onyx and Obsidian feature lists come from READMEs and docs snippets only, not hands-on tests.

---

## Sources (primary first)
- GBrain: https://github.com/garrytan/gbrain · README · docs/guides/open-loops.md, executive-assistant.md, cron-schedule.md, compiled-truth.md, quiet-hours.md, skillopt.md, brain-vs-memory.md · docs/integrations/embedding-providers.md · docs/architecture/key-files/core-ai.md · https://gbrain.io · issues #5012, #5252
- Utopia: https://github.com/deeplethe/utopia (README; docs/decisions/0025–0028; crates/utopia-server/src/adjudication.rs)
- Mem0: https://github.com/mem0ai/mem0 (README; issues #4573, #4956, #5867, #5245, #5352, #4695, #4923; PRs #6530, #4520) · https://docs.mem0.ai/migration/oss-v2-to-v3 · arXiv 2504.19413
- Graphiti/Zep: https://github.com/getzep/graphiti (README, mcp_server/README.md, graphiti_core/utils/maintenance/*.py, prompts/dedupe_edges.py; issues #1728, #467, #1707, #963, #868, #760) · https://github.com/getzep/zep · arXiv 2501.13956
- Letta: https://github.com/letta-ai/letta · https://github.com/letta-ai/letta-code · https://docs.letta.com/letta-code/memory · https://docs.letta.com/letta-code/permissions · arXiv 2504.13171, 2310.08560
- Cognee https://github.com/topoteretes/cognee · MemOS https://github.com/MemTensor/MemOS (arXiv 2507.03724) · Supermemory https://github.com/supermemoryai/supermemory, https://supermemory.ai/docs/self-hosting/overview · Memobase https://github.com/memodb-io/memobase · Second Me https://github.com/mindverse/Second-Me (arXiv 2503.08102)
- Khoj https://github.com/khoj-ai/khoj, https://docs.khoj.dev/features/automations/ · Pipali https://github.com/khoj-ai/pipali · Reor https://github.com/reorproject/reor · Smart Connections https://github.com/brianpetro/obsidian-smart-connections · Copilot https://github.com/logancyang/obsidian-copilot · Basic Memory https://github.com/basicmachines-co/basic-memory · MCP memory https://github.com/modelcontextprotocol/servers/tree/main/src/memory
- Screenpipe https://github.com/screenpipe/screenpipe (LICENSE.md), Launch HN https://news.ycombinator.com/item?id=49024620 · AnythingLLM https://github.com/Mintplex-Labs/anything-llm, https://docs.anythingllm.com/features/memories · Open WebUI https://github.com/open-webui/open-webui, https://docs.openwebui.com/features/chat-conversations/memory/ · Onyx https://github.com/onyx-dot-app/onyx · Honcho https://github.com/plastic-labs/honcho · Hindsight https://github.com/vectorize-io/hindsight · memU https://github.com/NevaMind-AI/memU · OpenViking https://github.com/volcengine/OpenViking
- OpenClaw https://github.com/openclaw/openclaw · NVD CVE-2026-25253 · Koi "ClawHavoc" https://www.koi.ai/blog/clawhavoc-341-malicious-clawedbot-skills-found-by-the-bot-they-were-targeting · The Hacker News 2026-02 · Unit 42 https://unit42.paloaltonetworks.com/openclaw-ai-supply-chain-risk/
- Hermes Agent https://github.com/NousResearch/hermes-agent (website/docs/user-guide/security.md, configuration.md) · https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
- Karpathy llm-wiki https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f · Notion Lore https://github.com/makenotion/lore, https://www.notion.com/blog/building-shared-memory-for-ai-agents-in-notion · Vestige https://github.com/samvallad33/vestige · OpenKnowledge https://github.com/inkeep/open-knowledge, https://news.ycombinator.com/item?id=48675435 · MagenticLite https://github.com/microsoft/magentic-ui · Agent Approve https://www.prnewswire.com/news-releases/agent-approve-brings-ai-agent-observability-and-control-to-your-wrist-302819165.html
- Obsidian 1.12 CLI https://obsidian.md/changelog/2026-02-27-desktop-v1.12.4/ , https://obsidian.md/help/cli
- ChatGPT: https://openai.com/index/chatgpt-memory-dreaming/ (403 to fetch; via search result) · https://openai.com/index/memory-and-new-controls-for-chatgpt/ · XDA https://www.xda-developers.com/chatgpt-quietly-rewrites-its-memories-of-you-not-sure-i-like-it/ · GPT-5 https://openai.com/index/introducing-gpt-5/ , arXiv 2601.03267
- Claude: https://claude.com/blog/memory · https://claude.com/blog/claudes-memory-works-everywhere-and-you-decide-whats-in-it · MacRumors 2026-03-02 · Claude Code auto mode https://www.anthropic.com/engineering/claude-code-auto-mode , https://claude.com/blog/auto-mode-default-in-claude-code
- Gemini https://blog.google/innovation-and-ai/products/gemini-app/personal-intelligence/
- Apple https://www.apple.com/newsroom/2026/06/apple-unveils-next-generation-of-apple-intelligence-siri-ai-and-more/ · https://www.apple.com/newsroom/2026/09/siri-ai-a-profoundly-more-capable-and-personal-assistant-is-here/ · https://security.apple.com/blog/private-cloud-compute/
- Recall https://blogs.windows.com/windowsexperience/2024/09/27/update-on-recall-security-and-privacy-architecture/ · GeekWire 2026-04-15 https://www.geekwire.com/2026/one-year-after-its-rocky-launch-microsofts-windows-recall-still-raises-security-red-flags/ · Signal/BleepingComputer 2025-05
- Limitless/Rewind https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/ · HN https://news.ycombinator.com/item?id=46166356
- Glean https://www.glean.com/product/personal-graph · https://docs.glean.com/security/knowledge-graph · Notion https://www.notion.com/releases/2025-09-18 · https://www.notion.com/releases/2026-09-15 · Mem https://get.mem.ai/blog/introducing-mem-2-0 · Tana https://outliner.tana.inc/learn/features/meeting-agent
- Meta Muse https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse
- Routing/trust: https://aws.amazon.com/bedrock/intelligent-prompt-routing/ · https://help.cleanlab.ai/tlm/ · https://security.apple.com/blog/private-cloud-compute/
- HN threads: https://news.ycombinator.com/item?id=46891715 (Mem0 doesn't learn patterns) · https://news.ycombinator.com/item?id=49513521 (staleness) · https://news.ycombinator.com/item?id=48091611 (GBrain)
- Hackathon context: https://events.ycombinator.com/gbrain-qm-river-memorable-hackathon · https://internshala.com/competitions/build-with-gemma-bengaluru-ai-sprint/
- Research (other slice): arXiv 2110.01834 (SOFAI), 2305.17390 (SwiftSage), 2410.08328 (Talker-Reasoner)
