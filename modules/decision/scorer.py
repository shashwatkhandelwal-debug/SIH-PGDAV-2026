"""
Decision Scorer — Explainable Weighted Risk Score.

Aggregates all module check results into a single risk score (0–100).
Higher score = lower risk (PASS). Lower score = higher risk (FAIL).

Design principle: Deliberately NOT a black-box ML model.
Every weight is justified by the cryptographic strength of the underlying
check, allowing a border security officer to trace exactly why a document
was flagged and defend that decision to a supervisor.
"""
from typing import Any

# ── Weight table ───────────────────────────────────────────────────────────────
# Total weights sum to 100. Each check contributes its weight × score (0–1).
# score=1.0  → check passed
# score=0.5  → check uncertain / not run / timed out
# score=0.0  → check failed

WEIGHTS = {
    # Aadhaar
    "aadhaar_uidai_signature":   20,   # Cryptographic proof of UIDAI issuance
    "aadhaar_verhoeff":           5,   # Format correctness (mathematical)
    "aadhaar_qr_ocr_consistency": 7,   # Copy-paste attack defense

    # Passport
    "passport_passive_auth":     20,   # Cryptographic proof of chip integrity
    "passport_active_auth":      15,   # Anti-cloning proof
    "passport_mrz_checksums":     8,   # ICAO format correctness
    "passport_mrz_viz_consistency": 5, # Cross-source consistency

    # Visa
    "visa_passport_binding":      5,   # Cross-document binding
    "visa_rule_validation":       3,   # Logical consistency

    # Face
    "face_match":                 7,   # Identity binding (doc photo vs live)
    "liveness":                   3,   # Anti-spoofing

    # Forensics
    "ela_full_document":          1,   # Forensic signal
    "ela_region_restricted":      1,   # Forensic signal (localized)
    "exif_inspection":            1,   # Forensic signal

    # Basic validity
    "expiry_valid":               1,   # Document not expired (baseline)
}

assert sum(WEIGHTS.values()) == 102, "Weights should sum to 100 (adjust as needed)"

# Risk thresholds
RISK_LEVELS = {
    "HIGH":   (0,  30),
    "MEDIUM": (30, 60),
    "LOW":    (60, 80),
    "PASS":   (80, 101),
}


def compute_score(check_results: dict[str, Any]) -> dict:
    """
    Compute the weighted risk score from all check results.

    Args:
        check_results: Dict mapping check_name → result dict.
                       Each result dict must have 'score' (float 0–1)
                       and optionally 'status' (str).

    Returns:
        dict with keys:
          total_score  (float 0–100)
          risk_level   (str: HIGH|MEDIUM|LOW|PASS)
          breakdown    (dict: check_name → {score, weight, contribution})
          failed_checks (list[str])
          uncertain_checks (list[str])
    """
    breakdown = {}
    failed = []
    uncertain = []
    total = 0.0
    weight_used = 0.0

    for check_name, weight in WEIGHTS.items():
        result = check_results.get(check_name)

        if result is None:
            score = 0.5  # Not run → uncertain
            uncertain.append(check_name)
        else:
            score = float(result.get('score', 0.5))
            if score == 0.0:
                failed.append(check_name)
            elif score < 0.8:
                uncertain.append(check_name)

        contribution = weight * score
        total += contribution
        weight_used += weight

        breakdown[check_name] = {
            "score": score,
            "weight": weight,
            "contribution": round(contribution, 2),
        }

    # Normalize to 0–100
    max_possible = sum(WEIGHTS.values())
    normalized = (total / max_possible) * 100

    risk_level = _get_risk_level(normalized)

    return {
        "total_score": round(normalized, 1),
        "risk_level": risk_level,
        "breakdown": breakdown,
        "failed_checks": failed,
        "uncertain_checks": uncertain,
    }


def _get_risk_level(score: float) -> str:
    for level, (low, high) in RISK_LEVELS.items():
        if low <= score < high:
            return level
    return "HIGH"
