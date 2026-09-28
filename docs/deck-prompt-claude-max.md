# Prompt for Claude Max: the Omnitrix pitch deck (9 slides)

**Attach before sending:**
1. `engram_template_8.pptx` (the template)
2. The screenshots from `Claude outputs/`:
   - `1280-dark-01-login.png`
   - `1280-dark-06-answer.png`
   - `1280-dark-07-atlas.png`
   - `1280-dark-09-agents.png` (despite its name, this shows the belief timeline)
   - `1280-dark-16-audit-verified.png`
   - `390-dark-views.png`

   Don't attach `1280-dark-13-add-done.png`: it shows a database login.
3. Optionally, a photo of the Galaxy Watch showing an approval card.

Then paste everything below the line.

---

You are an expert pitch-deck designer and technical writer. Build a **9-slide PowerPoint (.pptx)** for our MSRIT
Hackathon entry, Track 1 "Sovereign AI". The project is **Omnitrix**, a local AI secretary. Its brain is called
**engram**.

## 1. Use the attached template, exactly

Build the deck **on `engram_template_8.pptx`** by editing its slides, so its master, theme and background art carry
over. Do not recreate the style by eye. Keep its look exactly:

- **Background:** black `#000000`, with the template's own blob images (`ppt/media/image1–4.png`) as a full-bleed
  background on every slide. Rotate them across slides.
- **Titles:** Calibri, about 36 pt, centred and two-tone. The first words are grey `#A0A0A0` and the rest white
  `#FFFFFF`, e.g. "Storing is easy." in grey + "Judging is hard." in white.
- **Cards:** rounded rectangles, fill `#0E0E0E`, 1 pt border `#2C2C2C`.
- **Colours:** one accent only, amber `#F5B301`. Greys are `#A0A0A0`, `#5A5A5A` and `#E6E6E6`, plus white. **No
  other colours** anywhere, including in diagrams and charts.
- **Footer on every slide except the first:** "Omnitrix · MSRIT Hackathon · Track 1 Sovereign AI", 9 pt `#5A5A5A`,
  with the slide number at the right.
- **Blob art:** keep text off the blob art. Anything placed over a blob sits inside an opaque card.

## 2. Design rules

- **Not texty.** Each slide has at most about 30 words of body text: short labels, big numbers, and no paragraphs.
  Explanations go in the **speaker notes**.
- **Every slide gets a visual:** a diagram, a screenshot, a native chart, or an icon row.
- **Diagrams are clean SVGs** in the palette above: thin grey lines, amber for the one thing that matters, and
  Calibri labels. Insert each one as an image (SVG with a PNG fallback), and also save each SVG as a separate file.
- **Charts are native PowerPoint charts**, not images, with data labels on and greys plus amber.
- **Check your own work:** nothing overflows or overlaps, and margins are at least 0.5".

## 3. Facts: use only these

Every number on the slides must come from this list. Don't round, "improve" or add numbers. If you need a number
that isn't here, write **"TODO: need number for …"** on the slide instead of guessing.

**Setup:** one MacBook Pro (Apple M5 Pro, 24 GB). Postgres 17 + pgvector in Docker. Ollama and MLX for the models.
The example owner is the public Enron mailbox `kaminski-v`: 28,465 files → 11,528 items, ingested in **2.8 s**.

**The brain (engram):**
- It thinks in four tiers:
  - **S0**: code (parse, dedupe, dates, rules).
  - **S1**: a small judge, Qwen3-1.7B fine-tuned on the owner, giving one token plus a calibrated probability.
  - **S2**: Qwen3-14B, for the uncertain middle and all writing.
  - **H**: you.
- Every judgement goes into one **hash-chained ledger**, which serves as audit, cache and training data.
- Of the 55 judgements a brain needs, **10 are pure code, 42 go to System 1 first, and only 1** needs the large model
  first.
