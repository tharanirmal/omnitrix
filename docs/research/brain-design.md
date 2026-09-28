# Rebuilding the brain: dual-process design, the System 1 decision map, and the fine-tuning plan

*Ideation document, 25 Sep 2026. Builds on [`lit-review.md`](lit-review.md); section references like "LR §8" point there. Nothing here is built yet — the forks that need your call are collected in §9.*

---

## 1. The idea in one paragraph

**A database answers queries; a brain makes judgements.** The brain we rebuild is a database of *beliefs* (every fact with its time, its source, its reasons and a confidence) wrapped in a controller that makes a very large number of small judgements — *is this worth remembering? is this the same person? does this contradict what we decided? is this passage relevant? is this claim supported? does this need approval?* Almost all of those judgements are **a choice, a yes/no, or a confidence**, so they are made by a **fine-tuned small local model (System 1) that answers with a single token and a calibrated probability** in ~35 ms. Only the uncertain middle band, and the genuinely generative work, goes to the big local model (System 2); only risky actions go to the human. Every judgement — whoever made it — lands in one tamper-evident **decision ledger**, and the owner's corrections become training data, so **the brain gets measurably faster and more accurate the more it is used, without anything leaving the laptop.**

## 2. Design goals and non-goals

**Goals**
1. **Efficient** — the model calls, tokens and seconds spent per ingested item are a first-class metric; most decisions cost one forward pass of a small model.
2. **Sovereign** — every model, store and log is local; memory and ledger are exportable and verifiable without the app.
3. **Trustworthy** — calibrated confidence rather than self-reported numbers; nothing silent; every belief explainable ("why do you believe this?") and reversible.
4. **Learnable** — System 1 is fine-tuned on the owner's own data and corrections, locally, and the improvement is shown on stage.
5. **Safe to act** — actions are gated by code and the human; models can only add caution.

**Non-goals**
- Storing knowledge in model weights (LR §1.1, §9). Fine-tuning teaches *skills*, not facts.
- A general chatbot. The product is the memory, the judgements and the controlled actions.
- Letting any model be the final word on an irreversible or external action (LR §11).

---

## 3. The escalation ladder

```
            ┌──────────────── every judgement is written to the DECISION LEDGER ───────────────┐
 item ─►  S0  code ──► S1  fine-tuned judge ──► S2  14B deliberator ──► H  owner
          rules,       one token + calibrated   only the middle band,     only risky actions,
          hashes,      probability; kNN over     generation, and           and corrections that
          SQL, policy  past decisions            teacher labels            become training data
          µs–ms        ~35 ms                    0.2 s – seconds           budgeted attention
```

**Rules of the ladder** (each backed in the literature review):

1. **Code first.** Anything decidable deterministically is decided by S0 — hashes, dates, authentication, hidden-text detection, permissions, tier tables (LR §11.2).
2. **One token, read from the logits.** S1 answers a fixed question with a label whose first token is distinct; the probability comes from `top_logprobs`, renormalized over the labels — never from a number the model writes (LR §8.1, §10.1).
3. **Calibrate per decision type**, with ~100–400 labelled cases, after every model or adapter change (LR §8.1).
4. **Three bands.** `p ≥ τ_hi` → accept · `p ≤ τ_lo` → reject · otherwise → S2; if S2 is unsure or disagrees → H. Thresholds are chosen for a **precision target** on destructive decisions (merges, drops) and a **recall target** on safety decisions (approvals, contradictions) (LR §1.3, §8.2).
5. **Margins for choices; both orders for pairs.** For k-way choices escalate on `p(top1) − p(top2)`; for pairwise questions ask in both orders and treat disagreement as uncertainty (LR §2, §8.1).
6. **Monotone safety.** For anything touching security or actions, `tier = max(S0, S1, S2)` — models can raise a tier or add a flag, never lower or clear one (LR §11.1).
7. **Experience before trust.** A decision type starts in "shadow mode" (S1 decides, S2 also decides, both logged) until it has N audited cases; a **fuse** demotes a decision type back to S2 after repeated human reversals (SOFAI, Utopia — LR §5, §13.1).
8. **Everything is logged and reversible.** Memory writes are bitemporal and never destructive; merges can be undone; the ledger is hash-chained (LR §11.5).
9. **Learn from the ledger.** S2 labels on escalated cases + owner corrections → nightly recalibration, precedent memory, and adapter fine-tuning (LR §6 Cache & Distil, §9).

