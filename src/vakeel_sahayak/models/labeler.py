"""Evaluation labeler Llama-3.1-8B (4-bit). Never used by the system; non-Qwen so gold is not Qwen output (plan §12, §15.1).

`EvalLabeler` (alias `LabelerClient`) labels a text against a closed label set. It refuses to run when called from the
system's own packages (agents, orchestration, tools, api, batch, truth maintenance), so it can only feed `pipelines/gold`
and `eval/`. When Llama cannot run here (no transformers/torch, no weights, or `VS_MODELS=offline`) it raises
`LabelerUnavailable`, which is also a NotImplementedError: the gold pipeline then keeps provisional rule-only records
instead of pretending two labelers agreed. There is deliberately no offline labeler: a rule-based stand-in would agree
with the rules by construction.
"""

from __future__ import annotations

import os
import sys

from vakeel_sahayak.models.base import LabelerUnavailable, LLMClient, ModelUnavailable, model_family

DEFAULT_LABELER = "meta-llama/Llama-3.1-8B-Instruct"
SYSTEM_PACKAGES = (
    "vakeel_sahayak.agents", "vakeel_sahayak.orchestration", "vakeel_sahayak.tools", "vakeel_sahayak.api",
    "vakeel_sahayak.batch", "vakeel_sahayak.truth_maintenance", "vakeel_sahayak.export",
)  # fmt: skip


class SystemUseError(PermissionError):
    """The evaluation labeler was called from the running system (plan §12: never used by the system)."""


def assert_not_system_use() -> None:
    """Raise SystemUseError when any caller on the stack belongs to a system package."""
    frame = sys._getframe(2) if hasattr(sys, "_getframe") else None
    while frame is not None:
        module = str(frame.f_globals.get("__name__", ""))
        if any(module == p or module.startswith(p + ".") for p in SYSTEM_PACKAGES):
            raise SystemUseError(f"the evaluation labeler may not be used by the system (called from {module})")
        frame = frame.f_back


