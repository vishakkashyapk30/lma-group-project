"""Feature evaluation F5: Court-ready application vs one-call application. Test set: T1, G3 dates, format rules. Metrics: section compliance; List of Dates precision/recall vs G3; dates without source; annexure index matches uploads (plan §15.6).

Test set: T1 dev cases (`data/testsets/t1/dev.jsonl`; `VS_FEATURE_CASES` points at another file) with at least one G3 event date (`event=YYYY-MM-DD`).
Arms (one directory each, one JSON file per case):

- `application`: the Full pipeline (`system_runner("full")`), then `export.application.assemble_application_docx` with the brief, the dossier and
  `case.timeline` of that run. The written DOCX is read back: a section counts as present when its body holds text outside `[...]` placeholders, the
  paragraph numbers and the builder's fixed lines ("MOST RESPECTFULLY SHOWETH:", "No dated events are on record."), and the List of Dates rows are read
  from its table (a row whose source reads "No source on record" has none). With the offline stand-ins Peshkar extracts little from T1 facts, so the
  List of Dates is often empty offline; the arm measures the real extractor only on a hosted model or Ada.
- `one_call`: one structured call writes the whole application from the pseudonymised facts (B0-style, no retrieval, no tools): the eleven sections as
  fields, the List of Dates as {date, event, source}. A section is present when its field is not empty.

T1 cases are text only (no uploaded files), so `annexure_matches_uploads` is left out and `annexure_match_rate` is not reported; T2 bundles would test it.
Offline stand-in models by default: the one-call arm then comes from a rule-based stand-in (dates found in the facts, no sources), so the numbers
describe the harness, not a model.

`score` reads one arm's directory, one JSON file per case with `required_sections_present`, `required_sections_total`, `lod_dates`, `gold_dates`
(G3 dates), `dates_without_source`, `dates_total` and, when the case has uploads, `annexure_matches_uploads`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from vakeel_sahayak.eval import feature_common as fc
from vakeel_sahayak.export.sections import APPLICATION_SECTIONS

ARMS = ("application", "one_call")
TASK = "f5.one_call_application"
NO_SOURCE = "No source on record"
_PLACEHOLDER = re.compile(r"\[[^\]]*\]")
_DATE_IN_TEXT = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{4})\b")


class OneCallDate(BaseModel):
    """One row of the one-call List of Dates."""

    date: str
    event: str = ""
    source: str | None = None


class OneCallApplication(BaseModel):
    """The whole application in one call: one field per section of plan §8.2 (`export/sections.py`)."""

    cause_title: str = ""
    heading: str = ""
    synopsis: str = ""
    list_of_dates: list[OneCallDate] = Field(default_factory=list)
    brief_facts: str = ""
    earlier_bail_applications: str = ""
    grounds: list[str] = Field(default_factory=list)
    statutory_position: str = ""
    prayer: str = ""
    verification_and_affidavit: str = ""
    annexure_index: list[str] = Field(default_factory=list)


ONE_CALL_FIELDS = {  # section id -> field of OneCallApplication
    "cause_title": "cause_title", "heading_s483_bnss": "heading", "synopsis": "synopsis", "list_of_dates_and_events": "list_of_dates",
    "brief_facts": "brief_facts", "earlier_bail_applications": "earlier_bail_applications", "grounds": "grounds",
    "statutory_position": "statutory_position", "prayer": "prayer", "verification_and_affidavit": "verification_and_affidavit",
    "annexure_index": "annexure_index",
}  # fmt: skip


def gold_dates(case: dict[str, Any]) -> list[str]:
    """The G3 event dates of a T1 case (`event=YYYY-MM-DD` labels)."""
    labels = (case.get("gold", {}).get("G3") or {}).get("labels") or []
    return sorted({lab.split("=", 1)[1] for lab in labels if isinstance(lab, str) and lab.startswith("event=")})


def _filled(text: str) -> bool:
    """True when the text says something besides bracketed placeholders."""
    return bool(re.search(r"\w", _PLACEHOLDER.sub("", text or "")))


def docx_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split the text lines of an application DOCX into its sections at the heading lines of `export/application.py`."""
    from vakeel_sahayak.export.application import HEADING, SECTION_HEADINGS
    from vakeel_sahayak.export.docx_style import BANNER
    from vakeel_sahayak.schemas.bail_brief import DRAFT_LABEL

    by_heading = {h: s for s, h in SECTION_HEADINGS.items()}
    out: dict[str, list[str]] = {s: [] for s in APPLICATION_SECTIONS}
    current = "cause_title"
    for line in lines:
        text = line.strip()
        if not text or text == BANNER or text.startswith(DRAFT_LABEL):
            continue
        if text == HEADING:
            out["heading_s483_bnss"].append(text)
            current = "heading_s483_bnss"
        elif text in by_heading:
            current = by_heading[text]
        else:
            out[current].append(text)
    return out


