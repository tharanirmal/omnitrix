# Slice A — Agent memory architectures & memory benchmarks

*Literature notes for **Omnitrix** (MSRIT Hackathon, Track 1 "Sovereign AI"). Compiled 2026-09-25.*
*Scope: memory taxonomies; memory systems (pipelines + every internal decision point); memory benchmarks and the disputes around them; reported experience running memory systems on small local models. Other slices (routing/calibration, model zoo & runtimes, DB theory & cognitive science, security, product landscape) are deliberately not covered here.*

---

## 0. Reading guide

**Verification.** Every entry was checked on 2026-09-25 against a primary source: arXiv abstract/HTML, proceedings pages (ACL Anthology, PMLR, AAAI OJS, ICLR proceedings, ICML virtual site), ACM DL, the project's GitHub source code or official docs. Vendor blogs/pages are primary sources only for *what the vendor claims* and are tagged **[vendor]**. Single-author or non-peer-reviewed items are tagged **[preprint]** / **[practitioner]**. Anything I could not confirm is listed in §10 and not used as fact elsewhere.

**Legend for the decision tables (my assessment, grounded in evidence where cited):**

| Tag | Meaning |
|---|---|
| **CODE** | Is (or should be) a threshold, formula, rule or algorithm. No model call. |
| **S1** | A small fast model (1.7B–4B LLM) or an encoder (classifier / cross-encoder / embedding threshold) can own it. Output is a boolean, a pick-one, a pick-subset from a short list, or a bounded score. |
| **S1\*** | S1-feasible **only with guard-rails**: enumerated ids/enums, reasoning-first field order, all-required JSON schema, thinking disabled, validation + retry + dead-letter queue, confidence with escalation. |
| **S2** | Generative / deliberative. Keep on the 14B "thinking" model, preferably off the hot path ("sleep-time"). |

Output-type codes: **B** boolean · **C1** choose one · **CS** choose subset · **SC** score · **X** structured extraction into a schema · **G** free generation.

---

## 1. Taxonomies and surveys

### 1.1 CoALA — Cognitive Architectures for Language Agents
- **Citation:** Sumers, T. R., Yao, S., Narasimhan, K., Griffiths, T. L. (2023; v3 15 Mar 2024). *Cognitive Architectures for Language Agents.* TMLR (camera-ready). arXiv:2309.02427 — https://arxiv.org/abs/2309.02427
- **Mechanism:** A language agent = memory modules (short-term *working* memory; long-term *episodic* = experiences, *semantic* = facts, *procedural* = skills/code/weights) + an action space split into *internal* actions (retrieval, reasoning, **learning = writing to memory**) and *external* grounding actions + a decision cycle (planning: propose → evaluate → select; then execute).
- **Quantitative:** none (conceptual).
- **Relevance to Omnitrix:** Supplies vocabulary for Data→Knowledge→Memory→Reasoning→Action. Because every memory write is an *action chosen by the decision procedure*, every write is a decision point. The propose/evaluate/select split is a natural dual-process seam: S1 proposes and scores cheap candidates; S2 selects only when S1 is uncertain.

### 1.2 Zhang et al. — memory-mechanism survey (TOIS)
- **Citation:** Zhang, Z., Dai, Q., Bo, X., Ma, C., Li, R., Chen, X., Zhu, J., Dong, Z., Wen, J.-R. (2025). *A Survey on the Memory Mechanism of Large Language Model-based Agents.* ACM TOIS 43(6):155:1–155:47. DOI 10.1145/3748302 — https://dl.acm.org/doi/10.1145/3748302 (arXiv:2404.13501, v1 21 Apr 2024).
- **Mechanism:** Organizes the field around what agent memory is, why agents need it, and how to implement and evaluate it; reviews applications and limitations.
- **Quantitative:** none.
- **Relevance:** Early canonical reference; useful as the "related work" anchor in a pitch deck.

### 1.3 Wu et al. — From Human Memory to AI Memory
- **Citation:** Wu, Y., Liang, S., Zhang, C., Wang, Y., Zhang, Y., Guo, H., Tang, R., Liu, Y. (22 Apr 2025). *From Human Memory to AI Memory: A Survey on Memory Mechanisms in the Era of LLMs.* arXiv:2504.15965.
- **Mechanism:** Maps human memory categories onto LLM-system memory along three dimensions (object, form, time), giving eight quadrants.
- **Relevance:** Handy framing to separate the *user's* memory (the businessman's world) from the *system's* own memory (procedures, lessons).

### 1.4 Du et al. — Rethinking Memory (six atomic operations)
- **Citation:** Du, Y., Huang, W., Zheng, D., Wang, Z., Montella, S., Lapata, M., Wong, K.-F., Pan, J. Z. (1 May 2025; v3 24 Dec 2025). Originally *Rethinking Memory in AI: Taxonomy, Operations, Topics, and Future Directions*; v3 retitled *Rethinking Memory in LLM based Agents: Representations, Operations, and Emerging Topics.* arXiv:2505.00675.
- **Mechanism:** Two representations — *parametric* (weights) and *contextual* (external; structured or unstructured) — and six atomic operations: **consolidation, updating, indexing, forgetting, retrieval, condensation** (compression). Four research topics: long-term memory, long context, parametric modification, multi-source memory.
- **Relevance:** Use the six operations as a checklist for the Librarian/Historian: each hides S1-sized decisions (consolidation → "is this new?"; updating → "does this supersede X?"; forgetting → "still needed?"; retrieval → "relevant?").

### 1.5 Hu et al. — Memory in the Age of AI Agents
- **Citation:** Hu, Y., Liu, S., Yue, Y., Zhang, G., Liu, B., et al. (47 authors) (15 Dec 2025; v2 13 Jan 2026). *Memory in the Age of AI Agents.* arXiv:2512.13564. Paper list: https://github.com/Shichun-Liu/Agent-Memory-Paper-List
- **Mechanism:** *Forms* (token-level, parametric, latent) × *functions* (factual, experiential, working) × *dynamics* (formation, evolution, retrieval). Distinguishes agent memory from plain RAG and from LLM-internal memory; catalogs benchmarks and open-source frameworks; frontiers: memory automation, RL, multimodal, multi-agent, trustworthiness.
- **Relevance:** "Experiential" memory (lessons from outcomes) matches Omnitrix's Auditor / Promise Keeper track records; the survey positions RL-learned memory policies as the trend line (see Memory-R1, Mem-α).

### 1.6 P. Du — Memory for Autonomous LLM Agents
- **Citation:** Du, P. (8 Mar 2026). *Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers.* arXiv:2603.07670. **[preprint, single author]**
- **Mechanism:** Memory as a **write–manage–read loop** coupled to perception and action; axes = temporal scope, representational substrate, **control policy**; five families: context-resident compression, retrieval-augmented stores, reflective self-improvement, hierarchical virtual context, policy-learned management. Engineering concerns called out: write-path filtering, contradiction handling, latency, privacy.
- **Relevance:** "Control policy" as a first-class axis *is* the CODE/S1/S2 question — who decides each memory operation.

### 1.7 Jiang et al. — Anatomy of Agentic Memory (evaluation audit)
- **Citation:** Jiang, D., Li, Y., Wei, S., Yang, J., Kishore, A., Zhao, A., Kang, D., Hu, X., Chen, F., Li, Q., Li, B. (22 Feb 2026; v2 20 May 2026). *Anatomy of Agentic Memory: Taxonomy and Empirical Analysis of Evaluation and System Limitations.* arXiv:2602.19320.
- **Mechanism:** Four memory structures (lightweight semantic; entity-centric/personalized; episodic/reflective; structured/hierarchical) plus an empirical audit of saturation, metric validity (F1 vs LLM-judge), backbone sensitivity and runtime overhead.
- **Quantitative:**
  - Saturation risk: LoCoMo (~20k tokens) and LongMemEval-S (~103k) "moderate"; MemBench (~100k) "high"; only LongMemEval-M (>1M) "low".
  - **Backbone sensitivity (Table 4, "format error" = recoverable structured-output deviations during memory operations):** SimpleMem 1.20% on GPT-4o-mini vs **4.82% on Qwen-2.5-3B**; Nemori 17.91% vs **30.38%**; Nemori's answer score falls 0.781 → 0.447 on the 3B backbone. The authors call the result a "silent failure": the agent chats fluently while its long-term memory is corrupted by failed writes.
  - **"Agency tax" (Table 5):** offline construction 0.60–15.00 h and 1.3M–7.0M tokens across systems (Nemori 7,044k tokens; A-Mem 15.0 h; MAGMA 7.28 h / 2,725k); MemoryOS user-facing latency 32.4 s vs 1.73 s for full-context. (Dataset for Table 5 is not stated in the table.)
- **Relevance:** The single most direct warning for a small-model memory pipeline: write failures are silent and grow with pipeline complexity and with smaller backbones. Omnitrix must validate every S1 output and track *write-failure rate* as a metric.

### 1.8 Zhou et al. — Are We Ready For An Agent-Native Memory System?
- **Citation:** Zhou, W., Zhou, X., Han, S., Xu, H., Li, G., Li, Z., Xiong, F., Wu, F. (23 Jun 2026). arXiv:2606.24775. (Shares authors with the MemOS team.)
- **Mechanism:** Data-management decomposition — representation/storage, extraction, retrieval/routing, maintenance — and a benchmark of 12+ systems (MemoChat, Mem0, Mem0g, MEM1, MemAgent, MemTree, Zep, Cognee, LightMem, SimpleMem, MemOS, MemoryOS, A-MEM, Letta) vs long-context and embedding-RAG baselines over 5 workloads / 11 datasets.
- **Quantitative:** No architecture dominates; effectiveness depends on aligning structure with the workload's bottleneck. Average memory-operation latency per query on one workload: LightMem 3.67 s, MemTree 15.9 s, MemoryOS 28.6 s, Cognee 116.5 s, Zep 155.1 s; on LongBench, Mem0/MemoChat/MemoryOS/A-MEM reach 374–552 s. The slower systems also bought higher normalized utility on that workload (MemoryOS 82.0; Cognee and Zep >84 vs LightMem 48.3 and MemTree 63.5), so this is a cost–quality frontier, not a free win. Finding 5: **localized maintenance** gives the best cost–utility; whole-memory reorganization becomes the dominant cost.
- **Relevance:** Favors per-entity / per-fact maintenance with cheap S1 decisions over global rebuilds (e.g., GraphRAG community recomputation) on a laptop.

### 1.9 (Pointer only) Lin et al. — memory-security survey
- **Citation:** Lin, Z., Hao, X., Fu, R., Cui, S., Chen, K., Li, C., Li, Z., Xiong, F. arXiv:2604.16548 (v1 17 Apr 2026 titled *A Survey on the Security of Long-Term Memory in LLM Agents: Toward Mnemonic Sovereignty*; v3 22 Sep 2026 retitled *A Survey on Long-Term Memory Security in LLM Agents: Attacks, Defenses, and Governance Across the Memory Lifecycle*).
- **Relevance:** Belongs to the security slice; flagged because the v1 title literally names "sovereignty". Lifecycle: write, store, retrieve, execute, share/propagate, forget/rollback; recommends storage-time provenance, versioning and policy-aware retention.

**Synthesis of §1.** Surveys converge on *memory = a substrate plus policies over a write → manage → read loop*. Each policy step is a decision. The 2025–26 trend runs from hand-set heuristics → prompted LLM judgements → **learned (RL) policies**, while 2026 evaluation papers show the prompted-LLM middle stage is fragile on small backbones.

---

## 2. Systems — pipelines and every internal decision point

(Per-system notes; the consolidated decision table is §6.)

### 2.1 MemGPT → Letta (memory tiers, self-editing memory, sleep-time compute, MemFS)
- **Citations:**
  - Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., Gonzalez, J. E. (12 Oct 2023; v2 12 Feb 2024). *MemGPT: Towards LLMs as Operating Systems.* arXiv:2310.08560.
  - Lin, K., Snell, C., Wang, Y., Packer, C., Wooders, S., Stoica, I., Gonzalez, J. E. (17 Apr 2025). *Sleep-time Compute: Beyond Inference Scaling at Test-time.* arXiv:2504.13171.
  - Letta docs (accessed 2026-09-25): https://docs.letta.com/guides/agents/architectures/sleeptime · https://docs.letta.com/guides/agents/memory · https://docs.letta.com/guides/server/providers/ollama/
- **Pipeline:** Main context = system instructions + an editable working context ("core memory" / memory blocks) + a FIFO message queue. External context = *recall storage* (full, searchable message history) + *archival storage* (vector store). The LLM moves data between tiers through function calls (edit working context; insert/search archival; paged conversation search). Setting `request_heartbeat=true` requests another LLM step, which is how multi-step retrieval happens. A queue manager raises a "memory pressure" warning at **70%** of the context window; at **100%** it flushes about **50%** of the window into a recursive summary stored at the head of the queue.
- **Sleep-time compute:** let the model reason over the context *before* queries arrive. About **5× less test-time compute** for equal accuracy (Stateful GSM-Symbolic, Stateful AIME); up to **+13% / +18%** accuracy when scaling sleep-time compute; **2.5× lower average cost per query** when amortized across related queries; gains correlate with query predictability.
- **Letta in 2026:** memory is exposed as **MemFS, a git-backed memory filesystem** that the agent inspects and edits. Background "dreaming" subagents review recent conversations and consolidate lessons. They run after N completed steps or when the context is compacted, with an optional "agent reviews before applying" second pass. The docs recommend starting with a frontier model because weaker models "can cause the agent to behave in unexpected ways".
- **Quantitative (DMR, MemGPT Table 2):** GPT-3.5 Turbo 38.7% → 66.9% with MemGPT; GPT-4 32.1% → 92.5%; GPT-4 Turbo 35.3% → 93.4% (ROUGE-L 0.359 → 0.827).
- **Decision points:** pressure/flush (CODE thresholds) · write to core memory? + what text (LLM tool call: B + G) · search memory? which tool? (C1) · continue chaining? (B) · eviction summary (G) · when to dream (CODE) · what to consolidate and where to file it (G, optionally reviewed).
- **Relevance to Omnitrix:** The Obsidian vault is Omnitrix's equivalent of MemFS: human-readable, versionable files. Letta's split is the dual-process pattern already in production: a hot-path agent plus a background consolidator with a review gate. Put S1 on the hot path (should-save? which tool? continue?) and run S2 (Qwen3-14B thinking) as the sleep-time consolidator. Keep tool menus tiny for S1, and cap heartbeat loops in code.

