"""S16 and S16b: chunk granularity study (evaluation plan 3.3 row S16; Table 2 row "chunker choice"). Retrieval only, offline, no model.

Strategies are those of `stores/chunk_strategies.py` (`structure` is the control; `proposition` is S16; `late` is S16b; `fixed`, `recursive`, `semantic`, `page` are B3's). Each is
applied to the same corpus and scored with `eval.baselines.chunking_variants.evaluate_strategy` (a small in-memory hybrid index with the offline hashed embedder; recall@k at document
level, MRR, index size).

Targets (what the queries are, stated in every output):
* G2, where resolvable: queries are the facts of T1 dev and open orders that have a resolved court-cited precedent (G2) AND whose cited judgments' text is in the corpus file. Today the
  cited judgments are Supreme Court judgments whose text is not in `data/interim/t1_work/parts.jsonl`, so this set is empty (n is printed; no G2 number is invented).
* self-supervised, clearly NOT G2: `first_sentence`: a reasoning paragraph's first sentence (8 words or more) of each sampled order, target = that order; `dropout`: the same sentence with
  every third content word removed (a crude paraphrase), target = that order. These measure whether a chunking strategy keeps a sentence findable among other orders' near-duplicate
  boilerplate, not recall of court-cited precedents. Every strategy's chunks contain the sentence verbatim, so differences come from how the chunk dilutes it.

Corpus: `n_docs` orders sampled by a CRC of the doc id from the splitter's parts file (default 300 orders); queries: one per order and kind (default 300 each).
Run: `python -m vakeel_sahayak.eval.studies s16 --out <dir> [--n 300]` (a few minutes; `--n 60` for a quick look).
"""

from __future__ import annotations

import json
import re
import zlib
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval.studies.common import write_result
from vakeel_sahayak.pipelines.text_utils import paragraph_blocks, split_sentences
from vakeel_sahayak.schemas.enums import OrderPart

STOP = frozenset("the a an of to in and or for on by with that this is are was were be been as at from it its which who whom not no".split())
MIN_WORDS = 8


def parts_path() -> Path:
    from vakeel_sahayak.config import load_config

    return Path(load_config().paths.data_dir) / "interim" / "t1_work" / "parts.jsonl"


def first_sentence(parts: dict[str, str]) -> str | None:
    """The first sentence of at least `MIN_WORDS` words in the reasoning part's paragraphs (the 3rd paragraph on, to skip the opening formula), else None."""
    blocks = paragraph_blocks(parts.get("reasoning", ""))
    for block in blocks[2:] or blocks:
        for sent in split_sentences(re.sub(r"^\s*\d+\s*[.)]\s*", "", block)):
            if len(sent.split()) >= MIN_WORDS:
                return sent.strip()
    return None


def dropout(sentence: str) -> str:
    """The sentence without every third content word (stop words stay): a deterministic crude paraphrase."""
    out, k = [], 0
    for w in sentence.split():
        if w.lower().strip(".,;:()\"'") not in STOP:
            k += 1
            if k % 3 == 0:
                continue
        out.append(w)
    return " ".join(out)


def load_corpus(n_docs: int, path: Path | None = None, wanted: set[str] | None = None) -> list[dict[str, Any]]:
    """`n_docs` orders sampled by `crc32(doc_id) % 64 == 0` (about 1 in 64) plus any `wanted` doc ids, from the parts file; rows `{doc_id, court, date, parts: {OrderPart: text}, raw}`."""
    p = path or parts_path()
    if not p.is_file():
        raise FileNotFoundError(f"no parts file at {p}: build the T1 work files first (docs/handoff/data-and-models.md)")
    docs: list[dict[str, Any]] = []
    sampled = 0
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            did = str(row["doc_id"])
            gold = bool(wanted and did in wanted)
            if not gold and not (sampled < n_docs and zlib.crc32(did.encode()) % 64 == 0):
                continue
            parts = {k: str(v) for k, v in (row.get("parts") or {}).items() if v}
            if not parts.get("reasoning"):
                continue
            sampled += int(not gold)
            docs.append({"doc_id": did, "court": row.get("court"), "date": row.get("date"), "raw": parts, "gold": gold,
                         "parts": {OrderPart(k): v for k, v in parts.items() if k in {o.value for o in OrderPart}}})
    return docs


def g2_cases() -> list[dict[str, Any]]:
    """T1 dev and open orders with a resolved court-cited precedent (G2): `{query: the facts, gold: [doc ids], before}`. Never reads the blind slice's ids."""
    from vakeel_sahayak.eval import feature_common as fc
    from vakeel_sahayak.eval.scoring.loader import resolve_slice_ids

    ids = resolve_slice_ids("dev", "agreed") | resolve_slice_ids("open", "agreed")
    out = []
    for name in ("dev.jsonl", "cases.jsonl"):
        for r in fc.read_jsonl(fc.t1_dir() / name):
            gold = list((r.get("gold", {}).get("G2", {}) or {}).get("labels") or [])
            if str(r["case_id"]) in ids and gold:
                out.append({"query": str(r.get("facts_text") or "")[:600], "gold": gold, "before": r.get("before")})
    return out


