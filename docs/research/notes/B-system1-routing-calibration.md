# Slice B: Dual-process AI, routing and cascades, adaptive retrieval, confidence and calibration

**Literature notes for Omnitrix's "System 1 / System 2" decision layer**
Compiled 2026-09-25 by researcher B of 6. Sibling slices cover agent memory, the model zoo and runtimes, DB/cognitive science, security and the product landscape.

## How this was verified

- **Existence, titles, authors and dates:** every arXiv paper was pulled from the arXiv API (export.arxiv.org).
- **Venues:** checked against ACL Anthology, OpenReview, PMLR, the ICLR proceedings, Crossref DOIs, or a DBLP conference key surfaced through Semantic Scholar. Journal DOIs were confirmed on Crossref.
- **Numbers:** taken from abstracts, or grepped from the raw arXiv, ar5iv or Europe PMC paper text. A few came only from an LLM summary of a page, didn't match the raw text, and are either left out or listed under "Unverified".
- **"Reported"** means as claimed by the authors. Nothing here was reproduced.
- **Quotes:** none over 15 words. All summaries are paraphrased.

**Shorthand used below**

- S1 = small fast model (Qwen3-1.7B or Qwen3-4B, non-thinking).
- S2 = Qwen3-14B with thinking on.
- H = the human (the businessman), reached through Herald and the smartwatch.

Omnitrix decision types are labelled D1–D8:

| ID | Decision |
|---|---|
| D1 | Is this email noise? |
| D2 | Is this mention the same entity as an existing node? |
| D3 | Does this new fact contradict a stored decision? |
| D4 | Does this query need retrieval? |
| D5 | Is this retrieved passage relevant? |
| D6 | Is this answer supported by its sources? |
| D7 | Does this action need human approval? |
| D8 | (meta) Does this need System 2, and which agent or model should handle it? |

---

## 1. Dual-process AI

### 1.1 Framing: Kahneman and Bengio's "System 2 deep learning" (kept short on purpose)
- **Citation:**
  - Kahneman, D. (2011). *Thinking, Fast and Slow.* Farrar, Straus and Giroux. Framing only.
  - Bengio, Y. (2019). "From System 1 Deep Learning to System 2 Deep Learning." NeurIPS 2019 Posner Lecture. https://neurips.cc/virtual/2019/invited-talk/15488
  - Goyal, A., Bengio, Y. (2022). "Inductive biases for deep learning of higher-level cognition." *Proc. Royal Society A* 478(2266). DOI 10.1098/rspa.2021.0068; arXiv 2011.15091. https://arxiv.org/abs/2011.15091
- **Mechanism:** Bengio argues that deep learning has mostly solved System-1 perception tasks. System-2 abilities (sequential conscious reasoning, planning, causal structure, out-of-distribution generalization) need new inductive biases: attention, sparse factor graphs, and causal and compositional representations.
- **Key results:** A position paper and talk, with no benchmark numbers.
- **Relevance to Omnitrix:** Use this for framing only. Omnitrix's S1/S2 split is an engineering split driven by cost, latency and confidence. It is not Bengio's representation-learning agenda, so the pitch shouldn't claim otherwise.

### 1.2 SOFAI family: metacognitive arbiter between fast and slow solvers (2021 to 2026)
- **Citation:**
  - Booch, G., Fabiano, F., Horesh, L., et al. (2021). "Thinking Fast and Slow in AI." *AAAI 2021* 35(17):15042–15046. DOI 10.1609/aaai.v35i17.17765; arXiv 2010.06002. https://arxiv.org/abs/2010.06002
  - Ganapini, M. B., et al. (2022). "Combining Fast and Slow Thinking for Human-like and Efficient Navigation in Constrained Environments." arXiv 2201.07050. Extends arXiv 2110.01834, "…the Role of Metacognition". https://arxiv.org/abs/2201.07050
  - Fabiano, F., et al. (2023). "Fast and Slow Planning." arXiv 2303.04283.
  - Ganapini, M. B., Campbell, M., Fabiano, F., et al. (2025). "Fast, slow, and metacognitive thinking in AI." *npj Artificial Intelligence* 1, art. 27 (Oct 2025). DOI 10.1038/s44387-025-00027-5.
  - Khandelwal, V., Pallagani, V., Srivastava, B., Rossi, F. (2024, revised 2025). "A Neurosymbolic Fast and Slow Architecture for Graph Coloring" (SOFAI_v2). arXiv 2412.01752.
  - Khandelwal, V., Rossi, F., et al. (2025). "Language Models Coupled with Metacognition Can Outperform Reasoning Models" (SOFAI-LM). arXiv 2508.17959. https://arxiv.org/abs/2508.17959
  - Still active in Sept 2026: Yan, J., Fabiano, F., Abate, A. (2026). "Dual Process Motion Planning." arXiv 2609.01260.
- **Mechanism:**
  - Fast System-1 solvers are experience-driven and return a decision plus a confidence. Slow System-2 solvers deliberate. A metacognitive (MC) module arbitrates using a "model of self" (past solver performance) and a "model of the world".
  - **MC1 (fast check)** accepts the S1 answer only if all three hold:
    - there is enough experience in this state;
    - the trajectory's reward is on track relative to history;
    - S1's confidence clears a risk threshold.
  - **MC2 (runs otherwise)** invokes S2 only if S2's expected reward gain over S1, divided by S2's estimated cost relative to remaining resources, clears a threshold.
  - **SOFAI-LM** adds a loop before escalating. The metacognition gives the fast LLM targeted feedback and examples over several iterations. It calls the large reasoning model (LRM) only if that loop fails, and passes along what the loop learned.
- **Key results:**
  - Navigation instance thresholds: t1=200 (experience count), t2=0.8 (partial vs. average reward), t3=0.4 (S1 confidence), t4=0 (S2 gain/cost), t6=1.
  - As experience accumulates, usage shifts from mostly S2 to mostly S1. SOFAI beats S1 alone on reward and is faster than S2 alone (shown in figures).
  - SOFAI_v2: 10.5% higher success rate and up to 30% faster than a symbolic solver on graph colouring.
  - SOFAI-LM: matches or exceeds standalone LRMs on graph colouring and code debugging with much lower inference time (no single number in the abstract).
- **Relevance to Omnitrix:** This is the closest architectural precedent for a Chief-of-Staff arbiter written in plain code. Concretely:
  1. Keep a per-decision-type track record of S1 accuracy on audited cases. This is the "model of self".
  2. Don't trust S1 on a decision type or entity until it has N audited experiences.
  3. Escalate on low confidence *or* on off-track outcomes.
  4. Borrow SOFAI-LM's pattern of letting S1 retry with retrieved examples before waking S2.

### 1.3 SwiftSage
- **Citation:** Lin, B. Y., Fu, Y., Yang, K., et al. (2023). "SwiftSage: A Generative Agent with Fast and Slow Thinking for Complex Interactive Tasks." *NeurIPS 2023* (spotlight). arXiv 2305.17390. https://arxiv.org/abs/2305.17390
- **Mechanism:**
  - Swift is Flan-T5-large (770M), behaviour-cloned from oracle trajectories. Sage is GPT-4, used for subgoal planning and action grounding.
  - Control passes to Sage on any of four heuristic triggers: 5 consecutive zero-reward steps (stuck), an invalid Swift action, a critical decision such as the final answer, or an unexpected observation or exception.
  - Sage emits an action buffer, then control returns to Swift.
- **Key results:**
  - ScienceWorld (30 tasks) overall score: SwiftSage 84.68 vs Reflexion 45.34, ReAct 36.43, SayCan 33.82. All four use GPT-4.
  - Tokens per action: 757.07 vs 1,971.03 (ReAct), 1,855.84 (SayCan), 2,983.46 (Reflexion).
- **Relevance to Omnitrix:** Escalation doesn't have to rely only on confidence; *rule triggers* work too. S1 should hand over to S2 by rule when:
  - the decision is in a critical class (anything leading to outbound comms, money or commitments);
  - S1 produced an invalid or unparsable output;
  - there has been no progress for several steps;
  - a tool returns a surprising result.

  This fits the "deterministic checks before model judgement" rule.

### 1.4 Talker–Reasoner
- **Citation:** Christakopoulou, K., Mourad, S., Matarić, M. (2024). "Agents Thinking Fast and Slow: A Talker-Reasoner Architecture." arXiv 2410.08328. https://arxiv.org/abs/2410.08328
- **Mechanism:**
  - The Talker (S1) answers conversationally, fast, from the current belief state in memory.
  - The Reasoner (S2) does multi-step planning and tool calls, and writes an updated, structured belief state back to memory.
  - The Talker either proceeds on the latest belief or waits for the Reasoner.
- **Key results:** Architecture paper grounded in a sleep-coaching agent. No quantitative benchmark.
- **Relevance to Omnitrix:** A clean pattern for Herald and the Chief of Staff. Answer immediately from memory (Postgres, Obsidian) while S2 refreshes beliefs in the background. This decouples perceived latency from deliberation.

### 1.5 System-1.x
- **Citation:** Saha, S., Prasad, A., Chen, J. C.-Y., Hase, P., Stengel-Eskin, E., Bansal, M. (2025). "System-1.x: Learning to Balance Fast and Slow Planning with Language Models." *ICLR 2025*. arXiv 2407.14414. https://arxiv.org/abs/2407.14414
- **Mechanism:**
  - A controller splits a problem into sub-goals and labels each one easy (fast System-1 planner) or hard (System-2 search planner).
  - All three components are LoRA-fine-tuned from Mistral-7B-Instruct-v0.2.
  - Training labels come from a cheap domain hardness function, for example the number of obstacles in a sub-maze.
  - A user-set hybridization factor x controls how much of the problem goes to System 2.
- **Key results:** On mazes, System-1.5 produced 70.4% valid plans using 13.6 explored states on average. At that budget, System-1 managed 48.7% and System-2 37.2%, so gains of 21 and 33 points. System-2's best validity is 94%, but it needs 24.4 states.
- **Relevance to Omnitrix:** Supports exposing a **deliberation budget knob** per agent or decision type. It also shows a difficulty router can be trained from automatically derived hardness labels, with no human labelling.

### 1.6 Dualformer
- **Citation:** Su, D., Sukhbaatar, S., Rabbat, M., Tian, Y., Zheng, Q. (2025). "Dualformer: Controllable Fast and Slow Thinking by Learning with Randomized Reasoning Traces." *ICLR 2025*. arXiv 2410.09918. https://arxiv.org/abs/2410.09918
- **Mechanism:** One Transformer is trained on reasoning traces with parts randomly dropped. At inference it can run in fast mode (solution only), slow mode (trace plus solution) or auto mode.
- **Key results:** On 30×30 mazes:
  - Slow mode: 97.6% optimal, vs Searchformer's 93.3%, with 45.5% fewer steps.
  - Fast mode: 80%, vs 30% for a solution-only model.
  - Auto mode: 96.6% with 59.9% fewer steps.
- **Relevance to Omnitrix:** Conceptual background for single-checkpoint hybrid models like the original Qwen3. Omnitrix won't train such a model.

### 1.7 Distilling System 2 into System 1
- **Citation:** Yu, P., Xu, J., Weston, J., Kulikov, I. (2024). "Distilling System 2 into System 1." arXiv 2407.06023. https://arxiv.org/abs/2407.06023
- **Mechanism:**
  - Run expensive System-2 prompting on unlabelled inputs: Rephrase-and-Respond, System-2 Attention, Branch-Solve-Merge (BSM) or chain-of-thought (CoT).
  - Keep only outputs that pass unsupervised consistency filters: a majority vote across samples, and agreement under input perturbation.
  - Fine-tune the model to emit the final answer directly, with no intermediate reasoning.
- **Key results** (all on Llama-2-70B-chat):
  - Last-letter concatenation: 30.0% (S1) to 98.0% (distilled RaR) at about 25 output tokens.
  - SycophancyEval (biased): 51.6% to 81.3% (distilled S2A). S2A itself scores 76.0%.
  - LLM-as-judge on MT-bench, agreement with humans: 28.1% for System 1, 64.5% for BSM (about 2,064 tokens), 72.4% for distilled BSM (4 tokens). That beats GPT-4-0125 as a System-1 judge (68.1%). Position inconsistency drops from 80.9% to 9.1%.
  - CoT on GSM8k did **not** distil: 7.13% distilled vs 7.58% System 1, with CoT itself at 52.77%.
- **Relevance to Omnitrix:** Strong support for the plan. Judge-type choice and boolean decisions (relevance, support, preference) can be distilled from S2 into S1 using consistency-filtered self-labels. Multi-step reasoning should stay in S2. Caveat: these results are at 70B and need re-validating at 1.7B–4B.

### 1.8 Learning *when* to think (2025)
- **Citation:**
  - Fang, G., Ma, X., Wang, X. (2025). "Thinkless: LLM Learns When to Think." *NeurIPS 2025*. arXiv 2505.13379. https://arxiv.org/abs/2505.13379
  - Zhang, J., Lin, N., Hou, L., Feng, L., Li, J. (2025). "AdaptThink: Reasoning Models Can Learn When to Think." *EMNLP 2025*. arXiv 2505.13417.
  - Jiang, L., et al. (2025). "Think Only When You Need with Large Hybrid-Reasoning Models." *NeurIPS 2025*. arXiv 2505.14631.
- **Mechanism:** Reinforcement learning (RL) teaches a reasoning model to pick its mode based on query difficulty. Each paper does it differently:
  - **Thinkless:** control tokens `<short>` and `<think>`, trained with decoupled GRPO.
  - **AdaptThink:** chooses NoThinking vs Thinking under a constrained objective, with importance sampling.
  - **LHRM:** Hybrid Fine-Tuning followed by Hybrid GRPO.
- **Key results:**
  - Thinkless cuts long-chain thinking by 50–90% on Minerva Algebra, MATH-500 and GSM8K.
  - AdaptThink cuts DeepSeek-R1-Distill-Qwen-1.5B's response length by 53% and raises accuracy by 2.4% on three math sets.
- **Relevance to Omnitrix:** Shows that "when to think" can be learned, but only through RL on the model itself, which is out of scope for a hackathon. Omnitrix should make the when-to-think decision *outside* the model (a code router plus metacognition) and use Qwen3's explicit mode switches.

