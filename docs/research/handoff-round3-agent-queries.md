# Handoff: make the brain fast and cheap for AI agents to query (round 3)

*27 Sep 2026. For whoever picks up `engram/` next, human or agent. Read this first, then `README.md`, `brain-design.md` §5, `round2-plan.md` and the literature review (cited as LR §). Everything below was checked against code or measurements, and file references are exact.*

## 0. In one paragraph

engram is a working, measured local second brain covering data, knowledge, memory, reasoning and action. It has a fine-tuned System 1 judge, a gated agent, an Obsidian two-way vault and a 3D web frontend.

What it lacks is **an interface built for AI agents**. Today agents can only reach it through a CLI, a few web-page endpoints, or one monolithic `ask` call.

OpenJarvis (open-jarvis/OpenJarvis, Apache-2.0, ~10k stars) is weaker as a brain but stronger at exactly this. It gives agents small, well-described tools (search with filters, read-only SQL, a "semantic grep"), and it steers them with archetype recipes.

**Round 3 goal:** an agent answers questions about the owner with fewer tool calls, fewer tokens and lower latency, and every claim in its answer points to a record. The brain's measured strengths (tuned hybrid search, the calibrated judge, bitemporal beliefs, the ledger) should become agent tools, not stay buried behind `ask`.

## 1. Where engram is now (measured, on the example owner: Enron `kaminski-v`, M5 Pro 24 GB)

| Area | State |
|---|---|
| Store | Postgres 17 + pgvector (Docker, 127.0.0.1:5433), one database per brain (`--brain`). 11.5k items, 19.4k chunks, 2,013 contacts, 5,940 threads, about 320 MB |
| Search | BM25 over a postings table plus halfvec HNSW, fused with weighted RRF (k = 5, meaning weight 0.5). Keyword search 2 ms median; hybrid 28 ms per question including the embedding. Gold email in the top 5 for 78–81% (MRR 0.61–0.65), where standard RRF (k = 60, equal weights) reaches 0.55–0.59. LR §4.4 |
| Adding data | searchable 13 ms after ingest |
| Judge (S1) | Qwen3-1.7B LoRA fused and quantized to 4-bit (`data/models/judge-v1-q4`, 934 MB, MLX in-process): `relevant` 92% / AUROC 0.97 at about 214 ms per email; `supported` 97% / 0.99. The 14B is worse on what the judge escalates, so those go to the owner. LR §10.5, §10.8 |
| `ask` | 11 s median with the 14B answering (62% graded, same grader as before); **1.7 s** if qwen3:1.7b drafts and the judge upholds it (56%). The judge's support check separates right from wrong answers at AUROC 0.92 (audited). LR §10.6, §10.8 |
| Memory | bitemporal beliefs with verbatim quotes; recall-first gate (S0 bulk rules, then S1, then extraction); Obsidian two-way (`vault.py`) |
| Action | gate with code-set tiers, a 14B intent check and owner approval: WorkBench harm 40% → 6.7% (3.3% with the directory check). LR §11.6 |
| Interfaces | CLI (20 commands); `engram serve` (a local page with HTTP endpoints `/api/{status,search,ask,sql,beliefs,ledger,graph,node,item,add,act}`, bound to 127.0.0.1, origin-checked; SQL runs as the non-superuser `engram_reader`) |
| Quality bar | 53 tests (`uv run pytest -q`, database tests on throwaway DBs), `ruff` clean, a sonnet code review after every part |

## 2. How OpenJarvis builds its brain (verified in source)

OpenJarvis actually has three storage systems:

- **A.** A deep-research knowledge store in `connectors/*`, used by `DeepResearchAgent`.
- **B.** A generic pluggable `MemoryBackend` in `tools/storage/*`, used for context injection.
- **C.** A Rust mirror of B in `rust/crates/openjarvis-tools/src/storage/*`.

It also has a knowledge graph that nothing populates automatically.

