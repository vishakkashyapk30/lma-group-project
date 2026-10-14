"""Helpers for the ingestion unit tests: ladder rig (patched signals and routes), synthetic bundle pages, patching.

The ladder rig patches `compute_signals` and each route function BOTH at its source module and as an attribute of
`vakeel_sahayak.ingestion.ladder` (raising=False), so either import style in the implementation is covered.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from typing import Any

from tests.fixtures import pdfgen
from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute

# ASSUMPTION: thresholds.yaml leaves most values as `null` (tuned on dev). Tests use these concrete values.
# Only text_layer_word_share=0.85 is fixed by plan §4.2 step 1; the others are our choice.
THRESHOLDS: dict[str, float] = {
    "text_layer_word_share": 0.85,
    "text_coverage_min": 0.5,  # ASSUMPTION
    "ocr_conf_min": 0.6,  # ASSUMPTION: OCR confidence below this escalates to the vision model
    "vision_escalation_conf": 0.6,  # ASSUMPTION: same value, in case the implementation reads this key instead
    "dict_word_share_min": 0.85,  # ASSUMPTION
}

GOOD_TEXT_SIGNALS = PageSignals(has_text_layer=True, text_coverage=0.95, dict_word_share=0.95)
LEGACY_SIGNALS = PageSignals(has_text_layer=True, text_coverage=0.9, dict_word_share=0.2, legacy_font_pattern=True)
NO_TEXT_SIGNALS = PageSignals(has_text_layer=False)
HANDWRITING_SIGNALS = PageSignals(has_text_layer=False, handwriting_detected=True)

TEXT_LAYER_TEXT = pdfgen.REMAND_PAGE
GIBBERISH_TEXT = pdfgen.KRUTI_DEV_FIR_HEADER + " lak[;k 112@2024 fnukad 14-08-2024"
OCR_TEXT = "OCR transcript of the page: FIR No. 112/2024 arrested on 20.08.2024"
VISION_TEXT = "Vision transcript of the page: FIR No. 112/2024 arrested on 20.08.2024"

_ROUTE_TARGETS = {
    "text_layer": ("vakeel_sahayak.ingestion.routes.text_layer", "read_text_layer_page"),
    "layout": ("vakeel_sahayak.ingestion.routes.layout", "parse_layout_page"),
    "ocr": ("vakeel_sahayak.ingestion.routes.ocr", "ocr_page_route"),
    "vision": ("vakeel_sahayak.ingestion.routes.vision", "vision_route"),
    "ask_counsel": ("vakeel_sahayak.ingestion.routes.ask_counsel", "ask_counsel_route"),
}


@dataclass
class LadderRig:
    """Records which rungs the ladder ran (in order) and with which arguments."""

    calls: list[tuple[str, str, int]] = field(default_factory=list)

    @property
    def called(self) -> list[str]:
        return [name for name, _, _ in self.calls]

    def count(self, name: str) -> int:
        return self.called.count(name)

    def was_called(self, name: str) -> bool:
        return name in self.called


def patch_attr_everywhere(monkeypatch, module_name: str, attr: str, value: Any) -> None:
    """Patch `module.attr` at its source and on every already-imported vakeel_sahayak module that aliases it."""
    mod = importlib.import_module(module_name)
    original = getattr(mod, attr, None)
    monkeypatch.setattr(mod, attr, value, raising=False)
    for name, other in list(sys.modules.items()):
        if name.startswith("vakeel_sahayak") and other is not None and other is not mod:
            if original is not None and getattr(other, attr, None) is original:
                monkeypatch.setattr(other, attr, value, raising=False)


def patch_ladder(
    monkeypatch,
    signals: PageSignals,
    *,
    text_layer_text: str = TEXT_LAYER_TEXT,
    ocr_conf: float | None = 0.9,
    ocr_text: str = OCR_TEXT,
    vision_ok: bool = True,
    vision_text: str = VISION_TEXT,
    layout_extra: str = "\nTable: custody certificate, days in custody 167",
) -> LadderRig:
    """Install fakes for compute_signals and the five route functions; return the call recorder.

    Fake route logs are deliberately EMPTY: the ladder itself must write the route log (plan §4.2 'Badges').
    """
    rig = LadderRig()
    ladder = importlib.import_module("vakeel_sahayak.ingestion.ladder")

    def fake_signals(file_path: str, page: int) -> PageSignals:
        rig.calls.append(("signals", file_path, page))
        return signals.model_copy()

    def make(name: str, build):
        def fn(file_path: str, page: int) -> RouteOutcome:
            rig.calls.append((name, file_path, page))
            return build()

        fn.__name__ = f"fake_{name}"
        return fn

    builders = {
        "text_layer": lambda: RouteOutcome(route=ParseRoute.TEXT_LAYER, text=text_layer_text),
        "layout": lambda: RouteOutcome(route=ParseRoute.LAYOUT, text=text_layer_text + layout_extra),
        "ocr": lambda: RouteOutcome(route=ParseRoute.OCR, text=ocr_text, confidence=ocr_conf, lang="en"),
        "vision": lambda: (
            RouteOutcome(route=ParseRoute.VISION, text=vision_text, confidence=0.9)
            if vision_ok
            else RouteOutcome(route=ParseRoute.VISION, text="", confidence=0.1, status=PageStatus.UNREADABLE)
        ),
        "ask_counsel": lambda: RouteOutcome(route=ParseRoute.ASK_COUNSEL, text="", status=PageStatus.UNREADABLE),
    }

    monkeypatch.setattr("vakeel_sahayak.ingestion.signals.compute_signals", fake_signals)
    monkeypatch.setattr(ladder, "compute_signals", fake_signals, raising=False)
    for name, (module_name, attr) in _ROUTE_TARGETS.items():
        importlib.import_module(module_name)
        fake = make(name, builders[name])
        monkeypatch.setattr(f"{module_name}.{attr}", fake)
        monkeypatch.setattr(ladder, attr, fake, raising=False)
    return rig


# ---- synthetic bundle pages (plan §4.1 K8, §13.6 flow 1) -------------------------------------------------------------
def doc_pages(header: str, n: int, repeat_header: bool = False, body: str = "Body text of the document.") -> list[str]:
    """Pages of one synthetic document: header on page 1 (or on every page), 'Page i of n' footer."""
    pages = []
    for i in range(1, n + 1):
        lines = [header] if (i == 1 or repeat_header) else []
        lines.append(f"{body} (continued {i})")
        lines.append(f"Page {i} of {n}")
        pages.append("\n".join(lines))
    return pages


FIR_FIRST_PAGE = "FIRST INFORMATION REPORT\nFIR No. 112/2024 PS-1 under Section 318(4) BNS\nDate of occurrence 10.08.2024"


def flow1_bundle_pages() -> list[str]:
    """Plan §13.6 flow 1: FIR (pp.1-3), two remand orders (4-5, 6-7), Sessions bail rejection (8-14)."""
    fir = [f"{FIR_FIRST_PAGE}\nPage 1 of 3", "Complainant narrative continues.\nPage 2 of 3", "Signature of the officer.\nPage 3 of 3"]
    remand_1 = [pdfgen.REMAND_PAGE + "\nPage 1 of 2", "Remand continues.\nPage 2 of 2"]
    remand_2 = [pdfgen.REMAND_PAGE + "\nPage 1 of 2", "Remand extension continues.\nPage 2 of 2"]
    bail = [pdfgen.BAIL_ORDER_PAGE + "\nPage 1 of 7"] + [f"Reasoning paragraph {i}.\nPage {i} of 7" for i in range(2, 8)]
    pages = fir + remand_1 + remand_2 + bail
    assert len(pages) == 14
    return pages


def default_signals(n: int) -> list[PageSignals]:
    return [PageSignals(has_text_layer=True, text_coverage=0.9, dict_word_share=0.95) for _ in range(n)]