---

## 4. The System 1 decision map — every place the brain only needs a choice, a yes/no or a confidence

Legend — **Out**: `bool` yes/no · `k-way` pick one of k · `score` graded/ordinal · `multi` several yes/no. **Tier**: the proposed first decider (escalation follows §3). **Guard**: what stops a wrong answer from doing damage.

### A. Ingest — *Data*

| # | The question | Out | Tier | Guard / escalation | Precedent (LR §) |
|---|---|---|---|---|---|
| D01 | Have I stored this exact item already? | bool | **S0** content hash | — | NoScope difference detector (§1.3) |
| D02 | Is this a near-duplicate or forwarded copy of something stored? | score | **S0** MinHash → **S1** only in the ambiguous band | Link, never delete | Blocking (§4) |
| D03 | Does it hide content (white/microscopic PDF text, Unicode tag or zero-width characters)? | bool | **S0 only** | Quarantine + visible badge | §11.2 |
| D04 | Is the sender who they claim to be (DMARC alignment, look-alike domain)? | bool | **S0 only** (S1 may rank near-misses for display) | A model can never clear it | §11.2 |
| D05 | Does this chunk contain instructions aimed at an AI or automation? | bool | **S1** (Judge or Prompt Guard 2) | Escalate-only: above τ → quarantine + taint; below τ ≠ trusted | §11.1 |
| D06 | Is this worth remembering at all (newsletter, notification, FYI, thanks)? | bool | **S1** | Precision-targeted; "drop" = archive, reversible | §13.3 (97.8% junk audit), App. A |
| D07 | What kind of item is it (invoice, quote, contract, meeting note, report, request, newsletter, voice memo…)? | k-way | **S1** (embedding head or Judge) | A misroute only adds checks | Probabilistic predicates (§1.3) |
| D08 | Which language/script (English, Hindi, Kannada, code-mixed…)? | k-way | **S0** script detection → **S1** for code-mixed | Selects prompts/models | §10.3 |
| D09 | How sensitive is it (public / internal / confidential / personal data)? | k-way | **S0** regex (PAN, Aadhaar, IFSC, account, phone) + **S1** additive | S1 may only raise | §12 (DPDP), §10.3 (GLiNER-PII) |
| D10 | Personal or work? | bool | **S1** | Scopes access | — |
| D11 | Does this outside item (news, regulation) matter to anything I track? | score | **S1** per (item × watched entity/project) | S2 writes the impact note | TASTI (§1.3) |

### B. Understand — *Knowledge*

