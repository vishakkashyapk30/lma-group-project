"""Munshi's language-model decisions behind the model-client interface (plan §3.2, §4.3).

Everything Munshi decides by rule stays a rule. The one decision that may call a model is the document label when the
rules are not confident: `LlmAdvisor.classify` is the fallback `ingestion.classify.label_document` accepts. The model
only sees the document wrapped as untrusted data, answers in JSON constrained by a schema, and a reply that does not
parse or names an unknown type is ignored (the rule label stays).
"""

from __future__ import annotations

import json

from vakeel_sahayak.agents.munshi.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATES
from vakeel_sahayak.models.base import LLMClient, ModelUnavailable
from vakeel_sahayak.privacy.injection_guard import wrap_untrusted
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import DocumentType

MAX_MODEL_CONFIDENCE = 0.9  # a small model's self-reported confidence is capped
_SCHEMA = {
    "type": "object",
    "properties": {"type": {"enum": [t.value for t in DocumentType]}, "confidence": {"type": "number"}},
    "required": ["type", "confidence"],
}


class LlmAdvisor:
    """Wraps an LLMClient (role `munshi_4b`) for Munshi's fallback decisions."""

    def __init__(self, llm: LLMClient, *, spotlight: bool = True) -> None:
        """Keep the client; `spotlight=False` (S17b arm `no_spotlighting`) passes the document text without the delimiter block."""
        self.llm = llm
        self.spotlight = spotlight

    def classify(self, text: str) -> tuple[DocumentType, float] | None:
        """Label a document from its opening text; None when the model's reply cannot be used.

        Args:
            text: the document's opening text (data, not instructions)

        Returns:
            (type, confidence), or None.
        """
        prompt = SYSTEM_PROMPT + "\n\n" + USER_PROMPT_TEMPLATES["classify_document"].format(
            types=", ".join(t.value for t in DocumentType),
            document=wrap_untrusted(text, SourceRef(doc="document to label")) if self.spotlight else text,
        )
        try:
            reply = json.loads(self.llm.generate(prompt, max_tokens=64, temperature=0.0, json_schema=_SCHEMA))
            doc_type = DocumentType(reply["type"])
            confidence = min(MAX_MODEL_CONFIDENCE, max(0.0, float(reply["confidence"])))
        except (ValueError, KeyError, TypeError, NotImplementedError, ModelUnavailable):
            return None
        return doc_type, confidence

    __call__ = classify
