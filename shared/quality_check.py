"""
Document Quality Pre-Check.

Validates that an image meets minimum quality requirements before
running OCR or forensics. Prevents silent garbage-output from blurry
or low-resolution inputs.
"""
import cv2
import numpy as np


MIN_RESOLUTION = (400, 300)   # Minimum width × height in pixels
BLUR_THRESHOLD = 80.0         # Laplacian variance below this = blurry


def check_quality(image: np.ndarray) -> dict:
    """
    Check document image quality.

    Args:
        image: BGR numpy array.

    Returns:
        dict with keys:
          acceptable (bool)
          issues     (list[str])
          blur_score (float)   — higher is sharper
          resolution (tuple)   — (width, height)
    """
    issues = []
    h, w = image.shape[:2]

    # Resolution check
    if w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
        issues.append(f"Resolution too low: {w}×{h}px (minimum {MIN_RESOLUTION[0]}×{MIN_RESOLUTION[1]}px)")

    # Blur check (Laplacian variance)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < BLUR_THRESHOLD:
        issues.append(f"Image too blurry (sharpness score: {blur_score:.1f}, minimum: {BLUR_THRESHOLD})")

    return {
        "acceptable": len(issues) == 0,
        "issues": issues,
        "blur_score": round(blur_score, 2),
        "resolution": (w, h),
    }
