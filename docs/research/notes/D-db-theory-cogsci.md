# D: "Is the brain a database?" Knowledge representation, DB theory and cognitive-science foundations for Omnitrix

Researcher slice D. Compiled 2026-09-25 for the MSRIT Hackathon, Track 1 (Sovereign AI), project **Omnitrix**. Omnitrix is a local-first second brain with about 15 agents, running Qwen3-14B as System 2, Qwen3-4B/1.7B as System 1, bge-m3, and Postgres 17 + pgvector, with an Obsidian vault.

**How sources were checked.** Every source marked as verified was checked against a primary record in this session. The records were one of these:
- the arXiv abstract page or arXiv HTML
- the ACL Anthology page
- the VLDB/CIDR proceedings index
- the publisher, W3C or PostgreSQL page
- the Crossref DOI record
- the Europe PMC record, which carries the publisher abstract
- an author-hosted PDF, whose text was extracted locally with a stdlib parser

Items that could only partly be checked are marked, and they are listed again in the "Unverified" section at the end. Quantities quoted here are the ones in the abstract or paper. Anything that is my own inference is labelled *(our inference)*.

---

## 0. TL;DR

1. **LMs are not databases, and the private long tail is where they fail worst.**
   - On LAMA/T-REx, BERT-large reaches P@1 = 32.3. That is close to an oracle-linked relation extractor (33.8), but it drops to 24.3 on N-to-M relations (Petroni 2019).
   - LLM factual accuracy collapses on torso and tail entities (Head-to-Tail, NAACL 2024).
   - Parametric editing breaks at scale and does not propagate ripple effects (Gupta 2024; Cohen 2024).
   - A businessman's vendors, promises and decisions are all tail facts. The LM should *read and write* memory; it should never *be* the memory.