class EvalLabeler:
    """Llama-3.1-8B labeler for G1, G3-G7 and citation treatments."""

    name = "llama-3.1-8b-labeler"
    SYSTEM_USE = False

    def __init__(self, model: str | None = None, llm: LLMClient | None = None, backend: str | None = None) -> None:
        """Configure the labeler; nothing loads yet.

        Args:
            model: checkpoint (default configs/models.yaml `llm.eval_labeler.model`)
            llm: an LLMClient to use instead of loading Llama locally (e.g. a VllmClient serving Llama on Ada)
            backend: 'openai' or 'sarvam' to pick a hosted labeler for this object (wins over `VS_LABELER` and the yaml); None keeps them
        """
        self.model_id = model
        self._llm = llm
        self._backend = (backend or "").strip().lower() or None

    def _model_name(self) -> str:
        if self.model_id:
            return self.model_id
        if self._use_openai():
            from vakeel_sahayak.models.openai.config import openai_config

            return str(openai_config()["chat"]["model"])
        if self._use_sarvam():
            return "sarvam-105b"
        from vakeel_sahayak.config import load_config

        cfg = ((load_config().models.get("llm") or {}).get("eval_labeler") or {})
        return str(cfg.get("model") or DEFAULT_LABELER)

    def model_name(self) -> str:
        """The labeler's model name (nothing is loaded)."""
        return self._model_name()

    def backend(self) -> str:
        """'openai', 'sarvam' or 'local' (nothing is loaded)."""
        return "openai" if self._use_openai() else "sarvam" if self._use_sarvam() else "local"

    @property
    def family(self) -> str:
        """Model family of the labeler (for the rule that labeler, teacher and judged system differ in family)."""
        return "openai" if self._use_openai() else "sarvam" if self._use_sarvam() else model_family(self._model_name())

    def _use_openai(self) -> bool:
        """The other non-Qwen, non-Llama option: an OpenAI model as labeler (`VS_LABELER=openai` or yaml `llm.eval_labeler.runtime: openai`). Public text only; spend-capped."""
        if self._backend:
            return self._backend == "openai"
        raw = os.environ.get("VS_LABELER", "").strip().lower()
        if raw:
            return raw == "openai"
        from vakeel_sahayak.config import load_config

        return str(((load_config().models.get("llm") or {}).get("eval_labeler") or {}).get("runtime")) == "openai"

    def _use_sarvam(self) -> bool:
        """The documented non-Qwen, non-Llama option: Sarvam-105B as labeler (`VS_LABELER=sarvam` or yaml `llm.eval_labeler.runtime: sarvam`). Not the default."""
        if self._backend:
            return self._backend == "sarvam"
        raw = os.environ.get("VS_LABELER", "").strip().lower()
        if raw:
            return raw == "sarvam"
        from vakeel_sahayak.config import load_config

        return str(((load_config().models.get("llm") or {}).get("eval_labeler") or {}).get("runtime")) == "sarvam"

    def _sarvam_client(self) -> LLMClient:
        """Sarvam labelling of PUBLIC court text only (the client refuses anything else; it is never wired into the system's roles)."""
        from vakeel_sahayak.models.sarvam.adapters import SarvamLLMClient
        from vakeel_sahayak.models.sarvam.policy import DataClass

        client = SarvamLLMClient(self.model_id, data=DataClass.PUBLIC, where="api", role="eval_labeler")
        if model_family(client.model_id) == "qwen":
            raise ValueError("the evaluation labeler must not be a Qwen model (plan §15.1: no Qwen gold)")
        return client

    def _openai_client(self) -> LLMClient:
        """OpenAI labelling of PUBLIC court text only, behind the spend cap and the privacy gate (blocked or over the cap: `LabelerUnavailable`)."""
        from vakeel_sahayak.models.openai.adapters import OpenAILLMClient
        from vakeel_sahayak.models.sarvam.policy import DataClass

        return OpenAILLMClient(self.model_id, data=DataClass.PUBLIC, where="api", role="eval_labeler")

    def client(self) -> LLMClient:
        """The underlying LLM client (built on first use)."""
        assert_not_system_use()
        if self._llm is not None:
            return self._llm
        if model_family(self.model_id) == "qwen":  # refused before anything else, offline or not (plan §15.1: no Qwen gold)
            raise ValueError("the evaluation labeler must not be a Qwen model (plan §15.1: no Qwen gold)")
        from vakeel_sahayak.models.factory import models_mode

        if models_mode() == "offline":
            raise LabelerUnavailable("VS_MODELS=offline: the Llama evaluation labeler is not run; gold stays rule-only")
        from vakeel_sahayak.models.paid_lock import PaidProviderLocked, assert_unlocked

        if self._use_openai() or self._use_sarvam():  # a paid labeler is refused at once while locked (models/paid_lock.py)
            try:
                assert_unlocked("openai" if self._use_openai() else "sarvam")
            except PaidProviderLocked as exc:
                raise LabelerUnavailable(str(exc)) from exc
        if self._use_openai():
            self._llm = self._openai_client()
            return self._llm
        if self._use_sarvam():
            self._llm = self._sarvam_client()
            return self._llm
        from vakeel_sahayak.models.local_llm import LocalLLMClient

        name = self._model_name()
        if model_family(name) == "qwen":
            raise ValueError("the evaluation labeler must not be a Qwen model (plan §15.1: no Qwen gold)")
        if not LocalLLMClient.available():
            raise LabelerUnavailable("transformers and torch are not installed, so the Llama labeler cannot run", "models")
        self._llm = LocalLLMClient(model=name, role="eval_labeler", quant="int4")
        return self._llm

    def label(self, text: str, label_set: list[str]) -> list[str]:
        """Label text against a closed label set; agreed-labels-only logic lives in pipelines/gold.

        Args:
            text: the text to label (public court text)
            label_set: the allowed labels

        Returns:
            Labels from `label_set`, in label-set order.

        Raises:
            SystemUseError: when called from the system's packages.
            LabelerUnavailable: Llama cannot run here.
        """
        assert_not_system_use()
        if not label_set:
            return []
        from vakeel_sahayak.models.prompting import render_prompt
        from vakeel_sahayak.orchestration.structured_output import StructuredOutputError, constrained_generate

        schema = {
            "type": "object",
            "properties": {"labels": {"type": "array", "items": {"enum": list(label_set)}}},
            "required": ["labels"],
        }
        prompt = render_prompt(
            "eval.label",
            "Choose every label from the allowed set that the text clearly discusses. Choose none if none applies. "
            "Answer only with the JSON object.",
            {"allowed_labels": list(label_set), "text": text[:6000]},
            system="You are an annotator of Indian court orders.",
            schema=schema,
        )
        try:
            out = constrained_generate(self.client(), prompt, schema, max_tokens=256)
        except ModelUnavailable as exc:
            raise LabelerUnavailable(str(exc)) from exc
        except StructuredOutputError:
            return []
        chosen = set(out.get("labels", [])) if isinstance(out, dict) else set()
        return [lbl for lbl in label_set if lbl in chosen]


LabelerClient = EvalLabeler
