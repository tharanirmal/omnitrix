# Literature review: an efficient, sovereign "second brain" with a fine-tuned System 1

*Compiled 25 Sep 2026 for MSRIT Hackathon, Track 1 (Sovereign AI). Clean-slate: it assumes nothing from the earlier Omnitrix code.*

**The two questions this review answers**

1. *Is a sophisticated AI brain essentially a queryable database — and if not, what else is it?* (§1–§4)
2. *Where can a small, fast "System 1" model do the work — every place where the only thing needed is a **choice, a boolean or a confidence** — and how do we make that trustworthy, cheap and fine-tunable on a laptop?* (§5–§11)

**How it was made.** Eight research slices ran in parallel (A memory systems · B dual-process, routing and calibration · C small models and runtimes · D databases and cognitive science · E controlled execution and security · F product landscape · G fine-tuning · H efficient construction and storage). Every citation was checked against a primary source (arXiv, ACL Anthology, OpenReview, proceedings, official docs, GitHub, gazettes). Claims that could not be checked are listed as unverified in the slice notes and are not relied on here. Product and benchmark claims made by vendors about themselves are marked *self-reported*. One local experiment was run on the target machine (Appendix A). The full notes, with every citation and URL, are in [`notes/`](notes/).

**What building it measured** (25–26 Sep 2026, on the example owner; details in §4.4, §10.5 and §11.6)

- **Search.** Keyword search over a Postgres postings view answers in about 2 ms. Hybrid search takes 28 ms per question, embedding included, and puts the gold email in the top 5 for 78–81% of EnronQA questions.
- **The personal judge.** A 1.7B judge fine-tuned for 54 minutes on the owner's own ground truth beats the zero-shot 14B on all four decisions it learned. On answer-support checks it settles 83% of cases alone at 99.3% accuracy. On the cases it escalates, the 14B is *less* accurate, so those go to the owner.
- **Answering.** The brain answers 70% of held-out questions correctly. When the fine-tuned judge vouches for an answer it is right 84% of the time, otherwise 6% (AUROC 0.92). So System 1 is a reliable check on System 2.
- **The gate.** Code-set tiers, a 14B intent check and owner approval cut WorkBench's harmful side effects from 40% to 6.7%, and raised task success from 38% to 48%. The owner is asked 0.62 times per task. One code-checked fact in the preview (is this address in the directory?) brings harm to 3.3%.
- **Memory** runs end to end, but its uncalibrated gates are not yet selective. That is the next thing to label and calibrate.

**Vocabulary used throughout**

| Tier | What it is | Typical cost on the M5 Pro |
|---|---|---|
| **S0** | Plain deterministic code: parsers, hashes, rules, SQL, graph queries, policies | µs–ms |
| **S1** | A small local model answering with **one token** (a label) plus a probability read from its logits; also cheap embedding heads and nearest-neighbour lookups | ~35 ms (Qwen3-1.7B, measured) |
| **S2** | A large local model (Qwen3-14B) that deliberates or writes | ~0.2 s for a one-token judgement; seconds for prose |
| **H** | The human, reached through an approval channel | minutes, and scarce attention |

---

## Contents

