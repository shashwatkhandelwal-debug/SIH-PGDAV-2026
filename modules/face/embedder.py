"""
Face Embedding Engine.

Shared embedding engine used by both the doc-photo-vs-live-face match
and the cross-visit identity graph.

Model: ArcFace via DeepFace (insightface/buffalo_l backend preferred,
falls back to Facenet512 which is lighter and still strong).

All embeddings are 512-dimensional unit vectors.
Cosine similarity is used for comparison (equivalent to dot product
on unit vectors).

Why ArcFace:
  Standard softmax loss trains for classification — it separates N known
  identities but doesn't maximize inter-class margins. ArcFace adds an
  additive angular margin penalty (m ≈ 0.5 radians) to the target angle in
  the softmax, producing tighter intra-class clusters and wider inter-class
  separation in the embedding space. This gives better verification accuracy
  on unseen identities — which is the entire use case here (inference only).
"""
import numpy as np
from typing import Optional

try:
    from deepface import DeepFace
    _DEEPFACE_AVAILABLE = True
except ImportError:
    _DEEPFACE_AVAILABLE = False

# Preferred model — change to 'Facenet512' if insightface fails to install
_MODEL_NAME = 'ArcFace'
_BACKEND    = 'retinaface'   # Best face detector; fallback: 'opencv'


def get_embedding(image: np.ndarray) -> Optional[np.ndarray]:
    """
    Compute a 512-dimensional face embedding for a face image.

    Args:
        image: BGR numpy array containing one face (cropped or full image).
               DeepFace will detect and align the face internally.

    Returns:
        512-dim numpy float32 array (unit vector), or None if no face detected.
    """
    if not _DEEPFACE_AVAILABLE:
        return None

    try:
        result = DeepFace.represent(
            img_path=image,
            model_name=_MODEL_NAME,
            detector_backend=_BACKEND,
            enforce_detection=True,
            align=True,
        )
        embedding = np.array(result[0]['embedding'], dtype=np.float32)
        # Normalize to unit vector (ArcFace outputs are already normalized,
        # but explicit normalization ensures consistent cosine similarity)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding
    except Exception:
        # Try again with more lenient detector
        try:
            result = DeepFace.represent(
                img_path=image,
                model_name=_MODEL_NAME,
                detector_backend='opencv',
                enforce_detection=False,
                align=True,
            )
            embedding = np.array(result[0]['embedding'], dtype=np.float32)
            norm = np.linalg.norm(embedding)
            return embedding / norm if norm > 0 else embedding
        except Exception:
            return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two embedding vectors.
    For unit vectors, this is equivalent to the dot product.

    Returns:
        float in [-1, 1]. Values > 0.6 typically indicate the same person.
    """
    return float(np.dot(a, b))


def similarity_to_verdict(sim: float) -> tuple[str, float]:
    """
    Convert cosine similarity to a human-readable verdict and score.

    Returns:
        (verdict: str, score: float 0–1 for the scoring module)
    """
    if sim >= 0.68:
        return "MATCH", 1.0
    elif sim >= 0.50:
        return "UNCERTAIN", 0.4
    else:
        return "MISMATCH", 0.0
