"""Page-image clean-up: deskew, dewarp, denoise (plan §4.1 K3 K4, §4.2 step 3). OpenCV is imported lazily.

The stand-in images of the offline plain-text source pass through unchanged. A real image needs the `ocr` extra
(opencv-python-headless); without it `clean_image_bytes` raises `ModelUnavailable`.
"""

from __future__ import annotations

from vakeel_sahayak.ingestion.source import is_fixture_image
from vakeel_sahayak.models.base import ModelUnavailable

CLEAN_OPS = ("deskew", "dewarp", "denoise")
DEFAULT_OPS = ["deskew"]
STRONG_OPS = ["dewarp", "deskew", "denoise"]
_ORDER = {op: i for i, op in enumerate(STRONG_OPS)}  # always dewarp, then deskew, then denoise


def _cv():  # noqa: ANN202
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ModelUnavailable("opencv-python-headless and numpy are not installed, so page images cannot be cleaned", "ocr") from exc
    return cv2, np


def _deskew(cv2, np, img):  # noqa: ANN001, ANN202
    """Rotate by the angle (-10 to 10 degrees) whose horizontal projection profile is sharpest."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    scale = 600.0 / max(1, gray.shape[1])
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ink = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    h, w = ink.shape
    best_angle, best_score = 0.0, -1.0
    for angle in np.arange(-10.0, 10.5, 0.5):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), float(angle), 1.0)
        rotated = cv2.warpAffine(ink, m, (w, h), flags=cv2.INTER_NEAREST)
        score = float(np.var(rotated.sum(axis=1)))
        if score > best_score:
            best_angle, best_score = float(angle), score
    if abs(best_angle) < 0.3:
        return img
    ih, iw = img.shape[:2]
    m = cv2.getRotationMatrix2D((iw / 2, ih / 2), best_angle, 1.0)
    return cv2.warpAffine(img, m, (iw, ih), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _order_points(np, pts):  # noqa: ANN001, ANN202
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype="float32")


def _dewarp(cv2, np, img):  # noqa: ANN001, ANN202
    """Crop and flatten the page when its four corners can be found as the largest quadrilateral."""
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 50, 150), None, iterations=2)
    contours = sorted(cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea, reverse=True)
    for contour in contours[:5]:
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.contourArea(approx) > 0.3 * img.shape[0] * img.shape[1]:
            rect = _order_points(np, approx.reshape(4, 2).astype("float32"))
            tl, tr, br, bl = rect
            width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
            height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
            target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
            return cv2.warpPerspective(img, cv2.getPerspectiveTransform(rect, target), (width, height))
    return img


def clean_image_bytes(image: bytes, ops: list[str] | None = None) -> bytes:
    """Clean up a page image.

    Args:
        image: encoded image (PNG, JPEG, ...)
        ops: subset of 'deskew', 'dewarp', 'denoise'; defaults to deskew. They always run in the order dewarp, deskew, denoise.

    Returns:
        PNG bytes of the cleaned image (the input unchanged for an offline stand-in image).

    Raises:
        ValueError: for an unknown operation or an image that cannot be decoded.
        ModelUnavailable: OpenCV is not installed.
    """
    chosen = DEFAULT_OPS if ops is None else list(ops)
    unknown = [op for op in chosen if op not in CLEAN_OPS]
    if unknown:
        raise ValueError(f"unknown clean-up operations {unknown}: use {list(CLEAN_OPS)}")
    if is_fixture_image(image) or not chosen:
        return image
    cv2, np = _cv()
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("the image could not be decoded")
    for op in sorted(set(chosen), key=_ORDER.get):
        if op == "dewarp":
            img = _dewarp(cv2, np, img)
        elif op == "deskew":
            img = _deskew(cv2, np, img)
        else:
            img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
    ok, encoded = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("the cleaned image could not be encoded")
    return encoded.tobytes()
