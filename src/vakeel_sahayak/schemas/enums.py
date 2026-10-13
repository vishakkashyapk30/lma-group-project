"""Enumerations for statuses, stores, agents and factors (plan §4-§11, Appendix A)."""

from __future__ import annotations

from enum import Enum


class FieldStatus(str, Enum):
    """Status of a dossier field (plan §7.1)."""

    VERIFIED = "VERIFIED"
    COMPUTED = "COMPUTED"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    USER_STATED = "USER_STATED"
    USER_EDITED = "USER_EDITED"


class SlotStatus(str, Enum):
    """Assessment of an evidence-contract slot after retrieval (plan §6.2)."""

    FILLED = "FILLED"
    WEAK = "WEAK"
    MISSING = "MISSING"


class ClaimState(str, Enum):
    """Truth-maintenance state of a brief claim (plan §10)."""

    CURRENT = "CURRENT"
    STALE = "STALE"


class ClaimCheck(str, Enum):
    """Outcome of Vakeel's check-and-repair on a claim (plan §8.1)."""

    SUPPORTED = "SUPPORTED"
    REPAIRED = "REPAIRED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class SparringVerdict(str, Enum):
    """Abhiyojak's verdict on a reply (plan §9)."""

    ANSWERED = "ANSWERED"
    PARTLY = "PARTLY"
    UNANSWERED = "UNANSWERED"


class RightsStatus(str, Enum):
    """Union of all Rights Radar output statuses (plan §7.3). Per-rule allowed subsets live in rights/rules/*."""

    ELIGIBLE = "ELIGIBLE"
    NOT_YET = "NOT_YET"
    WINDOW_CLOSED = "WINDOW_CLOSED"
    CHECK = "CHECK"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FLAG = "FLAG"
    OK = "OK"
    UNKNOWN = "UNKNOWN"
    BAR_APPLIES = "BAR_APPLIES"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class RightsCheckName(str, Enum):
    """The seven Rights Radar checks (plan §7.3, Appendix C)."""

    DEFAULT_BAIL = "default_bail"
    UNDERTRIAL_LIMIT = "undertrial_limit"
    NOTICE_OF_APPEARANCE = "notice_of_appearance"
    GROUNDS_OF_ARREST = "grounds_of_arrest"
    PRODUCTION_24H = "production_24h"
    ANTIL_CATEGORY = "antil_category"
    STATUTORY_BAR = "statutory_bar"


class TransferFlag(str, Enum):
    """IPC-to-BNS transfer flag on a precedent (plan §5.4)."""

    SAME_TEXT = "SAME_TEXT"
    CHANGED = "CHANGED"
    NEW = "NEW"


class GoodLawStatus(str, Enum):
    """Good-law flag on an authority (plan §5.3)."""

    OK = "OK"
    OVERRULED = "OVERRULED"
    DISTINGUISHED = "DISTINGUISHED"
    UNKNOWN = "UNKNOWN"


class Treatment(str, Enum):
    """How a citing sentence treats the cited case (plan §5.3)."""

    FOLLOWED = "FOLLOWED"
    RELIED_ON = "RELIED_ON"
    DISTINGUISHED = "DISTINGUISHED"
    OVERRULED = "OVERRULED"
    REFERRED = "REFERRED"
    UNKNOWN = "UNKNOWN"


class ConcordanceEdgeType(str, Enum):
    """Typed edge of the IPC/BNS and CrPC/BNSS concordance (plan §5.1)."""

    SAME = "SAME"
    SPLIT = "SPLIT"
    MERGED = "MERGED"
    REWORDED = "REWORDED"
    NEW = "NEW"


class FactorStance(str, Enum):
    """Sutradhar's per-factor stance (plan §6.2)."""

    FAVOURABLE = "favourable"
    ADVERSE = "adverse"
    NOT_APPLICABLE = "not_applicable"


class OpenIssueType(str, Enum):
    """Type of open issue in a BailBrief (plan §8.1)."""

    NEEDS_REVIEW = "NEEDS_REVIEW"
    CHANGED_PROVISION = "CHANGED_PROVISION"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"


class AgentName(str, Enum):
    """The six agents (plan §3.2)."""

    MUNSHI = "MUNSHI"
    PESHKAR = "PESHKAR"
    SUTRADHAR = "SUTRADHAR"
    VAKEEL = "VAKEEL"
    ABHIYOJAK = "ABHIYOJAK"
    PAIROKAR = "PAIROKAR"


class Factor(str, Enum):
    """The 12 bail factors (plan Appendix A). Values are contract file stems."""

    GRAVITY_AND_PUNISHMENT = "gravity_and_punishment"
    CUSTODY_PERIOD = "custody_period"
    CHARGE_SHEET_FILED = "charge_sheet_filed"
    TRIAL_DELAY = "trial_delay"
    PARITY_WITH_CO_ACCUSED = "parity_with_co_accused"
    ANTECEDENTS = "antecedents"
    FLIGHT_RISK = "flight_risk"
    WITNESS_TAMPERING = "witness_tampering"
    WEAK_PRIMA_FACIE = "weak_prima_facie"
    HEALTH_AGE_FAMILY = "health_age_family"
    STATUTORY_BAR = "statutory_bar"
    UNDERTRIAL_PERIOD = "undertrial_period"


