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

import os
import re
from typing import Optional

import easyocr
import numpy as np
from PIL import Image

_reader: Optional[easyocr.Reader] = None


def _clean_corrupt_easyocr_models():
    """Remove partial or corrupted model files from EasyOCR cache directory."""
    try:
        model_dir = os.path.expanduser("~/.EasyOCR/model")
        if os.path.exists(model_dir):
            for fname in os.listdir(model_dir):
                fpath = os.path.join(model_dir, fname)
                if os.path.isfile(fpath) and (fname.endswith(".pth") or fname.endswith(".tmp")):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
    except Exception:
        pass


import cv2


def _preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Multi-stage contrast, scaling and edge enhancement for OCR."""
    if image is None or image.size == 0:
        return image

    if len(image.shape) == 2:
        img = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        img = image.copy()

    # Scale to optimal OCR width (~1280px)
    h, w = img.shape[:2]
    target_w = 1280
    if w > 0 and w != target_w:
        scale = target_w / float(w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(
            img,
            (new_w, new_h),
            interpolation=cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA,
        )

    # CLAHE contrast enhancement in LAB color space
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l)
    enhanced_lab = cv2.merge((l_enhanced, a, b))
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # Unsharp masking for text edge clarity
    gaussian = cv2.GaussianBlur(enhanced_bgr, (0, 0), 2.0)
    unsharp = cv2.addWeighted(enhanced_bgr, 1.4, gaussian, -0.4, 0)
    return unsharp


def _get_reader() -> easyocr.Reader:
    """Lazy-init EasyOCR reader with robust fallback and corrupted cache recovery."""
    global _reader
    if _reader is None:
        try:
            _reader = easyocr.Reader(["en", "hi"], gpu=False)
        except (AssertionError, Exception):
            _clean_corrupt_easyocr_models()
            try:
                _reader = easyocr.Reader(["en"], gpu=False)
            except (AssertionError, Exception):
                _clean_corrupt_easyocr_models()
                _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def extract_aadhaar_fields(image: np.ndarray) -> dict:
    """
    Extract all printed fields from an Aadhaar card image using multi-pass OCR.

    Args:
        image: BGR numpy array of the Aadhaar card.

    Returns:
        dict with keys: uid, name_en, name_hi, dob, gender, address, raw_text, confidence
    """
    reader = _get_reader()

    # Pass 1: Enhanced contrast image
    enhanced = _preprocess_for_ocr(image)
    results = reader.readtext(enhanced, detail=1)

    raw_text = " ".join([r[1] for r in results])
    confidences = [r[2] for r in results]
    avg_confidence = float(np.mean(confidences)) if confidences else 0.0

    uid = _extract_uid(raw_text)
    dob = _extract_dob(raw_text)
    gender = _extract_gender(raw_text)
    name_en = _extract_name_english(raw_text, results)
    name_hi = _extract_name_hindi(results)

    # Pass 2 Fallback: If critical fields missing, try adaptive thresholded image
    if not uid or not name_en:
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
        )
        p2_results = reader.readtext(thresh, detail=1)
        p2_raw_text = " ".join([r[1] for r in p2_results])
        if not uid:
            uid = _extract_uid(p2_raw_text)
        if not name_en:
            name_en = _extract_name_english(p2_raw_text, p2_results)
        if not dob:
            dob = _extract_dob(p2_raw_text)
        if not gender:
            gender = _extract_gender(p2_raw_text)
        raw_text = f"{raw_text} {p2_raw_text}".strip()

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
    """Extract 12-digit UID, stripping spaces and common OCR letter confusions."""
    match = re.search(r"\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b", text)
    if match:
        return re.sub(r"[\s\-]", "", match.group(1))

    # Clean common OCR digit substitutions in numeric blocks
    cleaned = re.sub(r"[Oo]", "0", text)
    cleaned = re.sub(r"[Il|]", "1", cleaned)
    cleaned = re.sub(
        r"[SsbB]",
        lambda m: {"S": "5", "s": "5", "b": "6", "B": "8"}.get(
            m.group(0), m.group(0)
        ),
        cleaned,
    )
    match = re.search(r"\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b", cleaned)
    if match:
        return re.sub(r"[\s\-]", "", match.group(1))

    # Try matching any sequence of 12 digits separated by whitespace
    digits = re.findall(r"\d+", cleaned)
    joined_digits = "".join(digits)
    if len(joined_digits) == 12:
        return joined_digits
    if len(joined_digits) > 12:
        for i in range(len(joined_digits) - 11):
            cand = joined_digits[i : i + 12]
            return cand
    return None


def _extract_dob(text: str) -> Optional[str]:
    """Extract DOB in DD/MM/YYYY format with flexible separators and prefixes."""
    match = re.search(
        r"(?:DOB|Birth|Date|जन्म)?[:\s]*(\d{2}[/.\-\s]\d{2}[/.\-\s]\d{4})\b",
        text,
        re.IGNORECASE,
    )
    if match:
        raw_dob = match.group(1)
        return re.sub(r"[/.\-\s]+", "/", raw_dob)
    # Handle 'Year of Birth: YYYY' format on older cards
    match = re.search(
        r"(?:Year of Birth|YOB|जन्म वर्ष)[:\s]+(\d{4})", text, re.IGNORECASE
    )
    if match:
        return match.group(1)
    return None


def _extract_gender(text: str) -> Optional[str]:
    """Detect gender from printed text in English or Hindi."""
    text_upper = text.upper()
    if re.search(r"\b(FEMALE|महिला|WOMAN|WOMEN)\b", text_upper):
        return "FEMALE"
    if re.search(r"\b(MALE|पुरुष|MAN|MEN)\b", text_upper):
        return "MALE"
    if re.search(r"\b(TRANSGENDER|किन्नर)\b", text_upper):
        return "TRANSGENDER"
    return None


def _extract_name_english(
    text: str, line_results: Optional[list] = None
) -> Optional[str]:
    """
    Extract English name from line bounding boxes or raw text.
    Handles ALL CAPS names and Title Case names accurately.
    """
    EXCLUDE = {
        "GOVERNMENT",
        "INDIA",
        "UIDAI",
        "AADHAAR",
        "MALE",
        "FEMALE",
        "DATE",
        "BIRTH",
        "ADDRESS",
        "YEAR",
        "DOB",
        "HELP",
        "ENROLMENT",
        "MERI",
        "PEHCHAN",
        "BHARAT",
        "SARKAR",
        "MY",
        "CARD",
        "UNIQUE",
        "IDENTIFICATION",
        "AUTHORITY",
        "FATHER",
        "NAME",
        "HUSBAND",
        "VID",
        "OF",
        "TO",
        "THE",
        "IN",
        "AND",
        "OR",
        "NO",
        "PH",
        "PIN",
    }

    # 1. First check individual line bounding boxes from OCR
    if line_results:
        for item in line_results:
            line_str = (
                item[1]
                if isinstance(item, (list, tuple)) and len(item) > 1
                else str(item)
            )
            cleaned_line = line_str.strip()
            cleaned_line = re.sub(
                r"^(?:Name|नाम|Applicant Name)[:\s]+",
                "",
                cleaned_line,
                flags=re.IGNORECASE,
            ).strip()
            words = [w.upper() for w in re.findall(r"[A-Za-z]+", cleaned_line)]
            if len(words) >= 2 and not any(w in EXCLUDE for w in words):
                if (
                    re.match(r"^[A-Za-z\s.'-]+$", cleaned_line)
                    and len(cleaned_line) >= 4
                ):
                    return cleaned_line

    # 2. Fallback: filter known stop phrases from text
    filtered_text = text
    for stop_word in [
        "GOVERNMENT OF INDIA",
        "UNIQUE IDENTIFICATION AUTHORITY OF INDIA",
        "BHARAT SARKAR",
        "DATE OF BIRTH",
        "YEAR OF BIRTH",
        "MERI AADHAAR",
        "ENROLMENT NO",
        "HELP LINE",
    ]:
        filtered_text = re.sub(stop_word, " ", filtered_text, flags=re.IGNORECASE)

    words_with_case = re.findall(r"\b[A-Za-z.'-]+\b", filtered_text)
    for i in range(len(words_with_case) - 1):
        for length in [2, 3, 4]:
            if i + length <= len(words_with_case):
                cand_words = words_with_case[i : i + length]
                if not any(w.upper() in EXCLUDE for w in cand_words):
                    candidate = " ".join(cand_words)
                    if (
                        all(w[0].isupper() for w in cand_words)
                        and len(candidate) >= 4
                    ):
                        return candidate
    return None


def _extract_name_hindi(results: list) -> Optional[str]:
    """
    Extract Hindi name  -  Devanagari script characters (U+0900–U+097F).
    """
    devanagari_texts = []
    for item in results:
        text = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else str(item)
        if re.search(r"[\u0900-\u097F]", text):
            devanagari_texts.append(text.strip())
    return " ".join(devanagari_texts) if devanagari_texts else None


def _extract_address(text: str) -> Optional[str]:
    """
    Address extraction: text following 'Address:' or 'S/O', 'D/O', 'C/O' markers.
    """
    match = re.search(
        r"(?:Address|S/O|D/O|C/O|पता)[:\s]+(.+)", text, re.IGNORECASE | re.DOTALL
    )
    if match:
        return match.group(1).strip()[:300]
    return None