- **Memory:** commitments, decisions and meetings become **beliefs**. Each carries a verbatim quote (checked in
  code), a date resolved in code, and a trust tier (owner / engram / external / quarantined). Beliefs are
  **bitemporal**: nothing is deleted, and newer beliefs supersede older ones.
- **Search:** BM25 in SQL plus pgvector HNSW, fused. Keyword search takes **1.9 ms** and hybrid **28 ms**. An item
  is searchable **13 ms** after it arrives.
- **SQL:** everything is plain Postgres tables:
  - `items`, `chunks`, `beliefs`, `judgements` (the ledger), `labels`, `people`
  - `belief_links`, `plan_entries`, `herald_cards`

  A read-only SQL console uses a reader role with a 3 s limit. There is one MCP server with 9 typed tools for other
  AI agents.
- **How the brain assists the agent:** the agent calls the brain's tools (search, read, beliefs, people, SQL,
  check), and its `answer` only accepts ids a tool returned *and* that the judge finds supporting.

**Society of agents: 22 planned agents became 7 roles on one pipeline.** They are named lanes, not chatting LLMs:
- **Librarian:** ingests and files.
- **Researcher:** answers with cited sources.
- **Memory:** keeps promises and decisions, and checks whether they were fulfilled or contradicted.
- **Planner:** plans the day with an OR-Tools CP-SAT solver.
- **Operator:** acts in your tools; this includes the smart meeting reply.
- **Guardian:** gates every action.
- **Herald:** reaches you on the watch.
- **Diplomat** (demo): negotiates a meeting time with another person's engram, and every outgoing message needs
  your approval.

Why the roster was merged:
- Sequential multi-agent setups lose **39–70%** and amplify errors up to **17.2×** (Kim et al.).
- 44.2% of multi-agent failures come from system design (MAST).
- Persona prompts don't improve accuracy (162 roles tested).
- LLMs manage **33–48%** on calendar planning; a solver-checked plan reaches **93.9%**.

**Fine-tuning the LLM:**
- LoRA on Qwen3-1.7B, **54 min** on the laptop (MLX, peak 18 GB).
- Trained on **5,958 labels the brain already had**: the owner's own replies and filing, plus EnronQA answers. There's
  no hand labelling and no cloud teacher. Skills are trained, never facts: facts stay in the database, where they can
  be cited and deleted.
- Held-out accuracy (1.7B base / **1.7B fine-tuned** / 14B zero-shot):

  | Decision | 1.7B base | 1.7B fine-tuned | 14B zero-shot |
  |---|---|---|---|
  | supported | 83.7 | **96.6** | 95.5 |
  | relevant | 74.4 | **90.9** | 87.5 |
  | will reply | 44.6 | **60.1** | 55.4 |
  | folder (12-way) | 31.5 | **52.7** | 47.9 |

- **3–5× faster** than the 14B. Fused and 4-bit, the judge is **934 MB** and **2.9× faster again**, with no loss in
  accuracy (214 ms per email).
- It settles **82.6%** of "supported?" on its own, at **99.3%** accuracy.
- **Adapter v2** adds `remember`, `meeting_request` and `todo`:
  - `remember` improves from **67% → 80%** (AUROC 0.70 → 0.86); `meeting_request` from **66% → 75%**.
  - The brain routes each decision to whichever adapter is better at it.
  - The memory gate now keeps **94–95%** of memorable emails, while sending ~60% of them to the 14B instead of 99%.

**The Kotlin watch app (Herald):**
- Hardware and stack: a Galaxy Watch 5 on Wear OS 5, a Kotlin + Compose app, and direct Wi-Fi to the Mac. There's no
  phone app and no cloud push: a foreground service long-polls the Mac.
- It finds the Mac over **mDNS**. The Mac proves it holds the token (an HMAC of a nonce) before the watch sends the
  token.
- **Approvals:** a real sandbox email reply was approved on the wrist and ledgered **19 s** after the gate paused.
  Destructive actions are decided only on the laptop.
