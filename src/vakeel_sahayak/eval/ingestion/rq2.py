"""RQ2 runner and scorer: the ingestion pipelines P1-P6 and Munshi on the T2 messy bundles (plan §15.5).

Output (README C6): `<out_dir>/runs/<job>/outputs/<arm>/<bundle_id>.json` with job `rq2_vision` for P1-P4 and `rq2_full` for P5, P6 and Munshi
(`--job` overrides). One file per bundle, written when the bundle finishes, so a run resumes where it stopped (`--shard i --n-shards n` splits by
bundle index). An arm whose backend is missing writes `ARM_UNAVAILABLE.json` (reason) and no bundle files: no number is made up.

Per bundle the record holds: kind, language, pages, seconds and seconds per page, `cer` (edits over reference characters of the whole bundle, with
`cer_devanagari` and `cer_latin` over the pages of that script), `boundary_f1`, `doc_type_accuracy`, `fields` (per field correct or not, against the
construction truth), `escalation_rate`, `questions`, `unreadable_share` and the notes of the backend (for example "no Hindi data in Tesseract").
The downstream field reader is the offline rule extractor of Peshkar (the stand-in of the fine-tuned 4B that plan §15.5 names), applied to each
pipeline's page text and document labels; Munshi's scripted counsel answers are added as unlabelled passages. These are offline stand-in results.

CLI: `python -m vakeel_sahayak.eval.ingestion.rq2 run --arms p1,p2 --out DIR [--truth data/testsets/t2/truth.jsonl] [--kinds K1,K5] [--limit N]`,
`... score --out DIR [--job rq2_vision]`.
"""

from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval.ingestion import common
from vakeel_sahayak.eval.ingestion.common import ArmUnavailable

ARMS = {"p1": "p1_text_layer_only", "p2": "p2_ocr_every_page", "p3": "p3_docling_default", "p4": "p4_vision_every_page",
        "p5": "p5_fixed_cascade", "p6": "p6_no_split_label", "munshi": "munshi_full"}
JOB_OF = {"p1": "rq2_vision", "p2": "rq2_vision", "p3": "rq2_vision", "p4": "rq2_vision", "p5": "rq2_full", "p6": "rq2_full", "munshi": "rq2_full"}
MUNSHI_FAMILY = ("p5", "p6", "munshi")
DEFAULT_TRUTH = "data/testsets/t2/truth.jsonl"


@contextlib.contextmanager
def ocr_for_run(arm: str):
    """Give the Munshi family the same OCR engine P2 uses when only the offline stand-in is configured (Tesseract through its command line), for the run only.

    Without this the ladder's OCR rung cannot read a real raster page offline and every scan would end in a question, which would measure the missing engine.
    """
    from vakeel_sahayak.models import factory
    from vakeel_sahayak.models.offline import OfflineOcrClient

    swap = arm in MUNSHI_FAMILY and isinstance(factory.get_ocr(), OfflineOcrClient) and bool(common.tesseract_languages())
    if swap:
        factory.set_client("ocr", common.TesseractCliOcr())
    try:
        yield
    finally:
        if swap:
            factory.set_client("ocr", None)


def arm_module(arm: str):
    """The pipeline module of an arm id."""
    import importlib

    return importlib.import_module(f"vakeel_sahayak.eval.ingestion.{ARMS[arm]}")