### 2.2 Generative Agents (memory stream, importance, reflection)
- **Citation:** Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., Bernstein, M. S. (2023). *Generative Agents: Interactive Simulacra of Human Behavior.* UIST 2023. arXiv:2304.03442.
- **Pipeline:** Every observation goes into a timestamped natural-language memory stream. Retrieval score = recency + importance + relevance, each min–max normalized to [0,1], all weights = 1. **Recency** decays exponentially (0.995 per game-hour since last retrieval). **Importance** is an LLM rating from 1 to 10 at write time (anchors: routine chores = 1; a break-up or college acceptance = 10). **Relevance** is embedding cosine. **Reflection** fires when the summed importance of recent events exceeds **150** (about 2–3 times a day). It takes the 100 most recent records, has the LLM pose 3 salient questions, retrieves evidence, and writes 5 insights that cite it. The LLM is also asked whether to react to each observation, and it plans and re-plans.
- **Quantitative:** Simulating 25 agents for 2 game-days cost "thousands of dollars" in tokens and took multiple days.
- **Decision points:** importance (SC — the archetypal S1 task) · retrieval ranking (CODE) · reflection trigger (CODE threshold over S1 scores) · reflection content (G, S2) · react? (B) · planning (G, S2).
- **Relevance:** Omnitrix's "is this email noise?" is importance scoring. The paper's cost shows why scoring every item with a big model does not scale. The sum-of-importance trigger is a ready-made escalation rule: S1 scores accumulate until S2 reflection is worth running.

### 2.3 MemoryBank (forgetting curve)
- **Citation:** Zhong, W., Guo, L., Gao, Q., Ye, H., Wang, Y. (2024). *MemoryBank: Enhancing Large Language Models with Long-Term Memory.* AAAI 2024, 38(17):19724–19731 — https://ojs.aaai.org/index.php/AAAI/article/view/29946 (arXiv:2305.10250).
- **Pipeline:** Stores timestamped conversations, daily→global event summaries, and daily→global personality summaries; retrieval via dense retrieval (DPR) + FAISS. Forgetting follows an Ebbinghaus curve R = e^(−t/S): strength S starts at 1, and each recall adds 1 to S and resets t.
- **Quantitative:** 194 probing questions over a 10-day simulated history for 15 virtual users; best retrieval accuracy 0.763 (ChatGPT backbone, English).
- **Decision points:** retain/forget (CODE formula) · strengthen on recall (CODE) · summaries (G, batch).
- **Relevance:** Decay and forgetting belong in code. Mem0's 2026 algorithm likewise applies decay only at ranking time (§2.4).

### 2.4 Mem0 and Mem0g (2025 paper) → Mem0's 2026 "token-efficient" ADD-only algorithm
- **Citations:**
  - Chhikara, P., Khant, D., Aryan, S., Singh, T., Yadav, D. (28 Apr 2025). *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory.* arXiv:2504.19413.
  - **[vendor]** Mem0 blog, *Introducing The Token-Efficient Memory Algorithm* (16 Apr 2026, updated 22 Sep 2026) — https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm ; *The Token-Efficient Memory Algorithm Now Has Temporal Reasoning* (14 May 2026, updated 31 Jul 2026) — https://mem0.ai/blog/the-token-efficient-memory-algorithm-now-has-temporal-reasoning
  - Source code inspected 2026-09-25: https://github.com/mem0ai/mem0 (`mem0/configs/prompts.py`, `mem0/memory/main.py`, `mem0/memory/utils.py`).
- **2025 pipeline (paper):**
  - *Extraction:* the prompt holds a running conversation summary, the last m = 10 messages and the new exchange; the LLM outputs candidate facts.
  - *Update:* for each fact, retrieve the s = 10 most similar memories by embedding. The LLM then picks **ADD / UPDATE / DELETE / NOOP** through a tool call.
  - *Mem0g:* adds LLM entity extraction and typing, LLM relationship triplets, node reuse above an embedding-similarity threshold, and an LLM "update resolver". The resolver marks conflicting relations *invalid* rather than deleting them, which preserves temporal reasoning. Retrieval combines an entity-centric graph walk with semantic search over triplets.
  - Stack: GPT-4o-mini, text-embedding-3-small, Neo4j.
- **2025 results (LoCoMo, LLM-judge "J"):**
  - Overall: Mem0 66.88; Mem0g 68.44; Zep 65.99; LangMem 58.10; OpenAI memory 52.90; best RAG 60.97; full-context 72.90.
  - Temporal category: Mem0g 58.13; Mem0 55.51; LangMem 23.43; OpenAI 21.71.
  - p95 total latency: Mem0 1.44 s; Mem0g 2.59 s; Zep 2.93 s; full-context 17.12 s; LangMem 60.40 s.
  - Memory footprint per conversation: Mem0 ≈7k tokens; Mem0g ≈14k; Zep >600k; the raw conversation is ≈26k.
  - Mem0 also reports that Zep answered poorly right after ingestion and much better hours later, which it attributes to asynchronous graph building.
- **2026 change (verified in code):**
  - The default `add()` now makes **one LLM call** with `ADDITIVE_EXTRACTION_PROMPT` (single pass, ADD-only).
  - Each extracted memory carries `attributed_to` (user or assistant) and `linked_memory_ids` pointing to related existing memories. Relative times are resolved against the observation date.
  - Prompt context is the top-10 similar existing memories plus the last 10 messages. Exact duplicates are dropped by MD5 hash. `infer=False` stores raw text with no LLM call.
  - The legacy ADD/UPDATE/DELETE/NONE prompt still exists in `prompts.py`, but `main.py` no longer uses it. Graph memory is no longer part of `main.py`.
- **Mem0's rationale for the change:**
  - The old second "reconcile" pass lost context through overwrites and deletes. ADD-only keeps the full history of state changes and "cuts extraction latency roughly in half".
  - Retrieval fuses semantic, keyword (with verb normalization) and entity matches.
  - The temporal update adds write-time metadata: event time; ongoing vs completed; time precision; and memory kind (current fact, historical fact, plan, preference, relationship, timeless).
  - It also adds **"state keys"**: when a new state supersedes an old one, the old state is closed with an `event_end`.
  - Decay is applied at search time only: recently used memories get up to ×1.5, idle ones are dampened toward ×0.3.
- **2026 claims [vendor]:** LoCoMo 92.5, LongMemEval 94.4, BEAM-1M 64.1 and BEAM-10M 48.6, using under 7k tokens per retrieval. Mem0 cites ±1 point of judge inconsistency. The page does not name the answer or judge models, and the results come from the managed platform; open-source users are told to expect gains that are "directionally similar".
- **Decision points:**

  | Decision | Type | Handled by |
  |---|---|---|
  | Store anything? | implicit B (empty extraction) | LLM |
  | Which facts to extract | X | LLM |
  | Which existing memories to link | CS over top-10 | LLM |
  | Exact duplicate? | — | CODE (hash) |
  | Temporal-kind fields | C1 inside X | LLM |
  | Supersession | link proposed by LLM | CODE (state closure) |
  | Decay | — | CODE |
  | ADD/UPDATE/DELETE/NOOP (legacy) | C1 | LLM |

- **Relevance to Omnitrix:** This is the most important design signal in this slice. The leading vendor **removed the write-time ADD/UPDATE/DELETE judgement**. It now uses append-only history plus temporal metadata and resolves conflicts at read time. For Omnitrix, S1 therefore does not need to be a perfect "diff engine":
  - S1 fills a fixed schema (classify and extract) and proposes links.
  - Supersession becomes a deterministic rule over typed fields: same subject and attribute, later valid-time.
  - S2 or a human reviews business-critical supersessions, such as a changed decision.

### 2.5 Zep / Graphiti (bi-temporal knowledge graph)
- **Citations:**
  - Rasmussen, P., Paliychuk, P., Beauvais, T., Ryan, J., Chalef, D. (20 Jan 2025). *Zep: A Temporal Knowledge Graph Architecture for Agent Memory.* arXiv:2501.13956.
  - Graphiti source, `main` branch inspected 2026-09-25 — https://github.com/getzep/graphiti. Files: `graphiti_core/prompts/{extract_nodes,extract_edges,dedupe_nodes,dedupe_edges,extract_nodes_and_edges}.py`; `graphiti_core/utils/maintenance/{node_operations,edge_operations,dedup_helpers}.py`; `graphiti_core/llm_client/config.py`.
  - Docs: https://help.getzep.com/graphiti/configuration/llm-configuration ; GitHub issues #868 (27 Aug 2025), #1135 (7 Jan 2026), #1666 (18 Jul 2026), #1909 and #1911 (23 Sep 2026).
- **Graph structure (paper):**
  - Three subgraphs: *episodes* (raw messages/text/JSON, non-lossy), *semantic entities + fact edges*, and *communities*.
  - Edges are bi-temporal: event-time validity (t_valid, t_invalid) plus system time (created, expired).
- **Per-episode ingestion (paper):**
  1. Entity extraction, using the last n = 4 messages as context; the speaker is always extracted.
  2. A reflexion-style re-check for missed entities.
  3. Entity resolution: candidates by cosine over 1024-d embeddings plus full-text search, then the LLM judges whether each is a duplicate and merges name and summary.
  4. Fact extraction between the resolved entities.
  5. Edge dedup, restricted to edges between the same entity pair.
  6. Temporal extraction: absolute and relative dates, resolved against the episode timestamp.
  7. Edge invalidation: the LLM compares a new edge with semantically related edges; contradicted ones get t_invalid.
  8. Community detection by label propagation with incremental extension (periodic full refreshes needed), and LLM community summaries.
- **Retrieval (paper):** cosine, BM25 and breadth-first graph search, reranked by RRF, MMR, episode-mention frequency, node distance, or a cross-encoder.
- **Current code (Sept 2026): the decision cascade has become more deterministic**
  - **Entity resolution:**
    1. Candidates by embedding similarity (`NODE_DEDUP_COSINE_MIN_SCORE = 0.6`, at most 15).
    2. Exact normalized-name match.
    3. **Entropy gate:** names shorter than 6 characters, with fewer than 2 tokens, or with entropy below 1.5 skip fuzzy matching.
    4. **MinHash-LSH** over 3-gram shingles (32 permutations, band size 4), accepting Jaccard ≥ **0.9**.
    5. Only still-unresolved entities go to **one batched LLM call**, which returns per entity a duplicate candidate id or **−1** (`NodeResolutions`).
  - **Edges:**
    - One extraction call per episode batch; facts carry `relation_type`, fact text, `valid_at` and `invalid_at`.
    - Exact dedup on (source, target, normalized fact), with a verbatim fast path.
    - Then, per new edge, **one small-model call** (`resolve_edge`) returns two index lists: `duplicate_facts` and `contradicted_facts`.
    - **Which edge expires is decided by deterministic interval logic** on `valid_at`/`invalid_at`.
    - Timestamps are re-asked (small model) only when extraction left both dates empty.
  - **Model tiers:**
    - `LLMConfig` has `model` and `small_model`.
    - **`ModelSize.small` handles edge resolution (duplicates + contradictions), edge timestamps, edge/entity attributes and entity summaries.**
    - Extraction and the node-dedup fallback use the main model.
    - The reflexion step no longer appears in the node path.
  - **LLM calls per episode** (my count from the code; default setup, no custom entity/edge types):
    - Roughly 1 node extraction + 0–1 node-dedup + ⌈N/30⌉ summary calls, then 1 edge extraction + ≤M `resolve_edge` + ≤M timestamp calls.
    - That is about **3–4 + M to 3–4 + 2M calls** for an episode yielding N entities and M facts, plus embeddings.
    - With custom types, add N + M attribute calls.
- **Quantitative (paper):**
  - **DMR:** 94.8% (gpt-4-turbo) vs MemGPT 93.4% vs full conversation 94.4%. With gpt-4o-mini: 98.2% vs full conversation 98.0%.
  - **LongMemEval-S overall:** gpt-4o-mini 55.4% → 63.8%; gpt-4o 60.2% → 71.2% (+18.5%).
  - Context fell from ~115k to ~1.6k tokens, and latency by ~90% (e.g., 31.3 s → 3.2 s with gpt-4o-mini).
  - **Per question type (gpt-4o), baseline → Zep:**

    | Question type | Baseline | Zep |
    |---|---|---|
    | Preference | 20.0 | 56.7 |
    | Temporal | 45.1 | 62.4 |
    | Multi-session | 44.3 | 57.9 |
    | Knowledge-update | 78.2 | 83.3 |
    | Single-session-user | 81.4 | 92.9 |
    | **Single-session-assistant** | 94.6 | **80.4 (−17.7%)** |

  - With gpt-4o-mini, knowledge-update slipped slightly (76.9 → 74.4).
