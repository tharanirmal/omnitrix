# Round 2: gating, a faster brain, and a frontend that shows it

*26 Sep 2026. Builds on `engram/` as described in [brain-design.md](brain-design.md) §5; cites the literature review as LR §.*

Owner's decisions for this round:

- Obsidian holds the brain's memory, **two-way**.
- The brain graph is **3D** (three.js + 3d-force-graph, vendored locally).
- **qwen3:0.6b** joins the System 1 comparison.

## Where we start (measured)

| Path | Now | Why |
|---|---|---|
| Memory gates | 59 of 60 emails pass to extraction; newsletters become "commitments" | three zero-shot yes/no gates per item, uncalibrated; the escalated 14B answers "yes" at p ≈ 1.0 |
| Memory build | 13–33 s per item | nearly every item costs a 14B extraction plus same-belief checks |
| `ask` | 10–16 s | the small judge reads 10 whole emails (3–8k characters each, bf16): **4–15 s**; the 14B answer: 2–11 s |
| Search | 28 ms warm; 0.3–2.7 s when the embedding model has been evicted | models swapping under memory pressure |
| Adding data | ingest ~0.3 s, but keyword search needs a full rebuild of the postings view (~3 s) | the postings view is recomputed in full |

## A. Gating: decide what is worth remembering cheaply, then let the owner correct it

One question replaces the three per-kind gates: `remember`, meaning "does this item hold a specific commitment, decision or meeting involving the owner or their work?" Extraction then pulls whichever kinds are present, in the one 14B call it already makes. The gate is a cascade, cheapest first (LR §5, §6):

| Tier | What | Cost |
|---|---|---|
| S0 | rules for bulk mail: many recipients, list/no-reply senders, unsubscribe text | µs |
| S1a | a **linear probe on the bge-m3 embeddings already stored** for every chunk (the LR's "cheap embedding heads") | µs; no model call |
| S1b | a one-token LLM judge, only for the probe's uncertain band: qwen3:0.6b, qwen3:1.7b or the fine-tuned 1.7B, chosen by measurement | 30–300 ms |
| S2 | 14B extraction, only for items that pass | seconds |
| H | the owner in Obsidian: every delete or edit becomes a label | on the owner's schedule |

**Labels.** 14B teacher labels on ~600 items with a sharp rubric, checked against a hand-labelled gold set. Obsidian verdicts join as `human` labels. Splits are by conversation, as before (LR §9).

**Measured.** Precision and recall of `remember` against gold; extraction calls per 100 items; seconds per item. Each tier's share of settled items.

## B. Obsidian as the brain's two-way memory

The vault holds three kinds of note:

- `Beliefs/`, one note per current belief. Its properties are kind, `[[actor]]`, `[[other]]`, due, status, confidence and `[[source]]`; the body holds the statement and the verbatim quote.
- `People/`, one note per person.
- `Sources/`, a read-only mirror of the items that beliefs come from.

An `engram.base` file gives Bases views: open commitments, decisions, meetings, and the review queue.

**Sync.** Import runs first, then export:

| Owner action in Obsidian | Effect in the brain | Label |
|---|---|---|
| Edits a belief's statement, date or people | a new belief by the owner supersedes it (bitemporal history kept) | `corrected` |
| Changes its status | the status is updated | — |
| Deletes the note | the belief is retracted | a negative label for the item's gate and extraction |
| Writes a new belief note | the note becomes an owner item plus a belief | — |
| Sets `verdict: keep` / `drop` on a review note | nothing else | a gate label |
| Writes any other note | the note is ingested as data, so the owner's own notes are searchable too | — |

**Conflicts.** The owner is the authority. An edited file is never overwritten; its edit is imported, then the file is re-rendered. Postgres keeps the full history.

## C. Latency and compute

1. **A cascade inside System 1 for relevance.** A probe on retrieval features (fused score, both ranks, cosine) settles the clear cases. The LLM judge sees only the uncertain ones, and only their best chunk, not the whole email.
2. **A faster judge.** The fine-tuned 1.7B fused and quantized to 4-bit (local), and qwen3:0.6b zero-shot, measured for accuracy and ms on the held-out labels (LR §10.2).
3. **System 1 answers first.** A small model drafts the answer from the top chunks. The fine-tuned judge checks it, and only unsupported drafts go to the 14B. This is the cascade applied to generation (LR §6).
4. **Trimmed context.** The 14B reads the top chunks, not ten whole emails.
5. **Caches and residency.** Query embeddings and answers are cached, and models are kept loaded, so there is no swapping.
6. **Incremental indexing.** Postings become a table updated per new chunk. Corpus statistics are refreshed lazily, since the error from a few new documents is negligible.

**Targets.** `ask` p50 ≤ 4 s at the same accuracy; warm search ≤ 40 ms; an added item searchable in ≤ 1 s. Measured on the same 100 held-out questions (accuracy audited as in LR §10.6).

## D. Frontend

- **Brain.** A 3D force graph of the owner, people, beliefs and sources, with directional particles. A query flies in and lights up what it touches (retrieved → kept → cited), and new data grows into the graph.
- **Query.** Ask and search, plus a read-only SQL console (a read-only transaction with a statement timeout) with example queries. It shows that the brain is a queryable database.
- **Add.** Paste text or drop `.txt`/`.md`/`.eml` files, and watch each stage: parse → chunk → embed → index → gate (which tier decided, at what p) → extract → belief → vault note.
- Memory, Act and Ledger are kept.

## Order

1. Teacher labels (14B on the GPU, in the background).
2. Obsidian sync (CPU, meanwhile).
3. Gate cascade and its evaluation.
4. Latency work and its evaluation.
5. Frontend.
6. Code review and docs after each part.

## Results (26 Sep 2026)

**A. Gate.** No model labels "worth remembering" well zero-shot: 60–72% against hand labels, even the 14B with reasoning. So the gate became recall-first:

- S0 rules drop ~20% of items and lose none;
- the S1 judge passes the rest;
- extraction may find nothing;
- the most borderline items go to Obsidian for the owner's verdict.

On 60 emails this took extraction from 59 items to 47, beliefs from 151 to 36, and time from 807 s to 255 s. Details: LR §10.7.

**B. Obsidian.** Two-way sync is built and tested for every owner action, including editing a note engram has since superseded (the edit corrects the current belief) and invalid values (skipped, never blocking). The example vault holds 119 beliefs in 300 notes.

**C. Latency.**

- The 4-bit fused judge is as accurate and 2.9× faster.
- `ask` p50 fell from 21 s to 11 s, with accuracy up.
- Drafting with a small model gives 1.7 s at −6 points (optional).
- An added item is searchable in 13 ms.
- Keyword search stays at 2 ms, after turning off JIT compilation.

Chunk-level judging, the retrieval-feature probe and qwen3:0.6b were measured and rejected. Details: LR §4.4, §10.8.

**D. Frontend.** The 3D brain graph (vendored 3d-force-graph) lights up retrieval → kept → cited for every question. Adding data shows each timed stage and the new beliefs growing into the graph. The SQL console runs under a non-superuser role after a read-only transaction proved insufficient: `COPY … TO PROGRAM` ran inside one.

**Review fixes.**

- An owner's edit of a superseded note forked memory into two current beliefs.
- A malformed status aborted the whole sync.
- A broken draft answer didn't fall back to the 14B.
- The static route allowed path traversal.
