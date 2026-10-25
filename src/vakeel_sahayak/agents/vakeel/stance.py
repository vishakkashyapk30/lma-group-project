"""Which side an authority is on: the outcome of the order it comes from (variant switch `authority_stance='outcome'`).

A bail brief argues for the accused, so a paragraph taken from an order that REFUSED bail states the State's point, not
counsel's. The drafter used to be offered retrieved paragraphs in retrieval order whatever the order's result, and a ground
could cite a refusal as if it supported bail (hosted pilot, t1dev-001 G1). With `Switches.authority_stance='outcome'`:

* the stance of a paragraph is read from the `outcome` of its order, which the store builders took from the order's operative
  part (`pipelines/order_splitter.infer_outcome`): 'granted' supports bail, 'rejected' is adverse, anything else is unknown. No
  label is written by hand and no model is asked;
* supporting paragraphs come first, unknown ones next; adverse ones are left out when anything else is available, and are offered
  only when nothing else is (or when the factor itself is the State's adverse point to answer), each marked as adverse;
* the drafting prompt says an adverse authority may only be cited to distinguish it, and a Warning note naming it as adverse
  authority to distinguish is added to every ground that cites one (same mechanism as the overruled-authority warning).

Idea: retrieving the strongest counter-argument to a claim as a separate kind of evidence, not as support (Wachsmuth et al.,
"Retrieval of the Best Counterargument without Prior Topic Knowledge", ACL 2018, https://aclanthology.org/P18-1023/); here the
counter-evidence is a precedent that went against the accused. Default (`authority_stance='off'`) is byte-identical to before.
"""

from __future__ import annotations

from typing import Any

SUPPORTS, ADVERSE, UNKNOWN = "supports", "adverse", "unknown"
_RANK = {SUPPORTS: 0, UNKNOWN: 1, ADVERSE: 2}
_LABEL = {
    SUPPORTS: "supports bail: the order granted it",
    ADVERSE: "adverse: the order refused bail; cite only to distinguish it on facts, never as support",
    UNKNOWN: "outcome of the order not recorded",
}
ADVERSE_INSTRUCTION = (
    " Each authority carries a 'decision' field. An authority whose decision says adverse went against bail: never cite it as support for "
    "counsel's side; cite it only in a sentence that says it is adverse authority and distinguishes it on the facts, and prefer the authorities "
    "that support bail."
)


def stance_of(item: dict[str, Any]) -> str:
    """'supports', 'adverse' or 'unknown' for a retrieved paragraph, from its order's outcome ('granted' or 'rejected')."""
    outcome = str(getattr(item.get("outcome"), "value", item.get("outcome")) or "").strip().lower()
    if outcome == "granted":
        return SUPPORTS
    if outcome in ("rejected", "dismissed", "refused"):
        return ADVERSE
    return UNKNOWN


def arrange(cands: list[dict[str, Any]], factor_stance: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Order the candidates by stance, mark each with its decision, and drop adverse ones when better ones exist.

    Args:
        cands: authority dicts in retrieval order (each may hold 'outcome')
        factor_stance: the factor's stance ('adverse' means the State's point is the topic, so adverse precedents are kept and marked)

    Returns:
        (the arranged list, 'doc#para' of the adverse paragraphs left out). Order inside one stance is the retrieval order.
    """
    marked = [{**c, "stance": stance_of(c), "decision": _LABEL[stance_of(c)]} for c in cands]
    marked.sort(key=lambda c: _RANK[c["stance"]])  # stable: retrieval order within a stance
    if factor_stance == "adverse" or all(c["stance"] == ADVERSE for c in marked):
        return marked, []
    keep = [c for c in marked if c["stance"] != ADVERSE]
    return keep, [f"{c['doc_id']}#{c['para']}" for c in marked if c["stance"] == ADVERSE]
