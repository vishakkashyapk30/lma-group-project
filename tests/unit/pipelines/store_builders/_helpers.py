"""Synthetic interim data for the store-builder tests (plan §5.1, §5.2, §2 leakage rules).

ASSUMPTION (the plan does not fix the layout of `data/interim`): `interim_dir` holds
  * `orders.jsonl`            one JSON object per order: doc_id, court, date, outcome, text (the whole order), plus the FIR key
                              (police_station, fir_number, fir_year) and `split`; the builders split the text with
                              `order_splitter.split_order` and chunk it with `stores.chunking.chunk_order`;
  * `citation_edges.jsonl`    resolved `CitationEdge` rows (the output of the citation-graph pipeline);
  * `concordance_edges.jsonl` `ConcordanceEdge` rows (used for `section_family`);
  * `statutes.jsonl`          `StatuteRow` rows.
`exclude_doc_ids=None` means nothing is excluded (`build_all` computes the set with `pipelines.leakage.excluded_doc_ids`);
`out_dir` receives one store and `<Store>().open(out_dir)` reads it; the return value is the number of rows written.
Embeddings are produced through `models.factory.get_embedder`, replaced here by `FakeEmbedder` (see conftest.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.fakes.data import load_concordance, load_statutes
from tests.unit.stores._helpers import long_paragraph, ntok, paragraph, sentence  # noqa: F401  (re-exported)

CASE_DATE = "2025-02-03"  # the as-of date of case-0007: queries must only see documents dated before it
TEST_ORDER = "TESTORD-2024-0001"
SAME_FIR_ORDER = "SAMEFIR-2024-0002"
EXCLUDED = {TEST_ORDER, SAME_FIR_ORDER}
LATE_ORDER = "DLHC-2025-0099"  # dated after the case: stored, never returned for before=CASE_DATE

DEFENSE_MARK = "falsely implicated"  # sentinel words of the defense part: must never reach caselaw.reasoning
PROSECUTION_MARK = "flee from justice"  # sentinel words of the prosecution part
FACTS_MARK = "induced the complainant"

HEADER = "IN THE HIGH COURT OF DELHI\nBAIL APPLN. 1234/2024\n"
FACTS = (
    "Facts: The applicant seeks regular bail in FIR No. 112/2024 PS-1 registered under Section 420 IPC. It is alleged that he "
    "induced the complainant to part with Rs. 5 lakh on 10.08.2024. He was arrested on 20.08.2024 and has been in judicial "
    "custody for about four months. The charge sheet has been filed. A co-accused has been granted bail."
)
DEFENSE = (
    "Learned counsel for the petitioner submits that the applicant is innocent and has been falsely implicated. It is urged that "
    "the co-accused with the same role has been released on bail."
)
PROSECUTION = (
    "Learned APP submits that the offence is serious and that the applicant may flee from justice. It is stated that the "
    "investigation revealed the applicant's role in the cheating."
)
OPERATIVE_ALLOWED = "Accordingly, the bail application is allowed. The applicant shall furnish a personal bond of Rs. 50,000 with one surety."
OPERATIVE_DISMISSED = "Accordingly, the bail application is dismissed. Nothing stated herein shall affect the trial."

REASONING_PARITY = (
    "1. Heard learned counsel for the parties and perused the record. "
    "2. The co-accused has already been granted bail on similar facts and the applicant stands on the same footing, so parity applies. "
    "3. The charge sheet has been filed and custodial interrogation is no longer required."
)
REASONING_GRAVITY = (
    "1. Heard learned counsel for the parties and perused the record. "
    "2. The Court has considered the gravity of the offence and the punishment prescribed, which is serious."
)
CITING_SENTENCE = "The principle in SC-2014-0463 was followed."


def order_text(operative: str = OPERATIVE_ALLOWED, *, reasoning: str = REASONING_PARITY, facts: str = FACTS) -> str:
    return HEADER + "\n".join([facts, DEFENSE, PROSECUTION, reasoning, operative])


def order_row(doc_id: str, date: str, outcome: str, text: str, *, court: str = "Delhi High Court", split: str = "train",
              ps: str = "PS-A", fir: str = "55", fir_year: int = 2021) -> dict[str, Any]:
    return {"doc_id": doc_id, "court": court, "date": date, "outcome": outcome, "text": text, "split": split,
            "police_station": ps, "fir_number": fir, "fir_year": fir_year}


def long_reasoning(n_sentences: int = 4, words: int = 300) -> str:
    """One numbered reasoning paragraph of n_sentences x `words` tokens (1,200 tokens): only splittable at sentence ends."""
    return "1. Heard learned counsel for the parties and perused the record. " + long_paragraph(2, n_sentences, words)


def orders() -> list[dict[str, Any]]:
    return [
        order_row("DLHC-2022-1187", "2022-06-03", "granted", order_text()),
        order_row("DLHC-2023-0911", "2023-05-19", "rejected", order_text(OPERATIVE_DISMISSED, reasoning=REASONING_GRAVITY),
                  ps="PS-B", fir="10", fir_year=2022),
        order_row("SC-2014-0463", "2014-07-02", "granted", order_text(), court="Supreme Court of India", ps="PS-C", fir="3", fir_year=2013),
        order_row(TEST_ORDER, "2024-11-20", "granted", order_text(), split="test", ps="PS-1", fir="112", fir_year=2024),
        order_row(SAME_FIR_ORDER, "2024-10-02", "granted", order_text(), ps="PS-1", fir="112", fir_year=2024),
        order_row(LATE_ORDER, "2025-03-01", "granted", order_text(), ps="PS-Z", fir="7", fir_year=2025),
        order_row("DLHC-2020-0500", "2020-01-15", "granted", order_text(reasoning=long_reasoning()), ps="PS-D", fir="9", fir_year=2019),
    ]


def citation_edges() -> list[dict[str, Any]]:
    from vakeel_sahayak.schemas.enums import Treatment as T

    rows = [
        ("DLHC-2022-1187", "SC-2014-0463", T.RELIED_ON, "HC"),
        ("DLHC-2020-0500", "SC-2014-0463", T.FOLLOWED, "HC"),
        ("SC-2020-0100", "DLHC-2023-0911", T.OVERRULED, "SC"),
        (TEST_ORDER, "SC-2014-0463", T.FOLLOWED, "HC"),  # an edge out of an excluded order must not survive
    ]
    return [{"citing_doc_id": a, "cited_doc_id": b, "treatment": t.value, "court_level": lvl, "sentence": CITING_SENTENCE}
            for a, b, t, lvl in rows]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path


def write_interim(root: Path, extra_orders: list[dict[str, Any]] | None = None) -> Path:
    """Write the whole interim directory (orders, citation edges, concordance edges, statutes) and return it."""
    root.mkdir(parents=True, exist_ok=True)
    write_jsonl(root / "orders.jsonl", orders() + list(extra_orders or []))
    write_jsonl(root / "citation_edges.jsonl", citation_edges())
    write_jsonl(root / "concordance_edges.jsonl", [e.model_dump(mode="json") for e in load_concordance()])
    write_jsonl(root / "statutes.jsonl", [s.model_dump(mode="json") for s in load_statutes()])
    return root


def doc_ids(rows: list[Any]) -> set[str]:
    return {r.doc_id for r in rows}
