"""Assemble the SFT dataset (chat format), excluding test and same-FIR orders (plan §2, §12).

Rows are {"messages": [system, user = facts text, assistant = target dossier JSON]}. The exclusion list comes from
`pipelines.leakage.excluded_doc_ids` over `<interim>/splits.json` and `<interim>/orders.jsonl`; a missing splits file is an error, never a
silent "nothing excluded". Train/dev is a deterministic hash split (about 10% dev, at least one row) used for the threshold tuning of plan §14.2.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vakeel_sahayak.finetune._io import read_rows, write_rows

DEV_SHARE = 0.1
SYSTEM_PROMPT = (
    "Read the facts section of an Indian bail order and output the CaseDossier as JSON. For every field you fill, quote the source "
    "sentence in source.quote. Leave a field empty when the text does not state it."
)


def _excluded() -> set[str]:
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.pipelines import leakage

    interim = Path(load_config().paths.interim_dir)
    return set(leakage.excluded_doc_ids(str(interim / "splits.json"), str(interim / "orders.jsonl")))


def chat_row(pair: dict[str, Any]) -> dict[str, Any]:
    """One pair as a conversation: facts in, the teacher's dossier JSON out (the target never changes under noise)."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": pair["facts"]},
            {"role": "assistant", "content": json.dumps(pair["dossier"], ensure_ascii=False)},
        ]
    }


def _rank(doc_id: str) -> str:
    return hashlib.sha256(str(doc_id).encode("utf-8")).hexdigest()


def build_sft_dataset(pairs_path: str, out_dir: str) -> int:
    """Write train/dev jsonl.

    Args:
        pairs_path: JSONL of {"doc_id", "facts", "dossier"} rows (after span filter and noise augmentation)
        out_dir: folder that receives `train.jsonl` and `dev.jsonl`

    Returns:
        Rows (train plus dev) after excluding test and same-FIR orders.
    """
    excluded = _excluded()
    pairs = [p for p in read_rows(pairs_path) if str(p.get("doc_id")) not in excluded]
    n_dev = max(1, round(DEV_SHARE * len(pairs))) if len(pairs) > 1 else 0
    dev_ids = {id(p) for p in sorted(pairs, key=lambda p: _rank(p["doc_id"]))[:n_dev]}
    out = Path(out_dir)
    write_rows(out / "train.jsonl", (chat_row(p) for p in pairs if id(p) not in dev_ids))
    write_rows(out / "dev.jsonl", (chat_row(p) for p in pairs if id(p) in dev_ids))
    return len(pairs)


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m vakeel_sahayak.finetune.build_dataset PAIRS OUT_DIR."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python -m vakeel_sahayak.finetune.build_dataset PAIRS.jsonl OUT_DIR")
        return 2
    print(f"{build_sft_dataset(args[0], args[1])} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
