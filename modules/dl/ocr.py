"""
Indian Driving Licence (DL) OCR Extractor.

Extracts:
  - DL Number (Standard Sarathi formats: State Code [A-Z]{2} + Year + 7-digit sequential, or legacy formats)
  - Holder Name
  - Date of Birth (DOB)
  - Issue Date (DOI)
  - Expiry Date / Validity (DOE)
  - Authorised Vehicle Classes (e.g. LMV, MCWG, HGMV)
"""

import os
import re
from typing import Optional

import easyocr
import numpy as np

_reader: Optional[easyocr.Reader] = None


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        try:
            _reader = easyocr.Reader(["en"], gpu=False)
        except Exception:
            _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def extract_dl_fields(image: np.ndarray, reader=None) -> dict:
    """
    Extract structured biographical and validity fields from an Indian Driving Licence image.
    """
    if image is None or getattr(image, "size", 0) == 0:
        return {}

    ocr_reader = reader or _get_reader()
    results = ocr_reader.readtext(image, detail=1)

    raw_text_lines = []
    confidences = []

    for item in results:
        if isinstance(item, (list, tuple)) and len(item) > 1:
            raw_text_lines.append(str(item[1]).strip())
            if len(item) > 2 and isinstance(item[2], (int, float)):
                confidences.append(float(item[2]))

    full_text = "\n".join(raw_text_lines)
    avg_conf = float(np.mean(confidences)) if confidences else 0.85

    dl_number = _extract_dl_number(full_text, raw_text_lines)
    name = _extract_dl_name(full_text, raw_text_lines)
    dob = _extract_dl_date(full_text, ["DOB", "D.O.B", "Birth", "Date of Birth"])
    issue_date = _extract_dl_date(full_text, ["Issue", "DOI", "Issued", "Date of Issue"])
    expiry_date = _extract_dl_date(full_text, ["Valid", "Expiry", "DOE", "Valid Till", "NT", "TR"])
    vehicle_classes = _extract_vehicle_classes(full_text)

    return {
        "dl_number": dl_number,
        "name": name,
        "dob": dob,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "vehicle_classes": vehicle_classes,
        "raw_text": full_text,
        "confidence": round(avg_conf, 4),
    }


def _extract_dl_number(text: str, lines: list) -> Optional[str]:
    pattern = r"\b([A-Z]{2}[-\s]?\d{2}[-\s]?\d{4}[-\s]?\d{7})\b"
    m = re.search(pattern, text)
    if m:
        return re.sub(r"[-\s]", "", m.group(1))

    gen_pattern = r"\b([A-Z]{2}[-\s\d]{11,18})\b"
    for line in lines:
        if "DL" in line.upper() or "LICENCE" in line.upper() or "NO" in line.upper():
            m2 = re.search(gen_pattern, line)
            if m2:
                cand = re.sub(r"[-\s]", "", m2.group(1))
                if len(cand) >= 13 and cand[:2].isalpha() and cand[2:].isdigit():
                    return cand

    m3 = re.search(gen_pattern, text)
    if m3:
        cand = re.sub(r"[-\s]", "", m3.group(1))
        if len(cand) >= 13 and cand[:2].isalpha() and cand[2:].isdigit():
            return cand
    return None


def _extract_dl_name(text: str, lines: list) -> Optional[str]:
    EXCLUDE = {"UNION", "INDIA", "DRIVING", "LICENCE", "LICENSE", "TRANSPORT", "DEPARTMENT", "STATE", "GOVERNMENT", "FORM"}
    for idx, line in enumerate(lines):
        clean = line.strip()
        if re.search(r"(?:Name|Holder|S/O|D/O|W/O)[:\s]+", clean, re.IGNORECASE):
            cand = re.sub(r"^(?:Name|Holder|S/O|D/O|W/O)[:\s]+", "", clean, flags=re.IGNORECASE).strip()
            words = [w.upper() for w in re.findall(r"[A-Za-z]+", cand)]
            if len(words) >= 2 and not any(w in EXCLUDE for w in words):
                return cand
        if clean.upper() in ("NAME", "NAME:", "HOLDER NAME"):
            if idx + 1 < len(lines):
                cand = lines[idx + 1].strip()
                words = [w.upper() for w in re.findall(r"[A-Za-z]+", cand)]
                if len(words) >= 2 and not any(w in EXCLUDE for w in words):
                    return cand
    return None


def _extract_dl_date(text: str, keywords: list) -> Optional[str]:
    for kw in keywords:
        pattern = rf"(?:{kw})[:\s]+(\d{{2}}[/\-\.]\d{{2}}[/\-\.]\d{{4}})"
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return _normalize_date(m.group(1))

    dates = re.findall(r"\b(\d{{2}}[/\-\.]\d{{2}}[/\-\.]\d{{4}})\b", text)
    if dates:
        return _normalize_date(dates[0])
    return None


def _extract_vehicle_classes(text: str) -> list:
    KNOWN_CLASSES = ["MCWG", "MCWOG", "LMV", "LMV-NT", "TRANS", "HGMV", "HPMV", "3W-CAB"]
    found = []
    text_up = text.upper()
    for vc in KNOWN_CLASSES:
        if vc in text_up:
            found.append(vc)
    return found if found else ["LMV"]


def _normalize_date(s: str) -> str:
    m = re.match(r"(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})", s.strip())
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return s.strip()