- **Voice:** the Mac transcribes with Whisper large-v3-turbo on MLX, **~0.5 s** for a 2.5 s clip (warm). "Remember …"
  becomes an owner belief.
- **Cards:** promises due within the hour, checks the judge couldn't settle, and new meeting requests. Code routes
  each card to buzz now or wait in the digest, with quiet hours 22:00–07:00 and at most **6 buzzes an hour**.

**Accuracy and safety:**
- Answers: **70%** correct on 100 held-out questions, and **80%** when it answers rather than saying it doesn't
  know. When the judge vouches, an answer is **84%** right, otherwise **6%** (AUROC 0.92).
- The action gate on 60 fresh sandbox tasks:
  - harmful side effects fall from **40.0% → 6.7%** (3.3% with a directory check);
  - tasks done right rise from **38.3% → 48.3%**;
  - **0.62** owner prompts per task, against 0.97 for approve-everything.

**Time and cost:**
- The memory gate on 60 emails: **807 s → 255 s**, and **151 → 36** beliefs (the junk gone).
- Answering: median **21 s → 11 s**, or **1.7 s** in draft mode.
- All models run locally, so there are no per-call API costs.

**Privacy:**
- **Zero cloud calls.** Even careful local + cloud delegation leaks private data on **7.5%** of queries (PAPILLON).
- India's **DPDP Rules 2025**: 1-year access logs, 72-hour breach reports, penalties up to ₹250 crore (from ~May
  2027).
- Vendor kill-switches are real: Rewind's local capture was disabled (Dec 2025), and Mem0's local server was sunset
  (Jul 2026).

**The problem, in numbers:**
- An audit of 10,134 Mem0 memories found **97.8% junk**.
- Graphiti's small-model judge invalidated **41% of ~3,950** facts, and 3 of 4 audited cases were wrong.

**Honest limits:**
- "Will they reply?" is only 60.1%, so it stays a suggestion.
- The watch speaks plain HTTP on the LAN.
- With Bluetooth on, the watch drops Wi-Fi when it sleeps.
- v2 lost ground on round-1 decisions, so those stay on v1.
- "Zero cloud calls" comes from the architecture; it was never measured with a network capture.

## 4. The 9 slides

For each slide, write the title, the minimal on-slide text, the visual, and 2–3 sentences of speaker notes.

1. **Intro (1 slide):** "Omnitrix", with the tagline "A local AI secretary that remembers, plans and acts, only with
   your OK." Add three pills: *Brain: engram · Track 1 Sovereign AI · MSRIT Hackathon*. Use `1280-dark-01-login.png`
   as a framed hero image, or keep it minimal.

2. **Problem statement 1: the problem.** Your work life is buried in email, meetings and notes, and today's AI
   memory tools either store junk, judge silently, or send it all to the cloud. Show three big numbers: **97.8%**
   junk (Mem0), **41%** of facts wrongly invalidated (Graphiti), and **7.5%** leaked (local + cloud). Use icons, not
   paragraphs.

3. **Problem statement 2: our answer, a personal AI.** Five tiles, each an icon plus 4–6 words:
   - **Personal AI:** learns how *you* judge.
   - **Locally hosted:** zero cloud calls.
   - **Fine-tuned LLM:** a 1.7B trained on you.
   - **Society of LLMs:** a fast small model, a slow large model, and you.
   - **Second brain:** memory with sources.

   Add one small SVG of the S0 → S1 → S2 → You ladder.

4. **Technical approach 1: the brain and the society of agents.** A full-width **SVG architecture diagram**:
   - a dashed boundary labelled "Your laptop · local only";
   - Sources → **engram** (amber outline) containing the S0/S1/S2/H tiers and the ledger → You (web app, watch,
     Obsidian vault, MCP tools);
   - underneath, the **7 role chips**, plus Diplomat marked as a demo;
   - a small "Postgres + pgvector" database icon with the main table names.

   Also show the one line "22 agents → 7 roles", and put the evidence in the notes.

