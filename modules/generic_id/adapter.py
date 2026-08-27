"""
Generic National Identity Card Adapter.
Provides fallback extraction and rule validation for non-MRZ identity cards (Nepal, Bhutan, Voter ID).
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


def extract_generic_id_fields(image: np.ndarray, reader=None) -> dict:
    if image is None or getattr(image, "size", 0) == 0:
        return {}

    ocr_reader = reader or _get_reader()
    results = ocr_reader.readtext(image, detail=0)
    full_text = "\n".join(results)

    id_number = _extract_id_number(results, full_text)
    name = _extract_name(results)
    dob = _extract_date(full_text, ["dob", "birth", "date of birth"])
    expiry = _extract_date(full_text, ["expiry", "valid", "valide"])

    return {
        "id_number": id_number,
        "name": name,
        "dob": dob,
        "expiry_date": expiry,
        "raw_text": full_text,
        "confidence": 0.85,
    }


def _extract_id_number(lines: list, full_text: str) -> Optional[str]:
    # Voter ID: 3 letters + 7 digits (e.g. ABC1234567)
    m_epic = re.search(r"\b([A-Z]{3}\d{7})\b", full_text)
    if m_epic:
        return m_epic.group(1)
    
    # Generic alphanumeric ID (6-16 chars)
    for line in lines:
        if "NO" in line.upper() or "ID" in line.upper() or "CARD" in line.upper():
            m = re.search(r"\b([A-Z0-9-]{6,16})\b", line)
            if m:
                return m.group(1)
    return None


def _extract_name(lines: list) -> Optional[str]:
    EXCLUDE = {"ELECTION", "COMMISSION", "IDENTITY", "CARD", "GOVERNMENT", "NATIONAL", "REPUBLIC", "CITIZEN"}
    for line in lines:
        words = [w.upper() for w in re.findall(r"[A-Za-z]+", line)]
        if len(words) >= 2 and not any(w in EXCLUDE for w in words):
            return line.strip()
    return None


def _extract_date(text: str, keywords: list) -> Optional[str]:
    for kw in keywords:
        m = re.search(rf"(?:{kw})[:\s]+(\d{{2}}[/\-\.]\d{{2}}[/\-\.]\d{{4}})", text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None