| Aspect | OpenJarvis | File |
|---|---|---|
| Schema | one SQLite table `knowledge_chunks` (source, doc_type, title, author, participants, timestamp, thread_id, channel, url, metadata, embedding BLOB, content_hash, soft delete); an FTS5 external-content index with the `porter unicode61` tokenizer; natural key `UNIQUE(source, source_id, chunk_index)` | `connectors/store.py` |
| Ingestion | ~30 connectors (Gmail, Calendar, Slack, Notion, Obsidian, iMessage…) → doc-type-aware chunking (email: reply boundary → paragraph → sentence; 512 tokens) → Ollama `nomic-embed-text`. **Incremental**: a `sync_state` cursor whose watermark advances only after a fully successful run; per-chunk SHA-256 skips re-embedding unchanged documents; an embedder-version check backfills vectors | `connectors/{pipeline,chunker,sync_engine}.py` |
| Retrieval | structured filters (person, time range, sources) are applied first; then BM25 (FTS5) and **brute-force numpy cosine** (no ANN index), fused by RRF with `rrf_k=60`, weights 0.5/0.5, `recall_k=200`. Hits get their **thread context attached** (up to 20 sibling chunks). Heuristics switch calendar-timeline queries to chronological order. An optional ColBERT reranker exists | `connectors/hybrid_search.py`, `retriever.py` |
| Agent tools | `knowledge_search` (filters, markdown results), `knowledge_sql` (read-only by regex blocklist, 50 rows), `scan_chunks` (up to 200 raw chunks fed in batches of 20 to the LLM: "extract anything relevant or reply NOTHING_RELEVANT"), knowledge-graph tools `kg_*` | `tools/knowledge_*.py`, `scan_chunks.py` |
| Steering | the system prompt lists about 10 query archetypes (quick lookup, people lookup, digest, meeting prep, task finder, cross-source synthesis…), each with a tool recipe, plus a research strategy (expand keywords → count with SQL → search → scan → cross-reference → cite). Native tool loop capped at 8 turns, temperature 0.3, a loop guard against repeated calls, and a forced final synthesis turn | `agents/deep_research.py` |
| Facts | a small LLM extracts durable facts per chat turn; an **injection scanner** screens the exchange and each fact; facts carry **trust tiers** (auto / trusted / untrusted) and only recallable tiers ever reach the model; an append-only JSONL store deduplicated by exact text; no supersession or time | `memory/{extractor,service,store}.py` |
| Learning | the model router learns per query class from traces (0.6 × success + 0.4 × feedback, at least 5 samples). No retrieval metrics (recall@k, MRR); QA graded by phrase containment, then an LLM judge | `learning/routing/*`, `evals/scorers/knowledge_base.py` |

## 3. Better or worse than engram

**Where engram is better:**

- **Retrieval quality and speed at scale.** BM25 over real postings plus a pgvector HNSW index, against brute-force cosine that its own docstring says to replace. The fusion is tuned and measured: OpenJarvis's k = 60 with equal weights is exactly the "standard RRF" engram measured at MRR 0.55–0.59 against 0.61–0.65.
- **Calibrated small-model judgements.** Typed yes/no and choice questions with logprob-calibrated bands, a precision target, and escalation routed by measurement. OpenJarvis has no System 1 judge; it spends LLM calls (`scan_chunks`: 200 chunks ÷ 20 = 10 LLM calls per scan) where engram's judge costs ~0.2 s per item.
- **Memory with time.** Bitemporal beliefs, verbatim-quote checks, and supersession including the owner's corrections, against exact-text dedup with no notion of time.
- **Audit and safety.** A hash-chained ledger of every judgement. Action tiers set by code, with a measured harm reduction. The SQL console runs under a non-superuser role, where OpenJarvis uses a regex blocklist. That blocklist doesn't stop reads of other tables or SQLite pragmas, and on Postgres a blocklist would not have stopped `COPY … TO PROGRAM`, which engram found and closed.
- **Measurement.** Recall@k and MRR, held-out calibration, audited QA, WorkBench. OpenJarvis measures model routing, not retrieval.
- **Structured citations.** `ask` returns item ids. OpenJarvis regex-parses `**Result N:**` out of markdown.

**Where OpenJarvis is better, and what to take:**

1. **An agent-first tool surface.** Small tools with clear parameters and filters (person, time, source), SQL for counts and aggregates, and a recall sweep. engram offers agents one opaque `ask`.
2. **Steering by archetypes.** A fixed recipe per query type makes small models use the tools well. engram can do the recipe choice in code or S1 instead of a long prompt (§4, W2).
3. **Thread context on every hit**, with a cap. engram collapses results to one per item but never attaches the conversation.
4. **Trust tiers on recalled memory, and an injection scan** before anything extracted from untrusted mail reaches a model. engram's gate keeps untrusted content out of the *action* check, but beliefs extracted from email are recalled without a trust tier.
5. **Incremental sync discipline.** Watermarks that advance only on success, content-hash skip of re-embedding, and embedder-version backfill. engram has content-hash dedup and `rederive`, but no per-connector cursor or embedder versioning.
6. **Breadth of connectors.** Around 30, against engram's Enron / QMSum / uploads / Obsidian. Useful later; out of scope here.

