# Slice E: Controlled execution, agent security, auditability and sovereignty

Research notes for **Omnitrix** (MSRIT Hackathon, Track 1 "Sovereign AI"). Compiled 2026-09-25.

**What this file covers:** MCP (spec, annotations, elicitation, security incidents, gateways), prompt injection and agent-security defences, human-in-the-loop approvals and warning fatigue, tamper-evident audit and undo, and local-first sovereignty including India's DPDP regime. It ends with a **System 0 / 1 / 2 / Human design checklist** for Guardian, Operator, Herald and the audit log.

**Terms used throughout**
- **System 0 (S0):** plain deterministic code: rules, schemas, hashes, allowlists, label propagation.
- **System 1 (S1):** a small local model (Qwen3-1.7B/4B, a PromptGuard-class encoder, or bge-m3 similarity) that returns one **choice, boolean or score**, cut at a calibrated threshold.
- **System 2 (S2):** a larger local model (Qwen3-14B) that deliberates.
- **Human (H):** an approval on the device tier chosen by Herald.
- **[V]** means verified against a primary source (arXiv abstract or HTML, official spec, blog or docs, government gazette or PIB, RFC). **[V-sec]** means verified only through an official listing, a search snippet or a reputable secondary source. Anything weaker is in the **Unverified** section at the end.

---

## 1. MCP: current spec, annotations, elicitation, sampling, roots, authorization, security issues, gateways

### 1.0 Spec timeline (as of 2026-09-25) [V]
| Revision | Status | What matters for Omnitrix |
|---|---|---|
| 2025-06-18 | Final | Structured tool output. MCP servers classified as OAuth Resource Servers, with RFC 8707 resource indicators required. **Elicitation added.** Resource links. New Security Best Practices page. JSON-RPC batching removed. |
| 2025-11-25 | Final | **URL-mode elicitation** (SEP-1036). Tool calling inside sampling (SEP-1577). Experimental **tasks** (SEP-1686). Client ID Metadata Documents (SEP-991). Icons. Tool-name guidance (SEP-986). Default values in elicitation schemas. |
| **2026-07-28** | **Current** | **Stateless core**: no initialize handshake and no `Mcp-Session-Id`. **Multi Round-Trip Requests (MRTR)** replace server-initiated `elicitation/create`, `sampling/createMessage` and `roots/list`. **Roots, Sampling and Logging deprecated** (SEP-2577). Tasks moved to an extension. `Mcp-Method`/`Mcp-Name` headers let gateways route requests. OpenTelemetry `traceparent` allowed in `_meta`. RFC 9207 `iss` validation. Dynamic Client Registration deprecated in favour of CIMD. |

Sources: https://modelcontextprotocol.io/specification/versioning ; https://modelcontextprotocol.io/specification/2025-06-18/changelog ; https://modelcontextprotocol.io/specification/2025-11-25/changelog ; https://modelcontextprotocol.io/specification/2026-07-28/changelog ; release post (D. Soria Parra and D. Delimarsky, 2026-07-28): https://blog.modelcontextprotocol.io/posts/2026-07-28/

---

#### [E1] MCP specification: Tools, tool annotations and client obligations (2025-06-18 → 2026-07-28) [V]
- **Citation:** Model Context Protocol Specification, "Server → Tools", revisions 2025-06-18 and 2026-07-28. https://modelcontextprotocol.io/specification/2025-06-18/server/tools ; https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- **Mechanism:**
  - Tools are "model-controlled". Both revisions say there **SHOULD always be a human in the loop** who can deny tool invocations. Clients SHOULD show which tools are exposed, indicate visibly when a tool is invoked, and present confirmation prompts.
  - Tools may carry optional `annotations`. Clients **MUST consider annotations untrusted unless they come from trusted servers.**
  - Security considerations: servers MUST validate inputs, enforce access control, rate-limit and sanitize outputs. Clients SHOULD prompt for confirmation on sensitive operations, **show tool inputs to the user before calling** (against exfiltration), validate results before passing them to the LLM, apply timeouts, and **log tool usage for audit**.
  - The 2026-07-28 page also has deterministic `tools/list` ordering, advice to disambiguate aggregated tools by prefixing them with a server id (tool-name guidance first appeared in 2025-11-25, SEP-986), and stateful-tool guidance: an opaque handle "is a name, not a capability", so the server must re-check authorization on every call.
- **Key quantitative results:** none (normative text).
- **Relevance to Omnitrix:** The spec's own client duties map almost one-to-one onto Guardian: confirm, show inputs, validate outputs, timeouts, audit log. Omnitrix's 12 FastMCP servers are first-party, so their annotations can be trusted **as authored by the team**. Guardian should still keep its **own** risk table as the source of truth and use the annotations only as a cross-check.

#### [E2] MCP blog, "Tool Annotations as Risk Vocabulary: What Hints Can and Can't Do" (2026-03-16) [V]
- **Citation:** O. Hungerford, S. Morrow (GitHub), L. Chang (AWS). MCP Blog, 16 Mar 2026. https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/
- **Mechanism:**
  - Four boolean hints, each with a conservative default: `readOnlyHint` (false), `destructiveHint` (**true**), `idempotentHint` (false), `openWorldHint` (**true**).
  - What hints can do: drive confirmation UX (skip dialogs for read-only tools from trusted servers), support graduated trust, and feed policy engines (for example, "no destructive tool without approval").
  - What hints cannot do: stop prompt injection, bind an untrusted server, or capture risk that only appears from the *combination* of tools in a session. The post uses Willison's lethal trifecta to make this point.
  - Open proposals: trust/sensitivity annotations (SEP-1913), governance annotations (SEP-1984), `unsafeOutputHint`, `secretHint`, `trustedHint`. A Tool Annotations Interest Group is being formed, and one question it is asking is whether some annotations should be evaluated at runtime.
- **Key quantitative results:** none.
- **Relevance to Omnitrix:** Guardian's action classes should not be derived from hints alone. An unknown or new tool should inherit the MCP defaults (destructive and open-world), which puts it in the highest approval tier. Mark any tool that returns external content (email fetch, Scout) as `openWorldHint: true`, and treat its output as untrusted.

#### [E3] MCP Elicitation (2025-06-18 form mode; 2025-11-25 URL mode; 2026-07-28 via MRTR) [V]
- **Citation:** MCP Spec, "Client → Elicitation" (2025-11-25). https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation ; 2026 changelog items 7 and 11.
- **Mechanism:**
  - Servers can ask the user for structured input mid-call. The user answers with `accept`, `decline` or `cancel`.
  - Form mode **MUST NOT** request passwords, API keys, tokens or payment credentials. Those go through **URL mode**, an out-of-band browser flow that the client and LLM never see.
  - Clients MUST show which server is asking, allow review and editing, and show the full URL before getting consent. They SHOULD highlight the domain, **warn on Punycode**, and never pre-fetch the URL.
  - Since 2026-07-28, elicitation happens through MRTR: the server returns `resultType: "input_required"` and the client retries the original call with `inputResponses`.
- **Key quantitative results:** none.
- **Relevance to Omnitrix:** Elicitation is a spec-native way for an MCP tool to ask a *confirmation question*. It does not provide approval binding, device tiers or fatigue control, so keep approvals in Guardian/Herald. Two spec details are worth copying: the three-way accept/decline/cancel outcome (cancel is not the same as decline), and "highlight the domain, warn on Punycode" for spoofed senders. MRTR means retries **re-issue the original request**, so Operator tools must be idempotent (see E36).

#### [E4] MCP Security Best Practices, Authorization, and deprecation of Sampling and Roots [V]
- **Citation:** https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices ; https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
- **Mechanism:**
  - The document covers confused-deputy consent, token passthrough (forbidden), SSRF, state-handle hijacking, **Local MCP Server Compromise**, OAuth URL validation, stdio-proxy escalation, mix-up attacks and scope minimization.
  - For local servers: clients offering one-click install MUST show the **exact command** and get explicit approval. They SHOULD sandbox the server and warn about `sudo`, `rm -rf` and network access. Servers intended to run locally SHOULD use **stdio**, or restrict HTTP with an auth token or unix domain sockets.
  - Authorization is OPTIONAL. **stdio implementations SHOULD NOT use the OAuth flow** and should read credentials from the environment instead.
  - 2026-07-28 deprecates Roots (pass directories through tool parameters or config instead), Sampling (call the LLM provider directly) and Logging (use stderr or OpenTelemetry).
- **Key quantitative results:** none.
- **Relevance to Omnitrix:**
  - **Complete mediation:** if the 12 FastMCP servers listen on localhost HTTP, any local process, or a DNS-rebinding page, can call them **directly and bypass Guardian**. Run them as **stdio child processes of Guardian**, or on unix sockets or bearer tokens that only Guardian holds.
  - Do not build on MCP Sampling or Roots. Guardian and Operator should call Ollama directly, and the Obsidian vault path belongs in config or tool parameters.

#### [E5] Invariant Labs: Tool Poisoning, Shadowing and Rug Pulls (2025) [V]
- **Citation:**
  - L. Beurer-Kellner and M. Fischer, "MCP Security Notification: Tool Poisoning Attacks", Invariant Labs blog, **1 Apr 2025**. https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks
  - PoC repository: https://github.com/invariantlabs-ai/mcp-injection-experiments
  - "Introducing MCP-Scan" (11 Apr 2025): https://invariantlabs.ai/blog/introducing-mcp-scan ; now `snyk/agent-scan`: https://github.com/snyk/agent-scan
  - Commentary: S. Willison, "Model Context Protocol has prompt injection security problems", 9 Apr 2025. https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/
- **Mechanism:**
  - **Tool poisoning:** hidden instructions in a tool *description*, which the LLM sees and the user does not. The PoC made Cursor read `~/.cursor/mcp.json` and SSH keys.
  - **Shadowing:** a malicious server's description rewrites how the agent uses a *trusted* server's tool. In the PoC, `send_email` was silently redirected to the attacker.
  - **Rug pull:** the description changes after the user approved the server.
  - Recommended mitigations: show the full descriptions, **pin versions and hashes**, and control data flow across servers. MCP-Scan detects changed tools by hashing them ("tool pinning").
- **Key quantitative results:** PoCs only. Note that agent-scan **sends tool names and descriptions to a remote API** for analysis (per its README).
- **Relevance to Omnitrix:** The email-redirection shadowing PoC is exactly Omnitrix's threat. Guardian should:
  - Pin a SHA-256 of each tool's name, description, input schema and annotations at install, and block the tool until a human re-approves it after any change.
  - Reject descriptions that mention other tools or servers.
  - Do all of this **locally**. A remote scanner would break the "nothing leaves the laptop" rule.

#### [E6] MCPTox: tool-poisoning benchmark on real MCP servers (2025) [V; venue V-sec]
- **Citation:** Z. Wang, Y. Gao, Y. Wang, S. Liu, H. Sun, H. Cheng, G. Shi, H. Du, X. Li. "MCPTox: A Benchmark for Tool Poisoning Attack on Real-World MCP Servers." arXiv:2508.14925 (19 Aug 2025). AAAI 2026 per AAAI OJS listing. https://arxiv.org/abs/2508.14925
- **Mechanism:** 45 live MCP servers and 353 real tools. Three attack templates generate 1,312 malicious cases across 10 risk categories. The poisoned metadata only has to be *present* in context; the poisoned tool never needs to be called.
- **Key quantitative results:** o1-mini ASR 72.8%. The paper reports an average ASR of 36.5% across models [V-sec]. Refusal was rare: the highest refusal rate was under 3% (Claude-3.7-Sonnet). The authors note that **more capable models were often more susceptible** because they follow instructions better.
- **Relevance to Omnitrix:** Alignment will not reliably refuse. Tool metadata must be treated as code: pinned, reviewed, and never authored by third parties without review.