class Shelf(str, Enum):
    """The four shelves (plan §5.1)."""

    LAW = "law"
    CASELAW = "caselaw"
    ADVOCACY = "advocacy"
    CASE = "case"


class StoreName(str, Enum):
    """The ten stores (plan §5.1)."""

    LAW_STATUTES = "law.statutes"
    LAW_CONCORDANCE = "law.concordance"
    CASELAW_REASONING = "caselaw.reasoning"
    CASELAW_CITATIONS = "caselaw.citations"
    CASELAW_SIMILAR = "caselaw.similar"
    ADVOCACY_ARGUMENTS = "advocacy.arguments"
    ADVOCACY_OBJECTIONS = "advocacy.objections"
    CASE_DOCS = "case.docs"
    CASE_TIMELINE = "case.timeline"
    CASE_FACTS = "case.facts"


class DocumentType(str, Enum):
    """Document labels assigned by Munshi (plan §4.3)."""

    FIR = "FIR"
    ARREST_MEMO = "ARREST_MEMO"
    REMAND_ORDER = "REMAND_ORDER"
    BAIL_ORDER = "BAIL_ORDER"
    ORDER_SHEET = "ORDER_SHEET"
    CHARGE_SHEET_COVER = "CHARGE_SHEET_COVER"
    CUSTODY_CERTIFICATE = "CUSTODY_CERTIFICATE"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    AFFIDAVIT = "AFFIDAVIT"
    OTHER = "OTHER"


class InputKind(str, Enum):
    """Input kinds K1-K10 (plan §4.1)."""

    K1_BORN_DIGITAL = "K1_BORN_DIGITAL"
    K2_SCANNED = "K2_SCANNED"
    K3_DEGRADED = "K3_DEGRADED"
    K4_PHONE_PHOTO = "K4_PHONE_PHOTO"
    K5_HINDI_MIXED = "K5_HINDI_MIXED"
    K6_LEGACY_HINDI_FONT = "K6_LEGACY_HINDI_FONT"
    K7_HANDWRITING = "K7_HANDWRITING"
    K8_BUNDLE = "K8_BUNDLE"
    K9_LOCKED_OR_BROKEN = "K9_LOCKED_OR_BROKEN"
    K10_NOT_PDF = "K10_NOT_PDF"


class ParseRoute(str, Enum):
    """Rungs of the routing ladder (plan §4.2)."""

    TEXT_LAYER = "text_layer"
    LAYOUT = "layout"
    OCR = "ocr"
    VISION = "vision"
    ASK_COUNSEL = "ask_counsel"


class PageStatus(str, Enum):
    """Final status of a page after routing (plan §4.6)."""

    OK = "OK"
    UNREADABLE = "UNREADABLE"


class OrderPart(str, Enum):
    """Part of a court order (plan §5.2)."""

    FACTS = "facts"
    DEFENSE = "defense_submissions"
    PROSECUTION = "prosecution_submissions"
    REASONING = "reasoning"
    OPERATIVE = "operative_order"


class InfoKind(str, Enum):
    """Kind of information a paragraph holds (plan §4.3)."""

    DATED_EVENT = "dated_event"
    PARTY = "party"
    SECTION = "section"
    EARLIER_OUTCOME = "earlier_outcome"
    CUSTODY = "custody"
    PERSONAL = "personal_circumstance"


class EventKind(str, Enum):
    """Kinds of event-log entries (plan §3.3)."""

    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    AGENT_MESSAGE = "AGENT_MESSAGE"
    STORE_WRITE = "STORE_WRITE"
    GATE_OPENED = "GATE_OPENED"
    GATE_APPROVED = "GATE_APPROVED"
    GATE_REJECTED = "GATE_REJECTED"
    BUDGET_HIT = "BUDGET_HIT"
    USER_ACTION = "USER_ACTION"
    CHANGE_SET_APPROVED = "CHANGE_SET_APPROVED"
    CLAIM_STALED = "CLAIM_STALED"
    ERROR = "ERROR"


class GateId(str, Enum):
    """The two approval gates (plan §3.1)."""

    GATE_1_DOSSIER = "GATE_1_DOSSIER"
    GATE_2_EXPORT = "GATE_2_EXPORT"


class Stage(str, Enum):
    """Workspace stages (plan §13.5)."""

    INTAKE = "INTAKE"
    DOSSIER = "DOSSIER"
    RIGHTS = "RIGHTS"
    BRIEF = "BRIEF"
    SPAR = "SPAR"
    HEARING_PREP = "HEARING_PREP"
    FILE = "FILE"


class ExportFormat(str, Enum):
    """Export formats (plan §8.2, §13.1)."""

    DOCX = "DOCX"
    PDF = "PDF"


class DocLang(str, Enum):
    """Document language codes."""

    EN = "en"
    HI = "hi"
    MIXED = "mixed"