| # | The question | Out | Tier | Guard / escalation | Precedent |
|---|---|---|---|---|---|
| D12 | Which sentences contain a to-do, a commitment, a decision, a meeting request, or a fact about someone? | multi | **S1** per sentence | Only positives are sent to extraction — the biggest single saving | Self-RAG gating (§7); App. A |
| D13 | Whose commitment is it — the owner's or the other party's? | bool | **S1** | Task vs promise | — |
| D14 | What kind of action (send, call, meet, review, write, decide, pay, buy, book, other)? | k-way (10) | **S1** label logprobs | Margin gate | §8.2 |
| D15 | Is the deadline hard, soft or absent? | k-way | **S1** | — | — |
| D16 | How big is it (15/30/60/120/240 min) and what kind of attention (focus/admin/any)? | score + k-way | **S1** + S0 history | Learns the owner's actual durations | Expected-score judgements (§8.2) |
| D17 | How specific is the proposed time (exact / window / vague / none)? Is a timezone named? | k-way + bool | **S1** → **S0** date arithmetic | Models never do date math | — |
| D18 | Which known person/company/project is this mention — or none of them? | k-way (≤5 + none) | **S0** blocking (alias, email, phone, GSTIN, embedding kNN) → **S1** *select* | Precision-targeted; new high-value entities → S2/H; merges reversible | ComEM, AnyMatch, Peeters (§4, notes D); Utopia (§13.1) |
| D19 | What type is a new entity? | k-way | **S1** | — | — |
| D20 | Which relation links these two (from the registry, "none", or "new type")? | k-way | **S1**; new types canonicalized by definition similarity → S2 | Schema grows deliberately | EDC, KGGen (§1.4) |
| D21 | Is this extracted item actually supported by its source sentence? | bool | **S1** grounding check | Unsupported extractions dropped | MiniCheck, Self-RAG `IsSup` (§7, §10.3) |
| D22 | How important is this person/company (0–3)? | score | **S1** proposal from interaction statistics → **H** confirms once | — | Need probability (§2) |
| D23 | Do these two figures refer to the same quantity (e.g. "6%" in the email vs "8%" in the PDF)? | bool | **S1** alignment → **S0** comparison | — | Claim-verification queries (notes D) |

### C. Remember — *Memory*