#### [E7] Other MCP ecosystem audits (2025–2026) [V]
- **Citations:**
  - B. Radosevich and J. Halloran, "MCP Safety Audit: LLMs with the Model Context Protocol Allow Major Security Exploits", arXiv:2504.03767 (Apr 2025). https://arxiv.org/abs/2504.03767
  - S. Zhao et al., "Parasites in the Toolchain: A Large-Scale Analysis of Attacks on the MCP Ecosystem", arXiv:2509.06572 (v5 May 2026; accepted at IEEE S&P 2026 per arXiv). https://arxiv.org/abs/2509.06572
- **Mechanism:**
  - Radosevich and Halloran coerce LLMs through standard MCP servers into malicious code execution, remote-access control and credential theft, and release the multi-agent McpSafetyScanner.
  - Zhao et al. define "MCP Unintended Privacy Disclosure" in three phases: parasitic ingestion (untrusted content enters), privacy collection, and privacy disclosure. They find exploitable "gadgets" across the ecosystem.
- **Key quantitative results:** Zhao et al. analyse 12,230 tools on 1,360 servers.
- **Relevance to Omnitrix:** "Parasitic ingestion" is Librarian's job description. The ingest → collect → disclose chain is what Guardian's taint rule (checklist row 16) must break.

#### [E8] CASCADE: component ablation of a layered **local** MCP defence (2026) [V]
- **Citation:** İ. Abasıkeleş Turgut, E. Gümüş. "CASCADE: A Component Ablation and Corpus Audit of a Layered Local Defense for MCP-Based Systems." arXiv:2604.17125 (18 Apr 2026; rev. 3 Sep 2026). https://arxiv.org/abs/2604.17125
- **Mechanism:** Structurally almost identical to Omnitrix's S0 → S1 → S2 idea:
  - **L1 (S0):** 93 regexes, 7 de-obfuscation decoders (Base64, ROT13, etc.) and 4 normalized views.
  - **L2 (S1):** `bge-small-en-v1.5` embedding similarity against 565 reference texts, fused into a score. The review threshold is 0.36 and the block threshold 0.49.
  - **Review stage (S2):** local `llama3 8B Q4_0` via Ollama at temperature 0.
  - Outcomes are ALLOW, REVIEW (sent to a human) or BLOCK.
- **Key quantitative results (5,000 samples):**
  - L1 alone: recall 61.05%, FPR 6.05%.
  - L1+L2: recall 94.77%, FPR 11.70%, with **68.5% of all traffic sent to human review**.
  - The LLM reviewer ran on 32.56% of requests at **2.51 s each** and **changed no classification outcome**. A guard condition suppressed its 90 "not malicious" verdicts; it only moved REVIEW items up to BLOCK, which cut human review to 38.6%.
  - Caveats flagged by the authors: 27% exact duplicates, 73% overlap with the embedding reference set, and no held-out evaluation.
- **Relevance to Omnitrix (important cautionary tale):**
  - An embedding stage buys recall **at the cost of human load**. At 68.5% of traffic, humans would rubber-stamp.
  - A small local reviewer was only useful in the **escalate-only** direction.
  - Report denials and referrals separately (1.51% denied versus 11.70% "FPR" once referrals are counted).
  - Log per-sample decision records so thresholds can be recalibrated later.

#### [E9] Execution-layer invariants for MCP-style runtimes (2026) [V]
- **Citation:** T. Liu. "From Tool Connection to Execution Control: Benchmarking Security Invariants in MCP-Style Agent Runtimes." arXiv:2606.29073 (27 Jun 2026). https://arxiv.org/abs/2606.29073
- **Mechanism:** Proposes eight execution-layer invariants: **metadata non-authority**, **grant-backed approval**, canonical resources, principal binding, scoped capability invocation, **source-and-target data-flow authorization**, **deny-path audit** and explicit protocol state. It compares a naive runtime, a "mitigation baseline" (metadata linting, session checks, per-call approvals) and a Handle-Capability Protocol (HCP).
- **Key quantitative results:** On 10 modeled attacks, the naive runtime allowed 10/10, the mitigation baseline 6/10, and HCP 0/10, with sub-millisecond policy latency. This is a single-author paper with a tiny benchmark, so treat it as design guidance rather than evidence.
- **Relevance to Omnitrix:** A good vocabulary for Guardian's slide. Per-call approvals **alone** still let 6/10 attacks through. Approvals must be **bound to grants and data flows**, and **denied calls must be logged too**.

