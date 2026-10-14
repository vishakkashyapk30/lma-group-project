"""Store classes and registry mapping (plan §5.1 'The stores', §2 leakage, §5.5).

Static, class-level checks that pass on the skeleton: names, shelves, index kinds, base classes, the STORE_CLASSES table,
the `before` parameter on every shared-store search, ReasoningStore's reasoning-only default, and that the advocacy
stores expose no way to obtain an authority citation (plan §5.1 'never cited as authority', §5.2).
"""

from __future__ import annotations

import importlib
import inspect
import re

import pytest

from vakeel_sahayak.schemas.enums import OrderPart, Shelf, StoreName
from vakeel_sahayak.stores.base import CaseStore, SharedStore, Store
from vakeel_sahayak.stores.registry import STORE_CLASSES

# Plan §5.1: store -> (shelf, keyword that its index kind must mention, shared or case)
PLAN_TABLE = {
    "law.statutes": (Shelf.LAW, "exact", "shared"),
    "law.concordance": (Shelf.LAW, "graph", "shared"),
    "caselaw.reasoning": (Shelf.CASELAW, "hybrid", "shared"),
    "caselaw.citations": (Shelf.CASELAW, "graph", "shared"),
    "caselaw.similar": (Shelf.CASELAW, "vector", "shared"),
    "advocacy.arguments": (Shelf.ADVOCACY, "hybrid", "shared"),
    "advocacy.objections": (Shelf.ADVOCACY, "hybrid", "shared"),
    "case.docs": (Shelf.CASE, "hybrid", "case"),
    "case.timeline": (Shelf.CASE, "exact", "case"),
    "case.facts": (Shelf.CASE, "exact", "case"),
}


def resolve(dotted: str) -> type:
    module, _, cls = dotted.rpartition(".")
    return getattr(importlib.import_module(module), cls)


def store_class(name: str) -> type:
    return resolve(STORE_CLASSES[name])


def test_store_classes_has_exactly_the_ten_plan_stores():
    """STORE_CLASSES keys are exactly the ten dotted store names of plan §5.1 and of StoreName."""
    assert set(STORE_CLASSES) == set(PLAN_TABLE)
    assert set(STORE_CLASSES) == {s.value for s in StoreName}
    assert len(STORE_CLASSES) == 10


@pytest.mark.parametrize("name", sorted(PLAN_TABLE))
def test_dotted_path_resolves_to_class_with_matching_name(name):
    """Each dotted path resolves to a Store subclass whose `name` is that store's StoreName."""
    cls = store_class(name)
    assert inspect.isclass(cls) and issubclass(cls, Store)
    assert cls.name == StoreName(name)
    assert cls.name.value == name


@pytest.mark.parametrize("name", sorted(PLAN_TABLE))
def test_store_class_attributes(name):
    """Each store class declares name, shelf and a non-empty index_kind."""
    cls = store_class(name)
    assert isinstance(cls.name, StoreName)
    assert isinstance(cls.shelf, Shelf)
    assert isinstance(cls.index_kind, str) and cls.index_kind.strip()


@pytest.mark.parametrize("name", sorted(PLAN_TABLE))
def test_shelf_matches_plan_table(name):
    """Shelf follows plan §5.1: law.*, caselaw.*, advocacy.*, case.* (and the dotted prefix equals the shelf)."""
    shelf, _, _ = PLAN_TABLE[name]
    cls = store_class(name)
    assert cls.shelf == shelf
    assert name.split(".")[0] == cls.shelf.value


@pytest.mark.parametrize("name", sorted(PLAN_TABLE))
def test_index_kind_matches_plan_table(name):
    """Index kind mentions the plan's index (exact lookup, graph, hybrid, vectors)."""
    _, keyword, _ = PLAN_TABLE[name]
    assert keyword in store_class(name).index_kind.lower()


@pytest.mark.parametrize("name", sorted(PLAN_TABLE))
def test_shared_and_case_base_classes(name):
    """law/caselaw/advocacy stores are SharedStore (read-only at run time); case.* stores are CaseStore."""
    _, _, kind = PLAN_TABLE[name]
    cls = store_class(name)
    if kind == "shared":
        assert issubclass(cls, SharedStore) and not issubclass(cls, CaseStore)
    else:
        assert issubclass(cls, CaseStore) and not issubclass(cls, SharedStore)


