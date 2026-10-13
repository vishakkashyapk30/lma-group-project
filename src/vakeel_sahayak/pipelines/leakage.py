"""Leakage rules for every store and the fine-tuning data (plan §2): test orders and orders with the same FIR as a test order are excluded."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from vakeel_sahayak.pipelines.text_utils import read_jsonl

_FIR_NO = re.compile(r"\bF\.?\s?I\.?\s?R\.?\s*(?:No\.?|Number)?\s*[:#-]?\s*(\d{1,6})(?:\s*(?:/|of)\s*((?:19|20)\d{2}))?", re.IGNORECASE)
_POLICE_STATION = re.compile(r"\b(?:P\.?\s?S\.?|police\s+station|thana)\s*[:.,-]?\s*([A-Z][A-Za-z ]{2,30}?)(?=[,.;:\n]|\s+(?:under|u/s|for|district|dist|on|vide)\b|$)")


def _norm(value: Any) -> str:
    """Lower-case alphanumeric key part."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def fir_key(order: dict[str, Any]) -> str | None:
    """The FIR key of an order record: police station, number and year (plus district or state when recorded).

    Taken from `fir_key` (a ready string), from flat `police_station`/`fir_number`/`fir_year` fields (the order's
    `court` is part of this key, since station names repeat across states), from `fir` ({police_station, number, year,
    district, state}), or by a regex
    over the first 3,000 characters of `text` ('FIR No. 123/2021 ... P.S. Rohini'). The court of the *order* is not part
    of the key because an HC bail order and an SC order on the same FIR must group together (plan §2).

    Args:
        order: order record

    Returns:
        Key like 'rohini|123|2021', or None when no FIR number is found.
    """
    if order.get("fir_key"):
        return _norm(order["fir_key"]) or None
    court = _norm(order.get("court"))
    if order.get("fir_number") and not isinstance(order.get("fir"), dict):
        number, year = str(order["fir_number"]), str(order.get("fir_year") or "")
        if "/" in number and not year:
            number, _, year = number.partition("/")
        return "|".join([court, _norm(order.get("police_station")), _norm(number), _norm(year)])
    fir = order.get("fir")
    if isinstance(fir, dict) and fir.get("number"):
        number = str(fir["number"])
        year = str(fir.get("year") or "")
        if "/" in number and not year:
            number, _, year = number.partition("/")
        parts = [fir.get("police_station"), number.strip(), year, fir.get("district") or fir.get("state")]
        return "|".join(_norm(p) for p in parts)
    head = str(order.get("text") or "")[:3000]
    m = _FIR_NO.search(head)
    if not m:
        return None
    ps = _POLICE_STATION.search(head)
    return "|".join([_norm(ps.group(1)) if ps else "", m.group(1), m.group(2) or "", ""])


def same_fir_groups(orders_path: str) -> dict[str, list[str]]:
    """Group orders sharing an FIR (court, police station, number, year).

    The key omits the order's own court on purpose (see `fir_key`), so it can over-group two FIRs with the same station
    name, number and year in different districts. Over-grouping only excludes more orders, which is the safe side.

    Args:
        orders_path: JSONL of order records (see `fir_key` for the FIR fields)

    Returns:
        FIR key to doc ids (every order with an FIR key, singletons included).
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for order in read_jsonl(orders_path):
        key = fir_key(order)
        if key and order.get("doc_id"):
            groups[key].append(str(order["doc_id"]))
    return dict(groups)


def excluded_doc_ids(splits_path: str, orders_path: str) -> set[str]:
    """Test orders plus same-FIR orders.

    Args:
        splits_path: file from `assign_splits` (JSON object doc id to split)
        orders_path: JSONL of order records

    Returns:
        Doc ids to exclude from stores and training.
    """
    from vakeel_sahayak.pipelines.splits import read_splits

    test_ids = {doc for doc, split in read_splits(splits_path).items() if split == "test"}
    return _with_same_fir(test_ids, orders_path)


def excluded_from_orders(orders_path: str) -> set[str]:
    """Like `excluded_doc_ids`, with the test orders read from the `split` field of the order records themselves.

    Args:
        orders_path: JSONL of order records with `doc_id` and `split`

    Returns:
        Doc ids to exclude.
    """
    test_ids = {str(o["doc_id"]) for o in read_jsonl(orders_path) if o.get("split") == "test" and o.get("doc_id")}
    return _with_same_fir(test_ids, orders_path)


def _with_same_fir(test_ids: set[str], orders_path: str) -> set[str]:
    """The test orders plus every order sharing an FIR with one of them."""
    excluded = set(test_ids)
    for members in same_fir_groups(orders_path).values():
        if test_ids.intersection(members):
            excluded.update(members)
    return excluded


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    """All word n-grams of a text (lower-case, punctuation removed)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def assert_no_overlap(facts_text: str, other_parts: list[str], n: int = 8) -> None:
    """Check RQ1 input (facts part) shares no 8-word sequence with the other parts (plan §15.1).

    Args:
        facts_text: see behaviour
        other_parts: see behaviour
        n: see behaviour

    Raises:
        ValueError: naming one shared sequence, when the facts share `n` words in a row with another part.
    """
    facts = _ngrams(facts_text, n)
    if not facts:
        return
    for part in other_parts:
        shared = facts & _ngrams(part, n)
        if shared:
            sample = " ".join(sorted(shared)[0])
            raise ValueError(f"facts share a {n}-word sequence with another part: {sample!r}")