#### 1.x Gateway/proxy pattern: synthesis for Guardian
- **Reference monitor principles** [V]: J. H. Saltzer and M. D. Schroeder, "The Protection of Information in Computer Systems" (SOSP 1973; CACM 17(7) 1974 per the mirror at https://www.cs.virginia.edu/~evans/cs551/saltzer/).
  - **Complete mediation:** every access is checked.
  - **Fail-safe defaults:** decisions are based on permission, not exclusion.
  - **Least privilege.**
  - **Separation of privilege:** two keys beat one.
  - **Psychological acceptability:** protection must be easy enough to apply routinely.
  - All five map directly onto Guardian and Herald.
- **MCP proxies in practice** [V]: mcp-scan's proxy mode injects a local gateway into client configs and applies guardrails (PII, secrets, tool restrictions). The 2026-07-28 spec adds `Mcp-Method`/`Mcp-Name` headers **so gateways and WAFs can route without parsing JSON**. That helps routing only; Guardian must still parse arguments to check them.
- **Omnitrix pattern:** Guardian is the *only* MCP client of the 12 servers. The agents talk to Guardian, never to the servers. Every `tools/call` passes through the same ordered pipeline (S0 → S1 → S2 → H) and writes one audit event, whether it is allowed or denied.

---

## 2. Prompt injection and agent security

#### [E10] Greshake et al. 2023: Indirect Prompt Injection [V]
- **Citation:** K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, M. Fritz. "Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection." arXiv:2302.12173 (Feb 2023). Published at ACM AISec '23 [V-sec]. https://arxiv.org/abs/2302.12173
- **Mechanism:** Retrieved data blurs the line between data and instructions, so an attacker can plant instructions in content the app will retrieve later. No direct access to the victim's interface is needed. The paper gives a threat taxonomy (data theft, worming, information-ecosystem contamination, code execution) and demonstrations on Bing Chat (GPT-4) and code-completion engines.
- **Discrete decision:** none proposed. The authors conclude that the defences of the time were inadequate.
- **Relevance to Omnitrix:** The foundational reference for the PDF-invoice demo. Every email, PDF, note, voice note and news item is an injection vector. Voice notes forwarded by others count as external content.

#### [E11] Willison: Dual LLM pattern (2023) and the Lethal Trifecta (2025) [V]
- **Citations:**
  - S. Willison, "The Dual LLM pattern for building AI assistants that can resist prompt injection", 25 Apr 2023. https://simonwillison.net/2023/Apr/25/dual-llm-pattern/
  - "The lethal trifecta for AI agents: private data, untrusted content, and external communication", 16 Jun 2025. https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- **Mechanism:**
  - **Dual LLM:** a *Privileged* LLM with tools sees only trusted input. A *Quarantined* LLM processes untrusted content and has no tools. A plain-code **Controller** passes symbolic variables (`$VAR1`) between them so raw untrusted text never reaches the privileged side. Only verifiable outputs, such as classifications, may cross.
  - **Lethal trifecta:** private data + untrusted content + the ability to communicate externally. When all three meet, exfiltration is possible. Willison argues that guardrails claiming around 95% detection are not acceptable security.
- **Discrete decision:** the quarantined LLM's *classification* output is explicitly the one kind of output allowed to cross. This is the conceptual root of Omnitrix's "System 1 returns only a choice or boolean".
- **Key quantitative results:** none. Willison calls the dual-LLM pattern imperfect himself: users can be socially engineered into copying data across, and the pattern adds UX cost.
- **Relevance to Omnitrix:** Omnitrix has the trifecta **by design**: it reads external email [untrusted], holds the owner's inbox and calendar [private], and sends email or messages another company's agent [external]. The trifecta therefore has to be broken **per action**, by approval or data-flow rules, because it cannot be broken per system.

#### [E12] Meta, "Agents Rule of Two" (31 Oct 2025) [V]
- **Citation:** Meta AI blog, "Agents Rule of Two: A Practical Approach to AI Agent Security", 31 Oct 2025. https://ai.meta.com/blog/practical-ai-agent-security/
- **Mechanism:** Within one session an agent should have at most two of:
  - [A] processes untrustworthy input
  - [B] accesses sensitive systems or private data
  - [C] changes state or communicates externally

  If all three are needed, require human-in-the-loop approval or another reliable validation. Examples: an email bot [BC] that only handles trusted senders; a travel agent [AB] that needs confirmation before booking.
- **Key quantitative results:** none. Framed as one layer of defence-in-depth.
- **Relevance to Omnitrix:** Split the reply flow into two sessions:
  1. **Draft** session [A+B]: reads the email and inbox; has no send tool.
  2. **Send** session [B+C]: runs only on the **human-approved draft**. Approval endorses the text and makes it trusted.

  Scout should be [A] only: no private data, no send tool. Diplomat receives [A] from the other agent and does [C] only through a fixed schema.

#### [E13] AgentDojo (NeurIPS 2024 Datasets and Benchmarks) [V]
- **Citation:** E. Debenedetti, J. Zhang, M. Balunović, L. Beurer-Kellner, M. Fischer, F. Tramèr. "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents." arXiv:2406.13352 (v3 Nov 2024). https://arxiv.org/abs/2406.13352
- **Mechanism:** 97 realistic tasks (workspace/email/calendar, banking, travel, Slack) and 629 security test cases. It measures utility with and without attacks, and targeted ASR.
- **Discrete decision and rates (GPT-4o, "important_instructions" attack):**

  | Defence | Benign utility | Utility under attack | Targeted ASR |
  |---|---|---|---|
  | None | 69.0% | 50.1% | 57.7% |
  | Delimiting | 72.7% | 55.6% | 41.7% |
  | **PI detector (BERT classifier)** | **41.5%** | 21.1% | 8.0% |
  | Prompt sandwiching | 85.5% | 67.3% | 27.8% |
  | Tool filter | 73.1% | 56.3% | 6.8% |

  The detector was `ProtectAI/deberta-v3-base-prompt-injection-v2`, run on every tool output. It cut ASR but **nearly halved benign utility because of false positives**.
- **Relevance to Omnitrix:** A small classifier that **blocks** on its own verdict destroys usefulness. Use it to **label and route**, not to refuse. A simple deterministic **tool filter** (expose only the tools the task needs) was the most effective cheap defence here, which supports per-task tool allowlists in S0. AgentDojo's email/calendar suite is also the closest public benchmark to Omnitrix, so borrow its scenarios for a local test set.

#### [E14] Spotlighting (Microsoft, 2024) [V]
- **Citation:** K. Hines, G. Lopez, M. Hall, F. Zarfati, Y. Zunger, E. Kiciman. "Defending Against Indirect Prompt Injection Attacks With Spotlighting." arXiv:2403.14720 (Mar 2024). https://arxiv.org/abs/2403.14720
- **Mechanism:** Transform untrusted input so the model receives a continuous signal of where it came from. Three variants: **delimiting**, **datamarking** (interleave a marker token between words) and **encoding** (for example base64).
- **Discrete decision:** none. It is a prompt-side transformation.
- **Key quantitative results:** ASR fell from over 50% to under 2% on the GPT-family models tested, with minimal task impact. **But** adaptive attacks later beat Spotlighting with over 95% ASR (E23).
- **Relevance to Omnitrix:** Cheap S0 hygiene: datamark every untrusted chunk before any model reads it. Treat it as friction, not a boundary.

#### [E15] LlamaFirewall, PromptGuard 2 and AlignmentCheck (Meta, 2025) [V]
- **Citation:** S. Chennabasappa, C. Nikolaidis, D. Song, D. Molnar, S. Ding, S. Wan, S. Whitman, L. Deason, N. Doucette, A. Montilla, A. Gampa, B. de Paola, D. Gabi, J. Crnkovich, J.-C. Testud, K. He, R. Chaturvedi, W. Zhou, J. Saxe. "LlamaFirewall: An open source guardrail system for building secure AI agents." arXiv:2505.03574 (6 May 2025). https://arxiv.org/abs/2505.03574 . Model card: https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M
- **Mechanism:**
  - **PromptGuard 2** is a small encoder classifier (86M mDeBERTa or 22M DeBERTa-xsmall) with benign/malicious output and a 512-token window, so long input must be segmented. The 86M model covers 8 languages **including Hindi**; the 22M model is English-centric.
  - **AlignmentCheck** is an LLM auditor that reads the agent's action trace and asks whether the actions still serve the user's goal (goal-hijack detection).
  - **CodeShield** does static analysis.
- **Discrete decisions and rates:**
  - PG2-86M: **97.5% recall at 1% FPR** on the English jailbreak set. PG2-22M: 88.7% recall at 1% FPR, about 19 ms latency (as extracted from the paper's HTML). PromptGuard 1 managed 21.2%.
  - AgentDojo, baseline ASR 17.6% at 47.7% utility:
    - PG2 alone: 7.5% ASR, 47.0% utility.
    - **AlignmentCheck (Llama 4 Maverick):** 2.89% ASR, 43.1% utility.
    - Combined: **1.75% ASR** (over 90% reduction), 42.7% utility.
  - On an internal goal-hijack set, AlignmentCheck with Maverick reached 83% recall at 2.5% FPR.
  - **AlignmentCheck on small models (Llama 3.2 1B, 3.1 8B) produced more false positives and a large loss of utility.** The authors note that the guard LLM itself can be prompt-injected.
- **Relevance to Omnitrix:**
  - PG2-86M is a realistic local **S1 injection scorer**. It is multilingual including Hindi, but has no Kannada, Tamil or Telugu coverage, and needs chunking.
  - **Intent consistency (AlignmentCheck-style) is an S2 job:** small models failed at it.
  - Even the best combined stack costs about 5 utility points on AgentDojo.

#### [E16] CaMeL: "Defeating Prompt Injections by Design" (Google DeepMind et al., 2025) [V]
- **Citation:** E. Debenedetti, I. Shumailov, T. Fan, J. Hayes, N. Carlini, D. Fabian, C. Kern, C. Shi, A. Terzis, F. Tramèr. arXiv:2503.18813 (v1 24 Mar 2025; v2 24 Jun 2025). https://arxiv.org/abs/2503.18813
- **Mechanism:**
  - A Privileged LLM writes **code** (a restricted Python dialect) from the trusted user query only.
  - A Quarantined LLM, with no tools, parses untrusted data into structured values.
  - A custom interpreter tracks a **data-flow graph with capabilities (provenance)** and checks **security policies before every tool call**. A violation either blocks or **asks the user**.
- **Discrete decision:** policy checks are deterministic (S0). The Q-LLM performs typed extraction.
- **Key quantitative results:**
  - **77% of AgentDojo tasks solved with provable security**, versus 84% undefended.
  - About **2.82× input and 2.73× output tokens** (median).
  - Stated limits: side channels, **user fatigue from approval requests**, and "text-to-text" attacks such as a summary that misstates the email.
- **Relevance to Omnitrix:** The blueprint for Guardian's taint rule and for "approval cards must not rely on an LLM summary". Render cards from the canonical action object (checklist row 21). The token overhead matters on a laptop, so apply CaMeL-style planning only to flows that end in external actions.

#### [E17] Design Patterns for Securing LLM Agents against Prompt Injections (2025) [V]
- **Citation:** L. Beurer-Kellner, B. Buesser, A.-M. Creţu, E. Debenedetti, D. Dobos, D. Fabian, M. Fischer, D. Froelicher, K. Grosse, D. Naeff, E. Ozoani, A. Paverd, F. Tramèr, V. Volhejn. arXiv:2506.08837 (Jun 2025). https://arxiv.org/abs/2506.08837
- **Mechanism:** Six patterns:
  - **Action-Selector:** the LLM only maps a request onto a fixed menu of actions and never sees tool output. Immune to injection, but low flexibility.
  - **Plan-Then-Execute:** the plan is fixed before untrusted data is read. Control flow is protected; arguments can still be manipulated.
  - **LLM Map-Reduce:** isolated per-document sub-agents with constrained aggregation.
  - **Dual LLM.**
  - **Code-Then-Execute:** the CaMeL style.
  - **Context-Minimization:** strip the user prompt or other context before later steps.

  The core principle, paraphrased: once untrusted input has been ingested, it must be impossible for it to trigger consequential actions. Ten case studies are included; the **email and calendar assistant** and the **booking assistant** match Omnitrix.
- **Discrete decision:** Action-Selector is the pattern-level justification for "S1 = choose from a closed set". The paper also says detection classifiers "raise the bar" but remain heuristic.
- **Relevance to Omnitrix:** A menu to pick from:
  - Herald tier selection and Diplomat replies: Action-Selector over fixed enums.
  - Reply workflow: Plan-Then-Execute.
  - Summarising 50 emails: Map-Reduce, one quarantined call per email.
  - Intent checker: Context-Minimization (it sees the user request and the proposed action, not the email body).

#### [E18] FIDES: information-flow control for agents (Microsoft, 2025) [V]
- **Citation:** M. Costa, B. Köpf, A. Kolluri, A. Paverd, M. Russinovich, A. Salem, S. Tople, L. Wutschitz, S. Zanella-Béguelin. "Securing AI Agents with Information-Flow Control." arXiv:2505.23643 (May 2025; rev. Sep 2025). https://arxiv.org/abs/2505.23643 ; code: github.com/microsoft/fides
- **Mechanism:**
  - Every value carries labels: **confidentiality** (the set of readers) and **integrity** (trusted or untrusted). A deterministic policy checks labels at each tool call.
  - **Hide:** a tool result that would taint the planner is stored in a variable instead of shown.
  - **Inspect:** a quarantined LLM answers with **constrained output types**. Low-capacity outputs such as booleans and enums are poor carriers for injection payloads or exfiltration, so they can be endorsed more safely.
- **Key quantitative results (AgentDojo):**
  - With policies, attacks were essentially eliminated: 0 successful, with 1 noted edge case, across 949 attack attempts on gpt-4o. The basic planner without policies allowed 156.
  - FIDES completed up to 16.7% more tasks than a basic planner with o1, and 24% more after prompt tuning.
- **Relevance to Omnitrix:** The **strongest academic backing for the System 1 idea**: small-model outputs restricted to bool, enum or score are safer to pass to the planner **because of their low channel capacity**. The flip side is that an attacker can still **flip** a boolean (E20). Use FIDES-style labels on pgvector chunks: source, reader set and integrity bit.

#### [E19] Progent: programmable privilege control (2025) [V]
- **Citation:** T. Shi, J. He, Z. Wang, H. Li, L. Wu, W. Guo, D. Song. "Progent: Programmable Privilege Control for LLM Agents" (arXiv title currently "Progent: Securing AI Agents with Privilege Control"). arXiv:2504.11703 (Apr 2025; rev. May 2026). https://arxiv.org/abs/2504.11703
- **Mechanism:**
  - A JSON-schema policy language of allow/forbid rules per tool, with **argument conditions** (regex, membership, comparisons). Forbid rules are checked first, and anything unmatched is denied by default. Fallbacks are terminate, ask the user, or return an error.
  - An LLM may propose policy updates. An **SMT solver** decides whether each update **narrows** the policy (applied automatically) or **expands** it (requires approval).
- **Key quantitative results:**
  - AgentDojo ASR 39.9% → **1.0%**. ASB 70.3% → 3.9%. About 1% ASR on LangChain, OpenAI Agents SDK and OpenHands agents, with utility preserved.
  - Manual-approval mode reached 0% ASR on AgentDojo.
  - **Only 6% of updates were expansions** needing approval; 94% were automatic narrowing.
- **Relevance to Omnitrix:** A direct model for Guardian's `check_rules`. Deterministic argument policies plus the principle that **permissions may narrow automatically and only widen with a human**. The 6% figure suggests the approval load can stay small if tasks start narrow.

#### [E20] Type-directed privilege separation (2025/2026) [V]
- **Citation:** D. Jacob, E. Alghamdi, Z. Hu, B. Alomair, D. Wagner. "Preventing Prompt Injection with Type-Directed Privilege Separation." arXiv:2509.25926 (Sep 2025; rev. 8 May 2026). https://arxiv.org/abs/2509.25926
- **Mechanism:** The quarantined agent may hand back **only** ints, floats, booleans or enums drawn from a vetted finite set. Strings are disallowed. Such values cannot encode an instruction.
- **Key quantitative results (ASR undefended → defended; utility):**
  - Online shopping (GPT-4o): 31.7% → **0.0%**; utility 21.8% → 22.4%.
  - Calendar scheduling (GPT-4o): 63.0% → **0.0%**; utility 90.0% → 91.0%.
  - Bug fixing (GPT-5.2): 98.9% → **0.0%**; utility 68.3% → 45.0%.
  - Stated residual risk: the attacker can still **mislead** by steering *which* value comes back.
- **Relevance to Omnitrix:** Precise backing for "System 1 answers are choices, booleans and scores". It also shows why such answers are **safe to pass along but not safe to trust as the final allow decision**: typing blocks instruction smuggling, not decision manipulation. The calendar case study, with no utility loss, fits Omnitrix's meeting-booking flow.

#### [E21] Intent- and alignment-checking defences: Task Shield (ACL 2025), MELON (ICML 2025), PromptArmor (2025) [V]
- **Citations:**
  - F. Jia, T. Wu, X. Qin, A. Squicciarini, "The Task Shield: Enforcing Task Alignment to Defend Against Indirect Prompt Injection in LLM Agents", ACL 2025. https://aclanthology.org/2025.acl-long.1435/
  - K. Zhu, X. Yang, J. Wang, W. Guo, W. Wang, "MELON: Provable Defense Against Indirect Prompt Injection Attacks in AI Agents", ICML 2025 (PMLR 267). https://arxiv.org/abs/2502.05174
  - T. Shi et al., "PromptArmor: Simple yet Effective Prompt Injection Defenses", arXiv:2507.15219 (Jul 2025). https://arxiv.org/abs/2507.15219
- **Mechanism:**
  - Task Shield checks whether each instruction or tool call **contributes to the user's stated goals**.
  - MELON re-runs the trajectory with the user prompt **masked**. If the agent still takes the same action, the action is driven by the injected content.
  - PromptArmor asks an off-the-shelf **large** LLM to detect injected text and remove it before the agent sees it.
- **Discrete decisions and rates:**
  - Task Shield (GPT-4o, AgentDojo): ASR **2.07%**, utility 69.79%.
  - PromptArmor with GPT-4o, GPT-4.1 or o4-mini: **FPR and FNR both under 1%** on AgentDojo, ASR under 1% after removal. No small-model results are reported.
- **Relevance to Omnitrix:** The "is this action consistent with what the user asked?" check works **with frontier-class models**. With Qwen3-14B it is plausible for S2. There is no evidence that a 1.7B/4B model can do it, and LlamaFirewall reports that 1B/8B models fail. MELON's "masked re-run" is a neat S2 demo for the hidden-text invoice: rerun without the user's request and show that the "forward bank details" action persists.

#### [E22] Over-defence in small guard classifiers: InjecGuard / NotInject (2024–2025) [V]
- **Citation:** H. Li, X. Liu. "InjecGuard: Benchmarking and Mitigating Over-defense in Prompt Injection Guardrail Models." arXiv:2410.22770 (Oct 2024; rev. Mar 2025). https://arxiv.org/abs/2410.22770
- **Mechanism:** The NotInject set contains 339 **benign** samples full of words that commonly appear in injections ("ignore", "override", "urgent"...). Existing guard models flag them. The proposed "MOF" training reduces trigger-word bias.
- **Key quantitative results:** Existing guards fall to about **60% accuracy, near random**, on NotInject. InjecGuard beats the best previous model by 30.8% on it.
- **Relevance to Omnitrix:** Indian business email is full of "urgent", "kindly ignore previous mail", "transfer today", often in Hinglish. Expect **high false-positive rates** from off-the-shelf S1 detectors. Calibrate on a **local, domain-specific** benign set, and keep S1 escalate-only so a false positive costs an approval, not a lost email.

#### [E23] "The Attacker Moves Second": adaptive attacks break 12 defences (2025) [V; venue V-sec]
- **Citation:** M. Nasr, N. Carlini, C. Sitawarin, S. V. Schulhoff, J. Hayes, M. Ilie, J. Pluto, S. Song, H. Chaudhari, I. Shumailov, A. Thakurta, K. Y. Xiao, A. Terzis, F. Tramèr. arXiv:2510.09023 (10 Oct 2025). Listed at USENIX Security 2026. https://arxiv.org/abs/2510.09023
- **Mechanism:** Adaptive attacks using gradient, RL, search and human red-teaming, run against 12 published jailbreak and prompt-injection defences that had reported near-zero ASR.
- **Key quantitative results:**
  - **Detectors:** PromptGuard over 90% ASR, ProtectAI detector over 90%, PIGuard 71%, Model Armor over 90%.
  - **Prompting defences:** Spotlighting over 95%, Prompt Sandwiching over 95%, RPO 96–98%.
  - **Training defences:** MetaSecAlign 96% (originally reported 2%), Circuit Breakers 100%.
  - **Secret-knowledge defences:** MELON 76–95%, Data Sentinel over 80%.
  - Human red-teamers defeated every challenge.
- **Relevance to Omnitrix:** **The main reason a small classifier must never be the final word on "is this safe?".** A classifier that is 97.5% accurate on static data can fall below 10% under an adaptive attacker. Security has to come from S0 structure (labels, allowlists, approval binding) and the human. S1 is triage.

#### [E24] Notable 2026 work [V]
- **E24a.** S. Abdelnabi, E. Bagdasarian, "AI Agents May Always Fall for Prompt Injections", arXiv:2605.17634 (17 May 2026). https://arxiv.org/abs/2605.17634
  - An impossibility-style argument through **Contextual Integrity**. An adversary can always construct a context in which a blocked flow looks legitimate, and tightening the norms blocks legitimate flows.
  - Relevance: this is exactly the look-alike-vendor, ₹4.8 L case. A plausible context defeats content judgement, so **identity verification (S0) plus a human** must decide.
- **E24b.** P. Narisetty et al., "Adaptive Evaluation of Out-of-Band Defenses Against Prompt Injection in LLM Agents", arXiv:2606.26479 (25 Jun 2026). https://arxiv.org/abs/2606.26479
  - Independent re-test of Progent with **Qwen2.5-7B** on AgentDojo: ASR about 25.8% → 4.2%, and a hand-crafted adaptive attack reached only 2.6%. The authors call this one small data point.
  - Relevance: tentative support that **deterministic enforcement outside the model holds up better under adaptive attack than detection**, even with a small local model.
- **E24c. Hidden-text and invisible-Unicode injection**, directly relevant to the white 3-pt text demo:
  - Z. Lin, "Hidden Prompts in Manuscripts Exploit AI-Assisted Peer Review", arXiv:2507.06185 (Jul 2025; rev. Aug 2026). https://arxiv.org/abs/2507.06185 . Found 18 arXiv manuscripts with instructions hidden by **white text and microscopic font**, in four prompt types.
  - Microsoft Security Blog (N. Kochavi, S. Wolstencroft), "ASCII smuggling crosses over from AI prompt injection to phishing evasion", 3 Sep 2026. https://www.microsoft.com/en-us/security/blog/2026/09/03/ascii-smuggling-crosses-over-from-ai-prompt-injection-to-phishing-evasion/ . Unicode tag characters (U+E0000–E007F) were used to split finance keywords in phishing mail. The campaign ran from 9 Feb 2026 with a peak above 2.3M messages per day across about 148 finance-themed domains. Recommended fixes: **strip tag characters before analysis, and treat their mere presence as anomalous.**
  - M. Graves, "Reverse CAPTCHA: Evaluating LLM Susceptibility to Invisible Unicode Instruction Injection", arXiv:2603.00164 (Feb 2026). https://arxiv.org/abs/2603.00164 . Across 8,308 outputs, **tool access increased compliance**, and decoding hints increased it by up to 95 percentage points.
  - Relevance: hidden-text detection is **pure S0**. Check PDF render mode, fill colour against background, font size, clipping and Unicode code-point classes. Do not hand this job to a model.

#### [E25] Deterministic anti-spoofing primitives (for detect_trick) [V]
- **E25a.** T. Herr, J. Levine (eds.), **RFC 9989**, "Domain-Based Message Authentication, Reporting, and Conformance (DMARC)", **May 2026**, Proposed Standard. It obsoletes RFC 7489 and RFC 9091. https://datatracker.ietf.org/doc/rfc9989/
  - The RFC5322.From domain must **align** with an SPF- or DKIM-authenticated domain. Domain owners publish none, quarantine or reject policies. A DNS tree walk replaces the Public Suffix List.
- **E25b.** Unicode Technical Standard #39, **Unicode Security Mechanisms**, v18.0.0 (2026-08-27). https://www.unicode.org/reports/tr39/
  - Two strings are confusable if `skeleton(X) == skeleton(Y)`. The standard also defines mixed-script and whole-script confusables and identifier restriction levels.
- **Relevance to Omnitrix:** "Is this sender spoofed?" is mostly **S0**:
  - Read the `Authentication-Results` header (SPF/DKIM/DMARC alignment).
  - Compare the UTS-39 skeleton against the known-contacts and vendor registry, add an edit-distance check, and flag Punycode or mixed-script domains and first-seen domains.
  - S1 may *rank* near-misses for display, but a model can never *clear* a DMARC failure or a skeleton collision.

**Summary: where discrete classifier decisions appear in the literature, and what they cost**
| Work | Discrete decision | Reported detection | False positives / utility cost | Robust to adaptive attack? |
|---|---|---|---|---|
| AgentDojo PI detector (DeBERTa) | inject? on each tool output | ASR 57.7% → 8.0% | Benign utility 69% → **41.5%** | No (E23) |
| PromptGuard 2 86M | benign/malicious | 97.5% recall at 1% FPR (static) | AgentDojo utility 47.7% → 47.0% | **No (>90% ASR, E23)** |
| AlignmentCheck (large LLM) | goal-hijack? on the trace | 83% recall at 2.5% FPR (Maverick) | Utility −4.6 pts; **small models: high FP** | Guard can itself be injected |
| Task Shield (GPT-4o) | does the call serve the user goal? | ASR 2.07% | Utility 69.8% | Not reported |
| PromptArmor (GPT-4o-class) | inject? plus removal | FNR < 1% | FPR < 1% | Paper claims some robustness |
| CASCADE embedding stage | score → allow/review/block | Recall 94.8% | FPR 11.7%; **68.5% of traffic to human** | Not held out |
| Claude Code auto mode (E32) | block? on each action | Stage 1 FNR 6.6%; full pipeline FNR 17% | Stage 1 FPR 8.5%; full pipeline **0.4%** | Tool results hidden from classifier |
| FIDES / type-directed | typed quarantined output | ~0 successful attacks | Small utility cost | Structural, so yes for injection; not for misinformation |

---

## 3. Human-in-the-loop approvals and risk

#### [E26] ToolEmu: LM-emulated sandbox and LM-based safety evaluator (ICLR 2024) [V]
- **Citation:** Y. Ruan, H. Dong, A. Wang, S. Pitis, Y. Zhou, J. Ba, Y. Dubois, C. J. Maddison, T. Hashimoto. "Identifying the Risks of LM Agents with an LM-Emulated Sandbox." ICLR 2024. https://arxiv.org/abs/2309.15817 ; https://proceedings.iclr.cc/paper_files/paper/2024/hash/7274ed909a312d4d869cc328ad1c5f04-Abstract-Conference.html
- **Mechanism:** An LM emulates tool execution, and an adversarial emulator stress-tests agents. An **LM safety evaluator** rates likelihood (certain / possible / likely) against severity (mild / severe) on a 0–3 scale, then binarizes: "certain no risk" and "possible mild" count as safe; likely-mild, possible-severe and likely-severe count as unsafe.
- **Key quantitative results:**
  - 36 high-stakes toolkits and 144 test cases.
  - **68.8%** of flagged failures were valid real failures (adversarial emulator).
  - The safest agent failed **23.9%** of the time.
  - Evaluator–human agreement: Cohen's κ **0.478**, versus 0.480 between human annotators.
- **Relevance to Omnitrix:** The **likelihood × severity** grid is a ready-made risk-tier rubric for Herald (checklist row 20). Compute severity from S0 action metadata and likelihood from labels and S1 flags. Note that even human raters agree only moderately (κ ≈ 0.48) on risk, a reminder that "risk" is not crisply learnable.

#### [E27] R-Judge: LLM safety-risk awareness in agent trajectories (EMNLP Findings 2024) [V]
- **Citation:** T. Yuan, Z. He, L. Dong, Y. Wang, R. Zhao, T. Xia, L. Xu, B. Zhou, F. Li, Z. Zhang, R. Wang, G. Liu. "R-Judge: Benchmarking Safety Risk Awareness for LLM Agents." EMNLP Findings 2024. https://arxiv.org/abs/2401.10019
- **Mechanism:** 569 multi-turn agent records across 27 scenarios, 5 application categories and 10 risk types (privacy leakage, computer security, financial loss, data loss...). The model must judge whether the trajectory is safe.
- **Key quantitative results:**
  - Best model GPT-4o: 74.42%. **"No other models significantly exceed the random"** baseline.
  - As extracted from the tables: Llama-2-7B/13B about 54% F1; Vicuna 7B/13B about 18–30%; Mistral-7B about 25–27%.
  - Plain prompting did not help. **Safety fine-tuning did**: Llama-Guard-2-8B beat GPT-4o with higher specificity in one setting.
- **Relevance to Omnitrix:** Prompted small models are **near chance at holistic risk judgement**, so "is this action risky?" must not be an S1 call. The exception is a *narrow, fine-tuned* guard, but a hackathon will not have time to fine-tune and validate one.

#### [E28] Levels of Autonomy for AI Agents (Feng, McDonald, Zhang 2025) [V]
- **Citation:** K. J. K. Feng, D. W. McDonald, A. X. Zhang. "Levels of Autonomy for AI Agents." arXiv:2506.12469 (Jun 2025; rev. Jul 2025). Knight First Amendment Institute. https://arxiv.org/abs/2506.12469
- **Mechanism:** Autonomy is a design choice, defined by the **user's role**: L1 operator, L2 collaborator, L3 consultant, L4 **approver**, L5 observer. At L4 the agent involves the user only for blockers, which include **signing off on consequential actions** and supplying credentials. At L5 the user can only watch logs and hit an emergency off-switch. The paper also proposes "autonomy certificates".
- **Key quantitative results:** none. It explicitly raises the risk of **meaningless rubber-stamping** at L4, and notes that misaligned agents could gradually talk disengaged users into approving risky actions.
- **Relevance to Omnitrix:** Omnitrix should present itself as an **L4 agent with per-action-class levels**: L4 for external or financial actions, L5-with-audit for reads and internal notes. The rubber-stamping warning justifies Herald's interrupt budget.

#### [E29] Warning habituation: Anderson et al. (JMIS 2016); Vance et al. (MISQ 2018) [V]
- **Citations:**
  - B. B. Anderson, A. Vance, C. B. Kirwan, J. L. Jenkins, D. Eargle, "From Warning to Wallpaper: Why the Brain Habituates to Security Warnings and What Can Be Done About It", *J. Management Information Systems* 33(3):713–743, 2016. https://www.tandfonline.com/doi/abs/10.1080/07421222.2016.1243947
  - A. Vance, J. L. Jenkins, B. B. Anderson, D. K. Bjornn, C. B. Kirwan, "Tuning Out Security Warnings: A Longitudinal Examination of Habituation Through fMRI, Eye Tracking, and Field Experiments", *MIS Quarterly* 42(2):355–380, 2018. https://aisel.aisnet.org/misq/vol42/iss2/3/
- **Mechanism:** fMRI and eye tracking show neural **repetition suppression**: attention to a repeated warning declines. **Polymorphic** warnings, whose appearance changes each time, resist this.
- **Key quantitative results:** Attention declines over a five-day workweek and partly recovers between days. In a three-week field study of app-permission warnings, adherence with polymorphic warnings dropped much more slowly and stayed high, while static warnings saw large drops. The source reports this qualitatively; it gives no percentages in the abstract.
- **Relevance to Omnitrix:** A watch buzz with the same layout 30 times a day becomes wallpaper. Vary the high-risk (T3) card appearance, keep low-risk items out of the buzz channel entirely, and use daily digests for them.

#### [E30] Pop-up fatigue and in-the-wild click-through [V]
- **Citations:**
  - C. Bravo-Lillo, L. Cranor, S. Komanduri, S. Schechter, M. Sleeper, "Harder to Ignore? Revisiting Pop-Up Fatigue and Approaches to Prevent It", SOUPS 2014. https://www.usenix.org/conference/soups2014/proceedings/presentation/bravo-lillo
  - D. Akhawe, A. P. Felt, "Alice in Warningland: A Large-Scale Field Study of Browser Security Warning Effectiveness", USENIX Security 2013. https://www.usenix.org/conference/usenixsecurity13/technical-sessions/presentation/akhawe
- **Mechanism:** Bravo-Lillo et al. habituated participants to a dialog and then changed one field. They tested "attractors" meant to draw attention to it. Akhawe and Felt measured click-through on more than 25M real browser warnings.
- **Key quantitative results:**
  - Bravo-Lillo: habituation reduced noticing for most attractors. **Attractors that forced users to interact with the changed field did not lose effectiveness as habituation increased.**
  - Akhawe and Felt: users clicked through about 10% of Firefox malware/phishing warnings, about 25% of Chrome's, about 33% of Firefox SSL warnings, and **70.2% of Chrome SSL warnings**. Design strongly affects outcomes, and warnings *can* work.
- **Relevance to Omnitrix:** For high-risk (T3) approvals such as a payment instruction or a new external recipient, **make the user interact with the critical field**: pick the correct payee from three options, or confirm the last four digits of the amount or account. A single "Approve" tap is not enough. Tapping on a watch is the lowest-attention channel, so reserve it for T1/T2.

#### [E31] Push-approval fatigue and transaction binding: CISA (2022) and RBI (2025) [V]
- **Citations:**
  - CISA, "Implementing Number Matching in MFA Applications" (fact sheet, Oct 2022). https://www.cisa.gov/sites/default/files/publications/fact-sheet-implement-number-matching-in-mfa-applications-508c.pdf ; alert 31 Oct 2022: https://www.cisa.gov/news-events/alerts/2022/10/31/cisa-releases-guidance-phishing-resistant-and-numbers-matching-multifactor-authentication
  - Reserve Bank of India, "Reserve Bank of India (Authentication mechanisms for digital payment transactions) Directions, 2025", 25 Sep 2025, effective 1 Apr 2026. https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12898&Mode=0
- **Mechanism:**
  - **MFA fatigue / push-bombing:** an attacker floods the user with approval prompts until one is accepted by accident or annoyance. **Number matching** forces the user to enter a code shown on the requesting screen, which kills blind approvals and prompt spam. CISA also recommends investigating denied pushes and bulk prompts.
  - RBI requires at least one authentication factor to be **dynamically created or proven, unique to that transaction**, and allows extra risk-based checks (location, behaviour, device, history).
- **Key quantitative results:** none (guidance and regulation).
- **Relevance to Omnitrix:** A prompt-injected agent can **push-bomb its own owner** through Herald. Guardian therefore needs:
  - approval-request rate limits, with a lockdown on bursts;
  - an approval token **bound to the action hash** (recipient, amount, payee, body hash), so that any change invalidates it;
  - for T3, a number or field-match step between laptop and phone.

  The RBI's "unique to the transaction" wording is a handy India-specific justification to cite to judges.

#### [E32] How production agents gate actions (brief) [V]
- **Claude Code** docs (https://code.claude.com/docs/en/permissions ; https://code.claude.com/docs/en/permission-modes) and Anthropic Engineering, "Claude Code auto mode" (J. Hughes et al., **25 Mar 2026**, https://www.anthropic.com/engineering/claude-code-auto-mode):
  - **Rule precedence:** deny, then ask, then allow; a broad deny beats any allow. Hooks cannot override deny rules. Read-only tools run without a prompt.
  - **Auto mode:** a separate classifier model reviews actions. It **sees user messages and tool calls, but tool results are stripped**, so hostile content cannot address it. A separate probe scans incoming tool results.
  - **Two stages:** stage 1 is a single-token yes/no tuned to over-block; stage 2 is chain-of-thought and runs only on stage-1 flags.
  - Results: real-traffic FPR 8.5% at stage 1 → **0.4%** for the full pipeline (n = 10,000). But on real overeager actions (n = 52), FNR was **6.6% at stage 1 → 17% for the full pipeline**, and on synthetic exfiltration (n = 1,000) 1.8% → 5.7%.
  - **Users approved 93% of permission prompts.**
  - Fallbacks: after **3 consecutive or 20 total blocks**, the session reverts to human prompts. **No verdict means deny.** Boundaries the user states in conversation ("don't push") count as block signals, but they can be lost on context compaction, so the docs recommend a deny rule for hard guarantees. An approval has to name the specific action.
- **LangGraph interrupts** (https://docs.langchain.com/oss/python/langgraph/interrupts): `interrupt()` plus a checkpointer plus `Command(resume=…)`. Code in a node before the interrupt **re-runs on resume**, so side effects must be idempotent.
- **OpenAI Agents SDK** (https://openai.github.io/openai-agents-python/guardrails/ ; …/human_in_the_loop/):
  - Guardrails: input, output and **tool** guardrails, each with **tripwires**. They can run blocking or in parallel, and the docs suggest a **fast/cheap model** for guardrails.
  - Human-in-the-loop: tools declare `needs_approval` (a bool or a callable). A paused `RunState` is serializable and can be resumed with `approve`/`reject`. Decisions can be made sticky with `always_approve`/`always_reject`.
- **Relevance to Omnitrix:**
  - The Anthropic numbers are the best public evidence on **S1 → S2 cascades**: escalating to deliberation cuts false positives about 20× **but almost triples misses**. Omnitrix should never let S2 *downgrade* a deterministic requirement.
  - "Strip untrusted tool results from the checker's context" is directly reusable for the intent-consistency check.
  - The 93% approval rate is the fatigue baseline to beat.
  - Fail closed when there is no verdict.

#### [E33] AirGapAgent: data minimization against context hijacking (CCS 2024) [V]
- **Citation:** E. Bagdasarian, R. Yi, S. Ghalebikesabi, P. Kairouz, M. Gruteser, S. Oh, B. Balle, D. Ramage. "AirGapAgent: Protecting Privacy-Conscious Conversational Agents." ACM CCS 2024. https://arxiv.org/abs/2405.05175
- **Mechanism:** A third party manipulates the conversation context so an agent reveals private data unrelated to the task. The defence gives the agent **only the data the task needs**, following contextual integrity.
- **Key quantitative results:** A single-query context-hijacking attack cut Gemini Ultra's data protection from **94% to 45%**. AirGapAgent kept **97%**.
- **Relevance to Omnitrix:** The design pattern for **Diplomat**. Negotiate from a projection containing only free/busy windows, created *before* talking to the other company's agent. The negotiating model then never holds meeting titles, attendees or notes, so it cannot be tricked into leaking them. This is S0 schema whitelisting, not a model decision.

(Also consulted: OWASP GenAI Security Project, "OWASP Top 10 for Agentic Applications for 2026", published 9 Dec 2025 [V]: https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/ . It lists ASI01 Agent Goal Hijack, ASI02 Tool Misuse, ASI03 Identity & Privilege Abuse, ASI04 Agentic Supply Chain, ASI05 Unexpected Code Execution, ASI06 Memory & Context Poisoning, ASI07 Insecure Inter-Agent Communication, ASI08 Cascading Failures, **ASI09 Human-Agent Trust Exploitation**, and ASI10 Rogue Agents. This makes a good judge-facing risk taxonomy: map each demo to an ASI id.)

---

## 4. Audit, provenance and undo

#### [E34] Forward-secure and tamper-evident logs: Schneier and Kelsey (1999); Crosby and Wallach (2009) [V]
- **Citations:**
  - B. Schneier, J. Kelsey, "Secure Audit Logs to Support Computer Forensics", *ACM TISSEC*, 1999. https://www.schneier.com/academic/archives/1999/05/secure_audit_logs_to.html (volume and issue numbering: see Unverified).
  - S. A. Crosby, D. S. Wallach, "Efficient Data Structures for Tamper-Evident Logging", USENIX Security 2009, pp. 317–334. https://www.usenix.org/conference/usenixsecurity09/technical-sessions/presentation/efficient-data-structures-tamper-evident
- **Mechanism:**
  - Schneier and Kelsey: evolving keys and hash chains make entries written *before* a compromise unreadable to the attacker and impossible to alter or delete undetectably.
  - Crosby and Wallach: an **untrusted logger** is kept honest by **auditors**. A Merkle-tree "history tree" gives **logarithmic-size** membership and consistency proofs, where hash chains need linear-size proofs, and supports agreed deletion of old events.
- **Key quantitative results:** logarithmic proof size (from the abstract). Throughput numbers were not captured.
- **Relevance to Omnitrix:** In Omnitrix the "untrusted logger" is the agent stack itself: a compromised agent process could rewrite Postgres. Guardian should write an **append-only hash-chained** event table. Periodically publish the chain head **somewhere the agents cannot write**, such as the owner's phone through ntfy or the daily digest. A verifier (auditor) then recomputes the chain. That makes a strong live demo: tamper with a row and watch the red badge appear.

#### [E35] Certificate Transparency: RFC 6962 (2013) → RFC 9162 (2021) [V]
- **Citation:** B. Laurie, A. Langley, E. Kasper, **RFC 6962** "Certificate Transparency", Jun 2013 (Experimental), https://www.rfc-editor.org/rfc/rfc6962 . Obsoleted by B. Laurie, E. Messeri, R. Stradling, **RFC 9162** "Certificate Transparency Version 2.0", 2021 (Experimental), https://www.rfc-editor.org/rfc/rfc9162
- **Mechanism:** An append-only Merkle log with **inclusion (audit) proofs**, **consistency proofs** (the new tree extends the old one) and **Signed Tree Heads**. Monitors and auditors compare tree heads to catch a log that shows different views to different clients.
- **Relevance to Omnitrix:** Use the same data structure at laptop scale. Every N events, Guardian emits a signed tree head (an ed25519 key held by Guardian only), keeps a copy locally and pushes one to the phone. Inclusion proofs let the "why did this happen?" UI prove a specific approval was in the log. Apple PCC (E41) applies the same transparency-log idea to software images.

#### [E36] Event sourcing, sagas and compensation for agents [V]
- **Citations:**
  - M. Fowler, "Event Sourcing", 12 Dec 2005. https://martinfowler.com/eaaDev/EventSourcing.html
  - H. Garcia-Molina, K. Salem, "Sagas", ACM SIGMOD 1987, pp. 249–259. https://dl.acm.org/doi/10.1145/38713.38742
  - S. Perera, K. Hapuarachchi, F. Leymann, R. Khalaf, "Robust Agent Compensation (RAC): Teaching AI Agents to Compensate", arXiv:2605.03409 (May 2026). https://arxiv.org/abs/2605.03409
  - Google, Gmail Help "Unsend an email". https://support.google.com/mail/answer/2819488
- **Mechanism:**
  - Event sourcing stores every change as an event, which allows full rebuilds, temporal queries and reversal events. Fowler warns that **external systems must sit behind gateways**, so that replaying events does not resend email.
  - A saga is a sequence of local steps, each with a **compensating** step that undoes it *semantically* rather than restoring the exact prior state.
  - RAC adds logging-based compensation to LangGraph/LangChain agents.
  - Gmail's "Undo Send" holds outgoing mail for a configurable **5, 10, 20 or 30 s**.
- **Key quantitative results:** RAC is 1.5–8× better on latency and token economy than LLM-based recovery on τ-bench and REALM-Bench. RAC **cannot compensate irreversible actions such as a sent email.**
- **Relevance to Omnitrix:**
  - Each Operator tool declares a compensator and an `irreversible` flag: `book_meeting` ↔ `cancel_meeting`; `create_task` ↔ `delete_task`; an Obsidian write ↔ revert, via a git-versioned vault; `send_email` has **no compensator**.
  - Irreversible means a higher approval tier plus an **outbox delay**, a Gmail-style undo window before Mailpit or SMTP release.
  - Put a gateway around external side effects so audit replay never re-executes them.
  - Idempotency keys cover LangGraph re-execution and MCP 2026 MRTR retries.

#### [E37] Agent-specific audit trails (2026) [V]
- **Citations:**
  - L. Bindschaedler, Q. Botha, C. Siebenbrunner, "Agent Flight Recorder: Tamper-Evident Audit Trails with On-Chain Anchoring for Long-Horizon Tool-Using Agents", arXiv:2609.01931 (1 Sep 2026; accepted at IEEE BCCA 2026 per arXiv). https://arxiv.org/abs/2609.01931
  - Microsoft Agent Governance Toolkit, Tutorial 04, "Audit & Compliance". https://microsoft.github.io/agent-governance-toolkit/tutorials/04-audit-and-compliance/
- **Mechanism:**
  - The Flight Recorder records each agent action as a canonically serialized event with **eight semantic fields, from intent through execution to provenance**. The abstract does not list the eight. Events are hash-chained, Merkle-batched and optionally anchored on a public chain.
  - Microsoft's toolkit keeps a Merkle-chained log with per-entry fields: agent id, action (allow / deny / audit / quarantine), resource, event type, outcome, policy decision, trace and session ids, timestamp and hash. It writes HMAC-signed JSONL.
- **Key quantitative results:** The Flight Recorder adds about **48 µs median per event** and **512 bytes per event**, and detected edit, delete, reorder and fork tampering at 100% with no false positives in its evaluation.
- **Relevance to Omnitrix:**
  - The overhead is negligible, so logging *every* model and tool call is affordable.
  - Use the toolkit's field list as a schema starter. Add for Omnitrix: the **System level that decided (0/1/2/H)**, the score and threshold, the model digest, the tool-definition hash and the approval-token id.
  - On-chain anchoring is unnecessary and **anti-sovereign** for a single owner. Anchor to the owner's phone instead.

#### [E38] Append-only logs versus the right to erasure: EDPB Guidelines 02/2025 [V]
- **Citation:** European Data Protection Board, "Guidelines 02/2025 on processing of personal data through blockchain technologies", adopted 8 Apr 2025 (news 14 Apr 2025). https://www.edpb.europa.eu/news/news/2025/edpb-adopts-guidelines-processing-personal-data-through-blockchains-and-ready_en
- **Mechanism:** Avoid storing personal data in immutable ledgers when that conflicts with data-protection principles. Keep personal data **off-chain**, with only hashes or references in the ledger, so erasure and rectification stay possible.
- **Relevance to Omnitrix (by analogy; this is EU guidance):** The same tension arises under DPDP (E42), which gives rights to erasure and requires logs. Keep the hash chain over **salted commitments and metadata**, and put payloads (email text, amounts, names) in an encrypted side table. Erasure deletes the payload or its per-record key (crypto-shredding) while the chain still verifies.

---

## 5. Sovereignty and privacy

#### [E39] Local-first software (2019) and "File over app" (2023) [V]
- **Citations:**
  - M. Kleppmann, A. Wiggins, P. van Hardenberg, M. McGranaghan, "Local-first software: you own your data, in spite of the cloud", Onward! 2019. https://www.inkandswitch.com/essay/local-first/
  - S. Ango, "File over app", 1 Jul 2023. https://stephango.com/file-over-app
- **Mechanism:** The seven local-first ideals are no spinners, multi-device, network optional, seamless collaboration, the long now (longevity), security and privacy by default, and ultimate ownership and control. CRDTs are presented as the enabling technology. "File over app" argues that durable, open files outlive the apps that made them.
- **Relevance to Omnitrix:**
  - Obsidian Markdown files are the durable, human-readable record of knowledge.
  - The audit log should be exportable as **JSONL plus its tree heads**, verifiable without Omnitrix running.
  - Score the product against the seven ideals on a slide. Multi-device (watch and phone) is met through self-hosted ntfy. "Collaboration" is Diplomat, with minimization.

#### [E40] Local↔cloud collaboration that keeps data local, as a contrast: Minions (ICML 2025), PAPILLON (NAACL 2025) [V]
- **Citations:**
  - A. Narayan, D. Biderman, S. Eyuboglu, A. May, S. Linderman, J. Zou, C. Ré, "Minions: Cost-efficient Collaboration Between On-device and Cloud Language Models", ICML 2025 (PMLR 267:45682–45719). https://arxiv.org/abs/2502.15964
  - Li Siyan, V. C. Raghuram, O. Khattab, J. Hirschberg, Z. Yu, "PAPILLON: Privacy Preservation from Internet-based and Local Language Model Ensembles", NAACL 2025. https://arxiv.org/abs/2410.17127
- **Mechanism:** A small local model holds the private context. A cloud model is consulted through decomposed subtasks (Minions) or privacy-conscious rewritten prompts (PAPILLON).
- **Key quantitative results:**
  - MinionS: **5.7× lower cost** and **97.9%** of cloud-only quality. The simpler Minion protocol: 30.4× lower cost and 87% quality.
  - PAPILLON: high quality on **85.5%** of queries with **7.5%** privacy leakage (PUPA benchmark).
- **Relevance to Omnitrix:** Useful as the **"why not hybrid?" answer** to judges. Even well-designed delegation leaks something (7.5% in PAPILLON), and Track 1 asks for ownership. Omnitrix's claim is **zero cloud calls**. If they ever add an opt-in cloud helper, Minions-style decomposition behind Guardian's egress rule is the pattern, but it breaks the sovereignty pitch.

#### [E41] Apple Private Cloud Compute (10 Jun 2024), an industry pattern [V]
- **Citation:** Apple Security Engineering and Architecture, "Private Cloud Compute: A new frontier for AI privacy in the cloud", 10 Jun 2024. https://security.apple.com/blog/private-cloud-compute/
- **Mechanism:** Five requirements: **stateless computation** on personal data, **enforceable guarantees**, **no privileged runtime access** (no remote shells), **non-targetability**, and **verifiable transparency**. Production software images are published to an append-only transparency log, and devices send data only to nodes that attest to logged images.
- **Relevance to Omnitrix:** Borrow the vocabulary for the pitch. "Enforceable, not policy" is Guardian's S0-first rule. "Verifiable transparency" becomes pinning and logging the model digests (Ollama) and tool hashes, so a judge can verify what ran. "No privileged runtime access" means no debug path around Guardian.

#### [E42] India: Digital Personal Data Protection Act 2023 and DPDP Rules 2025 (status as of Sep 2026) [V]
- **Citations:**
  - Digital Personal Data Protection Act, 2023 (No. 22 of 2023), assented 11 Aug 2023. MeitY PDF: https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf . The direct fetch was blocked (403); s.3 text was verified through a reproduction.
  - **DPDP Rules, 2025, G.S.R. 846(E)**, Gazette dated **13 Nov 2025**. Text verified from a gazette copy: https://www.dpdpa.com/DPDP_Rules_2025_English_only.pdf
  - PIB explainer, 17 Nov 2025 (it says the Rules were notified on 14 Nov 2025): https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf
- **Key facts [V]:**
  - **Commencement (Rule 1):** Rules 1, 2 and 17–21 came into force on publication. **Rule 4** (Consent Managers) comes into force **one year later, about 13 Nov 2026**. **Rules 3, 5–16, 22 and 23** come into force **18 months later, about 13 May 2027**. These include notice, **security safeguards** (Rule 6), **breach intimation** (Rule 7) and erasure (Rule 8).
  - **Rule 6, reasonable security safeguards (minimum):**
    - encryption, obfuscation, masking or virtual tokens;
    - access control;
    - **visibility on access through logs, monitoring and review**;
    - backups and continuity;
    - **retaining those logs and personal data for one year** (unless another law requires otherwise);
    - processor contract clauses;
    - technical and organisational measures.
  - **Rule 7, breach:** inform each affected Data Principal without delay, and inform the Board without delay **plus a detailed report within 72 hours**.
  - **Rule 8, erasure:** for the classes listed in the Third Schedule, with **48 hours' notice** before erasure.
  - **Penalties (PIB):** up to **₹250 crore** for failing to keep reasonable security safeguards; up to ₹200 crore for failing to notify a breach or for breaches of obligations concerning children; up to ₹50 crore otherwise.
  - Data-principal requests must be answered **within 90 days**. Consent Managers must be India-based. A four-member digital Data Protection Board exists from Nov 2025.
  - **s.3(c)(i):** the Act does not apply to personal data processed by an individual for a **personal or domestic purpose**.
- **Status in 2026:**
  - Secondary sources reported that MeitY consulted in Jan 2026 on **compressing** the 18-month window to 12 months.
  - An Aug 2026 law-firm note still lists **13 Nov 2026** (Rule 4) and **13 May 2027** (substantive obligations) as the operative dates.
  - No amendment notification was found (see Unverified).
- **Relevance to Omnitrix:**
  - A businessman's assistant processing **clients' and employees' emails for business** is unlikely to fall under the personal/domestic exemption. The owner, or his company, is then probably a **Data Fiduciary** for third parties' personal data. This is not legal advice; flag it as an open question.
  - Omnitrix can claim **"DPDP-ready by architecture"**: local-only processing, encryption at rest, Guardian access control, **one-year tamper-evident access logs** (Rule 6(c) and (e)), a breach runbook able to produce the 72-hour report from the audit log, and erasure through crypto-shredding (E38).
  - Pitch it as ready **before the May 2027 deadline**.

#### [E43] IndiaAI Mission and sovereign Indic models (brief) [V; model details V-sec]
- **Citations:**
  - DD News (Prasar Bharati), "Union Cabinet approves IndiaAI Mission with Rs 10,371 crore budget". https://ddnews.gov.in/en/union-cabinet-approves-indiaai-mission-with-rs-10371-crore-budget/
  - BharatGen, "From LLMs to Verticalisation: India's Sovereign AI Stack Takes Shape" (2026). https://bharatgen.com/from-llms-to-verticalisation-india-sovereign-ai-stack-takes-shape/
- **Facts:**
  - The Cabinet approved the mission on **7 Mar 2024** with **₹10,371.92 crore**. Pillars include **>10,000 GPUs** through public-private partnership and an IndiaAI Innovation Centre for indigenous large multimodal and foundation models.
  - At the **India AI Impact Summit (Feb 2026)**, Sarvam AI launched **30B and 105B** models. BharatGen launched **Param2 17B MoE** with **about 2.4B active parameters** per token, trained across **22 scheduled languages**, with docs and workflows on Hugging Face. Gnani.ai launched Vachana speech (STT/TTS) models.
- **Relevance to Omnitrix:** A sovereignty narrative and a roadmap line: "swap in Indic sovereign models when they fit a 24 GB laptop". A 17B MoE with about 2.4B active parameters is a plausible candidate but was **not verified** for local fit or licence. Also, the S1 injection classifiers' language coverage (PG2: Hindi only among Indic languages) is a real gap for regional-language email.

---

## 6. Design checklist: Guardian + Operator + Herald + Audit, classified by System level

**The decision rule, implemented as code in Guardian:**

1. **S0 hard denies first.** Examples: tool not allowed for this agent, pinned hash mismatch, schema failure, rate limit. A deny ends processing.
2. **S0 computes a base risk tier (T0–T4)** from static action metadata, data labels and the recipient class.
3. **S1 and S2 may only escalate:** `tier = max(tier_S0, tier_S1, tier_S2)`. No model output can lower a tier, clear a flag or skip a human step.
4. **The Human decides at T2 and above**, on the device given by the tier, with an approval token bound to the action hash.
5. **Execute** through the two-phase commit or outbox.
6. **Log every step, including denies**, with the deciding System level.

Rationale: E23 (detectors bypassed), E32 (S2 raises misses), E8 (the useful reviewer direction is escalate-only), E19 (monotone privileges) and Saltzer and Schroeder (fail-safe defaults, complete mediation).

**Risk tiers used below** (extending Herald's current rules):
- **T0:** read-only, or an internal note or log. No prompt; audit only.
- **T1:** internal reminder or task. Batched digest, or a watch tap if time-sensitive.
- **T2:** external email to a *known* contact, content not derived from untrusted data. Watch tap **with preview**.
- **T3:** new or unknown recipient; any argument derived from untrusted data; confidential attachment; anything payment-, bank-detail- or contract-related; any S1/S2 flag. **Phone + biometric + forced-interaction field match.**
- **T4:** delete data, change permissions or standing rules, add or modify an MCP server or tool. **Laptop only**, with the full command or diff shown.

| # | Stage / component | Check | Level | Can a model *allow* here? | Evidence | Default if unsure |
|---|---|---|---|---|---|---|
| 1 | Ingest / Librarian | Provenance label on every chunk: channel, sender-auth result, user-authored vs external, reader set, integrity bit | **S0** | n/a | E18 FIDES, E16 CaMeL, E11 | integrity = untrusted |
| 2 | Ingest | Unicode hygiene: strip or flag tag characters U+E0000–E007F, zero-width and bidi controls. NFKC normalize for analysis only; keep the original for audit | **S0** | n/a | E24c (Microsoft 2026, Reverse CAPTCHA) | any hit → flag and raise taint |
| 3 | Ingest (PDF) | Hidden-text detector: invisible render mode, fill colour ≈ background, font < ~4 pt, text outside the crop box or under images; diff OCR against the text layer | **S0** | n/a | E24c (Lin 2025: white and microscopic text) | quarantine chunk; "hidden text" badge |
| 4 | Ingest (email) | SPF/DKIM/**DMARC alignment** from `Authentication-Results` | **S0** | **No** | E25a RFC 9989 | fail/none → "unauthenticated sender" |
| 5 | Ingest (email) | Look-alike domain: UTS-39 skeleton against the known-contacts and vendor registry, edit distance, Punycode or mixed-script, first-seen domain | **S0** (S1 may only rank near-misses for display) | **No** | E25b UTS #39; E3 (warn on Punycode, highlight domain) | "possible impersonation", never clearable by a model |
| 6 | Ingest | Injection-likeness score per chunk (PG2-86M or a small Qwen classifier) with a calibrated threshold | **S1** | **No, escalate-only** | E15, E13 (FP cost), E22 (over-defence), E23 (bypass), E8 | above threshold → quarantine and label; below threshold ≠ trusted |
| 7 | Ingest | Message-type routing (invoice, payment-change request, meeting request, newsletter...) | **S1** | Routing only | E17 action-selector | a misroute only adds checks, because actions are gated later |
| 8 | Ingest / extract | Quarantined **typed** extraction (amount, due date, IFSC/account, payee, slots) into a JSON schema. Strings stay opaque references and inherit the source label | **S1/S2 (quarantined)** | n/a | E11, E16, E18, **E20** | extraction failure → ask the human |
| 9 | Plan | Planner context holds **only** the trusted request plus symbolic references to untrusted data, never raw untrusted text | **S2**, enforced by S0 context builder | n/a | E16, E17 (plan-then-execute, context-minimization) | violation → abort and log |
| 10 | Plan | Freeze the plan before reading untrusted data; any new tool not in the plan → re-plan from trusted input | **S0** enforcement | n/a | E17 | block the unplanned call |
| 11 | Guardian: check_permission | Per-agent tool allowlist: only Operator has side-effect tools; Scout has no send; Diplomat has free/busy only | **S0** | n/a | E13 (tool filter 6.8% ASR), E19, E12, Saltzer | deny |
| 12 | Guardian | **Complete mediation:** MCP servers are stdio children of Guardian, or on unix sockets or tokens only Guardian holds; no open localhost HTTP | **S0** | n/a | E4 (local server compromise), Saltzer | refuse to start if reachable otherwise |
| 13 | Guardian | Tool-definition pinning: hash of name, description, schema and annotations; lint descriptions for instructions or references to other tools; block on change until re-approved at T4 | **S0** | **No** | E5 (rug pull, shadowing), E6, E9 "metadata non-authority" | block the tool |
| 14 | Guardian | Action class (read-only / additive-internal / external-comm / destructive / financial / irreversible) from Guardian's **own static table**; unknown tools get MCP defaults (destructive, open-world) | **S0** | **No** | E1, E2 | treat as T4 |
| 15 | Guardian: check_rules | Argument schema plus business rules: recipient-domain allowlist, amount caps, vault path allowlist, working hours, calendar conflicts | **S0** | n/a | E1 (validate inputs), E19 (argument conditions) | deny with a reason |
| 16 | Guardian | **Taint and data-flow rule:** any argument derived from untrusted data in an external-comm, financial or destructive call → ≥ T3. Confidential label and a recipient outside the reader set → block | **S0** | **No** | E18, E16, E11, E12, E7 | block or T3 |
| 17 | Guardian | **Intent consistency:** does this action serve what the user asked? The checker sees **only** the user request and the proposed call, with tool results stripped | **S2** (an optional S1 pre-screen, tuned to over-flag, may only escalate) | **No.** "Consistent" never lowers the tier; "inconsistent" blocks or escalates | E15 (small models → FP), E21, E27, E32 | escalate |
| 18 | Guardian | Rate and anomaly limits: emails per hour, new recipients per day, **approval requests per hour**; a burst triggers lockdown and an alert | **S0** | n/a | E1 (rate limit), E31 (push-bombing) | lock down and require T4 to resume |
| 19 | Guardian | **Monotone permissions:** narrowing is automatic; any widening (new recipient allowed, new tool, standing rule, auto-approve class) → human at T4 | **S0 + H** | **No** | E19 (SMT narrowing vs expansion), E28 | deny widening |
| 20 | Herald | Tier → device mapping from a **deterministic table** (severity × likelihood grid) | **S0** | **No** | E26 (likelihood × severity), E28, E12, E31 (RBI) | higher tier |
| 21 | Herald | Approval card rendered **from the canonical action object** (recipient, domain highlighted, subject, body excerpt, attachments, amount and payee). Any model rationale is labelled as model-written | **S0** (S2 note optional) | n/a | E16 (text-to-text attacks), E1 (show inputs), E3 | show raw fields |
| 22 | Herald | **Approval token bound to the action hash**, with nonce and expiry. Any argument change invalidates it. T3 adds number or field matching between laptop and phone | **S0** | n/a | E31 (CISA number matching; RBI "unique to transaction"), E9 (grant-backed approval) | reject a stale token |
| 23 | Herald | **Anti-habituation:** daily interrupt budget; T1 goes to digests; T3 requires forced interaction and a varied layout; track the approve rate per class | **S0 + H** | n/a | E29, E30, E32 (93% approvals), E28, E8 (68.5% to review) | batch and defer |
| 24 | Herald | **Fail closed:** timeout, no verdict or no connectivity → do not act (T1 reminders may fire locally) | **S0** | n/a | E32 (no verdict → deny), Saltzer (fail-safe defaults) | deny |
| 25 | Herald / Guardian | Boundaries the user states ("never email X", "wait for my review") become **stored rules**, not just context | **S0** | n/a | E32 (boundaries lost on compaction; use deny rules) | deny |
| 26 | Operator | **Two-phase execution:** stage → approve → commit. Outbound mail is held in an **outbox delay window** after approval, with cancel available | **S0** | n/a | E36 (Gmail undo, sagas) | hold |
| 27 | Operator | Compensator registry and `irreversible` flag per tool; irreversible raises the tier | **S0** | n/a | E36 (sagas, RAC cannot undo sent email) | treat as irreversible |
| 28 | Operator | Idempotency keys on every side-effecting call (LangGraph resume, MRTR retries) | **S0** | n/a | E32 (LangGraph), E1/E3 (MRTR) | refuse duplicates |
| 29 | Operator | Post-execution read-back (Mailpit API, calendar) compared with the approved hash; mismatch → alert and compensate | **S0** | n/a | E1 (validate results) | alert |
| 30 | Audit | Hash-chained append-only log of **every** model call and tool call, **including denies**, with the deciding level (0/1/2/H), score, threshold, model digest, tool hash and token id | **S0** | n/a | E34, E9 (deny-path audit), E8 (per-sample records), E37 | refuse the action if logging fails |
| 31 | Audit | Periodic Merkle **signed tree head** exported off-box (phone via ntfy, daily digest), plus a verifier UI | **S0** | n/a | E35, E37, E41 | red banner |
| 32 | Audit | PII-minimized chain: commitments in the chain, payloads encrypted in a side table; erasure by key deletion; 1-year retention | **S0** | n/a | E38, E42 (Rule 6(e), erasure) | redact |
| 33 | Audit | Trace correlation: OpenTelemetry `traceparent` in MCP `_meta`; event-sourced timeline and "why" view | **S0** | n/a | E1/2026 changelog (SEP-414), E36 (Fowler) | n/a |
| 34 | Diplomat | Outbound schema whitelist, e.g. `{start, end, tz, duration}` only. Inbound agent messages are untrusted and cannot trigger actions without a tier check | **S0** (S1 may flag extra PII to strip; cannot add fields) | **No** | E33 AirGapAgent, OWASP ASI07 | send nothing |
| 35 | Redact | Outbound redaction: regex for PAN, Aadhaar, IFSC/account, phone, email, plus an S1 NER pass that can only **add** redactions | **S0 + S1** (additive only) | **No** (S1 can only remove more) | E42 (Rule 6(a) masking) | redact |
| 36 | Sovereignty | Egress deny-by-default for agent and model processes; allow only localhost Ollama, Postgres, Mailpit and self-hosted ntfy; **no remote scanners** | **S0** | n/a | E39, E4 (SSRF, local server), E5 (agent-scan sends data to an API) | block egress |
| 37 | Governance | Adding MCP servers, changing policies or thresholds, enabling auto-approve for a class | **H (T4, laptop)** | **No** | E4 (show exact command), E19 | deny |

### 6.1 Decisions where a small model must NOT be the final word
1. **Allowing any irreversible or external action:** sending external email, anything payment- or bank-detail-related, contract acceptance, data deletion. The final word is the S0 policy plus a human (E11, E12, E23, E36).
2. **Clearing a flag:** "this chunk is not an injection" or "this sender is legitimate". Small models can **raise** suspicion, never lower it (E8, E22, E23).
3. **Sender identity for payment or bank-detail changes (BEC):** DMARC, the confusables skeleton, the contact registry, out-of-band verification and a human. Context-level judgement is provably gameable (E24a, E25).
4. **Choosing the approval device or tier:** a deterministic table. A model may only bump a tier up (E26, E31).
5. **Intent consistency for T2 and above:** at least S2, and it still cannot remove the human step. Small models were near random on holistic risk judgement (R-Judge) and produced high FPs as alignment checkers (LlamaFirewall) (E15, E27).
6. **Read-only vs destructive classification of tools:** Guardian's static table, not a model and not untrusted annotations (E1, E2).
7. **What data leaves the device** (Diplomat, email bodies, attachments): schema whitelist plus deterministic redaction; models may only redact more (E33).
8. **Anything that widens permissions** (new tools, recipients, standing rules, auto-approve classes): human only (E19).
9. **Audit-log integrity and verification:** pure code (E34, E35).

### 6.2 Where S1 *does* earn its place (low-stakes, escalate-only, or routing)
- Scoring injection-likeness to **raise taint** and triage review order.
- Routing messages to workflows.
- Ranking look-alike candidates for display.
- Deciding digest vs immediate for **T0/T1** only.
- Typed extraction inside quarantine.
- Predicting "the user will approve" for **reversible internal** actions, to auto-execute with undo and a digest, i.e. the L4/L5 split.
- Additive PII redaction.

In every case a wrong S1 answer must cost at most an extra approval or a misrouted item, never a lost email or an unapproved external action.

A design alternative worth benchmarking: **"System 1 by output budget, not by model size."** Anthropic's stage 1 is a single-token decision from the same classifier model as stage 2 (E32). On an M5 Pro, a Qwen3-14B call with a one-token constrained answer may beat Qwen3-1.7B on accuracy at an acceptable latency for low-volume decisions. Measure both on the local test set.

---

## 7. Key takeaways for Omnitrix
1. **Make Guardian the one reference monitor.** Run the 12 FastMCP servers as stdio children, or behind sockets and tokens only Guardian holds. An open localhost HTTP port lets anything bypass the gateway (E4, Saltzer).
2. **S0 first, then escalate-only.** `tier = max(S0, S1, S2)`. No model can lower a tier or clear a flag. This is how CASCADE got value from its local reviewer (E8), and how Progent keeps privileges monotone (E19).
3. **System 1 answers are safe to pass along but not safe to trust.** Booleans and enums can't smuggle instructions (FIDES, type-directed separation, E18/E20), but they can be flipped. Adaptive attacks bypass small detectors more than 90% of the time (PIGuard: 71%) (E23), and the detectors over-fire on benign "urgent" business mail (E22).
4. **Never let a detector block on its own.** In AgentDojo a DeBERTa detector cut ASR to 8% but nearly halved benign utility (E13). S1 should **label and route**; blocking comes from S0 policy.
5. **Omnitrix has the lethal trifecta by design.** Break it per action. Draft replies in a session that cannot send, and send only the **human-endorsed** draft (Rule of Two, E11/E12). Any argument derived from untrusted data in an external call is T3 (E16/E18).
6. **Intent consistency is an S2 job, and the checker must not read the email.** Give Qwen3-14B only the user request and the proposed call (Anthropic strips tool results, E32). Small models failed as alignment checkers (E15, E27). Even S2 "consistent" never skips the human at T3.
7. **Spoofing and hidden text are deterministic problems.** Use DMARC alignment (RFC 9989), the UTS-39 skeleton against a contacts registry, Unicode tag and zero-width stripping, and PDF render-mode, colour and font-size checks (E24c, E25). These make crisp, explainable demo moments ("flagged by code, not by vibes").
8. **Bind approvals to the exact action.** Use an HMAC over the action hash with nonce and expiry. Any change voids it. T3 adds number or field matching and forced interaction (CISA, RBI "unique to transaction", Bravo-Lillo; E30/E31). Render cards from canonical fields, never from an LLM summary (E16).
9. **Budget the watch.** Users approve 93% of prompts (E32). A layered detector sent 68.5% of traffic to humans (E8). Warnings habituate within a workweek (E29). Use digests for T1, reserve the watch for T2, and put T3 on the phone with biometric. Rate-limit approval requests to stop self-inflicted push-bombing (E31).
10. **Make irreversibility explicit.** Each tool gets a compensator or an `irreversible` flag. Outbound mail waits in an undo window after approval. Every side effect gets an idempotency key (E36).
11. **Audit log.** Hash-chain every model and tool call, **including denies**, with the deciding System level, score and threshold. Export signed tree heads to the phone. Keep payloads in an encrypted side table so erasure works (E34/E35/E37/E38). The cost is about 48 µs and 512 B per event (E37), so log everything. Demo: tamper with a row and show the red badge.
12. **DPDP positioning.** Rules notified Nov 2025. Rule 4 applies from Nov 2026 and the substantive duties (Rule 6 safeguards, including **one-year logs**; Rule 7, the **72-hour** Board report) from May 2027. Penalties reach ₹250 crore. Pitch Omnitrix as "DPDP-ready by architecture" (E42). Flag honestly that business use likely makes the owner a Data Fiduciary for others' data.
13. **Stay on the current MCP spec (2026-07-28).** Don't build on Sampling or Roots (both deprecated). Use tool parameters and config for paths, and call Ollama directly. Expect MRTR-style retries (E1/E3/E4).
14. **Keep the sovereignty story clean.** No remote scanners or anchors: agent-scan uploads tool descriptions (E5), and on-chain anchoring is unnecessary (E37). Contrast with Minions and PAPILLON, where even good delegation leaks (7.5%) (E40). Borrow Apple PCC's language: enforceable, verifiable, no privileged access (E41).

---

## 8. Contested and open questions
- **Is a small-model S1 security layer worth it at all?**
  - For: PromptGuard 2 cut AgentDojo ASR by 57% at almost no utility cost (E15), and Anthropic uses a cheap first stage for latency (E32).
  - Against: detectors fall to adaptive attacks (E23), over-fire on benign trigger words (E22), and a local LLM reviewer changed nothing (E8).
  - Likely answer: S1 is worth it for **triage, routing and UX**, not as a security boundary.
- **Cascade direction.** Letting S2 overturn S1's flags cut false positives about 20× but almost tripled missed overeager actions, from 6.6% to 17% (E32). Which errors should S2 be allowed to fix? This proposal says S2 may escalate or block, but may not clear a deterministic requirement. That costs more approvals, and the trade-off is unmeasured for Omnitrix.
- **Fine-tuned small guards versus prompted ones.** R-Judge shows a safety-fine-tuned 8B guard can rival GPT-4o (E27). Can a Qwen3-4B fine-tuned on Omnitrix-specific data reach usable calibrated accuracy? That is out of hackathon scope, and slice B covers calibration.
- **Can content-level defences ever be enough?** Abdelnabi and Bagdasarian (E24a) argue that context manipulation makes detection a losing game. Structural defences (FIDES, CaMeL, Progent, type restriction) block injection-driven *control* but not *misinformation*, such as a summary that lies (E16, E20). Approval cards built from raw fields mitigate this but don't solve it.
- **Tool annotations.** Should Omnitrix trust its own annotations? Should annotations be evaluated at runtime (the Interest Group agenda, E2)? Hints stay unenforceable for third-party servers.
- **Approval UX on a watch.** No verified study was found on security-decision accuracy on smartwatch-sized UIs. The habituation and forced-interaction literature is desktop and mobile. Treat watch approvals as T1/T2 only; that is a design judgement.
- **Append-only audit versus erasure under DPDP.** Crypto-shredding with commitments follows EU guidance (E38). Nothing Indian regulators have said on this was found.
- **DPDP scope.**
  - Does a sole proprietor's assistant count as "personal or domestic purpose"? Probably not for business mail, but this is untested.
  - Does the "legitimate uses" basis for voluntarily shared email data apply? The Act's s.7 was not verified here.
  - The timeline-compression proposal (Jan 2026) remains unconfirmed.
- **Benchmarks versus reality.** Most numbers here (AgentDojo, MCPTox) come from frontier cloud models. Local Qwen3-class behaviour is largely unmeasured. The one independent small-model data point is Qwen2.5-7B with Progent (E24b). Build a small local AgentDojo-style suite: the three demo scenarios plus benign Hinglish business mail.

---

## 9. Unverified (not confirmed against a primary source; do not cite as fact)
- **PSD2 RTS "dynamic linking"** (Commission Delegated Regulation (EU) 2018/389, Art. 5). The official page bodies (EUR-Lex, legislation.gov.uk) did not render; only a search snippet was seen. RBI 2025 (E31) is used instead.
- **Jenkins, Anderson, Vance, Kirwan, Eargle, "More Harm Than Good? How Messages That Interrupt Can Make Us Vulnerable"**, *Information Systems Research* 27(4):880–896, 2016 (DOI 10.1287/isre.2016.0644). Title, venue and topic (dual-task interference reduces attention to interrupting security messages) come from search listings. The publisher page returned 403, so specific findings, such as "time warnings to task breakpoints", are **unverified**.
- **Schneier and Kelsey 1999 volume and issue:** Schneier's site says TISSEC vol. 1 no. 3, pp. 159–176, while a search listing says vol. 2 no. 2 (May 1999). The ACM DL page returned 403.
- **Saltzer and Schroeder:** the mirror cites SOSP 1973 and CACM 17(7) 1974. The widely cited *Proc. IEEE* 63(9), 1975 version was not re-checked.
- **Greshake et al. at AISec '23** and **"The Attacker Moves Second" at USENIX Security 2026:** venues seen only in search listings.
- **MCPTox at AAAI 2026 and its 36.5% average ASR:** from the AAAI OJS listing and search summaries of the paper body; the arXiv abstract gives only the o1-mini 72.8% and refusal figures.
- **PromptGuard 2 AUC:** the model card says 99.8% AUC for the 86M model, while the LlamaFirewall paper extraction said 0.98. The recall at 1% FPR (97.5%) matches in both.
- **ToolEmu "spotlight"** designation: only the ICLR 2024 poster was confirmed.
- **R-Judge per-model small-model F1 values** (Llama-2, Vicuna, Mistral) were machine-extracted from HTML tables. Only the abstract claims (GPT-4o 74.42%; others not significantly above random) are verified.
- **Rehberger / Embrace The Red "ASCII smuggling" (Jan 2024)**: seen only in search results, not fetched. The Microsoft Sept 2026 blog was verified instead.
- **Invariant Labs acquired by Snyk (Jun 2025)**: search snippet only.
- **DPDP 12-month compression proposal (Jan 2026 consultation)**: secondary sources only. **No amendment notification found.** Also the **section-by-section commencement of the DPDP Act itself** (as opposed to the Rules' Rule 1) was not verified in the gazette.
- **Sarvam 30B/105B specs and benchmark scores:** from the BharatGen and Inc42 article and search snippets, not Sarvam primary sources. **Param2 local-fit and licence** were not checked.
- **Agent Flight Recorder's eight semantic fields:** not enumerated in the abstract.
- **EDPB Guidelines 02/2025 "v2" final (Jul 2026 PDF):** seen only in a search listing. The April 2025 adoption is verified.
- **Anthropic auto-mode stage-1 and stage-2 model identity:** the docs say the classifier runs on Sonnet 5 by default. That both stages use the same model is inferred, not stated.
- **Tool-annotation semantics beyond the defaults**, such as whether `destructiveHint` is only meaningful when `readOnlyHint` is false: the schema page did not render in fetch.
