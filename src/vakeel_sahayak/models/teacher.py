"""Teacher for training data only: Qwen3-32B-AWQ on Ada or a Mistral API model; public orders only (plan §12, §17). Teacher and labeler must differ in family."""

from __future__ import annotations

from vakeel_sahayak.schemas.dossier import CaseDossier


class TeacherClient:
    """Teacher dossier generator."""

    def dossier_from_facts(self, facts_text: str) -> CaseDossier:
        """Output a CaseDossier quoting a source sentence per field (plan §12 step 1).

        Args:
            facts_text: see behaviour

        Returns:
            CaseDossier.
        """
        raise NotImplementedError
