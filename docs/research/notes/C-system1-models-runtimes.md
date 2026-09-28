# Slice C: System-1 model zoo and runtime support on an Apple-Silicon Mac

Research notes for **Omnitrix** (MSRIT Hackathon, Track 1 "Sovereign AI"). Compiled 2026-09-25.

Tags used below:
- **[measured]**: run on the team's own Mac today.
- **[card]** / **[docs]** / **[repo]** / **[paper]**: checked against that primary source.
- **[secondary]**: news, blog or search-snippet source only.
- **[estimate]**: my own arithmetic, not a measurement.

Anything I could not verify is repeated in **Unverified** at the end.

---

## 0. The team's machine (read-only checks, 2026-09-25)

| Item | Value | How verified |
|---|---|---|
| Chip / GPU | Apple M5 Pro, **16-core GPU**, Metal 4. CPU: 5 performance + 10 efficiency cores | `system_profiler`, `sysctl` |
| Memory | 24 GB unified. Metal reports **~18.2 GB usable by the GPU** ("MTL0 … 18186 MiB") | `hw.memsize`, Ollama server log |
| OS | macOS 26.6.2 (25G83) | `sw_vers` |
| Ollama | **0.34.4**, the latest stable (released 2026-09-23). v0.40.0-rc0 is a pre-release dated 2026-09-25 | `ollama --version`, GitHub releases |
| Ollama config | `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=0` (auto, which the docs say means 3 per GPU), `KEEP_ALIVE=5m`, `CONTEXT_LENGTH=0` (auto; the llama-server slots show n_ctx 4096) | server log |
| Ollama's GGUF runner | Spawns **upstream llama.cpp `llama-server`** per model. Log lines: `using llama-server for model`, `prompt cache is enabled, size limit: 8192 MiB`, `context checkpoints enabled, max = 32, min spacing = 8192`, `n_slots = 1`, `Flash Attention enabled` | server log [measured] |
| Models installed | qwen3:14b (9.3 GB), qwen3:4b (2.5 GB), qwen3:1.7b (1.4 GB), bge-m3 (1.2 GB on disk, F16, 566.7M params), gemma3:12b, qwen3-coder:30b, devstral, society/* | `ollama list` |
| **qwen3:4b is the Thinking-2507 build** | Digest `359d7dd4bcda` = `qwen3:4b-thinking-2507-q4_K_M`. `ollama show` lists thinking levels as `true` only. With `think:false` it still starts writing reasoning ("First, …") in the content | ollama.com/library/qwen3/tags + [measured] |
| qwen3:1.7b | Hybrid-thinking Qwen3-1.7B (April 2025). Thinking levels `false, true`; `think:false` works | `ollama show` + [measured] |
| Python | The project's uv environment has only pydantic, httpx, psycopg and similar. **No torch or transformers.** System python is 3.9 | `pyproject.toml`, `.venv` |
| Not installed | llama.cpp binaries, MLX/mlx-lm, Homebrew | `which` |

---

## 1. Runtime primitives

### 1.1 Ollama (already installed; this is the least-setup path)

**Token logprobs.** Added in **v0.12.11 (2025-11-12)** for the native API. The release notes name classification and retrieval evaluation as intended uses. [GitHub release v0.12.11]

Exact fields [docs.ollama.com/api/generate; measured on 0.34.4]:
- **Request** (`/api/generate` and `/api/chat`): `"logprobs": true`, `"top_logprobs": k`.
  - **k must be between 0 and 20.** Asking for 25 returned `{"error":"top_logprobs must be between 0 and 20"}` [measured].
  - Issue #18590 (2026-09-22, now closed) asked to raise the cap to 100; the outcome is unknown. PR #18580 (`logprob_tokens`, returning logprobs for caller-named tokens) was closed unmerged on 2026-09-22.
- **Response** (top level for both endpoints):
  - `logprobs: [{token, logprob, bytes[], top_logprobs:[{token, logprob, bytes[]}]}]`
  - plus `prompt_eval_count`, **`prompt_eval_cached_count`**, `prompt_eval_duration`, `eval_count`, `eval_duration`, `load_duration`, `total_duration` (all durations in ns).
- **Logprobs are raw.** They come from the model's softmax, not the temperature-scaled sampler. With `temperature:0` we still saw graded values such as −0.45 and −1.01 [measured].

**OpenAI-compatible `/v1/chat/completions`.**
- The docs page (docs.ollama.com/api/openai-compatibility) still lists logprobs as unsupported, and issue #16117 was "closed as not planned" on 2026-05-12.
- **On 0.34.4 it does return OpenAI-shaped logprobs** [measured]:
  - request: `"logprobs": true, "top_logprobs": 3`
  - response: `choices[0].logprobs.content[i].{token, logprob, bytes, top_logprobs[]}`
- `"reasoning_effort": "none"` disabled thinking for qwen3:1.7b [measured].
- `/v1/completions` returned `logprobs: null` [measured].
- **Recommendation:** use the native API so behaviour does not depend on stale docs.

**Structured outputs.**
- `format` takes `"json"` or a JSON-schema object; available since v0.5.0 (blog dated 2024-12-06). A schema with an `enum` produced `{"label": "noise"}` [measured].
- v0.33.1 added structured outputs to the MLX runner. v0.34.4 made structured outputs on thinking models apply in a single pass [GitHub releases summary].
- **Caveat [measured]:** with `format` set, the logprobs you get back are still the *unconstrained* distribution. The forced `{"` token showed logprob −34.2 while the model actually preferred "The". To score labels, use a plain single-token answer and renormalise over your label set; do not read scores off a constrained JSON string.

**`think`.**
- Accepts a boolean or a level (`"low"`, `"medium"`, `"high"`, `"max"`) on `/api/generate` and `/api/chat` [docs]. The feature launched 2025-05-30 [Ollama blog "thinking"].
- It only helps for hybrid models. The Qwen3 2507 **Thinking** tags cannot be switched off (see §0).
- For System 1, use `qwen3:1.7b` / `qwen3:0.6b` / `qwen3:14b` (hybrid) with `think:false`, or `qwen3:4b-instruct` (Instruct-2507, no thinking at all; digest `0edcdef34593`, 2.5 GB, 256K context) [ollama.com/library/qwen3/tags].

**keep_alive and scheduling** [docs.ollama.com/faq]:
- `keep_alive` defaults to 5m. `0` unloads immediately; a negative value keeps the model loaded. `OLLAMA_KEEP_ALIVE` sets the global default.
- `OLLAMA_NUM_PARALLEL` defaults to 1. RAM grows with NUM_PARALLEL × CONTEXT_LENGTH.
- `OLLAMA_MAX_LOADED_MODELS` defaults to 3 × number of GPUs. **On this Mac that is 3 resident models.** qwen3:14b + two S1 LMs + bge-m3 is four models, so one gets evicted and pays a cold load (we measured 0.5–1 s for small models and 14 s for the first qwen3:4b load).
- `OLLAMA_MAX_QUEUE` defaults to 512. `OLLAMA_KV_CACHE_TYPE` is f16 by default; q8_0 halves KV memory and q4_0 quarters it. `OLLAMA_FLASH_ATTENTION` is on in the log.

**Prompt / KV-cache reuse** [measured; llama.cpp PR #16391]:
- Because 0.34.4 runs `llama-server` with the **host-RAM prompt cache** (PR #16391, merged 2025-10-09, default 8 GiB), the runner keeps several past prompts and restores the one with the longest matching prefix.
- **Three alternating decision-type instruction prefixes stayed cached even with NUM_PARALLEL=1.** Each call after the first had 340–355 of ~400 tokens cached (details in §2.1).
- This works out of the box for pure-transformer models.
- **Hybrid/recurrent models behave differently** (Qwen3.5 small, LFM2/2.5, Granite-4.0-H). llama.cpp can only restore them at "context checkpoints". Ollama's log shows `min spacing = 8192`, so short classification prompts probably never get a checkpoint. Open llama.cpp issues report checkpoints being invalidated on hybrid models (#24055 open since 2026-06-03, #22384, #25913; discussion #19264). **Treat prefix caching of hybrid models as broken until tested locally.**

**Embeddings.**
- `/api/embed` takes `model`, `input` (string or list), `truncate`, `dimensions`, `keep_alive` [docs].
- bge-m3: a ~254-token text took **~21 ms** warm [measured]. A batch of 8 took ~155 ms, so no batching speed-up.
- Also in the library: `qwen3-embedding:0.6b|4b|8b` (639 MB / 2.5 GB / 4.7 GB) and `embeddinggemma:300m` (622 MB, 2K context, needs Ollama ≥0.11.10).

**Rerankers and classification heads.**
- Ollama has **no `/api/rerank`** and cannot return classifier-head scores. Issue #16076 (2026-05-10, open) proposes `/api/rerank` and pooling for the MLX engine. Community uploads such as `dengcao/Qwen3-Reranker-0.6B` exist but have no rerank API behind them.
- **Workaround [measured with a generic Qwen3]:** Qwen3-Reranker scores relevance as P("yes") vs P("no"), so it can be emulated:
  - call `/api/generate` with `"raw": true` and the reranker's own template, plus `num_predict:1, logprobs:true, top_logprobs:20`;
  - read `yes` and `no` from `top_logprobs`, then compute `p = e^yes / (e^yes + e^no)`.
  - With qwen3:1.7b standing in: p ≈ 1.0 for a relevant bill passage and ≈ 5e-9 for an irrelevant one. That saturation is typical of a generic LM; a trained reranker gives graded scores.
  - The real Qwen3-Reranker-0.6B GGUF (`hf.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF`, 639 MB) was *not* pulled or tested.

**Running any GGUF from Hugging Face:** `ollama run hf.co/{user}/{repo}[:quant]`. Q4_K_M is the default; the chat template is auto-picked from GGUF metadata [HF docs]. This covers small models that are not in the official library (LFM2.5-1.2B/350M, SmolLM3, Qwen3Guard, …).

**MLX engine inside Ollama:**
- Preview **2026-03-30** (Ollama 0.19, Qwen3.5-35B-A3B NVFP4; blog asked for >32 GB RAM).
- v0.21.1 (April) added "MLX runner adds logprobs support for compatible models".
- v0.33.1 added structured outputs to MLX. The MLX performance blog (2026-06-11) describes "snapshots" for cache reuse.
- **v0.40.0-rc0 (2026-09-25) makes the MLX runner the default on Apple Silicon for supported architectures.** It gives no details about opting out.
- **Pin 0.34.4 for the hackathon** and re-test logprobs and caching before upgrading.

**Minimal S1 call (verified shape):**
```json
POST /api/chat
{"model":"qwen3:1.7b","think":false,"stream":false,"keep_alive":-1,
 "messages":[{"role":"system","content":"<stable instruction prefix per decision type>"},
             {"role":"user","content":"<item>"}],
 "logprobs":true,"top_logprobs":20,
 "options":{"temperature":0,"num_predict":1}}
```
Scoring recipe:
- Take `logprobs[0].top_logprobs`.
- Keep the entries whose token is a label's first token (make those first tokens distinct).
- Apply a softmax over the kept entries, then apply per-task temperature or Platt calibration.
- If a label is missing from the top 20, treat its probability as ≤ the smallest listed probability.
- Tokenisation matters: "SIGNAL" came out as first token "S" and "NOISE" as "NO" [measured]. Prefer labels like `yes/no` or `A/B/C`.

### 1.2 llama.cpp `llama-server` (more knobs; needs a binary download since there is no brew)

From tools/server/README.md [docs]:
- **`n_probs`** returns the top-N token probabilities per generated token (`completion_probabilities[].top_logprobs`). `post_sampling_probs: true` switches to probabilities after sampling (`top_probs`, `prob`).
- **`grammar`** (GBNF) and **`json_schema`** (also as files).
- **`logit_bias`**: `[[token_id, bias]]`, `{"token": bias}` or string form. You can use it to restrict output to label tokens.
- **Reranking:** `/reranking` (aliases `/rerank`, `/v1/rerank`) with `--reranking` (or `--embedding --pooling rank`). Takes `query` + `documents`. Pooling can be `none|mean|cls|last|rank`.
- **Embeddings:** `/embedding` (all poolings, unnormalised) and `/v1/embeddings` (normalised; needs pooling ≠ none).
- **Caching:** `cache_prompt` is on by default. `cache_reuse` sets a minimum chunk size for KV shifting (0 = off). `--parallel N` slots, the `/slots` endpoint, and save/restore via `--slot-save-path`. The host-RAM prompt cache is `--cache-ram` (8192 MiB default, PR #16391).
- **Chat endpoint:** `/v1/chat/completions` supports `response_format` (json_object or schema) and `chat_template_kwargs` (e.g. `{"enable_thinking": false}`). `--jinja` is on by default. `--reasoning-budget` and `--reasoning-format` are available.
- On logprobs in the chat endpoint, a downstream project reports that llama.cpp honours boolean `logprobs` + `top_logprobs` and legacy `n_probs`, but not integer `logprobs=N` [secondary; ogx PR #6618].
- **Metal performance:** see §2.2. Ollama already embeds llama-server, so installing llama.cpp separately mainly buys `logit_bias`, rerank pooling and GBNF.

### 1.3 MLX / mlx-lm (best for exact label scoring and LoRA; needs `uv add mlx-lm`)

Versions: mlx 0.32.2 (2026-08-25; macOS ≥14, Python 3.10–3.14). mlx-lm 0.31.3 is the latest on PyPI (2026-04-22) [PyPI].

**Logits.**
- `generate_step(...)` yields `(token, logprobs)` where **logprobs is the full-vocabulary vector**. `GenerationResponse` carries `logprobs`, `prompt_tps`, `generation_tps` and `peak_memory` [repo generate.py].
- Calling `model(tokens)` directly gives logits, so P(label) is exact for any label set with no top-k cap. This is the cleanest route for calibration research.
- Prompt cache: `make_prompt_cache(model)`; passing `prompt_cache=` **updates it in place**, so copy it before reusing a shared prefix [repo].

**Server** (`mlx_lm.server`, port 8080) [SERVER.md]:
- `/v1/chat/completions` with `logprobs` as an **integer from 1 to 10**. Response carries `token_logprobs`, `tokens`, `top_logprobs`.
- Also supports `logit_bias` (token-id map), `repetition_penalty`, `presence_penalty`, `frequency_penalty`, `top_k`, `min_p`.
- No `response_format` is documented. The docs warn it is "not recommended for production".

**LoRA:** see §5.

**M5 Neural Accelerators** [Apple ML Research, 2025-11-19]:
- MLX on M5 vs M4, `mlx_lm.generate`, 4096-token prompt: **time to first token 3.33–4.06× faster** and generation 1.19–1.27× faster.
- Qwen3-1.7B BF16: TTFT 3.57×, generation 1.27×, 4.40 GB.
- Needs **macOS 26.2+**; the team has 26.6.2. The article gives ratios only, no absolute numbers.

### 1.4 SGLang `select` and vLLM `structured_outputs` (on macOS in 2026)

**SGLang `select` / `gen(choices=…)`** [docs.sglang.io choices_methods]:
- `token_length_normalized` (default): highest mean token logprob per option.
- `greedy_token_selection`: highest logprob of the first token; overlapping options are extended by their mean.
- `unconditional_likelihood_normalized`: one extra call to normalise by unconditional likelihood.
- Only `RuntimeEndpoint` honours `choices_method`.
- **macOS:** an MLX backend exists (`SGLANG_USE_MLX=1`). Requires macOS ≥14, Python 3.12, PyTorch 2.13.x, MLX ≥0.32.0 [SGLang Apple-Metal doc mirror]. A secondary source says it is greedy-only with no cross-request cache and no continuous batching. **Not worth it for the hackathon;** replicate `select` yourself with Ollama or MLX logprobs.

**vLLM** [docs.vllm.ai structured_outputs]:
- `extra_body={"structured_outputs": {"choice": [...]}}`; also `regex`, `json`, `grammar`.
- The old `guided_choice` / `guided_json` / … were **removed in v0.12.0**.
- Backends: xgrammar, guidance (llguidance), outlines, lm-format-enforcer. Default is `auto`.

**vllm-metal** (vllm-project, community plugin) [repo]:
- MLX-based. v0.2.0 (2026-04) switched to a paged varlen Metal kernel. 2026-08 update: M5 NAX prefill for MHA/GQA/MQA.
- Install via brew tap; needs macOS 15+.
- Structured-output and logprob coverage on Metal is **not documented**.
- SiliconBench (arXiv 2609.19169, 2026-09-12) found vllm-metal more than doubled throughput from concurrency 1 to 16 on a 0.6B model. Only 3 of 9 Apple Silicon stacks passed all completion, fidelity and coverage checks.

### 1.5 Constrained-decoding libraries

| Library | What it is | Integrations | License / version |
|---|---|---|---|
| **Outlines** (dottxt-ai) | Typed outputs: `Literal` choices, regex, JSON schema/Pydantic, context-free grammar | transformers, llama.cpp, vLLM, **Ollama** (JSON-schema only through Ollama), SGLang, OpenAI | Apache-2.0 [repo] |
| **XGrammar** (mlc-ai) | Grammar engine that builds token masks; default in vLLM, SGLang, TensorRT-LLM, MLC | `pip install "xgrammar[metal]"` for MPS | Apache-2.0; paper arXiv 2411.15100; XGrammar-2 (May 2026) [repo] |
| **llguidance** (guidance-ai) | Rust constraint engine, ~50 µs CPU per token (128k vocab); Lark-style CFG, JSON schema, regex | llama.cpp (`-DLLAMA_LLGUIDANCE=ON`), vLLM ≥0.8.2, SGLang ≥0.4.4, OpenAI structured outputs, Chromium | MIT; v1.0.0 (2025-06-23) [repo] |

For System 1 you rarely need a grammar. A single-token answer scored by logprobs is simpler and gives confidence for free. Keep grammars (Ollama `format`) for System 2 extraction.

### 1.6 Apple Foundation Models SDK for Python (optional, zero model download)

- `pip install apple-fm-sdk`. Needs macOS ≥26, Python ≥3.10, Xcode 26 and **Apple Intelligence enabled**.
- Gives access to the on-device system model with **guided generation** (`@generable`) and streaming. Apache-2.0, © 2026 [repo apple/python-apple-fm-sdk].
- **No logprobs or token probabilities are documented**, so it can make choices but gives no confidence to drive escalation.
- The `fm` CLI arrives with macOS 27 (WWDC26) [secondary].

---

## 2. Performance

### 2.1 Measured on this Mac (Ollama 0.34.4, Q4_K_M, `think:false`, `num_predict:1`, ~400-token prompt: ~340-token shared instruction + ~60-token item)

| Model | Cold load | Uncached prefill (~400 tok) | Prefill with 340-token prefix cached | Wall time per decision (cached) |
|---|---|---|---|---|
| qwen3:1.7b | 0.54–0.9 s | **96–117 ms** (~4,100 tok/s) | **29–31 ms** | **33–40 ms** |
| qwen3:4b (Thinking-2507; same weights shape as Instruct-2507) | 14.1 s (first load from disk) | **245–247 ms** (~1,600 tok/s) | **63–103 ms** | 69–108 ms |
| bge-m3 embed (254 tok) | 1.04 s | — | — | **~21 ms**; batch of 8 ≈ 155 ms |

- **Alternating decision prefixes** (qwen3:1.7b, sequence A, B, C, A, B, C, A): after the first round, each call had 340–355 tokens cached, ~29 ms prefill and 35–40 ms wall. The host-RAM prompt cache swaps prefixes in [measured].
- **Decode** time for one token rounds to 0 ms in Ollama's counters. Latency is almost entirely prefill.
- **Quality sanity check (n=4, not a benchmark):** qwen3:1.7b zero-shot NOISE/SIGNAL.
  - Personal email and bank statement: correct.
  - Shoe-sale promo: P(SIGNAL) 0.64 vs P(NOISE) 0.36, wrong.
  - Tech newsletter: P(SIGNAL) ≈ 1.0, confidently wrong.
  - Takeaway: raw small-LM logprobs are **overconfident and must be calibrated** or backed by fine-tuning or few-shot examples [measured].

### 2.2 Published numbers

**llama.cpp Apple Silicon thread** (discussion #4167; Llama-2-7B; PP512 / TG128 in tok/s; latest update 2026-08-25) [repo discussion]:

| Chip | GPU cores | Bandwidth | Q4_0 PP512 | Q4_0 TG128 |
|---|---|---|---|---|
| M5 Pro | 20 | 307 GB/s | 1620.6 | 66.3 |
| M4 Pro | 20 | 273 GB/s | 439.8 | 50.7 |
| M5 Max | 40 | 614 GB/s | 3220.0 | 119.9 |

So an M5 Pro prefills ~3.7× faster than an M4 Pro, the Neural Accelerator effect. **The team's M5 Pro has 16 GPU cores**, so expect roughly 80% of the 20-core prefill [estimate].

Other published figures:
- **Ollama MLX preview** (2026-03-30): Qwen3.5-35B-A3B on M5-class Macs, prefill 1,810 tok/s and decode 112 tok/s (0.19 vs 1,154 / 58 in 0.18). The blog does not break down which chip [Ollama blog].
- **BaseRT** (arXiv 2607.19438, 2026-07): hand-written Metal 4 tensor kernels on M5 Pro, up to 6.4× faster prefill than llama.cpp and 3.9× faster than MLX (up to 1.75× / 1.33× on decode). A research runtime, not something to adopt here.
- **Decode on small models:** apple-silicon-llm-bench (M4 Max, updated 2026-07-13) reports MLX-Swift beating llama.cpp on every cell, by 1.4–1.8× (Qwen3-0.6B Q4 ≈ 556 tok/s on MLX-Swift). Irrelevant for single-token classification.
- **LM Studio bug #2040:** on M5 Macs, some llama.cpp builds fail the Metal tensor-API check, leaving the Neural Accelerators unused and losing 2–3× prefill. Env knobs are `GGML_METAL_TENSOR_ENABLE` / `GGML_METAL_TENSOR_DISABLE` [secondary]. The Ollama 0.34.4 log does not say whether the tensor path is active; our measured ~4.1k tok/s prefill for a 1.7B model looks healthy.

### 2.3 Latency model for "one token over a ~300-token input"

- **Latency ≈ load (once) + prefill of the uncached tokens + ~1 decode step + HTTP overhead (~2–5 ms).**
- With a stable instruction prefix and only a 50–100-token variable tail on this Mac:
  - **qwen3:0.6b** ≈ 15–25 ms [estimate]
  - **qwen3:1.7b** ≈ 30–40 ms [measured]
  - **4B** ≈ 65–105 ms [measured]
  - **qwen3:14b** ≈ 250–400 ms cached and ≈ 0.8–1 s uncached [estimate, scaling from the 4B measurement]
- Without caching, costs roughly triple: ~100 ms for 1.7B and ~250 ms for 4B at 400 tokens.
- **Keep S1 models resident** (`keep_alive:-1`) and raise `OLLAMA_MAX_LOADED_MODELS`. Cold loads (0.5–14 s) are the real tail-latency risk.

---

## 3. Small generative LMs usable as classifiers

| Model (date) | Params / context | License | In Ollama library? | Notes relevant to System 1 |
|---|---|---|---|---|
| **Qwen3-0.6B** (Qwen3 family, 2025-04-29) | 0.6B (0.44B non-embedding), 28 layers, 32K | Apache-2.0 | `qwen3:0.6b` 523 MB | Hybrid thinking; `enable_thinking=False` or `/no_think`; non-thinking sampling T0.7/p0.8/k20 [card; QwenLM/Qwen3 news] |
| **Qwen3-1.7B** (2025-04-29) | 1.7B (Ollama shows 2.0B), 32K native (Ollama: 40,960) | Apache-2.0 | `qwen3:1.7b` 1.4 GB (installed) | Measured 33–40 ms per decision with a cached prefix; overconfident zero-shot [measured] |
| **Qwen3-4B-Instruct-2507** (2025-08-06) | 4.0B (3.6B non-embedding), 36 layers, 262,144 | Apache-2.0 | `qwen3:4b-instruct` 2.5 GB | **Non-thinking only.** MMLU-Pro 69.6, IFEval 83.4 [card]. The right "strong S1" |
| Qwen3-4B-Thinking-2507 (2025-08-06) | same | Apache-2.0 | `qwen3:4b` (installed) | Thinking-only, so unsuitable for S1 |
| **Qwen3.5-0.8B / 2B / 4B / 9B** (small series 2026-03-02) | 262K; hybrid **Gated DeltaNet** + gated attention (2B: 24 layers, 6×[3×GDN+FFN → 1×GatedAttn+FFN]); multimodal; 201 languages | Apache-2.0 | `qwen3.5:0.8b` 1.0 GB, `2b` 2.7 GB, `4b` 3.4 GB, `9b` 6.6 GB, plus `-mlx` variants | Thinking **off by default for 0.8B/2B**, on for 4B (`enable_thinking`). Small sizes "more prone to thinking loops" when thinking. Non-thinking card scores: 0.8B MMLU-Pro 29.7 / IFEval 52.1; 2B 55.3 / 61.2. **Hybrid, so prompt-cache reuse is doubtful in llama.cpp** (§1.1). Issue #18590 author used Qwen3.5-4B with top_logprobs [cards; QwenLM/Qwen3.8 README] |
| Qwen3.6 / Qwen3.8 (2026-04 / 2026-08) | 27B, 35B-A3B, 3.8-27B, 2.4T-A95B | Apache-2.0 | — | **No new sizes under 5B**; the Qwen3.5 small series is the newest small Qwen [QwenLM/Qwen3.8 README] |
| **Gemma 3 270M** (2025-08-14) | 270M (170M embedding + 100M transformer), 256k vocab, 32K, text-only | Gemma Terms of Use | `gemma3:270m` 292 MB | Google positions it explicitly as a **fine-tune base for classification, entity extraction, query routing, compliance checks**. QAT INT4 checkpoints; IFEval 51.2 [Google dev blog; card] |
| **Gemma 3 1B** (Gemma 3, Mar 2025) | 1B, 32K, text-only | Gemma ToU | `gemma3:1b` 815 MB (+`1b-it-qat`) | Plain transformer, so caching works |
| Gemma 3n E2B / E4B (full release 2025-06-26) | raw 5B/8B, effective 2B/4B; 32K | Gemma ToU | `gemma3n:e2b` 5.6 GB, `e4b` 7.5 GB (text-only in Ollama) | Too heavy for System 1 on this box |
| **Gemma 4** E2B / E4B / 26B-A4B / 31B (+12B later) (2026-04-02) | E2B 2.3B effective (5.1B with Per-Layer Embeddings), 128K; `<\|think\|>` toggle | **Apache-2.0** (a change from Gemma ToU) | `gemma4:e2b` 7.2 GB, `e4b` 9.6 GB, `12b` 7.6 GB, plus `-mlx` | Very large on disk for System 1 [Google blog; card; Ollama] |
| **SmolLM3-3B** (2025-07-08) | 3B, 64K native (128K YaRN) | Apache-2.0 | not in the official library (use `hf.co/...GGUF`) | `/think` `/no_think`; 6 EU languages + ar/zh/ru; IFEval 76.7 [HF blog; card] |
| **LFM2.5-1.2B-Instruct** (2026-01-05) | 1.17B, 16 layers (10 gated-conv + 6 GQA), 32K | **LFM Open License v1.0** (free commercial use below $10M annual revenue) | Library has only `lfm2.5:8b` and `lfm2:24b`; small ones via `hf.co/LiquidAI/…-GGUF` | IFEval 86.23. Recommended for extraction, agentic and RAG; *not* knowledge or code. **Hybrid**, same cache caveat [Liquid blog; card; license page] |
| **LFM2.5-350M** (2026-03-31) / **LFM2.5-230M** (late June 2026) | 350M / 230M, 32K | LFM Open License | via HF GGUF | 350M: IFEval 76.96, built for extraction and tool use. 230M: IFEval 71.71 [Liquid blog; cards] |
| Liquid Nanos: LFM2-350M-Extract / LFM2-1.2B-Extract (Sep 2025) | 350M / 1.2B | LFM Open License | via HF GGUF | Unstructured text to JSON/XML/YAML; vendor claims the 350M beats Gemma 3 4B at extraction [Liquid blog] |
| **Phi-4-mini-instruct** (Feb 2025) | 3.8B, 128K, 200K vocab | MIT | `phi4-mini` 2.5 GB (Ollama ≥0.5.13) | MMLU 67.3; function calling; no Indic languages listed [card; Ollama] |
| **Granite 4.0 Nano** (2025-10-28): 350M, 1B (dense); H-350M, H-1B (~1.5B, hybrid Mamba-2) | 350M dense: 28 layers, 32K | Apache-2.0 | `granite4:350m` 708 MB (32K), `granite4:1b` 3.3 GB (128K), `granite4:3b` (micro) 2.1 GB | 350M: IFEval 55.4, BFCLv3 39.3. Lists text classification and extraction as intended uses; 12 languages, no Indic [card; HF blog; Ollama] |
| **Granite 4.1** (2026-04-29) | dense 3B / 8B / 30B, up to 512K (Ollama lists 128K) | Apache-2.0 | `granite4.1:3b` 2.1 GB | Newest dense Granite; the release also includes Guardian 4.1 [IBM Research blog; Ollama] |
| **Llama 3.2 1B / 3B** (2024-09-25) | 1.23B / 3.21B, 128K | Llama 3.2 Community License | `llama3.2:1b` 1.3 GB, `3b` 2.0 GB | Officially supports **Hindi** and Thai. IFEval 59.5 / 77.4 [card; Ollama] |
| **Sarvam-1** (Oct 2024) | 2B **base** (not instruct), 8K; 10 Indic languages | "Sarvam non-commercial license" per card | — | Tokenizer fertility 1.4–2.1; meant to be fine-tuned [card] |
| Sarvam-M (May 2025) / Sarvam 30B & 105B (2026-03-06) | 24B / 30B (2.4B active MoE) / 105B MoE | Apache-2.0 | — | No open Sarvam instruct model under 5B; too big for System 1 [Sarvam blog; search] |

**Takeaway:**
- For logprob-scored System 1 on this Mac, the practical small LMs are the plain-transformer ones: **Qwen3-0.6B, Qwen3-1.7B, Qwen3-4B-Instruct-2507, Gemma 3 270M/1B, Granite 4.0 350M/1B, Llama 3.2 1B/3B**. Their prefix caching works in Ollama 0.34.4.
- Qwen3.5 small models are stronger and more multilingual but hybrid, so test caching first.

---

## 4. Encoders and task-specific small models

All of these run **in-process** (transformers / sentence-transformers / gliner / ONNX), not in Ollama. That means adding torch and transformers to the uv environment (not installed yet).

### 4.1 Backbones for fine-tuned heads

- **ModernBERT** (Warner et al. 2024, arXiv 2412.13663; released 2024-12-18): base 149M / 22 layers, large 395M / 28 layers, **8,192 context**, Apache-2.0, English + code. GLUE 88.4 (base) / 90.4 (large). On an **NVIDIA L4**, fine-tuning on ~15k examples × 5 epochs took **321 s** vs 1,048 s for BERT [card; philschmid.de].
- **mmBERT** (arXiv 2509.06888, Sept 2025): small 140M (42M non-embedding), base 307M (110M non-embedding), 8,192 context, **1,800+ languages**, MIT. Beats XLM-R on classification and retrieval [card]. The card does not list individual Indic languages.
- **DeBERTa-v3**: base / large (~184M / ~435M), MIT. The basis for most NLI / zero-shot / prompt-injection classifiers below.
- **LFM2.5-Encoder-230M**: bidirectional, 8K context, 15 languages **including Hindi**, LFM Open License. GLUE/SuperGLUE + multilingual average 79.29, vs ModernBERT-base 78.19 and ModernBERT-large 81.68 [card].

### 4.2 Extraction, NER and zero-shot classification

- **GLiNER** (Zaratiana et al., NAACL 2024, arXiv 2311.08526): zero-shot span NER with a bidirectional encoder, Apache-2.0. Variants include gliner_small-v2.5, gliner_multi_pii-v1, knowledgator bi-encoders and relex. ONNX, INT8 and FP16 supported [repo].
- **GLiNER2** (arXiv 2507.18546, 2025-07-24): `fastino/gliner2-base-v1`, **205M, Apache-2.0**. One model covers **NER + text classification + structured JSON extraction + relation extraction**. CPU-first; `pip install gliner2`; `extract_entities`, `classify_text`, `extract_json` [card; paper]. **Best single encoder for the Librarian.**
- **GLiClass** (arXiv 2508.07662, 2025-08-11; Knowledgator): zero-shot / few-shot sequence classification over many labels in one forward pass. The repo claims ~10× faster than cross-encoder NLI. Multi-label and hierarchical labels. Apache-2.0 [repo; paper].
- **GLiREL** (arXiv 2501.03172): zero-shot relation extraction (`glirel-large-v0`), **CC BY-NC-SA 4.0**, so non-commercial [repo].
- **NuExtract 2.0** (NuMind): 2B (Qwen2-VL-2B, MIT), 4B (Qwen2.5-VL-3B, **Qwen Research License**), 8B (MIT). JSON-template extraction, multimodal and multilingual; GGUF quantisations exist [card]. A System-2-ish extractor rather than a classifier.
- **GLiGuard** (arXiv 2605.07982, 2026-05-08): see §4.7.

### 4.3 Few-shot and NLI

- **SetFit** (Tunstall et al. 2022, arXiv 2209.11055; Apache-2.0): contrastive fine-tuning of a Sentence-Transformer plus a light head. With 8 examples per class it was competitive with RoBERTa-large trained on 3k examples. The 2022 blog reports ~30 s on a V100 for 8 examples per class. Any multilingual Sentence-Transformer body works [repo; HF blog].
- **NLI cross-encoders**:
  - `cross-encoder/nli-deberta-v3-base` (~0.2B, Apache-2.0): outputs **(contradiction, entailment, neutral)**; SNLI-test 92.38%, MNLI-mismatched 90.04% [card]. A natural Historian pre-filter for "does this new fact contradict a stored decision?".
  - `MoritzLaurer/deberta-v3-large-zeroshot-v2.0` (0.4B, MIT): 2-way entailment for zero-shot labels; mean F1-macro 0.676 over 28 datasets vs bart-large-mnli 0.497; 512-token limit.
  - Collection siblings: `-c` commercially-clean variants and `bge-m3-zeroshot-v2.0` (multilingual, 8,192 context) [card].

### 4.4 Rerankers (retrieved passage relevant?)

| Model | Size | License | Scoring | Reported quality | Local path |
|---|---|---|---|---|---|
| **Qwen3-Reranker-0.6B / 4B / 8B** (2025-06-05, arXiv 2506.05176) | 0.6B (28 layers), 32K | Apache-2.0 | P("yes") / (P("yes")+P("no")) from the LM head; instruction-aware (+1–5%) | 0.6B: MTEB-R 65.80, MMTEB-R 66.36, MLDR 67.28, vs bge-reranker-v2-m3 57.03 / 58.36 / 59.51 [card] | transformers / sentence-transformers; GGUF (ggml-org Q8_0, 639 MB); emulate through Ollama raw + logprobs (§1.1) |
| **bge-reranker-v2-m3** | ~0.6B (bge-m3 base) | Apache-2.0 | cross-encoder logit; `normalize=True` gives a sigmoid 0–1 score | strong multilingual baseline | FlagEmbedding / sentence-transformers; llama-server `--reranking` |
| bge-reranker-v2-gemma / v2-minicpm-layerwise | gemma-2b / MiniCPM-2B | per base model | LLM-based rerankers; layerwise lets you choose how many layers to run | — | transformers [card] |
| **mxbai-rerank-base-v2** (tech report 2506.03487, June 2025) | 0.5B (qwen2) | Apache-2.0 | cross-encoder | BEIR 55.57; 100+ languages [card] | `mxbai-rerank` package / sentence-transformers |
| **jina-reranker-v3** (2025-09-29) / **v3.5** (2026-07-27) | 0.6B (Qwen3-0.6B base), listwise, up to 64 docs in 131K | **CC BY-NC 4.0** | listwise "last but not late" interaction | v3 BEIR 61.94, vs mxbai-base-v2 58.40, bge-v2-m3 56.51, Qwen3-Reranker-0.6B 56.28 (Jina's own table) [card; arXiv 2607.18152] | GGUF / MLX available; **non-commercial** |
| monoT5 | T5-based | Apache-2.0 | P("true") | older baseline | transformers |

The two vendor tables disagree on how Qwen3-Reranker-0.6B ranks against bge-v2-m3 (different benchmarks). **Evaluate on your own data.**

### 4.5 Embeddings (routing, dedup candidates, SetFit bodies)

- **bge-m3** (installed; MIT; 1024-d; 8,192 context; multilingual). ~21 ms per 254 tokens through Ollama [measured].
- **Qwen3-Embedding-0.6B / 4B / 8B** (2025-06-05; Apache-2.0; 32K context; MRL dimensions 32–1024 for 0.6B). MTEB multilingual 64.33 (0.6B) vs bge-m3 59.56; the 8B was #1 at 70.58 in June 2025. Ollama `qwen3-embedding:0.6b` is 639 MB [card; Ollama].
- **EmbeddingGemma-300M** (2025, Gemma license): 2,048 context, 768-d with MRL 512/256/128. MTEB v2 multilingual 61.15, English 69.67. Uses task prompts such as `task: classification | query: …`. **No float16** activations. Ollama `embeddinggemma:300m` is 622 MB [card; Ollama].

### 4.6 Grounding and hallucination detectors ("is this answer supported by its sources?")

| Model | Size | License | Reported accuracy | How to run |
|---|---|---|---|---|
| **MiniCheck-Flan-T5-Large** (Tang, Laban, Durrett, EMNLP 2024, arXiv 2404.10774) | 0.8B | MIT | LLM-AggreFact **75.0** BAcc; "400× cheaper than GPT-4" | `minicheck` pip package; document + single sentence gives label + prob [repo; card; leaderboard] |
| **Bespoke-MiniCheck-7B** | 7–8B (InternLM2.5-7B) | **CC BY-NC 4.0** | LLM-AggreFact **77.4** (top of the board, above Claude-3.5 Sonnet 77.2) | **Ollama `bespoke-minicheck:7b` (4.7 GB, 32K)**: prompt `Document: … Claim: …`, output Yes/No, so logprobs give P(Yes) [card; Ollama; leaderboard] |
| **FactCG-DeBERTa-L** | 0.4B | (not checked) | LLM-AggreFact 75.6 | [leaderboard] |
| **AlignScore** (Zha et al., ACL 2023, arXiv 2305.16739) | 125M / 355M (RoBERTa) | MIT | SummaC 88.6 AUC, TRUE 83.8 AUC | chunks context into ~350-token pieces and claims into sentences [repo] |
| **Vectara HHEM-2.1-open** | 0.1B (flan-t5-base) | Apache-2.0 | AggreFact-SOTA 76.55 BAcc; RAGTruth-QA 74.28 BAcc; card says it beats GPT-3.5/GPT-4 | "<600 MB RAM, ~1.5 s for 2k tokens on a modern x86 CPU"; score 0–1; `trust_remote_code` [card] |
| **LettuceDetect** (arXiv 2502.17125) | ModernBERT-large 0.4B (also base, EuroBERT, mmBERT, Qwen-2B variants) | MIT | RAGTruth example-level F1 **79.22%** (large-en-v1); flags **token spans** | 4K–8K context; v0.2.2 (2026-07-05) adds code and agentic outputs [repo; card] |
| **IBM Granite Guardian** | Ollama `granite3-guardian:2b` (2.7 GB) / `:8b` (5.8 GB), v3.0 (2024-10-21); HF 3.3-8B (2025-08-01), 4.1-8B (2026-04) | Apache-2.0 | 3.3-8B: LLM-AggreFact 76.5 (leaderboard); TRUE 0.777 BAcc; function-call hallucination 0.74 | Ollama: set the **system prompt to the risk name** (`groundedness`, `relevance` = context relevance, `answer_relevance`, `jailbreak`, `harm`, …). The **single output token is Yes/No**, so logprobs give P(Yes). 3.3/4.1 wrap `<score>yes/no</score>` with optional `<think>` [Ollama; card; IBM docs] |
| **Patronus Lynx 8B v1.1** (2024-07-11) | 8B (Llama-3.1-8B) | **CC BY-NC 4.0** | HaluBench 84.3% vs GPT-4o 86.5% | JSON {REASONING, SCORE PASS/FAIL}; GGUF quantisations exist [card] |

### 4.7 Safety and prompt injection (coordinate with the security slice)

- **Llama Prompt Guard 2** (April 2025; license effective 2025-04-05; Llama 4 Community License; **gated download on HF**).
  - **86M** (mDeBERTa-base, multilingual incl. **Hindi**, Thai, fr, de, it, pt, es): English AUC .998, recall 97.5% at 1% false-positive rate, **92.4 ms on an A100 for 512 tokens**.
  - **22M** (DeBERTa-xsmall): AUC .995, recall 88.7% at 1% FPR, 19.3 ms; weaker multilingually.
  - Labels BENIGN / MALICIOUS; 512-token windows, so split long inputs and scan the pieces in parallel.
  - Covers **explicit, known** injection and jailbreak patterns and is "vulnerable to adaptive attacks" [card].
- **ProtectAI `deberta-v3-base-prompt-injection-v2`** (2024; Apache-2.0; 0.2B): held-out accuracy 95.25%, recall 99.74%. **Does not detect jailbreaks or non-English text. Project archived** [card].
- **qualifire `prompt-injection-sentinel`** (ModernBERT-large 0.4B; arXiv 2506.05446, June 2025): average F1 93.86 vs ProtectAI v2 70.93 across 4 datasets. **Gated, "other" license**; a v2 exists [card].
- **GLiGuard-LLMGuardrails-300M** (fastino; arXiv 2605.07982, 2026-05-08; Apache-2.0): GLiNER2-based and CPU-first. One pass covers prompt/response safety, refusal, harm categories and **jailbreak subtypes including prompt injection, instruction override and system-prompt exfiltration**. Prompt harmfulness average F1 87.7; up to 16× throughput vs decoder guards [card; paper].
- **Qwen3Guard-Gen-0.6B / 4B / 8B** and **Stream** variants (tech report arXiv 2510.14276, Oct 2025; Apache-2.0). Outputs Safe / Unsafe / Controversial plus categories (incl. **PII** and **Jailbreak**, input only) and refusal. 119 languages. Covers **safety, not prompt injection**. transformers, vLLM ≥0.9, SGLang [card].
- **Llama Guard 4 12B** (April 2025; Llama 4 license): multimodal S1–S14 hazard classifier. Meta itself points to Prompt Guard 2 for injection. **Too big** alongside qwen3:14b [card].
- **ShieldGemma 2 4B** (arXiv 2504.01081; Gemma license): **image** safety only (sexual / dangerous / violent), outputs Yes/No probabilities. Not relevant to text-injection detection [card].
- **WildGuard 7B** (June 2024; Mistral-7B; Apache-2.0): prompt harm, response harm and refusal; beats Llama-Guard-2 and matches GPT-4 [card]. Heavy for System 1.

### 4.8 PII

- **Microsoft Presidio** (MIT): analyzer (regex, checksum and NER recognizers), anonymizer, image redactor. Supports spaCy, stanza, transformers and **`GLiNERRecognizer`**. Disclaimer: no guarantee it finds all PII [repo; issues #1527 / #1760; docs mirror presidio.dataprivacystack.org].
- **knowledgator `gliner-pii-base-v1.0`** (Apache-2.0; 60+ PII types; ONNX FP16 330 MB / UINT8 197 MB): F1 edge 75.50 / small 76.84 / **base 80.99** / large 83.25 [card].
- **nvidia/gliner-PII** (2025-10-28; ~570M from gliner_large-v2.1; **NVIDIA Open Model License**; 55+ PII/PHI types; English): F1 at threshold 0.3 is 0.87 on Nemotron-PII, 0.70 on Gretel, 0.64 on AI4Privacy [card].
- `urchade/gliner_multi_pii-v1` (multilingual, Apache-2.0) and gretel-gliner-bi-* are alternatives. **GLiNER2-PII** (arXiv 2605.09973, 2026) is listed in the GLiNER README; details not checked.

---

## 5. Fine-tuning small classifiers on this Mac

- **MLX-LM LoRA** [LORA.md]:
  - LoRA, DoRA or full fine-tuning; QLoRA by passing a quantised model.
  - Data formats: chat, completions, tools, text. Flags: `--mask-prompt`, `--grad-checkpoint`, `--num-layers` (default 16), `--batch-size` (default 4), `--iters`.
  - Fuse adapters with `mlx_lm.fuse`; GGUF export only for Mistral/Mixtral/Llama.
  - Published speed: the doc's example runs at ~250 tok/s on an M1 Max 32 GB (a 7B model).
  - Community data point [repo sciences44/mlx-lora-finetune, M1 64 GB]: Qwen3.5-0.8B / 2B / 4B 4-bit, 5,000 examples, 600 iterations, took **~8–15 min** with peak RAM 3.9 / 5.9 / 11.1 GB.
  - **Estimate for this M5 Pro:** LoRA on Qwen3-0.6B/1.7B (or Gemma 3 270M) for single-token-label SFT on 500–5,000 examples of ~300 tokens, 2–3 epochs, should take **~5–40 min**. Peak memory stays under 6 GB for models of 1.7B or less. Unmeasured.
- **SetFit on MPS:** sentence-transformers picks MPS automatically [secondary]. With a small body (bge-small / e5-small / mpnet-base) and 500–2,000 examples: **~2–15 min** [estimate]. The contrastive pair count grows quickly, so cap `num_iterations`.
- **ModernBERT / DeBERTa fine-tuning on MPS:** the L4 reference was 321 s for 75k example-passes [card]. MPS has no FlashAttention path and is likely several times slower than an L4 [estimate]. For 500–5,000 short examples × 3–5 epochs, expect **~2–20 min** for base models [estimate]. Secondary sources suggest `dataloader_num_workers=0` and `pin_memory=False` on MPS [secondary].
- Google says Gemma 3 270M fine-tuning experiments take "hours rather than days" and recommends Hugging Face, Unsloth or JAX [Google dev blog].

---

## 6. Emerging: "System One" decision models (Sept 2026)

- **Jev** (TypeSafe AI, launched **2026-09-15**) is marketed as a "System One model" that returns typed decisions with probabilities:
  - `noul` = yes/no probability, `choice` = distribution over options, `score` = calibrated scale.
  - Trained with "RL for Calibrated Decisions"; ~100 ms median. **API-only, closed weights** [flaviocopes.com deep dive, secondary].
  - It validates the Omnitrix System-1 concept almost exactly, but it is not local, so it is not usable for Track 1.
- **Open local reproductions** appeared within days:
  - `amithgc/local-jev` (MIT code) serves the same API offline. Backends: **Qwen3.5-4B (bf16, 9.32 GB) reading next-token probabilities of A/B/C with temperature calibration** (80.5% on "JevBench", 651 ms median on M4 Max) and an NLI DeBERTa-large backend (54.1%, 76 ms) [repo].
  - Other names from search snippets (Kev, NanoJev-0.6B, Laya-421M, OpenJev Verdict-151M, KaLM-Jev) are unchecked.
  - Useful as design references; not vetted.

---

## 7. Recommended System-1 zoo for THIS machine

Budget: ~18 GB usable by the GPU. qwen3:14b (~9.3 GB + KV) stays resident as System 2. The S1 LMs below add ~4.5 GB. Encoders run in the Python process on CPU/MPS (~1–2 GB).

**Set `OLLAMA_MAX_LOADED_MODELS=5`** (the default is 3 here) and **`keep_alive:-1`** for S1 models.

| # | Role / decision types | Candidate | Size · License | How to call | Expected latency here | Caveats |
|---|---|---|---|---|---|---|
| 1 | **Default S1 LM:** email noise? · needs retrieval? · which store/tool (≤ ~10 options) · same-entity given a shortlist · action needs approval? · quick relevance yes/no | **qwen3:1.7b** (installed) | 1.4 GB · Apache-2.0 | Ollama `/api/chat`, `think:false`, `num_predict:1`, `logprobs:true`, `top_logprobs:20`; one stable system prefix per decision type | **33–40 ms** with cached prefix; ~100 ms uncached [measured] | Overconfident zero-shot (§2.1); calibrate per task on labelled dev data; design labels with distinct first tokens |
| 2 | **Strong S1 / tie-breaker:** does a new fact contradict a stored decision? · is the answer supported (fallback)? · ambiguous routing | **qwen3:4b-instruct** (Qwen3-4B-Instruct-2507) | 2.5 GB · Apache-2.0 | same as #1 (non-thinking model) | **65–105 ms** cached; ~250 ms uncached [measured, same-size build] | **Replace the current `qwen3:4b` (thinking-only)**; must be pulled |
| 3 | High-volume **fine-tuned** micro-classifiers (email triage, intent/tool routing) | **qwen3:0.6b** or **gemma3:270m** or **granite4:350m** + LoRA via MLX-LM (then GGUF or MLX serving) | 0.3–0.7 GB · Apache-2.0 / Gemma ToU / Apache-2.0 | Ollama (after fine-tune, import GGUF) or mlx-lm Python (exact logits) | ~15–25 ms [estimate] | Needs labelled data (500–5k); Gemma ToU if using 270M |
| 4 | Semantic routing, near-duplicate / entity-candidate retrieval, SetFit body, kNN "have we seen this?" | **bge-m3** (installed) (alt: qwen3-embedding:0.6b) | 0.57B · MIT (alt Apache-2.0) | Ollama `/api/embed` + pgvector | **~21 ms / 254 tok** [measured] | No batching speed-up in Ollama |
| 5 | **Retrieved passage relevant?** / rerank | **bge-reranker-v2-m3** or **Qwen3-Reranker-0.6B** | ~0.6B · Apache-2.0 | sentence-transformers `CrossEncoder` on MPS; or llama-server `--reranking`; or Ollama raw-mode P(yes) emulation | not measured (expect tens of ms per pair; batch) | Ollama has no rerank API; needs torch or llama.cpp |
| 6 | **Entity mentions / extraction / zero-shot labels / PII spans** (Librarian) | **GLiNER2-base** (+ knowledgator `gliner-pii-base-v1.0`, + Presidio) | 205M · Apache-2.0 (PII model Apache-2.0; Presidio MIT) | `gliner2` / `gliner` Python on CPU; Presidio `GLiNERRecognizer` | not measured (CPU-first design) | Mostly English-centred; test on Indic names |
| 7 | **Contradiction pre-filter** (Historian, Fact Checker) | **cross-encoder/nli-deberta-v3-base** (multilingual alt: bge-m3-zeroshot-v2.0) | ~0.2B · Apache-2.0 (alt MIT) | sentence-transformers `CrossEncoder` gives 3 logits (contradiction, entailment, neutral) | not measured | 512-token limit; escalate "contradiction" to #2 or System 2 |
| 8 | **Answer supported by sources?** (Fact Checker) | **HHEM-2.1-open** or **MiniCheck-Flan-T5-L**; Ollama option **granite3-guardian:2b** (`groundedness`, `answer_relevance`, `relevance`) | 0.1B Apache-2.0 / 0.8B MIT / 2.7 GB Apache-2.0 | transformers; or Ollama single-token Yes/No gives P(Yes) | HHEM card: ~1.5 s for 2k tokens on x86 CPU; others not measured | bespoke-minicheck:7b is stronger (77.4) but **CC BY-NC** and 4.7 GB |
| 9 | **Hidden prompt injection in PDFs / emails / web** (Guardian) | **Llama Prompt Guard 2 86M** (22M for speed); alt **GLiGuard-300M** | 86M / 22M · Llama 4 Community (gated) / Apache-2.0 | transformers `text-classification` over 512-token windows | A100: 92 / 19 ms per 512 tok [card]; Mac not measured | Explicit patterns only; pair with structural defences (security slice) |
| 10 | Output safety / PII / jailbreak moderation (optional) | **Qwen3Guard-Gen-0.6B** | 0.6B · Apache-2.0 | transformers, or `hf.co/…GGUF` in Ollama if a GGUF exists (not checked) | not measured | Safety categories, not injection |

**Which runtime path gives per-token logprobs with the least setup? The Ollama already running (0.34.4).**
- The native `/api/chat` and `/api/generate` take `"logprobs": true, "top_logprobs": ≤20`. `/v1/chat/completions` also works on this version.
- Nothing needs installing. Prompt-prefix caching comes free through the embedded llama-server host-RAM prompt cache.
- **mlx-lm** is the next step when you need exact probabilities for arbitrary label sets (no top-20 cap), LoRA training, or full-vocab logprobs. It costs one `uv add mlx-lm`.
- **llama-server** standalone adds `logit_bias`, GBNF and `/v1/rerank`.

---

## 8. Key takeaways for Omnitrix

1. **Logprobs already work on your stack.** Ollama 0.34.4 returns `logprobs[].top_logprobs[]` on `/api/chat` and `/api/generate` (added in v0.12.11, Nov 2025). `/v1/chat/completions` also returns them here even though the docs say otherwise. The cap is **20 alternatives per position**.
2. **Your `qwen3:4b` is the Thinking-2507 build and ignores `think:false`.** It starts reasoning in the answer, which breaks single-token scoring. Use `qwen3:4b-instruct` (Instruct-2507) or hybrid `qwen3:1.7b` / `qwen3:0.6b` with `think:false`.
3. **Measured latency:** qwen3:1.7b decides in **~35 ms** over a ~400-token prompt when the instruction prefix is cached (~100 ms uncached); the 4B takes ~65–105 ms. System 1 is ~10–30× cheaper than a 14B call.
4. **Prefix caching is automatic:** Ollama 0.34.4 runs llama-server with an 8 GiB host-RAM prompt cache, and three different decision-type prefixes all stayed cached with NUM_PARALLEL=1. **Keep each decision type's instructions as a fixed prefix and put the variable item last.**
5. **Avoid hybrid/SSM small models for cached System 1 until tested:** Qwen3.5 small, LFM2/2.5 and Granite-4.0-H have open prompt-cache reuse bugs in llama.cpp, and Ollama's checkpoint spacing is 8192.
6. **Don't score off JSON-constrained output:** Ollama's reported logprobs ignore the `format` grammar. Ask for a one-token answer, pick labels with distinct first tokens, and renormalise over the label set.
7. **Raw logprobs are overconfident.** The toy test showed P≈1.0 on a wrong label. Build a small labelled dev set per decision type, fit temperature or Platt scaling, and set escalation thresholds on it.
8. **Encoders win on fixed-schema tasks and give real scores:** GLiNER2 (Librarian), NLI DeBERTa (Historian), HHEM or MiniCheck (Fact Checker), Prompt Guard 2 (Guardian), bge-reranker-v2-m3 or Qwen3-Reranker (Researcher). The cost is adding torch and transformers to the uv environment.
9. **Ollama has no rerank endpoint and no classifier heads** (issue #16076 open). Run rerankers in-process, via llama-server `--reranking`, or emulate Qwen3-Reranker through raw-mode P(yes); the recipe was tested with a stand-in model.
10. **Granite Guardian in Ollama is a ready-made judge.** Set the system prompt to `groundedness`, `answer_relevance`, `relevance` or `jailbreak`; it answers with one Yes/No token, so logprobs give a probability with no extra code.
11. **Memory and scheduling:** ~18 GB is usable by the GPU. The default `OLLAMA_MAX_LOADED_MODELS` here is 3, so a 4th model evicts one and costs 0.5–14 s to reload. Set it to 5 and use `keep_alive:-1` for System-1 models.
12. **Licensing traps:**
    - Non-commercial (CC BY-NC): bespoke-minicheck, Lynx, jina-reranker-v3/3.5, GLiREL. Sarvam-1 carries a non-commercial licence.
    - Custom licences: Llama (Prompt Guard 2, Llama 3.2), Gemma ToU (Gemma 3 / 3n / EmbeddingGemma; Gemma 4 is Apache-2.0), LFM Open License (under $10M revenue), NVIDIA OML (gliner-PII).
    - Apache/MIT choices exist for every role.
13. **Indic coverage:** Qwen3.5 (201 languages), Gemma 3/4 (140+), bge-m3, mmBERT (1,800+), LFM2.5-Encoder (Hindi), Prompt Guard 2 86M (Hindi) and Llama 3.2 (Hindi). There is no open Sarvam instruct model under 5B.
14. **Pin Ollama 0.34.4.** v0.40.0-rc0 (released today) switches Apple Silicon to the MLX runner by default, which may change logprob and caching behaviour.
15. **The idea is timely.** TypeSafe's closed "Jev" System-One API (2026-09-15) and open local clones use exactly this next-token-probability plus calibration pattern. A good framing for the pitch: "sovereign Jev".

## 9. Open questions

- Does Ollama's MLX runner (default from v0.40) keep logprobs, `prompt_eval_cached_count` and multi-prefix caching for Qwen3 small models? Does the top_logprobs cap change (#18590 closed; outcome unknown)?
- Do Qwen3.5-0.8B/2B get **any** prefix reuse in Ollama 0.34.4 for ~400-token prompts? Needs `ollama pull qwen3.5:2b` and a re-run of `scratchpad/bench/s1_latency.py`.
- Actual MPS / CPU / ONNX latency on this M5 Pro for Prompt Guard 2, GLiNER2, NLI DeBERTa, bge-reranker-v2-m3 and HHEM (none measured).
- Is the llama.cpp Metal tensor (Neural Accelerator) path active in Ollama's bundled llama-server on the 16-core M5 Pro? The log is silent; measured prefill looks healthy.
- Which exact flags does llama-server need to serve Qwen3-Reranker via `/v1/rerank`? A GGUF exists; flags unchecked.
- How well are small-LM probabilities calibrated per decision type, and how many labels are needed to reach a useful escalation rate? Needs the team's own dev sets.
- Could Apple's on-device model (apple-fm-sdk) expose token probabilities? Not documented; if so it would be a no-download System 1.

## 10. Unverified (do not rely on without checking)

- Fine-tuning time estimates for this Mac in §5 (MLX LoRA 5–40 min; SetFit 2–15 min; ModernBERT/DeBERTa 2–20 min). **Estimates only.**
- qwen3:0.6b ~15–25 ms and qwen3:14b ~250–400 ms cached latencies (extrapolated, not measured).
- The 16-core M5 Pro reaching ~80% of the 20-core prefill in the llama.cpp #4167 table (assumed scaling).
- Qwen3.5-4B non-thinking benchmark numbers. The fetched card summary (MMLU-Pro 79.1, IFEval 89.8) may mix modes, so they are omitted above. The Qwen3.5-0.8B summary mentioning "sparse MoE" conflicts with the dense-FFN layout in the 2B/4B cards.
- LFM2.5-350M vendor speed claim (44.8K prefill tok/s on M5 Max "CPU") and LFM2.5-230M's exact release date (press dated 26–27 June 2026).
- Ollama v0.21.1 date (page summary said 2024-04-22, inconsistent with its content; probably April 2026). Details of the MLX runner's logprob support ("compatible models").
- SGLang MLX backend limitations (greedy-only, no cache reuse, no continuous batching) come from a secondary source. vllm-metal support for structured outputs and logprobs is undocumented.
- LM Studio / modelfit claims about the llama.cpp Metal tensor API env vars on M5.
- MPS training tips (`dataloader_num_workers=0`, `pin_memory=False`, graph-cache restarts): secondary.
- Presidio recognizers for Indian IDs (Aadhaar/PAN) not checked. The presidio.dataprivacystack.org mirror or org move not checked.
- GLiNER2-PII (arXiv 2605.09973) and FactCG-DeBERTa-L licence not checked.
- Open Jev reproductions other than local-jev (Kev, NanoJev, Laya, OpenJev Verdict, KaLM-Jev); "JevBench" validity; Jev latency and price (secondary).
- Whether Qwen3Guard GGUFs exist for Ollama.
- Outlines support for mlx-lm (not confirmed in this session).
- Qwen3.8-Flash-Next / "Qwen4 preview" (search snippet only).

---

## Sources (primary unless noted)

**Ollama**
- docs.ollama.com/api/generate · docs.ollama.com/api/openai-compatibility · docs.ollama.com/faq · github.com/ollama/ollama/blob/main/docs/api.md
- Releases: github.com/ollama/ollama/releases (v0.12.11, v0.21.1, v0.33.x, v0.34.x, v0.40.0-rc0)
- Issues: #16117 · #16076 · #18579 · #18590 · PR #18580
- Blogs: ollama.com/blog/structured-outputs · /thinking · /mlx · /mlx-performance
- Library pages: ollama.com/library/{qwen3, qwen3/tags, qwen3.5, gemma3, gemma3n, gemma4, granite4, granite4.1, granite3-guardian, bespoke-minicheck, llama3.2, phi4-mini, lfm2, lfm2.5, qwen3-embedding, embeddinggemma}
- huggingface.co/docs/hub/ollama

**llama.cpp**
- github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md · PR #16391 · discussion #4167 · discussion #19264 · issues #24055, #22384, #25913
- huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF · (secondary) github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2040

**MLX**
- github.com/ml-explore/mlx-lm (SERVER.md, LORA.md, generate.py) · pypi.org/project/mlx-lm · pypi.org/project/mlx
- machinelearning.apple.com/research/exploring-llms-mlx-m5 · arXiv 2607.19438 (BaseRT) · arXiv 2609.19169 (SiliconBench) · github.com/john-rocky/apple-silicon-llm-bench · github.com/sciences44/mlx-lora-finetune

**Other runtimes**
- docs.sglang.io/docs/references/frontend/choices_methods · lmsysorg.mintlify.app/docs/hardware-platforms/apple_metal
- docs.vllm.ai/en/latest/features/structured_outputs.html · github.com/vllm-project/vllm-metal
- github.com/dottxt-ai/outlines · github.com/mlc-ai/xgrammar · github.com/guidance-ai/llguidance · github.com/apple/python-apple-fm-sdk

**Small LMs**
- huggingface.co/Qwen/{Qwen3-0.6B, Qwen3-4B-Instruct-2507, Qwen3.5-0.8B, Qwen3.5-2B, Qwen3.5-4B} · github.com/QwenLM/Qwen3 · github.com/QwenLM/Qwen3.8
- huggingface.co/google/{gemma-3-270m, gemma-3n-E2B-it, gemma-4-E2B-it} · developers.googleblog.com/en/introducing-gemma-3-270m/ · developers.googleblog.com/en/introducing-gemma-3n-developer-guide/ · blog.google/…/gemma-4/
- huggingface.co/HuggingFaceTB/SmolLM3-3B · huggingface.co/blog/smollm3
- liquid.ai/blog/introducing-lfm2-5-the-next-generation-of-on-device-ai · liquid.ai/blog/lfm2-5-350m-no-size-left-behind · huggingface.co/LiquidAI/{LFM2.5-1.2B-Instruct, LFM2.5-230M, LFM2.5-Encoder-230M} · liquid.ai/lfm-license (search summary) · liquid.ai/blog/introducing-liquid-nanos… (search)
- huggingface.co/microsoft/Phi-4-mini-instruct · huggingface.co/ibm-granite/granite-4.0-350m · huggingface.co/blog/ibm-granite/granite-4-nano · research.ibm.com/blog/granite-4-1-ai-foundation-models
- huggingface.co/meta-llama/Llama-3.2-1B-Instruct · huggingface.co/sarvamai/sarvam-1 · sarvam.ai/blogs/sarvam-30b-105b

**Encoders**
- huggingface.co/answerdotai/ModernBERT-base · huggingface.co/jhu-clsp/mmBERT-base · philschmid.de/fine-tune-modern-bert-in-2025
- github.com/urchade/GLiNER · huggingface.co/fastino/gliner2-base-v1 · arXiv 2507.18546 · github.com/Knowledgator/GLiClass · arXiv 2508.07662 · github.com/jackboyla/GLiREL · huggingface.co/numind/NuExtract-2.0-2B
- github.com/huggingface/setfit · huggingface.co/blog/setfit · huggingface.co/cross-encoder/nli-deberta-v3-base · huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0

**Rerankers and embeddings**
- huggingface.co/Qwen/Qwen3-Reranker-0.6B · huggingface.co/BAAI/bge-reranker-v2-m3 · huggingface.co/mixedbread-ai/mxbai-rerank-base-v2 · huggingface.co/jinaai/jina-reranker-v3 · arXiv 2607.18152 (jina-reranker-v3.5)
- huggingface.co/Qwen/Qwen3-Embedding-0.6B · huggingface.co/google/embeddinggemma-300m

**Grounding**
- github.com/Liyan06/MiniCheck · huggingface.co/lytang/MiniCheck-Flan-T5-Large · huggingface.co/bespokelabs/Bespoke-MiniCheck-7B · llm-aggrefact.github.io
- huggingface.co/vectara/hallucination_evaluation_model · github.com/KRLabsOrg/LettuceDetect · huggingface.co/KRLabsOrg/lettucedect-large-modernbert-en-v1 · github.com/yuh-zha/AlignScore · huggingface.co/PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct-v1.1
- huggingface.co/ibm-granite/granite-guardian-3.3-8b · ibm.com/granite/docs/models/guardian

**Safety and PII**
- huggingface.co/meta-llama/{Llama-Prompt-Guard-2-86M, Llama-Prompt-Guard-2-22M, Llama-Guard-4-12B} · huggingface.co/protectai/deberta-v3-base-prompt-injection-v2 · huggingface.co/qualifire/prompt-injection-sentinel · huggingface.co/fastino/gliguard-LLMGuardrails-300M · arXiv 2605.07982
- huggingface.co/Qwen/Qwen3Guard-Gen-0.6B · huggingface.co/google/shieldgemma-2-4b-it · huggingface.co/allenai/wildguard
- github.com/microsoft/presidio · huggingface.co/nvidia/gliner-PII · huggingface.co/knowledgator/gliner-pii-base-v1.0

**System-One wave**
- flaviocopes.com/jev/ (secondary) · github.com/amithgc/local-jev

**Local benchmark scripts:** `scratchpad/bench/s1_latency.py`, `scratchpad/bench/s1_alternate.py` (session scratchpad).
