"""S16/S16b chunking study on a tiny synthetic parts file: sampling, the self-supervised queries, the table (offline, no data directory)."""

from __future__ import annotations

import json
import zlib

from vakeel_sahayak.eval.studies import run_study, s16

REASONING = ("1. Heard learned counsel for the parties and perused the record carefully.\n\n"
             "2. The applicant is in custody since the month of March and the investigation is complete.\n\n"
             "3. The learned counsel for the applicant submits that the applicant has no criminal antecedents whatsoever to his name.\n\n"
             "4. In view of the foregoing the Court is inclined to release the applicant on bail on suitable conditions.")


def parts_file(tmp_path, n=200):
    rows = []
    for i in range(n):
        did = f"DOC{i:04d}"
        text = REASONING.replace("March", f"month{i}") + f" Reference number {i} of the register."
        rows.append({"doc_id": did, "court": "X High Court", "date": "2020-01-01", "parts": {"facts": "Facts of the matter.", "reasoning": text}})
    p = tmp_path / "parts.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def test_first_sentence_skips_the_opening_formula_and_dropout_removes_every_third_content_word():
    s = s16.first_sentence({"reasoning": REASONING})
    assert s.startswith("The learned counsel for the applicant submits")
    assert s16.first_sentence({"reasoning": "Short."}) is None
    assert s16.dropout("alpha beta gamma delta epsilon zeta") == "alpha beta delta epsilon"  # every third content word (gamma, zeta) is dropped
    assert s16.dropout("the alpha of beta and gamma") == "the alpha of beta and"  # stop words neither count nor go


def test_corpus_sampling_is_by_hash_and_capped(tmp_path):
    p = parts_file(tmp_path)
    docs = s16.load_corpus(3, p)
    assert len(docs) == 3 and all(zlib.crc32(d["doc_id"].encode()) % 64 == 0 for d in docs)
    assert [d["doc_id"] for d in s16.load_corpus(3, p)] == [d["doc_id"] for d in docs]
    forced = s16.load_corpus(2, p, {"DOC0001"})
    assert "DOC0001" in {d["doc_id"] for d in forced}


def test_run_writes_table_with_each_strategy_and_labels_the_targets(tmp_path):
    res = run_study("s16", str(tmp_path / "o"), n=6, strategies=("structure", "proposition", "fixed"), parts_file=str(parts_file(tmp_path)), ks=(5, 10), use_g2=False)
    assert res["g2_resolvable_queries"] == 0 and set(res["queries"]) == {"first_sentence", "dropout"}
    for kind in ("first_sentence", "dropout"):
        assert set(res["results"][kind]) == {"structure", "proposition", "fixed"}
        assert all(0.0 <= r["recall"]["10"] <= 1.0 for r in res["results"][kind].values())
    assert res["results"]["first_sentence"]["proposition"]["index"]["chunks"] > res["results"]["first_sentence"]["structure"]["index"]["chunks"]
    md = (tmp_path / "o" / "s16.md").read_text(encoding="utf-8")
    assert "NOT G2" in md and "S16" in md and "no G2 recall to report" in md
