"""
Face Module
-----------
embedder.py      - ArcFace embedding engine (shared by all face checks)
match.py         - Document photo vs live capture face match
liveness.py      - Passive (LBP texture) + active (EAR blink) liveness
identity_graph.py - FAISS-backed cross-visit identity graph
"""

from .embedder import cosine_similarity, get_embedding, similarity_to_verdict
from .identity_graph import get_stats, search_and_store
from .liveness import detect_blink_in_frame, passive_liveness_check
from .match import match_face_to_document
