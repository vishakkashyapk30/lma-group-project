"""Builder for law.statutes: statutes (plan §5.1).

Input: `<interim_dir>/statutes.jsonl`, one `StatuteRow` per line: `{"code": "IPC", "section": "420", "text": "...",
"max_punishment": "7 years", "bailable": false, "cognisable": true}` (the last three optional). The file comes from the
Open India Law bare-act extraction (`oil_ingest.extract_statute_texts`). Without it, the plan-named seed rows are
written. Statutes are law, not orders, so there is nothing to exclude; `exclude_doc_ids` is accepted for a uniform signature.
"""

from __future__ import annotations

from vakeel_sahayak.stores.law_statutes import StatuteStore


def build_statutes(interim_dir: str, out_dir: str, exclude_doc_ids: set[str] | None = None) -> int:
    """Build the statutes SQLite file.

    Args:
        interim_dir: folder with `statutes.jsonl`
        out_dir: folder that receives the SQLite file named in configs/stores.yaml
        exclude_doc_ids: ignored (no orders in this store)

    Returns:
        Rows written.
    """
    store = StatuteStore()
    store.build(interim_dir, out_dir)
    store.open(out_dir)
    try:
        return store.count()
    finally:
        store.close()