### 1.9 Industrial hybrid thinking and routers: Qwen3, the Qwen3-2507 split, GPT-5, and 2026 leakage evidence
- **Citation:**
  - Yang, A., et al. (Qwen Team) (2025). "Qwen3 Technical Report." arXiv 2505.09388. https://arxiv.org/abs/2505.09388
  - QwenLM/Qwen3 README, news entries dated 21–31 July 2025. https://github.com/QwenLM/Qwen3
  - Model card for Qwen3-4B-Instruct-2507. https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
  - OpenAI (2025). "OpenAI GPT-5 System Card." Published August 2025; on arXiv as 2601.03267 (Dec 2025, updated May 2026). https://arxiv.org/abs/2601.03267
  - Wang, S., et al. (2026). "Path-Lock Expert: Separating Reasoning Mode in Hybrid Thinking via Architecture-Level Separation." arXiv 2604.27201.
- **Mechanism:**
  - **Qwen3** puts thinking and non-thinking modes in one checkpoint. You switch with `/think` and `/no_think` flags (the last flag in a multi-turn chat wins) or with `enable_thinking` in the chat template. A thinking budget cuts reasoning short by inserting a "stop thinking and answer" instruction.
  - **Qwen3-2507 (July 2025)** replaced the hybrid checkpoints with separate Instruct and Thinking models (4B, 30B-A3B, 235B-A22B). The Instruct-2507 card says the model supports only non-thinking mode.
  - **GPT-5** is a system: a fast model, a thinking model, and a real-time router that decides based on conversation type, complexity, tool needs and explicit intent. The router is continuously trained on real signals: users switching models, preference rates, and measured correctness.
  - **Path-Lock Expert** documents "reasoning leakage": hybrid models still produce long, self-reflective output in `/no_think` mode.
- **Key results:**
  - Qwen3 report, thinking vs non-thinking:

    | Benchmark | Qwen3-4B thinking | Qwen3-4B non-thinking | Qwen3-14B thinking | Qwen3-14B non-thinking |
    |---|---|---|---|---|
    | MMLU-Redux | 83.7 | 77.3 | 88.6 | 82.0 |
    | GPQA-Diamond | 55.9 | 41.7 | 64.0 | 54.8 |
    | AIME'24 | 73.8 | 25.0 | 79.3 | 31.7 |
    | IFEval (strict) | 81.9 | 81.2 | 85.4 | 84.8 |
    | BFCL v3 | 65.9 | 57.6 | 70.4 | 61.5 |

  - The Qwen3 report also notes that thinking-mode scores on AIME'24 and LiveCodeBench *dropped* after the general and mode-fusion training stages.
  - Path-Lock Expert on Qwen3-4B, AIME24, SFT baseline vs PLE: reflective tokens 6.01 vs 0.35 per answer; output length 8,665 vs 4,101 tokens; `/no_think` accuracy 35.33% vs 44.67%.
