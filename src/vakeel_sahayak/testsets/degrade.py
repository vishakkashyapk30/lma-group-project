"""Page degradations: faint photocopy, fax noise, blur, skew, stamps and signatures over text, JPEG artefacts (plan §15.2 T2, §12 noise-augmented training).

The degrader is written with Pillow and NumPy only (both ship with the `ocr` and `eval` extras), so it needs no Augraphy and no OpenCV. Everything is
drawn from one `numpy.random.Generator` seeded with `seed`, so the same image, severity and seed always give the same bytes; a different seed gives a
different page. Severity sets the strength of each effect:

* light: slight skew, mild blur, faint grain, JPEG quality 80.
* medium: skew up to 1.5 degrees, blur, grain, a few specks, uneven fading, one stamp, JPEG quality 55.
* heavy: skew up to 3 degrees, strong blur, heavy grain and salt-and-pepper noise, fax streaks, a stamp and a signature stroke over the text, JPEG quality 30.

Augraphy (Sarkar et al., ICDAR 2023) is the plan's reference tool; `engine="augraphy"` uses it when it is installed and raises ImportError otherwise.
"""

from __future__ import annotations

import io
from typing import Any

SEVERITIES: dict[str, dict[str, Any]] = {
    "light": {"skew": 0.6, "blur": 0.5, "grain": 4.0, "specks": 0.0, "fade": 0.05, "streaks": 0, "stamp": False, "signature": False, "quality": 80},
    "medium": {"skew": 1.5, "blur": 0.9, "grain": 9.0, "specks": 0.0006, "fade": 0.2, "streaks": 0, "stamp": True, "signature": False, "quality": 55},
    "heavy": {"skew": 3.0, "blur": 1.4, "grain": 16.0, "specks": 0.003, "fade": 0.35, "streaks": 6, "stamp": True, "signature": True, "quality": 30},
}


def _stamp(img: Any, rng: Any) -> None:
    """A round office stamp (two rings and a text band) in a grey-blue ink, somewhere on the page."""
    from PIL import ImageDraw

    w, h = img.size
    r = max(8, int(min(w, h) * rng.uniform(0.05, 0.09)))
    cx, cy = int(rng.uniform(r, w - r)), int(rng.uniform(r, h - r))
    d = ImageDraw.Draw(img)
    ink = int(rng.integers(70, 120))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ink, width=max(1, r // 14))
    d.ellipse((cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78), outline=ink, width=max(1, r // 20))
    d.rectangle((cx - r * 0.6, cy - r * 0.12, cx + r * 0.6, cy + r * 0.12), outline=ink, width=max(1, r // 24))
    d.text((cx - r * 0.5, cy - r * 0.08), "RECEIVED", fill=ink)


def _signature(img: Any, rng: Any) -> None:
    """A handwritten-looking stroke (a random smooth polyline) near the lower part of the page."""
    from PIL import ImageDraw

    w, h = img.size
    x, y = rng.uniform(0.1 * w, 0.5 * w), rng.uniform(0.6 * h, 0.9 * h)
    pts = []
    for _ in range(18):
        x += rng.uniform(0.01 * w, 0.04 * w)
        y += rng.uniform(-0.03 * h, 0.03 * h)
        pts.append((x, y))
    ImageDraw.Draw(img).line(pts, fill=int(rng.integers(20, 70)), width=max(1, w // 160))


def degrade_page(image: bytes, severity: str = "medium", seed: int = 0, engine: str = "pil") -> bytes:
    """K3 degradation (Pillow and NumPy; Augraphy on request).

    Args:
        image: encoded image bytes (PNG or JPEG)
        severity: "light", "medium" or "heavy"
        seed: random seed; the output is a pure function of (image, severity, seed)
        engine: "pil" (default) or "augraphy"

    Returns:
        Degraded page as JPEG bytes.

    Raises:
        ValueError: unknown severity or engine.
    """
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity {severity!r}; use one of {sorted(SEVERITIES)}")
    if engine not in ("pil", "augraphy"):
        raise ValueError(f"unknown engine {engine!r}")
    import numpy as np
    from PIL import Image, ImageFilter

    cfg = SEVERITIES[severity]
    rng = np.random.default_rng(seed)
    img = Image.open(io.BytesIO(image)).convert("L")
    if engine == "augraphy":
        try:
            from augraphy import default_augraphy_pipeline  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError("engine='augraphy' needs the augraphy package") from exc
        arr = np.asarray(img.convert("RGB"))
        import random as _random

        _random.seed(seed)
        np.random.seed(seed)  # noqa: NPY002  (augraphy draws from the global generators)
        out = default_augraphy_pipeline()(arr)
        img = Image.fromarray(out if out.ndim == 2 else out[..., :3]).convert("L")
    else:
        angle = float(rng.uniform(-cfg["skew"], cfg["skew"]))
        img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
        if cfg["stamp"]:
            _stamp(img, rng)
        if cfg["signature"]:
            _signature(img, rng)
        img = img.filter(ImageFilter.GaussianBlur(radius=cfg["blur"]))
        arr = np.asarray(img, dtype=np.float32)
        h, w = arr.shape
        # uneven fading: ink lightens towards one side, as on a worn photocopy
        ramp = np.linspace(0, 1, w, dtype=np.float32)[None, :]
        if rng.random() < 0.5:
            ramp = ramp[:, ::-1]
        arr = 255.0 - (255.0 - arr) * (1.0 - cfg["fade"] * ramp)
        arr += rng.normal(0.0, cfg["grain"], size=arr.shape).astype(np.float32)
        if cfg["specks"]:
            mask = rng.random(arr.shape) < cfg["specks"]
            arr[mask] = rng.choice([0.0, 255.0], size=int(mask.sum()))
        for _ in range(cfg["streaks"]):
            row = int(rng.integers(0, h))
            arr[row : row + int(rng.integers(1, 3)), :] -= float(rng.uniform(25, 70))
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=cfg["quality"])
    return buf.getvalue()