- **2026 claims [vendor]:** LoCoMo 94.7% (155 ms retrieval, 5,760 tokens) and LongMemEval 90.2% (162 ms, 4,408 tokens) — https://www.getzep.com/product/agent-memory/ (answer/judge models not stated there).
- **Relevance to Omnitrix:** Graphiti is the closest open blueprint for "deterministic checks before model judgement":
  1. Copy its entity-resolution cascade: exact match → entropy gate → MinHash → S1 pick-one, where −1 means "new entity".
  2. Copy its split between an S1 *judgement* (which facts are duplicated or contradicted) and a CODE *resolution* (which one expires, decided by time).
  3. Note that its maintainers already send the discrete decisions to a small model — but §5 (issue #1666) shows why that needs a reasoning-first schema.

### 2.6 A-MEM (Zettelkasten-style agentic memory)
- **Citation:** Xu, W., Liang, Z., Mei, K., Gao, H., Tan, J., Zhang, Y. (2025). *A-MEM: Agentic Memory for LLM Agents.* NeurIPS 2025. arXiv:2502.12110 (v1 17 Feb 2025; v11 8 Oct 2025).
- **Pipeline:**
  - *Note construction:* each new memory becomes a note — content + timestamp + LLM-generated keywords, tags and a context description — embedded together.
  - *Link generation:* take the top-k nearest notes by cosine (k ≈ 10–20 for Qwen/Llama backbones, 40–50 for GPT-4o-mini); the LLM then decides which to link.
  - *Memory evolution:* the LLM may rewrite the neighbours' context, keywords and tags in light of the new note.
  - *Retrieval:* top-k by cosine, plus the notes linked to them.
- **Quantitative:**
  - Cost: ≈1,200 tokens per memory operation (85–93% fewer than the LoCoMo/MemGPT baselines at ≈16,900); under $0.0003 per operation on commercial APIs.
  - Speed: 5.4 s per operation with GPT-4o-mini vs **1.1 s with a local Llama 3.2 1B**.
  - Small backbones (LoCoMo multi-hop F1): large *relative* gains but low *absolute* scores.

    | Backbone | A-MEM | MemGPT | LoCoMo baseline |
    |---|---|---|---|
    | Qwen2.5-3B | 12.57 | 5.07 | 4.61 |
    | Llama 3.2 1B | 19.06 | 9.19 | 11.25 |

  - Retrieval stays in microseconds up to 1M notes (3.70 μs).
- **Decision points:** note attributes (X) · link? (CS over k candidates) · evolve a neighbour? (B) + rewrite it (G).
- **Relevance:** 1B-class local models can run the *attribute* and *link* steps quickly. The *evolution* rewrite is the risky part, because old notes can drift silently. In Omnitrix, S1 may *propose* a link or a note edit, but rewrites of existing vault notes should be S2- or human-approved and git-versioned.

### 2.7 HippoRAG and HippoRAG 2
- **Citations:**
  - Gutiérrez, B. J., Shu, Y., Gu, Y., Yasunaga, M., Su, Y. (2024). *HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models.* NeurIPS 2024. arXiv:2405.14831.
  - Gutiérrez, B. J., Shu, Y., Qi, W., Zhou, S., Su, Y. (2025). *From RAG to Memory: Non-Parametric Continual Learning for Large Language Models* ("HippoRAG 2"). ICML 2025. arXiv:2502.14802.
- **Pipeline (v1):**
  - *Offline:* an LLM runs NER and then OpenIE triple extraction per passage (GPT-3.5-turbo-1106). **Synonymy edges** are added between phrase nodes whose encoder cosine exceeds **τ = 0.8**. Node specificity = 1/(number of passages containing the node).
  - *Online:* the LLM extracts query entities, which are linked to KG nodes by encoder similarity. Personalized PageRank (damping 0.5) spreads activation, and passages are scored by their nodes' PPR mass.
- **Pipeline (v2):**
  - Adds passage nodes with "contains" edges (dense + sparse coding).
  - Matches the whole query to **triples** (top-5).
  - A **"recognition memory" LLM filter** keeps the relevant subset of those triples; if none survive, it falls back to dense passage retrieval.
  - Filtered phrase nodes plus all passage nodes (reset weight 0.05) seed PPR.
  - OpenIE is done by Llama-3.3-70B-Instruct.
- **Quantitative:**
  - *v1:* up to +20% on multi-hop QA; single-step retrieval is 10–30× cheaper and 6–13× faster than iterative IRCoT.
  - *v2:* average F1 59.8 vs 57.0 for NV-Embed-v2; R@5 78.2 vs 73.4.
  - *v2 filter ablation:* removing the filter costs little (MuSiQue R@5 74.7 → 73.0; multi-hop average 87.1 → 86.4).
  - **Indexing cost (Table 12)** — MuSiQue, 11,656 passages, Llama-3.3-70B:

    | Method | Input tokens | Output tokens | Per passage (in + out) | Indexing time |
    |---|---|---|---|---|
    | HippoRAG 2 | 9.2M | 3.0M | ≈790 + 257 | 99.5 min |
    | RAPTOR | 1.7M | 0.2M | ≈146 + 17 | 100.5 min |
    | LightRAG | 68.5M | 18.3M | ≈5.9k + 1.6k | — |
    | GraphRAG | 115.5M | 36.1M | ≈9.9k + 3.1k | 277 min |

- **Decision points:** triple extraction (X, heavy) · synonym edge (CODE threshold) · query NER (X, small) · triple relevance filter (CS, low-stakes thanks to the fallback) · PPR (CODE).
- **Relevance:** The recognition filter is a clean template for Omnitrix's "is this retrieved passage relevant?" S1 check: pick a subset from ≤5 short items, with a safe fallback. The indexing table is the best apples-to-apples ingestion-cost comparison found: graph-summary systems (GraphRAG, LightRAG) cost **7–13× more LLM tokens** than triple-extraction memory.

### 2.8 GraphRAG
- **Citation:** Edge, D., Trinh, H., Cheng, N., Bradley, J., Chao, A., Mody, A., Truitt, S., Metropolitansky, D., Ness, R. O., Larson, J. (2024; v2 19 Feb 2025). *From Local to Global: A GraphRAG Approach to Query-Focused Summarization.* arXiv:2404.16130.
- **Pipeline:**
  - *Indexing:*
    1. 600-token chunks (100 overlap).
    2. LLM extraction of entities, relationships and claims.
    3. **"Gleaning":** the LLM is asked whether entities were missed, with a **logit bias of 100 forcing a yes/no token**; on "yes" it continues extracting, up to a maximum number of rounds.
    4. Element summaries, hierarchical Leiden communities, and LLM community reports.
  - *Global queries:* map over shuffled chunks of community summaries. Each partial answer gets an LLM **helpfulness score from 0 to 100**, and score-0 answers are dropped. The reduce step adds answers in descending score order until the context is full.
- **Quantitative:**
  - Indexing the ~1M-token podcast corpus took 281 min (GPT-4-turbo); the graph has 8,564 nodes and 20,691 edges.
  - Win rates vs vector RAG: comprehensiveness 72–83% (podcast) and 72–80% (news); diversity 75–82% and 62–71%. Vector RAG wins on directness.
- **Decision points:** gleaning continue? (B, logit-forced) · helpfulness (SC 0–100) · communities (CODE) · extraction and reports (X/G).
- **Relevance:** A flagship system built on two canonical S1 decisions: a forced yes/no and a bounded score. The logit-restriction trick also works locally (llama.cpp / Ollama grammars): restrict the output to a few tokens and read their probabilities as a confidence. GraphRAG's global community machinery, however, is too expensive to keep fresh on a laptop (see LightRAG's incremental-update critique below).

### 2.9 LightRAG
- **Citation:** Guo, Z., Xia, L., Yu, Y., Ao, T., Huang, C. (8 Oct 2024; v3 28 Apr 2025). *LightRAG: Simple and Fast Retrieval-Augmented Generation.* arXiv:2410.05779. Repo: https://github.com/HKUDS/LightRAG
- **Pipeline:**
  - *Indexing:* LLM entity/relation recognition, then LLM "profiling" into key–value index entries, then dedup of identical entities/relations across chunks. New data is added incrementally by union, with no rebuild.
  - *Queries:* the LLM extracts **low-level** (specific) and **high-level** (thematic) keywords; these are matched to entities/relations by vector search and expanded to neighbours.
- **Quantitative:**
  - Retrieval uses <100 tokens and 1 API call, vs ≈610 community reports × 1,000 tokens for GraphRAG global search.
  - GraphRAG incremental updates need a rebuild (≈1,399 × 2 × 5,000 tokens in their example).
  - Win rates: 60.0–84.8% vs NaiveRAG; 49.6–54.8% vs GraphRAG.
- **README guidance** (sentences checked verbatim):
  - For local deployment, "Qwen3-30B-A3B-Instruct is a reasonable minimum" for extraction.
  - A non-thinking model "is strongly recommended to avoid slow, expensive extraction"; reasoning is fine for the final answer.
  - bge-m3 embeddings and bge-reranker-v2-m3 are recommended locally; the embedding model must be fixed before indexing.
- **Decision points:** query keywords (X, small) · dedup (CODE, exact match) · extraction (X, heavy).
- **Relevance:** Independent confirmation of the S1/S2 split: *non-thinking* for extraction and keywords, *thinking* only for answers. The stated local minimum for extraction (a 30B-A3B MoE) is well above Omnitrix's Qwen3-4B — treat 4B extraction as an experiment to measure, not an assumption. Omnitrix already uses the recommended bge-m3.

### 2.10 RAPTOR
- **Citation:** Sarthi, P., Abdullah, S., Tuli, A., Khanna, S., Goldie, A., Manning, C. D. (2024). *RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval.* ICLR 2024. arXiv:2401.18059.
- **Pipeline:**
  1. 100-token chunks, embedded with SBERT.
  2. UMAP + Gaussian-mixture soft clustering; BIC picks the number of clusters, and oversize clusters are re-clustered.
  3. GPT-3.5 summaries (average 131 tokens from 6.7 children; ~4% contained minor hallucinations, which did not propagate).
  4. Recurse up the tree.
  5. *Retrieval:* the "collapsed tree" (rank all nodes by cosine up to ~2,000 tokens) beats layer-by-layer traversal.
- **Quantitative:** QuALITY 82.6% with GPT-4 (+20 points absolute over the prior best, 62.3%); QASPER F1 55.7%; build cost grows linearly with document length.
- **Decision points:** all structural decisions are CODE (clustering, thresholds); the only model step is summarization (G).
- **Relevance:** The cheapest structured index in the HippoRAG 2 cost table. A good pattern for long vault documents (contracts, reports): S1-sized summaries plus deterministic clustering.

### 2.11 ReadAgent (gist memory, pagination, lookup)
- **Citation:** Lee, K.-H., Chen, X., Furuta, H., Canny, J., Fischer, I. (2024). *A Human-Inspired Reading Agent with Gist Memory of Very Long Contexts.* ICML 2024, PMLR 235:26396–26415 — https://proceedings.mlr.press/v235/lee24c.html (arXiv:2402.09727).
- **Pipeline:**
  1. **Pagination:** once at least 280 words have accumulated (max 600), numbered break tags are inserted and the LLM **picks** a natural break.
  2. **Gisting:** each page is compressed.
  3. **Lookup:** given the gists, the LLM **chooses which pages to re-read** — ReadAgent-P takes up to 6 at once; ReadAgent-S takes one at a time, up to 6.
  4. Answer.
- **Quantitative:** QuALITY 86.91% (P) / 87.17% (S) vs 85.83% with full text. NarrativeQA (Gutenberg): +12.97% LLM rating and +31.98% ROUGE-L over the best retrieval baseline. Effective context grows 3.5–20×, and 25% fewer words are processed on QuALITY dev.
- **Decision points:** where to break (C1 over numbered tags) · gist (G, compressive) · which pages (CS, ≤6) · answer (G).
- **Relevance:** Numbered-option prompts ("pick tag #k", "pick pages {i, j}") are ideal S1 formats. For long PDFs and email threads, gist + page lookup is a cheap alternative to heavy graph extraction.

### 2.12 MemWalker
- **Citation:** Chen, H., Pasunuru, R., Weston, J., Celikyilmaz, A. (8 Oct 2023). *Walking Down the Memory Maze: Beyond Context Limit through Interactive Reading.* arXiv:2310.05029.
- **Pipeline:** Build a summary tree (≈1,000–1,200-token segments; 5–8 children per node). To answer, the LLM navigates: at each node it reads the child summaries, writes a justification, and chooses an action — go to child *i*, revert to the parent, or answer — carrying a working memory of what it has visited.
- **Quantitative:**
  - Stable Beluga 2 (70B), orig/long: QuALITY 67.4/73.6; SummScreenFD 67.3/64.5; GovReport 59.4/60.4.
  - 15–19% of paths revert, recovering 60–79% of the time.
  - **13B models lag far behind, and asking them to reason first makes them worse.**
- **Decision points:** navigation (C1 with reasoning, sequential and stateful).
- **Relevance:** A counter-example for System 1: sequential, stateful navigation compounds errors and did not work with small models. Keep S1 to single-shot, locally checkable decisions; leave multi-hop navigation to S2 or to code (graph traversal / PPR).

### 2.13 MemoryOS
- **Citation:** Kang, J., Ji, M., Zhao, Z., Bai, T. (30 May 2025). *Memory OS of AI Agent.* arXiv:2506.06326; EMNLP 2025 (Oral) per https://github.com/BAI-LAB/MemoryOS
- **Pipeline:**
  - *Short → mid term:* a short-term queue of 7 dialogue pages feeds FIFO into mid-term *segments*. A page joins a segment if cosine(embedding) + Jaccard(keywords) ≥ **0.6**; the LLM summarises segments and extracts keywords.
  - *Heat:* segment heat = α·visits + β·interaction length + γ·exp(−Δt/μ), with μ = 1e7.
  - *Promotion and eviction:* segments with **heat > 5** are promoted to long-term personal memory; the lowest-heat segments are evicted at capacity.
  - *Long-term memory:* a **90-dimension user-trait profile** plus user-knowledge and assistant-trait FIFO queues (100 entries each), all updated by the LLM.
  - *Retrieval:* top-5 segments, top-10 pages and top-10 long-term entries.
- **Quantitative:**
  - LoCoMo (GPT-4o-mini): on average +49.11% F1 and +46.18% BLEU-1 over baselines.
  - Efficiency (Table 3; granularity not stated):

    | System | LLM calls | Recalled tokens |
    |---|---|---|
    | MemoryOS | 4.9 | 3,874 |
    | A-Mem* | 13.0 | 2,712 |
    | MemGPT | 4.3 | 16,977 |
    | MemoryBank | 3.0 | 432 |

  - Independent 2026 measurements report high latency: 32.4 s user-facing in *Anatomy*; 28.6 s per operation in *Are We Ready*.
- **Decision points:** FIFO (CODE) · segment assignment (CODE score threshold) · heat, promotion and eviction (CODE) · summaries and keywords (G) · trait updates (X over a fixed 90-dimension schema).
- **Relevance:** Shows how much of "memory management" can be pure scoring code. A fixed trait schema is a good S1 target: filling an enumerated profile ("prefers morning meetings: yes / no / unknown") is classification, not generation.

