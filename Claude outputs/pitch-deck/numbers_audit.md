# Omnitrix deck: number audit

Every number on the slides, and the fact from the brief (or the cited market source) it came from.

## Slide 1: Intro
No numbers apart from "Track 1".

## Slide 2: The Problem
| On slide | Source |
|---|---|
| Context fragmentation (no number) | Problem: work life buried in email, meetings and notes |
| 97.8% junk in a Mem0 audit | Problem: Mem0 audit of 10,134 memories, 97.8% junk |
| 41% Graphiti facts invalidated; 3 of 4 audited invalidations wrong | Problem: Graphiti's small-model judge invalidated 41% of ~3,950 facts; 3 of 4 audited cases wrong |
| 7.5% of queries leak private data | Privacy: local + cloud delegation leaks on 7.5% of queries (PAPILLON) |

## Slide 3: Our answer
| On slide | Source |
|---|---|
| 1.7B | Fine-tuning: LoRA on Qwen3-1.7B |
| 10 / 42 / 1 of 55 (ladder SVG) | Brain: 55 judgements; 10 pure code, 42 go to S1 first, 1 needs the large model first |

## Slide 4: Architecture (SVG)
| On slide | Source |
|---|---|
| MacBook Pro, M5 Pro, 24 GB | Setup |
| 11,528 items, 2.8 s (kaminski-v) | Setup |
| S0/S1/S2/H; Qwen3-1.7B; Qwen3-14B; 1 token + p | Brain: four tiers |
| Postgres 17 + pgvector; 9 table names | Setup; SQL |
| BM25 + HNSW fused; read-only SQL, 3 s limit | Search; SQL |
| MCP server, 9 typed tools | SQL |
| 22 agents → 7 roles; 7 role names + Diplomat (demo) | Society of agents |

## Slide 5: Fine-tuning and watch
| On slide | Source |
|---|---|
| 5,958 labels, EnronQA | Fine-tuning |
| 54 min, 18 GB peak | Fine-tuning (MLX, peak 18 GB) |
| Chart: 83.7/96.6/95.5, 74.4/90.9/87.5, 44.6/60.1/55.4, 31.5/52.7/47.9 | Held-out accuracy table |
| 19 s | Watch: approved on the wrist and ledgered 19 s after the gate paused |
| mDNS + HMAC; Galaxy Watch 5, Wear OS 5, Kotlin | Watch |

## Slide 6: Impact
| On slide | Source |
|---|---|
| 0 cloud calls | Privacy: zero cloud calls (from the architecture) |
| 96.6% vs 95.5% | Accuracy table, "supported" |
| 7 roles | Society of agents |
| 807 s → 255 s, 60 emails | Time and cost |
| 3–5×, 934 MB, no API costs | Fine-tuning; Time and cost |
| 40.0% → 6.7%, 60 sandbox tasks | Accuracy and safety: action gate |
| TAM 855M users, ≈ ₹20.5 lakh crore | 1.14B knowledge workers (Gartner, 24 Sep 2019, forecast for 2023) × 75% using AI (Microsoft & LinkedIn 2024 Work Trend Index) × ₹23,988/yr |
| SAM 3.70M users, 40.2 lakh, ≈ ₹8,872 crore | 20,13,081 advocates (Law Ministry reply to Rajya Sabha, via LawChakra, 25 Oct 2025) + 4,23,105 CAs (ICAI 76th Annual Report) + 13,86,150 allopathic doctors (MoS Health, Rajya Sabha, 1 Apr 2025) + 1,97,692 DPIIT startups (PIB, 2 Dec 2025, one founder each) = 40,20,028 × 92% using AI (Microsoft India, 16 May 2024) × ₹23,988/yr |
| SOM 36,984 users, ≈ ₹88.7 crore | 1% of SAM over 3 years: **our assumption**, not a sourced figure |
| ₹1,999/month, ₹23,988/yr | ChatGPT Plus India price (TechCrunch, 18 Aug 2025) × 12 |

## Slide 7: Feasibility
| On slide | Source |
|---|---|
| 24 GB, MacBook Pro, Apple M5 Pro | Setup |
| 934 MB fused 4-bit judge | Fine-tuning |
| 54 min, 18 GB peak | Fine-tuning |
| Latency chart: 1.9 ms, 13 ms, 28 ms, 214 ms, ~0.5 s, 1.7 s, 11 s | Search; Fine-tuning (214 ms per email); Voice (~0.5 s for a 2.5 s clip); Time (11 s median, 1.7 s draft) |
| ₹250 crore, ~May 2027, DPDP Rules 2025 | Privacy |

## Slide 8: References
Only the reference details given in the brief, plus the market sources above.

## Slide 9: Thank you
No numbers. The team contact card is an icon only; add names or an email when ready.

## TODOs left
- Slide 6 notes: SAM is not yet filtered to people whose laptops can run local models; no citable figure was found.
- Market caveats (in the notes): the Gartner count is a 2019 forecast for 2023, and the ₹1,999 price dates from August 2025, so the TAM is indicative.
