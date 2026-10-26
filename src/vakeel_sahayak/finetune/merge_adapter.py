"""Export the adapter and int4 weights for the laptop (plan §12).

The laptop loads Qwen3-4B in int4 (the same weights as Munshi) and applies this LoRA adapter (`models.yaml` llm.extractor_4b). `export_for_laptop`
copies the adapter files and writes a manifest (base model, rank, sha256 of every file) so the local client can check what it loads. The adapter is
only a few tens of MB; the int4 base is quantised on the laptop at load (bitsandbytes), so no merged weights are shipped by default.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ADAPTER_FILES = ("adapter_config.json", "adapter_model.safetensors", "adapter_model.bin")
EXTRA_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
    "added_tokens.json",
    "chat_template.jinja",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_for_laptop(adapter_dir: str, out_dir: str) -> str:
    """Package for local_llm client.

    Args:
        adapter_dir: folder written by `train_qlora.train` (needs `adapter_config.json` and the adapter weights)
        out_dir: folder that receives the adapter files and `manifest.json`

    Returns:
        Output path.
    """
    src = Path(adapter_dir)
    if not src.is_dir() or not (src / "adapter_config.json").is_file():
        raise FileNotFoundError(f"no adapter at {adapter_dir} (train one first: scripts/ada/sbatch_qlora.sbatch)")
    if not any((src / f).is_file() for f in ADAPTER_FILES[1:]):
        raise FileNotFoundError(f"adapter weights (adapter_model.safetensors) missing in {adapter_dir}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ADAPTER_FILES + EXTRA_FILES:
        if (src / name).is_file():
            shutil.copy2(src / name, out / name)
            copied.append(name)
    cfg = json.loads((src / "adapter_config.json").read_text(encoding="utf-8"))
    manifest = {
        "base_model": cfg.get("base_model_name_or_path"),
        "lora_r": cfg.get("r"),
        "target_modules": cfg.get("target_modules"),
        "quantisation_at_load": {"bits": 4, "type": "nf4"},
        "files": {name: _sha256(out / name) for name in copied},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return str(out)


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m vakeel_sahayak.finetune.merge_adapter ADAPTER_DIR OUT_DIR."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python -m vakeel_sahayak.finetune.merge_adapter ADAPTER_DIR OUT_DIR")
        return 2
    print(export_for_laptop(args[0], args[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
