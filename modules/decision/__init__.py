"""
Decision Module
---------------
scorer.py     - Explainable weighted risk score formula
llm_summary.py - Gemini Flash plain-language officer summary
"""
from .scorer import compute_score
from .llm_summary import generate_summary