def load_truth(path: str, kinds: set[str] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """T2 truth rows (optionally only some kinds; `limit` takes the first rows of each kind so a small run still covers every kind)."""
    rows = [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    if kinds:
        rows = [r for r in rows if r["kind"] in kinds]
    if limit:
        seen: dict[str, int] = defaultdict(int)
        out = []
        for r in rows:
            if seen[r["kind"]] < limit:
                seen[r["kind"]] += 1
                out.append(r)
        rows = out
    return rows


def score_bundle(arm: str, truth: dict[str, Any], result: common.BundleResult, seconds: float) -> dict[str, Any]:
    """The scored record of one bundle (see the module docstring)."""
    report = result.report
    pages_truth = [p["text"] for p in truth["pages"]]
    n = len(pages_truth)
    texts = (result.page_texts + [""] * n)[:n]
    edits, chars = {"all": 0, "devanagari": 0, "latin": 0}, {"all": 0, "devanagari": 0, "latin": 0}
    for hyp, ref in zip(texts, pages_truth, strict=True):
        ref_n = common.normalise_text(ref)
        e = common.edit_distance(common.normalise_text(hyp), ref_n)
        for key in ("all", common.script_of(ref_n)):
            edits[key] += e
            chars[key] += len(ref_n)
    pred = [tuple(d.pages) for d in report.documents]
    gold = [tuple(d["pages"]) for d in truth["documents"]]
    gold_type = {tuple(d["pages"]): common.TRUTH_DOC_TYPES.get(d["type"], d["type"]) for d in truth["documents"]}
    typed = [gold_type[g] == next((d.type.value for d in report.documents if tuple(d.pages) == g), None) for g in gold]
    fields = common.field_scores(common.read_fields(common.passages_from(report, texts, result.counsel_answers)), truth.get("fields") or {})
    return {
        "case_id": truth["bundle_id"], "bundle_id": truth["bundle_id"], "arm": arm, "kind": truth["kind"], "lang": truth["lang"], "origin": truth.get("origin"),
        "status": "ok", "pages": n, "seconds": round(seconds, 3), "seconds_per_page": round(seconds / max(1, n), 3), "gpu_seconds": None,
        "cer": edits["all"] / chars["all"] if chars["all"] else None,
        "cer_devanagari": edits["devanagari"] / chars["devanagari"] if chars["devanagari"] else None,
        "cer_latin": edits["latin"] / chars["latin"] if chars["latin"] else None,
        "boundary_f1": common.boundary_f1(pred, gold), "doc_type_accuracy": sum(typed) / len(typed) if typed else None,
        "documents_predicted": len(pred), "documents_true": len(gold),
        "fields": fields, "escalation_rate": common.escalation_rate(report), "questions": common.questions_asked(report),
        "unreadable_share": common.unreadable_share(report), "notes": result.notes,
    }


def run(arm: str, truth_path: str, out_dir: str, shard: int = 0, n_shards: int = 1, kinds: set[str] | None = None, limit: int | None = None,
        job: str | None = None, page_budget: int | None = None) -> dict[str, Any]:
    """Run one arm over the T2 bundles, resumable; returns `{"done", "skipped", "unavailable"}`.

    Args:
        arm: p1 to p6 or munshi
        truth_path: `truth.jsonl` of T2 (bundle PDFs sit under `bundles/` beside it)
        out_dir: root of the result tree
        shard: this shard's index
        n_shards: number of shards (bundles are dealt out by index)
        kinds: only these kinds (K1-K6)
        limit: first N bundles of each kind (a smoke run)
        job: job directory name (default by arm)
        page_budget: stop after this many pages (P4's 1,500-page subset)
    """
    mod = arm_module(arm)
    dest = Path(out_dir) / "runs" / (job or JOB_OF[arm]) / "outputs" / arm
    dest.mkdir(parents=True, exist_ok=True)
    ok, note = mod.availability()
    if not ok:
        (dest / "ARM_UNAVAILABLE.json").write_text(json.dumps({"arm": arm, "reason": note}, indent=1), encoding="utf-8")
        return {"done": 0, "skipped": 0, "unavailable": note}
    root = Path(truth_path).parent
    rows = load_truth(truth_path, kinds, limit)
    done = skipped = pages = 0
    takes_counsel = "counsel" in inspect.signature(mod.run_bundle).parameters
    for index, truth in enumerate(rows):
        if index % n_shards != shard:
            continue
        target = dest / f"{truth['bundle_id']}.json"
        if target.exists():
            skipped += 1
            continue
        if page_budget is not None and pages >= page_budget:
            break
        pdf = str(root / truth["pdf"])
        kwargs: dict[str, Any] = {}
        if takes_counsel:
            from vakeel_sahayak.testsets.t2_messy_bundles import scripted_counsel

            kwargs["counsel"] = scripted_counsel(truth.get("fields") or {})
        started = time.perf_counter()
        try:
            with ocr_for_run(arm):
                result = mod.run_bundle(pdf, None, **kwargs)
        except ArmUnavailable as exc:
            (dest / "ARM_UNAVAILABLE.json").write_text(json.dumps({"arm": arm, "reason": str(exc)}, indent=1), encoding="utf-8")
            return {"done": done, "skipped": skipped, "unavailable": str(exc)}
        except Exception as exc:  # noqa: BLE001 - one broken bundle is a recorded failure, not a stopped run
            target.write_text(json.dumps({"case_id": truth["bundle_id"], "arm": arm, "kind": truth["kind"], "status": "error",
                                          "error": f"{type(exc).__name__}: {exc}"[:500]}, indent=1), encoding="utf-8")
            done += 1
            continue
        record = score_bundle(arm, truth, result, time.perf_counter() - started)
        target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        pages += record["pages"]
        done += 1
    return {"done": done, "skipped": skipped, "unavailable": None}


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def score(run_dir: str) -> dict[str, dict[str, float | int | None]]:
    """Per input kind and pooled ('all'): mean over bundles of the metrics of one arm directory.

    Field accuracy is the share of (bundle, field) pairs read right; fields with fewer than 30 pairs in a kind are reported with `fields_n` so the
    reader can discount them (plan §15.8: no pooled headline from fields with n < 30).

    Raises:
        ValueError: the directory has no scored bundle (or the arm is recorded as unavailable).
    """
    d = Path(run_dir)
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json")) if p.name != "ARM_UNAVAILABLE.json"]
    rows = [r for r in rows if r.get("status") == "ok"]
    if not rows:
        note = (d / "ARM_UNAVAILABLE.json").read_text(encoding="utf-8") if (d / "ARM_UNAVAILABLE.json").exists() else "no results"
        raise ValueError(f"nothing to score in {run_dir}: {note}")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[r["kind"]].append(r)
        groups["all"].append(r)
    out: dict[str, dict[str, float | int | None]] = {}
    for kind, rs in sorted(groups.items()):
        pairs = [ok for r in rs for ok in r["fields"].values()]
        out[kind] = {
            "n": len(rs), "cer": _mean([r["cer"] for r in rs if r["cer"] is not None]),
            "cer_devanagari": _mean([r["cer_devanagari"] for r in rs if r["cer_devanagari"] is not None]),
            "cer_latin": _mean([r["cer_latin"] for r in rs if r["cer_latin"] is not None]),
            "boundary_f1": _mean([r["boundary_f1"] for r in rs]), "doc_type_accuracy": _mean([r["doc_type_accuracy"] for r in rs if r["doc_type_accuracy"] is not None]),
            "field_accuracy": sum(pairs) / len(pairs) if pairs else None, "fields_n": len(pairs),
            "escalation_rate": _mean([r["escalation_rate"] for r in rs]), "questions": _mean([r["questions"] for r in rs]),
            "seconds_per_page": _mean([r["seconds_per_page"] for r in rs]),
        }
    return out


def table(out_dir: str, job: str | None = None, arms: list[str] | None = None) -> str:
    """A text table (rows: arm and kind) of every arm found under `out_dir/runs/<job>/outputs`; unavailable arms are listed with their reason."""
    lines = ["arm      kind    n    cer    cer_dev  cer_lat  boundF1  typeAcc  fieldAcc  esc    quest  s/page"]
    notes = []
    for arm in arms or list(ARMS):
        d = Path(out_dir) / "runs" / (job or JOB_OF[arm]) / "outputs" / arm
        if not d.is_dir():
            continue
        try:
            res = score(str(d))
        except ValueError as exc:
            reason = str(exc).split("reason")[-1].strip(" :}\"")[:150]
            notes.append(f"{arm}: UNAVAILABLE ({reason})")
            continue

        def f(v: Any) -> str:
            return "  -  " if v is None else f"{v:5.2f}"

        for kind, m in res.items():
            lines.append(f"{arm:<8} {kind:<6} {m['n']:>4} {f(m['cer'])}  {f(m['cer_devanagari'])}   {f(m['cer_latin'])}   {f(m['boundary_f1'])}   {f(m['doc_type_accuracy'])}   "
                         f"{f(m['field_accuracy'])}    {f(m['escalation_rate'])}  {f(m['questions'])}  {f(m['seconds_per_page'])}")
    return "\n".join([*lines, *notes])


def main(argv: list[str] | None = None) -> int:
    """CLI (see the module docstring)."""
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--arms", default="p1,p2,p3,p4,p5,p6,munshi")
    r.add_argument("--out", required=True)
    r.add_argument("--truth", default=DEFAULT_TRUTH)
    r.add_argument("--kinds", default="")
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--shard", type=int, default=0)
    r.add_argument("--n-shards", type=int, default=1)
    r.add_argument("--p4-page-budget", type=int, default=1500)
    s = sub.add_parser("score")
    s.add_argument("--out", required=True)
    s.add_argument("--job", default=None)
    s.add_argument("--arms", default=",".join(ARMS))
    args = ap.parse_args(argv)
    if args.cmd == "run":
        for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
            res = run(arm, args.truth, args.out, args.shard, args.n_shards, set(filter(None, args.kinds.split(","))) or None, args.limit,
                      page_budget=args.p4_page_budget if arm == "p4" else None)
            print(arm, res, flush=True)
    else:
        print(table(args.out, args.job, [a for a in args.arms.split(",") if a]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