**Not to copy:** brute-force vector scans; regex-parsed citations; the unbounded LLM sweep (replace it with a sweep by the S1 judge, W1 `brain_scan`); RRF k = 60 with equal weights; parallel, unconnected storage systems.

## 4. The work, in order

Each item states its design, its acceptance criteria and how it is measured. Keep the house style: small modules, SQL underneath, S0 → S1 → S2 → owner, everything logged to the ledger, a test per behaviour, and a review per part.

### W1. An agent tool surface (`engram/src/engram/tools.py` + `mcp.py`)

The core of round 3. The same functions are exposed three ways: an MCP server over stdio (`engram mcp`, for Claude Code, Claude Desktop and any MCP client), the existing HTTP server, and native tool schemas for the local agent loop (`agent.py`).

| Tool | Does | Returns (compact JSON) |
|---|---|---|
| `brain_search(query, person?, since?, until?, direction?, kinds?, k=8, cursor?)` | hybrid search, collapsed to one hit per **thread**, with the best chunk | `[{id, thread, date, from, to, subject, snippet ≤ 300 chars, why, score}]` plus `cursor` |
| `brain_read(ids, budget_tokens=1500)` | full items or threads, truncated to fit the budget, quoted history last | `[{id, text, truncated}]` |
| `brain_beliefs(kind?, person?, due_before?, due_after?, status?, as_of?)` | current (or as-of) beliefs: structured, no LLM | `[{id, kind, actor, other, statement, due, status, quote, source_id, author, trust}]` |
| `brain_people(name_or_address)` | entity lookup (see W4) | `[{person, addresses, first, last, n_items}]` |
| `brain_sql(sql)` | read-only, as `engram_reader`, 3 s, 200 rows, with a schema card in the tool description | `{columns, rows, truncated}` |
| `brain_scan(question, filter, max_items=200)` | **a sweep by the S1 judge**: the 4-bit judge asks `relevant` of every filtered item, and only those it finds relevant are returned | `[{id, p_relevant, snippet}]` |
| `brain_check(claim, ids)` | the `supported` judge on the agent's own claim: System 1 as a fact-checker the agent can call | `{supported, p, settled, by}` |
| `brain_ask(question)` | the existing pipeline, for agents that want one call | answer, citations and verdict |

Rules:

- Every result carries record ids. Citations are ids, never text parsed back out.
- Results fit a token budget, and cursors page beyond it.
- Tool descriptions state cost and latency, for example "brain_scan: ~0.2 s per item".
- Every call is recorded in the ledger (a new `tool_calls` table, or a `judgements`-like row). The same tool calls are the trace data for W6.

**Acceptance:** an MCP client can use all tools; the server tests (hermetic) cover every tool; `brain_sql` inherits the attack tests.

### W2. A query router (S0 → S1), OpenJarvis's archetypes done in code

Classify an agent's request into an archetype, then return a **plan** as a list of tool calls with parameters: lookup-by-person/time, keyword, semantic, count/aggregate (SQL), commitments/decisions (beliefs), thread-reconstruction, or multi-hop.

- **S0:** date and name parsing (dateparser + W4 people) extract filters.
- **S1:** a `choice` question classifies the archetype.
- Serve the plan as `brain_plan(question)` and use it inside `brain_ask`.

**Labels:** about 300 EnronQA questions labelled by archetype (auto-derived where possible: questions mentioning a date become time lookups, a person becomes a people filter). Measure with the agent eval (W6).

### W3. Thread context and collapse (from OpenJarvis)

`brain_search` groups by `thread_key`. `brain_read` of a hit includes up to N sibling items of the thread, ordered in time, within the token budget.

