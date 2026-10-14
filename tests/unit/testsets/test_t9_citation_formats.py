"""T9 citation formats (plan §15.2, §5.3, F7): about 500 Open India Law judgments, cited in each format the resolver handles, plus near-miss
distractors; about 2,000 strings; the answer is the document ID. Formats of plan §5.3: neutral INSC, SCC, AIR, SCC OnLine, Cri LJ and
'X v. State of Y' case names.

# ASSUMPTION: metadata_path rows {"doc_id", "court", "date", "neutral_citation", "scc", "air", "scc_online", "cri_lj", "title"};
# out_dir/strings.jsonl rows {"string", "format": "neutral"|"scc"|"air"|"scc_online"|"cri_lj"|"case_name", "doc_id": <id or None for a
# distractor>, "distractor": bool, "near_to": <doc_id of the real citation it imitates, for distractors>}.
"""

from __future__ import annotations

import collections
import json

import pytest

from tests.unit.testsets._helpers import assert_manifest, read_manifest, read_rows
from vakeel_sahayak.testsets.t9_citation_formats import build_t9

FORMATS = {"neutral", "scc", "air", "scc_online", "cri_lj", "case_name"}


def write_metadata(tmp_path, n: int = 500):
    rows = [{"doc_id": f"SC-{2000 + i % 25}-{i:04d}", "court": "Supreme Court", "date": f"{2000 + i % 25}-03-15",
             "neutral_citation": f"{2000 + i % 25} INSC {100 + i}", "scc": f"({2000 + i % 25}) {i % 12 + 1} SCC {200 + i}",
             "air": f"AIR {2000 + i % 25} SC {3000 + i}", "scc_online": f"{2000 + i % 25} SCC OnLine SC {400 + i}",
             "cri_lj": f"{2000 + i % 25} Cri LJ {1000 + i}", "title": f"Party{i} v. State of Region{i % 17}"} for i in range(n)]
    p = tmp_path / "metadata.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p, {r["doc_id"]: r for r in rows}


@pytest.fixture()
def built(tmp_path):
    path, meta = write_metadata(tmp_path)
    out = tmp_path / "t9"
    m = build_t9(str(path), str(out))
    return m, read_rows(out / "strings.jsonl"), meta, out


def test_about_two_thousand_strings_from_five_hundred_judgments(built):
    m, rows, _, out = built
    assert_manifest(m, "T9")
    assert 1800 <= m.size <= 2200 and m.size == len(rows) and read_manifest(out)["size"] == len(rows)
    assert m.used_for == ["F7"]
    assert len({r["doc_id"] for r in rows if r["doc_id"]}) == 500


def test_every_resolver_format_appears_many_times(built):
    """Resolution accuracy is reported by format (plan §15.6 F7), so each of the six formats needs enough strings."""
    _, rows, _, _ = built
    counts = collections.Counter(r["format"] for r in rows if not r["distractor"])
    assert set(counts) == FORMATS and all(c >= 100 for c in counts.values())


@pytest.mark.parametrize(("fmt", "key"), [("neutral", "neutral_citation"), ("scc", "scc"), ("air", "air"), ("scc_online", "scc_online"), ("cri_lj", "cri_lj")])
def test_a_true_citation_string_is_the_metadata_citation_of_its_document(built, fmt, key):
    """The answer is the document id and the string is rendered from that document's own metadata (never typed by hand)."""
    _, rows, meta, _ = built
    mine = [r for r in rows if r["format"] == fmt and not r["distractor"]]
    assert mine and all(meta[r["doc_id"]][key] in r["string"] for r in mine)


def test_case_name_strings_use_the_title(built):
    _, rows, meta, _ = built
    mine = [r for r in rows if r["format"] == "case_name" and not r["distractor"]]
    assert mine and all(meta[r["doc_id"]]["title"].split(" v. ")[0] in r["string"] for r in mine)


def test_near_miss_distractors_have_no_answer_and_imitate_a_real_citation(built):
    """A distractor is a plausible string that must NOT resolve (changed year, volume or page): its doc_id is None, and it differs from the
    real citation it imitates by a small edit."""
    _, rows, meta, _ = built
    dist = [r for r in rows if r["distractor"]]
    assert len(dist) >= 100 and all(r["doc_id"] is None and r["near_to"] in meta for r in dist)
    real = {meta[d][k] for d in meta for k in ("neutral_citation", "scc", "air", "scc_online", "cri_lj")}
    assert not any(r["string"] in real for r in dist), "a distractor must not be a real citation"


def test_every_distractor_is_close_to_its_original(built):
    """Close means a Levenshtein distance of at most 3 from the original citation of the same format (otherwise it is not a 'near' miss)."""
    _, rows, meta, _ = built
    key = {"neutral": "neutral_citation", "scc": "scc", "air": "air", "scc_online": "scc_online", "cri_lj": "cri_lj"}

    def lev(a: str, b: str) -> int:
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]

    for r in rows:
        if r["distractor"] and r["format"] in key:
            assert lev(r["string"], meta[r["near_to"]][key[r["format"]]]) <= 3


def test_strings_are_unique(built):
    _, rows, _, _ = built
    strings = [r["string"] for r in rows]
    assert len(strings) == len(set(strings))


def test_build_is_deterministic(tmp_path):
    path, _ = write_metadata(tmp_path)
    build_t9(str(path), str(tmp_path / "a"))
    build_t9(str(path), str(tmp_path / "b"))
    assert (tmp_path / "a" / "strings.jsonl").read_bytes() == (tmp_path / "b" / "strings.jsonl").read_bytes()


def test_fewer_than_five_hundred_judgments_still_builds_proportionally(tmp_path):
    """# ASSUMPTION: a smaller pool gives a proportionally smaller set (about four strings per judgment) rather than an error."""
    path, _ = write_metadata(tmp_path, n=50)
    m = build_t9(str(path), str(tmp_path / "t9"))
    assert 150 <= m.size <= 250
