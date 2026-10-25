# Sweep 5 (VI-02): plan v6 and citation check (handoff)

Date 2026-10-26. Nothing committed. Files: `docs/plan.md`, `docs/literature-review-and-usage.md`, `docs/literature-to-code-map.md`, one line of `AGENTS.md`. No code or tests touched. A backup of plan v5 was not kept in the repo (it is in git history).

## Plan v6
- Version header bumped; a changelog at the top lists the 25 edits by number and the reconciliations. Section numbers and anchors are unchanged (no links into `plan.md#...` exist in the repo). Only the heading of section 20 now says "not in v6".
- All 25 edits of the review's section 7 applied. Edit 23 (compute) was estimated from the measured pilot tokens: Full about 75K tokens per case replaces 150K (RQ1 main 82 to 60 node-h, ablations 50 to 25, RQ2 bundles 7.5 to 4) and new rows were added (budget sweeps 31, A8b+A8c 8, A11b 7.5, A13 8.5, faithfulness 1). Total about 285 node-h (about 225 with the API), about 57 sessions (74 with buffer). These are estimates on Qwen3-14B throughput of 2M tokens per node-hour, and the Qwen token counts are not measured; re-check in week 1.
- Reconciled with the build: statutes gap (CrPC 10 rows, NDPS 5 rows, from official PDFs); native Hindi High Court fallback for HLDC; built store sizes; hosted backends and caps (OpenAI USD 5, default 4.50; Sarvam INR ledger, default INR 25, prices 15/5/60); gold G1/G3 by agreement with span grounding and the kappa numbers of `gold-labeler.md`; implemented ids S1-S18, P5-P8, B5 (S15b not built); pilot tokens (about 70K in, 14K cached, 4K out, USD 0.0078); mask-instead-refuse, injection defences as built; S7 stays opt-in (sequential is the default until A11a is measured).
- Not in plan.md by design: no row is marked built for the claim-splitter, citation faithfulness, three-way status, conformal calibration, bundle-splitting baseline, MinerU2.5/olmOCR backends, or the OCR cross-check; they are labelled proposed, not built.
- Still outdated elsewhere (not my scope): `README.md` line 58 says "plan.md (v5)"; `docs/evaluation-plan.md` still carries the old Self-RAG (OpenReview), CRITIC (mlanthology) and semantic-chunking (preview) links; `docs/proposal/*` is v5.

## Citation check
57 papers checked on official pages: 53 VERIFIED, 4 CORRECTED, 0 UNVERIFIED (full table at the end of `docs/literature-to-code-map.md`).
- **S18 (Wachsmuth, Syed, Stein, ACL 2018):** P18-1023 is correct (title as cited, Long Papers, pp. 241-251). Pages added.
- Corrected: Self-RAG link (OpenReview ID would not open; ICLR 2024 proceedings page used); CRITIC link (third-party index replaced by the ICLR 2024 proceedings page); MAST first author is Cemri not Pan, and the NeurIPS page shows "spotlight" but not the "Datasets and Benchmarks" track (dropped in the map and the review); semantic chunking link (preview host replaced by the canonical anthology page).
- Confirmed claims: Debate or Vote is a spotlight; AFlow and MaAS are orals; ADAS is an ICLR 2025 poster (arXiv page shows no venue); RouterDC and GPTSwarm exist as cited; titles shortened in the EV-01 table were expanded.
- Review-only corrections: MinerU2.5 first author Niu, no venue on arXiv (the "ACL 2026 Industry" claim is unconfirmed); olmOCR no venue on arXiv.
- Limits: for about a dozen papers the fetch did not show author names (first authors come from the review's reference list; title, venue and link matched); arXiv-only papers show no venue; HippoRAG, StruQ, SecAlign and Stop-RAG take venue from the arXiv comment. "Check" counts in the review's section 2 were not recomputed.
- Not checked: papers in the review's catalogue that are not cited in the map (about 90, most "Check S"). Plan.md names only papers verified here (IntrAgent, AgentRouter, GraphRouter, DeepSieve, MAST, AgentCourt, IL-PCSR, Magesh et al. via the Stanford Law page and journal abstract found by search, not the Wiley page). Older plan text still names SAMVAD, NyayaRAG, PredEx, IBPS without citations: not verified here.

## Proposal references [21] to [26] (`docs/proposal/proposal.md`; not edited)
- [21] Self-RAG: authors, title match arXiv 2310.11511 (arXiv shows no venue); ICLR 2024 confirmed on the ICLR proceedings page. OK.
- [22] Adaptive-RAG: authors match; arXiv page says NAACL 2024. OK.
- [23] Docling Technical Report, arXiv 2408.09869: title matches; the arXiv author list begins C. Auer. OK (the review separately cites the AAAI-workshop toolkit paper 2501.17887, not checked).
- [24] HLDC: authors begin A. Kapoor; arXiv comment says ACL 2022 Findings. OK.
- [25] Augraphy: authors and title match, but the arXiv page shows no venue; "ICDAR 2023" rests only on the project's GitHub citation, so it is unconfirmed. Fix in the proposal: cite as arXiv 2208.14558 (2022) without a venue, or confirm on the ICDAR proceedings.
- [26] Doyle, A Truth Maintenance System, Artificial Intelligence 12 (1979) pp. 231-272: confirmed from the author's publication list and a bibliography; the publisher page redirected and could not be read, so issue 3 is unverified.
