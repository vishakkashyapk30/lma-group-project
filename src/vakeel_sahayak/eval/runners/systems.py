"""The systems of the run plan by name: Full, the baselines B0..B6, the ablations and every implemented variant (docs/evaluation-plan.md §3.1, §3.3, §3.4).

`system_runner(name)` returns `(runner, switches)`: `runner(case, ctx) -> BailBrief | dict` and the `Switches` the run uses. This is the single entry
that `driver run --system <id>` and the job table use.

System ids (case-insensitive; the manifest records the canonical spelling):
* `full`, `b0`, `b0l`, `b0s`, `b1`, `b2`, `b3`, `b4`, `b6`: Full and the baselines (`b5` is the variant B5, below).
* every id of `Switches.implemented_variants()`: `A1`..`A10`, `S1`..`S18`, `B5`, `P5`..`P8`, and the plan's aliases (`A11a`, `A12`, `A8b`, ...). Each runs the
  Full system with the variant's switches, except `A10` (retrieval and slot fill only: no drafting).
* three ids need an argument, written `ID:ARG`: `A5:base_4b` or `A5:prompted_32b` (the extractor), `A10:<store>` (the store knocked out, for example
  `A10:caselaw.reasoning`) and `S13:<field>=<value>[,<field>=<value>]` (a grid point of the searched switches, for example `S13:stopping=llm`).

An id that exists as a switch set but that no agent reads yet (today only `S15b`) raises `NotImplementedError` naming the variant; an unknown id raises `ValueError`
listing the valid ones. Nothing is ever run silently as Full under another name.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from typing import Any

from vakeel_sahayak.orchestration.switches import (
    IMPLEMENTED_VARIANTS,
    Switches,
    assert_variant_implemented,
    canonical_variant,
)

BASELINE_MODULES = {
    "b0": "b0_single_pass", "b1": "b1_single_rag", "b2": "b2_whole_doc", "b3": "b3_naive_chunking",
    "b4": "b4_all_stores", "b6": "b6_expert_rule",
}
B0_MODELS = {"b0": None, "b0l": "teacher", "b0s": "munshi_4b"}  # B0 on the shared 14B, B0L on the teacher role, B0S on the base 4B
BASELINE_IDS: tuple[str, ...] = ("full", "b0", "b0l", "b0s", "b1", "b2", "b3", "b4", "b6")
ARG_VARIANTS = ("A5", "A10", "S13")  # need `ID:ARG`
DEFAULT_ARMS: dict[str, tuple[str, ...]] = {  # the arms a smoke run and the job table use for the three ids that need an argument
    "A5": ("base_4b", "prompted_32b"),
    "A10": (),  # filled from the shared stores below
    "S13": ("stopping=llm",),
}

# What a variant changes in a per-case run of the evaluation driver (stored in the run manifest as `scope`, so nobody reads a no-op as a null result).
SCOPES: dict[str, str] = {
    "pipeline": "the switch is read inside the per-case pipeline (Munshi when a bundle is given, Peshkar, Sutradhar, Vakeel, Abhiyojak)",
    "bundle": "read by Munshi only: it changes a run only on cases with a bundle (T2 or T1 bundles); on a text-only T1 case the run equals Full",
    "batch": "needs a shared retrieval cache across cases: `run_cases` gives every case of the run one in-memory cache (a batch)",
    "scheduler": "read by the batch desk's scheduler (Pairokar), not by the per-case pipeline: a per-case run equals Full; measured on the batch test set T5",
    "retrieval_only": "read by the chunking study (`stores.chunk_strategies`, `eval.baselines.chunking_variants`), not by the per-case pipeline: a per-case run equals Full",
    "retrieval_stop": "retrieval and slot fill only (A10): the run stops after Sutradhar's evidence packs and drafts nothing",
    "grid": "a grid point of the searched switches (S13)",
    "baseline": "a baseline runner (no Full pipeline)",
}
VARIANT_SCOPE: dict[str, str] = {
    "S7": "bundle", "P5": "bundle", "P6": "bundle", "P7": "bundle", "P8": "bundle",
    "S14": "batch", "S14d": "batch", "S14b": "scheduler", "S14c": "scheduler",
    "S16": "retrieval_only", "S16b": "retrieval_only", "A10": "retrieval_stop", "S13": "grid",
}


def shared_stores() -> list[str]:
    """The seven shared stores A10 knocks out one at a time (never two together)."""
    from vakeel_sahayak.eval.ablations.a10_store_knockouts import SHARED_STORES

    return list(SHARED_STORES)


def split_system_id(name: str) -> tuple[str, str | None]:
    """`'A10:caselaw.reasoning'` -> `('A10', 'caselaw.reasoning')`; an id without an argument gives `(id, None)`."""
    base, _, arg = name.strip().partition(":")
    return base, (arg or None)


def canonical_system(name: str) -> str:
    """The canonical spelling of a system id: lower case for Full and the baselines ('b0l'), the variant's canonical id otherwise ('a12' -> 'S6', 'A11b' -> 'S3'),
    and the argument kept as given ('A10:caselaw.reasoning').

    Raises:
        ValueError: unknown id (the message lists the valid ones).
    """
    base, arg = split_system_id(name)
    key = base.lower()
    if key in BASELINE_IDS:
        if arg:
            raise ValueError(f"system {key!r} takes no argument (got {arg!r})")
        return key
    try:
        canon = canonical_variant(base)
    except ValueError:
        raise ValueError(f"unknown system {name!r}: use one of {', '.join(BASELINE_IDS)}, a variant id (A1-A10, S1-S18, B5, P5-P8; A5, A10 and S13 as ID:ARG) or a plan alias") from None
    return canon + (f":{arg}" if arg else "")


def dispatchable_ids() -> list[str]:
    """Every id `system_runner` accepts and a job may name: Full and the baselines, then each implemented variant (A5, A10 and S13 once per default arm).

    The list follows `Switches.implemented_variants()`, so a variant flipped into it is dispatchable without a code change here.
    """
    out = list(BASELINE_IDS)
    for ident in sorted(IMPLEMENTED_VARIANTS - {"full"}, key=_id_order):
        if ident in ARG_VARIANTS:
            arms = DEFAULT_ARMS[ident] or tuple(shared_stores())
            out.extend(f"{ident}:{arm}" for arm in arms)
        else:
            out.append(ident)
    return out


def _id_order(ident: str) -> tuple[Any, ...]:
    m = re.fullmatch(r"([A-Z]+)(\d+)([a-z]?)", ident)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (ident, 0, "")


def scope_of(name: str) -> str:
    """The scope key (`SCOPES`) of a system id."""
    base, _ = split_system_id(name)
    if base.lower() in BASELINE_IDS:
        return "pipeline" if base.lower() == "full" else "baseline"
    return VARIANT_SCOPE.get(canonical_variant(base), "pipeline")


def system_switches(name: str) -> Switches:
    """The `Switches` of a system id (the same object `system_runner` returns), without importing any runner.

    Raises:
        NotImplementedError: the variant is declared but no agent reads it (names the variant).
        ValueError: unknown id, a missing or malformed argument.
    """
    canon = canonical_system(name)
    base, arg = split_system_id(canon)
    if base in BASELINE_IDS:
        return Switches()
    assert_variant_implemented(base)
    if base == "A5":
        if arg not in {"base_4b", "prompted_32b"}:
            raise ValueError("A5 needs an arm: 'A5:base_4b' or 'A5:prompted_32b' (the fine-tuned 4B is Full)")
        return Switches.for_variant("A5", extractor=arg)
    if base == "A10":
        if not arg or arg not in shared_stores():
            raise ValueError(f"A10 needs the store to knock out: 'A10:<store>' with one of {', '.join(shared_stores())}")
        return Switches.for_variant("A10", knockout_store=arg)
    if base == "S13":
        if not arg:
            raise ValueError("S13 is a grid point of the searched switches: 'S13:stopping=llm' (fields as name=value, comma separated)")
        return Switches.for_variant("S13", **_parse_fields(arg))
    if arg:
        raise ValueError(f"{base} takes no argument (got {arg!r})")
    return Switches.for_variant(base)


def _parse_fields(arg: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for part in arg.split(","):
        key, sep, value = part.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"S13 argument {part!r} is not name=value")
        v: Any = value.strip()
        if v.lower() in {"true", "false"}:
            v = v.lower() == "true"
        fields[key.strip()] = v
    return fields


def system_runner(name: str) -> tuple[Callable[[dict[str, Any], Any], Any], Switches]:
    """The runner and switches of a system id (see the module docstring for the ids).

    Raises:
        NotImplementedError: a declared variant that no agent reads yet (today `S15b`), naming the variant and its switches.
        ValueError: unknown id, or an id of A5, A10, S13 without its argument.
    """
    canon = canonical_system(name)
    base, _ = split_system_id(canon)
    modules = "vakeel_sahayak.eval.baselines."
    if base == "full":
        return importlib.import_module(modules + "full_system").run_case, Switches()
    if base in B0_MODELS:
        mod = importlib.import_module(modules + "b0_single_pass")
        role = B0_MODELS[base]
        return (lambda case, ctx, _m=mod, _r=role: _m.run_case_with_model(case, ctx, _r)), Switches()
    if base in BASELINE_MODULES:
        return importlib.import_module(modules + BASELINE_MODULES[base]).run_case, Switches()
    switches = system_switches(canon)  # raises for an unimplemented or malformed id before anything is imported
    if base == "A10":
        from vakeel_sahayak.eval.runners.driver import run_agents

        return (lambda case, ctx: run_agents(case, ctx, stop_after="retrieval")), switches
    return importlib.import_module(modules + "full_system").run_case, switches