@pytest.mark.parametrize("name", sorted(PLAN_TABLE))
def test_store_classes_are_concrete(name):
    """No abstract methods are left unimplemented (the store can be instantiated)."""
    assert not inspect.isabstract(store_class(name))


def test_stores_yaml_mirrors_plan_shelves(load_yaml):
    """configs/stores.yaml groups the ten stores under the four shelves with the same names."""
    cfg = load_yaml("stores.yaml")
    flat = {f"{shelf}.{store}" for shelf in ("law", "caselaw", "advocacy", "case") for store in cfg[shelf]}
    assert flat == set(PLAN_TABLE)


def test_argument_store_never_cited_as_authority_in_config(load_yaml):
    """advocacy.arguments is flagged never_cited_as_authority (plan §5.1)."""
    assert load_yaml("stores.yaml")["advocacy"]["arguments"]["never_cited_as_authority"] is True


def test_chunk_limit_in_config_is_400(load_yaml):
    """caselaw.reasoning chunk_max_tokens is 400 (plan §5.2)."""
    assert load_yaml("stores.yaml")["caselaw"]["reasoning"]["chunk_max_tokens"] == 400


# ----------------------------------------------------------------- leakage: `before` on every shared search
SEARCH_METHODS = [
    ("caselaw.reasoning", "search"),
    ("caselaw.similar", "similar"),
    ("advocacy.arguments", "search"),
    ("advocacy.objections", "search"),
]


@pytest.mark.parametrize(("name", "method"), SEARCH_METHODS)
def test_shared_search_methods_take_before(name, method):
    """Every dated shared-store search takes a `before` parameter (plan §2: queries see only earlier documents)."""
    params = inspect.signature(getattr(store_class(name), method)).parameters
    assert "before" in params


@pytest.mark.parametrize(("name", "method"), SEARCH_METHODS)
def test_before_is_keyword_friendly_and_optional_in_signature(name, method):
    """`before` is a normal named parameter (tools pass it by keyword); the guard, not the signature, enforces presence."""
    p = inspect.signature(getattr(store_class(name), method)).parameters["before"]
    assert p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    assert p.default is None  # the guard (apply_before_filter) raises on None/empty; see test_leakage_guard.py


def test_reasoning_search_default_part_is_reasoning():
    """Authorities come from reasoning paragraphs only: ReasoningStore.search defaults part=OrderPart.REASONING (plan §5.2)."""
    params = inspect.signature(store_class("caselaw.reasoning").search).parameters
    assert params["part"].default is OrderPart.REASONING


def test_reasoning_search_accepts_before_and_filters():
    """ReasoningStore.search exposes the plan §6.3 retrieval args: factor, section_family, before, outcome, court, k."""
    params = inspect.signature(store_class("caselaw.reasoning").search).parameters
    assert {"query", "factor", "section_family", "before", "outcome", "court", "k"} <= set(params)
    assert params["k"].default == 10


@pytest.mark.parametrize("name", ["advocacy.arguments", "advocacy.objections"])
def test_advocacy_stores_expose_no_citation_or_authority_method(name):
    """Submissions are for coverage and phrasing only: no public attribute mentions citation/authority/cite (plan §5.1)."""
    cls = store_class(name)
    public = [n for n in dir(cls) if not n.startswith("_")]
    offenders = [n for n in public if re.search(r"cit|authorit", n, re.IGNORECASE)]
    assert offenders == []


@pytest.mark.parametrize("name", ["advocacy.arguments", "advocacy.objections"])
def test_advocacy_stores_have_no_part_parameter_to_reach_reasoning(name):
    """The advocacy stores' search cannot be redirected to reasoning paragraphs (no `part` parameter)."""
    assert "part" not in inspect.signature(store_class(name).search).parameters


def test_similar_store_has_no_grant_rate_method():
    """Plan §1.3: no grant rates; SimilarStore exposes only `similar` plus the base API."""
    public = {n for n in dir(store_class("caselaw.similar")) if not n.startswith("_")}
    assert not [n for n in public if re.search(r"rate|predict|probab", n, re.IGNORECASE)]
