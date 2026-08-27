"""
Generic National Identity Card Adapter.

Primary engine: OpenBharatOCR (voter_id_front).
Fallback: EasyOCR + regex pattern matching.
"""

import logging
import os
import re
import tempfile
from typing import Optional

import cv2
import easyocr
import numpy as np

logger = logging.getLogger(__name__)
_reader: Optional[easyocr.Reader] = None


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def _try_openbharatocr_voter(image: np.ndarray) -> Optional[dict]:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        temp_path = f.name
    try:
        cv2.imwrite(temp_path, image)
        import openbharatocr
        res = openbharatocr.voter_id_front(temp_path)
        if isinstance(res, dict) and any(res.values()):
            return res
        return None
    except Exception as e:
        logger.debug("OpenBharatOCR Voter ID extraction exception: %s", e)
        return None
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def extract_generic_id_fields(image: np.ndarray, reader=None) -> dict:
    if image is None or getattr(image, "size", 0) == 0:
        return {}

    # 1. Primary: OpenBharatOCR
    obo_res = _try_openbharatocr_voter(image)
    if obo_res:
        epic_num = obo_res.get("EPIC No") or obo_res.get("voter_id") or obo_res.get("Card No")
        name = obo_res.get("Name") or obo_res.get("name")
        dob = obo_res.get("DOB") or obo_res.get("dob") or obo_res.get("Age")
        if epic_num or name:
            return {
                "id_number": epic_num,
                "name": name,
                "dob": dob,
                "expiry_date": None,
                "raw_text": str(obo_res),
                "confidence": 0.93,
                "ocr_engine": "openbharatocr",
            }

    # 2. Fallback: EasyOCR
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
        "ocr_engine": "easyocr",
    }


def _extract_id_number(lines: list, full_text: str) -> Optional[str]:
    m_epic = re.search(r"\b([A-Z]{3}\d{7})\b", full_text)
    if m_epic:
        return m_epic.group(1)
    
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
        m = re.search(rf"(?:{kw})[:\s]+(\d{{2}}[\/\-\.]\d{{2}}[\/\-\.]\d{{4}})", text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None
