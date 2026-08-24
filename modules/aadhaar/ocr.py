"""
Aadhaar OCR  -  Extract printed fields from Aadhaar card image.

Extracts:
  - UID number (12 digits)
  - Name (English)
  - Name (Hindi / Devanagari)
  - Date of Birth (DD/MM/YYYY)
  - Gender
  - Address
"""
import re
import easyocr
import numpy as np
from PIL import Image
from typing import Optional

_reader: Optional[easyocr.Reader] = None


def _get_reader() -> easyocr.Reader:
    """Lazy-init EasyOCR reader (supports English + Hindi)."""
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['en', 'hi'], gpu=False)
    return _reader


def extract_aadhaar_fields(image: np.ndarray) -> dict:
    """
    Extract all printed fields from an Aadhaar card image.

    Args:
        image: BGR numpy array of the Aadhaar card (perspective-corrected).

    Returns:
        dict with keys: uid, name_en, name_hi, dob, gender, address, raw_text, confidence
    """
    reader = _get_reader()
    results = reader.readtext(image, detail=1)  # Returns (bbox, text, confidence)

    raw_text = " ".join([r[1] for r in results])
    confidences = [r[2] for r in results]
    avg_confidence = float(np.mean(confidences)) if confidences else 0.0

    uid = _extract_uid(raw_text)
    dob = _extract_dob(raw_text)
    gender = _extract_gender(raw_text)
    name_en = _extract_name_english(raw_text)
    name_hi = _extract_name_hindi(results)

    return {
        "uid": uid,
        "name_en": name_en,
        "name_hi": name_hi,
        "dob": dob,
        "gender": gender,
        "address": _extract_address(raw_text),
        "raw_text": raw_text,
        "confidence": round(avg_confidence, 4),
    }


# ── Private helpers ────────────────────────────────────────────────────────────

def _extract_uid(text: str) -> Optional[str]:
    """Extract 12-digit UID, stripping spaces."""
    match = re.search(r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b', text)
    if match:
        return re.sub(r'[\s\-]', '', match.group(1))
    return None


def _extract_dob(text: str) -> Optional[str]:
    """Extract DOB in DD/MM/YYYY format."""
    match = re.search(r'\b(\d{2}[/\-]\d{2}[/\-]\d{4})\b', text)
    if match:
        return match.group(1).replace('-', '/')
    # Handle 'Year of Birth: YYYY' format on older cards
    match = re.search(r'(?:Year of Birth|YOB)[:\s]+(\d{4})', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_gender(text: str) -> Optional[str]:
    """Detect gender from printed text."""
    text_upper = text.upper()
    if 'MALE' in text_upper and 'FE' not in text_upper:
        return 'MALE'
    if 'FEMALE' in text_upper:
        return 'FEMALE'
    if 'TRANSGENDER' in text_upper:
        return 'TRANSGENDER'
    return None


def _extract_name_english(text: str) -> Optional[str]:
    """
    Heuristic: Name is typically the longest consecutive all-caps / Title Case
    sequence before or after the DOB line, excluding common label words.
    """
    EXCLUDE = {'GOVERNMENT', 'INDIA', 'UIDAI', 'AADHAAR', 'MALE', 'FEMALE',
               'DATE', 'BIRTH', 'ADDRESS', 'YEAR', 'DOB'}
    candidates = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,4}\b', text)
    for candidate in candidates:
        if not any(w.upper() in EXCLUDE for w in candidate.split()):
            return candidate
    return None


def _extract_name_hindi(results: list) -> Optional[str]:
    """
    Extract Hindi name  -  Devanagari script characters (U+0900–U+097F).
    EasyOCR with 'hi' lang returns Devanagari text separately.
    """
    devanagari_texts = []
    for (bbox, text, conf) in results:
        if re.search(r'[\u0900-\u097F]', text):
            devanagari_texts.append(text.strip())
    return ' '.join(devanagari_texts) if devanagari_texts else None


def _extract_address(text: str) -> Optional[str]:
    """
    Address extraction: text following 'Address:' or 'S/O', 'D/O', 'C/O' markers.
    Returns the tail of the text as a best-effort address.
    """
    match = re.search(r'(?:Address|S/O|D/O|C/O)[:\s]+(.+)', text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()[:300]  # Cap at 300 chars
    return None
