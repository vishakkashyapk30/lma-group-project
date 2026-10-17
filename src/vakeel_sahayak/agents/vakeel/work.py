"""Working state of one claim while Vakeel drafts, checks and repairs it (plan §8.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.agents.vakeel.claims import Sentence
from vakeel_sahayak.agents.vakeel.facts import Fact
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack
from vakeel_sahayak.tools.types import ClaimCheckResult

# What a failed sentence needs: a better source (re-retrieve or swap the authority) or a rewording to the source it has.
AUTHORITY_PROBLEMS = frozenset({"authority", "overruled", "unretrieved", "citation"})
PROBLEM_WORDS = {
    "fact": "not supported by the dossier quote",
    "authority": "not supported by the cited paragraph",
    "unsupported": "not supported by its sources",
    "overruled": "cites an overruled authority",
    "unretrieved": "cites an authority that was not retrieved",
    "citation": "cites a document the corpus does not know",
    "uncited": "cites no fact or authority",
    "bad_ref": "has a malformed [F:...] or [A:...] reference",
    "prediction": "predicts an outcome",
    "invented": "names a case or a citation instead of an ID marker",
    "check_error": "could not be checked",
}


@dataclass
class SentenceCheck:
    """The check of one sentence: what failed and why."""

    text: str
    problems: list[str] = field(default_factory=list)
    detail: list[str] = field(default_factory=list)
    result: ClaimCheckResult | None = None

    @property
    def ok(self) -> bool:
        return not self.problems

    def describe(self) -> str:
        """'not supported by the dossier quote (fact support 0.31)' for an issue line."""
        words = ", ".join(PROBLEM_WORDS.get(p, p) for p in dict.fromkeys(self.problems))
        return words + (f" ({'; '.join(self.detail)})" if self.detail else "")


@dataclass
class Evidence:
    """What a claim may rest on: the facts and paragraphs offered to the drafter."""

    factor: str | None
    stance: str = "favourable"
    reason: str | None = None
    facts: dict[str, Fact] = field(default_factory=dict)
    auths: list[dict[str, Any]] = field(default_factory=list)  # retrieved reasoning paragraphs (never overruled ones)
    rights: list[dict[str, str]] = field(default_factory=list)
    open_issues: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)  # 'doc#para' left out of the drafter's sight (overruled)
    pack: EvidencePack | None = None

    def keys(self) -> set[tuple[str, int]]:
        return {(str(a["doc_id"]), int(a["para"])) for a in self.auths}


@dataclass
class Work:
    """One claim (a ground or a reply) between drafting and the final check."""

    key: str  # 'G1' or 'reply:O1'
    ev: Evidence
    sentences: list[Sentence] = field(default_factory=list)
    checks: list[SentenceCheck] = field(default_factory=list)
    initial_ok: bool | None = None  # did the first check pass as drafted?
    repaired: bool = False
    rounds: int = 0
    retrieved: bool = False  # re-retrieval through Sutradhar already tried
    empty: bool = False  # the model gave nothing to cite
    unchecked: bool = False  # A2/A9: nothing was checked
    notes: list[str] = field(default_factory=list)  # reasons the claim is flagged, for the open issues

    def failing(self) -> list[int]:
        return [i for i, c in enumerate(self.checks) if not c.ok]