def application_payload(path: str, case: dict[str, Any]) -> dict[str, Any]:
    """F5 payload of a written application DOCX."""
    from vakeel_sahayak.export.application import SHOWETH
    from vakeel_sahayak.export.list_of_dates import NO_EVENTS
    from vakeel_sahayak.pipelines.text_utils import normalise_date

    sections = docx_sections(docx_lines(path))
    boilerplate = {SHOWETH, NO_EVENTS}  # lines the builder writes whatever the case holds: not content
    present = sum(_filled(" ".join(re.sub(r"^\d+\.\s*", "", x) for x in sections[s] if x not in boilerplate)) for s in APPLICATION_SECTIONS)
    rows = [r.split(" | ") for r in sections["list_of_dates_and_events"] if r.count(" | ") == 2]
    dated = [(normalise_date(r[0]), r[2]) for r in rows if normalise_date(r[0])]
    return {"required_sections_present": present, "required_sections_total": len(APPLICATION_SECTIONS),
            "lod_dates": sorted({d for d, _ in dated}), "gold_dates": gold_dates(case),
            "dates_without_source": sum(1 for _, src in dated if src.strip() in ("", NO_SOURCE)), "dates_total": len(dated)}  # fmt: skip


def docx_lines(path: str) -> list[str]:
    """Paragraph and table-row text of a DOCX in document order (cells joined by ' | '), then header and footer."""
    import docx

    doc = docx.Document(path)
    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append("".join(t.text or "" for t in child.iter() if t.tag.endswith("}t")))
        elif tag == "tbl":
            for tr in (el for el in child.iter() if el.tag.endswith("}tr")):
                cells = [el for el in tr if el.tag.endswith("}tc")]
                lines.append(" | ".join("".join(t.text or "" for t in c.iter() if t.tag.endswith("}t")) for c in cells))
    for sec in doc.sections:
        lines += [p.text for p in sec.header.paragraphs] + [p.text for p in sec.footer.paragraphs]
    return lines


def one_call_payload(value: OneCallApplication, case: dict[str, Any]) -> dict[str, Any]:
    """F5 payload of a one-call application: present sections are the non-empty fields."""
    from vakeel_sahayak.pipelines.text_utils import normalise_date

    def present(field: str) -> bool:
        v = getattr(value, field)
        return any(_filled(x if isinstance(x, str) else x.event or x.date) for x in v) if isinstance(v, list) else _filled(v)

    dated = [(normalise_date(r.date), r.source) for r in value.list_of_dates if normalise_date(r.date)]
    return {"required_sections_present": sum(present(ONE_CALL_FIELDS[s]) for s in APPLICATION_SECTIONS), "required_sections_total": len(APPLICATION_SECTIONS),
            "lod_dates": sorted({d for d, _ in dated}), "gold_dates": gold_dates(case),
            "dates_without_source": sum(1 for _, src in dated if not (src or "").strip()), "dates_total": len(dated)}  # fmt: skip


INSTRUCTIONS = (
    "Write a regular bail application under Section 483 BNSS for an Indian High Court from the facts, as one JSON object with these fields: "
    "cause_title, heading, synopsis, list_of_dates (each {date: YYYY-MM-DD, event, source: where in the facts the date is stated, or null}), "
    "brief_facts, earlier_bail_applications, grounds (a list), statutory_position, prayer, verification_and_affidavit, annexure_index (a list of "
    "the uploaded documents with their pages). Use square-bracketed placeholders for names and details you do not have. Never predict the outcome."
)


def _register_offline() -> None:
    from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler
    from vakeel_sahayak.pipelines.text_utils import normalise_date

    def handler(req: OfflineRequest) -> dict[str, Any]:
        """Rule stand-in: the dates written in the facts (no sources), the first sentence as synopsis, a fixed heading and prayer."""
        facts = str(req.case.get("facts") or "")
        dates = sorted({d for d in (normalise_date(m) for m in _DATE_IN_TEXT.findall(facts)) if d})
        first = re.split(r"(?<=[.!?])\s+", facts.strip(), maxsplit=1)[0] if facts.strip() else ""
        return {"heading": "Application under Section 483 BNSS for grant of regular bail", "synopsis": first[:400],
                "list_of_dates": [{"date": d, "event": "", "source": None} for d in dates], "brief_facts": facts[:800],
                "prayer": "It is prayed that the applicant be released on regular bail."}  # fmt: skip

    register_offline_handler(TASK, handler)


