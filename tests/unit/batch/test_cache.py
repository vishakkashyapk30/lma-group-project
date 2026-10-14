"""Shared retrieval cache (plan §11 stage 2, §15.6 F4 cache hit-rate).

The key is the factor, section family, before-date MONTH and the query: two cases whose before-dates fall in the same
month share cache entries.
ASSUMPTIONS: `before` is an ISO date 'YYYY-MM-DD'; the order of the section family does not change the key;
`stats()` has a 'hit_rate' entry (0.0 when nothing was requested).
"""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from vakeel_sahayak.batch.cache import RetrievalCache
from vakeel_sahayak.schemas.enums import Factor

FAMILY = ["BNS 318", "BNS 316", "BNS 61"]
Q = "bail parity co-accused identical role"


def k(cache, factor=Factor.PARITY_WITH_CO_ACCUSED, family=FAMILY, before="2024-11-02", query=Q):
    return cache.key(factor, list(family), before, query)


# ---- key ----------------------------------------------------------------------------------------------------
def test_key_is_a_string():
    """Plan §11: key string."""
    assert isinstance(k(RetrievalCache()), str) and k(RetrievalCache())


def test_same_month_same_key():
    """Plan §11: two before-dates in the same month give the same key."""
    c = RetrievalCache()
    assert k(c, before="2024-11-02") == k(c, before="2024-11-29")


def test_different_month_different_key():
    """Plan §11: a different month gives a different key."""
    c = RetrievalCache()
    assert k(c, before="2024-11-02") != k(c, before="2024-12-02")


def test_same_month_of_a_different_year_is_a_different_key():
    """Plan §11: the month means year-and-month (Nov 2023 is not Nov 2024)."""
    c = RetrievalCache()
    assert k(c, before="2023-11-02") != k(c, before="2024-11-02")


def test_key_depends_on_the_factor():
    """Plan §11: factor is part of the key."""
    c = RetrievalCache()
    assert k(c, factor=Factor.PARITY_WITH_CO_ACCUSED) != k(c, factor=Factor.CHARGE_SHEET_FILED)


def test_key_depends_on_the_section_family():
    """Plan §11: section family is part of the key."""
    c = RetrievalCache()
    assert k(c, family=["BNS 318"]) != k(c, family=["BNS 303"])


def test_key_depends_on_the_query():
    """Plan §11: query is part of the key."""
    c = RetrievalCache()
    assert k(c, query="a") != k(c, query="b")


def test_section_family_order_does_not_change_the_key():
    """ASSUMPTION: the family is a set of sections; the same family in another order is the same key."""
    c = RetrievalCache()
    assert k(c, family=["BNS 318", "BNS 316", "BNS 61"]) == k(c, family=["BNS 61", "BNS 318", "BNS 316"])


def test_key_is_deterministic_across_instances():
    """Plan §11: the cache is shared across cases; the key does not depend on the instance."""
    assert k(RetrievalCache()) == k(RetrievalCache())


@given(d1=st.dates(dt.date(2015, 1, 1), dt.date(2025, 12, 31)), d2=st.dates(dt.date(2015, 1, 1), dt.date(2025, 12, 31)))
def test_property_key_equality_iff_same_year_month(d1, d2):
    """Plan §11: keys agree exactly when the before-dates share year and month (oracle: (year, month))."""
    c = RetrievalCache()
    same = (d1.year, d1.month) == (d2.year, d2.month)
    assert (k(c, before=d1.isoformat()) == k(c, before=d2.isoformat())) is same


# ---- get / put / stats --------------------------------------------------------------------------------------
def test_get_miss_returns_none():
    """Plan §11: unknown key -> None."""
    assert RetrievalCache().get("nope") is None


def test_put_then_get_returns_the_value():
    """Plan §11: a stored result is returned."""
    c = RetrievalCache()
    key = k(c)
    c.put(key, {"paragraphs": ["DLHC-2022-1187#14"]})
    assert c.get(key) == {"paragraphs": ["DLHC-2022-1187#14"]}


def test_cache_is_shared_between_two_cases_in_the_same_month():
    """Plan §11: case A fills the entry, case B (before-date in the same month) hits it."""
    c = RetrievalCache()
    c.put(k(c, before="2024-11-02"), ["hit"])
    assert c.get(k(c, before="2024-11-20")) == ["hit"]


def test_put_overwrites():
    """Plan §11: the latest value for a key wins."""
    c = RetrievalCache()
    c.put("k", 1)
    c.put("k", 2)
    assert c.get("k") == 2


def test_hit_rate_of_an_unused_cache_is_zero():
    """ASSUMPTION: no lookups -> hit_rate 0.0 (no division by zero)."""
    assert RetrievalCache().stats()["hit_rate"] == 0.0


def test_hit_rate_counts_hits_over_lookups():
    """Plan §15.6 F4: one miss then one hit -> 0.5; after two more hits -> 0.75."""
    c = RetrievalCache()
    assert c.get("a") is None  # miss
    c.put("a", "v")
    assert c.get("a") == "v"  # hit
    assert c.stats()["hit_rate"] == 0.5
    c.get("a")
    c.get("a")
    assert c.stats()["hit_rate"] == 0.75


def test_put_alone_does_not_change_the_hit_rate():
    """Plan §15.6 F4: only lookups count."""
    c = RetrievalCache()
    c.put("a", 1)
    assert c.stats()["hit_rate"] == 0.0
