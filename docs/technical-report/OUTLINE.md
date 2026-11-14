# Planning outline of the technical report (one sentence per planned paragraph)

The one idea: an agent system for bail briefs beat simpler systems on the same model only after its losses were read case by case and fixed with four switches, and the sealed test confirms four of five registered hypotheses.

Naming: the final system is **VS-Final** everywhere; "Full" is the first full system it extends. Every label is defined at first use and again in the Glossary.

## Abstract (5 sentences)
1. Context: legal-aid lawyers prepare bail applications from short, messy files, and a brief must rest on the file and on authorities that exist.
2. Gap (However): a model drafting from memory invents facts and case law, and nobody has shown that planning, checking and adversarial review ground a brief better than simpler retrieval on the same model.
3. Content: six agents, ten typed stores, two counsel gates; final configuration chosen on 50 development orders; five registered hypotheses; 80 sealed orders; seven baselines.
4. Result: 46 wins, 69 ties, 5 losses (first full system 29, 76, 15); four hypotheses hold, one fails on one count; 0 of 320 exports executed.
5. Why it matters: the system helped only after each decision was measured against a simpler alternative; 0.89 of sentences are still not entailed by the facts alone, so the brief stays a draft for counsel.

## 1 Introduction
1. A bail application in an Indian High Court starts from a pile of mixed documents and needs five kinds of knowledge.
2. Prior work falls in three groups: legal tools that fabricate, adaptive retrieval, and multi-agent verification with mixed evidence.
3. However, no study tests these parts together on legal drafting against simple baselines on the same model without hand-made gold, and our own first full system did not beat its baselines.
4. In this paper, we build, search, freeze and test; bulleted refutable contributions, each with its section.
5. Scope: a drafting aid for counsel; no outcome prediction.

## 2 System
1. Worked case first: order t1dev-019 from intake to the refused export.
2. Six agents, each with one narrow decision (Figure 1).
3. Ten typed stores on four shelves, each searched in its own way.
4. Evidence contracts tell the orchestrator what a factor needs; the orchestrator decides order, query, sufficiency and stop.
5. Every sentence is checked and repaired; counsel approves twice, and export before the second approval is impossible in code.
6. Client text leaves the machine only through a pseudonymisation boundary.

## 3 Architectures we tried
1. Every design change is an opt-in switch, in five families (B, A, S, P, X).
2. On three hosted model families the first full system did not beat every baseline, and no literature variant fixed that.
3. Reading the outputs of Full gave four causes of its losses.
4. Eight fixes (X1 to X8) were candidates; the protocol separates 30 search orders, 20 holdout orders and 80 sealed orders.
5. VS-Final has the fewest losses on the search orders and repeats on the holdout (Table 1).
6. Three candidates with more wins were rejected because they win by writing fewer or copied sentences.
7. The three losses that remain are structural.

## 4 Final method
1. VS-Final is Full with four switches, each answering one cause.
2. X1, X4, X5, X7: what each does and the evidence for it.
3. What the four switches cost: citation precision and tokens.

## 5 Evaluation setup
1. Data: public court orders; the system reads the facts part and gold comes from the rest.
2. Gold without annotators: two independent labelers must agree on a verbatim span.
3. Leakage control and the sealed slice.
4. Baselines B0 to B6 share the model, the checklist and the facts (Table 2).
5. 25 quality metrics; M6 and M6a explained.
6. Statistics: paired bootstrap, Holm, win only when the interval excludes zero.
7. Pre-registration and deviations.

## 6 Results
1. VS-Final has 46 wins, 69 ties and 5 losses on the sealed slice; Full has 29, 76, 15 (Table 2).
2. Four of five hypotheses hold; H-A1 fails on one cell, because B5 writes fewer sentences (Table 3).
3. In absolute terms the numbers are still low (Table 4).
4. The verdicts do not depend on the model labeler (D11).
5. The win and loss pattern survives two reruns; single orders do not (D12).
6. Tools are called with few bad arguments and no export is executed without approval.

## 7 Ablations
1. Strict abstention is the switch that the 30 orders can resolve (Table 5).
2. Removing check and repair or sparring costs wins; removing tools, the factor filter or the dossier changes nothing these orders resolve.
3. Two rows go against VS-Final and neither is a better brief.

## 8 Limitations and discussion
1. The unsupported-fact rate overstates fabrication.
2. The statutory position was empty in the frozen runs; fixed after the freeze, not rerun.
3. The statute store had wrong bail flags for 43 IPC sections; rebuilt.
4. One model, one slice, one run.
5. Gold is not human; Rights Radar check reads acts only.
6. Privacy, the paid-provider lock, no authentication, no outcome predictions.

## 9 Conclusion
1. The answer, the numbers, and the methodological lesson; next steps.

## After the body (outside the 8 pages)
References; Glossary (one table: term, plain meaning, where used); Appendix A full win/tie/loss tables; B metric definitions; C settings and budgets; D deviations D1 to D12; E cost and tool calls; F ablations in full; G reproducibility commands.

## Spine check
Reading the first sentences in order gives: task and its needs; what exists; what is missing; what we did and found; one case end to end; the parts; what we tried and why the first system lost; the fix; how we measure; what the sealed test says; which parts matter; what the numbers do not show; the lesson. Each results paragraph opens with its finding, and every table is called in numerical order (Tables 1 to 5, then A1 to A7).