### 2.14 MemOS
- **Citation:** Li, Z., Xi, C., Li, C., Chen, D., Chen, B., Song, S., Niu, S., Wang, H., Yang, J., Tang, C., et al. (39 authors) (4 Jul 2025; v4 3 Dec 2025). *MemOS: A Memory OS for AI System.* arXiv:2507.03724.
- **Pipeline:**
  - The unit of memory is a **MemCube**: payload + metadata (timestamp, origin, semantic type, access control, TTL/decay, priority, compliance tags, usage statistics, version chain).
  - There are three memory types: plaintext, activation (KV-cache) and parametric (adapters).
  - A **MemScheduler** picks which type to load using rules and heuristics (task type, load, cache hit rates, access history).
  - Lifecycle states run generated → activated → merged → archived → **frozen**, with snapshots and rollback.
- **Quantitative:** Claims first place on every LoCoMo category vs MIRIX, Mem0, Zep, Memobase, MemU and Supermemory (exact numbers not captured; see §10).
- **Decision points:** scheduling and lifecycle transitions (CODE rules) · merge detection (similarity) + merged text (G).
- **Relevance:** Governance-heavy metadata (provenance, versioning, access control, freeze) is directly reusable for the Guardian and Auditor — for example, "frozen" legal documents that no agent may rewrite.

### 2.15 Memory-R1 (RL-trained ADD/UPDATE/DELETE/NOOP manager)
- **Citation:** Yan, S., Yang, X., Huang, Z., Nie, E., Ding, Z., Li, Z., Ma, X., Bi, J., Kersting, K., Pan, J. Z., Schütze, H., Tresp, V., Ma, Y. (27 Aug 2025; v5 14 Jan 2026). *Memory-R1: Enhancing Large Language Model Agents to Manage and Utilize Memories via Reinforcement Learning.* arXiv:2508.19828.
- **Pipeline:** A **Memory Manager** receives newly extracted facts plus retrieved related memories and outputs ADD / UPDATE / DELETE / NOOP (with content). An **Answer Agent** "distils" the ~60 retrieved memories down to the relevant ones before answering. Both are trained with PPO/GRPO using only the downstream answer's exact-match reward.
- **Quantitative:**
  - Only **152 training QA pairs** (LoCoMo split 152/81/1,307).
  - Backbones: LLaMA-3.1-8B and Qwen-2.5 3B/7B/14B.
  - LLaMA-3.1-8B (GRPO) vs MemoryOS: F1 45.02 vs 35.04; BLEU-1 37.51 vs 27.99; LLM-judge 62.74 vs 48.20.
  - Transfers zero-shot to MSC and LongMemEval.
  - Case studies show the untrained manager issuing DELETE+ADD where a single UPDATE was correct.
- **Relevance:** The strongest evidence that the ADD/UPDATE/DELETE/NOOP *choice* is learnable by 3–8B models with very little supervision — but only after training. For the hackathon: **log every S1 op proposal alongside the S2 or human correction now**; that log becomes training data later.

### 2.16 Mem-α (RL-trained memory construction)
- **Citation:** Wang, Y., Takanobu, R., Liang, Z., Mao, Y., Hu, Y., McAuley, J., Wu, X. (30 Sep 2025). *Mem-α: Learning Memory Construction via Reinforcement Learning.* arXiv:2509.25911.
- **Pipeline:**
  - The agent reads chunks and calls memory tools over three stores: *core* (≤512 tokens, rewrite only), *semantic* (facts: insert/update/delete) and *episodic* (timestamped events: insert/update/delete).
  - Reward = QA correctness + tool-call validity + 0.05 × compression + LM-judged operation validity.
  - Trained with GRPO on **Qwen3-4B** (32 H100s, ~3 days).
- **Quantitative:**
  - MemoryAgentBench AR/TTL/LRU averages (conflict resolution excluded):

    | System | Average |
    |---|---|
    | **Mem-α (Qwen3-4B, trained)** | **0.592** |
    | GPT-4.1-mini | 0.517 |
    | RAG-top2 | 0.502 |
    | Long-context Qwen3-32B | 0.461 |
    | Untrained Qwen3-4B | 0.389 |
    | MemAgent | 0.198 |
    | MEM1 | 0.071 |

  - Memory size ~129K vs 207K tokens for RAG.
  - Trained on ≤30K-token streams, it generalizes to 400K+ (13×).
- **Relevance:** A 4B model — the size of Omnitrix's S1 — can out-decide a larger general model on memory construction *when trained for it*. Untrained, the same 4B model is much worse (0.389 vs 0.592). Do not assume zero-shot 4B competence on multi-store tool choices.

### 2.17 MemAgent
- **Citation:** Yu, H., Chen, T., Feng, J., Chen, J., Dai, W., Yu, Q., Zhang, Y.-Q., Ma, W.-Y., Liu, J., Wang, M., Zhou, H. (3 Jul 2025; v2 29 Jul 2026). *MemAgent: Reshaping Long-Context LLM with Multi-Conv RL-based Memory Agent.* ICLR 2026 (Oral). arXiv:2507.02259.
- **Pipeline:** Reads text segment by segment, overwriting a fixed-size memory; trained end-to-end with a multi-conversation extension of DAPO RL.
- **Quantitative:** Trained with an 8K window, it extrapolates to 3.5M-token QA with <5% loss and scores 95%+ on 512K RULER (7B and 14B).
- **Relevance:** A learned "overwrite memory" is the opposite of an auditable, inspectable store. Useful for one-off long-document reading, not as the sovereign brain.

### 2.18 LangMem
- **Citation:** LangChain LangMem conceptual guide (accessed 2026-09-25) — https://langchain-ai.github.io/langmem/concepts/conceptual_guide/
- **Pipeline:**
  - *Semantic memory* comes in two shapes: **collections** (many documents that must be reconciled — insert/update/delete) or **profiles** (one schema'd document updated in place).
  - *Episodic memory* stores successful interactions as exemplars; *procedural memory* is evolving system-prompt rules (via a prompt optimizer).
  - Memories can be formed on the **hot path** (adds latency) or in the **background** (higher recall, no user-facing latency); inserts and deletes can be toggled.
- **Quantitative:** In Mem0's LoCoMo run (Mem0's configuration), LangMem scored J 58.10 with a p95 total latency of 60.40 s.
- **Relevance:** "Profile vs collection" is a useful S1 simplification. Profiles turn updates into slot-filling (classification); collections need dedup and conflict judgement. Stable facts about the businessman (family, roles, preferences) belong in schema'd profiles.

### 2.19 Cognee
- **Citation:** https://github.com/topoteretes/cognee (README; v1.6.0 released 18 Sep 2026) · docs https://docs.cognee.ai/setup-configuration/structured-output-backends · issue #2119 (8 Feb 2026).
- **Pipeline:** `add` → `cognify` (chunking; LLM entity/relation extraction via structured output; summaries; graph + vectors) → `memify` and search. Backends include Kuzu/Neo4j (graph) and LanceDB/pgvector (vector). The README advertises running the whole memory layer on Postgres, though graph-on-Postgres is labelled a demo feature. v1.6.0 adds "keyless" workflows with local extraction and embedding models; text ingestion and retrieval can run without an LLM.
- **Small-model notes:**
  - The docs say small Ollama models (e.g., llama3.1:8b, qwen3.5:0.8b) often fail instructor-validated JSON; the fixes are the BAML backend or `json_schema_mode` (now the Ollama default).
  - Issue #2119: Qwen3-4B / Mistral-7B GGUF endpoints hung for 10+ minutes in silent structured-output retries (128-second retry windows).
- **Quantitative [vendor]:** BEAM conversational memory 0.79 (100K tokens) and 0.67 (10M), with benchmark-specific configuration.
- **Relevance:** The closest off-the-shelf fit to Omnitrix's Postgres + pgvector stack. But an independent 2026 evaluation (Wolff & Bennati, §4.11) put Cognee and Graphiti 22–26 points below mem0 and plain RAG on LoCoMo (55–56% vs 78–81%), attributing the gap to extraction losses.

### 2.20 Other notable 2025–2026 systems (brief)
- **LightMem** — Fang, J., Deng, X., Xu, H., et al. (12 authors). arXiv:2510.18866 (v4 28 Feb 2026); ICLR 2026 per https://github.com/zjunlp/LightMem
  - *Pipeline:*
    - *Sensory stage:* uses **LLMLingua-2**, a small token-classification model, to drop low-value tokens (keeping those above a percentile threshold). Topics are segmented where attention-based and similarity-based boundaries coincide.
    - *Short-term stage:* summarises when a buffer threshold is reached.
    - *Long-term stage:* does cheap "soft" inserts online and **merge/update/ignore consolidation offline** ("sleep-time").
  - *Reported* (LongMemEval-S, GPT-4o-mini, vs A-MEM/Mem0/MemoryOS/LangMem):
    - Up to 38× fewer tokens, 30× fewer API calls and 12.4× faster, with +2.1–6.4% accuracy.
    - Online phase alone: 105.9× fewer tokens and 159.4× fewer calls.
    - With Qwen3-30B: 21.8× fewer tokens, 17.1× fewer calls, up to +7.67% accuracy.
  - *Deployment:* supports Ollama and vLLM.
  - **Relevance:** the clearest published example of an *encoder-level System 1 gate before any LLM call*, combined with deferred consolidation.
- **SimpleMem** — Liu, J., Su, Y., Xia, P., Han, S., Zheng, Z., Xie, C., Ding, M., Yao, H. arXiv:2601.02553 (Jan 2026); ICML 2026 poster.
  - *Pipeline:* semantic structured compression → online synthesis within a session → intent-aware retrieval planning.
  - *Reported:* +26.4% average F1 on LoCoMo and up to 30× fewer inference-time tokens; lowest format-error rate on a 3B backbone in *Anatomy* (4.82%).
- **Mastra "Observational Memory"** **[vendor]** — research page dated 9 Feb 2026: https://mastra.ai/research/observational-memory
  - *Pipeline:* a background Observer turns messages into dated observations once history passes a token threshold (3–6× compression; up to 40× for tool output). A Reflector condenses observations past a second threshold. The context stays append-only, which keeps it cache-friendly.
  - *Reported* (LongMemEval; Gemini-2.5-flash as observer/reflector; ~30k-token context): 94.87% with a GPT-5-mini actor; 93.27% with Gemini-3-pro; 84.23% with GPT-4o.
  - **Relevance:** compaction by a fast model on token-count triggers — with no retrieval at all — scores near the top of LongMemEval. Omnitrix should use it as a baseline.
- **Hindsight** — Latimer, C., Boschi, N., Neeser, A., Bartholomew, C., Srivastava, G., Wang, X., Ramakrishnan, N. arXiv:2512.12818 (14 Dec 2025); ACL 2026 demo per ACL Anthology listing.
  - *Pipeline:* four networks (world facts, agent experiences, entity summaries, evolving beliefs) and three operations (retain / recall / reflect). Recall fuses semantic, BM25, entity-graph and temporal-filter searches with RRF and a neural reranker.
  - *Reported:* **83.6% on LongMemEval with a 20B open model**, 91.4% with a larger one; LoCoMo up to 89.61%.
- **MIRIX** — Wang, Y., Chen, X. arXiv:2507.07957 (10 Jul 2025).
  - *Pipeline:* six stores (core, episodic, semantic, procedural, resource, knowledge vault); a meta memory manager routes each update or query to per-store agents.
  - *Claims:* LoCoMo 85.4%; +35% accuracy with 99.9% less storage than RAG on ScreenshotVQA.
  - **Relevance:** "which store(s) does this go to?" is a pick-subset S1 decision.
- **Nemori** — Ma, W., Nan, J., Wu, W., Chen, Y. arXiv:2508.03341. v1 (5 Aug 2025) was titled *Nemori: Self-Organizing Agent Memory Inspired by Cognitive Science*; v4 (16 Apr 2026) is retitled *What Deserves Memory: Adaptive Memory Distillation for LLM Agents*.
  - *Pipeline:* episode-boundary detection plus "predict–calibrate" (store what existing memory failed to predict).
  - *Caveat:* highest format-error rate on a 3B backbone in *Anatomy* (30.38%).
- **ConvMemory v3** **[preprint, single author]** — Pan, T. arXiv:2606.26753 (25 Jun 2026).
  - *Pipeline:* decides whether a retrieved memory has been superseded using small **encoder** heads (MiniLM and DeBERTa-v3 "slot heads") with an evidence gate.
  - *Reported:* current-state hit@1 rises from 45.1% (never demote) to 95.7%, while protecting 99.4% of non-superseded memories (synthetic + transfer evaluation).
  - **Relevance:** "is this fact still current?" may not need an LLM at all.
- **Mnemosyne** — Jonelagadda, A., Hahn, C., Zheng, H., Penachio, S. arXiv:2510.08601 (7 Oct 2025).
  - *Pipeline:* edge-oriented and unsupervised — a graph store, "substance" and redundancy filters, commit/prune, and probabilistic recall with temporal decay.
  - *Reported:* 65.8% human-eval win rate vs 31.1% for RAG in longitudinal healthcare dialogue; LoCoMo average 54.6%.
- **Mi-Memory** — Liu, X., Teng, H., Li, C., et al. (18 authors). arXiv:2607.18975 (21 Jul 2026).
  - *Approach:* a lifecycle framework for personal AI across devices — typed evidence with source identity, diagnostic traces, explicit memory-policy changes, and gate/rollback records.
  - *Reported:* MemStack 93.59% LoCoMo, 57.24% PersonaMem-V2, 87.47% LongMemEval.

---

## 3. Ingestion cost — evidence that motivates System 1