5. **Technical approach 2: fine-tuning and the watch app.**
   - Left: an **SVG fine-tuning loop**: owner behaviour → labels → LoRA on the Mac (54 min) → the judge → the ledger →
     new labels. Beside it, a **native clustered column chart** of the four decisions (base / fine-tuned / 14B;
     fine-tuned in white or amber).
   - Right: an **SVG watch flow**: the gate pauses → long-poll → the watch buzzes → you tap → the ledger. Add a drawn
     round watch face showing "Approve? email.reply_email" with Deny / Approve, and the labels "mDNS + HMAC" and
     "19 s".

6. **Impact and benefits (1 slide).**
   - Six small tiles, each an icon, one big number and a label:
     - Private: zero cloud calls
     - Personalised: 96.6% vs 95.5%
     - Simplified: 7 roles and one watch tap
     - Time: 807 s → 255 s
     - Cost: 3–5× faster, 934 MB, no API costs
     - Accuracy: harm 40.0% → 6.7%
   - A **TAM / SAM / SOM** diagram as three concentric SVG circles. See section 5 for the numbers.

7. **Feasibility and viability (1 slide):** three columns.
   - **Compute:** one 24 GB laptop; the 934 MB judge; training in 54 min at an 18 GB peak.
   - **Brain latency:** a **native horizontal bar chart** of:
     - keyword search 1.9 ms, hybrid search 28 ms, searchable-after-add 13 ms
     - S1 judge 214 ms per email, Whisper ~0.5 s
     - answer 11 s median (1.7 s draft)

     Use a log scale, or label the bars clearly.
   - **Privacy:** zero cloud calls, the hash-chained ledger, DPDP-ready, and a DPDP penalty callout.

   One line for viability: "Runs today on hardware the owner already has."

8. **References (1 slide):** two columns, small type (the list is in section 6).

9. **Thank you:** "Thank you", with "Your brain, on your machine." and two pills: *github.com/tharanirmal/omnitrix*
   and *TODO: team contact*. Use the template's closing layout.

## 5. TAM / SAM / SOM: don't invent these

Our repo has no market data. Research current, citable figures and show the calculation on the slide in small type
(e.g. "users × price"). Suggested framing:

- **TAM:** knowledge workers worldwide who use AI assistants.
- **SAM:** knowledge workers in India on laptops that can run local models, especially regulated professions under
  DPDP (legal, finance, healthcare, founders).
- **SOM:** a realistic 3-year early-adopter share of the SAM, with the assumption stated.

Cite each source on the References slide. If you can't find a reliable source, write **"TODO: market figure"**
rather than guessing. Judges check numbers.

## 6. References (use exactly these)

1. Kim et al., multi-agent scaling across 180 configurations, arXiv:2512.08296
2. Cemri et al., MAST: why multi-agent systems fail, arXiv:2503.13657
3. Zheng et al., persona prompts don't improve accuracy, arXiv:2311.10054
4. NATURAL PLAN, arXiv:2406.04520
5. A solver-checked LLM planner (10% → 93.9%), arXiv:2404.11891
6. NVIDIA, "Small Language Models are the Future of Agentic AI", arXiv:2506.02153
7. PAPILLON (NAACL 2025): local + cloud delegation leaks 7.5%
8. The Mem0 memory audit (mem0 issue #4573) and Graphiti's invalidation report (graphiti issue #1728)
9. India's Digital Personal Data Protection Rules, 2025
10. Datasets: EnronQA (CC BY 4.0), WorkBench (MIT), QMSum / AMI
11. Models and tools: Qwen3-1.7B, Qwen3-14B, Whisper large-v3-turbo, MLX, Ollama, PostgreSQL + pgvector, OR-Tools
    CP-SAT
12. Plus any market sources used for TAM / SAM / SOM

## 7. Deliver

1. **The .pptx** built on the template, with 9 slides and speaker notes on each.
2. **Every SVG diagram** as a separate file.
3. **A short list** of every number on the slides and which fact above it came from, plus any TODOs left.