- [0. TL;DR — the findings that shape the design](#0-tldr--the-findings-that-shape-the-design)
- [1. Is an AI brain just a queryable database?](#1-is-an-ai-brain-just-a-queryable-database)
- [2. What cognitive science contributes (as mechanisms, not metaphors)](#2-what-cognitive-science-contributes-as-mechanisms-not-metaphors)
- [3. Agent memory systems: architectures, decisions, costs, benchmarks](#3-agent-memory-systems-architectures-decisions-costs-benchmarks)
- [4. Building the brain efficiently: indexing, graphs, storage, caching](#4-building-the-brain-efficiently-indexing-graphs-storage-caching)
- [5. Dual-process ("System 1 / System 2") AI](#5-dual-process-system-1--system-2-ai)
- [6. Cascades, routers and deferral](#6-cascades-routers-and-deferral)
- [7. Deciding about retrieval and evidence](#7-deciding-about-retrieval-and-evidence)
- [8. Confidence, calibration, abstention and guarantees](#8-confidence-calibration-abstention-and-guarantees)
- [9. Distillation and fine-tuning small models](#9-distillation-and-fine-tuning-small-models)
- [10. The System 1 model zoo and runtime on this Mac](#10-the-system-1-model-zoo-and-runtime-on-this-mac)
- [11. Controlled execution, security and audit](#11-controlled-execution-security-and-audit)
- [12. Sovereignty, privacy and the Indian context](#12-sovereignty-privacy-and-the-indian-context)
- [13. Landscape and prior art: where the white space is](#13-landscape-and-prior-art-where-the-white-space-is)
- [14. Synthesis: design principles for the rebuild](#14-synthesis-design-principles-for-the-rebuild)
- [15. Contested and open questions](#15-contested-and-open-questions)
- [Appendix A. Local System 1 probe on the M5 Pro](#appendix-a-local-system-1-probe-on-the-m5-pro)
- [Appendix B. Research notes index](#appendix-b-research-notes-index)

---

## 0. TL;DR — the findings that shape the design

1. **A brain's long-term memory should literally be a database; the brain is the controller around it.** Language models are poor stores for one person's long-tail facts, and editing facts into weights fails on ripple effects and at scale. The model's job is to read text into rows and to judge fuzzy predicates (§1).
2. **Database research already built System 1 / System 2 with guarantees.** A cheap proxy scores everything, an expensive oracle labels a small sample, and two thresholds give accept / reject / escalate with a precision *or* recall target (NoScope, SUPG, LOTUS, BARGAIN). Safety decisions should be recall-targeted; destructive ones precision-targeted (§1.3).
3. **Across 25+ agent-memory systems, structural decisions are already code; what is left for a model is short discrete judgements over small candidate sets** — duplicate id, contradicted facts, relevant subset, yes/no, importance score. That is exactly the System 1 shape (§3.2).
4. **Ingestion cost is the pain point and the opportunity.** Ten benchmark conversations took 0.9 h with plain retrieval vs 4.4–9.7 h with memory-graph systems, and graph-first systems lost 22–26 accuracy points to extraction errors. Gate before extracting, one extraction per kept item, small models for every discrete follow-up, lazy and localized maintenance (§3.3, §4).
5. **Updates and conflicts are the weakest category everywhere** (1–65% update correctness; ≤28% multi-hop conflict resolution). Store raw items, keep beliefs append-only and bitemporal, let the small model *propose* and code *resolve*, and confirm changed decisions with a human (§3.5–3.6).
6. **Single-token judgements work on the target Mac today.** Ollama returns token logprobs; `qwen3:1.7b` decides in ~35–70 ms; prompt prefixes are cached automatically (§10; Appendix A).
7. **Small instruction-tuned models are badly overconfident zero-shot** (fitted temperatures of 4.5–7.7 on our data). Calibrate per decision type on labelled data, correct label bias, swap order for pairwise questions, escalate on margins, recalibrate after any model change (§8).
8. **Measured on the owner's own data:** on "is this answer supported by the email?", zero-shot `qwen3:1.7b` reached 84.8% accuracy (AUROC 0.93) and `qwen3:14b` 95.2% (AUROC 0.99); at a 95% precision target the 1.7B could settle none of it on its own and the 14B 43% — precisely the gap a fine-tuned judge must close (§10.4).
9. **Fine-tuned small judges beat prompted large ones on narrow decisions** (0.77B relevance evaluator 84.3% vs ChatGPT ≤64.7%; a tuned 1.5B router 93% vs 34% untuned; a trained 4B memory manager beat GPT-4.1-mini). Judge-type decisions distil; multi-step reasoning does not. Fine-tune skills, never facts (§9).
10. **Three of the brain's commonest decisions already exist as trained single-token decisions** — retrieve? relevant? supported? (Self-RAG) — with a three-band evaluator (CRAG) and an honest "not enough evidence" state (Sufficient Context) (§7).
11. **Security: a small model may raise suspicion, never grant permission.** Adaptive attacks beat small injection detectors >90% of the time, and blocking on a detector halved useful work. Typed yes/no outputs cannot smuggle instructions but can be flipped, so `risk tier = max(code, S1, S2)`; spoofing and hidden text are code problems (§11).
12. **Approvals must be bound to the exact action, budgeted, and logged in a hash chain** (users approve 93% of prompts; warnings habituate within a week; tamper-evident logging costs ~48 µs per event) (§11.4–11.5).
13. **Sovereignty is concrete:** zero cloud calls (even careful local–cloud delegation leaks 7.5%), vendor kill-switches are real, and India's DPDP Rules (one-year access logs, 72-hour breach reports, penalties to ₹250 crore from ~May 2027) reward a local, auditable design (§12).
14. **The white space is the combination.** Utopia gates entity merges by confidence with a decision ledger, Claude Code gates actions with a single-token filter, TypeSafe's Jev sells calibrated typed decisions from the cloud — but no one ships one local decision fabric over memory *and* actions, with measured calibration, a user-facing ledger, and a System 1 fine-tuned on one person's own behaviour (§10.3a, §13).

---

## 1. Is an AI brain just a queryable database?

**Short answer: its long-term memory should literally *be* a database — but the brain is the controller around it.** The language model belongs in neither role as the store; its job is to read text into rows and to evaluate fuzzy predicates. The rest of the "brain" is a set of processes a database does not run on its own: deciding what to believe, what matters now, whether it knows something, when to think harder, how to get faster with practice, and when to act.

> **Brain = a database of beliefs** (bitemporal, with provenance and justifications) **+ semantic operators** (LLMs that read, extract and judge) **+ a metacognitive optimizer** (S0/S1/S2/H routing with guarantees) **+ maintenance** (belief revision, consolidation, forgetting, compilation) **+ policy-gated action.**

### 1.1 Why the model must not be the store

| Evidence | What it shows |
|---|---|
| Petroni et al., *Language Models as Knowledge Bases?* (EMNLP 2019, [arXiv 1909.01066](https://arxiv.org/abs/1909.01066)) | BERT-large answers cloze fact probes at P@1 = 32.3 (vs 33.8 for an oracle-linked extractor), dropping to 24.3 on many-to-many relations. Log-probability of the top answer does correlate with correctness — the seed of using logits as a System 1 confidence. |
| Sun et al., *Head-to-Tail* (NAACL 2024, [arXiv 2308.10168](https://arxiv.org/abs/2308.10168)) | LLM factual accuracy collapses from popular ("head") to rare ("tail") entities. |
| Mallen et al., *When Not to Trust Language Models* (ACL 2023, [arXiv 2212.10511](https://arxiv.org/abs/2212.10511)) | Scaling barely helps on the long tail; retrieval-augmented small models beat larger unaugmented ones. |
| Balog & Kenter, *Personal Knowledge Graphs* (ICTIR 2019) | A person's knowledge — their vendors, promises, decisions — is almost entirely tail knowledge. The worst case for parametric memory is the normal case for a second brain. |
| Cohen et al., *Ripple Effects of Knowledge Editing* (TACL 2024, [arXiv 2307.12976](https://arxiv.org/abs/2307.12976)); Gupta et al. (Findings ACL 2024, [arXiv 2401.07453](https://arxiv.org/abs/2401.07453)) | Editing facts into weights does not propagate to related facts (a plain in-context baseline did best), and sequential edits end in catastrophic forgetting. |
| AlKhamissi et al. (2022, [arXiv 2204.06031](https://arxiv.org/abs/2204.06031)) | A knowledge base needs five properties — access, edit, consistency, reasoning, explainability. Databases have them natively; model weights do not. |

**Consequence:** knowledge lives in an explicit, inspectable, deletable store (Lewis et al., RAG, NeurIPS 2020). Fine-tuning is for *skills* (how to judge, how to extract), never for *facts* — see §9.

### 1.2 The database-shaped half: what DB theory already provides

| DB idea | Brain function it supplies |
|---|---|
| Schema, integrity and exclusion constraints | Structured semantic memory with basic consistency |
| Append-only event log / event sourcing (Fowler 2005) | Episodic memory; replay; rebuildable projections |
| Bitemporal data — valid time vs transaction time (Snodgrass 2000; SQL:2011, Kulkarni & Michels 2012) | "When was it true?" vs "when did I learn it?"; audit "as of" any moment |
| Provenance: why/where (Buneman et al. 2001), provenance semirings (Green et al. 2007), W3C PROV (2013) | Source monitoring, citations, confidence propagation through derivations |
| Incomplete/probabilistic databases | Holding alternatives and uncertainty |
| Indexes (B-tree, full-text, vector HNSW) | Retrieval cues |
| Materialized views; triggers; Datalog rules | Consolidated knowledge; reflexes and habits |
| Cost-based query optimizer | Deciding how much effort to spend |
| Access control, row-level security, audit log | Inhibition and executive control |

Two lessons from "neural databases" sharpen this. Thorne et al. (PVLDB 2021; ACL 2021) showed transformers answer select-project-join questions well **only over a small, relevant fact set**, and cannot aggregate — so counts, sums and "which X since Y" must run in SQL, not in the model. Biswal et al., *Text2SQL is Not Enough* (TAG, CIDR 2025, [arXiv 2408.14717](https://arxiv.org/abs/2408.14717)) found standard Text2SQL or RAG answers at most **20%** of queries that need both: retrieve, *execute a query*, then generate. SUQL (Findings NAACL 2024) and BlendSQL (Findings ACL 2024) show the practical form — SQL with LLM functions inside it.

### 1.3 The database community already built System 1 / System 2 — with guarantees

This is the single most useful connection in the review. Database research on expensive predicates has, for a decade, used a **cheap proxy model** to score every item and an **expensive oracle** for the uncertain ones:

| Work | Idea | Reported result |
|---|---|---|
| NoScope (Kang et al., PVLDB 2017) | Specialized cheap models mimic an expensive network; a cascade decides | 265–15,500× faster than real time, within 1–5% of the reference |
| Probabilistic predicates (Lu et al., SIGMOD 2018) | Reusable cheap classifiers drop items that cannot match, each at a target accuracy | up to 10× faster queries |
| SUPG (Kang et al., PVLDB 2020, [arXiv 2004.00827](https://arxiv.org/abs/2004.00827)) | Choose thresholds on proxy scores that meet a **precision target or a recall target** with probability 1−δ, using a small oracle budget | up to 30× better result quality than naive thresholding |
| TASTI (Kang et al., SIGMOD 2022) | One embedding index whose neighbours share oracle labels → proxy scores for *any* predicate | 10× cheaper to build; queries up to 24× faster |
| LOTUS semantic operators (Patel et al., [arXiv 2407.11418](https://arxiv.org/abs/2407.11418)) | `sem_filter` (a boolean), `sem_join` (a pairwise boolean), `sem_topk`… A small model's True/False log-probability is the proxy; two thresholds τ− and τ+ are learned from a small sample labelled by both models; the middle band goes to the big model | up to 1,000× fewer LLM calls on a semantic join |
| BARGAIN (Zeighami et al., SIGMOD 2026, [arXiv 2509.02896](https://arxiv.org/abs/2509.02896)) | Cheap/expensive LLM cascade routed by log-prob confidence, with tighter statistics | up to 86% more cost reduction than prior work **at the same guarantee** |
| ThalamusDB (Jo & Trummer, SIGMOD 2024) | Natural-language predicates in SQL; bounds that tighten as it runs; **asks the user for a few labels**, pricing the human as an oracle | 35× faster than an exact baseline |

The recipe these share (per predicate): label ~100–300 items with the expensive model, choose **τ+** so that precision above it meets a target and **τ−** so that recall below it meets a target, accept above τ+, reject below τ−, escalate the middle. Two caveats matter: the guarantee is *relative to the oracle* (so the oracle itself must be audited against the human on a sample), and it assumes the calibration sample resembles live data (it drifts). **Safety predicates should be recall-targeted** ("never miss a needed approval"); **destructive predicates should be precision-targeted** ("never wrongly merge two people").

### 1.4 What a brain adds beyond a database

1. **Perception.** A database assumes rows arrive clean; a brain must *make* rows from prose and grow its schema (Extract-Define-Canonicalize, EMNLP 2024; KGGen, 2025).
2. **Fuzzy predicates.** "Relevant", "same person", "contradicts", "supported" have no SQL definition; they are learned, priced, uncertain operators — every answer needs a confidence.
3. **Belief revision instead of write rejection.** A database rejects writes that violate constraints; a brain must *accept* conflicting evidence, keep alternatives and revise minimally (Doyle's TMS 1979; de Kleer's ATMS 1986; AGM 1985 — §2).
4. **Need-driven availability.** Rows are equally available; memories are not — availability tracks recency, frequency and context (Anderson & Schooler 1991).
5. **Metacognition.** A query optimizer estimates *cost*, never *probability of being right*. A brain knows whether it knows before searching, and decides whether to retrieve, compute, escalate or ask.
6. **Learning that rewrites its own fast paths.** Practice turns deliberation into retrieval and rules (Logan 1988; ACT-R; Soar).
7. **Consolidation.** Offline replay turns episodes into gist and schemas.
8. **Agency.** A database never acts; a brain acts under policy, and must reconcile actions already taken on beliefs later revised.

**The link between the two questions:** items 2–6 are made almost entirely of *fuzzy yes/no, pick-one and how-confident judgements*. A database answers queries; a brain makes judgements — and most of those judgements are exactly the System 1 shape. That is the thesis of the rest of this review.

---

## 2. What cognitive science contributes (as mechanisms, not metaphors)

| Principle (source) | Mechanism it gives the brain |
|---|---|
| **Episodic vs semantic memory** (Tulving 1972; 2002) | Two stores: an append-only log of events (who, when, source) and distilled semantic facts that link back to them. Answers cite episodes; plans use facts. |
| **Complementary learning systems** (McClelland, McNaughton & O'Reilly 1995; Kumaran, Hassabis & McClelland 2016) and **sleep consolidation** (Klinzing et al. 2019) | Fast capture during the day, slow structured updates in batches. *Schema-consistent* facts (a new invoice from a known vendor) may be written straight to semantic memory by S1; *schema-violating* ones (a new bank account, a contradiction) stay episodic until S2 or the human confirms. A nightly "sleep" job replays, deduplicates, summarizes and recalibrates. |
| **Memory tracks the statistics of need** (Anderson & Schooler 1991 — one of their three datasets was the author's *email senders*) | Salience should decay as a power law of recency and grow with frequency; context packs should add items in order of need and **stop when the expected gain falls below the token cost**. |
| **ACT-R base-level activation** (Anderson et al. 2004; Petrov 2006; Derbinsky & Laird 2012) | Per item: `B = ln Σ t_j^(−0.5)` over past uses, computable in O(1) with Petrov's approximation. Items below a threshold are *archived, never deleted*; predict each item's decay time and index it. Pin anything with a future deadline. |
| **Spreading activation** (Collins & Loftus 1975) | "Find the entities in the question, then search what is linked to them" is one-hop spreading activation; extend to bounded two hops with fan attenuation so hubs (the user themself) don't flood results. |
| **Instance theory of automaticity** (Logan 1988) | Automaticity is *retrieval of stored past decisions*, racing against computation. Cache every S2 decision; S1's first move is to look up near-identical past cases. S2 calls should fall as a power law with use — a plottable demo metric. |
| **Production compilation / chunking** (Taatgen & Lee 2003; Laird, Rosenbloom & Newell 1986) and **CLARION** (Sun et al. 2005) | Repeated S2 resolutions become explicit, human-approvable rules conditioned on the features that mattered; conversely, mine S1's behaviour into readable rules. |
| **Dual-process debate** (Evans & Stanovich 2013; Kruglanski & Gigerenzer 2011) | S1 answers by default, S2 *intervenes*. But deliberation is not generally more accurate — route by **measured** per-decision accuracy, not by the assumption that the big model is always right. |
| **Margin-based switching** (De Neys, *BBS* 2023) | System 1 produces competing intuitions; escalate when the **gap between the top two** is small, and stop deliberating once it widens. For a choice, use `p(top1) − p(top2)`, not raw confidence. |
| **Monitoring and control** (Nelson & Narens 1990) | The architecture of a router: signals flow up (margins, familiarity, calibration, escalation rates); a meta-level policy decides retrieve / escalate / stop / ask. |
| **Feeling of knowing from cue familiarity** (Reder & Ritter 1992; Schunn et al. 1997) and **accessibility** (Koriat 1993) | A *pre-retrieval* gate with no model call: familiarity of the question's entities **and relations**, from activation, decides fast path vs deep search vs "I don't have this yet". Familiar entities with an unfamiliar relation are a known trap. After retrieval, the amount and agreement of evidence is a second, fallible signal. |
| **Feeling of rightness** (Thompson et al. 2011) | Low initial confidence predicts rethinking and answer changes — log how often S2 overturns S1 per confidence bin; that is the gate's calibration curve. |

---

## 3. Agent memory systems: architectures, decisions, costs, benchmarks

### 3.1 The shared shape

Surveys converge: memory is **a substrate plus policies over a write → manage → read loop** (CoALA, Sumers et al., TMLR 2024, [arXiv 2309.02427](https://arxiv.org/abs/2309.02427); Du et al.'s six operations — consolidation, updating, indexing, forgetting, retrieval, condensation, [arXiv 2505.00675](https://arxiv.org/abs/2505.00675); Hu et al., *Memory in the Age of AI Agents*, [arXiv 2512.13564](https://arxiv.org/abs/2512.13564)). CoALA's split of long-term memory into **episodic** (experiences), **semantic** (facts) and **procedural** (skills) is the working vocabulary. The field's trend runs from hand-set heuristics → prompted LLM judgements → **learned policies** — while 2026 evaluations show the prompted middle stage is fragile on small models.

### 3.2 What the main systems actually decide, and how

| System | Pipeline in one line | Discrete decisions inside | Who decides them |
|---|---|---|---|
| **MemGPT → Letta** (Packer et al. 2023; *Sleep-time Compute*, Lin et al. 2025, [arXiv 2504.13171](https://arxiv.org/abs/2504.13171)) | Editable core memory + recall + archival stores moved by tool calls; 2026: git-backed memory filesystem and background "dreaming" | save? which tool? keep chaining? when to consolidate? | Model for the first three; **code** for pressure thresholds and dream triggers. Sleep-time compute: ~5× less test-time compute at equal accuracy. |
| **Generative Agents** (Park et al., UIST 2023) | Memory stream; retrieval = recency + importance + relevance; reflection when Σimportance > 150 | importance 1–10 per observation; react? | Model rating — **the archetypal System 1 score**; triggers in code. Cost: "thousands of dollars" for 25 agents × 2 days. |
| **Mem0** (Chhikara et al. 2025, [arXiv 2504.19413](https://arxiv.org/abs/2504.19413)) | 2025: extract facts, then per fact choose **ADD / UPDATE / DELETE / NOOP** against 10 similar memories. **2026 (verified in code): one ADD-only extraction call**, temporal metadata ("state keys" close superseded states), conflicts resolved at read time | anything to store? which memories to link? | Model extracts; **code** handles duplicates (hash), supersession (state closure) and decay (×1.5 recent to ×0.3 idle at search time). Mem0 says dropping the reconcile pass "roughly halved" extraction latency. |
| **Zep / Graphiti** (Rasmussen et al. 2025, [arXiv 2501.13956](https://arxiv.org/abs/2501.13956); code inspected Sep 2026) | Episodes (raw, non-lossy) → entities → bitemporal fact edges → communities | **Entity resolution cascade:** embedding candidates (cos ≥ 0.6, ≤15) → exact name → entropy gate → MinHash Jaccard ≥ 0.9 → **one batched model call picking a candidate id or −1 ("new")**. **Edges:** a *small-model* call returns duplicate and contradicted fact indices; **which fact expires is decided by interval code**. | ~3–4 + M to 3–4 + 2M model calls per episode with M facts. A small non-reasoning model got contradiction detection right 7/15 times, and 14/15 with a **reasoning-first** output schema (graphiti #1666 — small n). |
| **A-MEM** (Xu et al., NeurIPS 2025) | Zettelkasten notes; link to top-k neighbours; "evolve" neighbours | link which? rewrite a neighbour? | ~1,200 tokens/op; **1.1 s per op with a local Llama 3.2 1B** vs 5.4 s with GPT-4o-mini. Rewrites risk silent drift. |
| **HippoRAG / HippoRAG 2** (NeurIPS 2024; ICML 2025, [arXiv 2502.14802](https://arxiv.org/abs/2502.14802)) | OpenIE triples + synonym edges (cos > 0.8) + Personalized PageRank; v2 adds a "recognition" filter over the top-5 triples | relevant subset of ≤5 triples | Model filter with a dense fallback (removing it costs <1 point) — a clean S1 pattern. |
| **GraphRAG** (Edge et al. 2024) | Entity/claim extraction, Leiden communities, community reports | "did we miss entities?" — **yes/no forced by a logit bias of 100**; helpfulness 0–100 per partial answer | Both canonical S1 judgements, inside a flagship system. |
| **LightRAG** (Guo et al. 2024) | Entity/relation profiling; dual-level keywords; incremental union | — | README: locally, Qwen3-30B-A3B-Instruct is "a reasonable minimum" for extraction; use a **non-thinking** model for extraction, thinking only for answers. |
| **RAPTOR** (ICLR 2024); **ReadAgent** (ICML 2024) | Recursive summary tree; gist memory with page lookup | pick a page break from numbered tags; pick ≤6 pages to re-read | Numbered-option prompts are ideal S1 formats. |
| **MemWalker** (Chen et al. 2023) | Navigate a summary tree step by step | child / revert / answer | **Counter-example:** 13B models failed, and asking them to reason first made them worse — keep S1 to single-shot, locally checkable decisions. |
| **MemoryOS** (EMNLP 2025); **MemOS** (2025) | Heat-based promotion/eviction; lifecycle states with versioning and "frozen" items | segment assignment, promotion, eviction, lifecycle | Almost all **code** (scores and thresholds); a fixed 90-dimension user-trait profile turns updates into classification. |
| **Memory-R1** ([arXiv 2508.19828](https://arxiv.org/abs/2508.19828)); **Mem-α** ([arXiv 2509.25911](https://arxiv.org/abs/2509.25911)) | RL-trained memory managers | ADD/UPDATE/DELETE/NOOP; which store and operation | Memory-R1 learned from **152 QA pairs** (3–14B). Mem-α's **trained Qwen3-4B** scored 0.592 vs GPT-4.1-mini 0.517 — and the *untrained* 4B only 0.389. **Small models can own these choices after training, not before.** |
| **LightMem** ([arXiv 2510.18866](https://arxiv.org/abs/2510.18866), ICLR 2026) | A small **encoder** (LLMLingua-2) drops low-value tokens before any LLM call; cheap online inserts; merge/update/ignore consolidation offline | keep/drop per token; merge/update/ignore | Up to 38× fewer tokens and 30× fewer calls than A-MEM/Mem0/MemoryOS/LangMem, with +2–6% accuracy — the clearest published *encoder-level System 1 gate*. |
| **ConvMemory v3** (2026 preprint) | "Is this memory superseded?" | bool | Small encoder heads with an evidence gate: current-state hit@1 45% → 96% on synthetic + transfer data. |

**The pattern across 25+ systems:** structural decisions — thresholds, decay, scheduling, clustering, graph ranking, interval logic — are already **code**. What remains for a model is **short discrete judgements over a small candidate set** (duplicate id, contradicted indices, relevant subset, yes/no continue, importance 1–10, helpfulness 0–100). Cost and fragility concentrate in the *generative* steps (extraction, summaries, rewrites).

### 3.3 Ingestion cost — the strongest argument for System 1

| Evidence | Cost |
|---|---|
| Wolff & Bennati (2026, [arXiv 2601.07978](https://arxiv.org/abs/2601.07978)) — 10 LoCoMo conversations, GPT-4o-mini | **4.4 h mem0 · 9.7 h Graphiti · 8.4 h Cognee · 0.9 h plain RAG**; accuracy mem0 81.1%, RAG 78.3%, full-context 77.2%, **Graphiti 56.0%, Cognee 55.3%** (information lost in extraction); only RAG and mem0 were Pareto-optimal |
| HippoRAG 2 indexing table (11,656 passages, Llama-3.3-70B) | tokens per passage ≈ 1.0k (HippoRAG 2) · 0.16k (RAPTOR) · 7.5k (LightRAG) · 13k (GraphRAG) |
| *Anatomy of Agentic Memory* (2026, [arXiv 2602.19320](https://arxiv.org/abs/2602.19320)) | 0.6–15 h and 1.3–7.0M tokens to build memory; a 32 s user-facing query latency (MemoryOS) |
| *Are We Ready for an Agent-Native Memory System?* (2026, [arXiv 2606.24775](https://arxiv.org/abs/2606.24775)) | memory-operation latency per query 3.7 s (LightMem) → 155 s (Zep); **localized maintenance gives the best cost-utility**; global reorganization dominates cost |
| HaluMem (2025) | adding one dataset took 273 min (Supermemory) to 2,768 min (Mem0) |

The published levers are orthogonal and stack: **gate before extraction** (encoder or S1), **one extraction call per kept item**, **route every discrete post-extraction judgement to S1**, **push consolidation to sleep-time**, **never recompute globally**.

### 3.4 Small local models fail silently — and how to guard them

- Structured-output "format errors" during memory writes: 4.8% (SimpleMem) and **30.4% (Nemori)** on a 3B backbone vs 1.2%/17.9% on GPT-4o-mini; the agent keeps chatting fluently while its memory is corrupted (*Anatomy*).
- GitHub issue evidence: schemas echoed back instead of data, optional fields skipped under constrained decoding (gemma3:12b omitted `valid_at` on 10/40 edges; with every field required, 0/72), `<think>` tags breaking parsers, prose around JSON, 10-minute silent retry storms, episodes dropped with "success".
- Worked with small models: write-time fact extraction (8B), note linking (1B), routing (3B), on-device reading with a good backend (0.6B), and **trained** memory managers. Failed: query-time *time-range* inference (8B), multi-step navigation (13B), zero-shot multi-store tool use (untrained 4B).
- **Guard-rails:** ask for ids/enums/booleans, never open JSON; make every field required; put a one-line reason first for relational judgements; disable thinking; validate → retry once → dead-letter queue with a visible alert; keep candidate sets ≤15 (matching) or ≤5 (relevance); track parse-failure, escalation and S1–S2 agreement rates.

### 3.5 Benchmarks — and why not to chase LoCoMo

| Benchmark | What it stresses | Headline |
|---|---|---|
| DMR (MemGPT) | single-fact recall | Saturated (full context 98%) |
| LoCoMo (Maharana et al., ACL 2024) | long conversations; temporal, adversarial | Human temporal F1 92.6 vs model 20.3 (2024). **An audit found 6.4% of the answer key wrong and a judge accepting 62.8% of topic-adjacent wrong answers → ceiling ≈ 93.6%**, below some vendor claims (Mem0 92.5, Zep 94.7, *self-reported*) |
| LongMemEval (Wu et al., ICLR 2025) | extraction, multi-session, **temporal**, **knowledge updates**, **abstention** | Fact-augmented keys extracted **by an 8B model** helped (+9.4% recall), but the 8B **could not infer time ranges** at query time → do time in code |
| MemoryAgentBench (Hu et al., ICLR 2026) | retrieval, test-time learning, long-range understanding, **conflict resolution** | Multi-hop conflict resolution: best 28%, most 1–7%; single-hop fact consolidation: memory systems 7–28 vs long-context up to 78 |
| HaluMem (2025) | extraction, **update**, QA separately | Extraction recall <60% for most; **update correctness 1–65%**, failures mostly *omissions* |
| BEAM (ICLR 2026) | up to 10M-token conversations | Genuinely exceeds context windows |
| MemoryArena (ICML 2026), MERIT (2026), RHELM (2026), MemArena (2026) | using memory to *act*; multi-source (email + documents); on-device | Agents acted on correctly retrieved values only **55%** of the time; multi-source aggregation is the weakest skill; on-device, **the memory backend mattered more than a bigger reader model**, and permission-aware access failed everywhere |

**What the benchmarks say matters most:** temporal reasoning; knowledge updates and conflicts; multi-session and multi-source aggregation; abstention ("I have no record of that"); extraction recall (keep raw episodes as ground truth); using memory to act; and cost. **Evaluation hygiene:** fix and disclose answer and judge models, include full-context and plain-RAG baselines, adversarially test the judge, and report ingestion calls, tokens and time.

### 3.6 Implications

1. **Store raw, gate only extraction.** Keep every item as a non-lossy, searchable episode; a System 1 "noise" call should decide what gets *extracted*, never what gets *kept*.
2. **Append-only and bitemporal; S1 proposes, code resolves.** S1 flags "duplicate of #k / contradicts #k" (reasoning-first); interval code decides validity; decisions and commitments go to S2 plus a human card.
3. **Do time in code.**
4. **Prefer slots to free text for stable facts** (profiles and enumerated traits turn updates into classification).
5. **Treat the graph as an index over the episodes, not a replacement** — graph extraction loses information; always keep a verbatim fallback.
6. **Log every S1 proposal with its final verdict** — Memory-R1 needed only 152 examples; the log *is* the training set.

---

## 4. Building the brain efficiently: indexing, graphs, storage, caching

*The dedicated efficiency research slice (H) was interrupted twice; this section draws on slices A and D, verified tool documentation, and our own measurements on the target machine (marked **measured**).*

### 4.1 Where the cost goes, and the levers that cut it

Published pipelines differ by more than an order of magnitude in what they spend per ingested item (§3.3): from **one model call per item** (Mem0's 2026 single-pass extraction) to **~3 + 2M calls per episode with M facts** (Graphiti), and from **≈0.16k tokens per passage** (RAPTOR) to **≈13k** (GraphRAG) on the same corpus (HippoRAG 2's indexing table). Ten LoCoMo conversations took **0.9 h with plain RAG vs 4.4–9.7 h** with memory-graph systems — while the graph systems also *lost* 22–26 accuracy points to extraction errors (Wolff & Bennati 2026). The levers that recur across the evidence:

| Lever | Evidence | What it means for the build |
|---|---|---|
| **Do structural work in code** | Across 25+ memory systems, thresholds, decay, clustering, graph ranking and interval logic are already code (§3.2) | Parsing, deduplication, threading, time, and permissions cost no model calls |
| **Store raw once; derive everything else** | Zep keeps non-lossy episodes; extraction recall is below 60% for most systems (HaluMem) | Raw items are the ground truth; derived facts and summaries can be rebuilt and are never the only copy |
| **Gate before extracting** | LightMem's small encoder gate cut calls up to 30× and tokens up to 38× with *higher* accuracy | A one-token System 1 "worth remembering?" before any generation |
| **One extraction call per kept item; S1 for every discrete follow-up** | Mem0 2026; Graphiti's `small_model` slot | Generation only where a label cannot do the job (§5 of the design) |
| **Localized, lazy maintenance** | *Are We Ready…* (2026): localized maintenance gives the best cost–utility; global reorganization dominates cost; LightRAG's critique of GraphRAG's rebuilds | No eager global graph or community summaries; per-entity work at sleep-time |
| **Reuse compute** | Automatic prefix caching (§10.1: ~100 ms → ~35 ms per decision); the ledger as a cache of past judgements (§2, Logan) | Put stable text first in prompts; never score the same prompt twice |

### 4.2 Postgres as the single store

Everything above fits in one Postgres database with the pgvector extension (0.8.6 in the `pgvector/pgvector:pg17` image, **measured**): relational rows for items and facts, a generated `tsvector` column with a GIN index for keyword search, a `halfvec(1024)` column (half the storage of 32-bit vectors) with an HNSW index for meaning search, and filtered vector search that keeps scanning until enough rows pass the filter (`hnsw.iterative_scan`, pgvector ≥ 0.8). Time-validity constraints for beliefs can be expressed on PG17 with `tstzrange` columns and `EXCLUDE USING gist` (PG18 adds native `WITHOUT OVERLAPS`; LR notes D). Keyword and meaning results are fused with reciprocal rank fusion; the fusion constant is tuned on EnronQA (§4.4) rather than assumed.

One operational trap, **measured**: a parallel HNSW build asks for shared memory sized to `maintenance_work_mem`, and Docker's default 64 MB `/dev/shm` makes it fail with "No space left on device" — set `shm_size` on the container.

### 4.3 Graph: lazy, not eager

The strongest evidence says to treat the graph as an **index over the raw items**, not a replacement: graph-first systems lost 22–26 points to extraction losses on LoCoMo (Wolff & Bennati 2026), Mem0 dropped graph memory from its open-source release (§13.2), and whole-graph reorganization dominates maintenance cost (*Are We Ready…*). What an email brain gets almost for free is a *people graph* (who wrote to whom, when — derived by SQL from headers), threads (normalized subjects), and the owner's own folder taxonomy. Entity and relation extraction is worth doing only for the facts that drive decisions and actions — commitments, decisions, meetings — and only for items that pass the System 1 gate.

### 4.4 Measured on this machine (Kaminski mailbox, M5 Pro)

| Step | Result |
|---|---|
| Ingest (parse, split quoted history, dedupe, thread, chunk, COPY) | 28,465 files → **11,528 unique items** (2.5× duplication across folders), 5,436 sent by the owner, **19,233 chunks, in 2.8 s** — no model calls |
| Embedding (bge-m3 via Ollama) | 19,233 chunks, all embedded in one resumable pass |
| HNSW build (halfvec, m=16, ef_construction=64) | **< 2 s**, 49 MB; whole database 195 MB |
| Keyword search (BM25 over a postings view, 1.2M rows, 112 MB) | **1.9 ms** median, 3.5 ms p90, 6 ms worst (200 EnronQA questions); 17–25 ms with people/time filters. The first version, which unnested every candidate chunk's vector, took 67 ms median and 353 ms worst |
| Hybrid search (warm) | **28 ms** per question on average, embedding it included (500 EnronQA questions in 14 s) |
| Adding an item (round 2) | searchable **13 ms** after it arrives. Postings became a table updated per new chunk, instead of a view rebuilt in ~3 s, with document frequencies for brand-new words counted on the fly. Turning off Postgres' JIT compiler, which cost ~15 ms per millisecond-scale query, kept keyword search at 2 ms |

**Retrieval quality, measured** (EnronQA questions about the owner's own emails; the exact gold email must be found; two independent samples of 500 questions):

| Search | Recall@1 | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|
| Postgres full text, `ts_rank_cd` (no IDF) | 0.196 | 0.384 | 0.468 | 0.286 |
| **BM25 in SQL** (IDF from `ts_stat`, k1 = 1.2, b = 0.75) | 0.478 / 0.518 | 0.764 / 0.786 | 0.828 / 0.842 | 0.598 / 0.636 |
| BM25 over postings (document length in words, not distinct words) | 0.488 | 0.766 | 0.828 | 0.608 |
| Dense (bge-m3, halfvec HNSW) | 0.348 / 0.408 | 0.622 / 0.678 | 0.708 / 0.740 | 0.467 / 0.523 |
| Hybrid, standard RRF (k = 60, equal weights) | 0.404 / 0.442 | 0.752 / 0.784 | 0.838 / 0.860 | 0.550 / 0.589 |
| **Hybrid, engram** (k = 5, meaning weight 0.5) | **0.482 / 0.522** | **0.786 / 0.812** | **0.850 / 0.862** | **0.608 / 0.646** |
| Hybrid, engram, on postings BM25 (first sample) | 0.484 | 0.784 | 0.852 | 0.611 |

Three lessons. Postgres' built-in ranking has no inverse document frequency, so the owner's own name (in nearly every email) swamped the query; BM25 more than doubled recall@1. And on personal email, lexical matching is the stronger signal (names, project codes, amounts) — consistent with EnronQA's own finding that BM25 retrieval is strong on this corpus — so fusion should weight it more than the standard equal-weight RRF does. And an inverted index makes lexical search nearly free: a `(word, chunk, count, length)` materialized view, refreshed after ingest, lets a query read only its own words' postings, about 35× faster. One trap: the driver prepares a statement after a few runs, and Postgres' generic plan can't see which words the query holds, so it scans every posting (~150 ms). The keyword query is therefore never prepared.

---

## 5. Dual-process ("System 1 / System 2") AI

| Work | Mechanism | Result | Take-away |
|---|---|---|---|
| **SOFAI** — Booch et al., *Thinking Fast and Slow in AI* (AAAI 2021, [arXiv 2010.06002](https://arxiv.org/abs/2010.06002)); Ganapini et al., *npj AI* 2025; SOFAI-LM ([arXiv 2508.17959](https://arxiv.org/abs/2508.17959)) | Fast solvers return a decision + confidence; a **metacognitive arbiter in code** accepts S1 only if (a) it has enough experience in this situation, (b) results are on track, (c) confidence clears a threshold; otherwise it calls S2 only if S2's expected gain justifies its cost. SOFAI-LM first retries S1 with targeted feedback and examples. | Usage shifts from mostly S2 to mostly S1 as experience accumulates; faster than S2 alone. | Keep per-decision **experience counters**; don't trust S1 on a decision type until it has N audited cases. |
| **SwiftSage** (Lin et al., NeurIPS 2023, [arXiv 2305.17390](https://arxiv.org/abs/2305.17390)) | A 770M fast model plus GPT-4; hand over on **rule triggers** — stuck, invalid output, critical step, surprising observation. | 84.7 vs ≤45.3 on ScienceWorld; ~757 vs ~1,971–2,983 tokens per action. | Escalation need not be only confidence-based — deterministic triggers are cheap and explainable. |
| **Talker–Reasoner** (Christakopoulou et al., 2024, [arXiv 2410.08328](https://arxiv.org/abs/2410.08328)) | Fast "talker" answers from current beliefs; slow "reasoner" plans and writes updated beliefs back. | Architecture paper. | Decouple perceived latency from deliberation: answer from memory now, refine in the background. |
| **System-1.x** (Saha et al., ICLR 2025, [arXiv 2407.14414](https://arxiv.org/abs/2407.14414)) | A controller labels sub-goals easy/hard, routing to fast or search planners; labels come from an automatic hardness function. | Up to +33 points over either planner alone at equal budget. | A difficulty router can be trained from **automatically derived labels**; expose a deliberation-budget knob. |
| **Distilling System 2 into System 1** (Yu et al., 2024, [arXiv 2407.06023](https://arxiv.org/abs/2407.06023)) | Run expensive reasoning on unlabelled inputs, keep consistency-filtered outputs, fine-tune to answer directly. | An LLM-as-judge went from 28.1% to **72.4%** human agreement using **4 output tokens** (the slow method it distilled used ~2,064); position inconsistency 80.9% → 9.1%. Chain-of-thought *arithmetic* did **not** distil (7.1% vs 52.8%). | **Judge-type decisions distil well; multi-step reasoning does not.** This is the empirical basis for a fine-tuned System 1 judge. (Shown at 70B — must be re-validated at 1–4B.) |
| **Learning when to think** — Thinkless (NeurIPS 2025), AdaptThink (EMNLP 2025), LHRM (NeurIPS 2025) | RL teaches a model to choose thinking vs direct mode. | 50–90% less long-chain thinking on maths sets. | Possible, but needs RL on the model; for a hackathon, make the when-to-think decision *outside* the model. |
| **Qwen3 hybrid thinking and the 2507 split** (Qwen3 Technical Report, [arXiv 2505.09388](https://arxiv.org/abs/2505.09388)) | One checkpoint with thinking/non-thinking modes; in July 2025 Qwen shipped separate Instruct and Thinking checkpoints instead. | Qwen3-4B IFEval 81.2 non-thinking vs 81.9 thinking; thinking matters for maths/GPQA, not instruction following. A 2026 study documents reasoning "leaking" into no-think mode. | Run S1 **non-thinking**, cap output tokens, and use checkpoints that honour it (see §10: the installed `qwen3:4b` does not). |
| **GPT-5 as a routed system** (OpenAI system card, 2025) | A fast model, a thinking model and a real-time router trained on user switches, preferences and measured correctness. | — | The headline industry precedent for a router that **learns from user feedback**. |
| **Claude Code auto mode** (Anthropic Engineering, 25 Mar 2026) | Stage 1: a **single-token** block/allow filter tuned to over-block; stage 2: chain-of-thought only when stage 1 flags. | Real-traffic false positives 8.5% → **0.4%** end-to-end; but misses on real overeager actions rose 6.6% → **17%**; users approved 93% of prompts. | Production evidence that single-token S1 + selective S2 works — and that letting S2 *overturn* S1 trades false alarms for misses. |

Surveys: *From System 1 to System 2: A Survey of Reasoning LLMs* (Li et al., IEEE TPAMI 2026, [arXiv 2502.17419](https://arxiv.org/abs/2502.17419)); *Metacognition in LLMs* (Liu et al., 2026, [arXiv 2607.11881](https://arxiv.org/abs/2607.11881)).

---

## 6. Cascades, routers and deferral

What decides escalation, and what it saves:

| Work | Escalation signal | Reported result |
|---|---|---|
| FrugalGPT (Chen et al., TMLR 2024) | A separate learned scorer of (query, answer) | Matches the best single model at up to 98% lower cost |
| AutoMix (Aggarwal, Madaan et al., NeurIPS 2024) | Small model self-verifies k times; a POMDP treats that as a *noisy* observation | >50% cost reduction; self-verification alone is poorly calibrated |
| Mixture-of-thought cascades (Yue et al., ICLR 2024) | Agreement among several cheap samples | GPT-4-level quality at 40% of its cost |
| Hybrid LLM (Ding et al., ICLR 2024) | An encoder predicts, *before generating*, whether the small model will suffice | Up to 40% fewer large-model calls, no quality loss; router latency 36 ms |
| RouteLLM (Ong et al., ICLR 2025) | Routers trained on preference data, incl. similarity-weighted ranking over past cases | >2× cost reduction; transfers to new model pairs |
| Cache & Distil (Ramírez et al., Findings ACL 2024) | A student retrained continuously on the big model's labels; **margin sampling** chooses what to escalate | Margin sampling and query-by-committee win consistently; student robust to label noise |
| Online Cascade Learning (Nie et al., ICML 2024) | Logistic regression → BERT → LLM, with learned deferral, trained online | LLM-level accuracy at up to 90% lower inference cost |
| Token-level deferral (Gupta et al., ICLR 2024) | Quantiles of token uncertainty, not sequence probability (length-biased) | Learned rules beat simple aggregation |
| Cascade routing (Dekoninck et al., ICML 2025) | Decide at each step which model to call next | Beats routing or cascading alone; **quality estimators are the critical factor** |
| Self-REF (Chuang et al., ICML 2025) | LoRA-train the small model to emit a confidence token after its answer | Routing 39% of queries matched sending all to a 70B model |
| Gatekeeper (Rabanser et al., NeurIPS 2025) | Fine-tune the small model to be confident when right and uniform when wrong | Better deferral across encoder, decoder and enc-dec models |
| **Cascaded LMs for human–AI decisions** (Fanconi & van der Schaar, NeurIPS 2025, [arXiv 2506.11887](https://arxiv.org/abs/2506.11887)) | Small → large → **human**; confidence = P(YES)/(P(YES)+P(NO)), calibrated by Bayesian logistic regression on **100 samples**; thresholds updated online from human feedback | Better accuracy per cost on most benchmarks; no help where confidence was poor |
| Arch-Router (Tran et al., 2025) | A 1.5B model fine-tuned to map requests onto natural-language routing policies | 93.2% routing accuracy vs Claude-3.7-Sonnet 92.8%; 51 ms vs 1,450 ms; the *untuned* base scored 34.4% turn-level |
| Agreement-based cascading (Kolawole et al., TMLR 2025) | Escalate when a small ensemble disagrees | 2–25× lower cost per request |
| 2026: Bouchard ([arXiv 2605.06350](https://arxiv.org/abs/2605.06350)); Mahmood (ICLR 2026); CascadeDebate; Signed Rescue Routing; *Forced Deferral* | Decision-theoretic analyses; escalate where the big model is predicted to *fix* (not break) the answer; adversarial inputs can force escalation | A pre-generation router beat the best cascade on 4 of 5 datasets because cascades pay for the cheap generation first |

**Take-aways.** (1) For **label-sized** decisions the cascade tax is one token, so "try S1, escalate the middle band" is cheap; for **long generations**, route *before* generating. (2) The fanciest routing logic matters less than **well-calibrated quality estimates** (Dekoninck). (3) Escalate where the big model is expected to *change and improve* the answer, and stop escalating categories where it historically doesn't. (4) A human tier fits the same framework (Fanconi & van der Schaar; ThalamusDB in §1.3). (5) Confidence is an attack surface: an adversary can push S1 into escalation — rate-limit escalations per source.

---

## 7. Deciding about retrieval and evidence

Three of the most common brain decisions — *does this need retrieval? is this passage relevant? is this answer supported?* — already exist as trained single-token decisions:

| Work | Decision(s) | How | Result |
|---|---|---|---|
| **Self-RAG** (Asai et al., ICLR 2024, [arXiv 2310.11511](https://arxiv.org/abs/2310.11511)) | `Retrieve` (yes/no/continue), `IsRel`, `IsSup` (fully/partially/no), `IsUse` (1–5) | GPT-4 labelled 4k–20k examples per token type; distilled into a 7B critic; retrieval fires when normalized P(yes) > 0.2 | Critic agrees with GPT-4 >90%; 7B/13B beat ChatGPT on QA and fact verification |
| **CRAG** (Yan et al., 2024, [arXiv 2401.15884](https://arxiv.org/abs/2401.15884)) | Is the retrieved document correct / ambiguous / incorrect? | A **0.77B T5** evaluator with **two thresholds → three actions** | 84.3% accuracy vs ChatGPT ≤64.7% (few-shot) |
| **Adaptive-RAG** (Jeong et al., NAACL 2024) | Query complexity: no retrieval / one-step / multi-step | T5-Large classifier, labels generated automatically | Only 54.5% classifier accuracy, yet matched the multi-step method's F1 at ~⅓ of the steps; an oracle classifier would do far better |
| Mallen et al. (ACL 2023) | Retrieve only for unpopular entities | Popularity threshold | +5.3 points while halving API cost — but **for personal data the logic inverts**: almost everything is "unpopular", so *retrieve by default whenever a known entity is mentioned* |
| SKR (Findings EMNLP 2023); Self-Routing RAG (2025) | Retrieve or not | **Nearest neighbours over past decisions** | Self-Routing RAG: 21–40% fewer retrievals with accuracy gains, no per-dataset tuning |
| UAR (Findings EMNLP 2024) | Four binary criteria: user asked? needs facts? time-sensitive? model lacks knowledge? | Linear heads on hidden states | 85.3% retrieval-timing accuracy vs Self-RAG 60.1% — *decomposing* the decision helps |
| Probing-RAG (Findings NAACL 2025) | More retrieval needed? | 5 MB probe on a 2B model's hidden states | Skipped 57% of retrievals with better accuracy |
| **Sufficient Context** (Joren et al., ICLR 2025, [arXiv 2411.06037](https://arxiv.org/abs/2411.06037)) | Is the retrieved context *sufficient* to answer? | An autorater, combined with the model's self-rated correctness in a **logistic regression** → abstain below a threshold | +2–10% correct among answered; small models hallucinate *or* abstain even with sufficient context |
| Moskvoretskii et al. (ACL 2025, [arXiv 2501.12835](https://arxiv.org/abs/2501.12835)) | Retrieve or not (35 methods compared) | — | Simple uncertainty signals (token entropy, lexical similarity of samples) **match elaborate adaptive-retrieval pipelines at a fraction of the compute** |
| FLARE (EMNLP 2023), DRAGIN (ACL 2024), SeaKR (2024) | Retrieve mid-generation | Low token probability / attention × entropy / hidden-state spread | Strong, but DRAGIN/SeaKR need white-box access not exposed by typical local runtimes |

**Take-aways.** Decompose "needs retrieval?" into criteria, answer the obvious ones in code (a known entity, a date, an explicit ask), and use S1 for the rest. Judge **evidence sufficiency separately from model confidence** and combine them with a tiny logistic regression — this yields an honest "my memory doesn't have enough to answer this" state. Retrieval can hurt (~10% of otherwise-correct answers in Mallen et al.), and retrieval-augmented models over-refuse when all evidence is irrelevant (Zhou et al., AAAI 2026) — design an "irrelevant evidence" path that doesn't force a refusal.

---

## 8. Confidence, calibration, abstention and guarantees

### 8.1 Getting a usable number out of a small model

| Technique | Evidence | Verdict |
|---|---|---|
| **Label-token probability** — one-token answer (YES/NO or A/B/C), probability renormalized over the label set | Kadavath et al. (2022, [arXiv 2207.05221](https://arxiv.org/abs/2207.05221)): pretrained models are well calibrated on lettered choices; post-trained ones needed temperature ≈2.5. Tian et al. (EMNLP 2023): for Llama-2-70B-chat, label probability *discriminated* better than verbalized confidence (AUC 0.707 vs 0.648 on SciQ). | **Default for S1** |
| **Post-hoc calibration** per decision type — temperature, Platt, Bayesian logistic, isotonic | 100 samples sufficed in Fanconi & van der Schaar; ~400 for conformal sets (KnowNo). Calibration fixes ECE but **not ranking** — routing depends on AUROC. | **Required** |
| **Bias correction** — contextual/batch calibration (Zhao et al., ICML 2021: up to +30 points; Zhou et al., ICLR 2024); surface-form competition (Holtzman et al., EMNLP 2021); option-ID prior (PriDe, ICLR 2024) | Models prefer some label tokens regardless of input. | **Required**: measure each template's label prior once and divide it out |
| **Swap-and-average** for pairwise decisions | Position bias: GPT-4 kept its verdict only 65% of the time when two answers were swapped (MT-Bench, NeurIPS 2023); reordering let a weaker model "beat" ChatGPT on 66/80 queries (Wang et al., ACL 2024). | **Required** for "same entity?", "which passage?"; disagreement between orders is a free escalation signal |
| **Nearest neighbours over past decisions** (SKR, RouteLLM, Self-Routing RAG; Logan's instances) | Cheap, self-updating prior | **Default companion** |
| Verbalized confidence ("90%") | Overconfident; weaker in small/open models (Xiong et al., ICLR 2024); needs fine-tuning to be calibrated (Lin et al., TMLR 2022) | A/B only; never the gate |
| Self-verification / P(True) | Noisy (AutoMix); **ownership bias** — models are up to 26% more confident in answers presented as their own (Sanz-Guerrero et al., Findings ACL 2026) | Present the text being checked as *someone else's*; feed into a calibrator |
| Sampling agreement / semantic entropy (Kuhn et al., ICLR 2023; Farquhar et al., *Nature* 2024) | AUROC 0.790 vs 0.691 for naive entropy, but ~10× the cost | For escalated, high-stakes answers only |
| Hidden-state probes (Azaria & Mitchell 2023; CCS; INSIDE; semantic-entropy probes; Orgad et al., ICLR 2025) | Cheap at inference and strong — but **do not generalize across tasks**, and need activations the runtime may not expose | Later |
| Fine-tuned confidence (Self-REF, Gatekeeper; RLCR, ICLR 2026) | Train the model to *defer well*, not just to be accurate | A natural fine-tuning target (§9) |

**Pitfalls that apply directly.** Post-training degrades calibration (GPT-4 report; Zhu et al. 2023; Nakkiran et al. 2025) — assume every instruction-tuned checkpoint is miscalibrated and **recalibrate after every model or adapter change**. Meaning-preserving prompt-format changes swung accuracy by up to 76 points (Sclar et al., ICLR 2024) — freeze and version decision prompts. Whether "thinking" improves calibration is contested (Yoon et al., NeurIPS 2025 vs Nakkiran et al. 2025) — measure it locally.

### 8.2 Three bands, margins and guarantees

- **Three bands per decision**: calibrated p ≥ τ_hi → accept; p ≤ τ_lo → reject; otherwise escalate (S2, then H if S2 is unsure or disagrees). Precedents: CRAG, SOFAI, Fanconi & van der Schaar, LOTUS/SUPG/BARGAIN (§1.3).
- **Margins for choices**: escalate when `p(top1) − p(top2)` is small (De Neys; Cache & Distil's margin sampling).
- **Conformal "ask for help"** — KnowNo (Ren et al., CoRL 2023, [arXiv 2307.01928](https://arxiv.org/abs/2307.01928)): frame candidate actions as lettered options, calibrate option scores with split conformal prediction on ~400 examples; act if the prediction set has one option, otherwise ask the human *with the set as buttons*. Up to 24% less human help than a naive baseline at the same success target.
- **Auto-accept with a controlled false-accept rate** — Conformal Alignment (Gui et al., NeurIPS 2024); **claim back-off with 80–90% factuality guarantees** — Mohri & Hashimoto (ICML 2024).
- **Human deferral as a policy**: defer where the human actually changes outcomes (Mozannar & Sontag, ICML 2020; CoAnnotating, EMNLP 2023), with an attention budget.
- **Graded judgements**: use the expected score Σ p(k)·k over score tokens rather than the argmax (LLM-as-a-Verifier, 2026).
- **Errors compound into memory**: a wrong accept becomes a stored "fact" (Xia et al., 2026) — store confidence and provenance with every write and allow retraction.

---

## 9. Distillation and fine-tuning small models

*The dedicated fine-tuning research slice (G) was interrupted twice; this section draws on slices A, B and D and on tool documentation verified directly (mlx-lm source and PyPI, 25 Sep 2026).*

### 9.1 Should a small judge be fine-tuned? The evidence says yes — for skills, not facts

| Evidence | Result |
|---|---|
| CRAG retrieval evaluator (Yan et al. 2024) | A **fine-tuned 0.77B** T5 judged passage relevance at 84.3% vs ChatGPT at ≤64.7% prompted |
| Arch-Router (Tran et al. 2025) | Fine-tuned 1.5B routing accuracy 93.2% (≈ Claude-3.7-Sonnet) vs **34.4%** turn-level for the untuned base |
| Distilling System 2 into System 1 (Yu et al. 2024) | A judge distilled to answer in 4 tokens reached 72.4% human agreement (from 28.1%); judge-type decisions distil, multi-step arithmetic does not |
| Self-RAG (ICLR 2024) | GPT-4 labels (4k–20k per decision) distilled into a critic agreeing >90% with GPT-4 |
| MiniCheck (EMNLP 2024) | A 0.77B grounding checker at GPT-4 accuracy for 400× less |
| AnyMatch (2024); Ditto (VLDB 2021) | Small fine-tuned entity matchers within ~4 F1 of GPT-4 at ~3,900× lower cost |
| Memory-R1 (2025); Mem-α (2025) | Memory-operation choices learned from as few as **152** examples (RL, 3–14B); a *trained* Qwen3-4B beat GPT-4.1-mini (0.592 vs 0.517) while the *untrained* one scored 0.389 |
| Self-REF (ICML 2025); Gatekeeper (NeurIPS 2025) | Fine-tuning can also teach a small model to **defer well** — confidence tokens or a loss that separates right from wrong answers |
| LLM labels as training data (Wang et al. 2021; Gilardi et al. 2023; LLMaAA 2023; Thomas et al. 2024) | LLM labels cut labelling cost 50–96%, match or beat crowd workers on relevance-type judgements, and small students trained on a few hundred of them can **surpass their teacher** on narrow tasks |

**Knowledge stays in the database.** EnronQA's authors tested exactly the alternative — memorizing a person's emails into LoRA adapters — and found that it can match long-context prompting, but **retrieval beats memorization and long context at every scale they tried** (Ryan et al. 2025). Weight editing also fails on ripple effects and collapses after many edits (§1.1). So the fine-tune targets the *judge's skills* — what this person treats as worth remembering, who they answer, where they file things, what supports an answer — and never the facts themselves.

### 9.2 Where the labels come from — without hand-labelling

1. **The owner's own behaviour** (personal, real): whether they replied to a message (a sent message in the same thread soon after), which of their own folders they filed it in, what they deleted. Email foldering is a long-standing personal-classification task on this very corpus (Bekkerman et al. 2004, cited in the notes; per-user results not re-verified here).
2. **Benchmarks with ground truth**: EnronQA's gold answers and deliberately plausible wrong answers (supported / not supported), gold emails vs hard negatives (relevant / not).
3. **A local teacher**: the 14B model's answers on the decisions without behavioural ground truth (commitment? decision? meeting request?), kept only when self-consistent, spot-checked by the owner.
4. **Corrections**: every human override in the ledger becomes a gold label (Cache & Distil; online cascade learning, §6).

Split by time and thread, not at random, so the model is tested on later mail than it trained on.

### 9.3 Tooling on Apple Silicon (verified)

- **mlx-lm 0.31.3** (PyPI, 22 Apr 2026; `pip install "mlx-lm[train]"`) includes a `qwen3` model implementation. `mlx_lm.lora --model … --train --data DIR` trains LoRA (or DoRA/full via `--fine-tune-type`) from `train.jsonl` / `valid.jsonl` / `test.jsonl` in **chat format** (`{"messages": [...]}`); `--mask-prompt` computes the loss on the answer only — exactly what a one-token judge needs. `--batch-size` (default 4), `--num-layers` (default 16), `--grad-checkpoint` and `--grad-accumulation-steps` trade memory for speed.
- `mlx_lm.load(path, adapter_path=…)` applies a trained adapter, and the model's logits are directly available, so label probabilities are **exact** (no top-20 cap) and the prompt prefix can be cached (`make_prompt_cache`).
- `mlx_lm.fuse --export-gguf` supports only Mistral, Mixtral and Llama-style models — **a fine-tuned Qwen3 cannot be handed back to Ollama this way**; serve it in-process with MLX instead.
- Checkpoint sizes (Hugging Face): `mlx-community/Qwen3-1.7B-4bit` 0.98 GB, `…-bf16` 3.46 GB; `mlx-community/Qwen3-0.6B-bf16` 1.21 GB.

### 9.4 Pitfalls to design for

Fine-tuning changes calibration: recalibrate per decision after every adapter version (§8). Keep a before/after comparison on the *same* runtime and precision, so quantization is not mistaken for learning. Guard against label leakage (the same thread in train and test). Version adapters and keep the previous one for rollback. Never fine-tune on data that must remain deletable — erasure is only guaranteed for what lives in the database.

---

## 10. The System 1 model zoo and runtime on this Mac

**Machine (checked 25 Sep 2026):** Apple M5 Pro (16-core GPU), 24 GB unified memory (~18 GB usable by the GPU), macOS 26.6; Ollama 0.34.4 (which runs upstream llama.cpp `llama-server` per model), Docker, Python 3.12 via uv. Installed models: `qwen3:14b` and `qwen3:1.7b` (original hybrid Qwen3, honour `think:false`), `qwen3:4b` (**the thinking-only 2507 build — it ignores `think:false`**), `bge-m3` embeddings.

### 10.1 Runtime facts that decide the implementation

- **Logprobs work today.** Ollama's native `/api/chat` and `/api/generate` accept `"logprobs": true, "top_logprobs": k` (added in v0.12.11, Nov 2025) with **k ≤ 20**. On 0.34.4, `/v1/chat/completions` also returns them despite the docs. Keep label sets tiny and give each label a **distinct first token** (e.g. yes/no, A/B/C — "SIGNAL" tokenizes as "S", "NOISE" as "NO").
- **Don't read scores off constrained JSON.** With `format` (a JSON schema) set, the logprobs Ollama returns are still the *unconstrained* distribution. Score labels from a plain one-token answer and renormalize over the label set.
- **Prefix caching is automatic** (llama-server's host-RAM prompt cache, 8 GiB default): three alternating decision-type prefixes all stayed cached; a ~340-token cached prefix cut prefill from ~100 ms to ~30 ms for the 1.7B. Put each decision type's fixed instructions first and the item last.
- **Avoid hybrid/recurrent small models for cached S1 until tested** — Qwen3.5 small, LFM2/2.5 and Granite-4.0-H have open llama.cpp cache-reuse bugs.
- **Residency.** Ollama keeps 3 models loaded by default here; a fourth evicts one (reload 0.5–14 s). Set `OLLAMA_MAX_LOADED_MODELS=5` and `keep_alive: -1` for S1 models.
- **Pin Ollama 0.34.4 for the hackathon.** v0.40.0-rc0 (25 Sep 2026) makes the MLX runner the default on Apple Silicon, which may change logprob and caching behaviour.
- **Ollama has no rerank endpoint and no classifier heads.** Rerankers and encoder classifiers run in-process (transformers/sentence-transformers), via standalone `llama-server --reranking`, or — for Qwen3-Reranker — by emulating its P("yes") scoring through raw-mode logprobs.
- **MLX (`mlx-lm`)** gives exact full-vocabulary logits (no top-20 cap) and LoRA training; one `uv add` away. Apple reports 3.3–4.1× faster time-to-first-token on M5 vs M4 with MLX (needs macOS ≥26.2).

### 10.2 Measured latency (Ollama 0.34.4, Q4_K_M, `think:false`, one output token, ~400-token prompt)

| Model | Cold load | Uncached | With cached instruction prefix |
|---|---|---|---|
| qwen3:1.7b | 0.5–0.9 s | ~100 ms (~4,100 tok/s prefill) | **~35 ms** |
| qwen3 4B (2507 build) | up to 14 s first load | ~250 ms | 65–105 ms |
| qwen3:14b | — | ~200 ms per judgement on short prompts (Appendix A) | — |
| bge-m3 embedding (~254 tokens) | ~1 s | ~21 ms (no batching speed-up) | — |

Latency is almost entirely prefill; decoding one token is negligible. The published llama.cpp Apple Silicon table shows the M5 Pro prefilling ~3.7× faster than the M4 Pro (Neural Accelerators).

### 10.3 Candidates for System 1

**Small generative models scored by label logprobs** (plain transformers, so prefix caching works):

| Model | Size · licence | Notes |
|---|---|---|
| **Qwen3-1.7B** (installed) | 1.4 GB · Apache-2.0 | ~35 ms/decision; honours `think:false`; **overconfident zero-shot** — needs calibration or fine-tuning |
| **Qwen3-4B-Instruct-2507** (`qwen3:4b-instruct`) | 2.5 GB · Apache-2.0 | Non-thinking only; the right "strong S1"; 65–105 ms |
| Qwen3-0.6B | 0.5 GB · Apache-2.0 | ~15–25 ms (estimated); a fine-tuning base |
| **Gemma 3 270M** | 0.3 GB · Gemma Terms | Google positions it explicitly as a fine-tuning base for **classification, extraction, routing, compliance checks** |
| Granite 4.0 350M/1B (dense) | Apache-2.0 | Lists classification/extraction as intended uses |
| Llama 3.2 1B/3B | Llama licence | Officially supports Hindi |
| Qwen3.5 0.8B/2B/4B (Mar 2026) | Apache-2.0 | Stronger, 201 languages — but hybrid architecture: test cache reuse first |

**Specialist encoders and judges** (run in-process; need torch added):

| Decision | Candidate | Size · licence | Reported quality |
|---|---|---|---|
| Entities, zero-shot labels, structured extraction, PII spans | **GLiNER2** ([arXiv 2507.18546](https://arxiv.org/abs/2507.18546)) + gliner-pii | 205M · Apache-2.0 | One CPU-first model for NER + classification + JSON extraction + relations |
| Contradiction (entail / neutral / contradict) | `cross-encoder/nli-deberta-v3-base` | ~0.2B · Apache-2.0 | MNLI-mismatched 90.0% |
| Is this claim supported by the source? | HHEM-2.1-open; MiniCheck-Flan-T5-L (EMNLP 2024); **Granite Guardian in Ollama** | 0.1B / 0.8B / 2B | MiniCheck: GPT-4-level at 400× lower cost; Granite Guardian answers `groundedness`, `relevance`, `answer_relevance` with a single Yes/No token → P(Yes) from logprobs, no extra code |
| Is this passage relevant? | Qwen3-Reranker-0.6B (P("yes") from the LM head); bge-reranker-v2-m3 | ~0.6B · Apache-2.0 | Vendor tables disagree on ranking — evaluate locally |
| Injection-like text | Llama Prompt Guard 2 (86M, multilingual incl. Hindi) | Llama licence (gated) | 97.5% recall at 1% FPR on static data — **but see §11: bypassed >90% by adaptive attacks** |
| Routing / duplicates / "seen this before?" | bge-m3 (installed) or Qwen3-Embedding-0.6B | MIT / Apache-2.0 | kNN over past decisions; SetFit heads (8 examples/class competitive with 3k-example RoBERTa) |

**Licence traps:** non-commercial — Bespoke-MiniCheck-7B, Lynx, jina-reranker v3/3.5, GLiREL, Sarvam-1. Custom — Llama (incl. Prompt Guard 2), Gemma 3 (Gemma 4 moved to Apache-2.0), LFM (free under $10M revenue). Apache/MIT choices exist for every role.

**Indic coverage:** Qwen3.5 (201 languages), Gemma 3/4, bge-m3, mmBERT, Llama 3.2 (Hindi) and Prompt Guard 2 86M (Hindi). There is no open Sarvam instruct model under 5B.

### 10.3a Jev — TypeSafe's "System One model" (launched 15 Sep 2026)

The closest product to what this review calls System 1 (sources: typesafe.ai and docs.typesafe.ai, fetched 25 Sep 2026; flaviocopes.com/jev deep-dive; github.com/amithgc/local-jev):

- **What it is:** a *decision model*, not a chatbot — "typed decisions … more like code". You send a **state** (text or JSON) plus named **questions**; each is answered independently and in parallel against the same state.
- **Three primitives:** **noul** (yes/no → a single probability 0–1), **choice** (pick one of up to 255 labelled options → `choice`, `probabilities`, `confidence`), **score** (2–10 ordered levels → probability-weighted `score`, `legend`, `probabilities`, `confidence`). Answers always conform to the schema. `confidence` measures how concentrated the distribution is.
- **Calibration:** trained with "Reinforcement Learning for Calibrated Decisions (RLCD)" so that 90%-probability answers are right ~90% of the time; the docs recommend asking **each factor as a separate question and combining results in code**, acting when confidence is high and escalating when it is not.
- **Speed and price:** 70–500 ms end to end, most ~100 ms; $0.042 per million input tokens, output free. **Cloud API only; weights closed.**
- **Documented limits** (which match this review's S0/S1 split exactly): unreliable at **maths, counting and comparisons**, weak at **dates and relative time**, hurt by **indirection** (double negatives) and by **large unrelated state**, and **cannot extract or generate** — it only chooses among provided options.
- **Local reproduction:** `local-jev` (MIT) serves the same wire format with local models, reading next-token probabilities of option letters and applying per-model temperature scaling. On the 231 public items of **JevBench** (github.com/fstandhartinger/jevbench, MIT): Qwen3.5-4B 80.5% (651 ms), Qwen3-4B 70.1% (177 ms), Qwen3.5-2B 66.2% (261 ms), Qwen2.5-1.5B 58.9% (74 ms), NLI DeBERTa-large 54.1% (76 ms) on an M4 Max — against **86.6% published for hosted Jev**.

**What this means for the rebuild:** the typed-question API (state + noul/choice/score + calibrated probabilities) is a clean, already-familiar interface for System 1, and JevBench gives an *external* yardstick. The gap Jev leaves is exactly the sovereign one: a local judge, **fine-tuned on one person's own decisions**, whose every answer is logged and correctable.

### 10.4 What our own probe showed (Appendix A; n = 16, indicative only)

Single-token yes/no decisions over 16 hand-labelled examples (actionable? conflicts with a stored decision? hidden instructions? same piece of work?):

| Setup | Correct | Brier | Time |
|---|---|---|---|
| qwen3:1.7b, one token | 13/16 | 0.139 | 34 ms median |
| qwen3:14b, one token | 15/16 | 0.061 | ~200 ms median |
| **Cascade**: 1.7b decides unless 0.1 < P(yes) < 0.9, else 14b | **15/16** | — | 1.2 s total vs 3.6 s for 14b-only; **3/16 escalated** |
| qwen3 4B (thinking build), JSON full extraction | invented a task from a newsletter with self-reported confidence 0.9 | — | 1.4–2.1 s per email |

The 1.7B's errors sat mostly in the uncertain band — exactly what a confidence band catches — but one error was confidently wrong, which is why calibration on labelled data and code-level floors are non-negotiable.

### 10.5 Fine-tuning the personal judge: before and after (measured 25–26 Sep 2026)

**Setup.** Qwen3-1.7B (bf16) with a LoRA adapter trained by MLX-LM: rank 8, scale 20, 16 layers, learning rate 1e-4, batch 4, 1,050 steps (one pass over 4.2k training examples), loss on the answer only. Training took 54 minutes on the M5 Pro at a peak of 18 GB; final validation loss was 0.096.

The training data is 5,958 labelled examples of four decisions, all taken from ground truth the brain already holds:

- `supported`: EnronQA's gold answers against its wrong ones.
- `relevant`: the gold email against the best keyword match from another thread, a hard negative.
- `replied`: did the owner write in the same thread within 14 days?
- `filed`: which of the owner's 12 busiest personal folders an email ended up in.

The data is split by conversation, 70/10/20, so no thread in the test set was seen in training. Every model is scored on the same test examples. Temperature and the settle band are fitted on one half of them and measured on the other.

| Decision (held-out conversations) | 1.7B base | **1.7B fine-tuned** | 14B, zero-shot | Settled at 95% precision: fine-tuned 1.7B (its accuracy) / 14B | Median latency, 1.7B-ft / 14B |
|---|---|---|---|---|---|
| `supported` (n = 326) | 83.7% · 0.935 | **96.6% · 0.993** | 95.5% · 0.981 | **82.6% (99.3%)** / 44.4% | 184 / 610 ms |
| `relevant` (n = 312) | 74.4% · 0.883 | **90.9% · 0.956** | 87.5% · 0.926 | **44.3% (94.9%)** / 0% | 285 / 1,310 ms |
| `replied` (n = 290) | 44.6% · 0.562 | **60.1% · 0.670** | 55.4% · 0.608 | 0% / 0% | 362 / 889 ms |
| `filed`, 12 folders (n = 301) | 31.5% | **52.7%** | 47.9% | 0% / 0% | 301 / 983 ms |

Cells show accuracy · AUROC. For `filed`, chance is 8.3%. Latency is for the whole prompt: emails of up to 6,000 characters, bf16 in-process for the 1.7B and Q4 Ollama for the 14B.

**What it shows.**

1. **The fine-tuned 1.7B beats the untuned 14B on all four decisions, at one third to one fifth of the latency.** On the text-grounded decisions (`supported`, `relevant`) it is also calibrated enough to *settle* most cases at 95% precision. The 14B mostly cannot: its probabilities need temperatures of 7–36 to calibrate, and its confident region is narrow. This is the payoff the design bet on (§5, §9). A small model trained on the owner's own ground truth answers the brain's recurring yes/no questions, and the large one rarely has to.
2. **The cascade settles most easy cases on the small model.** For `supported`, S1 settles 82.6% at 99.3% accuracy. For `relevant`, only the reject side settles: 44.3% of pairs are confidently irrelevant and dropped. The kept items go to S2, which reads them anyway when answering (`ask.py`).
3. **Escalation must be measured on what is escalated.** S2 only ever sees the cases S1 is unsure about, and on those it is *worse* than the fine-tuned S1 for every decision:

   | Decision | Escalated cases | S1 correct | S2 correct |
   |---|---|---|---|
   | `supported` | 31 | 83.9% | 80.6% |
   | `relevant` | 98 | 87.8% | 86.7% |
   | `replied` | 148 | 60.1% | 55.4% |
   | `filed` | 146 | 52.7% | 47.9% |

   S2's confidence band was fitted on all examples, which overstates how sure it can be on hard ones. The few `supported` cases it settled were only 3 of 5 correct, which pulled cascade accuracy on settled cases from 99.3% down to 98.0%. A band fitted on everything cannot promise precision on the subset it is actually used for. §6's take-away 3 gives the remedy: escalate only where the big model historically *improves* the answer (as in Signed Rescue Routing). So `evaluate` now records S1 and S2 accuracy on the escalated cases, and the judge skips S2 for any decision where S2 is no better there. An unsure answer goes straight to the owner instead: D41, "does this need System 2 at all?", decided from the ledger's statistics (D55) rather than by a fixed tier order. The `supported` sample is small (a difference of one case), so the rule is re-measured whenever the judge is re-evaluated. With the owner's own judge in place, the 14B stays where it is needed: writing answers and extractions, the intent check (D45), and decisions S1 has not been trained on.
4. **Personal decisions are learnable, but only partly from text.** Fine-tuning helps on `replied` (+15.5 points, AUROC 0.56 → 0.67) and `filed` (+21 points), where the generic 14B knows nothing about the person. But what the owner will do can't be predicted at 95% precision from the email alone, so nothing settles. These stay suggestions for the owner, and the owner's corrections become the next round of training data.

### 10.6 System 1 checking System 2: answering from the brain (measured)

`engram ask` answers in five steps:

1. Hybrid search retrieves 10 items.
2. The fine-tuned judge drops the ones it is sure are irrelevant and orders the rest by P(relevant).
3. The 14B answers from what is left, citing items.
4. The judge checks the answer against each cited item (`supported`).
5. An unsure verdict goes to the owner, not the 14B, as §10.5 found.

The test set is 100 EnronQA questions whose emails lie in conversations the judge never trained on.

| | |
|---|---|
| Gold email among the 10 retrieved / kept by the judge / cited by the 14B | 82% / 82% / 59% |
| Correct: 14B grader, strict / reworded / **audited** | 52% / 55% / **70%** |
| Correct when the brain answers (cites something; 87% of questions) | **80%** |
| Judge vouches (settled `supported`, 82% of answers): correct / otherwise | **84%** / 6% |
| The judge's support probability as a signal of correctness | **AUROC 0.92** |

The 14B grader turned out to be the weakest instrument. It marked "Merrill Lynch-Houston Director Carl Kirst…" wrong against the reference "Merrill Lynch.", and "Gas, Power and Liquids" wrong against a full-sentence reference. So all 45 answers it graded wrong were audited by hand, as was a pass over the 55 it graded right. 15 of the 45 were right; no false positives were found among the 55.

Ordering the context by the judge's relevance didn't change accuracy (52% against 53% under the strict grader), so order isn't the bottleneck. The losses are retrieval (18% of gold emails never retrieved) and the 14B citing a similar but different email: several Enron newsletters and interview emails nearly duplicate one another.

The useful finding is the check itself. A 1.7B model trained on the owner's data tells right answers from wrong ones almost perfectly. When it won't vouch for an answer, that answer is right 6% of the time, so the brain can say "I'm not sure, check these emails" instead of confidently misleading its owner. Its limit is by design: it checks an answer against one item at a time. An answer synthesized across several meeting segments is rightly "not supported" by any single segment, even when the synthesis is fair.



### 10.7 The memory gate: what is worth remembering? (measured, round 2)

The first memory build sent 59 of 60 emails to the 14B for extraction, and newsletters became "commitments". Three per-kind yes/no gates (commitment? decision? meeting?) were replaced by one question, `remember`: does the item hold a specific commitment or task, a decision, or a meeting involving the owner or their work? It was measured against 90 random emails the assistant hand-labelled with that rubric: 50 to refine the rubric (dev) and 40 held out (test). About 38% are worth remembering.

| Candidate (one token) | Test accuracy | AUROC | Passes | ms/item |
|---|---|---|---|---|
| qwen3:0.6b, zero-shot | 62% | 0.44 | 0% ("no" to everything) | 75 |
| qwen3:1.7b, zero-shot | 47% | 0.66 | 90% | 137 |
| fine-tuned 1.7B (p ≥ 0.5) | 72% | 0.80 | 10%, every one right | 149–403 |
| qwen3:14b, zero-shot | 60% | 0.75 | 72% | ~1,000 |
| qwen3:14b with reasoning (dev only) | 72% | — | 58% | 12,400 |
| **S0 bulk rules** (sender and text patterns) | — | — | drops ~20% | µs |

No model separates this well zero-shot. Even the 14B with reasoning only matches the owner's rubric 72% of the time, so it is no teacher. The definition is genuinely fuzzy: is "any thoughts?" a task, and is an automated access-approval request memorable?

A linear probe on the stored embeddings needs more labels than 90. Cross-validated it reached AUROC 0.74 against 0.62 for shuffled labels. (A first, buggy solver had reported 100%; the shuffled-label control is what caught it.)

**What was built.** A recall-first cascade:

1. **S0** drops bulk and machine mail. On the gold set it removed about 20% of items and no memorable one.
2. **S1** (the fine-tuned judge, p ≥ 0.2) passes the rest, keeping 93–95% of memorable items.
3. **S2** extracts, and may now return nothing.
4. The most borderline items go to the owner's Obsidian review queue.

On 60 real emails this took extraction calls from 59 to 47, beliefs from 151 to 36, and time from 807 s to 255 s. Precision beyond S0 now depends on the owner's verdicts: each one becomes a label, and a few hundred of them will train the probe (LR §9).

### 10.8 A faster System 1 (measured, round 2)

`ask` spent 4–15 s having the fine-tuned judge read ten whole emails. Candidates for that `relevant` check, on the held-out test pairs (n = 312):

| System 1 option | Accuracy | AUROC | ms/item |
|---|---|---|---|
| fine-tuned 1.7B, bf16, adapter (before) | 89.4% | 0.955 | 623 |
| **fine-tuned 1.7B, adapter fused and quantized to 4-bit (934 MB)** | **90.4%** | **0.963** | **214** |
| the same, reading only the best-matching chunk | 77.2% | 0.835 | 156 |
| qwen3:1.7b, zero-shot, best chunk | 66.3% | 0.756 | 90 |
| qwen3:0.6b, zero-shot, best chunk | 61.2% | 0.642 | 48 |
| probe on retrieval signals (both ranks, fused score, cosine) | 72.4% | 0.758 | ~0 |

Fusing the LoRA adapter and quantizing to 4-bit costs no accuracy and is 2.9× faster: the judge now reads a whole email in about 200 ms. Reading only the best chunk is not a shortcut: the judge was trained on whole emails, and the chunk loses context. The smaller zero-shot models and the probe are far weaker; the probe settles nothing at 95% precision.

On the calibration sets the 4-bit judge scores `supported` at 96.6% (AUROC 0.992) and `relevant` at 92.1% (AUROC 0.966). Once again the 14B is less accurate on the cases the judge escalates.

**Answering (the same 100 held-out questions, the same grader).** `ask` now judges retrieved items in rank order, stops once two are clearly relevant, and gives the answering model at most four:

| Pipeline | Median | 90th percentile | Graded correct | Who answered |
|---|---|---|---|---|
| round 1: bf16 judge on all 10 items, 14B reads everything kept | ~21 s | — | 55% | 14B |
| **round 2: 4-bit judge, early stop, top 4 to the 14B** | 11.1 s | 17.9 s | **62%** | 14B |
| **round 2 + System 1 answers first** (qwen3:1.7b drafts; the judge must settle "supported") | **1.7 s** | 6.0 s | 56% | 1.7B 80%, 14B 13%, none 7% |

Less context made the 14B *more* accurate. Answering with System 1 first cuts median latency another 6.5×, for about 6 points of accuracy. That makes it an owner's choice (`ENGRAM_DRAFT_MODEL`), not the default. (The grader is the lenient 14B one of §10.6; audited accuracy runs higher, as shown there.)

---

## 11. Controlled execution, security and audit

The track asks for "agentic tool execution through systems such as MCP" with "controlled execution where actions can be reviewed and audited". The literature is unusually clear here, and it sets hard limits on what System 1 may decide.

### 11.1 The core finding: small models may raise suspicion, never grant permission

| Evidence | Finding |
|---|---|
| *The Attacker Moves Second* (Nasr et al., 2025, [arXiv 2510.09023](https://arxiv.org/abs/2510.09023)) | Adaptive attacks broke 12 published defences: PromptGuard, ProtectAI and Model Armor detectors >90% attack success; spotlighting and sandwiching >95%; human red-teamers defeated every challenge. |
| AgentDojo (Debenedetti et al., NeurIPS 2024 D&B, [arXiv 2406.13352](https://arxiv.org/abs/2406.13352)) | A DeBERTa injection detector cut attack success 57.7% → 8.0% but **halved benign task success (69% → 41.5%)** through false positives. A deterministic *tool filter* (expose only the tools the task needs) reached 6.8% attack success without that cost. |
| InjecGuard / NotInject (Li & Liu, 2024–25) | Guard models fall to ~60% (near chance) on benign text containing words like "ignore", "urgent", "override" — which Indian business email is full of. |
| R-Judge (Findings EMNLP 2024) | Prompted small models were near chance at judging whether an agent trajectory is risky; only safety-*fine-tuned* guards competed with GPT-4o. |
| LlamaFirewall (Chennabasappa et al., 2025, [arXiv 2505.03574](https://arxiv.org/abs/2505.03574)) | Prompt Guard 2 (86M): 97.5% recall at 1% FPR on static data. AlignmentCheck ("do these actions still serve the user's goal?") worked with a large model, but with 1B/8B models produced many false positives and lost utility. |
| CASCADE (2026, [arXiv 2604.17125](https://arxiv.org/abs/2604.17125)) — a layered **local** MCP defence almost identical to an S0→S1→S2 stack | Regex + embedding stage: recall 94.8% but **68.5% of all traffic sent to human review**; the local 8B reviewer, run on a third of requests at 2.5 s each, **changed no outcome** — it was only useful for escalating. |
| FIDES (Costa et al., Microsoft 2025, [arXiv 2505.23643](https://arxiv.org/abs/2505.23643)); type-directed privilege separation (Jacob et al., [arXiv 2509.25926](https://arxiv.org/abs/2509.25926)) | Outputs restricted to booleans/enums/numbers **cannot carry injected instructions** (low channel capacity): 0% attack success with no utility loss on calendar scheduling. But an attacker can still *flip* the value. |

**So System 1 outputs are safe to pass along but not safe to trust as the final "allow".** Security comes from structure (S0) and the human; S1 is triage. The resulting rule: **`risk tier = max(S0, S1, S2)`** — models may only raise a tier, never lower one, clear a flag or skip a human step.

### 11.2 Structural defences that do work

- **Dual-LLM / quarantine pattern** (Willison 2023) and the **lethal trifecta** (Willison 2025: private data + untrusted content + external communication = exfiltration risk). A second brain has all three by design, so it must break the trifecta *per action*.
- **Agents Rule of Two** (Meta, Oct 2025): within one session, at most two of {processes untrusted input, touches private data, changes state or communicates externally}; otherwise require a human. Practical form: draft replies in a session that *cannot send*; send only the human-approved draft.
- **CaMeL** (Debenedetti et al., 2025, [arXiv 2503.18813](https://arxiv.org/abs/2503.18813)): a privileged model writes a plan in code from the trusted request only; a quarantined model parses untrusted data; an interpreter tracks provenance and checks policies before every tool call — 77% of AgentDojo tasks solved with provable security vs 84% undefended, at ~2.8× tokens.
- **Design patterns for securing LLM agents** (Beurer-Kellner et al., 2025, [arXiv 2506.08837](https://arxiv.org/abs/2506.08837)): *action-selector* (the model only picks from a fixed menu — the pattern-level justification for "S1 chooses from a closed set"), plan-then-execute, map-reduce, dual LLM, code-then-execute, context-minimization.
- **Progent** (Shi et al., 2025): deterministic allow/forbid policies with argument conditions; permissions may **narrow automatically but widen only with a human** — AgentDojo attack success 39.9% → 1.0%; only 6% of policy updates needed approval. An independent 2026 re-test with a local Qwen2.5-7B held up (25.8% → 4.2%).
- **Deterministic anti-spoofing**: DMARC alignment (RFC 9989, May 2026), Unicode confusables skeleton (UTS #39), Punycode/mixed-script flags, first-seen domains. **Hidden text** (white or microscopic PDF text, Unicode tag characters — seen at 2.3M phishing messages/day in 2026) is detected by code, not models.

### 11.3 MCP specifics

The current spec is **2026-07-28**: a stateless core; Roots, Sampling and Logging **deprecated** (call the local model directly); multi-round-trip requests replace server-initiated elicitation. Tools are "model-controlled" and there SHOULD always be a human able to deny invocations; clients should show tool inputs before calling and log usage. Tool annotations (`readOnlyHint`, `destructiveHint` default *true*, `idempotentHint`, `openWorldHint` default *true*) **must be treated as untrusted unless the server is trusted** and cannot stop injection (MCP blog, Mar 2026). Known attacks: tool poisoning, cross-server shadowing (a PoC silently redirected `send_email`) and rug pulls (Invariant Labs, 2025); MCPTox measured 72.8% attack success on o1-mini across 45 real servers. Mitigations: pin a hash of every tool's name/description/schema, block on change, and make the gateway the **only** client of the tool servers (stdio children, not open localhost HTTP — otherwise any local process bypasses it).

### 11.4 Humans in the loop without rubber-stamping

- **Autonomy levels** (Feng et al., 2025): present the agent as *L4 "approver"* for consequential actions and *L5 "observer with audit"* for reversible internal ones — and heed their warning about meaningless rubber-stamping.
- **Habituation**: attention to repeated warnings drops within a work-week (Anderson et al., JMIS 2016; Vance et al., MISQ 2018); **forcing interaction with the critical field** resists habituation (Bravo-Lillo et al., SOUPS 2014). Users approved 93% of Claude Code permission prompts.
- **Push-bombing and transaction binding**: an injected agent can spam its own owner with approvals. Bind each approval token to a hash of the exact action (any change voids it); rate-limit requests; for high-risk items use number matching (CISA 2022) — RBI's 2025 authentication directions require a factor "unique to that transaction".
- **Risk grid**: ToolEmu (ICLR 2024) rates likelihood × severity; even human raters agree only moderately (κ ≈ 0.48) — risk is not crisply learnable, another reason for a deterministic tier table.
- **Data minimization for agent-to-agent talk** (AirGapAgent, CCS 2024): a context-hijacking attack cut protection from 94% to 45%; giving the agent only the data the task needs kept 97%.

### 11.5 Audit, provenance and undo

Tamper-evident logs are cheap and old: hash chains and forward-secure logging (Schneier & Kelsey 1999), Merkle history trees with logarithmic proofs (Crosby & Wallach, USENIX Security 2009), signed tree heads (Certificate Transparency, RFC 6962/9162). A 2026 "agent flight recorder" measured **~48 µs and 512 bytes per event** with 100% tamper detection — so log *every* model and tool call, including denials, with the tier that decided, the score, the threshold, the model digest and the tool hash. Keep personal payloads *outside* the chain (encrypted side table) so erasure works by deleting keys (EDPB Guidelines 02/2025). Event sourcing and sagas give undo: each action declares a compensator or an `irreversible` flag; sent email has no compensator (RAC, 2026), so outbound mail waits in an undo window after approval.

### 11.6 Measured: the gate on WorkBench (25–26 Sep 2026)

WorkBench (Styles et al., 2024) gives an agent a company sandbox (email, calendar, CRM, project tasks, analytics) and grades each task by the state the agent leaves behind. It also flags *harmful side effects*: state changed on a task that was not done right. The agent here is qwen3:14b with native tool calling and no reasoning mode, running 10 tasks from each of WorkBench's six task files.

The benchmark replays each run. The agent does every task once with no gate, and each policy's gate then replays the recorded calls in order. A gate decision depends only on the request, the call and the state so far, so the replay shows what that policy would have let run; WorkBench's own grader then scores the result. The "owner" is an oracle who approves exactly the calls the task needs. The replay cannot capture an agent that recovers, or tries something else, after being told no.

| Policy | Correct | Harmful side effects | Owner prompts per task |
|---|---|---|---|
| No gate (WorkBench's setting) | 38.3% | **40.0%** | 0 |
| Owner approves every external or destructive call | 46.7% | 13.3% | 0.97 |
| **engram: intent check + owner, default autonomy** | **48.3%** | **6.7%** | **0.62** |
| intent check alone, full autonomy | 43.3% | 28.3% | 0.03 |

These are 60 fresh tasks, none of which were used while developing the gate. On the 60 development tasks, after the intent question was reworded (below), the same four rows read 33.3 / 41.7 / 0 · 43.3 / 18.3 / 1.35 · 43.3 / 10.0 / 0.90 · 33.3 / 31.7 / 0.02.

What it shows:

1. **The structure does most of the work.** Code-set tiers plus owner approval for external and destructive calls take harm from 40% to 13%.
2. **The intent check adds two things.** It halves the remaining harm, because it also catches unwanted *internal* changes that would otherwise run automatically. And it cuts owner prompts by a third, because it blocks clearly wrong calls before they reach the owner. For example, the agent tried to delete event 00000000 for "Delete the next Health & Wellness Expo meeting" without searching first. The preview showed the 14B a different event, so it blocked the call and the owner was never asked.
3. **The intent check cannot be trusted alone** (§11.1, confirmed). At full autonomy it lets 28% of tasks do harm. It passed 42 of 70 unwanted calls, because context minimization keeps it from checking facts the request depends on. It can't tell which meeting is "the first", or which email is "the latest", without reading the mailbox. One example: asked to "move my first meeting with dmitri on December 18 by 30 minutes", the agent moved the right meeting and then a second one; the 14B approved the second move with full confidence.
4. **The question's wording mattered.** The first version asked whether the action "does what the owner asked … and nothing more". It blocked 19 of 46 wanted calls in the development tasks. 15 of those were single steps of multi-step requests ("delete all my emails from raj…", "reassign all of fatima's tasks…"). Asking whether the action is "one of the steps the request asks for" fixed that systematic error. On the fresh tasks, 8 of 31 wanted calls were blocked.
5. **Code facts beat model guesses.** In a demo, the agent forwarded an email to `kofi@atlas.com`; Kofi's real address is `kofi.mensah@atlas.com`. The 14B passed the call with p = 1.00, because nothing in the preview said the address was unknown. The preview now adds a code-checked fact: any address that isn't in the company directory is flagged. For the owner's own brain, the `contacts` view plays that role. Re-grading the same 60 fresh trajectories with this one line, harm at default autonomy falls from 6.7% to **3.3%**, with 0.53 owner prompts per task. At full autonomy it falls from 28.3% to 16.7%, and the judge blocks 34 of 70 unwanted calls instead of 27, with no extra wanted calls blocked. The check was added after the fresh run (prompted by the demo, not by these tasks), so treat these numbers as a second, post-hoc reading.

---

## 12. Sovereignty, privacy and the Indian context

- **Local-first software** (Kleppmann et al., Onward! 2019): seven ideals — fast, multi-device, offline, collaboration, longevity, privacy, user control. **"File over app"** (Ango 2023): durable open files outlive apps. A brain whose memory is exportable (Markdown + a verifiable log) scores on "you own it".
- **Why not hybrid local+cloud?** Minions (ICML 2025) reached 97.9% of cloud quality at 5.7× lower cost, and PAPILLON (NAACL 2025) kept quality on 85.5% of queries — but still leaked private information on **7.5%**. Even good delegation leaks; the sovereign claim is *zero cloud calls*.
- **Vendor kill-switch risk is real:** Rewind's local capture was disabled after Meta's acquisition (Dec 2025); Mem0's local OpenMemory server was sunset (2026). Owning the stack is a feature, not a slogan.
- **Apple Private Cloud Compute** (2024) supplies useful vocabulary: enforceable (not policy) guarantees, no privileged runtime access, verifiable transparency.
- **India's DPDP Act 2023 and DPDP Rules 2025** (notified 13 Nov 2025): Consent Manager rules from ~13 Nov 2026; most duties — including **security safeguards with access logs retained for one year** (Rule 6), **72-hour breach report** (Rule 7) and erasure (Rule 8) — from ~13 May 2027. Penalties up to ₹250 crore. The personal/domestic exemption (s.3(c)(i)) likely does **not** cover business use of other people's email — flag as an open legal question, not advice. A local-only brain with tamper-evident logs and crypto-shredding can honestly pitch "DPDP-ready by architecture".
- **Sovereign Indic models:** IndiaAI Mission (₹10,372 crore, Mar 2024); Sarvam 30B/105B and BharatGen Param2 (17B MoE, ~2.4B active) launched Feb 2026 — too large or unverified for the S1 role on this laptop, but a roadmap line.

---

## 13. Landscape and prior art: where the white space is

### 13.1 The organizer-named tools

- **GBrain** (github.com/garrytan/gbrain; Garry Tan; MIT; TypeScript/Bun; created Apr 2026, ~30k★): Markdown pages in git as canonical, PGLite or Postgres+pgvector; a rewritten **"compiled truth"** per page plus an **append-only timeline**; keyword + vector + typed-graph retrieval; nightly "dream cycle", cron jobs, morning briefing; an **open-loop engine** that extracts commitments from Gmail (a deterministic zero-LLM thread-state detector first, then an LLM extractor). Storage is local, but **reasoning defaults to cloud models** (the Ollama recipe covers embeddings only; sub-agents are pinned to Anthropic). Detecting that a commitment was *fulfilled* is listed as future work. It refuses to answer when its sync is stale.
- **Utopia** (github.com/deeplethe/utopia; DeepLethe; Apache-2.0; Rust + Postgres/pgvector; created Aug 2026, v0.1): a bitemporal enterprise knowledge graph. **Its Sept 2026 governance design is the closest prior art to this project:** an LLM adjudicator auto-decides duplicate-entity merges at confidence ≥ 0.8, a tool-using "second look" handles unsure cases, then a human queue; every look is an `agent_decisions` row; human rationales return as precedents; a **fuse** switches automation off after two reverts in a week; 96.9% agreement on 589 hand-labelled pairs. Limits: entity resolution only, **one model for both tiers, self-reported (uncalibrated) confidence**, documents only (no email/calendar), no action gating yet.

### 13.2 What the memory tools actually do in 2026

- **Mem0**: open-source v3 (Apr 2026) is **ADD-only** — no update or delete, contradictions coexist; graph memory removed from open source; OpenMemory (local MCP) sunset and deleted (Jul 2026).
- **Graphiti/Zep**: bitemporal fact edges with invalidation; edge dedup and contradiction resolution go to a static "small model" slot with **no confidence and no escalation**; no Postgres backend; Zep Community Edition deprecated.
- **Letta** moved to Letta Code (git-backed memory filesystem, "dreaming" consolidation); rule-based permission modes.
- Others: Cognee, MemOS, Supermemory (claims contradiction handling, self-reported), Hindsight (facts vs experiences, proof counts, PII redaction at write), Honcho (statically tiered cloud models), Basic Memory (Markdown + SQLite over MCP), AnythingLLM (confidence-rated memory candidates filtered by the same model), Hermes Agent (an auxiliary model **approves / denies / escalates** shell commands; mines approval history into allowlist suggestions), Second Me (LoRA+DPO "AI self" — dormant; illustrates the slow, uncitable parametric route).

### 13.3 Evidence that the problems are real

| Failure | Evidence | Implication |
|---|---|---|
| Junk writes | A 32-day audit of **10,134 Mem0 memories found 97.8% junk** (mem0 #4573) — restated system prompts, cron noise, transient tasks, hallucinated profiles from a 2B local model, leaked secrets. Notion's Lore pilot: only 55–60% of stored memory stayed useful. | A **System 1 write gate** (noise? duplicate? transient? sensitive?) is the most defensible S1 use. |
| Silent wrong contradictions | Graphiti's small-model judge invalidated 41% of ~3,950 facts; 3 of 4 audited were collateral (graphiti #1728). | Contradiction decisions need calibrated confidence, escalation and a **visible, reversible** record. |
| Silent failures | "Success" returned while dropping data (graphiti #1707, mem0 #5245, gbrain #5012). | Nothing silent: every decision and write gets an outcome row. |
| Opacity and staleness | Complaints about ChatGPT's "Dreaming" memory (Jun 2026); Gemini admits over-personalization. | "Why do you believe this?" on every fact; bitemporal validity; refuse when stale. |
| Ingestion cost | ~$0.80 per 40 short chats with Graphiti (#467); GBrain's always-on path is its "highest-cost" mode. | Settle most decisions locally in S1; show the calls avoided. |
| Acting agents get owned | OpenClaw's one-click RCE (CVE-2026-25253) and 341→824 malicious skills. | Gate every outbound action; treat inbound content as untrusted. |

### 13.4 Novelty verdict

Each **mechanism** has precedent (Utopia's decision ledger and precedents; Claude Code's single-token-then-reasoning gate; Hermes' approve/deny/escalate; GPT-5's learned router; KnowNo; SOFAI). What nobody ships is the **combination for a personal, local brain**:

1. one decision fabric spanning **memory decisions** (write, merge, contradict, retrieve, relevant, grounded) **and actions** (send, schedule, pay);
2. a separate **small local System 1 with measured calibration** (reliability curves, per-decision thresholds) rather than self-reported confidence;
3. a **user-facing ledger** of every decision (tier, confidence, evidence, latency, outcome);
4. **learning that feeds back into System 1** — precedents, recalibration, fine-tuned adapters — with a visible falling escalation rate.

Judges should be shown the delta against Utopia, Claude Code and Hermes explicitly: "the pattern is proven; we bring it to a sovereign personal brain, calibrated and fine-tuned on the owner's own corrections."

---

## 14. Synthesis: design principles for the rebuild

1. **One store, raw first.** Postgres holds every raw item once (duplicates collapse, every original location is kept), retrieval chunks with keyword and vector indexes, beliefs, judgements and actions. Everything derived can be rebuilt from the raw items (§1.2, §3.6, §4.2).
2. **Four tiers, code first.** S0 code decides everything decidable; S1 answers typed one-token questions with calibrated probabilities; S2 takes the uncertain middle band and all writing; the human takes what neither settles and every consequential action (§5, §6, §8).
3. **Typed questions as the only interface to System 1** — yes/no, choice, score, the same shapes as Jev — so every judgement is loggable, calibratable, cacheable and trainable the same way (§10.3a).
4. **Calibrate, then set bands by target.** Temperature per (decision, model); thresholds from a precision or recall target with a confidence bound; recalibrate on drift and after every adapter (§1.3, §8).
5. **Every judgement goes into one hash-chained ledger**, which is also the cache (never score the same prompt twice), the audit trail, and the training set (§2, §11.5).
6. **Gate before generating; verify generation in code.** One-token gates decide which items deserve an extraction call; extracted quotes must occur verbatim in the source; dates are resolved by code against the message date (§3.4, §4.1).
7. **Beliefs are bitemporal and append-only.** Superseding closes the old belief's recorded range; conflicts keep both versions; changed decisions go to the human (§1.4, §3.6).
8. **Fine-tune the judge on the owner's own behaviour and on ground truth, not on facts.** Replies, filing, benchmark answers and corrections are the labels; split by item and time; compare before/after on the same runtime (§9).
9. **Models can only add caution to actions.** Code tier tables, approval tokens bound to action hashes, budgeted interruptions, outbox delays and compensators (§11).
10. **Measure everything that is claimed**: recall@k, calibration, settle rate at a target, cascade accuracy, latency, model calls per item — on this person's data, with fixed baselines (§3.5, §4.4, §10.4).

---

## 15. Contested and open questions

- **How far can a fine-tuned 1–2B judge go on this person's decisions?** The literature suggests far (§9.1), but no study covers one person's email judgements; this build measures it.
- **Is 95% precision the right target everywhere?** A tight target leaves more for S2 and the human; the right target differs by decision (relevance can be looser than an approval gate). Calibration sets of ~100–400 per decision make the bounds wide.
- **Guarantees are relative to the oracle and assume no drift.** A person's mail changes with seasons and roles; calibration must be refreshed, and S2 itself audited against the human on a sample (§1.3, §8.2).
- **Cascade or route first?** Label-sized decisions favour cascading; long generations favour routing before generating (§6).
- **Does "thinking" help calibration?** The evidence is split (§8.1); measure locally.
- **Graph or no graph?** Graphs help some question types when extraction is good and lose badly when it is not (§3.5, §4.3).
- **Language coverage.** Indian business email mixes English, Hindi and regional languages; neither the benchmarks nor the small guard models cover this well (§10.3, §11.1).
- **Personal data law.** Whether a sole proprietor's assistant falls under DPDP's personal/domestic exemption is untested (§12).

---

## Appendix A. Local System 1 probe on the M5 Pro

**Question.** Can the models already on the machine act as a System 1 — answer a yes/no question in one output token and report a usable probability, fast enough to sit in front of every decision?

**Method.** 16 hand-labelled items written in the style of a busy Indian SME owner's inbox, across four decision types: *does this ask the owner to act?* (6), *does this go against a stored decision?* (4), *does this text contain instructions aimed at an AI or automated system?* (3), *do these two messages ask for the same piece of work?* (3). Each call: Ollama `/api/chat`, `think:false`, temperature 0, `num_predict: 1`, `logprobs: true, top_logprobs: 10`. P(yes) = mass of yes-variants ÷ (yes + no mass) among the top first-token candidates — read from the logits, **not** self-reported. Wall time measured from Python with the model loaded. Script and raw numbers: [`probe/`](probe/). **n = 16: indicative, not a benchmark.**

| Mode | Model | Correct | Brier ↓ | Median time per decision |
|---|---|---|---|---|
| one token | qwen3:1.7b | 13/16 | 0.139 | **34 ms** (prefill ≈ 5,400 tok/s) |
| one token | qwen3:14b | 15/16 | 0.061 | 198 ms (prefill ≈ 790 tok/s) |
| one token | qwen3:4b (thinking-only 2507 build) | unusable — ignores `think:false`, begins "Hmm, the user…" | – | – |
| JSON enum answer | qwen3:1.7b / 4b / 14b | 12/16 · 11/16 · 15/16 | 0.155 · 0.282 · 0.057 | 96 · 195 · 496 ms |
| **cascade**: 1.7b, escalate to 14b when 0.1 < P(yes) < 0.9 | 1.7b → 14b | **15/16** | – | **1.2 s** for all 16 vs 3.6 s 14b-only; 3/16 escalated |

- **Prefix caching:** a 958-token shared instruction prefix cost 551 ms of prefill on the first call and 64–69 ms on later calls with different items.
- **Contrast with "extract everything as JSON":** the 4B with a JSON schema took 1.36 s (105 output tokens) on a shortlist email and 2.12 s on a newsletter — and for the newsletter it *invented* a task with self-reported confidence 0.9. The 1.7B yes/no gate gave that newsletter P(actionable) = 0.000 in 57 ms.
- **What it does not show:** accuracy at scale, calibration per decision type, Hindi/Hinglish behaviour, or behaviour under GPU contention from other work.

## Appendix B. Research notes index

| File | Slice | Contents |
|---|---|---|
| [`notes/A-memory-architectures.md`](notes/A-memory-architectures.md) | A | Agent memory systems, their internal decision points, ingestion costs, benchmarks and disputes |
| [`notes/B-system1-routing-calibration.md`](notes/B-system1-routing-calibration.md) | B | Dual-process AI, cascades/routers, adaptive retrieval, calibration, conformal methods, distillation (~115 papers) |
| [`notes/C-system1-models-runtimes.md`](notes/C-system1-models-runtimes.md) | C | Small models, encoders, judges; Ollama/llama.cpp/MLX facts; measured latencies on this Mac |
| [`notes/D-db-theory-cogsci.md`](notes/D-db-theory-cogsci.md) | D | LMs vs databases, semantic operators and proxy cascades with guarantees, TMS/AGM, bitemporal data, entity resolution, cognitive science |
| [`notes/E-controlled-execution-security.md`](notes/E-controlled-execution-security.md) | E | MCP, prompt injection defences, approvals and fatigue, tamper-evident audit, DPDP; a 37-row S0/S1/S2/H checklist |
| [`notes/F-landscape-prior-art.md`](notes/F-landscape-prior-art.md) | F | GBrain, Utopia, Mem0, Graphiti, Letta, Hermes and ~30 more; commercial memory products; complaints; novelty check |
| — | G, H | The fine-tuning and efficient-construction slices were interrupted (twice) before writing notes. §4 and §9 were written from slices A, B and D, tool documentation verified directly, and measurements on the target machine |

The notes were written while the project was still framed as the earlier multi-agent "Omnitrix" secretary; their "Relevance to Omnitrix" paragraphs refer to that framing. The literature itself is unaffected.