| System / study | Unit | LLM calls per unit | Tokens | Time | Source |
|---|---|---|---|---|---|
| Mem0 (2025 algorithm) | message batch | 2 (extract + reconcile); Mem0g adds graph LLM stages | — | — | paper; Mem0 2026 blog ("two LLM passes") |
| Mem0 (2026 OSS default) | `add()` | **1** (single-pass ADD-only); 0 with `infer=False` | context = top-10 memories + last 10 messages | extraction latency "roughly half" of before | code + [vendor] blog |
| Mem0 vs Zep memory footprint | LoCoMo conversation | — | Mem0 ≈7k; Mem0g ≈14k; **Zep >600k** (raw ≈26k) | Zep retrieval good only hours later | Mem0 paper (Zep disputes their setup) |
| Graphiti (Sept 2026 code) | episode with N entities, M facts | ≈ 3–4 + M … 3–4 + 2M (+ N + M with custom types) | + embeddings for every node and fact | — | my count from source |
| Zep (paper design) | episode | ≥ 7 LLM stages (extract, reflexion, resolve, facts, edge dedup, dates, invalidation) + community summaries | — | — | arXiv:2501.13956 |
| A-MEM | memory note | 3 LLM steps (construct, link, evolve) | ≈1,200 tokens | 5.4 s (GPT-4o-mini); **1.1 s (Llama 3.2 1B, local)** | arXiv:2502.12110 |
| MemoryOS / A-Mem* / MemGPT | LoCoMo unit (unspecified) | 4.9 / 13.0 / 4.3 | 3,874 / 2,712 / 16,977 recalled tokens | — | MemoryOS Table 3 |
| HippoRAG 2 vs RAPTOR / LightRAG / GraphRAG | passage (MuSiQue, 11,656 passages; Llama-3.3-70B) | — | ≈790+257 vs ≈146+17 / ≈5.9k+1.6k / ≈9.9k+3.1k | 99.5 / 100.5 / — / 277 min total | HippoRAG 2 Table 12 |
| GraphRAG | ~1M-token podcast corpus | many | — | 281 min (GPT-4-turbo) | arXiv:2404.16130 |
| LightRAG vs GraphRAG | global query | 1 vs hundreds | <100 vs ≈610k | — | arXiv:2410.05779 |
| Wolff & Bennati (LoCoMo, 10 conversations; GPT-4o-mini) | whole corpus | — | $4.82 mem0 / $5.49 Graphiti / $1.32 cognee / $0.01 RAG | **4.44 h / 9.69 h / 8.44 h / 0.93 h** | arXiv:2601.07978 |
| HaluMem-Medium | whole dataset (~1.5k turns per user) | — | — | **2,768 min Mem0** vs 273 min Supermemory | arXiv:2511.03506 |
| *Anatomy* Table 5 | benchmark build | — | 1.3M–7.0M tokens | 0.6–15.0 h build; MemoryOS 32.4 s per query | arXiv:2602.19320 |
| *Are We Ready* | query (one workload) | — | — | memory-op latency 3.67 s (LightMem, utility 48.3) → 155.1 s (Zep, utility >84); 374–552 s on LongBench (Mem0, MemoChat, MemoryOS, A-MEM) | arXiv:2606.24775 |
| LightMem vs A-MEM/Mem0/MemoryOS/LangMem | LongMemEval-S | up to 30× fewer calls (159× online) | up to 38× fewer tokens (106× online) | up to 12.4× faster | arXiv:2510.18866 |
| Generative Agents | 25 agents × 2 game-days | every observation scored + reflections + plans | — | "thousands of dollars", multiple days | arXiv:2304.03442 |

