"""Ingestion thresholds: configs/thresholds.yaml values, with provisional defaults where the YAML says null (plan §4.2).

Every threshold is tuned on the dev set before the test run (plan §2, §14.2). Until then `PROVISIONAL` supplies a
working value. TODO: tune on dev.
"""

from __future__ import annotations

from typing import Any

PROVISIONAL: dict[str, float] = {
    "text_layer_word_share": 0.85,  # fixed by plan §4.2 step 1
    "text_coverage_min": 0.2,  # share of the page area covered by text blocks; below this the layer is thin (K2)
    "ocr_conf_min": 0.60,  # mean OCR confidence below this fails the OCR step
    "dict_word_share_min": 0.70,  # word-list share an OCR or vision transcript must reach
    "script_consistency_min": 0.90,  # share of words that stay in one script
    "chars_per_area_min": 0.5,  # characters per 10,000 square points of page area (about 25 characters on A4)
    "vision_escalation_conf": 0.75,  # pages read below this are candidates for a stronger re-read
    "doc_type_conf_min": 0.55,  # below this the rule label is passed to the LLM fallback
    "boundary_sensitivity": 0.70,  # confidence a page's own type needs to start a new document
    "handwriting_conf_max": 0.45,  # an image-only page with OCR confidence below this is treated as handwriting
    "legacy_font_marker_share": 0.06,  # share of Kruti Dev marker words that flags legacy Hindi fonts
    "max_questions_per_round": 3,  # shared by Munshi and Peshkar (plan §4.3)
}


def load_thresholds(overrides: dict[str, float] | None = None, config: Any | None = None) -> dict[str, float]:
    """The flat threshold dictionary the signals, ladder and bundle splitter take.

    Args:
        overrides: values that win over the YAML (for tests and baselines)
        config: an AppConfig; defaults to `load_config()`

    Returns:
        Keys of `PROVISIONAL`, from the YAML when it holds a number, else the provisional value.
    """
    if config is None:
        from vakeel_sahayak.config import load_config

        config = load_config()
    section = {**(config.thresholds.get("ingestion") or {}), **(config.thresholds.get("safety") or {})}
    out = dict(PROVISIONAL)
    for key in PROVISIONAL:
        value = section.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = float(value)
    out.update({k: float(v) for k, v in (overrides or {}).items()})
    return out


def threshold(thresholds: dict[str, Any] | None, key: str) -> float:
    """One threshold from a possibly partial dictionary; a missing or null entry falls back to the provisional value."""
    value = (thresholds or {}).get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else PROVISIONAL[key]