| # | The question | Out | Tier | Guard / escalation | Precedent |
|---|---|---|---|---|---|
| D24 | Write gate: keep, duplicate, transient, noise, or sensitive? | k-way (5) | **S1** | Junk never enters semantic memory | mem0 audit taxonomy (§13.3) |
| D25 | Given the most similar stored facts **about the same entity**: add, reinforce, refine, supersede, or conflict? | k-way (5) | **S1** → S2 middle band → H if a decision depends on it | Never delete; supersede closes a validity interval; conflicts keep both versions | Mem0 ops, Memory-R1 (§3); AGM/TMS (§1.4); Graphiti collateral-invalidation bug (§13.3) |
| D26 | Does this contradict a stored decision or commitment? | k-way (entails/neutral/contradicts) | **S1** per candidate → S2 explanation → H card | Recall-targeted | NLI, SummaC (§8), Self-RAG |
| D27 | Does this new message fulfil an open commitment? | bool | **S1** per (message × counterparty's open commitments) → **S0** marks on-time/late | — | GBrain lists this as *future work* (§13.1) |
| D28 | Does this decision replace an earlier one? | bool | **S1** → **H** confirm | Bitemporal supersession | §1.2 |
| D29 | Is this a durable preference or a one-off? | bool | **S1** + S0 frequency | — | — |
| D30 | Does it fit what I already know (fast path) or violate it (stay episodic until confirmed)? | bool | **S0** rules + **S1** | New bank account, new vendor → confirm first | Complementary learning systems (§2) |
| D31 | How available should this memory be now; archive it? | score | **S0** activation formula — no model | Archive, never delete; pin future deadlines | ACT-R (§2) |

### D. Recall and reason — *Reasoning*

| # | The question | Out | Tier | Guard / escalation | Precedent |
|---|---|---|---|---|---|
| D32 | Do I probably know this? (before searching) | score | **S0** familiarity of the question's entities *and* relations | Low → "I don't have this yet — shall I look?" | Feeling of knowing (§2); Mallen inverted (§7) |
| D33 | Which stores does this need (documents, facts, commitments, decisions, calendar, graph)? | multi | **S0** obvious cues → **S1** | Retrieve by default when a known entity is named | UAR, SKR (§7) |
| D34 | Which strategy: direct lookup, one retrieval, a multi-hop graph walk, or an SQL aggregate? | k-way | **S1** router | — | Adaptive-RAG (§7), TAG (§1.2) |
| D35 | Is this retrieved passage relevant? | score | **S1** (reranker or `IsRel`) | Keep top-k | Self-RAG, CRAG, Qwen3-Reranker (§7, §10.3) |
| D36 | Is the evidence sufficient to answer? | bool | **S1** + tiny logistic combiner | Widen search, ask, or abstain | Sufficient Context (§7) |
| D37 | Is each claim in the answer supported by its cited source? | bool per claim | **S1** | Strip or flag unsupported claims | MiniCheck; conformal back-off (§8.2) |
| D38 | Answer, ask one clarifying question, or abstain? | k-way (3) | **S1** + combiner | — | Abstention (§8) |
| D39 | Is this item affected by that change (ripple analysis)? | bool per neighbour | **S0** walk over reasons and relations → **S1** filter → **S2** impact memo | — | RippleEdits, TMS (§1.1, §1.4) |
| D40 | Is checklist item X satisfied by the documents? | bool per item | **S1** map → **S2** explains gaps | — | Map-reduce pattern (§11.2) |
| D41 | Does this need System 2 (or thinking mode) at all? | k-way | **S0** triggers + **S1** router | — | Hybrid LLM, RouteLLM, SwiftSage, Arch-Router (§5, §6) |

### E. Act — *Action*

| # | The question | Out | Tier | Guard / escalation | Precedent |
|---|---|---|---|---|---|
| D42 | Which action from the allowed menu for this step? | k-way | **S0** allowlist → **S1** action-selector | Menu is fixed per task | Action-selector pattern (§11.2) |
| D43 | What risk tier (T0 read … T4 delete/permissions)? | k-way | **S0** table (action class × recipient × data labels × taint) | **S1/S2 may only raise** | §11 |
| D44 | Does outgoing content reveal more than allowed? | bool | **S0** schema whitelist + regex; **S1** additive redaction | Models can only redact more | AirGapAgent (§11.4) |
| D45 | Does this action match what the owner actually asked? | bool | **S2** seeing only the request and the proposed action | Never removes the human step | §11.1 (small models fail here) |
| D46 | Which approval channel (none / digest / watch tap / phone + biometric / laptop)? | k-way | **S0 only** | — | §11.4 |
| D47 | Notify now, batch, put in the digest, or drop? | k-way (4) | **S1** trained on the owner's reactions | Only for low tiers; attention budget | Habituation, learning to defer (§8.2, §11.4) |
| D48 | Which tone for this recipient? | k-way | **S1** from past sent mail | S2 writes the draft | — |
| D49 | What did the owner mean by this reply (approve / reject / approve with edit / snooze)? | k-way (4) | **S1** → S2 applies an edit | Approval token bound to the action hash | §11.4 |
| D50 | Did the action happen exactly as approved? | bool | **S0** read-back vs approved hash | Alert + compensate | §11.5 |
| D51 | What should be remembered from the outcome? | k-way | **S1** (+S0 known patterns) | — | — |

### F. Maintain — the nightly "sleep" job

| # | The question | Out | Tier | Guard / escalation | Precedent |
|---|---|---|---|---|---|
| D52 | Should these episodes be consolidated into one fact or gist? | bool per cluster | **S1** → **S2** writes the gist | — | Sleep consolidation (§2); GBrain dream cycle (§13.1) |
| D53 | Are these two entity records the same (sweep)? | bool | **S1** select → S2/H | Reversible merge | Entity resolution (§4) |
| D54 | Should this recurring S2 resolution become a rule? | bool | **S0** (k consistent instances) → **H** approves | Rules are auditable | Instance theory, chunking (§2) |
| D55 | Should decision type X be recalibrated, retrained, or have its fuse tripped? | bool | **S0** statistics on the ledger | — | Utopia fuse (§13.1); online cascades (§6) |

### Tally

| | Count | Decisions |
|---|---|---|
| **Pure code (S0)** | 10 | D01, D03, D04, D31, D32, D43 (base), D46, D50, D54 (trigger), D55 |
| **System 1 first** | 42 | everything else except D45 — including all ingestion gates, entity linking, memory operations, contradiction and fulfilment checks, relevance, sufficiency, support, routing and notification |
| **System 2 first** | 1 judgement (D45) | plus the generative work below |

### What stays with System 2 (and why)

- **Writing**: replies and drafts in the owner's voice, answers with citations, impact memos, explanations of flagged conflicts, the morning brief.
- **Consolidation text**: per-entity "compiled truth" summaries and episode gists (§5.3).
- **Planning** novel multi-step requests (plan-then-execute, LR §11.2).
- **Free-text extraction fields** that are not labels (titles, amounts in context, quoted evidence) — only for sentences D12 marked positive.
- **Teacher labels** for System 1: the middle band online, bulk labelling offline.
- **Intent consistency** (D45) — the one *judgement* the literature says small models fail at.

---

## 5. As built (25 Sep 2026) — the `engram/` framework

Decisions taken with the owner of this project: **Postgres + pgvector** (Docker) as the single store; the **Enron mailbox of Vince Kaminski** (`kaminski-v`: 28,465 files, 44 personal folders, 8,623 sent) as the example person, with **EnronQA** as ground truth; the **personal System 1 judge** as the model to fine-tune (Qwen3-1.7B, bf16, MLX LoRA); **WorkBench** (a company sandbox whose tasks are graded by the state they leave, with a harmful-side-effect check) for agent workflows, and **QMSum**'s AMI product-team meetings as a second brain.

| Layer | Module | Decision-map items implemented | Evidence it works |
|---|---|---|---|
| Data | `sources/enron.py`, `text.py`, `store.py` | D01 (content hash), quoted-history splitting, threads, owner addresses, folders kept as labels | 28,465 files → 11,528 items in 2.8 s; parser fixes re-derivable in place (`rederive`) |
| Knowledge / retrieval | `index.py`, `sql/004_bm25.sql`, `sql/005_postings.sql` | D33–D35 substrate: BM25 over a postings materialized view + halfvec HNSW, weighted RRF, time/people/direction filters | recall@5 0.78–0.81, MRR 0.61–0.65 on EnronQA; keyword search 1.9 ms median, hybrid 28 ms per question including the embedding (LR §4.4) |
| System 1 | `judge.py`, `calibrate.py` | the typed-question interface (noul/choice/score), Ollama and MLX scorers, per-decision temperature, precision-targeted bands, S1 → S2 → human cascade with D41 routing measured on escalated cases, hash-chained ledger that is also the cache | the fine-tuned 1.7B settles 82.6% of `supported` at 99.3% accuracy (LR §10.5) |
| Ground truth | `labels.py`, `evaluate.py` | labels for D21/D37 (`supported`), D35 (`relevant`), D47-like personal behaviour (`replied`), D07-like personal taxonomy (`filed`) — all from benchmark answers or the owner's own actions, grouped by conversation | 5,958 labelled examples built in 44 s |
| Memory | `memory.py`, `sql/003_memory.sql` | D12 as one recall-first gate (round 2: S0 bulk rules → S1 `remember` p ≥ 0.2 → one S2 extraction that may find nothing; the three per-kind gates are gone), one extraction per gated item, D21 as a *code* check (quote must occur verbatim), D17 time in code, D25/D28 supersession with bitemporal rows | Runs end to end on real mail and meetings, with verbatim quotes, correct local-time resolution ("4 pm, Tuesday Oct. 30" → 22:00 UTC) and supersession. **Not yet selective:** the zero-shot gates passed 59 of 60 emails and 40 of 40 meeting segments to extraction, and the 14B turned newsletters and opinions into "commitments" and "decisions". The gates need calibration labels, like the four trained decisions got |
| Learning | `finetune.py` | chat-format data split by conversation, template check, LoRA with loss on the answer only | 54 min on the laptop. On held-out conversations the fine-tuned 1.7B beats the zero-shot 14B on all four decisions (`supported` 96.6% vs 95.5%; `relevant` 90.9% vs 87.5%; `replied` 60.1% vs 55.4%; `filed` 52.7% vs 47.9%) at a third to a fifth of the latency (LR §10.5) |
| Reasoning | `ask.py` | D35 (S1 drops surely irrelevant items and orders the rest) and D37 (S1 checks the answer against each cited item): System 1 checking System 2 with the same fine-tuned decisions | 100 held-out EnronQA questions: 70% correct (audited), 80% when the brain answers; when the judge vouches, 84% correct, otherwise 6% (AUROC 0.92; LR §10.6) |
| Action | `act.py`, `agent.py`, `sources/workbench.py` | D43 as a code table (read < internal < external < destructive); D45 as an S2 intent check that sees the request and a preview of the call, including the record it touches but no message bodies; a sure "no" blocks, an unsure verdict goes to the owner at any autonomy; D49-style approval as a callback; every check in the ledger | WorkBench, 60 fresh tasks: harmful side effects 40.0% with no gate → **6.7%** with the gate at default autonomy; tasks done right 38.3% → 48.3%; the owner is asked 0.62 times per task, against 0.97 for approval-only (13.3% harmful). One code fact in the preview (is this address in the directory?) takes harm to 3.3% at 0.53 prompts (post-hoc; LR §11.6) |
| Memory in Obsidian (round 2) | `vault.py`, `sql/006_vault.sql` | two-way: beliefs, people and sources as linked notes with Bases views; the owner's edits supersede (an owner-authored belief), deletions retract, new notes become beliefs or items, review verdicts become gate labels; files the owner changed are never overwritten | database test of every owner action; 119 beliefs → 300 notes on the example owner |
| Product | `serve.py`, `web/index.html` | the owner's view of every layer (round 2: a 3D force graph of the owner, people, items and beliefs that lights up what a question touches; adding data with every pipeline stage timed; a read-only SQL console under a non-superuser role): answers with the judge's verdict and sources, search with why each item was found, current beliefs with their quotes, the agent's calls with each gate decision and Approve/Deny on escalations, the ledger with a chain check. Standard library only; 127.0.0.1; refuses other origins and host names | end to end on the example owner (a blocked wrong recipient, the agent's self-correction and the owner's approval, in one run) |
| A second brain | `sources/qmsum.py`, `--brain` | one database per brain on the same server; AMI product-team meetings as undated, threaded items | 137 meetings → 1,555 items, 4,991 chunks in 2 s |

**Differences from the original plan, and why.**

- **Keyword search needed true BM25.** Postgres' ranking has no IDF, and recall@1 went from 0.20 to 0.48 with BM25. It was then made about 35× faster with a postings view and unprepared statements.
- **Calibration sets must be hundreds per decision.** A 95% precision target needs roughly 50+ correct examples on a side before anything can settle. That is cheap, because every label comes from ground truth the brain already has.
- **The ledger commits on its own connection,** so it can never commit a caller's unrelated work.
- **Escalation is decided by measurement, not tier order.** On exactly the cases the fine-tuned S1 escalates, the generic 14B was *less* accurate for every trained decision. Those decisions now go from an unsure S1 straight to the owner (D41 from the ledger, LR §10.5).
- **The intent check (D45) had to be phrased per step.** "Does it do what was asked and nothing more?" wrongly blocked single steps of multi-step requests: 19 of 46 wanted calls in the first 60 WorkBench tasks. "Is it one of the steps asked for?" fixed that systematic error: 8 of 31 wanted calls were blocked on fresh tasks. Even so, the 14B ranks wanted against unwanted calls only weakly (AUROC ≈ 0.61), because it cannot check which email is the latest without reading the mailbox, which context minimization forbids. So the model may only add friction, and full autonomy stays a choice the owner makes knowingly (LR §11.1).

<!-- DESIGN-REST -->
