"""Shared gold-label logic: keyword rules + Llama-3.1-8B, agreed labels only, with agreement stats (plan §15.1).

The rule labelers are implemented in g1..g7. Every module's `build_gold(parts_path, out_path)` and `label_order(parts)` take
the labeler from `active_labeler()` (`models.labeler.EvalLabeler`, or a client given to `set_labeler`; while the Llama
client is a stub the records are provisional `rule_only`). `LabelerClient` is the protocol,
`merge_labels` keeps agreed labels only and `AgreementReport` carries the numbers for the label-sensitivity report
(plan §15.9). No model is called from this package, and Qwen output is never used as gold (plan §15.1).

Each module has `label_detail(parts)` (the full record below, used by `build_gold`) and `label_order(parts)` (the same
without `rule_labels` and `llm_labels`, so only agreed labels are visible to callers).

Gold record format (one JSON object per order, written by each `build_gold`):
`{"doc_id", "gold": "G1", "rule_labels": [...], "llm_labels": [...] | null, "labels": [...], "status": "agreed" | "rule_only", ...}`.
`labels` is the agreed intersection when a labeler was supplied; with no labeler it equals `rule_labels` and `status` is
`rule_only` (provisional, not yet gold).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from vakeel_sahayak.pipelines.text_utils import read_jsonl, write_jsonl
from vakeel_sahayak.schemas.enums import Factor, OrderPart

_OVERRIDE: list[LabelerClient | None] = []


def set_labeler(client: LabelerClient | None) -> None:
    """Use `client` as the evaluation labeler of every gold module (None goes back to `models.labeler.EvalLabeler`)."""
    _OVERRIDE[:] = [client] if client is not None else []


def active_labeler() -> LabelerClient:
    """The labeler the gold modules consult: the one given to `set_labeler`, else Llama-3.1-8B (`EvalLabeler`)."""
    if _OVERRIDE:
        return _OVERRIDE[0]  # type: ignore[return-value]
    from vakeel_sahayak.models.labeler import EvalLabeler

    return EvalLabeler()


class LabelerClient(Protocol):
    """Client protocol of the evaluation labeler (Llama-3.1-8B, plan §12, §15.1); `models.labeler.EvalLabeler` fits it."""

    def label(self, text: str, label_set: list[str]) -> list[str]:
        """Label text against a closed label set; returns the labels that apply."""
        ...


def agreed_labels(rule_labels: list[str], llm_labels: list[str]) -> list[str]:
    """Intersection used as gold.

    Args:
        rule_labels: see behaviour
        llm_labels: see behaviour

    Returns:
        Agreed labels, in the order of `rule_labels`, no duplicates.
    """
    other = set(llm_labels)
    seen: set[str] = set()
    out: list[str] = []
    for label in rule_labels:
        if label in other and label not in seen:
            seen.add(label)
            out.append(label)
    return out


def cohen_kappa(rule_labels: list[list[str]], llm_labels: list[list[str]]) -> float:
    """Labeler agreement for the label-sensitivity report.

    Multi-label kappa: every (item, label) pair is one binary decision by each labeler, pooled over the label set seen.

    Args:
        rule_labels: per item, the rule labeler's labels
        llm_labels: per item, the LLM labeler's labels (same length)

    Returns:
        Kappa; 1.0 when both labelers never use any label or agree on everything by construction, 0.0 for chance level.
    """
    if len(rule_labels) != len(llm_labels):
        raise ValueError("rule_labels and llm_labels must have the same number of items")
    universe = sorted({x for items in (*rule_labels, *llm_labels) for x in items})
    cells = len(rule_labels) * len(universe)
    if cells == 0:
        return 1.0
    both = a_only = b_only = 0
    for r, m in zip(rule_labels, llm_labels, strict=True):
        rs, ms = set(r), set(m)
        both += len(rs & ms)
        a_only += len(rs - ms)
        b_only += len(ms - rs)
    neither = cells - both - a_only - b_only
    observed = (both + neither) / cells
    p_a, p_b = (both + a_only) / cells, (both + b_only) / cells
    expected = p_a * p_b + (1 - p_a) * (1 - p_b)
    if expected >= 1.0:
        return 1.0 if observed >= 1.0 else 0.0
    return (observed - expected) / (1 - expected)


@dataclass
class AgreementReport:
    """Agreement of the rule labeler and the LLM labeler over a set of items (plan §15.1, §15.9)."""

    n_items: int = 0
    n_agreed: int = 0
    n_rule_only: int = 0
    n_llm_only: int = 0
    kappa: float = 1.0
    per_label: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def agreement_rate(self) -> float:
        """Share of all proposed labels (either labeler) that both proposed."""
        total = self.n_agreed + self.n_rule_only + self.n_llm_only
        return self.n_agreed / total if total else 1.0


def merge_labels(
    rule_labels: list[list[str]], llm_labels: list[list[str]]
) -> tuple[list[list[str]], AgreementReport]:
    """Keep agreed labels only, per item, and report agreement.

    Args:
        rule_labels: per item, the rule labeler's labels
        llm_labels: per item, the LLM labeler's labels (same length)

    Returns:
        (agreed labels per item, AgreementReport).
    """
    if len(rule_labels) != len(llm_labels):
        raise ValueError("rule_labels and llm_labels must have the same number of items")
    merged = [agreed_labels(r, m) for r, m in zip(rule_labels, llm_labels, strict=True)]
    report = AgreementReport(n_items=len(merged), kappa=cohen_kappa(rule_labels, llm_labels))
    per: dict[str, dict[str, int]] = {}
    for r, m, a in zip(rule_labels, llm_labels, merged, strict=True):
        for label in set(r) | set(m):
            slot = per.setdefault(label, {"agreed": 0, "rule_only": 0, "llm_only": 0})
            slot["agreed" if label in a else "rule_only" if label in r else "llm_only"] += 1
    report.per_label = per
    report.n_agreed = sum(v["agreed"] for v in per.values())
    report.n_rule_only = sum(v["rule_only"] for v in per.values())
    report.n_llm_only = sum(v["llm_only"] for v in per.values())
    return merged, report


def agreed_view(record: dict[str, Any]) -> dict[str, Any]:
    """A gold record without the per-labeler lists: what `label_order` returns (agreed labels only, plan §15.1).

    The raw `rule_labels` and `llm_labels` stay in the written records (`label_detail`) for the label-sensitivity report.
    """
    return {k: v for k, v in record.items() if k not in ("rule_labels", "llm_labels")}


def combine(rule_labels: list[str], labeler: LabelerClient | None, text: str, label_set: list[str]) -> dict[str, Any]:
    """The label fields of one gold record: rule labels, the LLM's labels when a client is given, the agreed result.

    Args:
        rule_labels: labels from the keyword or regex rules
        labeler: the evaluation labeler, or None (rule only)
        text: the text the labelers see
        label_set: closed label set offered to the LLM

    Returns:
        Dict with `rule_labels`, `llm_labels`, `labels` and `status`.
    """
    if labeler is None:
        return {"rule_labels": rule_labels, "llm_labels": None, "labels": list(rule_labels), "status": "rule_only"}
    try:
        llm = [x for x in labeler.label(text, label_set) if x in label_set]
    except NotImplementedError:  # the Llama client is not wired yet: provisional rule-only record, not gold
        return {"rule_labels": rule_labels, "llm_labels": None, "labels": list(rule_labels), "status": "rule_only"}
    return {"rule_labels": rule_labels, "llm_labels": llm, "labels": agreed_labels(rule_labels, llm), "status": "agreed"}


def run_gold(
    gold: str, parts_path: str, out_path: str, label_fn: Callable[[dict[OrderPart, str]], dict[str, Any]]
) -> int:
    """Label every order of a split file and write the gold JSONL.

    Args:
        gold: gold id such as 'G1'
        parts_path: JSONL from `order_splitter.split_all` (`doc_id`, `parts`)
        out_path: output JSONL
        label_fn: labels one order from its parts

    Returns:
        Number of orders labelled.
    """
    rows = []
    for order in read_jsonl(parts_path):
        raw = order.get("parts")
        if not isinstance(raw, dict):
            continue
        parts = {OrderPart(k): str(v) for k, v in raw.items() if k in {p.value for p in OrderPart}}
        rows.append({"doc_id": order.get("doc_id"), "gold": gold, **label_fn(parts)})
    return write_jsonl(out_path, rows)


def part_text(parts: dict[OrderPart, str], *wanted: OrderPart) -> str:
    """Joined text of the wanted parts (missing parts are empty)."""
    return "\n\n".join(parts.get(p, "") for p in wanted if parts.get(p))


# A factor is answerable from the input only if its supporting fact is stated there (plan §15.1). The rule tagger
# decides whether the topic is present; the extra checks below require the concrete fact for factors that need one.
_FACT_NEEDS: dict[Factor, str] = {
    Factor.CUSTODY_PERIOD: r"\d+\s*(?:days?|months?|years?)|since\s+\d|arrest(?:ed)?\s+on|custody\s+since",
    Factor.UNDERTRIAL_PERIOD: r"\d+\s*(?:days?|months?|years?)|since\s+\d|arrest(?:ed)?\s+on|custody\s+since",
    Factor.PARITY_WITH_CO_ACCUSED: r"co[\s-]?accused|other\s+accused|similarly\s+(?:placed|situated)",
    Factor.CHARGE_SHEET_FILED: r"charge[\s-]?sheet|final\s+report|challan|investigation",
}


def answerable_factors(input_text: str, labeler: LabelerClient | None = None) -> list[Factor]:
    """A factor is scored only if its supporting fact appears in the input (decided by both methods).

    The rule method needs the factor's keywords and, for custody, parity and charge-sheet factors, the concrete fact
    (a duration or date, a co-accused, a charge sheet or investigation status). With a labeler, only factors both
    methods find are kept.

    Args:
        input_text: the RQ1 input (facts part)
        labeler: evaluation labeler for the second opinion; None keeps the rule decision

    Returns:
        Answerable factors in Appendix A order.
    """
    import re

    from vakeel_sahayak.pipelines.factor_tagger import tag_factors

    ruled = [
        f for f in tag_factors(input_text)
        if f not in _FACT_NEEDS or re.search(_FACT_NEEDS[f], input_text, re.IGNORECASE)
    ]  # fmt: skip
    if labeler is None:
        return ruled
    label_set = [f.value for f in Factor]
    try:
        llm = set(labeler.label(input_text, label_set))
    except NotImplementedError:  # labeler not wired yet: keep the rule decision
        return ruled
    return [f for f in ruled if f.value in llm]


def factor_gold(parts: dict[OrderPart, str], part: OrderPart, labeler: LabelerClient | None = None) -> dict[str, Any]:
    """Label fields for a factor gold (G1, G4, G5): the factors the keyword rules find in one part."""
    from vakeel_sahayak.pipelines.factor_tagger import tag_factors

    text = parts.get(part, "")
    return combine([f.value for f in tag_factors(text)], labeler or active_labeler(), text, [f.value for f in Factor])
