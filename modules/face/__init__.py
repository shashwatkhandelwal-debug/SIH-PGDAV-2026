"""
Face Module
-----------
embedder.py      - ArcFace embedding engine (shared by all face checks)
match.py         - Document photo vs live capture face match
liveness.py      - Passive (LBP texture) + active (EAR blink) liveness
identity_graph.py - FAISS-backed cross-visit identity graph
"""
from .embedder import get_embedding, cosine_similarity, similarity_to_verdict
from .match import match_face_to_document
from .liveness import passive_liveness_check, detect_blink_in_frame
from .identity_graph import search_and_store, get_stats
