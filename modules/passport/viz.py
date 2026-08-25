"""
Passport VIZ OCR  -  Visual Inspection Zone extraction.

Extracts biographical fields from the printed data page of a passport
using EasyOCR. The VIZ is cross-checked against MRZ fields to detect
inconsistencies that reveal tampering.

Fields extracted:
  - Surname, given names
  - Date of birth
  - Date of issue
  - Date of expiry
  - Place of birth
  - Passport number (printed above MRZ)
  - Nationality
"""

import re
from typing import Optional

import easyocr
import numpy as np

_reader: Optional[easyocr.Reader] = None


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def extract_viz_fields(image: np.ndarray) -> dict:
    """
    Extract VIZ fields from a passport biographical page image.

    Args:
        image: BGR numpy array of the passport bio page (perspective-corrected).

    Returns:
        dict with keys: surname, given_names, dob, doi, doe, pob,
                        passport_number, nationality, raw_text, confidence
    """
    reader = _get_reader()
    results = reader.readtext(image, detail=1)
    raw_text = "\n".join([r[1] for r in results])
    confidences = [r[2] for r in results]
    avg_conf = float(np.mean(confidences)) if confidences else 0.0

    return {
        "surname": _extract_surname(raw_text),
        "given_names": _extract_given_names(raw_text),
        "dob": _extract_date_field(raw_text, ["date of birth", "birth", "dob"]),
        "doi": _extract_date_field(raw_text, ["date of issue", "issue"]),
        "doe": _extract_date_field(
            raw_text, ["date of expiry", "expiry", "valid till"]
        ),
        "pob": _extract_pob(raw_text),
        "passport_number": _extract_passport_number(raw_text),
        "nationality": _extract_nationality(raw_text),
        "raw_text": raw_text,
        "confidence": round(avg_conf, 4),
    }


# ── Private helpers ────────────────────────────────────────────────────────────


def _extract_surname(text: str) -> Optional[str]:
    match = re.search(
        r"(?:surname|last\s*name)[:\s]+([A-Z][A-Za-z\s\-]+)", text, re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    return None


def _extract_given_names(text: str) -> Optional[str]:
    match = re.search(
        r"(?:given\s*name[s]?|first\s*name)[:\s]+([A-Z][A-Za-z\s\-]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return None


def _extract_date_field(text: str, labels: list) -> Optional[str]:
    """Find a date near any of the label keywords."""
    for label in labels:
        pattern = rf"(?:{label})[:\s/]+(\d{{2}}[/\-\s]\d{{2}}[/\-\s]\d{{4}}|\d{{2}}\s+\w{{3}}\s+\d{{4}})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _normalize_date(match.group(1))
    # Fallback: find any date near the label
    for label in labels:
        idx = text.lower().find(label)
        if idx != -1:
            snippet = text[idx : idx + 40]
            dm = re.search(r"(\d{2}[/\-]\d{2}[/\-]\d{4})", snippet)
            if dm:
                return _normalize_date(dm.group(1))
    return None


def _extract_pob(text: str) -> Optional[str]:
    match = re.search(
        r"(?:place of birth|pob)[:\s]+([A-Za-z\s,]+)", text, re.IGNORECASE
    )
    if match:
        return match.group(1).strip()[:50]
    return None


def _extract_passport_number(text: str) -> Optional[str]:
    """Indian passport number: 1 letter + 7 digits (e.g. A1234567)."""
    match = re.search(r"\b([A-Z]\d{7})\b", text)
    return match.group(1) if match else None


def _extract_nationality(text: str) -> Optional[str]:
    match = re.search(r"(?:nationality)[:\s]+([A-Za-z]+)", text, re.IGNORECASE)
    return match.group(1).upper() if match else None


def _normalize_date(date_str: str) -> str:
    """Normalize to DD/MM/YYYY."""
    date_str = date_str.strip()
    # Already DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"(\d{2})[/\-](\d{2})[/\-](\d{4})", date_str)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    # DD Mon YYYY
    MONTHS = {
        "jan": "01",
        "feb": "02",
        "mar": "03",
        "apr": "04",
        "may": "05",
        "jun": "06",
        "jul": "07",
        "aug": "08",
        "sep": "09",
        "oct": "10",
        "nov": "11",
        "dec": "12",
    }
    m2 = re.match(r"(\d{2})\s+([A-Za-z]{3})\s+(\d{4})", date_str)
    if m2:
        mon = MONTHS.get(m2.group(2).lower(), "00")
        return f"{m2.group(1)}/{mon}/{m2.group(3)}"
    return date_str
