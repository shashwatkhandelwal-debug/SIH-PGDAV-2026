"""
Error Level Analysis (ELA) — JPEG Compression Forensics.

Detects regions of a document image that have a different JPEG compression
history than the surrounding image — evidence of digital splicing or editing.

Theory:
  JPEG compression is lossy via DCT quantization. Recompressing an image at
  a fixed quality Q produces near-zero pixel differences in regions already
  at quality Q, and elevated differences in regions edited/saved at a
  different quality (e.g., a spliced photo or modified text block).

Three modes:
  1. full_document  — whole image ELA (detects large-scale edits)
  2. region         — ELA restricted to a supplied bounding box (photo/QR/stamp)
  3. heatmap        — returns amplified RGB difference array for visualization
"""
import io
import numpy as np
from PIL import Image
from typing import Optional


def run_ela(
    image: np.ndarray,
    quality: int = 90,
    region: Optional[tuple] = None,
) -> dict:
    """
    Run ELA on an image or a sub-region.

    Args:
        image:   BGR numpy array of the document.
        quality: JPEG recompression quality (0–95). Default 90.
        region:  Optional (x1, y1, x2, y2) tuple to restrict analysis.
                 If None, analyses the full image.

    Returns:
        dict with keys:
          mean_variance (float)  — average pixel-level difference variance
          max_variance  (float)  — maximum variance across channels
          heatmap       (np.ndarray) — amplified difference map (RGB uint8)
          suspicious    (bool)   — True if variance exceeds threshold
          threshold     (float)  — threshold used
    """
    pil_img = Image.fromarray(image[..., ::-1])  # BGR→RGB

    if region:
        x1, y1, x2, y2 = region
        pil_img = pil_img.crop((x1, y1, x2, y2))

    # Recompress at fixed quality
    buffer = io.BytesIO()
    pil_img.save(buffer, format='JPEG', quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer).convert('RGB')

    orig_arr = np.array(pil_img, dtype=np.float32)
    recomp_arr = np.array(recompressed, dtype=np.float32)

    diff = np.abs(orig_arr - recomp_arr)
    mean_var = float(diff.mean())
    max_var = float(diff.max())

    # Amplify for visualization
    scale = 255.0 / (diff.max() + 1e-6)
    heatmap = np.clip(diff * scale, 0, 255).astype(np.uint8)

    # Threshold: empirically set, higher for lower-quality originals
    threshold = _adaptive_threshold(image, quality)
    suspicious = mean_var > threshold

    return {
        "mean_variance": round(mean_var, 4),
        "max_variance": round(max_var, 4),
        "heatmap": heatmap,
        "suspicious": suspicious,
        "threshold": threshold,
        "region": region,
    }


def _adaptive_threshold(image: np.ndarray, recomp_quality: int) -> float:
    """
    Estimate adaptive ELA threshold from the image's estimated JPEG quality.
    Higher original quality → lower expected ELA variance → tighter threshold.
    Lower original quality → higher baseline variance → looser threshold.

    Returns a mean-variance threshold float.
    """
    # Encode to JPEG, read back quality from quantization tables
    pil = Image.fromarray(image[..., ::-1])
    buf = io.BytesIO()
    pil.save(buf, format='JPEG', quality=95)  # Save at near-lossless
    buf.seek(0)
    img_back = Image.open(buf)

    # Crude quality estimate: variance of luma channel
    luma = np.array(img_back.convert('L'), dtype=np.float32)
    luma_var = float(np.var(luma))

    # Scale threshold inversely with estimated quality
    if luma_var > 3000:
        return 8.0   # High-quality scan — tight threshold
    elif luma_var > 1000:
        return 12.0  # Medium quality
    else:
        return 18.0  # Low quality / heavily compressed