**Measure:** thread-level recall@k (is the gold email's thread in the top k?) against item-level recall.

### W4. People as entities

The known memory limit is "Vince" versus "Vince Kaminski" versus an address. Build a `people` table (person id, display name, aliases, addresses) from the `contacts` view, owner addresses, and belief actors and others. Use S0 rules first (name ↔ address local part, signature lines), then S1 `same_person` for the uncertain pairs, and a Review note in Obsidian for the owner.

Then: person filters accept names; belief chains supersede across aliases; the 3D graph links beliefs to people correctly.

**Measure:** precision and recall of merges on a small hand-labelled set.

### W5. Trust tiers and injection screening for recalled memory (from OpenJarvis)

- Add `trust` to beliefs: `owner` (written or confirmed in Obsidian) > `engram` (extracted from the owner's own sent mail) > `external` (extracted from received mail).
- Screen extracted quotes and statements with rules plus an S1 `injection` question before they are stored; flagged ones become `quarantined`.
- Tools return `trust`, and `brain_ask` refuses quarantined beliefs as evidence.

**Test:** a planted instruction in an email never reaches a tool result unflagged.

### W6. An agent-level evaluation, the measure of this round

Run a local agent (the 14B with native tools, the `agent.py` loop) on the 100 held-out EnronQA questions from LR §10.6 under three regimes:

- **(a)** context injection (top-k prepended, OpenJarvis's `inject_context`);
- **(b)** `brain_ask` alone;
- **(c)** the W1 tool surface with the W2 plans.

Record accuracy (grade, then audit disagreements by hand as in §10.6), tool calls, **context tokens**, wall time and citation validity (does every claimed fact have a supporting id, per `brain_check`?).

**Targets for (c):** accuracy at least (b)'s; median context tokens at most half of (a)'s; p50 latency ≤ 5 s with drafting on. Add 30 multi-hop and aggregate questions written from the data, since EnronQA is single-email. Store every trace; they are the training data for a learned router later, the OpenJarvis `LearnedRouterPolicy` idea applied to retrieval plans.

### W7. Cheaper upkeep (from OpenJarvis, small)

- A `sync_state` per source (cursor, watermark, advanced only on success).
- An `embedding_model` column on chunks, so a new embedder backfills only its own vectors.
- A per-chunk content hash, to skip re-embedding in `rederive`.

**Acceptance:** re-running an unchanged sync costs no model calls.

### W8. Caches (small, measurable)

- An in-process LRU for query embeddings.
- A result cache keyed on (tool, arguments, corpus version), where the corpus version is the maximum `items.id` plus the maximum `beliefs.id`.
- A per-session "already shown" set, so an agent is not re-sent items it has seen (fewer tokens).

**Measure:** the hit rate and tokens saved in the W6 traces.

**Order:** W1 → W6 (baseline) → W3 → W2 → W4 → W5 → W7 → W8, re-running W6 after each. Stop and ask the owner if two options are genuinely close (their standing instruction: explain each choice).

## 5. Practicalities

- **Run:** `docker compose up -d` (Docker Desktop must be running; it has quit on its own before), then `uv sync --extra finetune`, then `uv run engram serve` (port 8770; the command now says when the port is busy). `.env`: `ENGRAM_JUDGE_MODEL=mlx:data/models/judge-v1-q4`. Ollama: `bge-m3`, `qwen3:1.7b`, `qwen3:14b`, `qwen3:0.6b`. Everything runs offline (`HF_HUB_OFFLINE=1` is set by the CLI).
- **MLX constraint:** a model loaded on one thread can't be used from another. The server funnels all MLX work through one worker thread (`serve.py`); the MCP server must do the same.
- **Memory budget:** the 14B (~10 GB) + the judge (1 GB) + bge-m3 fit in 24 GB. LoRA training (18 GB peak) cannot run alongside the 14B.
- **Don't** run `pgrep -f "<text>"` waiters that match a sibling job's command line; it deadlocked the queue once. Wait on PIDs.
- **Data and licences:** Enron (public), EnronQA (CC BY 4.0), WorkBench (MIT, cloned into `data/raw/workbench`), QMSum; 3d-force-graph (MIT, vendored with a NOTICE); OpenJarvis is Apache-2.0, so ideas and patterns may be adopted freely. Copying code requires keeping its licence notice.
- **Docs to keep current:** README (commands and results), `brain-design.md` §5 (as built), `lit-review.md` (measured sections §4.4, §10.5–10.8, §11.6), and a `round3` results section in this file.

## 6. Round 3 results (built; measured 2026-09-27)

**Adopted from OpenJarvis, rebuilt on engram's engines**

| OpenJarvis idea | In engram | Where |
|---|---|---|
| Small typed tools an agent calls, results with ids | `brain_search` (one hit per conversation, person/date/direction filters, `next_cursor`), `brain_read` (token budget, `thread=true` adds the conversation, `omitted_ids` when over budget), `brain_beliefs`, `brain_people`, `brain_sql`, `brain_scan`, `brain_check`, `brain_ask`, `answer` | `tools.py` |
| MCP server | stdio JSON-RPC, hand-written (initialize, ping, tools/list, tools/call; tool errors come back as `isError`, not crashes) — `claude mcp add engram -- uv --directory engram run engram mcp` | `mcp.py`, `engram mcp` |
| Thread context around a hit (`thread_context_cap` 20) | search collapses to the best hit per `thread_key` and reports `thread_items`; read pulls up to 20 siblings, oldest first | `tools.py` |
| Knowledge graph entities | `people`: addresses and belief names merged (all owner addresses → one person with aliases *me/owner*; `sgibner@` joins Stinson Gibner; a bare first name only when unique) — 1,948 people on the example owner | `people.py`, `010_agents.sql` |
| Trust tiers + injection scanner on recalled facts | `beliefs.trust` ∈ owner / engram / external / quarantined; the extraction screens for instruction-like text; quarantined beliefs are never served to a model | `memory.py`, `vault.py` |
| Embedder recorded per vector | `chunks.embedding_model`; `index` re-embeds only what another embedder made | `index.py` |
| Deep-research agent: archetype recipes, max turns, forced final answer | `engram agent brain`: the 14B, ≤ 8 turns, one recipe line per kind of question, reminded once to call `answer` if it replies in prose | `research.py`, `agent.py` |

**Deliberately not copied:** the regex SQL blocklist (engram runs agent SQL as a read-only role with a 3 s timeout
instead), LLM batch `scan_chunks` (the fine-tuned S1 judge reads each item at ~0.2 s instead), brute-force numpy
cosine (pgvector HNSW), RRF k = 60 with equal weights (engram's measured k = 5, meaning 0.5 stays), facts without
supersession (engram's beliefs are bitemporal), and the learned router (W2 below: not yet justified by data).

**Beyond OpenJarvis: citations that must be true.** `answer` accepts only ids a tool returned in this run (the model
invented ids [12345, 67890] before this), and when a judge is present the fine-tuned `supported` judge checks each
cited item; if none supports the answer it refuses once with a menu of what was seen. `answer` ends the run, so an
MCP session cannot cite a previous question's results; MCP clients pass `question` so the check runs for them too.

**W6: the test agent against `ask`** (`engram eval-agent --n 30`; the same 30 held-out EnronQA questions, same grader;
rows in `engram/data/results/agent-qa*.jsonl`)

| | correct | gold email cited | calls | tool tokens read (p50) | seconds (p50) |
|---|---|---|---|---|---|
| `ask` (one call) | **66.7%** | **60.0%** | 1 | — | **4.5** |
| agent, first build | 50.0% | 36.7% | 4.3 | 1,776 | 31.1 |
| agent + query-focused snippets, "read before saying it isn't there" | 60.0% | 43.3% | 3.5 | 1,638 | 20.6 |
| either one right | 80.0% | | | | |

What the traces showed and what changed it:
- The agent said "not mentioned" without opening the emails search had found (4 of 30); snippets were the first
  300 characters of a chunk, often not the passage that matched. Snippets now show the 300 characters where most of
  the query's words are; the recipe says to read the top ids before concluding absence (2 of 30 now).
- It sometimes wrote the answer call as text; the recipe now says to call the tool (0 of 30 now).
- The grader is strict ("Merrill Lynch-Houston" for "Merrill Lynch" was marked wrong), so both columns are
  somewhat understated; the comparison is on identical questions and grader.

**Reading of the result.** For single-fact questions, the one-call pipeline is still better, 5× faster and needs no
tool tokens: it retrieves with the question verbatim and lets the judge filter, where the agent rewrites the query and
reads snippets. The agent's value is on what `ask` can't do — commitments by person and date, counts, people,
following a thread — and the two are complementary (80% either-right). So the next step is W2 as planned: a router
that sends fact questions to `ask` (or makes `brain_ask` the agent's first call for them) and uses the tools for
structured and multi-step questions. It needs a question set with those kinds (EnronQA is almost all single-fact).

**Code review** (independent reviewer) found and we fixed: MCP state carried across questions (citations from an
earlier question accepted; the judge's check never ran for MCP clients), `read` exceeding its budget by 50% with
many thread items, LIKE wildcards in person names matching everyone, and unqualified first-name matching. Left as
is: search paging is capped by the ~100-chunk candidate pool; the support check makes one judge call per cited id.
Tests: 58 pass; ruff clean.

**Still to do from §4:** W2 (router, with a mixed question set), W7 (sync upkeep), W8 (caches).
