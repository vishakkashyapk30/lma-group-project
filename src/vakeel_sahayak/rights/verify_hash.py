"""Bind a rule's `last_verified` date to what was verified (design review 2026-10-27, item 7).

A person who re-checks a rule against the bare act records two things in `configs/rights_rules.yaml`: the date
(`last_verified`) and the hash this module prints (`verified_hash`). The hash covers the rule's yaml section (rule text,
sources, statuses, params; never the two verification keys) and the source of its module `rights/rules/<rule>.py`, so
any later change to the rule text or to its code clears the verification: `default_rules()` treats a date whose hash is
missing or different as unverified.

Usage, when re-verifying: `python -m vakeel_sahayak.rights.verify_hash <rule>` (no argument: every rule).
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import sys
from typing import Any

VERIFICATION_KEYS = ("last_verified", "verified_hash")


def _section(rule_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    if config is None:
        from vakeel_sahayak.config import load_config

        config = load_config().rights_rules
    section = config.get(rule_id) or {}
    return {k: v for k, v in section.items() if k not in VERIFICATION_KEYS}


def _module_source(rule_id: str) -> str:
    module = importlib.import_module(f"vakeel_sahayak.rights.rules.{rule_id}")
    return inspect.getsource(module).replace("\r\n", "\n")


def rule_hash(rule_id: str, config: dict[str, Any] | None = None) -> str:
    """The hash a person records as `verified_hash` after checking `rule_id` against the bare act (16 hex characters of SHA-256).

    Args:
        rule_id: a rule name, e.g. 'notice_of_appearance'
        config: the `rights_rules` config; default the loaded one
    """
    payload = json.dumps({"rule": rule_id, "config": _section(rule_id, config), "code": _module_source(rule_id)},
                         sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def effective_last_verified(rule_id: str, section: dict[str, Any], config: dict[str, Any] | None = None) -> str | None:
    """The `last_verified` date if `verified_hash` matches the rule as it is now, else None (shown as 'unverified')."""
    date = section.get("last_verified")
    if not date:
        return None
    recorded = section.get("verified_hash")
    return str(date) if recorded and recorded == rule_hash(rule_id, config) else None


def main(argv: list[str] | None = None) -> int:
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.schemas.enums import RightsCheckName

    config = load_config().rights_rules
    names = (argv if argv is not None else sys.argv[1:]) or [c.value for c in RightsCheckName]
    for name in names:
        section = config.get(name) or {}
        state = "verified" if effective_last_verified(name, section, config) else "unverified"
        print(f"{name}\t{rule_hash(name, config)}\t{state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
