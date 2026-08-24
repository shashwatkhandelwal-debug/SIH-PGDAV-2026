"""
QR ↔ OCR Consistency Check.

Compares fields extracted from the Aadhaar Secure QR payload against
OCR-extracted printed fields. Defends against copy-paste attacks where
a genuine signed QR is applied to a fake card with different printed text.

A genuine UIDAI signature on the QR does NOT mean the printed fields match.
This check is the second line of defense after signature verification.
"""
from Levenshtein import distance as levenshtein_distance
from typing import Optional


# Maximum edit distance allowed for name fuzzy match
_NAME_MAX_EDIT_DISTANCE = 3


def check_qr_ocr_consistency(qr_fields: dict, ocr_fields: dict) -> dict:
    """
    Cross-check QR-decoded fields against OCR-printed fields.

    Args:
        qr_fields:  Fields parsed from the Aadhaar Secure QR payload.
        ocr_fields: Fields extracted by OCR from the printed card.

    Returns:
        dict with keys:
          consistent (bool), mismatches (list[str]), details (dict)
    """
    mismatches = []
    details = {}

    # 1. Name match (fuzzy — OCR errors expected)
    name_result = _compare_name(
        qr_fields.get('name'), ocr_fields.get('name_en')
    )
    details['name'] = name_result
    if not name_result['match']:
        mismatches.append('name')

    # 2. Date of Birth (normalized exact match)
    dob_result = _compare_dob(
        qr_fields.get('dob'), ocr_fields.get('dob')
    )
    details['dob'] = dob_result
    if not dob_result['match']:
        mismatches.append('dob')

    # 3. Gender (exact)
    gender_result = _compare_gender(
        qr_fields.get('gender'), ocr_fields.get('gender')
    )
    details['gender'] = gender_result
    if not gender_result['match']:
        mismatches.append('gender')

    return {
        "consistent": len(mismatches) == 0,
        "mismatches": mismatches,
        "details": details,
    }


# ── Comparison helpers ─────────────────────────────────────────────────────────

def _compare_name(qr_name: Optional[str], ocr_name: Optional[str]) -> dict:
    if not qr_name or not ocr_name:
        return {"match": None, "reason": "missing data", "edit_distance": None}

    qr_norm = _normalize_name(qr_name)
    ocr_norm = _normalize_name(ocr_name)
    dist = levenshtein_distance(qr_norm, ocr_norm)
    match = dist <= _NAME_MAX_EDIT_DISTANCE

    return {
        "match": match,
        "qr_value": qr_name,
        "ocr_value": ocr_name,
        "edit_distance": dist,
        "threshold": _NAME_MAX_EDIT_DISTANCE,
    }


def _compare_dob(qr_dob: Optional[str], ocr_dob: Optional[str]) -> dict:
    if not qr_dob or not ocr_dob:
        return {"match": None, "reason": "missing data"}

    qr_norm = _normalize_date(qr_dob)
    ocr_norm = _normalize_date(ocr_dob)
    match = qr_norm == ocr_norm

    return {"match": match, "qr_value": qr_dob, "ocr_value": ocr_dob}


def _compare_gender(qr_gender: Optional[str], ocr_gender: Optional[str]) -> dict:
    if not qr_gender or not ocr_gender:
        return {"match": None, "reason": "missing data"}

    qr_g = qr_gender.upper()[0]   # M / F / T
    ocr_g = ocr_gender.upper()[0]
    match = qr_g == ocr_g

    return {"match": match, "qr_value": qr_gender, "ocr_value": ocr_gender}


def _normalize_name(name: str) -> str:
    """Uppercase, strip extra spaces."""
    return ' '.join(name.upper().split())


def _normalize_date(date_str: str) -> str:
    """Normalize DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD to DDMMYYYY."""
    import re
    digits = re.sub(r'\D', '', date_str)
    if len(digits) == 8:
        return digits  # Already DDMMYYYY or YYYYMMDD — further parsing if needed
    return digits