_register_offline()


def one_call(case: dict[str, Any]) -> OneCallApplication:
    """The one-call arm: pseudonymised facts (as the intake files them), one structured call, no retrieval and no tools."""
    from vakeel_sahayak.eval.baselines.common import resolve_llm
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.models.json_schema import schema_of
    from vakeel_sahayak.models.prompting import render_prompt
    from vakeel_sahayak.orchestration.structured_output import StructuredOutputError, structured_call

    ctx = driver.build_context(case)
    facts = driver.file_facts(ctx, case, shelve=False)
    data = {"case": {"case_id": case["case_id"], "facts": facts, "uploaded_documents": []}}
    prompt = render_prompt(TASK, INSTRUCTIONS, data, system="You assist legal-aid counsel in India. You never predict outcomes.", schema=schema_of(OneCallApplication))
    try:
        res = structured_call(resolve_llm(ctx), prompt, OneCallApplication, max_tokens=3072, temperature=0.0, retries=2)
    except StructuredOutputError:
        return OneCallApplication()
    return res.value if isinstance(res.value, OneCallApplication) else OneCallApplication.model_validate(res.value)


def application(case: dict[str, Any], out_dir: str) -> dict[str, Any]:
    """The system arm: the Full pipeline, then the court-ready application built from its brief, dossier and timeline."""
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.eval.runners.systems import system_runner
    from vakeel_sahayak.export.application import assemble_application_docx
    from vakeel_sahayak.record.case_state import CaseState
    from vakeel_sahayak.schemas.bail_brief import BailBrief

    runner, switches = system_runner("full")
    ctx = driver.build_context(case, switches)
    produced = runner(case, ctx)
    brief = produced if isinstance(produced, BailBrief) else produced.get("_brief_obj") or BailBrief(case_id=case["case_id"])
    state = CaseState(case["case_id"], ctx.log)
    path = fc.arm_dir(out_dir, "application") / f"{case['case_id']}.docx"
    assemble_application_docx(brief, state.dossier(), state.timeline(), [], str(path))
    return {**application_payload(str(path), case), "docx": Path(path).name, "errors": (getattr(ctx, "eval_record", None) or {}).get("errors", [])}


def pick_cases(n: int | None) -> list[dict[str, Any]]:
    """T1 cases with at least one G3 event date (the first `n`; default 3)."""
    path = os.environ.get("VS_FEATURE_CASES") or str(fc.t1_dir() / "dev.jsonl")
    return [r for r in fc.read_jsonl(path) if gold_dates(r)][: n or 3]


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F5 (system and comparison arms), resumable.

    Args:
        out_dir: results directory; one sub-directory per arm (`application`, `one_call`), one `<case id>.json` per case (and the DOCX for `application`)
        shard: this shard's index
        n_shards: the number of shards (cases are dealt out by index)
    """
    cases = fc.shard_slice(pick_cases(fc.env_limit()), shard, n_shards)
    for arm in fc.selected_arms(ARMS):
        for case in cases:
            if fc.case_file(out_dir, arm, case["case_id"]).exists():
                continue
            payload = application(case, out_dir) if arm == "application" else {**one_call_payload(one_call(case), case), "llm": fc.llm_backend()}
            fc.save_case(out_dir, arm, case["case_id"], {"arm": arm, **payload})


def score(run_dir: str) -> dict[str, float]:
    """Compute F5 metrics for one arm directory.

    Args:
        run_dir: an arm's directory (see the module docstring for the keys)

    Returns:
        `section_compliance` (required sections present over required, micro), `lod_precision` and `lod_recall` (List of Dates against the G3 dates, macro over cases with dates),
        `dates_without_source_rate` (micro), `annexure_match_rate` (share of cases whose annexure index matches the uploaded files).

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    prf = [fc.set_prf(r.get("lod_dates", []), r.get("gold_dates", [])) for r in rows]
    out = {
        "section_compliance": fc.rate(sum(r["required_sections_present"] for r in rows), sum(r["required_sections_total"] for r in rows)),
        "lod_precision": fc.mean(p[1] for p in prf if p[1] is not None),
        "lod_recall": fc.mean(p[0] for p in prf if p[0] is not None),
        "dates_without_source_rate": fc.rate(sum(r["dates_without_source"] for r in rows), sum(r["dates_total"] for r in rows)),
        "annexure_match_rate": fc.mean(float(bool(r["annexure_matches_uploads"])) for r in rows if "annexure_matches_uploads" in r),
    }
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