- **Relevance to Omnitrix:**
  1. Non-thinking mode costs almost nothing on instruction-following style tasks (IFEval 81.2 vs 81.9 at 4B). Thinking matters mainly for math and hard reasoning. So S1 classification should run non-thinking.
  2. Hybrid checkpoints can leak reasoning even in `/no_think`. Cap `max_tokens` and constrain S1 output to a schema or grammar. Consider the 2507 Instruct checkpoints (slice C to confirm they're available in Ollama).
  3. GPT-5's router is the headline industry precedent: a fast model answers most queries, and the router learns from user feedback. Omnitrix can log user overrides as router training data.

### 1.10 Surveys
- **Citation:**
  - Li, Z.-Z., Zhang, D., et al. (2025). "From System 1 to System 2: A Survey of Reasoning Large Language Models." arXiv 2502.17419. Published in *IEEE TPAMI* 48 (2026), DOI 10.1109/TPAMI.2025.3637037; the TPAMI record lists a different author order. https://arxiv.org/abs/2502.17419
  - Liu, G. K.-M., Gani, A., Lu, J., Thomas, J., Steyvers, M., Cohan, A. (2026). "Metacognition in LLMs: Foundations, Progress, and Opportunities." arXiv 2607.11881.
- **Mechanism:** The first survey covers how o1/R1-style reasoning LLMs are built (search, reward models, RL, self-improvement) and their benchmarks. The 2026 survey organizes methods and benchmarks for LLM metacognition: monitoring, control, and eliciting or improving self-assessment.
- **Relevance to Omnitrix:** Citable background for the judges. "Metacognition" is the right word for Omnitrix's "knows when it doesn't know" feature.

---

## 2. Cascades and routers (what signal decides escalation; savings vs accuracy)

### 2.1 FrugalGPT
- **Citation:** Chen, L., Zaharia, M., Zou, J. (2024). "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance." *TMLR 2024*. arXiv 2305.05176. https://arxiv.org/abs/2305.05176
- **Mechanism:**
  - A sequential cascade over 12 commercial LLM APIs.
  - After each model answers, a **DistilBERT regression scorer** g(query, answer) estimates whether the answer is reliable. If the score clears that stage's threshold τ_i the answer is accepted; otherwise the next model is called.
  - The model order and thresholds are learned from labelled data by budget-constrained optimization.
- **Escalation signal:** a separate, learned answer-quality scorer.
- **Key results:**
  - Matches the best single LLM with up to 98% lower cost, or improves accuracy over GPT-4 by 4% at the same cost.
  - Cost savings needed to reach best-single-LLM accuracy: HEADLINES 98.3%, OVERRULING 73.3%, COQA 59.2%.
- **Relevance to Omnitrix:** A template where the **scorer is separate from the generator**. The scorer could be a tiny classifier over bge-m3 features, or S1 prompted to grade S1's own answer. It needs in-distribution labels, which Omnitrix would bootstrap from S2 and human audits.

### 2.2 AutoMix
- **Citation:** Aggarwal, P., Madaan, A., et al. (equal-contribution first authors) (2024). "AutoMix: Automatically Mixing Language Models." *NeurIPS 2024*. arXiv 2310.12963. https://arxiv.org/abs/2310.12963
- **Mechanism:**
  - The small model answers, then checks itself with a generic few-shot, entailment-style prompt, sampled k times. The fraction of "correct" votes is the verification probability.
  - Because self-verification is noisy, a POMDP router treats that probability as a noisy observation and decides whether to escalate. It learns from as few as 50 examples.
- **Key results:** Over 50% compute-cost reduction at comparable performance, across five models and five datasets. The authors report that self-verification is noisy and poorly calibrated, especially on reasoning tasks.
- **Relevance to Omnitrix:** Direct precedent for S1 checking itself on context-grounded tasks (D6). Feed the self-check into a calibrator (a POMDP or logistic model) rather than thresholding it raw.

### 2.3 LLM cascades with mixture-of-thought (MoT) consistency
- **Citation:** Yue, M., Zhao, J., Zhang, M., Du, L., Yao, Z. (2024). "Large Language Model Cascades with Mixture of Thoughts Representations for Cost-efficient Reasoning." *ICLR 2024*. arXiv 2310.03094. https://arxiv.org/abs/2310.03094
- **Mechanism:** Sample several answers from the weaker LLM, mixing chain-of-thought and program-of-thought prompts. If they agree (by vote or a consistency check), accept; otherwise escalate.
- **Key results:** GPT-3.5-turbo cascading to GPT-4 matched GPT-4-alone performance at **40% of GPT-4's cost** on six reasoning benchmarks.
- **Relevance to Omnitrix:** Answer agreement is a strong, model-agnostic escalation signal and needs no logprobs. It costs k calls to S1, which is acceptable for short labels from Qwen3-1.7B or 4B.

### 2.4 Hybrid LLM (pre-generation routing)
- **Citation:** Ding, D., Mallick, A., Wang, C., et al. (2024). "Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing." *ICLR 2024*. arXiv 2404.14618. https://arxiv.org/abs/2404.14618
- **Mechanism:**
  - A BERT-style encoder router (DeBERTa) looks at the query alone and predicts whether the small model's answer will be close in quality to the large model's.
  - Training labels come from BART-score quality gaps, including soft or relaxed labels computed from 10 samples per model.
  - The quality threshold can be tuned at test time.
- **Key results:** Up to 40% fewer calls to the large model with no drop in response quality. Router latency is 0.036 ± 0.002 s, vs 0.46 s for FLAN-T5 (800M) generation.
- **Relevance to Omnitrix:** Routing before generation avoids paying for S1 when S2 will be needed anyway. A bge-m3 embedding plus a logistic head could route "which agent or model?" (D8) in milliseconds.

### 2.5 RouteLLM
- **Citation:** Ong, I., Almahairi, A., Wu, V., et al. (2025). "RouteLLM: Learning to Route LLMs from Preference Data." *ICLR 2025*; the arXiv title says "with" instead of "from". arXiv 2406.18665. OpenReview https://openreview.net/forum?id=8sSqNntaMr
- **Mechanism:**
  - Routers are trained on about 80k Chatbot Arena preference battles, augmented with golden labels or GPT-4-judge labels.
  - Four router types are tested: similarity-weighted ranking (embedding-based Bradley–Terry), matrix factorization, a BERT classifier, and a Llama-3-8B classifier.
  - Each predicts the probability that GPT-4 would win over Mixtral-8x7B, and a threshold decides.
- **Key results:**
  - Over 2× cost reduction without compromising quality.
  - On MT Bench, matrix factorization needs only 13.40% of calls to go to GPT-4 to close 50% of the quality gap, and 31.31% to close 80%.
  - Router overhead is at most 0.4% of GPT-4 generation cost.
  - Up to 40% fewer GPT-4 calls than commercial routers at equal performance.
  - The routers transfer to new model pairs without retraining.
- **Relevance to Omnitrix:** Similarity-weighted routing over past (query, outcome) pairs maps directly onto pgvector plus bge-m3. Route by the outcomes of the k nearest past cases.

### 2.6 RouterBench
- **Citation:** Hu, Q. J., Bieker, J., Li, X., et al. (2024). "RouterBench: A Benchmark for Multi-LLM Routing System." arXiv 2403.12031. https://arxiv.org/abs/2403.12031
- **Mechanism and results:** More than 405k inference outcomes from representative LLMs, plus a theoretical framework and a comparison of routers on cost–quality curves.
- **Relevance to Omnitrix:** Borrow the evaluation method. Report a cost–quality curve for each decision type in the demo.

### 2.7 Cache & Distil ("neural caching")
- **Citation:** Ramírez, G., Lindemann, M., Birch, A., Titov, I. (2024). "Cache & Distil: Optimising API Calls to Large Language Models." *Findings of ACL 2024* (DOI 10.18653/v1/2024.findings-acl.704). arXiv 2310.13561. https://arxiv.org/abs/2310.13561
- **Mechanism:**
  - A student model is retrained continuously on the LLM's labels. For each request, a policy decides whether the student answers alone or the LLM is called, in which case the new label also goes into training.
  - Policies compared (from active learning): front-loading, margin sampling (MS), prediction entropy, query-by-committee (QBC) and coreset.
  - Setup: classification tasks (ISEAR, RT-Polarity, FEVER, Openbook) with text-davinci-003 as the teacher.
- **Key results:** Margin sampling and query-by-committee give consistent gains across tasks and budgets. The student was surprisingly robust to label noise from the LLM.
- **Relevance to Omnitrix:** This is exactly the loop where S1 learns from S2 over time, for D1 and D2. S1 could be a cheap classifier or a kNN over bge-m3 embeddings, with S2 labelling the uncertain cases. **The margin between the top two probabilities is the escalation signal.**

### 2.8 Online Cascade Learning
- **Citation:** Nie, L., Ding, Z., Hu, E., Jermaine, C., Chaudhuri, S. (2024). "Online Cascade Learning for Efficient Inference over Streams." *ICML 2024*. arXiv 2402.04513. https://arxiv.org/abs/2402.04513
- **Mechanism:**
  - A cascade of logistic regression, then BERT-base, then an LLM (GPT-3.5-turbo or Llama-2-70B-chat).
  - Learned deferral functions (MLPs over model confidences) decide when to pass an input up.
  - Training is online imitation of LLM demonstrations, with a no-regret guarantee and a cost weight μ.
- **Key results:** Matches LLM accuracy while cutting inference cost by up to 90%, and stays robust under input distribution shift.
- **Relevance to Omnitrix:** The stream setting matches the inbox and news feeds (Librarian, Scout). Supports a three-tier design: S0 (a linear model on embeddings), then S1 (Qwen3-4B), then S2 (Qwen3-14B), with learned deferral.

### 2.9 Deferral rules for generative outputs (token-level uncertainty); speculative cascades
- **Citation:**
  - Gupta, N., Narasimhan, H., Jitkrittum, W., Rawat, A. S., Menon, A. K., Kumar, S. (2024). "Language Model Cascades: Token-level uncertainty and beyond." *ICLR 2024*. arXiv 2404.10136. https://arxiv.org/abs/2404.10136
  - Narasimhan, H., et al. (2025). "Faster Cascades via Speculative Decoding." *ICLR 2025*. arXiv 2405.19261.
- **Mechanism:** The probability of a whole output sequence is length-biased, so it's a poor deferral signal. Learned post-hoc rules over token-level uncertainty statistics (quantiles), optionally with embeddings, do better. Speculative cascades implement deferral through speculative execution.
- **Key results:** Learned token-level deferral rules clearly beat simple aggregation (FLAN-T5 experiments). Speculative cascades give better cost–quality trade-offs than either plain cascades or speculative decoding (Gemma, T5).
- **Relevance to Omnitrix:** When S1 output is longer than a label (for example Librarian extraction), don't use mean log-probability as confidence. Use the minimum or a low quantile of token probabilities, or a small learned rule.

### 2.10 Cascade routing: unifying routing and cascading
- **Citation:** Dekoninck, J., Baader, M., Vechev, M. (2025). "A Unified Approach to Routing and Cascading for LLMs." *ICML 2025* (PMLR 267). arXiv 2410.10347. https://proceedings.mlr.press/v267/dekoninck25a.html
- **Mechanism:** Derives an optimal cascading strategy, proves an existing routing strategy optimal, and proposes cascade routing, which decides at each step which model (if any) to call next from quality and cost estimates.
- **Key results:** Cascade routing consistently beats routing alone and cascading alone by a large margin. **The quality estimators are the critical factor.**
- **Relevance to Omnitrix:** Put the effort into calibrated quality estimators, not elaborate routing logic.

### 2.11 Self-REF: confidence tokens for routing and rejection
- **Citation:** Chuang, Y.-N., Sarma, P. K., Gopalan, P., et al. (2025). "Learning to Route LLMs with Confidence Tokens." *ICML 2025*. arXiv 2410.13284. https://arxiv.org/abs/2410.13284
- **Mechanism:**
  - LoRA-fine-tune the small LLM to append `<CN>` after answers it got right and `<UN>` after answers it got wrong. Gradients on the wrong answers themselves are masked.
  - Confidence = P(`<CN>`) / (P(`<CN>`) + P(`<UN>`)), thresholded to route or reject.
- **Key results:** With Llama3-8B-Instruct on MMLU, confidence-based routing of just 39% of queries matched the performance of sending everything to Llama3-70B-Instruct, with up to 2.03× lower latency. It beat verbalized confidence and raw token probabilities on both routing and rejection.
- **Relevance to Omnitrix:** A post-hackathon upgrade: LoRA-train Qwen3-4B on its own audited mistakes. For the hackathon, P(label) with Platt scaling approximates it.

### 2.12 Gatekeeper
- **Citation:** Rabanser, S., Rauschmayr, N., Kulshrestha, A., et al. (2025). "Gatekeeper: Improving Model Cascades Through Confidence Tuning." *NeurIPS 2025* (DOI 10.52202/085713-0656). Earlier at the ICML 2025 TTODLer-FM workshop. arXiv 2502.19335. https://arxiv.org/abs/2502.19335
- **Mechanism:**
  - Fine-tune the small model with a combined loss: α × cross-entropy on examples it gets right, plus (1−α) × KL divergence to uniform on examples it gets wrong. This separates the confidence of correct and incorrect answers.
  - Defer when max-softmax probability or negative predictive entropy falls below τ.
- **Key results:** Substantially better deferral across encoder-only, decoder-only (Gemma 2B deferring to 7B) and encoder–decoder setups (abstract).
- **Relevance to Omnitrix:** Same idea as Self-REF: train S1 to be good at *deferring*, not only at being accurate.

### 2.13 Rational tuning of cascade thresholds
- **Citation:** Zellinger, M. J., Thomson, M. (2025). "Rational Tuning of LLM Cascades via Probabilistic Modeling." *TMLR 2025*. arXiv 2501.09345. https://arxiv.org/abs/2501.09345
- **Mechanism:** Fit a parametric Markov-copula model of how calibrated confidences co-vary across cascade stages, then set thresholds by continuous optimization instead of grid or Bayesian search.
- **Key results:** Area under the error–cost curve improves by 4.3% on average for cascades of 3 or more models, and by 10.2% with 30 or fewer training examples.
- **Relevance to Omnitrix:** Early on there will be few labels per decision type. Model-based threshold tuning is more sample-efficient than grid search.

### 2.14 Cascades with a human tier (closest blueprint)
- **Citation:** Fanconi, C., van der Schaar, M. (2025). "Cascaded Language Models for Cost-effective Human-AI Decision-Making." *NeurIPS 2025* (DOI 10.52202/085713-0388). arXiv 2506.11887. https://arxiv.org/abs/2506.11887
- **Mechanism:**
  - A base model answers. A **deferral policy** based on confidence decides whether to accept or regenerate with the large model. Then an **abstention policy** based on uncertainty decides whether to hand the case to a human expert.
  - Confidence comes from a "surrogate token probability", P(YES) / (P(YES) + P(NO)), or from self-verification. It is calibrated with Bayesian logistic regression (a Bayesian version of Platt scaling) on **100 samples**.
  - The posterior standard deviation serves as the uncertainty for abstention.
  - Thresholds are updated online with Adam (learning rate 0.05, batch size 10) from human feedback.
- **Key results:**
  - Model pairs tested: Qwen2.5-1.5B→7B, Llama3.2-1B→Llama3.1-8B, Llama3.2-3B→Llama3.1-8B.
  - The cascade beats single models on accuracy per cost on most benchmarks, with large incremental-benefit-per-cost gains on ARC-Easy and ARC-Challenge.
  - Gains are small or negative on MedQA and MedMCQA, where confidence estimation was poor.
  - Online learning lowered cumulative regret over 1,000 samples compared with either model alone.
- **Relevance to Omnitrix:** The most direct blueprint for S1 → S2 → human. It uses small models, YES/NO token probabilities, 100-sample Bayesian calibration, posterior-uncertainty abstention, and online threshold learning from human feedback (Herald approvals). Caveat: when confidence is poor, the cascade doesn't help.

### 2.15 Arch-Router (preference-aligned, small-model routing)
- **Citation:** Tran, C., Paracha, S., Hafeez, A., Chen, S. (2025). "Arch-Router: Aligning LLM Routing with Human Preferences." arXiv 2506.16655. https://arxiv.org/abs/2506.16655
- **Mechanism:**
  - A 1.5B model (Qwen2.5-1.5B), supervised-fine-tuned on 43k synthetic conversations.
  - It maps a conversation to one of the user's natural-language "domain–action" route policies.
  - New routes or models are added by editing the policy list, with no retraining.
- **Key results:**
  - Overall routing accuracy 93.17% vs Claude-3.7-Sonnet's 92.79%.
  - Turn-level 96.05%, vs 34.37 for the untuned Qwen2.5-1.5B base.
  - Latency 51 ± 12 ms vs 1,450 ± 385 ms for Claude-3.7-Sonnet.
- **Relevance to Omnitrix:** Precedent for a small model doing the Chief-of-Staff's "which agent handles this?" dispatch (D8) from natural-language policies. The untuned-vs-tuned gap shows that **specialization matters**.

### 2.16 Agreement-based cascading (ABC)
- **Citation:** Kolawole, S., Dennis, D., Talwalkar, A., Smith, V. (2025). "Agreement-Based Cascading for Efficient Inference." *TMLR 2025*. arXiv 2407.02348. https://arxiv.org/abs/2407.02348
- **Mechanism:** Run a small ensemble at each level and escalate when its members disagree.
- **Key results:** 2–25× lower average price per token or request than state-of-the-art LLM cascades through APIs, and up to 14× lower communication cost for edge-to-cloud inference.
- **Relevance to Omnitrix:** Ensemble Qwen3-1.7B and Qwen3-4B, or prompt variants, and escalate on disagreement. This is cheap if both models stay resident in memory (slice C to confirm).

### 2.17 The 2026 frontier on routing and cascades
- **Citation:**
  - Bouchard, D. (2026). "Is Escalation Worth It? A Decision-Theoretic Characterization of LLM Cascades." arXiv 2605.06350.
  - Mahmood, R. (2026). "Routing, Cascades, and User Choice for LLMs." *ICLR 2026*. arXiv 2602.09902.
  - Chang, R., Kwon, D., Lee, J., Verma, N. (2026). "CascadeDebate: Multi-Agent Deliberation for Cost-Aware LLM Cascades." arXiv 2604.12262.
  - Wang, Z., et al. (2026). "Signed Rescue Routing: Harm-Aware Cascades for Efficient LLM Inference." arXiv 2609.07786.
  - Liu, Z., Zeng, Y., Chang, Y., Lin, L. (2026). "Forced Deferral: Manipulating Routing Decisions in Multimodal LLM Cascades." arXiv 2606.15308.
  - Moslem, Y., et al. (2026). "Cluster, Route, Escalate: Cascaded Framework for Cost-Aware LLM Serving." arXiv 2606.27457.
  - Surveys:
    - Varangot-Reille, C., et al. "Doing More with Less: A Survey on Routing Strategies for Resource Optimisation in LLM-Based Systems." *JAIR* 86 (2026), DOI 10.1613/jair.1.19801; arXiv 2502.00409.
    - Moslem, Y., Kelleher, J. D. (2026). "Dynamic Model Routing and Cascading for Efficient LLM Inference: A Survey." *TMLR 2026*; arXiv 2603.04445.
- **Mechanism and key results:**
  - **Bouchard:**
    - Two-model cascades have a piecewise-concave cost–quality frontier.
    - A lightweight *pre-generation* router beat the best cascade policy on 4 of 5 datasets. The main reason is that cascades must pay for the cheap model's generation before deciding to escalate.
    - Longer multi-stage chains gave no meaningful held-out gain over the best two-model cascade.
  - **Mahmood:** When users can re-prompt or give up, the optimal policy is almost always static routing with no cascading. Provider-optimal and user-preferred routes can diverge.
  - **CascadeDebate:**
    - Runs a small multi-agent deliberation only on uncertain cases at each escalation boundary, with humans as the final fallback.
    - Up to 26.75% better than single-model cascades.
    - An online threshold optimizer gives 20.98–52.33% relative accuracy gains over fixed thresholds.
  - **Signed Rescue Routing:** Ranks requests by the predicted probability that the large model *fixes* the small model's answer minus the probability that it *breaks* a correct one. This is Bayes-optimal under a fixed escalation budget. Tested with Qwen3-4B deferring to Qwen3-8B. The v1 abstract still has "TBD" placeholders instead of results.
  - **Forced Deferral:** Adversarial inputs can lower the weak model's confidence and force escalation.
  - **Cluster, Route, Escalate:** Cluster-level routing plus escalation driven by quality estimation keeps 97–99% of the strongest model's accuracy.
- **Relevance to Omnitrix:**
  1. When S1 outputs a label (a few tokens), the "cascade tax" is tiny, so cascades are fine. For long generations (Writer), route up front.
  2. Escalate when S2 is expected to *change and improve* the answer (the signed-rescue logic), not whenever S1 is uncertain.
  3. Confidence is an attack surface. Untrusted email or news text can push S1 toward escalation or overconfidence. Rate-limit escalations per source, and never let S1 loosen a security gate.

---

## 3. Deciding about retrieval and evidence

### 3.1 Mallen et al.: when not to trust parametric memory
- **Citation:** Mallen, A., Asai, A., Zhong, V., Das, R., Khashabi, D., Hajishirzi, H. (2023). "When Not to Trust Language Models: Investigating Effectiveness of Parametric and Non-Parametric Memories." *ACL 2023*. arXiv 2212.10511. https://aclanthology.org/2023.acl-long.546/
- **Mechanism:**
  - On PopQA, LMs memorize facts about popular entities but fail on the long tail, and scaling barely helps there.
  - "Adaptive Retrieval" retrieves only when the question entity's popularity falls below a threshold tuned per relation type on dev data.
- **Key results:**
  - GPT-3 davinci-003 with adaptive retrieval (GenRead plus Contriever) scored 46.5% on PopQA, 5.3 points above any non-adaptive method.
  - With BM25, davinci-003 retrieved for only 40% of questions. The authors report up to a 10% improvement while roughly halving GPT-3 API cost.
  - Retrieval *hurt* on about 10% of questions the LM would otherwise have answered correctly.
- **Relevance to Omnitrix:** For a *personal* knowledge base the popularity logic flips. Nearly all user-specific facts (clients, deals, past decisions) are long-tail, so **retrieval should be the default for any query that mentions an entity**. Skip retrieval only for generic world knowledge or chit-chat. A cheap code-level proxy: does the query mention an entity that exists in the graph?

### 3.2 SKR: self-knowledge guided retrieval
- **Citation:** Wang, Y., Li, P., Sun, M., Liu, Y. (2023). "Self-Knowledge Guided Retrieval Augmentation for Large Language Models." *Findings of EMNLP 2023*. arXiv 2310.05002. https://aclanthology.org/2023.findings-emnlp.691/
- **Mechanism:** Collect "self-knowledge" labels recording whether retrieval helped or hurt on training questions. For a new question, decide by prompting, a small classifier, or **k-nearest-neighbour search over similar past questions**.
- **Key results:** Beats chain-of-thought-only and always-retrieve baselines with InstructGPT and ChatGPT (no single headline number).
- **Relevance to Omnitrix:** A kNN over past decisions in pgvector is a cheap S1 for D4 that updates itself. Log whether retrieval changed the answer, and reuse the neighbours' outcomes.

### 3.3 FLARE: active retrieval during generation
- **Citation:** Jiang, Z., Xu, F. F., Gao, L., et al. (2023). "Active Retrieval Augmented Generation." *EMNLP 2023*. arXiv 2305.06983. https://arxiv.org/abs/2305.06983
- **Mechanism:** Generate a tentative next sentence. If any token falls below a probability threshold, use the sentence as a search query (with the uncertain tokens masked), retrieve, and regenerate.
- **Key results:** Best or competitive on 4 long-form, knowledge-intensive tasks.
- **Relevance to Omnitrix:** Needs token logprobs. A candidate for mid-draft fact retrieval by the Writer agent.

### 3.4 Self-RAG: reflection tokens (the core precedent for D4, D5 and D6)
- **Citation:** Asai, A., Wu, Z., Wang, Y., Sil, A., Hajishirzi, H. (2024). "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection." *ICLR 2024*. arXiv 2310.11511. https://arxiv.org/abs/2310.11511
- **Mechanism:**
  - The generator emits four kinds of reflection token:

    | Token | Values |
    |---|---|
    | Retrieve | yes, no, continue |
    | IsRel | relevant, irrelevant |
    | IsSup | fully supported, partially supported, no support |
    | IsUse | 5 to 1 |

  - GPT-4 produced 4k–20k labels per token type. These were distilled into a Llama-2-7B critic, which then labelled the generator's training data.
  - At inference, retrieval fires when P(Retrieve=yes), normalized over the Retrieve options, exceeds a threshold (default 0.2).
  - Candidate segments are ranked by LM probability plus a weighted sum of critique-token probabilities. Default weights: IsRel 1.0, IsSup 1.0, IsUse 0.5.
- **Key results:** The critic agrees with GPT-4 labels more than 90% of the time on most token types. Self-RAG at 7B and 13B beats ChatGPT and retrieval-augmented Llama2-chat on open-domain QA, reasoning and fact verification.
- **Relevance to Omnitrix:** **Three of Omnitrix's decisions are exactly Self-RAG's reflection tokens:** D4 is Retrieve, D5 is IsRel, and D6 is IsSup. The recipe is also Omnitrix's: labels from a big model, distilled into a small critic. Here that means Qwen3-14B labels feeding a Qwen3-4B or 1.7B critic, first as prompts and later with LoRA. Use normalized label-token probabilities with a tunable threshold per decision.

### 3.5 CRAG: a lightweight retrieval evaluator with three actions
- **Citation:** Yan, S.-Q., Gu, J.-C., Zhu, Y., Ling, Z.-H. (2024). "Corrective Retrieval Augmented Generation." arXiv 2401.15884. arXiv only; an ICLR 2025 submission was withdrawn. https://arxiv.org/abs/2401.15884
- **Mechanism:**
  - A T5-large evaluator (0.77B), fine-tuned on PopQA relevance labels, scores each retrieved document from −1 to 1.
  - Two thresholds give three actions:
    - **Correct** (above the upper threshold): refine the documents by splitting, filtering and recomposing.
    - **Incorrect** (all below the lower threshold): discard and search the web.
    - **Ambiguous** (in between): do both.
- **Key results:**
  - Evaluator accuracy on PopQA: 84.3%, vs ChatGPT 58.0%, ChatGPT with CoT 62.4%, and ChatGPT few-shot 64.7%.
  - Thresholds (upper, lower): PopQA (0.59, −0.99); PubHealth and ARC (0.5, −0.91); Biography (0.95, −0.91).
- **Relevance to Omnitrix:** The canonical **three-band accept / reject / escalate** pattern for D5. It also shows a fine-tuned sub-1B classifier beating a prompted large LLM on a narrow judgement. In Omnitrix, "Incorrect" should mean "widen the local search or hand to Researcher", not web search, to keep data sovereign.

### 3.6 Adaptive-RAG: a query-complexity classifier
- **Citation:** Jeong, S., Baek, J., Cho, S., Hwang, S. J., Park, J. C. (2024). "Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity." *NAACL 2024*. arXiv 2403.14403. https://aclanthology.org/2024.naacl-long.389/
- **Mechanism:**
  - A T5-Large classifier sorts each query into A (no retrieval), B (single-step retrieval) or C (multi-step iterative retrieval).
  - Labels are generated automatically: the simplest strategy that actually answered correctly wins. Where none did, the dataset's nature decides (single-hop datasets map to B, multi-hop to C).
- **Key results:**
  - Classifier accuracy is only 54.52% overall (30.52% on no-retrieval, 66.28% single, 65.45% multi).
  - Even so, with GPT-3.5 Adaptive-RAG reached F1 50.91 at 1.03 retrieval steps and 1.46 relative time. The multi-step method got F1 50.87 at 2.81 steps and 3.33 relative time.
  - With an oracle classifier: F1 62.80 at 0.50 steps.
- **Relevance to Omnitrix:** Routing between *strategies* (answer from working memory, one vector lookup, or a multi-hop graph walk) pays off even with a mediocre classifier, and the oracle gap shows large headroom. Researcher should route its queries this way.

### 3.7 DRAGIN
- **Citation:** Su, W., Tang, Y., Ai, Q., Wu, Z., Liu, Y. (2024). "DRAGIN: Dynamic Retrieval Augmented Generation based on the Real-time Information Needs of Large Language Models." *ACL 2024*; the arXiv title omits "Real-time". arXiv 2403.10081. https://aclanthology.org/2024.acl-long.702/
- **Mechanism:**
  - RIND scores each generated token as entropy × the maximum attention it receives from later tokens × a stopword filter. Retrieval fires when the score crosses a threshold.
  - The query is built from the most-attended tokens (QFS).
- **Key results:** Best across 2WikiMultihopQA, HotpotQA, StrategyQA and IIRC with Llama2-7B, Llama2-13B and Vicuna-13B. For example, HotpotQA exact match 0.314 vs FLARE's 0.180 on Llama2-13B-chat.
- **Relevance to Omnitrix:** Needs attention weights, which is white-box access. Probably not reachable through a chat API. Slice C should confirm; otherwise skip it.

### 3.8 UAR: Unified Active Retrieval
- **Citation:** Cheng, Q., Li, X., Li, S., et al. (2024). "Unified Active Retrieval for Retrieval Augmented Generation." *Findings of EMNLP 2024*. arXiv 2406.12534. https://arxiv.org/abs/2406.12534
- **Mechanism:**
  - Four binary classifiers, each a single fully connected layer on the frozen LLM's last-input-token hidden state:
    - intent-aware: did the user ask for retrieval?
    - knowledge-aware: does this need facts?
    - time-sensitive: does it depend on recent information?
    - self-aware: does the model lack the knowledge?
  - They run as a decision tree in that order.
- **Key results:** With Llama2-7B-chat on AR-Bench, retrieval-timing accuracy is 85.32%, vs Self-RAG 60.12%, SKR 62.14% and FLARE 56.50%. At 13B: 86.33%.
- **Relevance to Omnitrix:** Breaking D4 into criteria transfers directly. Intent and time-sensitivity can often be plain code (explicit asks, "latest", dates, "what did X say"). Knowledge-need and self-awareness go to S1 prompts.

### 3.9 SeaKR
- **Citation:** Yao, Z., Qi, W., Pan, L., et al. (2024). "SeaKR: Self-aware Knowledge Retrieval for Adaptive Retrieval Augmented Generation." arXiv 2406.19215. https://arxiv.org/abs/2406.19215
- **Mechanism:**
  - Sample k=20 generations and take middle-layer hidden states at the end-of-sequence token.
  - "Self-aware uncertainty" is the (log-)determinant of their regularized Gram matrix. Retrieval fires above a threshold tuned on dev data.
  - Retrieved snippets are re-ranked by which one reduces that uncertainty most.
- **Key results:** On LLaMA-2-7B-chat, F1 on HotpotQA is 39.7 vs DRAGIN 34.2 and FLARE 22.1; on 2WikiMultihopQA it's 36.0 vs 30.0 for DRAGIN.
- **Relevance to Omnitrix:** Strong but expensive: 20 samples plus hidden states. The idea of re-ranking by uncertainty reduction can be approximated black-box, for example by measuring answer agreement given each passage.

### 3.10 Probing-RAG
- **Citation:** Baek, I., Chang, H., Kim, B., Lee, J., Lee, H. (2025). "Probing-RAG: Self-Probing to Guide Language Models in Selective Document Retrieval." *Findings of NAACL 2025*. arXiv 2410.13339. https://arxiv.org/abs/2410.13339
- **Mechanism:** A roughly 5 MB prober (one hidden layer) reads intermediate hidden states of Gemma-2B (even layers from the 6th) and decides whether (more) retrieval is needed. It's trained on about 26k synthetic examples.
- **Key results:**
  - Gemma-2B across 5 QA sets: average accuracy 35.8, vs 29.2 with no retrieval, 27.4 single-step and 26.8 Adaptive-RAG.
  - Skipped retrieval in 57.46% of cases.
  - 1,988 retrieval calls in total, vs 3,068 for Adaptive-RAG and 13,570 for DRAGIN.
- **Relevance to Omnitrix:** Even a 2B model's internals encode when it needs retrieval. This is usable only if the runtime exposes hidden states.

### 3.11 Overconfidence limits self-reported retrieval need
- **Citation:** Ni, S., Bi, K., Guo, J., Cheng, X. (2024). "When Do LLMs Need Retrieval Augmentation? Mitigating LLMs' Overconfidence Helps Retrieval Augmentation." *Findings of ACL 2024*. arXiv 2402.11457.
- **Mechanism and key results:** LLMs are overconfident about the edges of their own knowledge. Methods that reduce this overconfidence let the system retrieve selectively, with far fewer retrieval calls and equal or better results.
- **Relevance to Omnitrix:** Don't take S1's "I know this" at face value without calibration.

### 3.12 Sufficient Context: judge the evidence separately from the model
- **Citation:** Joren, H., Zhang, J., Ferng, C.-S., Juan, D.-C., Taly, A., Rashtchian, C. (2025). "Sufficient Context: A New Lens on Retrieval Augmented Generation Systems." *ICLR 2025*. arXiv 2411.06037. https://openreview.net/forum?id=Jjr2Odj8DJ
- **Mechanism:**
  - Defines "sufficient context": the context makes a plausible answer possible. No ground truth is needed.
  - An autorater classifies each (query, context) pair.
  - Selective generation feeds the sufficiency label and the model's self-rated P(True) or P(Correct) into a **logistic regression**, and abstains below a threshold.
- **Key results:**
  - The best autorater (Gemini 1.5 Pro, 1-shot) is 93% accurate on 115 human-labelled instances. FLAMe is a cheaper but weaker option; TRUE-NLI and a contains-ground-truth check need the answer.
  - Large models tend to answer wrongly rather than abstain when context is insufficient. Small models (Mistral 3, Gemma 2) hallucinate or abstain even when the context *is* sufficient.
  - Selective generation raises the share of correct answers among those given by 2–10% for Gemini, GPT and Gemma.
- **Relevance to Omnitrix:** A key design for D6: **score evidence sufficiency separately from model confidence, and combine the two with a tiny logistic regression.** It's cheap, fits the plain-code rule, and gives Omnitrix an honest "my memory doesn't have enough to answer this" state.

### 3.13 Moskvoretskii et al.: simple uncertainty methods are enough
- **Citation:** Moskvoretskii, V., et al. (2025). "Adaptive Retrieval Without Self-Knowledge? Bringing Uncertainty Back Home." *ACL 2025* (long). arXiv 2501.12835. https://aclanthology.org/2025.acl-long.319/
- **Mechanism:** Benchmarks 35 methods (8 adaptive-retrieval pipelines and 27 uncertainty estimators) on 6 QA datasets with 10 metrics, using LLaMA 3.1-8B-Instruct.
- **Key results:**
  - No method dominates on every axis. But well-established uncertainty estimators (mean and max token entropy, EigValLaplacian, Lex-Similarity, SAR) often match the complex pipelines at a fraction of the compute.
  - Example on Natural Questions:

    | Method | QA score | LM calls | Retrieval calls |
    |---|---|---|---|
    | Lex-Similarity | 0.512 | 1.6 | 0.58 |
    | DRAGIN | 0.480 | 4.5 | 2.24 |
    | AdaptiveRAG | 0.496 | 2.0 | 0.98 |

- **Relevance to Omnitrix:** Strong evidence that cheap S1 signals, such as token entropy on a short draft answer, are enough for D4. Don't build DRAGIN-style machinery.

### 3.14 2025–2026 follow-ups (brief)
- **Wu, Gu, Chang, Peng (2025). "Self-Routing RAG" (arXiv 2504.01018).** Treats the LLM itself as one knowledge source to choose from, and combines LLM uncertainty with an external "policy datastore" of past decisions (nearest neighbours). Across three 7B-class LLMs it beats a strong selective-retrieval baseline by 8.5%, 2.1% and 4.7%, with 26%, 40% and 21% fewer retrievals, and needs no per-dataset threshold tuning.
- **Sah, Zhang, Lian (2026). "Beyond Self-Knowledge: Propagating Uncertainty Across Reasoning and Retrieval in LLMs" (arXiv 2607.25600).**
  - Routing on verbalized confidence, with a threshold frozen from validation data, gave mean token F1 of 0.483, vs 0.467 for always retrieving and 0.401 for never retrieving, and retrieved 20.4% fewer passages.
  - But total token use rose 28.2% because of the provisional-answer probe.
  - Confidence was poorly calibrated in absolute terms (AUROC 0.628 for predicting whether retrieval would help).
- **Guo, Gu, Jin, Spanos, Lavaei (2026). "LLMs Should Express Uncertainty Explicitly" (arXiv 2604.05306).** Post-training the model to give a verbalized confidence at the end, or an `<uncertain>` marker mid-reasoning, cuts overconfident errors, and both signals work as retrieval triggers.
- **Zhou, Huang, Liu, et al. (2026). "Do Retrieval Augmented Language Models Know When They Don't Know?" (AAAI 2026; arXiv 2509.01476).** Retrieval-augmented models *over-refuse* when every retrieved document is irrelevant, even on questions they could answer. Better refusal doesn't mean better calibration.
- **Guo, Wu, Yiu (2026). "When to Retrieve During Reasoning: Adaptive Retrieval for Large Reasoning Models" (SIGIR 2026; arXiv 2604.26649).** A step-level uncertainty detector for thinking models: +10.1 F1 over standard RAG, with 47% fewer retrieval calls than fixed-interval (IRCoT-style) retrieval.
- **Dhole (2025). "To Retrieve or Not to Retrieve?" (ICLR 2025 workshop; arXiv 2501.09292).** Sampling-based uncertainty measures (Degree Matrix Jaccard, Eccentricity) nearly halve retrieval calls with a small accuracy loss.
- **Relevance to Omnitrix:** The 2025–26 consensus is that cheap uncertainty signals plus a nearest-neighbour memory of past decisions are competitive. Watch the token overhead of the "draft an answer, then decide" pattern, and design an "irrelevant evidence" path that doesn't force a refusal.

---

## 4. Confidence, calibration and abstention

### 4.1 Kadavath et al.: P(True) and P(IK)
- **Citation:** Kadavath, S., Conerly, T., Askell, A., et al. (2022). "Language Models (Mostly) Know What They Know." arXiv 2207.05221. https://arxiv.org/abs/2207.05221
- **Mechanism:**
  1. Large pretrained models are well calibrated on multiple-choice and true/false questions when the options are presented as letters.
  2. **P(True):** the model proposes an answer, then is asked whether it's true. Confidence is the probability of "True". It works better if the model first sees several of its own samples.
  3. **P(IK):** a value head predicts, before answering, whether the model knows the answer. Labels come from 30 samples per question.
- **Key results:**
  - RLHF policies looked miscalibrated, but a single temperature of **T=2.5** largely fixed that.
  - P(IK) trained on TriviaQA: AUROC 0.864 on TriviaQA but only **0.606 on LAMBADA**. Training on all tasks raised LAMBADA to 0.853, so cross-task generalization is weak.
  - Calibration improves with model size and with few-shot prompts.
- **Relevance to Omnitrix:** Frame decisions as lettered multiple choice or true/false. Expect post-trained Qwen3 to need temperature scaling. Calibrate **per decision type**, because P(IK)-style signals don't transfer across tasks.

### 4.2 Lin, Hilton, Evans: verbalized uncertainty
- **Citation:** Lin, S., Hilton, J., Evans, O. (2022). "Teaching Models to Express Their Uncertainty in Words." *TMLR* (2022). arXiv 2205.14334. https://arxiv.org/abs/2205.14334
- **Mechanism:** Fine-tune GPT-3 to output an answer plus a verbalized confidence ("90%", "high"). Introduces the CalibratedMath suite.
- **Key results:** After fine-tuning, verbalized probabilities are well calibrated and stay moderately calibrated under distribution shift.
- **Relevance to Omnitrix:** Verbalized confidence *can* be calibrated, but here it took supervised fine-tuning. Don't expect it zero-shot from a 4B model.

### 4.3 Tian et al.: "Just Ask for Calibration"
- **Citation:** Tian, K., Mitchell, E., Zhou, A., et al. (2023). "Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback." *EMNLP 2023*. arXiv 2305.14975. https://arxiv.org/abs/2305.14975
- **Mechanism:** Compares several ways of getting a confidence score, with and without temperature scaling:
  - label probability;
  - "Is True" probability;
  - verbalized confidence (one- or two-stage, top-k guesses, chain-of-thought);
  - linguistic expressions such as "likely".
- **Key results:**
  - For RLHF'd API models, verbalized top-k is often best. ChatGPT on TriviaQA: ECE 0.054 (verbalized, 1-stage, top-4) vs 0.140 (label probability). A relative ECE reduction of about 50% is typical.
  - For **Llama-2-70B-chat** the benefit is much less consistent (per the authors' Table 5). Verbalized confidence cuts ECE but *lowers discrimination*: SciQ AUC 0.648 (verbalized top-1 and top-4) vs 0.707 (label probability); TriviaQA AUC 0.816 (top-4) vs 0.865.
  - Temperature scaling helps label probability too: ChatGPT TriviaQA ECE 0.140 → 0.097.
- **Relevance to Omnitrix:** For open models, **label-token probability plus temperature or Platt scaling is the safer default**. Keep verbalized top-k as an A/B option. Routing depends on ranking (AUROC), which post-hoc scaling cannot fix; ECE can be fixed afterwards.

### 4.4 Xiong et al.: black-box confidence elicitation
- **Citation:** Xiong, M., Hu, Z., Lu, X., et al. (2024). "Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs." *ICLR 2024*. arXiv 2306.13063. https://arxiv.org/abs/2306.13063
- **Mechanism:** Breaks black-box elicitation into three parts: prompting strategy, sampling, and aggregation (consistency).
- **Key results:**
  - Verbalized confidence is overconfident.
  - Calibration and failure prediction improve with model scale.
  - Consistency across samples and better aggregation help.
  - White-box methods beat black-box ones only narrowly (for example, AUROC 0.605 vs 0.522).
  - Every method struggles on expert-knowledge tasks.
- **Relevance to Omnitrix:** Expect worse verbalized calibration from 1.7B–4B models than from GPT-4-class ones. Prefer agreement across a few samples plus token probabilities.

### 4.5 Post-training (instruction tuning, RLHF, RL) degrades calibration
- **Citation:**
  - OpenAI (2023). "GPT-4 Technical Report." arXiv 2303.08774. Fig. 8.
  - Zhu, C., Xu, B., Wang, Q., Zhang, Y., Mao, Z. (2023). "On the Calibration of Large Language Models and Alignment." *Findings of EMNLP 2023*. arXiv 2311.13240.
  - Xie, J., Chen, A. S., Lee, Y., Mitchell, E., Finn, C. (2024). "Calibrating Language Models with Adaptive Temperature Scaling." *EMNLP 2024*. arXiv 2409.19817.
  - Leng, J., Huang, C., Zhu, B., Huang, J. (2025). "Taming Overconfidence in LLMs: Reward Calibration in RLHF." *ICLR 2025*. arXiv 2410.09724. https://openreview.net/forum?id=l0tg0jzsdL
  - Nakkiran, P., Bradley, A., Goliński, A., Ndiaye, E., Kirchhof, M., Williamson, S. (2025). "Trained on Tokens, Calibrated on Concepts: The Emergence of Semantic Calibration in LLMs." arXiv 2511.04869.
  - Sanz-Guerrero, M., Mager, M., von der Wense, K. (2026). "Large Language Models Are Overconfident in Their Own Responses." *Findings of ACL 2026*. arXiv 2606.03437.
- **Mechanism and key results:**
  - **GPT-4 report:** the pre-trained model was highly calibrated on an MMLU subset; post-training reduced calibration.
  - **Zhu et al.:** a systematic study of calibration through the pretraining and alignment stages.
  - **Xie et al. (ATS):** predicts a per-token temperature, fitted on supervised fine-tuning data. Improves calibration by 10–50% after RLHF without hurting performance.
  - **Leng et al.:** PPO reward models favour confident-sounding answers regardless of quality, which makes RLHF models verbally overconfident. Their PPO-M and PPO-C variants reduce calibration error (Llama3-8B, Mistral-7B).
  - **Nakkiran et al.:** base LLMs are *semantically* calibrated (measured by sampling) on open QA. RL instruction-tuning systematically breaks this, and so does chain-of-thought.
  - **Sanz-Guerrero et al.:** chat templates add an "ownership bias". Models are up to 26% more confident in their *own* answers than in identical answers attributed to the user. Presenting the answer as user input during elicitation improves calibration by up to 26% across six open-weight LLMs.
- **Relevance to Omnitrix:** Qwen3 Instruct and hybrid models are post-trained, so **assume they're miscalibrated** and calibrate each decision on held-out data. **When S1 or S2 checks an answer, present it as someone else's** ("A colleague proposed…"), not as the model's own previous turn.

### 4.6 Reasoning, RL and confidence (2025–26)
- **Citation:**
  - Yoon, D., Kim, S., Yang, S., et al. (2025). "Reasoning Models Better Express Their Confidence." *NeurIPS 2025*. arXiv 2505.14489.
  - Song, L., Shi, T., Zhao, J. (2025). "The Hallucination Tax of Reinforcement Finetuning." *Findings of EMNLP 2025*. arXiv 2505.13988. https://aclanthology.org/2025.findings-emnlp.112/
  - Damani, M., Puri, I., Slocum, S., et al. (2026). "Beyond Binary Rewards: Training LMs to Reason About Their Uncertainty." *ICLR 2026*. arXiv 2507.16806. https://openreview.net/forum?id=ASQ649zdHm
  - Zhai, S., Liang, J., Kang, D. (2026). "Abstain-R1: Calibrated Abstention and Post-Refusal Clarification via Verifiable RL." *ACL 2026*. arXiv 2604.17073.
- **Mechanism and key results:**
  - **Yoon et al.:** across six reasoning models and six datasets, reasoning models had better verbalized calibration than their non-reasoning counterparts in 33 of 36 settings. The gains come from slow-thinking behaviours such as exploring alternatives and backtracking. Non-reasoning models also improve when prompted to think slowly.
  - **Hallucination tax:** standard reinforcement fine-tuning can cut refusal rates on unanswerable problems by more than 80%. Mixing in 10% unanswerable examples restores appropriate refusals.
  - **RLCR:** the reward is correctness plus a Brier score on a verbalized confidence given after reasoning. This provably yields models that are both accurate and calibrated. Ordinary RL hurts calibration; RLCR improves it with no accuracy loss.
  - **Abstain-R1:** a 3B model learns to abstain *and* to say what information is missing, competitive with much larger systems.
- **Relevance to Omnitrix:** S2 (Qwen3-14B, thinking) may state confidence better than S1, so use it as a second opinion on escalated cases. RL-tuned reasoning models may **under-abstain**, so compute the "insufficient evidence" state in code with a logistic combiner (see 3.12) rather than trusting the model to refuse. Abstain-R1 maps onto Omnitrix asking the user one targeted question.

### 4.7 Contextual calibration and batch calibration (label-bias correction)
- **Citation:**
  - Zhao, T. Z., Wallace, E., Feng, S., Klein, D., Singh, S. (2021). "Calibrate Before Use: Improving Few-Shot Performance of Language Models." *ICML 2021*. arXiv 2102.09690. https://arxiv.org/abs/2102.09690
  - Zhou, H., Wan, X., Proleev, L., et al. (2024). "Batch Calibration: Rethinking Calibration for In-Context Learning and Prompt Engineering." *ICLR 2024*. arXiv 2309.17249.
- **Mechanism:**
  - **Contextual calibration:** feed the prompt a content-free input such as "N/A", read off the bias toward each label, and rescale predictions so that input would come out uniform.
  - **Batch calibration:** estimate the contextual bias from the batch of real inputs instead. It's zero-shot and inference-only.
- **Key results:** Contextual calibration gives up to 30.0% absolute accuracy gains (GPT-3, GPT-2) and less variance across prompts. Batch calibration beats earlier calibration baselines on more than 10 tasks (PaLM 2, CLIP) at negligible cost.
- **Relevance to Omnitrix:** Cheap fixes for S1 label bias. Compute label priors once per prompt template (from a content-free input or the batch mean) and divide them out. This is plain code.

### 4.8 Surface-form competition
- **Citation:** Holtzman, A., West, P., Shwartz, V., Choi, Y., Zettlemoyer, L. (2021). "Surface Form Competition: Why the Highest Probability Answer Isn't Always Right." *EMNLP 2021*. arXiv 2104.08315. https://aclanthology.org/2021.emnlp-main.564/
- **Mechanism:** Probability mass gets split between synonyms ("computer" vs "PC"), so the highest-probability option can be wrong. Domain-conditional PMI re-weights each option by its prior.
- **Key results:** Consistent zero-shot gains over both calibrated and uncalibrated scoring for GPT-2 and GPT-3 on multiple-choice sets.
- **Relevance to Omnitrix:** Use short, unambiguous, single-token labels (A/B/C, YES/NO) rather than free-text labels, or normalize by each label's prior.

### 4.9 Label-token, position and format biases
- **Citation:**
  - Zheng, C., Zhou, H., Meng, F., Zhou, J., Huang, M. (2024). "Large Language Models Are Not Robust Multiple Choice Selectors." *ICLR 2024* (spotlight). arXiv 2309.03882.
  - Zheng, L., Chiang, W.-L., Sheng, Y., et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." *NeurIPS 2023 Datasets & Benchmarks*. arXiv 2306.05685.
  - Wang, P., Li, L., Chen, L., et al. (2024). "Large Language Models are not Fair Evaluators." *ACL 2024*. arXiv 2305.17926. https://aclanthology.org/2024.acl-long.511/
  - Sclar, M., Choi, Y., Tsvetkov, Y., Suhr, A. (2024). "Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design…" *ICLR 2024*. arXiv 2310.11324.
- **Mechanism and key results:**
  - **Selection bias (PriDe):** across 20 LLMs, "selection bias" in multiple-choice answers comes mainly from a prior preference for certain option-ID tokens. PriDe estimates that prior by permuting the options on a few samples, then removes it from the rest.
  - **MT-Bench position bias** (default prompt), share of verdicts that stay the same when the two answers swap places:

    | Judge | Position consistency |
    |---|---|
    | GPT-4 | 65.0% |
    | GPT-3.5 | 46.2% |
    | Claude-v1 | 23.8% |

    Claude-v1 favoured the first position 75.0% of the time.
  - **MT-Bench verbosity attack:** fooled Claude-v1 and GPT-3.5 91.3% of the time, GPT-4 8.7%.
  - **MT-Bench agreement:** GPT-4 agreed with humans 85% (excluding ties), vs 81% human–human.
  - **Wang et al.:** just reordering answers let Vicuna-13B "beat" ChatGPT on 66 of 80 queries when ChatGPT was the judge. Fixes:
    - require multiple pieces of evidence before scoring;
    - swap the order and average the verdicts;
    - bring in a human when the swapped verdicts disagree.
  - **Sclar et al.:** meaning-preserving formatting changes swing accuracy by up to 76 points (LLaMA-2-13B). The effect persists with scale and instruction tuning.
- **Relevance to Omnitrix:**
  - Run every S1 pairwise or choice decision (D2 candidate matches, D5 passage choice) **in both orders and average**.
  - Freeze prompt templates and version them.
  - Disagreement across the two orders is a **free escalation signal**.

### 4.10 Semantic entropy
- **Citation:**
  - Kuhn, L., Gal, Y., Farquhar, S. (2023). "Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation in Natural Language Generation." *ICLR 2023* (spotlight). arXiv 2302.09664.
  - Farquhar, S., Kossen, J., Kuhn, L., Gal, Y. (2024). "Detecting hallucinations in large language models using semantic entropy." *Nature* 630:625–630. DOI 10.1038/s41586-024-07421-0.
- **Mechanism:**
  - Sample several answers and cluster them by meaning, using bidirectional entailment judged by an NLI model (for example DeBERTa-large-MNLI) or an LLM.
  - Compute entropy over the meaning clusters.
  - A discrete variant uses cluster frequencies only, so it needs no logprobs.
- **Key results:**
  - Averaged over 30 task × model combinations, AUROC is **0.790**, vs 0.691 for naive entropy, 0.698 for P(True) and 0.687 for embedding regression.
  - Stable at 0.78–0.81 across LLaMA, Falcon and Mistral. Uses ten generations.
- **Relevance to Omnitrix:** The best-evidenced black-box hallucination detector, but it costs about 10× a single call. Use it at the answer level (Researcher, Fact Checker), not per email. The discrete variant works without logprobs.

### 4.11 Semantic entropy probes (SEPs)
- **Citation:** Kossen, J., Han, J., Razzak, M., Schut, L., Malik, S., Gal, Y. (2024). "Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs." arXiv 2406.15927. https://arxiv.org/abs/2406.15927
- **Mechanism:** A linear probe on the hidden states of *one* generation predicts semantic entropy, which removes the 5–10× sampling cost.
- **Key results:** Keeps high hallucination-detection performance, and generalizes out of distribution better than probes that predict accuracy directly.
- **Relevance to Omnitrix:** A future upgrade, if the runtime exposes hidden states.

### 4.12 Hidden-state truth and error probes
- **Citation:**
  - Azaria, A., Mitchell, T. (2023). "The Internal State of an LLM Knows When It's Lying." *Findings of EMNLP 2023*. arXiv 2304.13734.
  - Burns, C., Ye, H., Klein, D., Steinhardt, J. (2023). "Discovering Latent Knowledge in Language Models Without Supervision" (CCS). *ICLR 2023*. arXiv 2212.03827.
  - Chen, C., Liu, K., Chen, Z., et al. (2024). "INSIDE: LLMs' Internal States Retain the Power of Hallucination Detection." *ICLR 2024*. arXiv 2402.03744.
  - Orgad, H., Toker, M., Gekhman, Z., et al. (2025). "LLMs Know More Than They Show: On the Intrinsic Representation of LLM Hallucinations." *ICLR 2025*. arXiv 2410.02707.
- **Mechanism and key results:**
  - **Azaria and Mitchell:** a classifier on hidden activations separates true from false statements with 71–83% accuracy on balanced sets. That's more reliable than sentence probability, which is confounded by length and word frequency.
  - **CCS:** finds an unsupervised direction in activation space where a statement and its negation get opposite truth values. It averages 4% above zero-shot across 6 models and 10 datasets, and halves prompt sensitivity.
  - **INSIDE:** EigenScore, computed from the eigenvalues of the covariance of several responses' embeddings, plus clipping of extreme activations at test time.
  - **Orgad et al.:** the truthfulness signal concentrates in the exact-answer tokens. Error detectors **do not generalize across datasets**. A model can encode the right answer internally and still output a wrong one.
- **Relevance to Omnitrix:** Promising, but these need white-box access and task-specific training (see Orgad). Only viable after the hackathon, and only if the runtime exposes activations.

### 4.13 Conformal "ask for help": KnowNo and Introspective Planning
- **Citation:**
  - Ren, A. Z., Dixit, A., Bodrova, A., et al. (2023). "Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners." *CoRL 2023* (oral). arXiv 2307.01928. https://arxiv.org/abs/2307.01928
  - Liang, K., Zhang, Z., Fisac, J. F. (2024). "Introspective Planning: Aligning Robots' Uncertainty with Inherent Task Ambiguity." *NeurIPS 2024*. arXiv 2402.06529.
- **Mechanism:**
  - The LLM writes candidate next actions as multiple-choice options (A–D plus "none of these").
  - Next-token scores on the option letters are calibrated with split conformal prediction on N=400 examples, so the prediction set contains a correct option with probability at least 1−ε.
  - If the set has exactly one option, act. Otherwise ask a human to choose.
  - Introspective planning retrieves stored "introspective reasoning" examples, which tightens the sets.
- **Key results:**
  - PaLM-2L; meets user-specified success targets.
  - Compared with a naive "Simple Set" baseline, KnowNo cuts human help by up to 24% in simulation. On hardware, help drops by 14% per step and 8% per trial at matched error.
  - Introspective planning keeps the guarantees with fewer unnecessary clarification requests.
- **Relevance to Omnitrix:** The most direct precedent for **D7 with a statistical guarantee**. Operator proposes actions as options. If the conformal set has more than one option, Herald asks the user on the watch with those options as buttons. Needs about 400 labelled calibration cases per action family, bootstrapped from logs.

### 4.14 Conformal Language Modeling
- **Citation:** Quach, V., Fisch, A., Schuster, T., Yala, A., Sohn, J. H., Jaakkola, T. S., Barzilay, R. (2024). "Conformal Language Modeling." *ICLR 2024*. arXiv 2306.10193. https://arxiv.org/abs/2306.10193
- **Mechanism:** Calibrates a stopping rule for sampling candidate outputs, plus a rejection rule for bad ones, so the returned set contains at least one acceptable answer with high probability. It can also flag individually correct sub-components.
- **Key results:** Validated on open-domain QA, summarization and radiology reports.
- **Relevance to Omnitrix:** For Writer, return a small calibrated set of drafts instead of a single one.

### 4.15 Conformal factuality and selection with guarantees
- **Citation:**
  - Mohri, C., Hashimoto, T. (2024). "Language Models with Conformal Factuality Guarantees." *ICML 2024*. arXiv 2402.10978.
  - Cherian, J. J., Gibbs, I., Candès, E. J. (2024). "Large language model validity via enhanced conformal prediction methods." *NeurIPS 2024*. arXiv 2406.09714.
  - Gui, Y., Jin, Y., Ren, Z. (2024). "Conformal Alignment: Knowing When to Trust Foundation Models with Guarantees." *NeurIPS 2024*. arXiv 2405.10301.
- **Mechanism and key results:**
  - **Mohri and Hashimoto:** drop or weaken claims until a calibrated score threshold is met ("back-off"). This gives 80–90% correctness guarantees while keeping most of the output (FActScore, Natural Questions, MATH).
  - **Cherian et al.:** guarantees that adapt by topic, and learned scoring functions that avoid over-filtering.
  - **Gui et al.:** train an alignment predictor on reference data, then auto-select only outputs above a data-dependent threshold, so that a set fraction of selected outputs is truly aligned (false-discovery-rate style).
- **Relevance to Omnitrix:** Fact Checker can strip unsupported claims from briefings with a guarantee. Conformal Alignment is the right frame for "auto-accept S1 outputs at a controlled false-accept rate."

### 4.16 Abstention survey
- **Citation:** Wen, B., Yao, J., Feng, S., et al. (2025). "Know Your Limits: A Survey of Abstention in Large Language Models." *TACL* 13 (2025). DOI 10.1162/tacl_a_00754. arXiv 2407.18418.
- **Mechanism:** Organizes abstention by query, model and human-values perspectives, and reviews methods, benchmarks and metrics.
- **Relevance to Omnitrix:** A checklist for how to evaluate abstention: coverage vs accuracy, and over-abstention.

### 4.17 APRICOT: an auxiliary confidence model
- **Citation:** Ulmer, D., Gubri, M., Lee, H., Yun, S., Oh, S. J. (2024). "Calibrating Large Language Models Using Their Generations Only." *ACL 2024*. arXiv 2403.05973. https://aclanthology.org/2024.acl-long.824/
- **Mechanism:** Train a separate model to predict the LLM's confidence from its input and output text alone.
- **Key results:** Calibration error competitive with other methods, for both white-box and black-box LLMs, on closed-book QA.
- **Relevance to Omnitrix:** A small separate confidence model (for example a light head over bge-m3 features) works even when the runtime gives no logprobs.

### 4.18 Learning to defer
- **Citation:** Mozannar, H., Sontag, D. (2020). "Consistent Estimators for Learning to Defer to an Expert." *ICML 2020*. arXiv 2006.01862. https://arxiv.org/abs/2006.01862
- **Mechanism:** Learn a classifier and a "rejector" together, using a consistent surrogate loss built from samples of the expert's decisions.
- **Relevance to Omnitrix:** The theory behind human deferral: the best policy depends on how accurate the *human* is on each case type, not only on the model's confidence. Learn where the businessman's input actually changes outcomes.

### 4.19 Expected-score verifiers (2026, brief)
- **Citation:** Kwok, J., Li, S., Atreya, P., et al. (2026). "LLM-as-a-Verifier: A General-Purpose Verification Framework." arXiv 2607.05391.
- **Mechanism and key results:** Replace the judge's single discrete score with the expected score under its distribution over score tokens. Finer score granularity gives better separation between good and bad answers and better-calibrated comparisons.
- **Relevance to Omnitrix:** For graded S1 judgements such as priority 1–5, compute Σ p(k)·k from logprobs instead of taking the argmax.

### 4.20 Uncertainty propagation in compound systems (2026, brief)
- **Citation:** Xia, B., Zhu, L., Gao, E., Lu, Q., Xue, M., Sejdinovic, D. (2026). "Uncertainty Propagation in LLM-Based Systems." arXiv 2604.23505 (work in progress).
- **Mechanism:** A taxonomy of how uncertainty propagates within a model, across system stages and state, and into human and organizational processes.
- **Relevance to Omnitrix:** With about 15 agents and persistent memory, a wrong S1 accept becomes a stored "fact". **Store confidence and provenance with every memory write.**

---

## 5. LLM labels to small classifiers, and small judges

### 5.1 Wang et al.: GPT-3 as a cheap labeller
- **Citation:** Wang, S., Liu, Y., Xu, Y., Zhu, C., Zeng, M. (2021). "Want To Reduce Labeling Cost? GPT-3 Can Help." *Findings of EMNLP 2021*. arXiv 2108.13487. https://arxiv.org/abs/2108.13487
- **Key results:** Reaching the same downstream performance costs 50–96% less with GPT-3 labels than with human labels. Mixing GPT-3 pseudo-labels with human labels does even better on a limited budget.
- **Relevance to Omnitrix:** Supports S2 (Qwen3-14B) as the labeller for S1 training data, with the user's corrections mixed in as gold labels.

### 5.2 Distilling step-by-step
- **Citation:** Hsieh, C.-Y., Li, C.-L., Yeh, C.-K., et al. (2023). "Distilling Step-by-Step! Outperforming Larger Language Models with Less Training Data and Smaller Model Sizes." *Findings of ACL 2023*. arXiv 2305.02301.
- **Mechanism:** Train the small model multi-task, on the LLM's labels plus its rationales.
- **Key results:** A 770M T5 beats few-shot 540B PaLM using 80% of one benchmark's data. Standard fine-tuning of the same T5 can't match PaLM even with 100%.
- **Relevance to Omnitrix:** When distilling S2 into a small model, keep S2's short rationale as an extra training target.

### 5.3 Gilardi et al.: LLM vs crowd annotators
- **Citation:** Gilardi, F., Alizadeh, M., Kubli, M. (2023). "ChatGPT outperforms crowd workers for text-annotation tasks." *PNAS* 120(30): e2305016120. arXiv 2303.15056.
- **Key results:**
  - On 2,382 tweets, zero-shot ChatGPT beat MTurk crowd workers on 4 of 5 tasks (relevance, stance, topics, frames).
  - Its intercoder agreement was higher than both the crowd's and trained annotators'.
  - Under $0.003 per annotation, about 20× cheaper.
- **Relevance to Omnitrix:** Evidence that LLM labels can beat crowd quality on relevance and topic judgements, the same kind of decision as D1 and D5. Validate local Qwen3-14B on a small gold set, since it isn't ChatGPT.

### 5.4 Active learning with LLM annotators
- **Citation:**
  - Zhang, R., Li, Y., Ma, Y., Zhou, M., Zou, L. (2023). "LLMaAA: Making Large Language Models as Active Annotators." *Findings of EMNLP 2023*. arXiv 2310.19596.
  - Xiao, R., et al. (2023). "FreeAL: Towards Human-Free Active Learning in the Era of Large Language Models." *EMNLP 2023*. arXiv 2311.15614.
  - Li, M., Shi, T., Ziems, C., et al. (2023). "CoAnnotating: Uncertainty-Guided Work Allocation between Human and Large Language Models for Data Annotation." *EMNLP 2023*. arXiv 2310.15638.
- **Mechanism and key results:**
  - **LLMaAA:** the LLM labels actively selected examples, using kNN demonstrations and learnable example weights. Task models trained on these labels **outperform the teacher LLM with only hundreds of annotated examples** (NER, relation extraction).
  - **FreeAL:** the LLM annotates, and a small model filters clean examples back to the LLM. Both models improve zero-shot with no human labels.
  - **CoAnnotating:** assigns each item to a human or the LLM based on the LLM's uncertainty. Up to 21% better than random allocation.
- **Relevance to Omnitrix:** The human is scarce and costly, so use CoAnnotating-style uncertainty to pick the few questions that reach the user. LLMaAA suggests small models can surpass their teacher on narrow extraction (Librarian) given a few hundred labels.

### 5.5 Thomas et al.: LLM relevance labels at Bing
- **Citation:** Thomas, P., Spielman, S., Craswell, N., Mitra, B. (2024). "Large language models can accurately predict searcher preferences." *SIGIR 2024*. DOI 10.1145/3626772.3657707. arXiv 2309.10621.
- **Key results:**
  - LLM relevance labels are as accurate as human labellers.
  - Measured against first-party gold labels, they beat third-party workers.
  - Prompt changes, and even paraphrases, shift accuracy.
  - The labels trained notably better rankers.
- **Relevance to Omnitrix:** D5 relevance labelling at scale is established industry practice. Tune the prompt against a small gold set of the user's own judgements.

### 5.6 Prometheus 2: an open evaluator
- **Citation:** Kim, S., Suk, J., Longpre, S., et al. (2024). "Prometheus 2: An Open Source Language Model Specialized in Evaluating Other Language Models." *EMNLP 2024*. arXiv 2405.01535. https://aclanthology.org/2024.emnlp-main.248/
- **Mechanism:** Evaluators built on Mistral-7B and Mixtral-8x7B, trained separately for direct scoring and for pairwise ranking, then weight-merged (DARE-Linear worked best). Supports user-defined rubrics.
- **Key results:**
  - Pairwise accuracy on HHH alignment: 74.66% (7B) and 85.52% (8x7B), vs 90.95% for GPT-4-1106.
  - Agreement with MT-Bench human judgments: 70.78% (7B) and 71.96% (8x7B).
  - Highest agreement with humans and proprietary judges among open evaluators.
- **Relevance to Omnitrix:** Open 7B judges reach roughly GPT-3.5-level pairwise judging, so expect less from a 4B S1. Use S1 judges for binary rubric checks and S2 for nuanced ones.

### 5.7 MiniCheck: small grounding checkers
- **Citation:** Tang, L., Laban, P., Durrett, G. (2024). "MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents." *EMNLP 2024*. arXiv 2404.10774. https://aclanthology.org/2024.emnlp-main.499/
- **Mechanism:** Small fact-checkers trained on hard synthetic examples written by GPT-4: subtle errors produced by structured generation, plus claims that need several sentences combined. Introduces the LLM-AggreFact benchmark.
- **Key results:** MiniCheck-FT5 (770M) reaches **GPT-4 accuracy at 400× lower cost**.
- **Relevance to Omnitrix:** D6 can be handled by a specialized checker under 1B parameters, an ideal S1 for Fact Checker. Slice C should check whether MiniCheck can run locally; otherwise prompt Qwen3-4B with claim–evidence pairs.

### 5.8 Entity matching with LLMs (D2)
- **Citation:**
  - Narayan, A., Chami, I., Orr, L., Ré, C. (2022). "Can Foundation Models Wrangle Your Data?" *PVLDB* 16(4):738–746. arXiv 2205.09911.
  - Peeters, R., Steiner, A., Bizer, C. (2025). "Entity Matching using Large Language Models." *EDBT 2025*. arXiv 2310.11244.
  - Steiner, A., Peeters, R., Bizer, C. (2024, revised 2025). "Fine-tuning Large Language Models for Entity Matching." arXiv 2409.08185.
- **Mechanism and key results:**
  - **Narayan et al.:** prompting large foundation models reached state of the art on entity matching, error detection and imputation.
  - **Peeters et al.**, mean zero-shot F1 across prompts:

    | Model | Mean F1 |
    |---|---|
    | GPT-4 | 86.80 |
    | GPT-4o | 69.90 |
    | GPT-4o-mini | 65.10 |
    | Llama-3.1-70B | 62.77 |
    | Llama-2-70B | 60.98 |
    | Mixtral | 46.90 |

    The standard deviation across prompts was 2.26 F1 for GPT-4 but 6.18–18.54 for the others. There's no single best prompt, and fine-tuning adds 1–26% F1.
  - **Steiner et al.:** fine-tuning substantially improves smaller models (for example Llama 3.1 8B). It helps in-domain generalization but hurts cross-domain transfer. Structured explanations in the training data help 3 of 4 LLMs.
- **Relevance to Omnitrix:** Open models are well below GPT-4 zero-shot and very prompt-sensitive. So:
  1. Do **deterministic blocking in code** first: exact, alias, phone, email and GSTIN matches, then a bge-m3 kNN.
  2. Send only ambiguous candidate pairs to S1, in both orders.
  3. Escalate low-margin cases to S2.
  4. Later, LoRA-tune S1 on the user's confirmed merges.

### 5.9 NLI-based inconsistency detection (D3)
- **Citation:**
  - Laban, P., Schnabel, T., Bennett, P. N., Hearst, M. A. (2022). "SummaC: Re-Visiting NLI-based Models for Inconsistency Detection in Summarization." *TACL* 2022. arXiv 2111.09525.
  - Xu, R., Qi, Z., Guo, Z., et al. (2024). "Knowledge Conflicts for LLMs: A Survey." arXiv 2403.08319.
- **Mechanism and key results:**
  - **SummaC:** splits documents into sentences, scores sentence pairs with an NLI model, and aggregates (SummaCConv). Reaches 74.4% balanced accuracy on the SummaC benchmark, 5 points above prior work.
  - **Xu et al.:** classifies conflicts as context vs memory, between contexts, or within memory.
- **Relevance to Omnitrix:** For D3, break the new fact into claim pairs against candidate stored decisions. Have S1 give an NLI-style three-way label (entails, neutral, contradicts). Only a confident "contradicts" wakes Historian (S2). The memory slice covers this in more depth.

---

## Synthesis A: Turning a small model into a decision with a calibrated confidence

**Techniques that are defaults or required for S1 now**

| # | Technique | How it works | Extra cost | Evidence | Needs | Verdict |
|---|---|---|---|---|---|---|
| 1 | Constrained label-token probability | Ask for a single-token label (YES/NO, A/B/C). Confidence = p(label) normalized over the label set. Used by Self-RAG, Fanconi, KnowNo, Kadavath. | 1 forward pass, 1 output token | Large pretrained models are calibrated in lettered MC format; post-trained ones need temperature (T=2.5 in Kadavath). Label probability had better AUC than verbalized for Llama-2-70B-chat (0.707 vs 0.648 on SciQ). | Logprobs. Ollama has had them since v0.12.11, 12 Nov 2025; `top_logprobs` capped at 20 per an issue opened 22 Sep 2026. | **Default for S1** |
| 2 | Post-hoc calibration | Temperature, Platt, or Bayesian logistic regression per decision type, on 100–400 labelled cases (Fanconi 100; KnowNo 400). ATS for per-token temperatures. | ~0 | Fixes ECE, but not ranking (AUROC) | Labelled calibration set | **Required** |
| 3 | Bias correction | Content-free or batch calibration, PriDe, and swapping the order then averaging | 1 extra call per template, or 2× for swaps | Up to +30.0 accuracy points (Zhao); swap-and-average fixes judge position bias | None | **Required** for choice and pairwise decisions |
| 8 | kNN over past decisions | Nearest-neighbour outcomes from a decision log (SKR, Self-Routing RAG policy datastore, RouteLLM similarity-weighted ranking, SOFAI experience counts) | Embedding lookup in pgvector | Self-Routing RAG: 26–40% fewer retrievals with accuracy gains | bge-m3 plus a decision log | **Default companion to #1** |

**Techniques to use selectively (second opinions, higher stakes, or specific decisions)**

| # | Technique | How it works | Extra cost | Evidence | Needs | Verdict |
|---|---|---|---|---|---|---|
| 4 | Verbalized confidence (0–100 or top-k) | Ask for a number or ranked guesses (Lin, Tian, Xiong, Yoon, RLCR) | A few tokens | Overconfident; weaker for small and open models; better with reasoning | None | Use for S2 second opinions; A/B test for S1 |
| 5 | Self-verification or P(True) | Ask "is this answer correct?", optionally k times (Kadavath, AutoMix) | +1 to k calls | Noisy; needs a meta-calibrator; present the answer as third-party to avoid ownership bias | None | Use for D6, behind a calibrator |
| 6 | Sampling agreement or semantic entropy | k samples, then vote, agreement, or entropy over meaning clusters (MoT, ABC, Kuhn and Farquhar, Lex-Similarity) | k× calls (3–10) | Semantic entropy AUROC 0.790 vs 0.691 for naive entropy; MoT reached GPT-4 quality at 40% of its cost | None (discrete variant) | Use at S2 or on high-stakes S1 decisions |
| 11 | Conformal wrappers | Calibrated prediction sets, or auto-accept with a controlled false-accept rate (KnowNo, Conformal Alignment, Mohri) | ~0 at inference | Coverage guarantees; KnowNo needs up to 24% less human help than a naive set | Calibration set of about 400 that resembles live data | Use for D7 and for auto-accept |
| 12 | Online threshold learning | Update thresholds from feedback (Online Cascade Learning, Fanconi, CascadeDebate, Cache & Distil, GPT-5 router) | ~0 | CascadeDebate: +20.98–52.33% relative over fixed thresholds; Online Cascade Learning: up to 90% cost cut | A feedback stream | Use: Herald approvals and overrides become labels |

**Techniques for later (need training data or runtime support)**

| # | Technique | How it works | Extra cost | Evidence | Needs | Verdict |
|---|---|---|---|---|---|---|
| 7 | Small specialized classifier or evaluator | A dedicated model scores the input or answer (FrugalGPT DistilBERT, Hybrid LLM DeBERTa, CRAG T5-large, MiniCheck-FT5, RouteLLM, Arch-Router 1.5B) | Milliseconds | CRAG evaluator 84.3% vs ChatGPT ≤64.7%; MiniCheck GPT-4-level at 400× lower cost; Hybrid LLM router 0.036 s | Training data (S2 labels) | After bootstrapping |
| 9 | Fine-tuned confidence | Confidence tokens (Self-REF), a deferral-tuned loss (Gatekeeper), or calibration rewards (RLCR) | LoRA or RL training | Self-REF: routing 39% of queries matches a 70B model | A training pipeline | Later |
| 10 | Hidden-state probes | Small probes on activations (Azaria, CCS, SEPs, Probing-RAG, UAR, SeaKR, Orgad) | Near zero at inference | Probing-RAG +6.6 points over no retrieval while skipping 57% of retrievals; UAR 85% retrieval-timing accuracy | Access to activations; per-task training | Later, and only if the runtime allows |

**Runtime note** (facts verified; the rest is slice C's area):

- **Logprobs exist but are top-k only.** Ollama added `logprobs` and `top_logprobs` to its native and OpenAI-compatible APIs in v0.12.11 (released 12 Nov 2025). GitHub issue #18579 (opened 22 Sep 2026) says you only get logprobs for tokens in the top-k, and `top_logprobs` is capped at 20. PR #18580 proposes a `logprob_tokens` field to request specific tokens. **Implication:** keep label sets tiny and single-token so every label falls inside the top-k.
- **Hidden states and attention weren't checked.** Whether Ollama exposes them (needed by DRAGIN, UAR, SeaKR and probes) is not verified here.

## Synthesis B: Escalation and abstention patterns

The patterns fall into four groups:

- **What triggers escalation:** 1–2 and 8.
- **How the decision is structured:** 3–7.
- **How thresholds improve over time:** 9–11.
- **Security:** 12.

1. **Rule triggers first (SwiftSage).** Always escalate on:
   - invalid output or schema failure;
   - a "critical" action class;
   - repeated lack of progress;
   - a tool exception or surprising observation.

   Deterministic, and it matches Omnitrix's rules.
2. **A single threshold on calibrated confidence.** FrugalGPT's τ_i per stage; Self-RAG's retrieval threshold (default 0.2); SeaKR's δ.
3. **Three bands: accept, reject, escalate.** CRAG's upper and lower thresholds; SOFAI's MC1 then MC2; Fanconi's accept, then large model, then human. **Suggested for each Omnitrix decision:**
   - calibrated p ≥ τ_hi: auto-accept;
   - p ≤ τ_lo: auto-reject;
   - in between: send to S2 (thinking plus verbalized confidence);
   - S2 still uncertain, or S2 disagrees with S1: send to H.
4. **Conformal set-valued decisions (KnowNo).** Act on a singleton set; otherwise ask H to pick from the set. Coverage is at least 1−ε, provided the calibration data resembles live data (exchangeability).
5. **Auto-accept with false-discovery-rate control (Conformal Alignment).** Accept only above a data-dependent threshold that caps false accepts at α.
6. **Decision-theoretic escalation.** AutoMix's POMDP; SOFAI MC2's gain over cost; Bouchard 2026; Zellinger & Thomson 2025. Escalate when expected quality gain × stakes exceeds the cost. For Omnitrix, cost means M5 latency, holding the 14B model in memory, and the user's attention.
7. **Signed rescue (2026).** Escalate where S2 is predicted to change *and fix* the answer. Skip categories where S2 is historically no better than S1.
8. **Disagreement triggers.** Ensemble disagreement (ABC); inconsistent samples (MoT); verdicts that flip when order is swapped (Wang et al.); S1 disagreeing with the kNN-over-history prediction.
9. **Online-learned thresholds.** Online Cascade Learning, Fanconi, CascadeDebate, Cache & Distil. Log the outcome of every escalation.
10. **Route before generating vs cascade after.**
    - Route first: Hybrid LLM, RouteLLM, Arch-Router.
    - Cascade: FrugalGPT, AutoMix, MoT.
    - Combined: cascade routing (Dekoninck).

    Bouchard and Mahmood (2026) favour routing first when the cheap model's generation cost isn't trivial. For Omnitrix, cascade on label-sized decisions and route first for long generations.
11. **Human deferral as a learned policy.** Mozannar & Sontag; CoAnnotating. Defer only where the human changes outcomes, and put a daily budget on watch prompts, with low-stakes items batched into a digest.
12. **Protect the escalation channel.** Forced Deferral shows confidence can be manipulated, and ownership bias inflates self-checks. So:
    - S1 judgements about untrusted content may **only tighten, never loosen**, Guardian's gates;
    - cap escalations per source.

## Synthesis C: Decision-type precedent map

**D1. Is this email noise?**
- **Precedents:**
  - Online Cascade Learning: a logistic regression → BERT → LLM cascade over a stream.
  - Cache & Distil: neural caching with margin sampling.
  - Wang et al. 2021 (GPT-3 labels) and Gilardi et al. 2023 (LLM vs crowd).
  - CoAnnotating.
- **What they used:** Classifier probabilities, top-2 margin, and LLM labels as training data.
- **Suggested S1 design:**
  1. Code rules first: allowlists, OTP and receipt patterns, calendar invites.
  2. A kNN on bge-m3 over past triage decisions.
  3. Qwen3-1.7B/4B P(YES/NO), calibrated.
  4. Three bands; S2 handles the middle band.
  5. User overrides are logged as labels, with Cache & Distil-style retraining.

**D2. Is this mention the same entity as an existing node?**
- **Precedents:**
  - Peeters et al. 2025; Narayan et al. 2022; Steiner et al. 2024/25.
  - PriDe and position-bias work.
  - Distilling System 2 into System 1 (BSM judge).
- **What they used:** Pairwise yes/no. Large prompt sensitivity for open models.
- **Suggested S1 design:**
  1. Blocking in code, then a bge-m3 candidate list.
  2. S1 pairwise YES/NO in both orders, with calibrated p.
  3. Low margin or order disagreement: S2.
  4. Never auto-merge below τ_hi. High-value nodes need human confirmation.

**D3. Does this new fact contradict a stored decision?**
- **Precedents:**
  - SummaC (NLI).
  - Self-RAG IsSup "no support".
  - MiniCheck.
  - The knowledge-conflicts survey.
  - Semantic entropy's bidirectional entailment.
- **What they used:** Three-way NLI labels aggregated over sentence pairs.
- **Suggested S1 design:**
  1. Librarian or S2 extracts claims.
  2. Retrieve candidate decisions.
  3. S1 gives an NLI three-way label.
  4. A confident "contradicts" goes to Historian (S2), then to H if S2 confirms.

**D4. Does this query need retrieval?**
- **Precedents:**
  - Mallen 2023 (popularity); SKR (kNN); FLARE; Self-RAG Retrieve; Adaptive-RAG (three strategies); UAR (four criteria); SeaKR; Probing-RAG.
  - Moskvoretskii 2025 (simple entropy is enough).
  - Self-Routing RAG 2025; Sah et al. 2026.
- **What they used:** Entity popularity, token entropy, a classifier on the query, kNN, verbalized confidence.
- **Suggested S1 design:**
  1. Code first: an entity in the graph means retrieve; time words or an explicit ask mean retrieve.
  2. UAR-style criteria in an S1 prompt.
  3. Adaptive-RAG-style choice of strategy (none, single lookup, multi-hop graph walk).
  4. Token entropy on a short draft answer as a backstop.

**D5. Is this retrieved passage relevant?**
- **Precedents:**
  - Self-RAG IsRel.
  - The CRAG evaluator (three bands).
  - Thomas et al. 2024 (Bing).
  - The Sufficient Context autorater; Gilardi.
- **What they used:** Relevant/irrelevant token probability; a score in [−1, 1] with two thresholds.
- **Suggested S1 design:**
  1. bge-m3 or reranker scores in code.
  2. S1 IsRel probability.
  3. Three bands. "Insufficient" sends Researcher to widen the local search.

**D6. Is this answer supported by its sources?**
- **Precedents:**
  - Self-RAG IsSup; MiniCheck.
  - Sufficient Context (sufficiency plus P(True), combined by logistic regression).
  - AutoMix self-verification.
  - Mohri and Hashimoto (conformal back-off); semantic entropy.
- **What they used:** Support labels (full, partial, none); a logistic-regression combiner; calibrated back-off.
- **Suggested S1 design:**
  1. S1 checks each claim: supported, partially supported, or unsupported.
  2. A logistic regression over sufficiency, P(True) and agreement.
  3. Remove or weaken unsupported claims before anything reaches the watch.
  4. Semantic entropy is used only on escalated answers.

**D7. Does this action need human approval?**
- **Precedents:**
  - KnowNo (conformal ask-for-help); Introspective Planning.
  - Fanconi (human tier); Mozannar & Sontag.
  - CascadeDebate (human fallback); Know Your Limits.
- **What they used:** Conformal set size; posterior uncertainty; learned deferral.
- **Suggested S1 design:**
  1. A code policy sets the floor: money and external communications always need approval.
  2. S1 may only *raise* the requirement (ambiguous recipient, unusual amount or tone).
  3. The Operator proposes the action as options. If the conformal set has more than one option, ask H with those options as buttons.

**D8. (meta) Does this need System 2? Which agent or model?**
- **Precedents:**
  - The GPT-5 router; Arch-Router; RouteLLM; Hybrid LLM.
  - Adaptive-RAG; the SOFAI metacognition module; SwiftSage triggers; Thinkless and AdaptThink.
- **What they used:** A router classifier or policy descriptions; learning from user switches and overrides.
- **Suggested S1 design:**
  1. Code rules first.
  2. An Arch-Router-style natural-language policy prompt on S1.
  3. Experience counters per decision type.
  4. User overrides logged as router training data, as GPT-5 does.

## Synthesis D: Pitfalls

**Calibration**
1. **Post-training miscalibration.** Instruction tuning, RLHF and RL reduce calibration. Sources: GPT-4 report, Kadavath (T=2.5 fix), Tian, Zhu, Leng, Nakkiran, Hallucination Tax, RLCR. Calibrate per decision, and recalibrate after every model swap (for example, hybrid Qwen3 to 2507 Instruct).
2. **Calibration (ECE) is not discrimination (AUROC).** Scaling fixes ECE but not ranking. For Llama-2-70B-chat, verbalized confidence improved ECE but *lowered* AUC (SciQ 0.648 vs 0.707). Routing depends on AUROC or area under the risk–coverage curve, so track those per decision.
3. **Small-model verbalized overconfidence.** Calibration scales with model size (Xiong).
4. **Probes and P(IK) don't transfer across tasks.** Kadavath AUROC 0.864 → 0.606; Orgad. Calibrate each decision separately.
5. **"Thinking" and calibration are contested.** Yoon (better verbalized calibration) vs Nakkiran (chain-of-thought breaks semantic calibration). Measure it on Omnitrix's own decisions.

**Prompt and format biases**
6. **Label-token and selection bias** (PriDe, Zhao, Batch Calibration), and **surface-form competition** (Holtzman).
7. **Position and order bias** in pairwise judging. MT-Bench position consistency ranges from 23.8% to 65.0%. Llama-2-70B-chat as a System-1 judge was 80.9% inconsistent on MT-bench.
8. **Prompt-format sensitivity.** Up to 76 points (Sclar). A standard deviation of up to 18.54 F1 across prompts for open matchers (Peeters). Even paraphrases matter (Thomas). Freeze templates, version them, and test 3–5 paraphrases before shipping.
9. **Ownership bias.** Self-checks are overconfident (Sanz-Guerrero). Present the text to be verified as someone else's.
10. **Noisy self-verification** on reasoning tasks (AutoMix). Use it only as one input to a calibrated combiner.

**Model and mode**
11. **Hybrid-thinking leakage in `/no_think`** (Path-Lock Expert), and Qwen's July 2025 switch to separate checkpoints. Cap tokens and grammar-constrain S1 outputs.

**Retrieval**
12. **Retrieval can hurt, and refusals can misfire.**
    - Retrieval broke about 10% of otherwise-correct answers (Mallen).
    - Retrieval-augmented models over-refuse when the documents are irrelevant (Zhou, AAAI 2026).
    - Small models hallucinate or abstain even with sufficient context (Joren).

**System level**
13. **The cascade's built-in cost** (Bouchard; Mahmood). For hard queries, S1 followed by S2 costs more than S2 alone. Route up front on latency-critical generative paths.
14. **Confidence is an attack surface** (Forced Deferral), and prompt injection in untrusted email can steer S1. Coordinate with the security slice.
15. **Cold start and drift.** Thresholds from public benchmarks won't transfer to one businessman's inbox. Online Cascade Learning and Cache & Distil show online adaptation works; SOFAI-style experience counters stop S1 from being trusted too early.
16. **Errors propagate into memory** (Xia 2026). Store confidence and provenance with every memory write, and allow retraction.
17. **Runtime constraint.** Only the top-k tokens get logprobs (cap 20 as of Sept 2026). Keep label sets tiny and single-token. Methods that need hidden states or attention depend on runtime support.

---

## Key takeaways for Omnitrix's design

**How S1 and S2 are arbitrated**

1. **The S1/S2 split is well supported, but the arbiter should be code, not a model.**
   - Precedents: SOFAI's metacognition, SwiftSage's rule triggers, and the GPT-5 router trained on feedback.
   - The arbiter combines three inputs: calibrated S1 scores, rule triggers, and per-decision experience counters.
   - This fits "ranking, scheduling and security checks are plain code".
2. **Default S1 recipe:**
   - single-token constrained labels, confidence from the normalized label probability;
   - Platt or Bayesian-logistic calibration per decision on 100–400 labelled cases;
   - label-bias correction (content-free or batch), and swapping the order then averaging on pairwise decisions;
   - AUROC and ECE logged per decision.
3. **Three bands on every decision.**
   - At or above τ_hi, auto-accept.
   - At or below τ_lo, auto-reject.
   - In between, send to S2 (thinking plus verbalized confidence).
   - If S2 is still uncertain, or S1 and S2 disagree, the case goes to the human through Herald.
   - Precedents: CRAG, Fanconi & van der Schaar, SOFAI.
4. **Keep S1 in non-thinking mode for classification.** Qwen3-4B IFEval is 81.2 non-thinking vs 81.9 thinking; thinking only pays off hugely on math and GPQA. Guard against `/no_think` leakage with token caps and grammar-constrained outputs, and consider the 2507 Instruct checkpoints (slice C).
5. **Escalate by expected *improvement*, not raw uncertainty.** Track per decision type whether S2 or the human actually changed the outcome, and stop escalating categories where they don't. Precedents: Signed Rescue Routing, AutoMix's POMDP, learning to defer.

**Specific decisions**

6. **Use conformal "ask for help" for Operator and Guardian (KnowNo).** Present actions as options, calibrate on about 400 logged cases, and if the set has more than one option, show those options on the watch. A code policy sets the floor. S1 can only raise the approval requirement.
7. **Separate "is the evidence sufficient?" from "is the model confident?"** Combine the two with a tiny logistic regression (Sufficient Context). This gives an honest "not enough in memory" state that is cheap, interpretable and easy to demo.
8. **Retrieval decisions: code first, then cheap uncertainty.** In a personal knowledge base most facts are long-tail, so retrieve by default when a query mentions a known entity (Mallen's logic, inverted). Simple entropy methods match complex adaptive-RAG pipelines (Moskvoretskii, ACL 2025), and a nearest-neighbour memory of past decisions helps further (SKR, Self-Routing RAG).
9. **Cite Self-RAG and CRAG as the core precedent in the pitch.** Three of the seven decisions (D4, D5, D6) are exactly Self-RAG's reflection tokens, labelled by a big model and distilled into a small critic. CRAG supplies the three-band evaluator. D2 maps to the entity-matching papers, D3 to NLI, D7 to KnowNo.

**Learning over time**

10. **Distil S2 into S1 continuously.** S2 labels the uncertain cases; S1 (a kNN, a small classifier or LoRA) learns from them; margin sampling chooses what to escalate. Judge-type decisions distil well (distilled BSM reached 72.4% agreement at 4 tokens), while multi-step reasoning doesn't (CoT on GSM8k). Precedents: Cache & Distil, Online Cascade Learning, Distilling System 2 into System 1.
11. **Budget the human's attention.** Route to the user only where their input changes outcomes (CoAnnotating, Mozannar & Sontag). Cap watch prompts per day and batch low-stakes questions into a digest.

**Safety, provenance and demo**

12. **Treat confidence as an attack surface.** Adversarial content can manipulate S1's confidence (Forced Deferral). Judgements derived from untrusted content can only tighten Guardian's gates, and escalations are rate-limited per source.
13. **Store confidence and provenance with every memory write.** The Auditor can then revisit low-confidence S1 accepts. Uncertainty compounds across 15 agents.
14. **Make the dual-process claim measurable in the demo.** Show a live cost–quality curve in the RouteLLM and RouterBench style:
    - the share of decisions S1 handled;
    - accuracy vs "S2 for everything" on a labelled slice;
    - median latency saved;
    - escalation reasons.

## Contested and open questions

1. **Does "thinking" help or hurt calibration?** Yoon et al. (NeurIPS 2025) say reasoning improves verbalized calibration. Nakkiran et al. (2025) say RL tuning and chain-of-thought break semantic calibration. RLCR (ICLR 2026) suggests it depends on the training reward. Test Qwen3-14B thinking vs non-thinking on Omnitrix's own decisions.
2. **Verbalized vs token-probability confidence at 1.7B–4B.** Tian et al. favour verbalized confidence for RLHF'd API models, but it lowered AUC on Llama-2-70B-chat, and Xiong et al. show small models are worse at verbalizing. The 2026 work (Guo et al.) trains explicit uncertainty signals. Nobody has measured this for Qwen3-4B.
3. **Cascade or route first?** Dekoninck et al. (ICML 2025) find cascade routing best. Bouchard (2026) and Mahmood (ICLR 2026) find static up-front routing usually wins once the cheap model's generation cost counts. For label-sized decisions the question may be moot, but measure it.
4. **Prompted small model, or fine-tuned?** Evidence that specialization matters:
   - Arch-Router: the untuned 1.5B base scored 34.37 turn-level; the tuned model 96.05.
   - CRAG: a fine-tuned T5 at 84.3% vs prompted ChatGPT at 64.7%.
   - Peeters: open models zero-shot sit well below GPT-4.

   Distilling System 2 into System 1 shows self-distillation works, but only at 70B. How far a *prompted* Qwen3-4B gets is unknown.
5. **Hidden-state probes vs black-box signals.** Probes are cheap and strong (Probing-RAG, UAR, SEPs) but generalize poorly across tasks (Orgad) and need runtime access to activations.
6. **Conformal guarantees on drifting personal data.** KnowNo-style guarantees assume calibration data resembles live data. One person's inbox changes over time; online or adaptive conformal methods weren't covered here.
7. **No benchmark for personal-memory decisions.** Adaptive-retrieval benchmarks use world knowledge (PopQA, HotpotQA), whereas a personal knowledge base is almost entirely long-tail. Omnitrix will need a small in-house evaluation set, which could also be a demo asset.
8. **Hybrid vs separate thinking checkpoints at 4B.** Qwen moved to separate checkpoints in July 2025, and Path-Lock Expert proposes an architectural fix. Which behaves better as S1 is untested at this size.
9. **The cost metrics don't match.** Router papers optimize API dollars or FLOPs. Omnitrix's real costs are latency, thermals and battery, memory residency within 24 GB, and the user's attention. No paper optimizes these together.

## Unverified

These were seen only in secondary summaries or search snippets, or couldn't be matched in primary text. None of them is relied on in the analysis above.

- **Qwen's X announcement text** saying they stopped hybrid thinking "to get the best quality". Seen in a search snippet only. The separate 2507 releases themselves are verified from the GitHub README (21–31 July 2025) and the Qwen3-4B-Instruct-2507 model card.
- **Hybrid LLM (Ding et al.) "22% fewer calls to GPT-3.5-turbo with about 1% quality drop".** Appeared in an LLM summary but not in the raw text. Only the abstract's "up to 40% fewer calls with no quality drop" is used.
- **Sufficient Context autorater accuracies** of 87.8% (FLAMe) and 82.6% (TRUE-NLI). From a summary, not matched verbatim. Only the 93% Gemini figure is used.
- **Cache & Distil per-policy online accuracies** (~0.757 MS, ~0.755 QBC, ~0.728 random, ~0.745 front-loading) and the student model's size. From a summary. Not used.
- **Online Cascade Learning per-dataset accuracy and cost figures.** From a summary. Only the abstract's "up to 90%" is used.
- **Gatekeeper's "7×/10× improvement" on ARC-e/ARC-c.** The metric was unclear. Not used.
- **Self-RAG 7B PopQA score (54.9) vs ChatGPT (29.3).** The first number wasn't matched in the raw table text, so only the abstract's qualitative claim is used.
- **GPT-4 Technical Report Fig. 8 ECE values.** Not in the text, so only the qualitative claim is used.
- **AutoMix author order.** Cited as arXiv v5 and NeurIPS 2024 give it: Aggarwal and Madaan as equal-contribution first authors. Earlier versions weren't checked.
- **Signed Rescue Routing (arXiv 2609.07786) results.** The v1 abstract has "TBD" placeholders, so only the idea is cited.
- **Whether Ollama exposes hidden states or attention weights.** Not checked; left to slice C. Only the logprobs facts (v0.12.11 release; issue #18579, top-k cap of 20) were verified, on GitHub.