**What this implies for a 24 GB laptop.** Per-item ingestion cost ≈ Σ over calls of (prompt tokens ÷ prefill speed + output tokens ÷ decode speed). Thinking models also add hidden reasoning tokens to every call.
- A Graphiti-style pipeline makes roughly 8–14 calls for an email that yields 5 facts (my estimate from the code count above).
- Running all of those calls on a 14B thinking model makes ingestion of a normal day's mail take hours. Cloud-GPU systems already need hours for ten LoCoMo conversations (Wolff & Bennati).
- The published levers, all orthogonal:
  1. **Gate before extraction** (LightMem's encoder filter; Generative-Agents-style importance).
  2. **One extraction call per item** (Mem0 2026).
  3. **Route every discrete post-extraction judgement to S1** (Graphiti's `small_model`).
  4. **Push consolidation to sleep-time** (Letta, LightMem).
  5. **Never recompute globally** (*Are We Ready*, Finding 5).
- The runtime slice should plug measured tokens/s for Qwen3-1.7B/4B/14B into the formula above to size the budget. I did not measure these speeds.

---

## 4. Benchmarks and results

### 4.1 DMR (Deep Memory Retrieval)
- **Source:** introduced in MemGPT (arXiv:2310.08560). Zep describes it as 500 conversations of 5 sessions each, ~60 messages per conversation (arXiv:2501.13956).
- **Results:** MemGPT 93.4% (GPT-4 Turbo); Zep 94.8%; full conversation 94.4%. With gpt-4o-mini, full conversation already scores 98.0% (Zep 98.2%).
- **Takeaway:** saturated. It fits in context and asks single-turn fact questions, so it no longer discriminates between systems.

### 4.2 LoCoMo
- **Citation:** Maharana, A., Lee, D.-H., Tulyakov, S., Bansal, M., Barbieri, F., Fang, Y. (2024). *Evaluating Very Long-Term Conversational Memory of LLM Agents.* ACL 2024. arXiv:2402.17753. Data: https://github.com/snap-research/locomo
- **Design:** machine–human generated dialogues grounded in personas and temporal event graphs. Tasks: QA (single-hop, multi-hop, temporal, open-domain, adversarial), event summarization, multimodal dialogue generation.
- **Paper statistics:** 50 conversations; on average 19.3 sessions, 304.9 turns and 9,209 tokens each. 7,512 QA pairs: 2,705 single-hop, 1,104 multi-hop, 1,547 temporal, 285 open-domain, 1,871 adversarial.
- **Released data:** the README says the release (`locomo10.json`) is a 10-conversation subset of the original 50, keeping the longest ones. Memory papers typically score its **1,540 non-adversarial questions** (the count used by Mem0's research page, the Penfield audit and Wolff & Bennati).
- **Results (2024):**
  - Human QA F1 87.9 vs 37.8 for the best model (GPT-3.5-turbo-16K, full context).
  - **Temporal:** human 92.6 vs 20.3.
  - Adversarial: long-context models collapsed (12.8 → 2.1).
  - Retrieving "observations" (extracted assertions) beat retrieving raw dialogue by ~5%.
- **Takeaway:** it pointed the field at temporal reasoning and false-premise questions. But the released conversations (16–26k tokens) fit in modern context windows (§4.12).

### 4.3 LongMemEval
- **Citation:** Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W., Yu, D. (2025). *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory.* ICLR 2025. arXiv:2410.10813.
- **Design:** 500 questions covering five abilities — information extraction, multi-session reasoning, temporal reasoning, **knowledge updates**, **abstention** — across seven question types: single-session-user / -assistant / -preference, multi-session, knowledge-update, temporal-reasoning, and 30 false-premise abstention questions. Variants: **S** ≈115k tokens per question; **M** ≈500 sessions, ≈1.5M tokens.
- **Results — accuracy drops:**
  - Long-context models on S: GPT-4o −30.3%, Llama 3.1 70B −55.1%, Llama 3.1 8B −36.1%, Phi-3 128k −45.9%.
  - Commercial assistants on a 10× shorter history: ChatGPT (GPT-4o) −37%, Coze −64%.
- **Results — design findings:**
  - Round-level memory units beat session-level ones.
  - Fact-augmented keys give +9.4% recall@k and +5.4% accuracy; **the facts were extracted by Llama 3.1 8B**.
  - Time-aware query expansion gives +11.3% (rounds) / +6.8% (sessions) recall with GPT-4o, but **Llama 3.1 8B "struggles to generate accurate time ranges"**, hallucinating or missing temporal cues.
  - Chain-of-Note + JSON-formatted reading adds up to +10 points.
- **Takeaway for Omnitrix:** A clean small-model split. *Write-time* extraction of facts, keyphrases and timestamped events was fine at 8B. *Query-time* temporal-range inference was not. Parse time expressions with deterministic code, anchored on the message and query timestamps. The categories (updates, time, abstention) are exactly what a secretary brain must get right.

### 4.4 MemoryAgentBench
- **Citation:** Hu, Y., Wang, Y., McAuley, J. (2025; v4 28 Jun 2026). *Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions.* ICLR 2026. arXiv:2507.05257.
- **Design:** long-context datasets are fed incrementally as multi-turn chunks. Four competencies:
  - accurate retrieval (AR);
  - test-time learning (TTL);
  - long-range understanding (LRU);
  - selective forgetting / conflict resolution (CR).

  New datasets: EventQA, and **FactConsolidation**, built from MQuAKE counterfactual edit pairs where later facts must override earlier ones.
- **Results (v4, Table 3):**
  - "All methods fail" on multi-hop conflict resolution. The best is 28% (GPT-5-mini, long-context); every other method scores 1–7%.
  - FactConsolidation single-hop:

    | Group | Scores |
    |---|---|
    | Long-context | 30–78 (GPT-5-mini 78, GPT-4o 60, GPT-4o-mini 45) |
    | RAG | BM25 48; embedding RAG 18–29; HippoRAG-v2 54 |
    | **Memory systems** | Mem0 18, Cognee 28, **Zep 7**, MemGPT 28, MIRIX 14–20, RAPTOR 14, GraphRAG 14 |

  - Long-context wins TTL and LRU; RAG (even BM25) wins AR.
- **Takeaway:** the Historian's contradiction job is the hardest category in the field. Design for it explicitly (bi-temporal facts, supersession rules, human confirmation) rather than hoping retrieval handles it.

### 4.5 BEAM
- **Citation:** Tavakoli, M., Salemi, A., Ye, C., Abdalla, M., Zamani, H., Mitchell, J. R. (31 Oct 2025; v2 21 Feb 2026). *Beyond a Million Tokens: Benchmarking and Enhancing Long-Term Memory in LLMs.* ICLR 2026. arXiv:2510.27246. Repo: https://github.com/mohammadtavakoli78/BEAM
- **Design:** 100 generated conversations of up to 10M tokens, with 2,000 validated questions.
- **Results:** even 1M-context LLMs degrade as dialogues lengthen. LIGHT (episodic memory + working memory + scratchpad) adds 3.5–12.69% over the strongest baselines.
- **Takeaway:** the first widely used benchmark that genuinely exceeds context windows. Vendors now report BEAM-1M / BEAM-10M.

### 4.6 HaluMem (operation-level)
- **Citation:** Chen, D., Niu, S., Li, K., Liu, P., Zheng, X., Tang, B., et al. (9 authors) (5 Nov 2025; v3 5 Jan 2026). *HaluMem: Evaluating Hallucinations in Memory Systems of Agents.* arXiv:2511.03506. Repo: https://github.com/MemTensor/HaluMem. **Caveat:** authored by the MemOS (MemTensor) team, and MemOS wins.
- **Design:** separate evaluation of **extraction**, **updating** and **QA**. HaluMem-Medium / -Long: ~15k memory points, ~3.5k questions, 1.5k / 2.6k turns per user, >1M tokens.
- **Results:**
  - Extraction recall was below 60% for every system except MemOS.
  - **Update correctness (Medium / Long):**

    | System | Medium | Long |
    |---|---|---|
    | Mem0 | 25.50% | 1.45% |
    | Mem0-Graph | 24.50% | 1.47% |
    | Memobase | 5.20% | 4.10% |
    | Supermemory | 16.37% | 17.01% |
    | MemOS | 62.11% | 65.25% |

  - Failures are overwhelmingly **omissions** (Mem0 74–98%) rather than hallucinated updates (≤1.2%).
  - Time to add HaluMem-Medium: 273 min (Supermemory) to 2,768 min (Mem0).
- **Takeaway:** measure the write path directly. Extraction recall and update omission are where memory quietly fails, and the errors then propagate into answers.

### 4.7 MemoryArena
- **Citation:** He, Z., Wang, Y., Zhi, C., Hu, Y., Chen, T.-P., Yin, L., et al. (14 authors) (18 Feb 2026; v2 17 Sep 2026). *MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks.* ICML 2026. arXiv:2602.16313.
- **Design:** human-crafted tasks with interdependent subtasks across sessions — bundled shopping, group travel planning with preferences, progressive search, sequential formal reasoning.
- **Result:** agents that are near-saturated on LoCoMo perform poorly here.
- **Takeaway:** recall benchmarks overstate how useful memory is for *acting*. This matters for the Operator and Planner.

### 4.8 RHELM
- **Citation:** Zhang, H., Tang, Z., Yu, X., Liu, X., Gong, Y., Huang, H., Lu, Y., Deng, W., Sun, F., Zhang, Q., Yang, H. (29 May 2026). *Beyond Static Dialogues: Benchmarking Realistic, Heterogeneous, and Evolving Long-Term Memory.* arXiv:2605.31086.
- **Design:** dialogues interleaved with heterogeneous streams (documents, emails) and evolving user timelines (LOOP generator); 7 inquiry types mapped to 27 memory characteristics.
- **Result:** current systems are weakest at **multi-source aggregation** and real-world contextual reasoning.
- **Takeaway:** the benchmark closest to Omnitrix's businessman scenario (emails + documents + chats).

### 4.9 MERIT
- **Citation:** Mishra, S., Mishra, S. (26 Jul 2026). *When Does Memory Help? A Cost-Aware Evaluation of Long-Term Memory in Tool-Using LLM Agents.* arXiv:2609.05441. **[preprint]**
- **Results:**
  - Memory raises dependent-task success from 0.00 to 0.55–1.00.
  - Embedding retrieval is unstable across models (0.30–0.95); structured fact stores and LLM summaries hold 0.70–1.00.
  - **Agents acted on correctly retrieved values only 55% of the time.**
  - Implementation choices swing success by up to 60 points; the best configurations give 2.7–3.9× the marginal utility per dollar of full replay. (23,440 episodes, $42.57 total.)
- **Takeaway:** retrieval is not use. The Operator should read structured fields (amount, date, counterparty), not free-text snippets.

### 4.10 MemArena (on-device personal memory)
- **Citation:** Zhang, J., Ma, X. (20 May 2026). *MemArena: An Ego-Centric Benchmark for On-Device Agentic Personal Memory Assistants at Scale.* arXiv:2608.02613. **[preprint]**
- **Design:** 50 agents × 15 days (10.3M tokens); open-weight readers down to Qwen3-0.6B on an edge node; backends: vanilla context, BM25-RAG, oracle, Memobase, MemSearch.
- **Results:**
  - **Backend choice mattered more than scaling the reader model** (+32.5 / +19.2 pp vs +10.6 / +6.8 pp).
  - **Permission-aware access failed universally.**
  - Memory search adds 7–87 ms.
- **Takeaway:** on-device, invest in the memory substrate and retrieval before a bigger model. Enforce permissions in code.

### 4.11 Evaluation-methodology studies (2026)
- **Wolff & Bennati** — Wolff, B., Bennati, J. (12 Jan 2026; v5 3 Sep 2026). *Cost and Accuracy of Long-Term Memory in Distributed Multi-Agent Systems Based on Large Language Models.* arXiv:2601.07978.
  - *Setup:* LoCoMo (1,540 questions); GPT-4o-mini for extraction and answers. Qwen2.5-3B (q4_K_M) was used only as the tool-calling edge agent during Q&A.
  - *Accuracy:* mem0 81.08%; RAG 78.31%; full-context 77.16%; **Graphiti 56.03%; cognee 55.27%**.
  - *Why graphs lost:* 25.58% and 28.18% "unknown" answers, attributed to information lost during entity resolution, relation labelling and schema-constrained extraction.
  - *Cost:* the RAG baseline had 8.4× lower total cost of ownership than mem0; only RAG and mem0 were Pareto-optimal.
- **MemDelta** — Wang, K. (29 Jun 2026). *MemDelta: Controlled Baselines and Hidden Confounds in Agent Memory Evaluation.* arXiv:2606.29914. **[preprint, single author]**
  - The answer model flips rankings, and swapping the embedding model alone moves accuracy 6.2 pp.
  - Mem0 ≈ cloud RAG (72.7 vs 73.9) on 2 of 6 question types at ~50× the cost; agent self-managed memory (42%) scored below basic retrieval (47%).
- **Harness the Memory** — Huang, W.-C., Zhang, W., Wu, Y., Chen, Y., Jiang, E. H., Yang, W., Yang, Y., Zou, H. P., Zhang, H., Wu, Y. N., Wu, H., Chang, K.-W., Yu, P. S., Liu, X., Caliskan, A. (15 Aug 2026). *Harness the Memory: A Holistic Evaluation of Memory Substrates in Memory Agents.* arXiv:2608.15008.
  - *Setup:* 7 substrate families, 3 backbones, 4 suites, 26 metrics.
  - *Finding:* broad retrieval helps factual QA, but **excessive retrieval harms sequential decision-making**; the authors call for adaptive routing.
- **Penfield Labs LoCoMo audit** **[practitioner]** — 8 Apr 2026. https://penfieldlabs.substack.com/p/we-audited-locomo-64-of-the-answer · code https://github.com/dial481/locomo-audit
  - **99 of 1,540 (6.4%) answers in the key are wrong** in ways that corrupt scores.
  - The standard gpt-4o-mini judge accepted **62.81%** of deliberately wrong but topic-adjacent answers, while catching ~89% of specific wrong names and dates.
  - Resulting ceiling ≈ **93.6%**.
- *Anatomy* (§1.7) and *Are We Ready* (§1.8) complete this set.

### 4.12 The LoCoMo disputes (Mem0 vs Zep vs Letta) — and what they imply
1. **Apr 2025 — Mem0 paper:** Mem0g 68.44 J, Zep 65.99, full-context 72.90. Mem0 also reports MemGPT/Letta numbers.
2. **6 May 2025 — Zep rebuttal** **[vendor]** (https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/; modified 3 Jun 2026):
   - Zep says Mem0 misconfigured it: both speakers were entered as the "user"; timestamps were appended to message text instead of set in `created_at`; searches ran sequentially rather than in parallel, inflating latency.
   - Zep's own rerun: **75.14% ± 0.17**, p95 search 0.632 s.
   - Zep also criticised LoCoMo itself: conversations fit in context; full-context beats the memory systems; category 5 is dropped for missing answers; there are data errors. It pointed to LongMemEval instead.
3. **12 Aug 2025 — Letta** **[vendor]** (https://www.letta.com/blog/benchmarking-ai-agent-memory/): a plain **filesystem agent** (grep / search_files / open / close, gpt-4o-mini) scored **74.0%**, above Mem0g's reported ~68.5%. Letta said it could not see how Mem0 had backfilled LoCoMo into MemGPT/Letta, and argued that such benchmarks mostly measure retrieval and tool use.
4. **2026 — vendor scores jump to 90%+:** Mem0 92.5; Zep 94.7 (product page). Token budgets and latencies are now reported alongside, but answer and judge models are often undisclosed.
5. **Apr 2026 — independent audit:** 6.4% of the answer key is wrong and the judge is lenient, so the ceiling is ≈93.6%. A reported 94.7% is therefore above what a perfectly correct system could score against the published key. That implies judge leniency or systematic agreement with key errors — a logical consequence of the audit, not a demonstrated fault.
6. **2026 academic re-evaluations disagree with vendor rankings:**
   - Wolff & Bennati: mem0 > RAG ≈ full-context ≫ Graphiti ≈ Cognee.
   - MemDelta: Mem0 ≈ RAG at ~50× the cost.
   - *Anatomy*: judge and metric problems.
   - *Are We Ready*: no universal winner.

**Implications for evaluation methodology:**
- Fix and disclose the answer model, the judge model and prompt, the retrieval token budget, and the ingestion protocol (speaker roles, timestamps, concurrency, wait-for-indexing). Report confidence intervals over reruns.
- Always include **full-context** and **plain RAG (BM25 + dense)** baselines. LoCoMo-scale data fits in context, and simple RAG is often on the Pareto front.
- Validate the judge adversarially (topic-adjacent wrong answers) and audit the gold answers. Avoid claiming scores above the audited ceiling.
- Prefer benchmarks that exceed the context window (LongMemEval-M, BEAM) or that test updates, abstention and action: LongMemEval, MemoryAgentBench, HaluMem, MemoryArena, RHELM.
- Report **cost**: ingestion calls, tokens and time, plus query latency and tokens. The 2026 vendor pages and *Anatomy* show this is becoming standard.

### 4.13 What the benchmarks say matters most
1. **Temporal reasoning.** It is the largest human–model gap in LoCoMo (92.6 vs 20.3 F1), and one of the biggest wins from structured memory: Zep LongMemEval temporal 45.1 → 62.4; Mem0's temporal category +29.3 after adding write-time temporal metadata. Query-time time-range inference needs a strong model (LongMemEval), so do it in code.
2. **Knowledge updates and conflict resolution.** Multi-hop conflict resolution tops out at 28% (MemoryAgentBench). Update correctness is 1–65% with omission-dominated failures (HaluMem). Zep's knowledge-update results are mixed (−2.5 points with gpt-4o-mini, +5.1 with gpt-4o).
3. **Multi-session aggregation and multi-source synthesis.** Multi-session is still the weakest LongMemEval category even at 95% overall (Mastra 87.2%). RHELM's weak spot is multi-source aggregation (emails + documents).
4. **Abstention / false premises.** 30 LongMemEval questions; LoCoMo adversarial questions crushed long-context models (12.8 → 2.1); lenient judges reward vague answers. A secretary must be able to say "I have no record of that."
5. **Extraction recall.** Below 60% for most systems (HaluMem); graph ingestion loses information (Wolff & Bennati). **Keep raw episodes as ground truth.**
6. **Assistant-side and preference memory.** Zep lost 9–18% (relative) on single-session-assistant questions. Mem0 reports its largest 2026 LongMemEval gain (+51.8) on this category after it began extracting agent-generated facts; the causal link is Mem0's framing, not an ablation I could verify. Preference questions improved most with structure (Zep +36.7 points with gpt-4o).
7. **Using memory to act.** MemoryArena and MERIT (only 55% of correctly retrieved values acted on) show that recall scores overstate end-to-end value.
8. **Cost and latency.** Now reported by vendors and academic audits alike; the "agency tax" can reach tens of seconds per query and hours of ingestion.

---

## 5. Running memory systems with small local models — reported experience

### 5.1 Official guidance from the projects
- **Graphiti** (README + LLM-configuration docs):
  - It works best with providers that support structured output; other providers risk wrong schemas and ingestion failures, "particularly problematic when using smaller models."
  - The docs tell Ollama users to **avoid smaller local models** and to set both `model` and `small_model` to a capable model.
  - Use `OpenAIGenericClient`, because Ollama lacks the `/v1/responses` endpoint.
  - Concurrency is set by `SEMAPHORE_LIMIT` (default 10).
- **LightRAG** (README): Qwen3-30B-A3B-Instruct is "a reasonable minimum" locally for extraction. Use a *non-thinking* model for extraction and keywords; thinking is acceptable only for answers.
- **Letta** (docs): start with a frontier model, because weaker models can make agents behave unexpectedly.
- **Cognee** (docs): small Ollama models (llama3.1:8b, qwen3.5:0.8b) often fail instructor-validated JSON. Use BAML or `json_schema_mode`, which is now the Ollama default.
- **Mem0** (blog, "Local AI Agent with Persistent Memory" — date unverified, see §10): recommends `qwen3:8b` for reliable structured output and disabling thinking.

### 5.2 Failure classes seen in GitHub issues and studies
| Failure class | Evidence | Impact |
|---|---|---|
| Schema echo / validation errors | Graphiti #868 (27 Aug 2025): deepseek-r1:7b/8b returned the schema's definitions instead of entities, plus malformed JSON. Graphiti #1911 (23 Sep 2026): validation errors (model returned the JSON schema) and empty responses | #1911: of ~700 episodes, 2 substantive ones were **silently dropped with 0 edges**; retrying the same content succeeded 2 times out of 3 |
| Optional fields skipped under grammar-constrained decoding | Graphiti #1909 (23 Sep 2026), graphiti-core 0.30.1: gemma3:12b omitted `valid_at` on 10 of 40 edges; with every property marked required, 0 of 72 were missing and gold-fact recovery rose 28 → 37 of 45. phi4:14b emitted the keys consistently | Temporal facts lose their dates, and invalidation logic silently stops working |
| Thinking tokens break parsers | Mem0 blog: Qwen `<think>` prefixes made the parser return nothing, so `memory.add()` wrote no vectors (current `mem0/memory/utils.py` strips `<think>…</think>`) | Silent memory loss |
| Prose around JSON | Mem0 #5998 (29 Jun 2026): `extract_json` takes the text from the first `{` to the last `}`, so prose containing braces corrupts the parse and memories are dropped — common with chatty local models (Ollama, LM Studio) | Silent memory loss (a recurring bug class) |
| Provider plumbing drops `response_format` | Mem0 #4607 (29 Mar 2026): the vLLM provider did not forward `response_format` → "Invalid JSON response" during extraction and update | Updates fail on corrections |
| Retry storms / hangs | Cognee #2119 (8 Feb 2026): Qwen3-4B / Mistral-7B GGUF via llama-cpp-python; 128-second retry windows led to 10+ minutes of silent retries | Pipeline appears frozen |
| Small non-reasoning model on a pick-subset judgement | Graphiti #1666 (18 Jul 2026): gpt-4.1-nano with the stock `EdgeDuplicate` schema was correct in **7 of 15** trials (5 cases × 3 replicates) and missed "User sold X" vs "User owns X". A **reasoning-first** schema variant was correct in **14 of 15** | Stale facts survive. Small n — treat as directional |
| Format-error rate grows with pipeline complexity and smaller backbones | *Anatomy*: Qwen-2.5-3B 4.82% (SimpleMem) / 30.38% (Nemori) vs 1.20% / 17.91% on GPT-4o-mini | Memory is corrupted by failed writes while chat stays fluent ("silent failure") |

### 5.3 What small models did well vs poorly (task-dependence)
- **Worked:**
  - Indexing-time extraction of facts, keyphrases and timestamped events (Llama 3.1 8B, LongMemEval).
  - Note attributes and linking (A-MEM, Llama 3.2 1B at 1.1 s per op; relative gains, low absolute scores).
  - Tool-calling router during QA (Qwen2.5-3B q4, Wolff & Bennati).
  - On-device reading with a good memory backend (Qwen3-0.6B readers, MemArena).
  - **Trained** memory managers (Memory-R1 at 3B–14B; Mem-α at 4B).
- **Failed or struggled:**
  - Query-time time-range inference (Llama 3.1 8B, LongMemEval).
  - Multi-step tree navigation (13B, MemWalker).
  - Contradiction detection without a reasoning field (gpt-4.1-nano, #1666).
  - Complex multi-stage structured pipelines on 3B (Nemori, *Anatomy*).
  - Zero-shot multi-store tool use (untrained Qwen3-4B: 0.389 vs 0.592 after training).

### 5.4 Guard-rails distilled for Omnitrix's S1 prompts
1. Ask for **ids / enums / booleans**, not open JSON. Constrain decoding with a grammar (Ollama `format` / llama.cpp GBNF), and make **every field required** (#1909).
2. For relational judgements (duplicate, contradiction, supersession), put a **one-line reason field first** (#1666). Keep it short, and A/B it on real data: MemWalker shows free-form reasoning can hurt weaker models.
3. **Disable thinking** for S1 calls and strip `<think>` tags defensively (Mem0 blog; LightRAG README).
4. Validate → retry once with the error message → **dead-letter queue + visible alert**. Never drop silently (#1911, #5998, Cognee #2119).
5. Keep candidate sets small: ≤15 for entity matching (Graphiti's limit); ≤5 for relevance filtering (HippoRAG 2).
6. Use the probabilities of the constrained answer tokens as a raw confidence signal (GraphRAG's logit-bias idea). How to calibrate them belongs to the routing/calibration slice.
7. Track per-decision **parse-failure rate, escalation rate, and S1–S2 agreement** on an audited sample. This is the metric *Anatomy* says the field is missing.

---

## 6. Decision-point table — system × decision × how it is decided × could System 1 do it?

"How decided" describes the source system. "S1?" is my assessment using the §0 legend, with the evidence for it.

| System | Decision point | Out | How it's decided in the source | S1? — evidence / note |
|---|---|---|---|---|
| MemGPT/Letta | Warn / flush context | B | CODE: 70% / 100% of context; evict ~50% | CODE |
| MemGPT/Letta | Save to core memory? | B | LLM tool call | S1\* (Letta warns weaker models behave unexpectedly) |
| MemGPT/Letta | What to write to core memory | G | LLM tool arguments | S2, or S1 with a strict template |
| MemGPT/Letta | Search memory? Which tool? | C1 | LLM tool choice | S1\* (tiny tool menu) |
| MemGPT/Letta | Continue chaining (heartbeat)? | B | LLM flag | S1\*, with a step cap in CODE |
| MemGPT/Letta | Eviction summary | G | LLM recursive summary | S1 feasible for compression (ReadAgent/LightMem); S2 for quality |
| Letta 2026 | When to dream / consolidate | B | CODE: after N steps or on compaction | CODE |
| Letta 2026 | What lesson, and where to file it | G+C1 | LLM subagent; optional review pass | S2 offline; review = approval gate |
| Generative Agents | Importance of an observation | SC 1–10 | LLM rating | **S1** (archetypal; calibrate thresholds) |
| Generative Agents | Retrieval ranking | SC | CODE: recency (0.995/h) + importance + relevance | CODE |
| Generative Agents | Reflect now? | B | CODE: Σimportance > 150 | CODE (fed by S1 scores) |
| Generative Agents | Reflection questions and insights | G | LLM | S2 (offline) |
| Generative Agents | React to this observation? | B | LLM | S1 |
| Generative Agents | Plan / re-plan | G | LLM | S2 |
| MemoryBank | Forget / retain | B | CODE: R = e^(−t/S); S+1 on recall | CODE |
| MemoryBank | Event / personality summaries | G | LLM, daily batch | S2 batch (or S1 for short summaries) |
| Mem0 (2025) | Candidate facts from new messages | X | LLM extraction (summary + last 10 messages) | S1\* for short messages (Mem0 suggests qwen3:8b locally, thinking off) |
| Mem0 (2025) | Which existing memories to compare | CS | Embedding top-10 | CODE |
| Mem0 (2025) | ADD / UPDATE / DELETE / NOOP | C1 (+G) | LLM tool call | S1\* only if trained (Memory-R1); untrained small models mis-issue DELETE+ADD; Mem0 itself dropped this step in 2026 |
| Mem0g (2025) | Entity type | C1 | LLM | S1 |
| Mem0g (2025) | Reuse an existing node? | B | Embedding threshold t | CODE |
| Mem0g (2025) | Mark relation invalid? | CS | LLM "update resolver" | S1\* (reasoning-first schema; see Graphiti #1666) |
| Mem0 (2026) | Anything worth storing? | B (implicit) | LLM single-pass extraction may return nothing | S1 |
| Mem0 (2026) | Link to which existing memories | CS | LLM `linked_memory_ids` over top-10 | S1\* |
| Mem0 (2026) | Exact duplicate? | B | CODE: MD5 hash | CODE |
| Mem0 (2026) | Temporal kind / ongoing vs completed | C1 | LLM fields inside extraction | S1\*; date arithmetic in CODE |
| Mem0 (2026) | Supersede an older state? | B | State key + `event_end` closure | CODE rule over S1-proposed keys |
| Mem0 (2026) | Rank decay | SC | CODE: up to ×1.5 recent, down to ×0.3 idle | CODE |
| Graphiti | Extract entities + type id | X+C1 | LLM (main model) | S2, or strong S1\* (docs: avoid small local models) |
| Graphiti | Dedup candidates | CS | Embedding cosine ≥ 0.6, ≤15; plus full-text search | CODE |
| Graphiti | Same entity by exact name? | B | CODE: normalized exact match | CODE |
| Graphiti | Name informative enough for fuzzy match? | B | CODE: length ≥ 6, ≥ 2 tokens, entropy ≥ 1.5 | CODE |
| Graphiti | Fuzzy duplicate? | B | CODE: MinHash-LSH, Jaccard ≥ 0.9 | CODE |
| Graphiti | Which candidate is the duplicate (or −1 = new) | C1 | LLM batched `NodeResolutions` (main model) | **S1\*** (ideal pick-one over ≤15 ids; escalate on near-ties) |
| Graphiti | Extract facts + valid_at / invalid_at | X | LLM (main model) | S2 / S1\*; make all JSON fields required (#1909) |
| Graphiti | Exact duplicate fact? | B | CODE: (source, target, normalized fact) | CODE |
| Graphiti | Which existing facts are duplicates / contradicted | CS×2 | LLM **small model** (`resolve_edge`) | **S1\* only with a reasoning-first schema** (#1666: 7/15 → 14/15) |
| Graphiti | Which contradicted fact expires | B | CODE: valid_at / invalid_at interval rules | CODE |
| Graphiti | Missing timestamps | X | LLM small model | CODE date parser first, S1 fallback (LongMemEval: 8B hallucinated time ranges) |
| Graphiti | Custom attributes | X | LLM small model | S1\* |
| Graphiti | Entity summaries (batch ≤ 30) | G | LLM small model | S1 |
| Zep paper | Missed entities (reflexion)? | B+X | LLM | S1 (gleaning-style); since removed from Graphiti code |
| Zep / Graphiti | Communities | — | CODE: label propagation; LLM summaries | CODE + S2 offline |
| Zep / Graphiti | Rerank retrieved results | SC | CODE: RRF / MMR / mentions / node distance, or a cross-encoder | CODE / S1 (encoder) |
| A-MEM | Note keywords / tags / context | X | LLM | S1 (Llama 3.2 1B at 1.1 s per op) |
| A-MEM | Link to which neighbours | CS | LLM over top-k cosine | S1\* |
| A-MEM | Evolve (rewrite) a neighbour? | B+G | LLM | S1 for the bool; rewrite needs S2 or human approval (drift risk) |
| HippoRAG | OpenIE triples per passage | X | LLM (GPT-3.5 / Llama-3.3-70B) | S2 (heavy); S1 unproven |
| HippoRAG | Synonym edge? | B | CODE: encoder cosine > 0.8 | CODE |
| HippoRAG | Query entities | X | LLM NER | S1 |
| HippoRAG | Graph ranking | SC | CODE: PPR, damping 0.5; node specificity | CODE |
| HippoRAG 2 | Which retrieved triples are relevant | CS | LLM "recognition memory" filter over top-5, with dense fallback | **S1** (low stakes; ablation delta < 1 point) |
| GraphRAG | Were entities missed? (gleaning) | B | LLM yes/no forced by logit bias 100 | **S1** (canonical) |
| GraphRAG | Community structure | — | CODE: hierarchical Leiden | CODE |
| GraphRAG | Community reports | G | LLM | S2 offline |
| GraphRAG | Helpfulness of a partial answer | SC 0–100 | LLM; drop 0; sort | **S1** (canonical) |
| LightRAG | Entity / relation profiling | X | LLM, non-thinking | S2-fast (README: ≥ ~30B-A3B locally) |
| LightRAG | Duplicate entity? | B | CODE: identical names | CODE |
| LightRAG | Low- / high-level query keywords | X-small | LLM, non-thinking | S1 |
| RAPTOR | Cluster membership / number of clusters | CS | CODE: UMAP + GMM + BIC, soft threshold | CODE |
| RAPTOR | Node summaries | G | LLM | S1 / S2 (GPT-3.5: 4% minor hallucinations) |
| ReadAgent | Where to break a page | C1 | LLM picks a numbered tag | **S1** |
| ReadAgent | Which pages to re-read | CS ≤ 6 | LLM | S1\* |
| MemWalker | Navigate: child / revert / answer | C1 + reasoning | LLM (70B) | **Not S1**: 13B failed; reasoning hurt weak models |
| MemoryOS | Promote short → mid term | B | CODE: FIFO at 7 pages | CODE |
| MemoryOS | Which segment a page joins | C1 | CODE: cosine + Jaccard ≥ 0.6 | CODE |
| MemoryOS | Promote / evict segment | B | CODE: heat > 5; lowest heat evicted | CODE |
| MemoryOS | Update 90 user-trait dimensions | X (enum) | LLM | S1\* (enumerated schema) |
| MemOS | Memory type to load (KV / param / text) | C1 | CODE: rules / heuristics | CODE |
| MemOS | Lifecycle state (merge / archive / freeze) | C1 | Policy rules + user action | CODE (+ S1 for "semantic overlap?") |
| Memory-R1 | ADD / UPDATE / DELETE / NOOP | C1 | RL-trained 3B–14B LLM | **S1 when trained** (152 QA pairs) |
| Memory-R1 | Which of ~60 memories to use | CS | RL-trained LLM | S1 when trained |
| Mem-α | Which store + op per chunk | C1 + X | RL-trained Qwen3-4B | **S1 when trained** (0.592 vs GPT-4.1-mini 0.517; untrained 4B 0.389) |
| MemAgent | What to keep in overwrite memory | G | RL-trained 7B/14B | S1/S2 boundary; not auditable |
| LangMem | Hot path or background | C1 | Config | CODE |
| LangMem | Insert / update / delete | C1 | LLM | S1\* (prefer schema'd profiles) |
| LangMem | Procedural prompt edits | G | LLM prompt optimizer | S2 |
| Cognee | Graph extraction | X | LLM structured output (instructor / BAML) | S2, or S1\* with BAML / json_schema |
| LightMem | Keep / drop each token | B per token | LLMLingua-2 encoder, percentile threshold | **S1 (encoder)** |
| LightMem | Topic boundary | B | CODE: attention ∩ similarity boundaries | CODE |
| LightMem | Summarize now? | B | CODE: buffer threshold | CODE |
| LightMem | Merge / update / ignore (offline) | C1 | LLM, sleep-time | S1\* / S2 offline |
| Mastra OM | Observe / reflect now? | B | CODE: token thresholds | CODE |
| Mastra OM | Observation text | G | Fast LLM (Gemini-2.5-flash) | S1-class fast model |
| Nemori | Episode boundary? | B | LLM | S1 |
| Nemori | What is novel vs prediction | G | LLM predict–calibrate | S2 |
| MIRIX | Which memory store(s) | CS | LLM meta-manager | S1\* |
| Hindsight | Retrieval fusion | SC | CODE: RRF over 4 searches + neural reranker | CODE + S1 (encoder) |
| ConvMemory v3 | Is this memory superseded? | B | MiniLM / DeBERTa-v3 heads + evidence gate | **S1 (encoder)**: 95.7% hit@1 (synthetic) |
| Mnemosyne | Substance / redundancy filter | B | Filters + thresholds | CODE / S1 |

**Pattern across the table.**
1. Almost every *structural* decision — thresholds, decay, scheduling, clustering, graph ranking, interval logic — is already **CODE** in the literature.
2. The genuinely model-dependent decisions are **short discrete judgements over a small candidate set**: duplicate id, contradicted indices, relevant subset, yes/no continue, 0–100 helpfulness, importance 1–10, break-point choice.
3. The **generative** steps (extraction, reflection, community/entity summaries, rewrites) are where cost and fragility concentrate.
4. The counter-examples are telling. *Sequential navigation* (MemWalker) and *zero-shot multi-store tool choice* (untrained Qwen3-4B in Mem-α) did not work with small models; *trained* small models (Memory-R1, Mem-α) did.

### 6b. Omnitrix's proposed System-1 decisions, mapped to precedents

| Omnitrix decision | Closest precedents | Recommended split (my synthesis) |
|---|---|---|
| Is this email noise? | Generative Agents importance 1–10; LightMem token and topic filter; Mnemosyne substance filter; Mem0 2026 extraction may return nothing | CODE rules first (sender allow/deny lists, List-Unsubscribe / bulk headers, known automated domains). Then an S1 importance score with two thresholds (drop / keep / escalate). **Always store the raw item** (Zep's non-lossy episodes), so S1 only gates *extraction*, never *storage*. |
| Is this mention the same entity as an existing node? | Graphiti cascade; HippoRAG synonym τ = 0.8; Mem0g node threshold | Graphiti cascade verbatim: embedding candidates → exact → entropy gate → MinHash Jaccard ≥ 0.9 → **S1 pick-one id or −1**. Escalate on near-tied candidates or low confidence. For Indian names and transliterations (e.g., "Sharma ji" vs "R. K. Sharma"), expect the entropy gate to route short names to S1. |
| Does this new fact contradict a stored decision? | Graphiti `resolve_edge` + interval logic; Mem0 2026 state keys; ConvMemory encoder; Memory-R1 | S1\* proposes `contradicted_ids` with a **reasoning-first** schema. CODE decides expiry from valid-times. Contradictions of *decisions / commitments* go to S2 plus a human confirmation card (Historian). Never hard-delete — append-only + invalidate. |
| Does this query need retrieval? | MemGPT tool choice; *Harness the Memory*: over-retrieval harms action | S1 boolean with **default = retrieve** on uncertainty (retrieval is cheap; missing context is expensive). Deterministic overrides: any named entity or date in the query means retrieve. |
| Is this retrieved passage relevant? | HippoRAG 2 recognition filter; GraphRAG helpfulness 0–100; cross-encoder rerankers (Zep, Hindsight) | Encoder reranker first (bge-reranker-v2-m3, as LightRAG recommends). Then an S1 pick-subset over ≤5 short items, with fallback to the top-k dense results if S1 returns nothing. |
| Is this answer supported by its sources? | LoCoMo judge audit: a gpt-4o-mini judge accepted 62.81% of topic-adjacent wrong answers but caught ~89% of specific wrong names/dates | A holistic "supported?" S1 judge will be lenient. Do **claim-level** checks instead: split the answer into atomic claims (names, amounts, dates) and verify each against its cited span with S1 or string/number matching in CODE. (Full treatment belongs to the routing/verification slice.) |
| Does this action need human approval? | MemOS governance metadata (access control, frozen); MemArena: permission-aware access failed universally | CODE policy (Guardian) decides. S1 may only *raise* a flag, never lower one. |

---

## 7. Key takeaways for Omnitrix's design

1. **The premise holds.** Across 25+ systems, structural memory decisions are already code. The remaining model calls are mostly short discrete judgements over small candidate sets (§6), and every System-1 decision Omnitrix proposed has a direct precedent (§6b).
2. **Use a four-step cascade, not a two-way split:** CODE → S1 → S2 → human. Graphiti's entity resolution (embedding candidates → exact → entropy gate → MinHash ≥ 0.9 → small pick-one with −1 = new) is the template to copy. MemoryOS and MemOS show heat, promotion, scheduling and lifecycle can all be code.
3. **Store raw, gate only extraction.** Keep every email/document/message as a non-lossy episode (Zep) that stays BM25 + vector searchable. Extraction recall is <60% for most systems (HaluMem), and graph extraction loses information (Wolff & Bennati). An S1 "noise" mistake must be recoverable, never destructive.
4. **Go append-only and bi-temporal; don't make S1 run UPDATE/DELETE.**
   - Mem0 removed write-time reconciliation in 2026, halving extraction latency. Graphiti lets a small model *flag* duplicates/contradictions but decides expiry with interval code. Updates and conflicts remain the field's weakest category (MemoryAgentBench ≤28% multi-hop; HaluMem omissions).
   - For the Historian: S1 proposes "supersedes/contradicts #k" (reasoning-first schema); CODE sets validity; S2 plus a human confirmation card handles *decisions and commitments*.
5. **Do time in code.** Resolve relative dates against the message timestamp, store event-time metadata at write time (Mem0 2026, Zep), and filter by time ranges deterministically. An 8B model failed at query-time time-range inference (LongMemEval).
6. **Budget ingestion explicitly and make it a demo metric.**
   - Aim for 0 LLM calls on noise (rules + encoder, as in LightMem), at most one extraction call per kept item (Mem0 2026), and S1 calls for each discrete judgement (Graphiti's `small_model`).
   - Report calls, tokens and seconds per ingested email next to a "14B does everything" baseline. Published pipelines range from 1 call per item to ~3 + 2M calls per episode, and from minutes to many hours per corpus (§3).
7. **Give S2 the night shift.** Reflections, entity/"community" summaries, contradiction audits and re-scoring should run at sleep-time (Letta's sleep-time compute and "dreaming", LightMem's offline updates). Trigger them by accumulated S1 importance (Generative Agents' Σ > threshold) or idle time. Keep Letta's "review before applying" step, surfaced as approval cards in Obsidian/Herald.
8. **Retrieval: keep the scoped hybrid design and add the proven pieces:** a temporal filter, RRF fusion and a cross-encoder rerank (Zep, Hindsight, Mem0 2026). Implement "is this passage relevant?" as encoder rerank → optional S1 pick-subset over ≤5 items with a dense fallback (HippoRAG 2). Default "needs retrieval?" to *yes* under uncertainty.
9. **Harden every S1 call with the §5.4 guard-rails.** Small-model memory failures are *silent* by default (#1911, #5998, *Anatomy*). Make write-failure rate and escalation rate first-class dashboard numbers.
10. **Prefer slots to free text for stable facts.** Profiles (LangMem) and enumerated traits (MemoryOS) turn updates into classification, which is ideal for S1. Use free-text collections only for events and notes.
11. **Treat the graph as an index over the vault, not a replacement.** Graph memory helps temporal, preference and multi-hop questions when extraction is good (Zep LongMemEval). But independent 2026 evaluations found Graphiti/Cognee 22–26 points below mem0/plain RAG on LoCoMo (Wolff & Bennati), and Mem0 ≈ RAG at ~50× the cost (MemDelta). Always keep a verbatim fallback path.
12. **Don't chase LoCoMo.** Build a 40–60-question in-house suite over the synthetic businessman's data, modelled on LongMemEval categories (temporal, knowledge-update, multi-session, abstention, preference), plus HaluMem-style write-path metrics (extraction recall, update omission). Include full-context and plain-RAG baselines, a fixed judge, and an adversarial judge check (topic-adjacent wrong answers). This both de-risks the design and makes a convincing demo.
13. **Encoders are System 1 too.** LLMLingua-2 (token filtering), cross-encoders (relevance), MiniLM/DeBERTa heads (supersession, ConvMemory v3) and embedding thresholds (HippoRAG 0.8; Graphiti 0.6 / 0.9) are cheaper than a 1.7B LLM and easier to threshold. Reserve LLM-based S1 for decisions that need language understanding.
14. **Log for the future.** Record every S1 proposal with the final S2/human verdict. Memory-R1 needed only 152 QA pairs for RL, and a trained 4B model beat GPT-4.1-mini on memory construction (Mem-α). Fine-tuning is a roadmap item, not hackathon scope.
15. **Permissions and approvals belong in code.** Permission-aware memory access failed across all backends in MemArena. MemOS-style metadata (origin, access scope, TTL, version chain, "frozen") maps onto Guardian and Auditor. S1 may raise a flag, never clear one.

---

## 8. "Is a sophisticated AI brain essentially a queryable database — or what else is it?" (view from this slice)

- **The substrate is a database** — tables, vectors, graph edges, files. Every system here persists memory somewhere queryable (Postgres/Neo4j/vector stores/git-backed files).
- **What makes it a "brain" is the policy layer around the store:**
  - a *write policy* (what enters, how important it is, how it is typed — Generative Agents, Mem0);
  - a *maintenance policy* (consolidate, invalidate, forget, reflect — often offline; Zep, MemoryBank, Letta sleep-time);
  - a *read policy* (whether to look, where, and what to keep — MemGPT tool choice, HippoRAG 2 recognition filter, ReadAgent lookup);
  - *procedural memory* that changes the agent's own behaviour (LangMem prompt rules; Hu et al.'s "experiential" memory).
- CoALA makes memory writes *learning actions* chosen by a decision cycle; P. Du frames memory as a write–manage–read loop coupled to action.
- **Evidence that the policy, not the store, drives outcomes:**
  - a plain filesystem plus a good agent loop matched specialised memory stores on LoCoMo (Letta);
  - backend choice mattered more than the reader model on-device (MemArena);
  - learned policies beat prompted ones (Memory-R1, Mem-α);
  - offline "thinking" over stored context cut online compute ~5× (sleep-time compute);
  - memory only pays off when it changes actions (MemoryArena; MERIT's 55% act-on-retrieved rate).
- **One-line answer:** a sovereign second brain = a *temporal, provenance-tracked database* + *always-on processes that decide what enters, how it is reorganised, what surfaces, and how it changes behaviour*. The dual-process idea is precisely a proposal for who runs those processes (code, S1, S2, human). The DB-theory and cognitive-science slices can extend this.

---

## 9. Contested / open questions

1. **Leaderboards.** As of Sept 2026 there is no trustworthy cross-vendor LoCoMo ranking. Vendor self-reports (92–95%) sit at or above the audited ceiling (~93.6%); answer and judge models are often undisclosed; independent re-evaluations order systems differently (§4.12).
2. **Where conflicts should be resolved.** Options: at write time with an LLM plus interval code (Zep/Graphiti); append-only with read-time resolution (Mem0 2026); learned write-time ops (Memory-R1); read-time encoder demotion (ConvMemory v3). No controlled head-to-head exists.
3. **Graph vs flat.** Zep and Mem0g report gains on temporal/multi-hop/preference questions; Wolff & Bennati measured 22–26-point *losses* for Graphiti/Cognee vs mem0/RAG (same GPT-4o-mini extraction); results appear to hinge on extraction quality and the backbone.
4. **Untrained 1.7B–4B models on duplicate/contradiction judgements.** I found only anecdotal, small-n evidence (#1666: 15 trials, and on gpt-4.1-nano rather than a local model). No systematic study of memory-specific judgements with local models turned up.
5. **Does reasoning help or hurt small models on these decisions?** A reasoning-first field helped a small non-reasoning model (#1666). Reasoning prompts hurt 13B models in navigation (MemWalker). Qwen3 thinking adds latency. This needs an ablation on Omnitrix's own data.
6. **Calibration of LLM-emitted scores** (importance 1–10, helpfulness 0–100). Memory papers use them raw; none report calibration. This belongs to the routing/calibration slice.
7. **What drove the 2026 vendor jumps** (Mem0 LoCoMo 71.4 → 92.5; LongMemEval 67.8 → 94.4)? The algorithm, the answer model, the judge and the retrieval budget cannot be separated from public information.
8. **Is global structure worth maintaining for personal data?** Community/cluster summaries (GraphRAG, Zep) are expensive to keep fresh (*Are We Ready*, Finding 5; LightRAG's rebuild critique), and their benefit for personal QA is unproven.
9. **Language coverage for an Indian user.** No memory benchmark in this slice targets code-mixed Hindi/English/Kannada chat or Indian name transliteration. One single-author 2026 evaluation of a dense-only memory engine reported weaker results for a low-resource Indic language (Telugu 64.0%) — Kim, S., arXiv:2608.23920 **[preprint]**. Entity resolution for transliterated names is an open risk.

---

## 10. Unverified (not used as fact above, or only with an explicit caveat)
- Date of Mem0's blog "Local AI Agent with Persistent Memory: Mem0, Ollama, Qdrant, and OpenClaw" (the fetch reported 25 Sep 2026, which I could not confirm). The content (qwen3:8b recommendation; `<think>` parsing failure) was read on the page.
- Publication dates on Mem0's "2026 AI Memory Benchmark Guide" page, and third-party figures quoted there (ByteRover's independent Zep 75.1%, ByteRover 92.2–96.1%, Dakera 88.2%, ZeroMemory 96.1%). Not used.
- Cognee: "json_mode 2/5 vs json_schema_mode 5/5 on llama3.1:8b" appeared only in a search snippet, not on a page I fetched. Not used.
- A "2 minutes per item sequential vs ~10 s with a semaphore" Graphiti timing seen in a search snippet (source unclear). Not used.
- *Anatomy* Table 5: the dataset used for the construction-cost numbers is not stated in the table.
- MemoryOS Table 3: whether "calls" and "tokens" are per question, per turn or per conversation is not stated.
- MemOS: exact LoCoMo numbers (only the claim of first place was captured).
- MemoryAgentBench Appendix E.5 (latency and construction-time numbers): not retrieved.
- Zep's 94.7% / 90.2%: answer and judge models are not stated on the product page (a research page is linked but was not fetched).
- A-MEM: whether the "memory evolution" step is one LLM call or one per neighbour. The paper's notation suggests per-neighbour; the reported ~1,200 tokens per operation suggests few calls.
- ACL 2026 demo status of Hindsight: seen in the ACL Anthology listing title (aclanthology.org/2026.acl-demo.27) via search, but the page was not fetched.
- Graphiti default model names (the docstring and issues disagree: gpt-4.1-mini / gpt-4.1-nano vs newer names). Not used.
- LightRAG README model names other than the two sentences quoted in §2.9.
- The exact number of QA pairs in `locomo10.json` (commonly cited as 1,986 including adversarial). Only the 1,540 non-adversarial count is used, as confirmed by three independent sources.
- Emergence AI's 2026 LongMemEval claims (seen only in a Medium post title). Not fetched or used.
- OpenReview record for LightMem (blocked by a bot check; ICLR 2026 acceptance taken from the official repo README instead).

---

## 11. Source index (quick links)
- Surveys:
  - CoALA https://arxiv.org/abs/2309.02427
  - Zhang et al. (TOIS) https://dl.acm.org/doi/10.1145/3748302
  - Wu et al. https://arxiv.org/abs/2504.15965
  - Du et al. https://arxiv.org/abs/2505.00675
  - Hu et al. https://arxiv.org/abs/2512.13564
  - P. Du https://arxiv.org/abs/2603.07670
  - Anatomy https://arxiv.org/abs/2602.19320
  - Are We Ready https://arxiv.org/abs/2606.24775
  - Security survey https://arxiv.org/abs/2604.16548
- Systems:
  - MemGPT https://arxiv.org/abs/2310.08560
  - Sleep-time compute https://arxiv.org/abs/2504.13171
  - Letta docs https://docs.letta.com/guides/agents/architectures/sleeptime
  - Generative Agents https://arxiv.org/abs/2304.03442
  - MemoryBank https://ojs.aaai.org/index.php/AAAI/article/view/29946
  - Mem0 https://arxiv.org/abs/2504.19413 · Mem0 2026 blog https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm · Mem0 source https://github.com/mem0ai/mem0
  - Zep https://arxiv.org/abs/2501.13956 · Graphiti https://github.com/getzep/graphiti · Graphiti issues #868 #1135 #1666 #1909 #1911
  - A-MEM https://arxiv.org/abs/2502.12110
  - HippoRAG https://arxiv.org/abs/2405.14831 · HippoRAG 2 https://arxiv.org/abs/2502.14802
  - GraphRAG https://arxiv.org/abs/2404.16130
  - LightRAG https://arxiv.org/abs/2410.05779 · https://github.com/HKUDS/LightRAG
  - RAPTOR https://arxiv.org/abs/2401.18059
  - ReadAgent https://proceedings.mlr.press/v235/lee24c.html
  - MemWalker https://arxiv.org/abs/2310.05029
  - MemoryOS https://arxiv.org/abs/2506.06326
  - MemOS https://arxiv.org/abs/2507.03724
  - Memory-R1 https://arxiv.org/abs/2508.19828
  - Mem-α https://arxiv.org/abs/2509.25911
  - MemAgent https://arxiv.org/abs/2507.02259
  - LangMem https://langchain-ai.github.io/langmem/concepts/conceptual_guide/
  - Cognee https://github.com/topoteretes/cognee
  - LightMem https://arxiv.org/abs/2510.18866
  - SimpleMem https://arxiv.org/abs/2601.02553
  - Mastra OM https://mastra.ai/research/observational-memory
  - Hindsight https://arxiv.org/abs/2512.12818
  - MIRIX https://arxiv.org/abs/2507.07957
  - Nemori https://arxiv.org/abs/2508.03341
  - ConvMemory v3 https://arxiv.org/abs/2606.26753
  - Mnemosyne https://arxiv.org/abs/2510.08601
  - Mi-Memory https://arxiv.org/abs/2607.18975
- Benchmarks and evaluation:
  - LoCoMo https://arxiv.org/abs/2402.17753
  - LongMemEval https://arxiv.org/abs/2410.10813
  - MemoryAgentBench https://arxiv.org/abs/2507.05257
  - BEAM https://arxiv.org/abs/2510.27246
  - HaluMem https://arxiv.org/abs/2511.03506
  - MemoryArena https://arxiv.org/abs/2602.16313
  - RHELM https://arxiv.org/abs/2605.31086
  - MERIT https://arxiv.org/abs/2609.05441
  - MemArena https://arxiv.org/abs/2608.02613
  - Wolff & Bennati https://arxiv.org/abs/2601.07978
  - MemDelta https://arxiv.org/abs/2606.29914
  - Harness the Memory https://arxiv.org/abs/2608.15008
  - Penfield LoCoMo audit https://penfieldlabs.substack.com/p/we-audited-locomo-64-of-the-answer
  - Zep rebuttal https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/
  - Letta filesystem benchmark https://www.letta.com/blog/benchmarking-ai-agent-memory/
  - Zep product claims https://www.getzep.com/product/agent-memory/
  - Wontopos Tablet 2 https://arxiv.org/abs/2608.23920
