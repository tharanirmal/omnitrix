# H — Agent-roster evidence: does the 22-agent design earn its keep against engram's pipeline?

Compiled 2026-09-28. Method: WebSearch/WebFetch against arXiv papers, official lab blog posts (Anthropic,
Google Research, Cognition), and current 2025–2026 coverage. Every claim below carries a source link and the
paper's own numbers where the source gave numbers; anything the search/fetch pass could not pin down is marked
**UNVERIFIED** rather than estimated. Two PDFs (Cemri et al. MAST, CODA) were fetched directly from arXiv rather
than read only as search snippets. Context: the team's roster document names 22 LLM-agent personas (Chief of
Staff, Librarian, Researcher, Historian, Promise Keeper, Planner, Auditor, Analyst, Writer, Fact Checker,
Operator, Guardian, Herald, Diplomat, Scout, + 7 "later"); the actual built system ("engram") is a single
tool-calling agent behind a code-rules → fine-tuned-1.7B-judge → 14B-model → human pipeline. This note asks what
the 2024–2026 literature says about that specific fork in the road.

---

## 1. Multi-agent vs. single-agent evidence (2024–2026)

- **Cemri et al., "Why Do Multi-Agent LLM Systems Fail?"** built **MAST** (Multi-Agent System Failure
  Taxonomy) from **1600+ annotated traces across 7 popular open-source MAS frameworks**, with the taxonomy
  itself distilled from 150 traces by human annotators reaching **inter-annotator agreement κ = 0.88**. The
  paper's own framing: "despite enthusiasm for Multi-Agent LLM Systems (MAS), their performance gains on
  popular benchmarks are often minimal." Failures cluster into 3 categories — **system design issues (44.2% of
  annotated failure occurrences), inter-agent misalignment (32.3%), and task verification failures (23.5%)** —
  spanning 14 named failure modes, the two most common individually being **step repetition (15.7%)** and
  **reasoning–action mismatch (13.2%)**. [arXiv:2503.13657](https://arxiv.org/abs/2503.13657)
  **Relevance to engram:** nearly half of real-world MAS failures are *system-design* failures (lost context,
  ignoring requirements, continuing after the task is done) — exactly the class of bug a single pipeline with
  one shared conversation state structurally cannot have, because there's no second agent to lose sync with.
  The other 56% (misalignment + no verification) map onto problems engram already solves differently: Guardian
  is a verification *gate*, not a peer agent that might silently skip checking.

- **Kim et al. (Google Research / Google DeepMind / MIT), "Towards a Science of Scaling Agent Systems"**
  (arXiv Dec 2025, blogged Jan 2026) ran **180 controlled agent configurations across 5 canonical architectures,
  4 benchmarks, and 3 LLM families**, holding tools/prompts/token budgets fixed so topology could be isolated.
  Headline numbers: **independent (fully decentralized) multi-agent systems amplify errors 17.2× relative to a
  single-agent baseline; centralized-coordination (orchestrator-worker) architectures cut that to 4.4×** — the
  orchestrator acts as a "validation bottleneck" that catches errors before they propagate. Task structure
  matters enormously: on a decomposable/parallelizable benchmark (financial reasoning), centralized multi-agent
  coordination gave **+80.8% to +80.9%** relative improvement; on a **sequential-planning** benchmark
  (PlanCraft), every multi-agent variant *lost* **39–70%** relative to single-agent, and performance also
  degraded disproportionately once tool count passed roughly 16. A regression using measurable task properties
  (decomposability, tool density) predicted the best-performing architecture for **87% of held-out
  configurations** (R² = 0.373–0.513 depending on the feature set).
  [Google Research blog](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/) ·
  [arXiv:2512.08296](https://arxiv.org/abs/2512.08296)
  **Relevance to engram:** engram's own pipeline (S0 code rules → S1 judge → S2 14B → human) is a strictly
  **sequential** decision chain, not a decomposable/parallel workload — this is precisely the regime where the
  paper's own numbers say decentralized multi-agent loses 39–70% and even *centralized* multi-agent buys little,
  because there's nothing to parallelize. It also directly supports keeping a single orchestrator-style
  arbitration point (which S1→S2 escalation already *is*) rather than adding peer agents.

- **Anthropic, "How we built our multi-agent research system"** (engineering blog): a multi-agent system
  (Opus 4 lead + parallel Sonnet 4 subagents) beat a single-agent Opus 4 baseline by **90.2%** on an internal
  research eval, but at **~15× the token cost of a single chat turn** (vs. ~4× for a single agent using tools).
  Anthropic's own conclusion: multi-agent is worth it only for "tasks where the value... is high enough to pay
  for the increased performance," specifically **heavy parallelization, context that exceeds one window, or
  many complex tools** — and explicitly *not* a good fit for tasks (their example: most coding) with "fewer
  truly parallelizable tasks" and tight cross-agent dependencies, partly because "LLM agents are not yet great
  at coordinating and delegating to other agents in real time."
  [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
  **Relevance to engram:** the token multiplier this paper reports (4–15×) is a *cloud-frontier-model* number
  bought back by parallel wall-clock speedup across many workers. On one laptop GPU running local 1.7B/14B
  models serially, there is no parallel-worker speedup to buy back the multiplier with — the 4–15× token cost
  becomes a pure 4–15× *latency* cost with nothing to show for it (see the on-device note below).

- **Cognition, "Don't Build Multi-Agents"** (2025) argues from two context-engineering principles: (1) "share
  context, and share full agent traces, not just individual messages," and (2) "actions carry implicit
  decisions, and conflicting decisions carry bad results." Their worked example: splitting a "build a Flappy
  Bird clone" task across subagents produced one subagent building a *Super Mario*-style background and another
  building a mismatched bird, leaving a merge agent to reconcile two independent, uncommunicated decisions.
  [Cognition blog](https://cognition.com/blog/dont-build-multi-agents)
  **Follow-up, "Multi-Agents: What's Actually Working"** (2026): Cognition now says the pattern *can* work in
  production when **writes stay single-threaded** and additional agents only "contribute intelligence" (parallel
  read/reasoning, e.g. running Claude and GPT together to catch each other's mistakes) rather than each agent
  independently taking actions; they attribute part of the turnaround to frontier models (e.g. their own SWE 1.6)
  getting good enough at coordination to make the pattern pay off, calling the remaining open problems "all
  communication problems." [Cognition blog — Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working)
  **Relevance to engram:** the safe subset even Cognition endorses — many readers/reasoners, one writer — is
  effectively what the roster's own **Operator** already guarantees by being "the only agent that acts." The
  parts of the roster this blesses (if any) are read-only advisory roles feeding one writer, never two agents
  each independently calling tools.

- **"Architectural Design, Not Only Model Intelligence, Governs Multi-Agent LLM Performance"** (2026) built
  **MAFBench** across 9 frameworks with a fixed underlying LLM and found the coordination *scaffolding itself*
  dominates outcomes: plain **orchestration overhead adds over 60× latency** versus a minimal implementation;
  **schema-constrained planning interfaces cut accuracy by up to 32 points through formatting failures, not
  reasoning errors**; and **mismatched communication topology drops coordination success from >90% to <30%**.
  [arXiv:2602.03128](https://arxiv.org/abs/2602.03128)
  **Relevance to engram:** every one of these failure modes is a tax paid purely for having >1 agent talk to
  >1 agent — a 60× latency multiplier is fatal on a laptop already budgeting ~35–200 ms S1 latencies, and a
  32-point accuracy hit from schema/formatting friction is a real risk if 22 personas each get their own
  structured-output contract instead of one pipeline's already-tested schema.

- **Small/local models, single GPU, no real parallelism (the case that matters here).** Direct evidence for
  *this exact regime* is thin in the 2025–2026 literature — most of the studies above use cloud frontier models
  with genuine parallel workers. The closest concrete numbers found: a multi-agent **edge-device** KV-cache
  study reports that on an **Apple M4 Pro with a 10.2 GB cache budget, only 3 agents fit simultaneously at 8K
  context in FP16**, and a 10-agent workflow must constantly evict and reload caches, with reload latency
  (~500 ms) only hidden when one agent's decode phase overlaps another's cache load — i.e., true concurrency,
  not serialized turn-taking.
  [arXiv:2603.04428 — Agent Memory Below the Prompt](https://arxiv.org/pdf/2603.04428)
  General 2026 local-hardware surveys corroborate that "multi-agent on one GPU" setups are usually just multiple
  processes competing for the same card rather than genuinely parallel, and that multi-GPU pipelining adds a
  **15–30% throughput penalty** from inter-GPU communication.
  [Local LLM 2026 guide (general survey, UNVERIFIED as a peer-reviewed source)](https://medium.com/@paulhoke/the-complete-guide-to-running-large-language-models-locally-in-2026-hardware-tools-and-da9efb3170be)
  **Relevance to engram:** no controlled study was found that isolates "multi-agent overhead with a fine-tuned
  ~1.7B judge + one 14B model on one Apple-Silicon GPU, no parallelism." Extrapolating from the above: on a
  single laptop GPU, agents run one after another regardless of how many personas exist, so every additional
  "agent" in the roster is pure added *serial* latency and extra context-reconstruction cost, never a
  wall-clock win. This is the single strongest argument against multiplying personas in engram specifically,
  and it is **UNVERIFIED by a dedicated study** — flagged as an open question below.

---

## 2. Role-play personas vs. typed functions

- **Zheng, Pei & Jurgens, "Is 'A Helpful Assistant' the Best Role for LLMs? A Systematic Evaluation of Social
  Roles in System Prompts"** (EMNLP Findings 2024). Curated **162 roles across 6 relationship types and 8
  expertise domains**, tested on **4 LLM families over 2,410 factual questions**. Finding: adding a persona to
  the system prompt **does not improve accuracy** on factual QA versus a plain "helpful assistant" or no-persona
  control. [arXiv:2311.10054](https://arxiv.org/abs/2311.10054) ·
  [ACL Anthology](https://aclanthology.org/2024.findings-emnlp.888/)
  **Relevance to engram:** this is close to the actual proposed roster shape — "You are the Historian," "You are
  the Promise Keeper" — but tested on *factual QA*, not structured extraction/commitment-tracking; treat as
  strong-but-not-perfectly-matched evidence (see Open questions).

- **"When Does Persona Prompting Actually Help? A Retrieval and Metric Analysis of Expert Role Injection in
  LLMs"** (2026). Controlled 4-condition comparison (no role, generic domain-expert, embedding-retrieved role,
  hybrid retrieval) across **1,140 open-ended questions, 38 expert roles, 6 domains**. Aggregate scores show only
  small differences between conditions, but **metric-level analysis reveals role prompting systematically
  increases expertise depth and terminology while *reducing* clarity and conciseness** — a real trade-off
  hidden by averaged scores. Persona prompting helped most on **advisory questions in medicine/psychology**,
  where risk framing has intrinsic value. [arXiv:2605.29420](https://arxiv.org/abs/2605.29420)
  **Relevance to engram:** none of the 22 roles are advisory-medical in nature; per this paper the expected
  effect of naming a persona is *not* better task accuracy but denser, less concise output — a cost, not a
  benefit, for something like the Auditor or Promise Keeper that needs terse structured output.

- **"Expert Personas Improve LLM Alignment but Damage Accuracy: Bootstrapping Intent-Based Persona Routing
  with PRISM"** (2026). Reports that expert personas can shift outputs toward a target style/audience
  ("alignment") but at a measurable cost to factual accuracy, motivating a routing layer that applies personas
  selectively rather than universally. [arXiv:2603.18507](https://arxiv.org/html/2603.18507v1)
  **Relevance to engram:** reinforces that persona identity should be a *targeted, occasional* prompt choice
  (e.g., Writer matching the owner's voice for a draft) rather than the organizing principle for 22 separate
  always-on agents, most of which do extraction/verification work where accuracy, not voice, is the deliverable.

---

## 3. LLMs for scheduling / day planning

- **NATURAL PLAN** (Zheng et al., Google DeepMind, 2024): a realistic natural-language planning benchmark with
  3 tasks — Trip Planning, Meeting Planning, Calendar Scheduling — built from real-world service data with
  single correct solutions. **Calendar Scheduling:** GPT-4 Turbo scores **under 10% at 1-shot**, rising to
  **36% at 40-shot**; Gemini 1.5 Pro scores **33% at 1-shot**, rising to **48% at 40-shot**. **Trip Planning:**
  GPT-4 **31.1%**, Gemini 1.5 Pro **34.8%** solve rate overall, with **all models falling below 5% once trip
  complexity reaches 10 cities**. [arXiv:2406.04520](https://arxiv.org/abs/2406.04520)
  **Relevance to engram:** the Planner agent's job (day schedule + re-planning under constraints) is structurally
  the Calendar Scheduling task, and even frontier 2024 models solve well under half of it directly — no 2025–26
  re-run of NATURAL PLAN against newer frontier reasoning models turned up in this search pass (flagged as an
  open question), so treat "an LLM alone schedules the day" as evidenced-unreliable until shown otherwise.

- **TravelPlanner** (2024): under rigorous multi-constraint settings, **GPT-4-Turbo with ReAct achieves only
  0.6% final-pass rate**, and language-agent approaches in general report **0.6–4.4% overall feasibility**.
  [arXiv:2402.01622](https://arxiv.org/pdf/2402.01622) ·
  [OpenSymbolic summary](https://www.opensymbolic.ai/blog/travelplanner-benchmark)
  **Relevance to engram:** corroborates NATURAL PLAN — raw LLM constraint planning is close to unusable at
  real-world constraint density, independent of which benchmark is used.

- **Kambhampati et al., "LLMs Can't Plan, But Can Help Planning in LLM-Modulo Frameworks"** (ICML 2024
  position paper): argues autoregressive LLMs cannot themselves guarantee sound planning or self-verification,
  and proposes an **LLM-Modulo** architecture where the LLM proposes candidates that external, sound
  verifiers/critics (symbolic planners, solvers) check and refine — LLM as idea-generator, not final arbiter.
  [arXiv:2402.01817](https://arxiv.org/abs/2402.01817)
  **"Robust Planning with LLM-Modulo Framework: Case Study in Travel Planning"** applies this specifically to
  TravelPlanner; independent secondary coverage of a solver-coupled TravelPlanner approach reports **success
  rates jumping to ≈97%** once a formal solver checks/repairs the LLM's candidate plan, vs. sub-1% for raw LLM
  planning. [arXiv:2405.20625](https://arxiv.org/pdf/2405.20625) ·
  [secondary summary, numbers UNVERIFIED against the primary PDF directly](https://www.opensymbolic.ai/blog/travelplanner-benchmark)

- **"Large Language Models Can Solve Real-World Planning Rigorously with Formal Verification Tools"** (2024):
  formalizes TravelPlanner as a constraint-satisfiability problem checked by a sound-and-complete SAT/SMT
  solver. Reports **o1-preview alone at only 10% success**, vs. **93.9% success** once the LLM's plan is passed
  through the solver-verification loop. [arXiv:2404.11891](https://arxiv.org/abs/2404.11891)

- **CP-Agent: Agentic Constraint Programming** (2025): an agent that writes/repairs constraint-programming
  models interactively; notes that even **direct prompting with Python-based frameworks like OR-Tools achieves
  up to ~65% accuracy** on constraint-modeling tasks — lower than the SAT/SMT-checked-loop numbers above but
  still far above raw natural-language planning, and directly names OR-Tools (the solver family the roster
  design already floated). [arXiv:2508.07468](https://arxiv.org/pdf/2508.07468)
  **Relevance to engram:** across four independent lines of evidence (NATURAL PLAN, TravelPlanner, LLM-Modulo,
  CP-Agent), the pattern is consistent: **raw LLM scheduling tops out well under 50%, LLM-extracts-constraints
  → solver-executes hybrids reach 65–97%.** This is the single most decision-relevant, best-replicated finding
  in this note for the Planner role.

---

## 4. Agent-to-agent negotiation (the "Diplomat")

- **A2A protocol status, 2026.** Google's Agent2Agent (A2A) protocol reached **v1.0.0 in January 2026**,
  marking a move from experimental to "production-ready," adding signed Agent Cards for cryptographic
  verification. On **2026-09-17**, Google transferred A2A's specification, SDKs, and tooling to the **Linux
  Foundation**, forming an Agent2Agent project backed by AWS, Cisco, Google, Microsoft, Salesforce, SAP, and
  ServiceNow, consolidating under the Foundation's **Agentic AI Foundation (AAIF)** (formed Dec 2025, also
  hosting MCP). Coverage reports **150+ supporting organizations**.
  [Google Developers Blog — A2A donated to Linux Foundation](https://developers.googleblog.com/en/google-cloud-donates-a2a-to-linux-foundation/) ·
  [Google Open Source Blog — A2A anniversary](https://opensource.googleblog.com/2026/04/a-year-of-open-collaboration-celebrating-the-anniversary-of-a2a.html)
  **Relevance to engram:** A2A is real, governed, and standardizing — a plausible on-ramp if a future Diplomat
  ever needs to talk to another company's agent — but it is infrastructure for *transport/discovery*, not a
  guarantee of safe negotiation content (see next finding).

- **A2ABreak: Systematic Security Analysis of the A2A Protocol** (2026): built a formal model (**37 states, 76
  transitions**, derived from 929 formalized spec statements) and found **11 new vulnerabilities**, all
  exploitable by *spec-compliant* adversaries (no implementation bugs needed): **cross-client context
  injection** (unprotected context identifiers let one client's data leak into another's), **credential
  harvesting via multi-hop identity loss** across delegation chains, and **data exfiltration via unattested
  capability claims** from rogue agents. The formal-analysis approach validated at **73.3% precision / 84.6%
  F1** against expert review, while a baseline "ask an LLM to audit the spec" approach found **zero** of these
  issues. [arXiv:2609.10871](https://arxiv.org/pdf/2609.10871)
  **Relevance to engram:** direct evidence that agent-to-agent protocols leak identity/context/credentials
  *by design*, not just by bad implementation — this is the strongest reason to keep Diplomat, if built at all,
  behind the same Guardian approval gate as every other external action, never autonomous.

- **ConfAIde** (Mireshghallah et al., 2024): a four-tier contextual-integrity benchmark showing LLMs
  inappropriately reveal private information in situations where a human would recognize the norm violation,
  even with no adversary present. [Referenced via secondary survey](https://arxiv.org/html/2506.04245v3)

- **PrivacyLens** (Shao et al., 2024): extends contextual-integrity evaluation from Q&A into actual **agent
  actions** (tool calls), finding a gap between a model's *stated* awareness of privacy norms and its *actual
  behavior* once it's executing a user's instruction with tools. [Referenced via secondary survey](https://arxiv.org/html/2506.04245v3)

- **AirGapAgent** (Bagdasarian et al., ACM CCS 2024): proposes a **two-stage architecture** — a "data
  minimizer" LLM filters what a privacy-conscious agent is allowed to send before a second LLM actually talks to
  the third party — as a concrete mitigation for exactly this class of leakage.
  [arXiv:2405.05175](https://arxiv.org/abs/2405.05175)
  **Relevance to engram:** if Diplomat is ever built, the ConfAIde/PrivacyLens/AirGapAgent line together argue
  for an explicit data-minimizer stage *before* anything is sent to another company's agent — not something a
  single "be diplomatic" system prompt can be trusted to enforce on its own.

---

## 5. Fine-tuning a small model as a specialist inside an agent system

- **NVIDIA, "Small Language Models are the Future of Agentic AI"** (Belcak et al., 2025): argues that in
  agentic systems, most individual model invocations are narrow, repetitive, low-variation subtasks — exactly
  where SLMs are "sufficiently powerful, inherently more suitable, and necessarily more economical." Reports
  SLMs as **10–30× cheaper to run** than frontier LLMs, with lower latency, and fine-tunable **"overnight
  instead of over weeks."** Recommends heterogeneous systems (a general-purpose LLM only where broad
  conversational ability is truly needed, SLMs everywhere else).
  [arXiv:2506.02153](https://arxiv.org/abs/2506.02153)
  **Relevance to engram:** this is close to a direct endorsement of the S1-judge design already built —
  a small, fine-tuned, fast model doing the frequent narrow yes/no/choice classification work, escalating to
  the expensive general model only when needed.

- **CODA: Coordinating the Cerebrum and Cerebellum for a Dual-Brain Computer-Use Agent** (2025): a
  neurobiology-inspired split between a large "cerebrum" model for deliberative planning and a small,
  fast "cerebellum" model for rapid tactical decisions, trained together via **decoupled reinforcement
  learning** so the fast model handles moment-to-moment action while the large model supervises/corrects.
  [arXiv:2508.20096](https://arxiv.org/pdf/2508.20096)
  **Relevance to engram:** structurally the same shape as S1 (fast judge) / S2 (large deliberator) — direct,
  if indirect-domain (computer-use, not personal-assistant), evidence that this fast/slow split is an active,
  validated pattern rather than a one-off hackathon idea.

- **Agent-as-a-Router: Agentic Model Routing for Coding Tasks** (2026): an orchestrator built from a
  **fine-tuned lightweight LLM (Qwen3.5-0.8B)** combined with heuristic rules and historical-task retrieval,
  paired with an LLM-as-judge verifier for output quality. [arXiv:2606.22902](https://www.alphaxiv.org/abs/2606.22902)
  **Relevance to engram:** a close analog — a small fine-tuned model doing routing/judging duty, general LLM
  doing verification/generation — matching engram's S1-routes/S2-executes shape with a sub-1B model, smaller
  even than the project's own 1.7B judge.

- **Distilled judge specialists (general pattern).** JudgeLM-style work fine-tunes smaller models on
  supervision signals distilled from a stronger model (e.g., GPT-4) so the small model can evaluate/grade
  open-ended generations cheaply. Compact-classifier routers (fine-tuned BERT/DistilBERT-class models) are
  reported to offer the best latency-accuracy trade-off for routing at scale, at the cost of needing labeled
  training data. [Referenced via secondary survey, specific benchmark numbers UNVERIFIED in this pass](https://arxiv.org/pdf/2602.07773)
  **Relevance to engram:** general confirmation that "distill a judge out of a bigger model, run it small and
  fast" is a recognized, load-bearing pattern industry-wide, not a one-off.

---

## Implications for the roster

**Deserve to stay separate systems (not personas, but genuinely distinct code/process boundaries):**
- **Operator** — the evidence in §1 (Cognition's "writes stay single-threaded" recovery, Anthropic's own
  caution about coordination) converges on exactly this: there should be one, and only one, thing that takes
  external actions. This maps cleanly onto engram's existing single tool-calling agent.
- **Guardian** — not really an "agent" in the LLM sense at all; it's a policy/approval gate, and §4's A2ABreak
  and privacy-leakage findings (ConfAIde/PrivacyLens/AirGapAgent) are exactly why every effectful and
  external-facing action — including anything a future Diplomat proposes — should pass through one gate rather
  than trusting each persona's own judgment.
- **S1 judge / S2 model split** — squarely supported by §5 (NVIDIA SLM paper, CODA, Agent-as-a-Router): keep
  investing here, this is the one place the roster's "many specialized minds" intuition is actually
  well-evidenced, just realized as a fast/slow model pair rather than named personas.

**Should become pipeline stages, judge decisions, or plain tool functions, not separate LLM personas:**
- **Librarian, Researcher, Historian, Promise Keeper, Auditor, Analyst, Fact Checker, Chief of Staff** — these
  are almost entirely *extraction/verification/QA* jobs against the S2 model with different prompts and
  tool-schemas, exactly the shape §1 and §2 warn against multiplying: §1's MAST/Kim-et-al results show
  sequential, tightly-dependent workflows lose 39–70% under decentralized multi-agent and pay a 60×
  latency/32-point-accuracy tax on orchestration/schema overhead for no benefit, while §2's persona-prompting
  studies find role identity buys no factual-accuracy improvement (and, per the 2026 retrieval study, actively
  trades conciseness for unwanted "expertise depth" that these terse, structured jobs don't want). Each should
  be a typed function/tool call with its own schema and prompt, invoked by the one pipeline, not a
  "you are the Historian" persona layered onto repeat calls to the same model.
- **Writer** — the one place persona/voice-matching plausibly earns its keep (§2's finding that persona
  prompting shifts style/register, and helps most on advisory/communicative tasks) — but even here, treat it as
  a *prompt variant* invoked at the drafting step, not a standing separate agent with its own state.
- **Herald** — pure notification plumbing; no LLM judgment finding in this note applies to it at all — it's a
  code/tool function, full stop.

**Scheduling should be solver-based, not LLM-only.** §3's four independent lines of evidence (NATURAL PLAN,
TravelPlanner, LLM-Modulo, CP-Agent) agree: raw LLM planning tops out well under 50% (often under 10%) on
calendar/constraint tasks of realistic size, while LLM-extracts-constraints → OR-Tools/CP-SAT-or-SAT-solver
architectures reach roughly **65–97%** depending on the specific hybrid. The **Planner** should be built as
"LLM parses the request into a constraint set → a solver schedules it → LLM explains the result back," never
as an LLM asked to produce a schedule directly.

**Diplomat and Scout should stay "later," and Diplomat specifically needs safeguards before it exists at all.**
§4 shows the A2A transport layer is maturing fast (Linux Foundation governance, v1.0.0, 150+ orgs) but that
spec-compliant multi-agent protocols still leak context/credentials by design (A2ABreak's 11 vulnerabilities),
and that LLM agents leak contextually-inappropriate private information even without an adversary (ConfAIde,
PrivacyLens). If a Diplomat is ever prototyped, it needs an AirGapAgent-style data-minimizer stage in front of
it and must route every outbound message through Guardian — it should not be scoped as "give an agent a
diplomatic persona and let it talk to other agents."

**On the core single-agent-vs-22-agents question for a hackathon on one laptop:** every piece of quantitative
evidence gathered here (Kim et al.'s sequential-task numbers, Anthropic's token multiplier, the MAFBench
orchestration-latency numbers, and the KV-cache/edge-device constraints) points the same direction for
*this specific deployment*: a single local GPU running local models serially cannot recover the token/latency
cost multi-agent architectures pay for coordination, because there is no parallel-worker speedup to buy it back
with, and engram's own pipeline (code → judge → 14B → human) is a sequential decision chain, which is exactly
the task shape every study found multi-agent architectures handle *worst*. The 22-agent roster is best read as
a **naming scheme for prompts/tools inside one pipeline**, not a literal deployment target.

---

## Open questions

- No controlled study was found that isolates multi-agent coordination overhead specifically for **small local
  models (sub-2B judge + ~14B main model) serialized on one Apple-Silicon GPU** — every quantitative multi-agent
  study located here (Kim et al., Anthropic, MAFBench) uses cloud frontier models with real parallel workers.
  The conclusion above extrapolates from first principles (no parallelism → no way to amortize the token/latency
  multiplier) rather than a direct benchmark; worth a small in-project A/B if time allows.
- Zheng et al.'s persona-prompting null result was measured on **factual QA**, not on **structured
  extraction/commitment-tracking** (the actual job of Historian/Promise Keeper/Auditor) — plausible that the
  finding transfers, but not directly tested in that form by any paper found here.
- No 2025–2026 re-run of **NATURAL PLAN** or **TravelPlanner** against current frontier reasoning models
  (Gemini 3-class, GPT-5-class, Claude 4.x-class) turned up in this search pass — the calendar-scheduling and
  trip-planning numbers cited in §3 are from the original 2024 papers; today's frontier ceiling on these
  benchmarks is plausibly higher but is **UNVERIFIED** here.
- A2ABreak's findings are from **formal/static analysis of the specification**, not measured exploit rates
  against production A2A deployments in the wild — real-world incident data for A2A specifically was not found.
- Whether giving engram's own fine-tuned 1.7B S1 judge a named persona (vs. a plain task-schema prompt) changes
  its calibration (the p-values used for routing decisions) is untested by any paper found here and is specific
  enough to this project's own model that it would need a direct internal experiment, not a literature answer.