2. **The DB community already built "System 1 / System 2" with statistical guarantees.** Examples: NoScope cascades, probabilistic predicates, SUPG, TASTI, LOTUS model cascades, BARGAIN (SIGMOD'26), ThalamusDB and SemBench.
   - The recipe is to score each item with a cheap proxy and learn two thresholds (τ−, τ+) from a small oracle-labelled, importance-sampled set.
   - Scores ≥ τ+ are accepted, scores ≤ τ− are rejected, and everything in between is escalated.
   - This gives a precision or recall target with probability 1−δ *relative to the oracle*.
   - That is exactly Omnitrix's "choice / boolean / confidence" gate, now with a defensible guarantee.
3. **Beliefs, not rows.** A second brain has to *accept* contradictory evidence and then revise. This goes beyond rejecting writes the way integrity constraints do.
   - The mechanism is Doyle's TMS (reasons attached to beliefs), de Kleer's ATMS (minimal assumption sets, "nogoods") and AGM revision (minimal change guided by entrenchment).
   - DB provenance, meaning why-provenance and provenance semirings, is the relational twin of TMS justifications.
4. **Time and provenance are first-class.** Use bitemporal records (valid time vs. transaction time), an append-only event log, and W3C PROV-style lineage. Together they give "what did I know when I approved X?" and auditable revision.
5. **Cognitive science gives concrete formulas, not just metaphors.**
   - ACT-R base-level activation for salience and forgetting: `B = ln Σ t_j^−d`, d = 0.5, with Petrov's O(1) approximation.
   - Anderson & Schooler's need-probability stopping rule for context packs.
   - Reder's cue-familiarity feeling-of-knowing as a *pre-retrieval* retrieve/compute gate: `P(retrieve) = Φ((A−T)/σ)`.
   - De Neys' margin-based uncertainty as the S1→S2 switch.
   - Logan/ACT-R/Soar compilation of S2 decisions into S1 instances and rules.
   - CLS/sleep-replay as a nightly consolidation job.

---

## 1. LMs vs databases; semantic operators; cheap proxies vs expensive oracles

### 1a. Are language models knowledge bases?

**[1] Petroni et al., "Language Models as Knowledge Bases?", EMNLP-IJCNLP 2019.** https://arxiv.org/abs/1909.01066 (ACL Anthology D19-1250). *Verified: arXiv page; numbers from the paper PDF.*
- **Idea.** Probe pretrained LMs with no fine-tuning, using cloze statements over KB triples (the LAMA probe). Knowledge is "retrieved" by ranking the fill-in token.
- **Numbers.** On T-REx, total mean P@1 is 32.3 for BERT-large, against 33.8 for relation extraction with *oracle* entity linking (Table 2).
  - By relation type, 1-to-1 relations reach 74.5 but N-to-M relations only 24.3.
  - On cloze-SQuAD, P@10 is 57.1 against 63.5 for DrQA.
  - The log-probability of the top prediction correlates strongly with correctness.
- **Relevance to Omnitrix.** (a) Parametric recall is partial and depends on relation type, so it is not a store of record. (b) Confidence does carry signal. That is the basis for using a small model's log-probs as a System-1 score, provided it is calibrated (§1e).

**[2] AlKhamissi et al., "A Review on Language Models as Knowledge Bases", arXiv 2204.06031, 2022.** https://arxiv.org/abs/2204.06031. *Verified: arXiv; aspects read from the PDF.*
- **Idea.** The review defines five properties a system needs to count as a KB: **Access, Edit, Consistency, Reasoning, and Explainability/Interpretability.** It argues these are natural in KBs and hard in LMs.
- **Relevance.** Use this list as the "is it a database?" rubric. Omnitrix gets all five from Postgres plus a justification graph, and uses the LM only as reader and writer.

**[3] Sun et al., "Head-to-Tail: How Knowledgeable are Large Language Models (LLMs)? A.K.A. Will LLMs Replace Knowledge Graphs?", NAACL 2024.** https://arxiv.org/abs/2308.10168. *Verified: arXiv.*
- **Idea and numbers.** A benchmark of 18K QA pairs stratified into head, torso and tail by popularity, run on 16 LLMs. Factual grasp is far from perfect, especially for torso-to-tail entities.
- **Relevance.** Personal knowledge (Balog & Kenter's PKGs, [42]) is almost entirely tail. That argues strongly for an explicit store in Omnitrix.

**[4] Mallen et al., "When Not to Trust Language Models: Investigating Effectiveness of Parametric and Non-Parametric Memories", ACL 2023.** https://arxiv.org/abs/2212.10511. *Verified: arXiv.*
- **Idea and numbers.** Uses PopQA (14K questions), 10 models and 4 augmentation methods.
  - LMs struggle with less popular facts, and scaling barely helps on the long tail.
  - Retrieval-augmented small models beat much larger unaugmented ones.
  - *Adaptive retrieval* retrieves only when the popularity of the entity is low. It improves accuracy and cuts inference cost.
- **Relevance.** This is an ML twin of the cognitive "feeling-of-knowing" gate (§6e). A *familiarity* signal, computed cheaply, decides retrieve vs. answer-from-parameters.

### 1b. Neural databases

**[5] Thorne et al., "From Natural Language Processing to Neural Databases", PVLDB 14(6):1033–1039, 2021.** http://www.vldb.org/pvldb/vol14/p1033-thorne.pdf. arXiv version: "Neural Databases", https://arxiv.org/abs/2010.06973. *Verified: arXiv plus PVLDB PDF listing.*
- **Idea.** A schema-less "NeuralDB" where both updates and queries are natural-language sentences.
  - Transformers can answer select-project-join queries *if handed exactly the relevant facts*. They cannot scale to large DBs and cannot do aggregation.
  - Fix: run many parallel Neural-SPJ operators over small fact sets chosen by a learned support-set generator, followed by a *symbolic* aggregation operator.
- **Relevance.** This is the template for Omnitrix's "brain." Keep retrieval scoped (Omnitrix already does), let the LM answer only over a small context pack, and do counting, sums and set operations **in SQL, not in the LM.**

**[6] Thorne et al., "Database Reasoning over Text", ACL-IJCNLP 2021 (Long), pp. 3091–3104.** https://aclanthology.org/2021.acl-long.241/. *Verified: ACL Anthology.*
- **Idea.** Introduces the WikiNLDB benchmark for queries like "list/count all X born in the 20th century" over text. The modular architecture scales to thousands of facts.
- **Numbers.** On small DBs, accuracy rises from 85% to 90% over the baseline. Accuracy is maintained at scale, where transformer baselines cannot encode the context.
- **Relevance.** Questions like "which promises to Sharma Traders are overdue?" must become *set queries* over extracted rows, not free-form RAG.

### 1c. Semantic operators: declarative LLM-powered query processing

**[7] Patel et al., "Semantic Operators: A Declarative Model for Rich, AI-based Data Processing" (LOTUS), arXiv 2407.11418 (v1 Jul 2024, v3 Mar 2025).** https://arxiv.org/abs/2407.11418. *Verified: arXiv and arXiv HTML v3.*
- **Idea.** Relational-style operators with natural-language parameters: `sem_filter`, `sem_join`, `sem_topk`, `sem_agg`, `sem_group_by`, `sem_map`, `sem_extract`, `sem_search`, `sem_sim_join`. Each operator's semantics is defined by a "gold algorithm", meaning the oracle LLM applied exhaustively. The optimizer then substitutes cheaper plans with accuracy guarantees relative to the gold.
- **Cascades.**
  - `sem_filter`: a small LLM's True/False log-prob is the proxy score. Per the v3 HTML, the system importance-samples a small fraction of the data (about 0.01%, minimum 100 tuples) and labels them with both proxy (e.g., Llama-8B) and oracle (Llama-70B). It then learns τ+ (a precision target at error δ/2) and τ− (a recall target at error δ/2) using a CLT/normal approximation. Items between the two thresholds go to the oracle.
  - `sem_join`: embedding similarity, or an LLM "project then similarity" step, serves as the proxy.
  - `sem_topk`: embedding-ranked pivot selection for quickselect. This is lossless.
- **Numbers.** Up to 1,000× fewer LLM calls for `sem_join` (BioDEX). Up to 3.6× faster than the highest-quality baselines. Up to 170% accuracy gains versus prior systems (abstract). A cascaded `sem_filter` gives about a 1.7× speed-up on a FEVER pipeline.
- **Relevance.** Omnitrix's System-1 questions are `sem_filter`s: is_noise, contradicts, needs_approval and so on. Entity resolution is a `sem_join`, and relevance ranking is a `sem_topk`. LOTUS gives both the API shape and the threshold-learning recipe.

**[8] Liu et al., "Palimpzest: Optimizing AI-Powered Analytics with Declarative Query Processing", CIDR 2025.** https://www.vldb.org/cidrdb/papers/2025/p12-liu.pdf. *Verified: CIDR 2025 index.*
- **Idea.** Declarative AI analytics over unstructured collections. A cost-based optimizer searches over models, prompting strategies and related optimizations, trading off runtime, dollar cost and output quality.
- **Follow-up [8b]: Russo et al., "Abacus: A Cost-Based Optimizer for Semantic Operator Systems", PVLDB 19(5):1060–1073, 2026 (VLDB'26).** https://arxiv.org/abs/2505.14661. *Verified: arXiv.*
  - Abacus optimizes quality, cost or latency *subject to constraints* on the other dimensions. It builds Cascades-style rule-based plan spaces and estimates performance from validation examples, priors and LLM judges.
  - **Numbers:** 6.7–39.4% better quality, 10.8× cheaper and 3.4× faster than the next-best system.
- **Relevance.** The S1/S2 router *is* a query optimizer. Frame it as "minimise cost subject to precision ≥ p on a predicate," not as ad-hoc if-else logic.

**[9] Shankar et al., "DocETL: Agentic Query Rewriting and Evaluation for Complex Document Processing", arXiv 2410.12189 (rev. Apr 2025).** https://arxiv.org/abs/2410.12189. *Verified: arXiv. Venue not verified.*
- **Idea.** LLM-powered map/reduce/resolve pipelines over documents. An agent rewrites the logical plan, for example by decomposing a map into chunked sub-maps, and validates candidates with LLM-based evaluation.
- **Numbers.** 25–80% higher accuracy than well-engineered baselines on 4 tasks.
- **Relevance.** DocETL has a "resolve" operator for entity canonicalization, and its decomposition rewrites fit Librarian's long-document extraction.

**[10] Liu et al., "SUQL: Conversational Search over Structured and Unstructured Data with Large Language Models", Findings of NAACL 2024, pp. 4535–4555.** https://aclanthology.org/2024.findings-naacl.283/ ; https://arxiv.org/abs/2311.09818. *Verified: ACL Anthology and arXiv.*
- **Idea.** SQL extended with free-text primitives (`SUMMARY`, `ANSWER`), so IR and structured access compose inside one formal, interpretable query produced by an LLM semantic parser.
- **Numbers.** On Yelp, it finds an entity meeting all requirements 90.3% of the time vs. 63.4% for a linearization baseline. On HybridQA it lands within 8.9% EM / 7.1% F1 of SOTA with no training data.
- **Relevance.** Researcher can emit SUQL-like queries against Postgres: `SELECT … WHERE answer(doc, 'is this a payment promise?') = 'yes'`. That makes reasoning inspectable.

**[11] Biswal et al., "Text2SQL is Not Enough: Unifying AI and Databases with TAG", CIDR 2025.** https://arxiv.org/abs/2408.14717. *Verified: arXiv and CIDR 2025 index.*
- **Idea.** Table-Augmented Generation has three steps: query synthesis, then query execution in the DB, then answer generation. Text2SQL covers only relational-algebra questions, and RAG covers only point lookups.
- **Numbers.** On the TAG benchmark, standard methods answer at most 20% of queries correctly.
- **Relevance.** This is strong evidence for the judges that "scoped hybrid retrieval → context pack" should become retrieval *plus* SQL execution *plus* generation.

**[12] Glenn et al., "BlendSQL: A Scalable Dialect for Unifying Hybrid Question Answering in Relational Algebra", Findings of ACL 2024, pp. 453–466.** https://aclanthology.org/2024.findings-acl.25/. *Verified.*
- **Idea.** A SQLite superset with LLM UDFs (`LLMMap`, `LLMQA`, `LLMJoin`) that encodes a multi-hop plan as one interpretable query, with type constraints on outputs.
- **Numbers.** 35% fewer tokens overall. On HybridQA, +8.63% over a naive end-to-end system with 45% fewer prompt tokens.
- **Relevance.** This is a light path for Omnitrix: LLM calls as typed SQL functions inside Postgres queries, via a PL/Python or app-side UDF.

**[13] Jo & Trummer, "ThalamusDB: Approximate Query Processing on Multi-Modal Data", Proc. ACM Manag. Data (SIGMOD) 2(3), 2024.** https://dl.acm.org/doi/10.1145/3654989 ; code https://github.com/itrummer/thalamusdb. *Verified: Semantic Scholar record and the author's GitHub.*
- **Idea.** SQL with natural-language predicates (`NLfilter`, `NLjoin`) evaluated by zero-shot models, with *deterministic approximate query processing*.
  - It shows lower and upper bounds that tighten as more tuples are processed.
  - It **asks the user for a small number of labels**, and the optimizer trades approximation error against compute time and labelling overhead.
- **Numbers.** Average 35.0× speed-up over MindsDB (exact baseline). Beats ABAE (sampling) in 78.9% of cases.
- **Relevance.** This is the closest DB analogue of "S1 → S2 → human." The human is treated as a *priced oracle* inside the optimizer, and results carry explicit bounds.

**[14] Lao et al., "SemBench: A Benchmark for Semantic Query Processing Engines", VLDB 2026.** https://arxiv.org/abs/2511.01716. *Verified: arXiv.*
- **Idea.** A benchmark across scenarios, modalities (text, image, audio) and operators (filter, join, map, rank, classify). It compares LOTUS, Palimpzest, ThalamusDB and BigQuery.
- **Findings, from the v2 HTML.** Cost varies by orders of magnitude across systems on the same query, and semantic joins dominate cost. Cascading smaller models before larger ones cuts cost with little accuracy loss. Operator coverage is still patchy.
- **Relevance.** Expect joins (entity resolution, "which email relates to which decision") to be the cost hotspot. Block them first (§4).

**[15] 2025–2026 follow-ups on guarantees and optimization.** *All verified on arXiv.*
- **Zeighami, Shankar & Parameswaran, "Cut Costs, Not Accuracy: LLM-Powered Data Processing with Guarantees" (BARGAIN), SIGMOD'26 (PACMMOD, DOI 10.1145/3769776).** https://arxiv.org/abs/2509.02896.
  - A cheap/expensive LLM cascade routed by log-prob confidence. It uses adaptive sampling and tighter statistical estimation to guarantee a target accuracy, precision or recall.
  - Over 8 real datasets it gives up to 86% more cost reduction on average than the prior state of the art, at the same guarantees.
  - **This is the most directly usable recipe for Omnitrix's S1/S2 gates.**
- **Sanmartino, Urban, Papotti & Binnig, "The Stretto Execution Engine for LLM-Augmented Data Systems", arXiv 2602.04430 (Feb 2026).** https://arxiv.org/abs/2602.04430.
  - *End-to-end* query guarantees. Error budgets are allocated across a pipeline by constrained (gradient-based) optimization, and KV-caching is used to create a continuum of cheaper physical operators.
  - Relevance: Omnitrix chains several predicates (noise → entity → contradiction → approval), and per-predicate guarantees compound.
- **Zhao et al., "Larch: Learned Query Optimization for Semantic Predicates", arXiv 2606.07923 (Jun 2026).** https://arxiv.org/abs/2606.07923.
  - Learns the evaluation order of semantic filters from predicted selectivities, via a GNN/RL or supervised variant, and exploits existing embeddings.
  - 3–19× lower token overhead than Palimpzest and Quest.
  - Relevance: order Omnitrix's cheap filters first (is_noise before contradicts).
- **Lee et al., "Evergreen: Efficient Claim Verification for Semantic Aggregates", arXiv 2604.26180 (Apr/Jul 2026).** https://arxiv.org/abs/2604.26180.
  - Compiles *claims* into declarative verification queries, with provenance capture, early stopping, relevance sorting and confidence sequences.
  - 3.1× cheaper at F1 0.94. With a weaker LLM it is 7.0× cheaper, at F1 0.87 vs. 0.83 for the baseline.
  - Relevance: this is the blueprint for Fact Checker ("is this summary claim supported by the rows?").
- **Trummer, "Implementing Semantic Join Operators Efficiently", arXiv 2510.08489 (Oct 2025).** https://arxiv.org/abs/2510.08489.
  - A block-nested-loop semantic join that batches rows from both sides into one prompt, with formulas for batch size under a context limit.
  - Relevance: batch entity-matching prompts (compare BatchER, §4).

### 1d. Proxy models for expensive predicates: the origin of the S1/S2 analogy in DB research

**[16] Kang et al., "NoScope: Optimizing Neural Network Queries over Video at Scale", PVLDB 2017.** https://arxiv.org/abs/1703.02529. *Verified.*
- **Idea.** Train *specialized* cheap models that mimic an expensive reference model on the target distribution, plus "difference detectors" that skip unchanged frames. A cost-based optimizer picks the cascade and its thresholds.
- **Numbers.** 265–15,500× real-time speed-ups, with accuracy within 1–5% of the reference network.
- **Relevance.** This is the original "System 1 = specialized distilled proxy." It is also an analogue of Omnitrix's *difference detector*: skip re-processing a document whose hash or content has not materially changed.

**[17] Lu, Chowdhery, Kandula & Chaudhuri, "Accelerating Machine Learning Inference with Probabilistic Predicates", SIGMOD 2018, pp. 1493–1508.** https://www.microsoft.com/en-us/research/publication/accelerating-machine-learning-queries-with-probabilistic-predicates/. *Verified: MSR page.*
- **Idea.** Cheap classifiers act as *probabilistic predicates* (PPs). They drop blobs that won't satisfy the query predicate, each parameterized to a target accuracy. The query optimizer then combines simple PPs to cover complex predicates, with no per-query training.
- **Numbers.** Query processing is up to 10× faster.
- **Relevance.** Build *reusable* S1 predicates (noise, language, topic, has-date, mentions-money) and let a planner combine them. Don't train a new gate for every agent question.

**[18] Kang, Gan, Bailis, Hashimoto & Zaharia, "Approximate Selection with Guarantees using Proxies" (SUPG), PVLDB 2020.** https://arxiv.org/abs/2004.00827. *Verified.*
- **Idea.** Defines *precision-target* and *recall-target* selection queries with a limited oracle budget. Uses proxy scores plus importance sampling to choose thresholds that meet the target with probability 1−δ. Naive thresholding can fail badly on these targets.
- **Numbers.** Up to 30× better query-result quality than baselines, for both precision-target and recall-target queries (abstract).
- **Relevance.** This gives the *semantics* Omnitrix needs. Safety gates such as needs_approval must be **recall-targeted**, so the system never misses one. Merges such as same_entity must be **precision-targeted**, so it never wrongly merges two people.

**[19] Kang, Guibas, Bailis, Hashimoto & Zaharia, "Semantic Indexes for Machine Learning-based Queries over Unstructured Data" (TASTI), SIGMOD 2022.** https://arxiv.org/abs/2009.04540. *Verified.*
- **Idea.** Build one *semantic index* whose embeddings are trained so that nearby records have similar oracle outputs. Proxy scores for *any* query come from the labels of nearby cluster representatives, so no per-query proxy is needed.
- **Numbers.** 10× cheaper to build than proxy annotation. Queries up to 24× faster. Theory: low embedding error implies downstream accuracy for a class of queries.
- **Relevance.** Omnitrix already has bge-m3 embeddings for every chunk. Label a few representatives per cluster with S2 and propagate those labels as S1 priors. This is effectively a free System 1 for many predicates.

### 1e. Synthesis: "System 1 = cheap proxy, System 2 = expensive oracle" and the guarantees DB theory offers

| DB concept | S1/S2 reading for Omnitrix | Guarantee available |
|---|---|---|
| Proxy score + oracle (NoScope, PP, SUPG) | S1 log-prob / embedding score; S2 = Qwen3-14B; human = top oracle | Precision **or** recall ≥ γ with prob. ≥ 1−δ, relative to the oracle, under i.i.d. sampling (SUPG, LOTUS, BARGAIN) |
| Two thresholds τ−/τ+ (LOTUS `sem_filter`) | Three-way decision: accept / reject / escalate | Each side at δ/2; the middle band sets the cost |
| Semantic index (TASTI) | Label cluster representatives once with S2; reuse for all predicates | Accuracy bound tied to embedding quality (theory in paper) |
| Cost-based optimizer (Palimpzest, Abacus, Larch) | Router chooses model, prompt and predicate order | Optimize cost s.t. quality constraint |
| End-to-end error budgets (Stretto) | Chains of gates (noise → entity → contradiction → approval) | Pipeline-level guarantee instead of per-gate |
| User labels as priced resource (ThalamusDB) | Ask the human only where marginal value is highest | Bounds that tighten with labels |

**Practical recipe for each Omnitrix predicate** *(our synthesis, following LOTUS/SUPG/BARGAIN)*:
1. Collect a calibration set of about 100–300 items. Sample preferentially where S1 is uncertain, but record the sampling weights. Label each item with S2. For high-risk predicates, a human labels S2's output on a sub-sample.
2. Pick τ+ as the lowest score whose *lower confidence bound* on precision (items with score ≥ τ+) is at least γp, at δ/2.
3. Pick τ− as the highest score such that rejecting everything ≤ τ− keeps the *lower confidence bound* on recall of positives at least γr, at δ/2.
4. At runtime, route score ≥ τ+ to ACCEPT, score ≤ τ− to REJECT, and everything else to S2. If S2 is itself uncertain, route to the human.
5. Log every decision, then recalibrate nightly or weekly. Monitor the escalation rate and drift. The guarantees break under distribution shift.
6. Caveat: the guarantees are relative to the *oracle* (S2), not to the truth. So S2's own accuracy has to be audited by the human on a sample, which gives a chained guarantee.

---

## 2. Truth maintenance and belief revision (vs. parametric knowledge editing)

**[20] Doyle, "A Truth Maintenance System", Artificial Intelligence 12(3):231–272, 1979.** DOI 10.1016/0004-3702(79)90008-0. *Verified: Semantic Scholar/Crossref record with abstract.*
- **Idea.** A subsystem that *records reasons (justifications) for each belief*, maintains the current belief set as assumptions change, and uses **dependency-directed backtracking** to find which assumptions caused a contradiction. It produces explanations from the recorded reasons, supports "dialectically arguing" modules, and lets a problem solver choose between alternative belief systems.
- **Relevance.** This is Historian's core data structure. Each decision or fact row carries the reasons it is believed. When a new email contradicts it, follow the reasons back to the culprit assumption instead of guessing.

**[21] de Kleer, "An Assumption-based TMS", Artificial Intelligence 28(2):127–162, 1986.** Author PDF: https://dekleer.org/Publications/An%20Assumption-Based%20TMS.pdf. *Verified: author PDF; text extracted.*
- **Idea.** Each datum gets a **label**, a set of *environments* (assumption sets) under which it holds. The ATMS keeps every label **consistent, sound, complete and minimal**. Inconsistent assumption sets are stored as **nogoods**, and supersets of nogoods are pruned.
  - Payoff: the system can work with inconsistent information, context switching is free, and retraction is avoided because many contexts coexist.
- **Relevance.** Omnitrix can hold *competing versions* ("delivery date per the PO" vs. "per the WhatsApp message") at the same time, each labelled with its source assumptions. It answers "under which sources is X true?" and shows the conflict set to the user rather than silently picking one.

**[22] Alchourrón, Gärdenfors & Makinson, "On the Logic of Theory Change: Partial Meet Contraction and Revision Functions", Journal of Symbolic Logic 50(2):510–530, 1985.** DOI 10.2307/2274239. *Verified: Crossref.* Background: Hansson, "Logic of Belief Revision", Stanford Encyclopedia of Philosophy, https://plato.stanford.edu/entries/logic-belief-revision/ (verified).
- **Idea.** There are three operations. *Expansion* adds a belief. *Contraction* removes one. *Revision* adds one while restoring consistency.
  - The rationality postulates are closure, success, inclusion, vacuity, extensionality and recovery.
  - The **Levi identity** defines revision as: contract by ¬p, then add p.
  - **Minimal change** (informational economy) means never dropping more than necessary.
  - **Epistemic entrenchment** means that under pressure, less entrenched beliefs are given up first.
  - SEP notes that *belief bases* (finite, non-closed sets) are the practical form. It also notes that *iterated* revision (e.g., the Darwiche–Pearl postulates) remains unsettled.
- **Relevance.** This gives Omnitrix a principled *plain-code* conflict policy. Revising with a new fact p means retracting the least-entrenched support of ¬p, then asserting p. Entrenchment is a deterministic score, which respects the rule "ranking is plain code".

**[23] Almeida & Casals, "From Doyle to AGM: A Survey and an Implementation Roadmap for Belief Change", arXiv 2608.14567 (May 2026; European Journal on AI 2026 per arXiv comments).** https://arxiv.org/abs/2608.14567. *Verified: arXiv.*
- **Idea.** Traces computational belief change from the Doyle–London taxonomy through AGM to post-AGM work, framed as an *implementation* roadmap.
- **Relevance.** A current (2026) reference to cite when judges ask "why TMS in 2026?"

**[24] Parametric knowledge editing: ROME and MEMIT.** *Both verified.*
- Meng, Bau, Andonian & Belinkov, "Locating and Editing Factual Associations in GPT", NeurIPS 2022. https://arxiv.org/abs/2202.05262
- Meng, Sen Sharma, Andonian, Belinkov & Bau, "Mass-Editing Memory in a Transformer", ICLR 2023. https://arxiv.org/abs/2210.07229 ; OpenReview https://openreview.net/pdf?id=MkbcAHIYgyS
- **Idea.** Causal tracing localizes factual recall to mid-layer MLPs. ROME applies a rank-one weight edit. MEMIT scales editing to thousands of facts on GPT-J (6B) and GPT-NeoX (20B).
- **Relevance.** Editing weights to "remember" is technically possible. But see [25] and [26].

**[25] Cohen et al., "Evaluating the Ripple Effects of Knowledge Editing in Language Models", TACL 2024.** https://arxiv.org/abs/2307.12976. *Verified.*
- **Idea and numbers.** RippleEdits has 5,000 edits. An edit must propagate to logically entailed facts; the paper's example is that a new parent implies a new sibling.
  - Existing editors fail to keep related knowledge consistent.
  - *A simple in-context editing baseline scores best.*
- **Relevance.** This directly justifies an explicit graph plus in-context facts over weight edits. Analyst's "ripple effects of a change" is a graph traversal over justifications and relations, which a parametric store cannot do.

**[26] Gupta, Rao & Anumanchipalli, "Model Editing at Scale leads to Gradual and Catastrophic Forgetting", Findings of ACL 2024.** https://arxiv.org/abs/2401.07453. *Verified.*
- **Idea.** Sequential ROME/MEMIT edits cause gradual forgetting of earlier edits and of downstream ability, then an abrupt collapse after enough edits.
- **Relevance.** A second brain changes daily, so weight edits are a non-starter for continual personal memory.

**[27] Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", NeurIPS 2020.** https://arxiv.org/abs/2005.11401. *Verified.*
- **Idea.** Pair *parametric* memory (a seq2seq model) with *non-parametric* memory (a dense index). The authors name provenance and knowledge updating as open problems for parametric-only models.
- **Relevance.** This is the canonical citation for Omnitrix's design rule: knowledge lives in the index and DB, where it is swappable, deletable and citable.

**[28] Buneman, Khanna & Tan, "Why and Where: A Characterization of Data Provenance", ICDT 2001, LNCS 1973, pp. 316–330.** DOI 10.1007/3-540-44503-X_20. https://www.research.ed.ac.uk/en/publications/why-and-where-a-characterization-of-data-provenance/. *Verified: Edinburgh research portal.*
- **Idea.** *Why-provenance* is the source tuples that justify an output's existence. *Where-provenance* is the source locations a value was copied from.
- **Relevance.** Every answer Omnitrix gives should carry its why-set (the witness rows and documents) and its where-links (the exact note, email or line).

**[29] Green, Karvounarakis & Tannen, "Provenance Semirings", PODS 2007, pp. 31–40.** Author PDF: https://web.cs.ucdavis.edu/~green/papers/pods07.pdf. *Verified: author PDF; text extracted.*
- **Idea.** Annotate tuples with elements of a commutative semiring and propagate them through positive relational algebra and Datalog.
  - Incomplete databases (c-tables, PosBool), probabilistic event tables, bag semantics and why-provenance all turn out to be instances of one algorithm.
  - Provenance polynomials are the most general case.
- **Relevance.** *(our inference)* ATMS labels, meaning minimal sets of assumptions, are essentially PosBool/why-provenance in minimal form. So one annotation mechanism in Postgres, an array of source-assertion IDs per derived row, gives Omnitrix TMS-style labels, citations *and* confidence propagation. For confidence, use a max-product "Viterbi" semiring in place of PosBool.

**Synthesis for §2: why non-parametric, revisable memory.**
- It passes all five KB properties [2].
- It is editable without ripple failure [25] or forgetting collapse [26].
- It is auditable and citable [27, 28].
- It supports principled revision (AGM) with explanations (TMS).
- It is *sovereign*: the user can inspect, export and delete it. None of that holds for weights.

---

## 3. Time and provenance

**[30] Snodgrass, *Developing Time-Oriented Database Applications in SQL*, Morgan Kaufmann, 2000.** Author-hosted: https://www2.cs.arizona.edu/~rts/tdbbook.pdf ; ACM Guide record https://dl.acm.org/doi/10.5555/320037. *Partially verified: bibliographic record only; the PDF text could not be extracted.*
- **Idea.** A standard treatment of **valid time** (when a fact is true in the world), **transaction time** (when the DB recorded it) and **bitemporal** tables in plain SQL.
- **Relevance.** Every Omnitrix assertion needs both times. A promise made on 3 Sept, recorded on 5 Sept, due on 30 Sept and retracted on 12 Sept is four different timestamps.

**[31] Kulkarni & Michels, "Temporal Features in SQL:2011", SIGMOD Record 41(3):34–43, 2012.** DOI 10.1145/2380776.2380786 ; PDF https://sigmodrecord.org/publications/sigmodRecord/1209/pdfs/07.industry.kulkarni.pdf. *Verified: PDF text extracted.*
- **Idea.**
  - **Application-time period tables** give valid time, with a user-named `PERIOD FOR`, `PRIMARY KEY (…, p WITHOUT OVERLAPS)`, temporal foreign keys, and `UPDATE/DELETE … FOR PORTION OF` that splits rows automatically.
  - **System-versioned tables** give transaction time with `SYSTEM_TIME`. Their history rows are system-maintained, and they are queried with `FOR SYSTEM_TIME AS OF / FROM … TO`.
  - **Bitemporal tables** combine both.
- **Relevance.** Use this as the schema vocabulary. It answers the Guardian audit question: "as of the moment I approved payment X, what did the system believe about vendor Y?"

**[32] PostgreSQL 18 release notes (released 25 Sept 2025): temporal constraints.** https://www.postgresql.org/docs/release/18.0/. *Verified.*
- **Idea.** PG18 adds non-overlapping `PRIMARY KEY/UNIQUE … WITHOUT OVERLAPS` and temporal foreign keys via `PERIOD`, over range columns backed by GiST. SQL:2011 system versioning is *not* included.
- **Relevance.** Omnitrix runs on **PG17**, so emulate this with `tstzrange` columns plus `EXCLUDE USING gist (entity_id WITH =, valid_period WITH &&)` (needs `btree_gist`). Model transaction time as an append-only history table, or use the event log below. Upgrading to PG18 gives native `WITHOUT OVERLAPS`.

**[33] Fowler, "Event Sourcing" (2005), https://martinfowler.com/eaaDev/EventSourcing.html, and "Bitemporal History" (2021), https://martinfowler.com/articles/bitemporal-history.html.** *Verified.*
- **Idea.** Store every state change as an immutable event, which enables complete rebuild, temporal query, replay and retroactive corrections.
  - Caveats: outbound effects to external systems must be *gated during replay*, and external query results must be recorded so replays reproduce them.
  - "Bitemporal History" separates *actual history* from *record history*. The worked example is a retroactive raise that makes an already-paid salary wrong, which then needs a compensating action.
- **Relevance.** This is Omnitrix's source of truth.
  - Every ingest, extraction, merge, approval and Operator action is an event. Semantic tables become *projections* that consolidation can rebuild.
  - Operator (the only agent that acts) must sit behind a replay-aware gateway, so no emails get re-sent on rebuild.
  - Retroactive corrections trigger Promise Keeper and Analyst checks for "actions taken on stale beliefs."

**[34] W3C PROV family (30 Apr 2013).** PROV-DM (W3C Recommendation), https://www.w3.org/TR/prov-dm/ ; PROV-Overview (WG Note), https://www.w3.org/TR/prov-overview/. PROV-O, PROV-N and PROV-CONSTRAINTS are also Recommendations. *Verified.*
- **Idea.** The core types are **Entity, Activity and Agent**. The core relations are wasGeneratedBy, used, wasInformedBy, wasDerivedFrom, wasAttributedTo, wasAssociatedWith and actedOnBehalfOf. Specializations include wasRevisionOf, wasQuotedFrom, hadPrimarySource and wasInvalidatedBy.
- **Relevance.** This is a ready-made, standard vocabulary for Omnitrix lineage:
  - Entity = document, chunk, assertion or summary.
  - Activity = an agent run, with model, prompt hash and parameters.
  - Agent = the user, a contact, an Omnitrix agent, or a model.
  - `actedOnBehalfOf` captures "Operator sent this on behalf of the user, approved by Guardian." `wasInvalidatedBy` captures retraction.
  - It is also a strong "sovereignty and auditability" story for judges.

---

## 4. KG construction and entity resolution with LLMs

**[35] Pan et al., "Unifying Large Language Models and Knowledge Graphs: A Roadmap", IEEE TKDE 2024.** https://arxiv.org/abs/2306.08302. *Verified.*
- **Idea.** Three frameworks: KG-enhanced LLMs, LLM-augmented KGs (construction, completion, KGQA) and synergized LLM+KG.
- **Relevance.** Omnitrix is "LLM-augmented KG" on the write path and "KG-enhanced LLM" on the read path.

**[36] Zhang & Soh, "Extract, Define, Canonicalize: An LLM-based Framework for Knowledge Graph Construction" (EDC), EMNLP 2024.** https://arxiv.org/abs/2404.03868. *Verified.*
- **Idea.**
  - (1) Open IE extracts free-form triples.
  - (2) The LLM writes a *definition* for each new relation or type.
  - (3) Canonicalize by retrieving semantically similar schema definitions and mapping to them, or add new types when no schema exists.
  - A trained retriever fetches the schema elements relevant to the input text, RAG-style, which lets it handle schemas too large for the prompt.
- **Relevance.** Omnitrix's schema must grow ("export licence", "GST credit note"). Keep a `relation_types(name, definition, embedding)` registry and canonicalize new relations by definition similarity. This is an S1 job, escalated to S2 when the similarity margin is small.

**[37] Mo et al., "KGGen: Extracting Knowledge Graphs from Plain Text with Language Models", arXiv 2502.09956 (v2 Nov 2025).** https://arxiv.org/abs/2502.09956. *Verified: arXiv. Venue not verified.*
- **Idea.** LLM extraction followed by iterative entity and edge *clustering*.
  - Embed with S-BERT, k-means into groups of 128, then retrieve the top-16 neighbours by fused BM25 and embedding.
  - The LLM marks exact duplicates (tense, plural, abbreviation) and picks a canonical alias. Repeat.
  - Also introduces the MINE benchmark.
- **Numbers.** MINE-1: KGGen 66.07% vs. GraphRAG 47.80% vs. OpenIE 29.84% (from the v2 HTML).
- **Relevance.** A concrete dedup loop for Librarian: blocking by embedding and BM25, then an LLM duplicate check, then canonical alias. It maps onto S1 for the "select duplicates" step and S2 for ambiguous clusters.

**[38] Lairgi et al., "iText2KG: Incremental Knowledge Graphs Construction Using Large Language Models", WISE 2024.** https://arxiv.org/abs/2409.03284. *Verified: arXiv (accepted at WISE 2024).*
- **Idea.** Four modules: Document Distiller, Incremental Entity Extractor, Incremental Relation Extractor, and Graph Integrator. New entities are matched to the global set by exact match, then by embedding cosine with a threshold of 0.7 (text-embedding-3-large).
- **Numbers.** Entity and relation resolution false-discovery rate is about 0–0.01, and schema consistency is 0.94–0.98. The authors themselves flag that entity *types* are not used in matching.
- **Relevance.** This is the minimum viable incremental ER for a hackathon. Improve on it by adding type and attribute blocking plus a calibrated τ−/τ+ instead of one fixed cosine threshold.

**[39] Li, Li, Suhara, Doan & Tan, "Deep Entity Matching with Pre-Trained Language Models" (Ditto), PVLDB 14(1), VLDB 2021.** https://arxiv.org/abs/2004.00584. *Verified.*
- **Idea.** Entity matching as sequence-pair classification with a fine-tuned small PLM (BERT, DistilBERT, RoBERTa), plus domain-knowledge injection, summarization of long strings, and data augmentation.
- **Numbers.** Up to 29% F1 over prior SOTA, and a further 9.8% from the three optimizations. It matches prior SOTA with at most half the labels. It reaches 96.5% F1 matching company datasets of 789K and 412K records.
- **Relevance.** The small-model baseline. A fine-tuned tiny matcher is a legitimate System 1.

**[40] Peeters, Steiner & Bizer, "Entity Matching using Large Language Models", EDBT 2025.** https://arxiv.org/abs/2310.11244. *Verified: arXiv. Details from the v4 HTML.*
- **Idea and numbers.**
  - The best LLMs match PLMs fine-tuned on thousands of examples with zero or few examples. GPT-4 zero-shot F1 on WDC Products is 89.61.
  - LLMs are **far more robust to unseen entities**. PLMs transferred across datasets lose tens of F1 points: about 22–61 for RoBERTa and 36–56 for Ditto.
  - A fine-tuned open model (Llama 3.1) exceeded GPT-4 on 4 of 6 datasets.
- **Relevance.** A small *general* model generalizes better than a small *specialized* PLM to new vendors and people, and light fine-tuning closes the gap. Omnitrix's contacts shift constantly, so prefer the general small LLM as S1, optionally LoRA-tuned on S2 labels.

**[41] Cost-aware LLM matching.** *All verified.*
- **Fan et al., "Cost-Effective In-Context Learning for Entity Resolution: A Design Space Exploration" (BatchER), ICDE 2024.** https://arxiv.org/abs/2312.03987 ; IEEE CSDL record https://www.computer.org/csdl/proceedings-article/icde/2024/171500d696/1YOtACyvPyg.
  - Batch several pairs per prompt and use covering-based demonstration selection.
  - **4–7× lower API cost** and +1.3–30.6% F1 on most datasets versus standard prompting. Fine-tuned PLMs needed ≥2,000 labels to match BatchER's ≤50.
- **Wang et al., "Match, Compare, or Select? An Investigation of Large Language Models for Entity Matching" (ComEM), COLING 2025.** https://arxiv.org/abs/2405.16884.
  - *Selecting* the match among candidates, which uses record interactions and global consistency, beats pairwise "match".
  - ComEM uses a **small LLM to filter obvious non-matches, then a larger LLM to select**. Evaluated on 8 datasets and 10 LLMs.
  - This is literally Omnitrix's S1 → S2 pattern for entity resolution.
- **Zhang, Groth, Calixto & Schelter, "AnyMatch – Efficient Zero-Shot Entity Matching with a Small Language Model", arXiv 2409.04073 (2024).** https://arxiv.org/abs/2409.04073.
  - A fine-tuned *GPT-2-class* model comes within 4.4% F1 of MatchGPT (GPT-4), with 4 orders of magnitude fewer parameters and **3,899× lower** inference cost per 1K tokens. It ranks second-best across nine datasets.
- **Papadakis, Skoutas, Thanos & Palpanas, "Blocking and Filtering Techniques for Entity Resolution: A Survey", ACM Computing Surveys 53(2), 2020.** https://arxiv.org/abs/1905.06167 ; https://dl.acm.org/doi/abs/10.1145/3377455.
  - ER is inherently quadratic. *Blocking* restricts comparisons to likely pairs, and *filtering* prunes pairs below a similarity threshold. The survey covers schema-agnostic blocking for messy, semi-structured data.
- **2026 follow-ups.**
  - Wang et al., "Adaptive Graph Refinement and Label Propagation with LLMs for Cost-Effective Entity Resolution" (Alper), arXiv 2605.25814. It mixes "weak but cheap" graph-propagation signals with "strong but expensive" LLM queries, with greedy selection under guarantees, and reports it beats cascaded pipelines. https://arxiv.org/abs/2605.25814
  - Pulsone, Shraga & Goren, "BEACON: Budget-Aware Entity Matching Across Domains", SIGMOD 2026. It selects out-of-domain training data by embeddings under a label budget. https://arxiv.org/abs/2603.11391
- **Synthesis: small vs large for pairwise matching.**
  - Small *fine-tuned* models can come close to GPT-4-class matchers at orders-of-magnitude lower cost (AnyMatch, Ditto). General LLMs are more robust to distribution shift (Peeters).
  - Per-pair calls are wasteful: batch them (BatchER, Trummer) and *select* among candidates instead of scoring isolated pairs (ComEM).
  - Blocking is mandatory before any model (Papadakis). Use cheap graph signals, such as shared phone, email, GSTIN or co-occurrence, before LLM calls (Alper).

---

## 5. Second-brain lineage (only what is useful)

**[42] Personal knowledge graphs.**
- **Balog & Kenter, "Personal Knowledge Graphs: A Research Agenda", ICTIR 2019, pp. 217–220.** DOI 10.1145/3341981.3344241 ; https://research.google/pubs/personal-knowledge-graphs-a-research-agenda/. *Verified.*
  - A PKG is structured information about entities *personally related to the user*, including ones that are not globally important. The paper sets out construction and usage challenges.
- **Skjæveland, Balog, Bernard, Łajewska & Linjordet, "An Ecosystem for Personal Knowledge Graphs: A Survey and Research Roadmap", AI Open 2024.** https://arxiv.org/abs/2304.09572. *Verified.*
  - Two core aspects: **individual data ownership** and **personalized services**. The PKG lifecycle is population, then representation and management, then utilization, with clear interfaces to data sources and services.
- **Relevance.** This is the academic name for Omnitrix's "sovereign second brain," with ownership as a defining property. Combine it with [3]: PKG entities are tail entities, exactly where LLM parameters fail.

**[43] Gemmell, Bell & Lueder, "MyLifeBits: a personal database for everything", CACM 49(1):88–95, 2006.** https://www.microsoft.com/en-us/research/publication/mylifebits-a-personal-database-for-everything/. *Verified: MSR page; PDF text extracted.*
- **Idea and lessons.**
  - The project started with files in folders, which "went from unwieldy to overwhelming". It moved to a **SQL Server database** of about 25 item types holding content, metadata and **links**, with Memex as the explicit blueprint.
  - Full-text search is *not enough*, because many items need other attributes.
  - Asking the user to act as a manual filing clerk fails, so annotation must be *automatic*.
  - Timelines and "stories" such as trip diaries add value.
  - Its table lists about 245K items and about 108 GB for Gordon Bell's archive.
- **Relevance.** This is a 20-year-old demonstration that "a second brain *is* a database at its core." Its open problem, automatic organization and annotation, is exactly what LLM extraction now solves. That is Omnitrix's pitch.

**[44] Bush, "As We May Think", The Atlantic Monthly, July 1945; Engelbart, "Augmenting Human Intellect: A Conceptual Framework", SRI Summary Report AFOSR-3223, Oct 1962.** Engelbart: https://www.dougengelbart.org/content/view/138/ (*verified*). Bush: The Atlantic URL could not be fetched (*partially verified*, see Unverified).
- **Idea.** The memex is a mechanized personal store with **associative trails**: named, user-built link chains between items. Engelbart's **H-LAM/T** (Human using Language, Artifacts, Methodology, in which he is Trained) frames augmentation as a *system* of tools plus methods plus training.
- **Relevance.** Trails correspond to typed links and saved query paths in the graph and Obsidian. H-LAM/T is a reminder that the demo must show a *method* (the daily brief, the approval flow), not just a store.

**[45] Luhmann's Zettelkasten.** Bielefeld University Luhmann Archive: https://www.uni-bielefeld.de/fakultaeten/soziologie/forschung/luhmann-archiv/ ; digital edition https://niklas-luhmann-archiv.de. *Verified: about 90,000 notes, 1951–1996, now an edited database. Numbering and link details come from the archive's description and are partly verified.*
- **Idea.** Atomic notes with *fixed identifiers*, dense cross-references and a keyword index. It worked as Luhmann's "theory-development and publication machine."
- **Relevance.** Stable IDs plus links plus an index is how Obsidian notes should mirror DB rows. Every Obsidian note should carry the DB UUID in frontmatter, so links survive renames and the TMS can point at them.

**[46] Forte, "Building a Second Brain": CODE (Capture, Organize, Distill, Express), PARA, and Progressive Summarization.** https://fortelabs.com/blog/basboverview/ (*verified*). The book (2022) is partially verified.
- **Idea.** Capture selectively. Organize by actionability (Projects, Areas, Resources, Archives). Distill by layered summaries. Express as output.
- **Relevance.** CODE maps one-to-one onto the Track-1 pipeline: Capture = Data, Organize = Knowledge, Distill = Memory/consolidation, Express = Reasoning → Action. PARA's *actionability* ordering is a cheap prior for activation (§6b): active projects get a salience boost.

---

## 6. Cognitive science to borrow

### 6a. Memory systems and consolidation

**[47] Tulving, "Episodic and semantic memory", in Tulving & Donaldson (eds.), *Organization of Memory*, Academic Press, 1972, pp. 381–403.** *Partially verified; see Unverified.* Modern restatement, verified: **Tulving, "Episodic memory: From mind to brain", Annual Review of Psychology 53:1–25, 2002**, DOI 10.1146/annurev.psych.53.100901.135114 (Europe PMC record).
- **Idea.** *Episodic* memory is personally experienced, time-and-place-stamped events, later framed as "mental time travel" with autonoetic awareness. *Semantic* memory is general knowledge detached from when it was learned.
- **Relevance.** Two stores:
  - `events`/`episodes` is append-only, with who, when, where and source.
  - `entities`, `relations`, `decisions` and `promises` are semantic, distilled from episodes, and link back to them.
  - Answers cite episodes; policies and plans use semantic facts.

**[48] Complementary Learning Systems.** *Both verified via Europe PMC and PubMed metadata.*
- McClelland, McNaughton & O'Reilly, "Why there are complementary learning systems in the hippocampus and neocortex…", Psychological Review 102(3):419–457, 1995. DOI 10.1037/0033-295X.102.3.419.
- Kumaran, Hassabis & McClelland, "What Learning Systems do Intelligent Agents Need? Complementary Learning Systems Theory Updated", Trends in Cognitive Sciences 20(7):512–534, 2016. DOI 10.1016/j.tics.2016.05.004.
- **Idea.** A fast system (hippocampus) stores specifics of single experiences. A slow system (neocortex) gradually extracts structure through *interleaved* replay, which avoids catastrophic interference. The 2016 update adds three points:
  - replay allows **goal-dependent weighting** of experience
  - recurrent activation of hippocampal traces supports some generalization
  - neocortical learning can be fast for **schema-consistent** information
- **Relevance.** Fast = the raw event log and chunk index. Slow = the curated semantic graph and compiled rules, updated in *batches* that replay episodes weighted by goals (open projects, due promises).
  - Schema-consistent facts, such as a new invoice from a known vendor, can be written straight to the semantic store by S1.
  - Schema-violating facts, such as a new vendor, a changed bank account or a contradiction, stay episodic until S2 or the human confirms them.

**[49] Klinzing, Niethard & Born, "Mechanisms of systems memory consolidation during sleep", Nature Neuroscience 22(10):1598–1610, 2019.** DOI 10.1038/s41593-019-0467-3. *Verified: Europe PMC abstract.*
- **Idea.** *Active systems consolidation* during slow-wave sleep. Hippocampal replay drives a gradual transformation and integration of representations into neocortex, coordinated by sleep oscillations. Memories become **abstracted, gist-like** representations, embedded in global synaptic downscaling.
- **Relevance.** This is the "sleep job" (§8, principle 9):
  - replay the day's events
  - re-extract with S2 at leisure
  - merge and deduplicate (downscaling)
  - write gist summaries (Forte's progressive summarization) into Obsidian
  - recompute activations
  - compile rules
  - It also makes a good demo moment: "Omnitrix slept on it."

### 6b. Rational memory, activation, spreading activation and forgetting

**[50] Anderson & Schooler, "Reflections of the Environment in Memory", Psychological Science 2(6):396–408, 1991.** DOI 10.1111/j.1467-9280.1991.tb00174.x. *Verified: Crossref; text extracted from PDF.*
- **Idea.** Memory availability tracks the *need probability* of an item in the environment. They studied three environments:
  - 730 days of *New York Times* headlines (1986–87)
  - child-directed speech (CHILDES)
  - **the senders of the first author's email (1985–89)**
- In all three, need odds follow power functions of recency and frequency, with spacing effects, mirroring the laws of human memory.
- Memories are considered in order of need probability, and search stops when p·G < C (expected gain below retrieval cost).
- **Relevance.** Their *email-sender* analysis is directly a businessman's contact memory. This justifies (a) power-law recency and frequency salience, not exponential TTLs, and (b) a *stopping rule* for context packs: add items in need order until marginal expected value is below token cost.

**[51] ACT-R declarative memory.**
- Anderson, Bothell, Byrne, Douglass, Lebiere & Qin, "An Integrated Theory of the Mind", Psychological Review 111(4):1036–1060, 2004. DOI 10.1037/0033-295X.111.4.1036. *Verified: Crossref.*
- Petrov, "Computationally efficient approximation of the base-level learning equation in ACT-R", ICCM 2006, pp. 391–392. Two-page abstract: http://act-r.psy.cmu.edu/wordpress/wp-content/uploads/2012/12/652petrovAbstract.pdf. *Verified: text extracted.*
- Derbinsky & Laird, "Computationally Efficient Forgetting via Base-Level Activation", ICCM 2012 (Berlin). https://iccm-conference.neocities.org/2012/proceedings/papers/0022/paper0022.pdf. *Verified: text extracted.*
- **Idea.**
  - **Base-level activation**: `B_i = ln( Σ_{j=1..n} t_j^(−d) )`, with t_j the time since the j-th use and default **d = 0.5**. It gives a spike after use, power-law decay, and accretion with frequency.
  - **Petrov's approximation** keeps only n, the lifetime t_n and the last k lags. Even k = 1 is nearly exact, so each item needs O(1) storage:
    `B ≈ ln( Σ_{i=1..k} t_i^(−d) + (n−k)(t_n^(1−d) − t_k^(1−d)) / ((1−d)(t_n − t_k)) )`
  - **Derbinsky & Laird** define an element as "decayed" when B < θ; their example uses d = 0.5 and θ = −2. Rather than scanning all items every step, they *predict the future time at which each item will cross θ* and index items by that time.
  - Standard ACT-R also adds context via **spreading activation**, `A_i = B_i + Σ_j W_j S_ji`, with retrieval if A_i exceeds a threshold. This form was not re-read from the 2004 PDF in this session; see Unverified.
- **Relevance.** A concrete salience and forgetting model for Omnitrix, computable in SQL. See principle 7.

**[52] Collins & Loftus, "A spreading-activation theory of semantic processing", Psychological Review 82(6):407–428, 1975.** DOI 10.1037/0033-295X.82.6.407. *Verified: Crossref.*
- **Idea.** Concepts are nodes in a semantic network. Activation spreads along links from primed concepts and weakens with distance and time; intersecting activation from two sources signals a relation.
- **Relevance.** Omnitrix's "detect entities, then restrict to linked documents" step is already one-hop spreading activation. Generalize it to bounded 2-hop propagation with fan-based attenuation, i.e. divide by node degree so hubs like the user don't flood the result. Use the summed activation as the S1 "familiarity" feature (§6e).

### 6c. Automatization and compilation: System 2 turning into System 1

**[53] Logan, "Toward an Instance Theory of Automatization", Psychological Review 95(4):492–527, 1988.** DOI 10.1037/0033-295X.95.4.492. *Citation verified via Crossref. Content from the abstract; the original PDF host refused connection.*
- **Idea.** Automaticity is *memory retrieval of stored instances* of past processing, not faster computation.
  - At each trial, the algorithm and the retrieval of prior instances *race*; whichever finishes first wins.
  - Practice adds instances and speeds retrieval, which gives a power-law speed-up, and the SD shrinks with the same exponent. Consistency is needed for retrieved instances to be valid.
- **Relevance.** Every S2 decision becomes a stored *instance* (normalized input, decision, justification). S1's first move is to look up near-identical past cases, via content hash and embedding kNN over a decisions table, and return the cached decision if it is consistent. S2 runs only when no instance matches, and the system gets cheaper with use, **measurably**: plot the power-law drop in S2 calls.

**[54] Taatgen & Lee, "Production Compilation: A Simple Mechanism to Model Complex Skill Acquisition", Human Factors 45(1):61–76, 2003.** DOI 10.1518/hfes.45.1.61.27224. *Verified: Europe PMC abstract.*
- **Idea.** ACT-R *combines and specializes* general, task-independent procedures into task-specific ones, folding retrieved facts into new rules.
- **Relevance.** Compile a recurring S2 chain, such as "retrieve vendor's payment terms, then compare to invoice date, then decide overdue", into a single parameterized SQL rule or check. This follows "scheduling and security checks are plain code".

**[55] Laird, Rosenbloom & Newell, "Chunking in Soar: The Anatomy of a General Learning Mechanism", Machine Learning 1(1):11–46, 1986.** DOI 10.1007/BF00116249. *Verified: Crossref.*
- **Idea.** When Soar hits an impasse, it deliberates in a subgoal. *Chunking* then caches the result as a new production conditioned on the features that mattered, so the impasse does not recur.
- **Relevance.** An escalation to S2 is an "impasse." Store the resolution *together with the minimal features that justified it*, which the TMS justification already provides. That produces a well-scoped rule, not an over-general one.

**[56] Sun, Slusarz & Terry, "The Interaction of the Explicit and the Implicit in Skill Learning: A Dual-Process Approach" (CLARION), Psychological Review 112(1):159–192, 2005.** DOI 10.1037/0033-295X.112.1.159. *Verified: Europe PMC abstract.*
- **Idea.** An explicitly dual-process architecture with both levels interacting (synergy effects). It argues for **bottom-up learning**: implicit knowledge first, then explicit rules *extracted* from it.
- **Relevance.** It adds the reverse direction to Logan and ACT-R. Periodically mine S1 and instance behaviour for explicit, human-readable rules, e.g. "emails from *@bank.* with 'OTP' → noise". Show them to the user for approval (Guardian), and make them auditable. That turns an opaque S1 into inspectable policy, which is a sovereignty win.

### 6d. Dual-process theory and its critiques

**[57] Evans & Stanovich, "Dual-Process Theories of Higher Cognition: Advancing the Debate", Perspectives on Psychological Science 8(3):223–241, 2013.** DOI 10.1177/1745691612460685. *Verified: Europe PMC abstract.*
- **Idea.** A *default-interventionist* view. Fast, autonomous Type 1 processes produce defaults unless Type 2 intervenes. Type 2 is defined by **hypothetical thinking and heavy working-memory load**, not by being "correct." The paper rebuts five lines of criticism while conceding some force.
- **Relevance.** S1 answers by default, and S2 is an *intervention* triggered by a monitor. Define S2 by *what it can do* (multi-document reasoning, counterfactual "what if this date slips"), not by being "the accurate one."

**[58] Kruglanski & Gigerenzer, "Intuitive and deliberate judgments are based on common principles", Psychological Review 118(1):97–109, 2011.** DOI 10.1037/a0020762. *Verified: Europe PMC abstract.*
- **Idea.** Both modes are rule-based, and the real question is *rule selection*. Deliberate judgment is not generally more accurate; accuracy depends on the rule–environment fit (ecological rationality). Frugal heuristics can beat more computation.
- **Relevance.** A useful critique for the pitch. Do not claim S2 is always better. Measure per-predicate accuracy of S1 and S2 on labelled data and route by *measured* ecological fit. Some predicates may never need S2, and some may need the human.

**[59] De Neys, "Advancing theorizing about fast-and-slow thinking", Behavioral and Brain Sciences 46:e111, 2023 (online 2022).** DOI 10.1017/S0140525X2200142X ; author PDF https://www.wdeneys.org/data/Advancing%20fast-and-slow%20BBS%20target.pdf. *Verified: text extracted.*
- **Idea.** De Neys critiques **exclusivity**, the assumption that some answers are only reachable by System 2, and the resulting **switch problem**. His working model is:
  - System 1 generates *multiple competing intuitions* with activation strengths.
  - An *uncertainty monitor* computes the strength **difference** between them.
  - If uncertainty exceeds a **deliberation threshold d**, System 2 is engaged. System 2's output feeds back into the strengths, and deliberation stops once uncertainty falls below d.
  - Intuitions arise through automatization of practised deliberation.
- **Relevance.** This is exactly an **S1 margin gate**: escalate when p(top1) − p(top2) < d, computed from S1 log-probs over the option set. The paper also backs the compile loop [53–55]. "Stop deliberating when uncertainty falls" gives S2 an early-exit rule.

### 6e. Metacognition: knowing whether you know, before searching

**[60] Nelson & Narens, "Metamemory: A Theoretical Framework and New Findings", Psychology of Learning and Motivation 26:125–173, 1990.** DOI 10.1016/S0079-7421(08)60053-5. *Verified: Crossref; Crossref metadata lists only Nelson.*
- **Idea.** There is an *object level* (cognition) and a *meta level* that holds a model of it. **Monitoring** is information flowing from object to meta; **control** is meta modifying the object (start, continue or stop search; allocate study).
- **Relevance.** This is the architecture diagram for the router. Monitoring signals (S1 margin, familiarity, calibration stats, escalation rates) feed a meta-level policy that controls whether to retrieve, escalate, stop or ask. The rule "security checks are plain code" makes the meta level deterministic and auditable.

**[61] Reder & Ritter, "What determines initial feeling of knowing? Familiarity with question terms, not with the answer", JEP:LMC 18(3):435–451, 1992.** DOI 10.1037/0278-7393.18.3.435. *Verified: Crossref and author-hosted PDF header.* Paradigm and model details verified via **Schunn, Reder, Nhouyvanisvong, Richards & Stroffolino, "To Calculate or Not to Calculate: A Source Activation Confusion Model of Problem Familiarity's Role in Strategy Selection", JEP:LMC 23(1):3–29, 1997** (author-lab PDF, text extracted), and Reder, "Strategy selection in question answering", Cognitive Psychology 19(1):90–138, 1987.
- **Idea: the "game-show" paradigm.** People had about **850 ms** to choose *retrieve* or *compute* for arithmetic problems.
  - If they chose retrieve, they got 1,400 ms to answer; if compute, 20 s. Payoffs rewarded fast correct retrievals.
  - Their choices were accurate. Separately, Reder (1987) found that explicitly choosing a strategy adds no net time.
  - The feeling of knowing was driven by **familiarity with the problem's terms, not by an early read of the answer**. Operator-switched problems (× vs +) produced *spurious* feelings of knowing.
  - The SAC model formalizes this as `P(retrieve) = Φ((A − T)/σ)`, where A is the activation of the most active problem node.
- **Relevance.** This gives a *pre-retrieval* gate that costs no LLM call.
  - Compute familiarity A from the base-level and spreading activation of the entities and relations detected in the question.
  - High A: take the fast path (scoped retrieval, S1 answer).
  - Low A: deep path (broad search, S2), or honestly answer "I don't have this, shall I look?"
  - Beware the spurious-familiarity failure: familiar *entities* with an unfamiliar *relation* ("Sharma's GST number") should require relation-level familiarity too.

**[62] Koriat, "How do we know that we know? The accessibility model of the feeling of knowing", Psychological Review 100(4):609–639, 1993.** DOI 10.1037/0033-295X.100.4.609. *Verified: Europe PMC abstract.*
- **Idea.** Feeling of knowing is *parasitic on the retrieval attempt*. It reflects the amount and ease of partial information accessed, whether correct or not. There is no privileged internal monitor.
- **Relevance.** This is a second, *post-retrieval* monitor. The amount and agreement of retrieved evidence (number of independent supporting chunks, score spread) is a feeling-of-knowing signal. But it can be confidently wrong when retrieval returns plentiful *incorrect* partial matches, so combine it with Fact Checker's support check.

**[63] Thompson, Prowse Turner & Pennycook, "Intuition, reason, and metacognition", Cognitive Psychology 63(3):107–140, 2011.** DOI 10.1016/j.cogpsych.2011.06.001. *Verified: Europe PMC abstract.*
- **Idea.** Initial intuitive answers come with a **Feeling of Rightness (FOR)**. A low FOR predicts longer rethinking and a higher chance of changing the answer.
- **Relevance.** Empirical support for gating S2 on S1's self-assessed rightness, which is the margin in [59]. Also log how often S2 *changes* S1's answer as a function of S1 confidence: that is the calibration curve for the gate.

*(Also see [4] Mallen et al.: popularity-gated adaptive retrieval is the ML analogue of cue-familiarity feeling of knowing.)*

---

## 7. Is it a database? The answer

**Short answer.** *The long-term memory of a sovereign AI brain should literally be a database. The "brain" is the set of processes around it:*
- *deciding what to believe (belief maintenance)*
- *deciding what is salient (activation)*
- *deciding whether it knows and whether to think harder (metacognition with guarantees)*
- *turning experience into faster skill (consolidation and compilation)*
- *acting under policy*

A sophisticated brain is a queryable database **plus a self-monitoring, self-optimizing controller**. It is **not** the LLM: LLMs are poor databases (§1a), and their proper role is the *semantic operator*, the thing that reads text into rows and evaluates fuzzy predicates.

### What DB theory already gives, and which brain function it maps to

| DB theory / feature | Brain function | Omnitrix component |
|---|---|---|
| Schema, integrity constraints, exclusion constraints (PG17 `EXCLUDE`, PG18 `WITHOUT OVERLAPS`) | Structured semantic memory; basic consistency | entities, relations, decisions, promises, tasks |
| Append-only log, event sourcing [33] | Episodic memory; replay | `events` table; Obsidian daily notes as a projection |
| Temporal DBs: valid and transaction time [30–32] | "When was it true" vs. "when did I learn it" | bitemporal assertions; Guardian's "as-of" audit |
| Provenance: why/where, semirings, W3C PROV [28, 29, 34] | Source monitoring; justifications; explanations | citations; TMS labels; confidence propagation |
| Incomplete and probabilistic DBs (c-tables, PosBool) [29] | Holding alternatives and uncertainty | ATMS environments; competing versions |
| Indexes (B-tree, GIN full-text, pgvector HNSW) | Retrieval cues, pattern completion | hybrid retrieval |
| Cost-based optimizer [8, 8b] | Strategy selection, effort allocation | S1/S2/human router as optimizer |
| Probabilistic predicates, proxy cascades with guarantees [16–19, 7, 15] | System 1 heuristics with *bounded error* | calibrated S1 gates (τ−, τ+) |
| Materialized views, incremental view maintenance | Consolidated, precomputed knowledge (gist) | nightly consolidation outputs |
| Deductive rules (Datalog), triggers (active DBs) | Inference, reflexes, habits | compiled S2→S1 rules; Promise Keeper triggers |
| Access control, row-level security, audit log | Inhibition and executive control | Guardian; the Operator gateway |

### What a "brain" adds beyond a DB

1. **Perception and understanding of unstructured input.** DBs assume a clean schema on the way in. The brain must *create* rows from prose and grow its schema (EDC [36], KGGen [37]).
2. **Fuzzy, open-world predicates.** "Relevant," "supported," "same person" and "contradicts" have no crisp SQL definition. They are *learned, priced, uncertain* operators, so every answer needs a confidence and a guarantee [7, 15, 18].
3. **Belief revision instead of write rejection.** A DB rejects writes that violate constraints. A brain must *accept* conflicting evidence, keep alternatives, and revise minimally by entrenchment (TMS, ATMS, AGM [20–22]).
4. **Need-driven availability.** DB rows are all equally available. A brain's availability tracks recency, frequency and context, i.e. need probability [50–52], and it forgets or archives gracefully.
5. **Metacognition.** DB optimizers estimate *cost*, never *probability of being right*. A brain knows whether it knows *before* searching [60–63], and decides whether to retrieve, compute, escalate or ask.
6. **Learning that rewrites its own fast paths.** Practice turns deliberation into retrieval and rules (Logan, ACT-R, Soar, CLARION [53–56]). DBs have adaptive indexing, but not *policy* learning.
7. **Consolidation and abstraction.** Offline replay produces gist and schemas (CLS, sleep [48, 49]).
8. **Goals and agency.** A DB never acts. The brain acts through Operator, under Guardian, and must reconcile actions taken on beliefs that were later revised (Fowler's bitemporal lesson [33]).

**One-line formula for the pitch** *(our synthesis)*: **Brain = DB of beliefs (bitemporal + provenance + justifications) + semantic operators (LLMs) + a metacognitive optimizer (S1/S2/human with guarantees) + maintenance (TMS, consolidation, forgetting, compilation) + policy-gated action.**

---

## 8. Principles → mechanisms for Omnitrix

1. **Store beliefs with reasons, not bare facts (TMS [20], PROV [34]).**
   - Schema sketch:
     `assertions(id, subj, pred, obj, valid tstzrange, recorded tstzrange, status IN|OUT|CONTESTED, confidence, entrenchment)`
     `justifications(id, assertion_id, antecedents uuid[], source_chunk_id, rule_or_prompt_hash, agent, model)`
     `nogoods(id, assertion_ids uuid[], detected_at, resolution)`
   - Historian answers "why do I believe X?" by walking justifications. A contradiction becomes a nogood row, not a silent overwrite.
2. **Revise by minimal change with an entrenchment score computed in plain code (AGM [22]).**
   - Entrenchment is a deterministic function of: source authority (signed contract > invoice > email > chat > inference), user confirmation, the number of *independent* justifications, and recency of valid time.
   - Apply the Levi identity: retract the least-entrenched support of ¬p, then assert p.
   - Never delete; close `recorded` (transaction time). Show the losing version on hover.
3. **Hold competing versions side by side when the evidence is truly split (ATMS [21]).** Keep both assertions with their environments, meaning their source sets. The UI says "per PO: 30 Sept; per WhatsApp from Ramesh: 5 Oct". Ask the human only when a *decision* depends on the difference: Guardian checks whether any pending action's justification includes a contested node.
4. **Ripple analysis is graph traversal, not weight editing (RippleEdits [25], TMS).**
   - When an assertion changes, a recursive CTE over `justifications` (consequents) and `relations` finds dependent decisions, promises and tasks.
   - Analyst re-evaluates only those, and Promise Keeper re-schedules the affected promises.
   - This beats parametric editing, which fails at ripples and collapses at scale [26].
5. **Every System-1 question is a cascaded semantic predicate with a statistical guarantee (SUPG [18], LOTUS [7], BARGAIN [15], PP [17]).**
   - For each predicate, store a `predicate_calibration(pred, tau_lo, tau_hi, target_type, gamma, delta, n_labels, calibrated_at)` row.
   - Use *recall targets* for safety predicates (`needs_approval`, `is_promise`, `contradicts_decision`) and *precision targets* for destructive ones (`same_entity` merge, `is_noise` drop).
   - Show on the dashboard: the guaranteed precision/recall, the escalation rate, and S2 calls saved. This is a judge-friendly technical highlight.
6. **Escalate on margin, not raw confidence (De Neys [59], Thompson [63]).**
   - Force S1 to score all options of a CHOICE and compute `margin = p1 − p2`.
   - If margin < d (calibrated), go to S2. If S2's margin is also < d₂, or the action is irreversible, go to the human.
   - S2 stops early when its margin clears d₂. Log how often S2 flips S1 per confidence bin (the "FOR curve").
7. **Salience and forgetting use ACT-R base-level activation (Anderson & Schooler [50], ACT-R [51]).**
   - Per memory item (entity, note, chunk, assertion), store `n_uses`, `first_seen`, `last_k_uses timestamptz[]` with k = 1–3.
   - Compute `B` with Petrov's formula and d = 0.5, using hours or days as the time unit.
   - Context activation is `A = B + Σ_j W_j·S_ji`, spreading from the question's entities with fan attenuation `S_ji = S − ln(fan_j)`.
   - Rank context-pack candidates by `relevance × f(A)`.
   - Forgetting means *archiving*, never deleting (Derbinsky & Laird): store `predicted_decay_at` (when B drops below θ), index it, and have a nightly job move expired items to a cold tier.
   - **Pin** anything with future valid time: open promises, deadlines and active PARA projects.
8. **Context packs obey a need-probability stopping rule (Anderson & Schooler [50]).** Add candidates in descending estimated need (activation × relevance). Stop when the marginal expected gain is below the token cost, or when a hard budget is hit. This makes "small context pack" principled and tunable instead of a fixed top-k.
9. **Episodic log + semantic store + nightly "sleep" consolidation (Tulving [47], CLS [48], sleep [49], Forte [46]).**
   - During the day, S1 writes episodes and *schema-consistent* facts only.
   - At night, the sleep job replays the day's episodes, weighted by goals (open projects, due promises), and does the following:
     - S2 re-extraction of flagged items
     - entity-merge sweeps
     - contradiction detection and nogoods
     - gist summaries written to Obsidian (progressive summarization)
     - activation recomputation
     - rule compilation (principle 10)
     - recalibration of S1 thresholds (principle 5)
10. **Compile System 2 into System 1 (Logan [53], ACT-R production compilation [54], Soar chunking [55], CLARION [56]).**
    - (a) *Instances*: cache every S2 decision with normalized input, features and justification. S1 first tries instance retrieval (hash, then kNN with a similarity threshold), racing against computation.
    - (b) *Rules*: when at least k consistent instances share a feature pattern, induce an explicit rule. Examples: a SQL predicate, a regex, or "sender domain + keyword → label". The rule goes to Guardian for human approval and gets utility statistics.
    - (c) Retract rules that later cause errors, as a TMS dependency.
    - Plot the power-law drop in S2 calls over time as a live demo metric.
11. **Bitemporal and event-sourced storage (Snodgrass [30], SQL:2011 [31], PG18 [32], Fowler [33]).**
    - All semantic tables carry `valid tstzrange` and `recorded tstzrange`. On PG17 use `EXCLUDE USING gist (entity WITH =, valid WITH &&)`.
    - The `events` table is the source of truth. Semantic tables are rebuildable projections.
    - Operator side effects go through a replay-aware gateway.
    - Retroactive corrections trigger a "stale action" check: any action whose justification was later revised.
12. **Provenance and citations everywhere (W3C PROV [34], why/where [28], semirings [29]).**
    - Every derived row has `derived_from uuid[]` (why-provenance), `where` spans (doc, offset), and `generated_by` (agent run, model, prompt hash).
    - Answers render minimal witness sets.
    - Confidence propagates by a simple semiring: max-product for derivations, noisy-OR for independent supports.
13. **Entity resolution: block → cheap match → select → enforce consistency (Papadakis [41], AnyMatch [41], ComEM [41], Peeters [40], BatchER [41], KGGen [37]).**
    - Block with deterministic keys (phone, email, GSTIN, PAN, normalized name) plus bge-m3 kNN.
    - S1 (1.7B/4B) filters obvious non-matches with a precision-target threshold.
    - S2 (14B) *selects* the match among the top-k candidates rather than judging pairs, in batched prompts.
    - Code enforces transitivity and cluster constraints. Merges touching money or commitments need human confirmation, and every merge is reversible (event-sourced).
14. **Ask the database, not just the retriever (Neural DBs [5, 6], TAG [11], SUQL [10], BlendSQL [12]).** Researcher and Analyst compile questions into SQL plus LLM UDFs (`sem_filter`, `sem_topk`). Lists, counts, sums and "which X since Y" go through the relational engine. The LLM only generates the final prose over the returned rows, which avoids the ≤20% failure mode of Text2SQL/RAG alone [11].
15. **Pre-retrieval feeling-of-knowing gate with honest ignorance (Reder & Ritter / SAC [61], Mallen [4], Koriat [62]).**
    - Before calling any model, compute familiarity A of the detected entities *and relations* from activations, then `P(known) = Φ((A − T)/σ)`.
    - Low familiarity means broad search or "I don't have this yet". High familiarity means the fast path.
    - After retrieval, a second monitor (evidence amount and agreement) plus Fact Checker's support check guards against confident-but-wrong answers.

---

## 9. Contested and open questions

- **Dual-process realism.** De Neys [59] and Kruglanski & Gigerenzer [58] reject strict exclusivity: S1 can produce "S2 answers," and S2 is not generally more accurate. Evans & Stanovich [57] defend a default-interventionist split.
  - *Implication:* present S1/S2 as a **cost continuum**: code/rules → 1.7B → 4B → 14B → human. Route by *measured* accuracy per predicate, and don't overclaim psychological fidelity.
- **Guarantees are relative to the oracle.** SUPG, LOTUS and BARGAIN guarantee S1 against S2 or gold labels, under i.i.d. sampling.
  - Personal data drifts (new vendors, festivals, tax season), calibration sets are small, and per-predicate δ's compound across a pipeline. Stretto [15] targets end-to-end guarantees.
  - Quantized small models' log-probs may be badly calibrated. That is the calibration slice (another researcher); check their notes.
- **Feeling-of-knowing can be fooled.** Cue familiarity yields spurious feelings of knowing [61], and accessibility-based FOK tracks the *amount* of retrieved material, even when it is wrong [62]. Familiarity gates must include relation-level familiarity and a post-retrieval support check.
- **AGM idealizations.** Its logically closed belief sets, and unresolved iterated revision [22], don't directly fit a large, noisy base. Practical systems use belief bases plus heuristic entrenchment, so the entrenchment weights are a *design choice* to expose and justify to the user.
- **Is the episodic/semantic split real?** Tulving himself revised the construct over 30 years [47]. For engineering the split is still useful: raw log vs. distilled facts.
- **CLS transfer.** Non-parametric stores don't suffer catastrophic interference, so the original "interleave to avoid interference" rationale [48] mostly doesn't apply. The value is in abstraction, compression, schema-consistency fast paths and goal-weighted replay.
- **Forgetting vs. audit and legal retention.** Activation-based archiving must not delete evidence needed for audit, disputes or tax. A true "forget this" request conflicts with append-only logs. One mitigation is per-subject encryption keys with key destruction ("crypto-shredding") *(our suggestion; not researched here)*.
- **ACT-R parameters.** d = 0.5 and the thresholds were fit on lab tasks. Anderson & Schooler's email data support power-law need functions, but Omnitrix should fit d and θ on its own access logs.
- **Is knowledge editing coming back?** Newer editors keep appearing. As of this survey, ripple consistency and scale remain unsolved [25, 26], and sovereignty (inspect, export, delete) favours explicit memory regardless.
- **Semantic-operator overhead at personal scale.** Optimizers and sampling pay off at scale. A single user's corpus may be small enough that 100–300 calibration labels per predicate is a real burden. Bootstrap with S2-as-oracle labels plus TASTI-style cluster propagation [19], and share calibration across similar predicates.

---

## 10. Unverified or partially verified (do not cite without checking)

- **LOTUS** is cited as arXiv 2407.11418. Publication in PVLDB/VLDB 2025 was *not verified* in this session.
- **DocETL** VLDB/PVLDB publication *not verified*; only the arXiv version was checked.
- **KGGen** NeurIPS 2025 acceptance *not verified*. The arXiv v2 includes a NeurIPS checklist, but that is not proof of acceptance.
- **AnyMatch** peer-reviewed venue *not verified*; arXiv only.
- **Snodgrass (2000)** definitions: the author-hosted book PDF could not be text-extracted. Only the bibliographic record was confirmed (via search results listing ACM Guide 10.5555/320037 and the arizona.edu PDF). The valid/transaction-time definitions above rest on Kulkarni & Michels [31].
- **Bush (1945)**: the Atlantic page could not be fetched. The title, venue and month come from search-result listings of an archived Atlantic copy (ETH Zurich-hosted PDF) and from MyLifeBits' description of Memex.
- **Tulving (1972)**: the chapter scan (alicekim.ca/EMSM72.pdf) could not be text-extracted, so editors and pages (Tulving & Donaldson, pp. 381–403) are from standard citation, not machine-verified. The concept is verified through Tulving (2002).
- **Logan (1988)**: the citation is verified via Crossref, but the abstract content comes from search-result snippets. The Vanderbilt PDF refused connection.
- **Luhmann (1981)**, "Kommunikation mit Zettelkästen": book, pages and publisher come from search snippets only. Details of the Zettelkasten's numbering and link scheme are only partly verified; the note count and dates are verified via Bielefeld University.
- **Forte's book** (Atria Books / Simon & Schuster, 14 June 2022, ISBN 9781982167387) is known only from retailer and search listings; the S&S page returned 403.
- **ACT-R equations beyond base-level learning** (spreading activation `A_i = B_i + Σ W_j S_ji`, `S_ji = S − ln(fan_j)`, logistic retrieval probability, latency `F·e^(−A)`) are from the standard ACT-R formulation (Anderson et al. 2004). They were not re-read from the PDF in this session because the act-r.psy.cmu.edu PDF link returned 404. The base-level equation and d = 0.5 *are* verified via Petrov (2006) and Derbinsky & Laird (2012).
- **de Kleer ATMS year.** The author PDF and the DOI indicate Artificial Intelligence 28(2), 1986. The Semantic Scholar record says 1987. Use 1986.
- **Nelson & Narens (1990).** Crossref metadata lists only Nelson. The standard citation includes Narens.
- **SemBench per-query cost and quality numbers** came from an automated summary of the v2 HTML. Only the qualitative findings are safe to quote without re-reading.
- **Peeters et al. per-dataset F1 and robustness numbers** came from an automated summary of the v4 HTML. Re-check before quoting exact figures.
- **LOTUS FEVER number.** The "~1.7× faster `sem_filter`" figure comes from the v3 HTML summary. The abstract-level numbers (up to 1,000× on `sem_join`, 3.6× faster, up to 170% accuracy) are safe.
- **Not used** because they could not be verified before the search budget ran out: Jensen & Snodgrass (TKDE 1999), Keren & Schul (2009), Diekelmann & Born (2010), and SUPG's exact importance-weighting scheme.

*Tooling note: the shared WebSearch budget (200 calls) ran out mid-session. Later checks used WebFetch against arXiv, Crossref, Europe PMC, ACL Anthology, proceedings pages and author PDFs.*
