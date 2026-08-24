"""
Shared image preprocessing utilities.

- Perspective correction (document deskewing)
- Image loading and format normalization
- Region cropping helpers
"""
import cv2
import numpy as np
from typing import Optional


def load_image(source) -> Optional[np.ndarray]:
    """
    Load an image from a file path, bytes, or numpy array.
    Always returns a BGR numpy array.
    """
    if isinstance(source, np.ndarray):
        return source
    if isinstance(source, bytes):
        buf = np.frombuffer(source, dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if isinstance(source, str):
        return cv2.imread(source)
    return None


def correct_perspective(image: np.ndarray, output_size: tuple = (800, 550)) -> np.ndarray:
    """
    Detect document corners and apply perspective correction.

    Finds the largest quadrilateral contour (assumed to be the document),
    orders its corners (TL, TR, BR, BL), and warps to a flat rectangle.

    Args:
        image:       BGR numpy array with the document on any background.
        output_size: (width, height) of the output corrected image.

    Returns:
        Perspective-corrected BGR numpy array, or original if correction fails.
    """
    gray   = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur   = cv2.GaussianBlur(gray, (5, 5), 0)
    edges  = cv2.Canny(blur, 75, 200)

    # Dilate to close small gaps in document border
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges  = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

    doc_corners = None
    for c in contours:
        peri  = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            # Minimum area check — reject tiny quads
            if cv2.contourArea(approx) > 0.10 * image.shape[0] * image.shape[1]:
                doc_corners = approx.reshape(4, 2).astype(np.float32)
                break

    if doc_corners is None:
        return image  # Fallback: return original

    ordered = _order_corners(doc_corners)
    w, h    = output_size
    dst     = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)

    M       = cv2.getPerspectiveTransform(ordered, dst)
    warped  = cv2.warpPerspective(image, M, (w, h))
    return warped


def crop_region(image: np.ndarray, region_frac: tuple) -> np.ndarray:
    """
    Crop a relative region from the image.

    Args:
        image:       BGR numpy array.
        region_frac: (x1_frac, y1_frac, x2_frac, y2_frac) — values in [0, 1].

    Returns:
        Cropped BGR array.
    """
    h, w = image.shape[:2]
    x1f, y1f, x2f, y2f = region_frac
    x1, y1 = int(x1f * w), int(y1f * h)
    x2, y2 = int(x2f * w), int(y2f * h)
    return image[y1:y2, x1:x2]


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """
    Order 4 corner points as: [top-left, top-right, bottom-right, bottom-left].
    """
    rect  = np.zeros((4, 2), dtype=np.float32)
    s     = pts.sum(axis=1)
    diff  = np.diff(pts, axis=1).ravel()

    rect[0] = pts[np.argmin(s)]     # TL: smallest x+y
    rect[2] = pts[np.argmax(s)]     # BR: largest x+y
    rect[1] = pts[np.argmin(diff)]  # TR: smallest y-x
    rect[3] = pts[np.argmax(diff)]  # BL: largest y-x
    return rect
