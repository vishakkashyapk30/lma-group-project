"""DOCX to PDF via headless LibreOffice (plan §13.1)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

TIMEOUT_S = 120


def docx_to_pdf(docx_path: str) -> str:
    """Convert and return PDF path.

    Runs `soffice --headless --convert-to pdf` (or `libreoffice`, whichever is installed) into the DOCX's folder.

    Args:
        docx_path: the DOCX to convert

    Returns:
        PDF path, next to the DOCX.

    Raises:
        RuntimeError: LibreOffice is missing, failed, or wrote no PDF.
    """
    src = Path(docx_path).resolve()
    binary = shutil.which("soffice") or shutil.which("libreoffice") or "soffice"
    cmd = [binary, "--headless", "--convert-to", "pdf", "--outdir", str(src.parent), str(src)]
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_S, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("PDF export needs LibreOffice (soffice) on PATH; the DOCX export works without it") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"LibreOffice did not finish converting {src.name} within {TIMEOUT_S} s") from exc
    out = src.with_suffix(".pdf")
    if done.returncode != 0 or not out.exists():
        detail = (done.stderr or b"").decode("utf-8", "replace").strip()[:300]
        raise RuntimeError(f"LibreOffice could not convert {src.name} (exit {done.returncode}): {detail or 'no PDF written'}")
    return str(out)