def run(out_dir: str, n: int | None = None, seed: int = 0, *, strategies: tuple[str, ...] | None = None, parts_file: str | None = None, ks: tuple[int, ...] = (5, 10, 20),
        use_g2: bool = True, late_embedder: str | Any = "hashed") -> dict[str, Any]:
    """The chunking study; writes `s16.json` and `s16.md` under `out_dir`.

    Args:
        out_dir: output directory
        n: orders in the corpus and queries per kind (default 300)
        seed: unused (sampling is by a hash of the doc id); kept for the common signature
        strategies: subset of `stores.chunk_strategies.STRATEGIES` (default all)
        parts_file: the splitter's parts file (default `<data>/interim/t1_work/parts.jsonl`)
        ks: recall cut-offs
        use_g2: look for resolvable G2 queries (needs T1 files)
        late_embedder: 'hashed' (default, unchanged: the blend approximation of late chunking) or 'bge-m3' (S16b with true late chunking over BGE-M3 token vectors; opt-in, needs torch and
            models/hf/BAAI--bge-m3, slow on CPU, so only the control `structure` and `late` are run, both on BGE-M3; an embedder object with `embed_tokens` is also accepted)
    """
    from vakeel_sahayak.eval.baselines.chunking_variants import evaluate_strategy
    from vakeel_sahayak.stores.chunk_strategies import STRATEGIES

    n_docs = n or 300
    cases: list[dict[str, Any]] = []
    if use_g2:
        try:
            cases = g2_cases()
        except (FileNotFoundError, OSError, KeyError, ValueError):
            cases = []
    docs = load_corpus(n_docs, Path(parts_file) if parts_file else None, {g for c in cases for g in c["gold"]})
    present = {d["doc_id"] for d in docs}
    g2 = [{**c, "gold": [g for g in c["gold"] if g in present]} for c in cases if any(g in present for g in c["gold"])]
    sets: dict[str, list[dict[str, Any]]] = {"first_sentence": [], "dropout": []}
    for d in docs:
        s = first_sentence(d["raw"])
        if s:
            sets["first_sentence"].append({"query": s, "gold": [d["doc_id"]]})
            sets["dropout"].append({"query": dropout(s), "gold": [d["doc_id"]]})
    if g2:
        sets["g2"] = g2
    names = strategies or STRATEGIES
    embedder = None
    if late_embedder != "hashed":
        if late_embedder in ("bge-m3", "bge_m3"):
            from vakeel_sahayak.stores.late_encoder import BgeM3TokenEmbedder

            embedder = BgeM3TokenEmbedder()
        else:
            embedder = late_embedder
        names = tuple(x for x in ("structure", "late") if x in (strategies or ("structure", "late")))  # the control and S16b, on the same embedder
    results: dict[str, dict[str, Any]] = {}
    rows = []
    for kind, queries in sets.items():
        for s in names:
            r = evaluate_strategy(s, docs, queries, ks=ks, **({"embedder": embedder} if embedder is not None else {}))
            results.setdefault(kind, {})[s] = r
            rows.append([kind, f"{s} ({'S16' if s == 'proposition' else 'S16b' if s == 'late' else 'control' if s == 'structure' else 'B3'})", len(queries),
                         *[r["recall"][str(k)] for k in ks], r["mrr"], r["index"]["chunks"], r["index"]["mean_tokens"]])
    out = {"n_docs": len(docs), "queries": {k: len(v) for k, v in sets.items()}, "g2_resolvable_queries": len(g2), "ks": list(ks), "results": results,
           "targets": {"g2": "facts of T1 dev/open orders whose cited judgments are in the corpus (n above; 0 means no G2 number exists)",
                       "first_sentence": "self-supervised, NOT G2: first sentence of a reasoning paragraph, target = its order",
                       "dropout": "self-supervised, NOT G2: the same sentence with every third content word removed"},
           "embedder": "offline hashed n-gram (the stores' own embedder is not used: the corpus is re-chunked in memory)" if embedder is None else f"{getattr(embedder, 'name', 'custom')} with token vectors (structure and late only)"}
    notes = [f"Corpus: {len(docs)} orders from the splitter's parts file. G2 queries resolvable in this corpus: {len(g2)}" + (" (none: the cited Supreme Court judgments are not in the parts file, so there is no G2 recall to report)" if not g2 else "") + ".",
             "first_sentence and dropout are self-supervised proxies, NOT G2 (target = the order the sentence came from); they measure findability of a sentence among near-duplicate boilerplate, not recall of court-cited precedents.",
             "late = approximation (blend of chunk and document vectors) with the hashed embedder; true late chunking needs token vectors from the long-context embedder. Recall at document level, equal corpus for every strategy; index size is in the last two columns."]
    return write_result(out_dir, "s16", out, "S16/S16b: chunk granularity (retrieval only, preliminary)",
                        "Recall@k by chunking strategy on a re-chunked sample of orders; offline, hashed embedder; self-supervised targets unless the G2 row is present.",
                        ["Target", "Strategy (arm)", "Queries", *[f"Recall@{k}" for k in ks], "MRR", "Chunks", "Mean tokens/chunk"], rows, notes)
