"""
Unit tests for Aadhaar Secure QR parse and QR↔OCR consistency null-match handling.
"""

import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.aadhaar.consistency import check_qr_ocr_consistency
from modules.aadhaar.qr import (
    _parse_secure_qr_bytes,
    _parse_secure_qr_decimal,
    _split_delimiter_fields,
)
from modules.decision.llm_summary import _rule_based_summary


def _build_signed_secure_payload(
    name: str = "RAMESH KUMAR",
    dob: str = "01/01/1990",
    gender: str = "M",
) -> bytes:
    """Build a minimal 0xFF-delimited Secure QR signed body + 256-byte signature."""
    fields = [
        b"0",  # email/mobile flag
        name.encode("iso-8859-1"),
        dob.encode("iso-8859-1"),
        gender.encode("iso-8859-1"),
        b"S/O Suresh",  # care_of
        b"New Delhi",  # district
        b"",  # landmark
        b"12",  # house
        b"Karol Bagh",  # location
        b"110005",  # pincode
        b"Karol Bagh",  # postoffice
        b"Delhi",  # state
        b"Main Road",  # street
        b"",  # subdistrict
        b"Karol Bagh",  # vtc
    ]
    body = b"\xff".join(fields)
    signature = bytes([0xAB] * 256)
    return body + signature


def test_split_delimiter_fields():
    data = b"0\xffNAME\xff01/01/1990\xffM"
    parts = _split_delimiter_fields(data)
    assert parts[0] == b"0"
    assert parts[1] == b"NAME"
    assert parts[2] == b"01/01/1990"
    assert parts[3] == b"M"


def test_secure_qr_gzip_decimal_roundtrip():
    decompressed = _build_signed_secure_payload()
    compressed = gzip.compress(decompressed)
    decimal_str = str(int.from_bytes(compressed, byteorder="big"))

    result = _parse_secure_qr_decimal(decimal_str)
    assert result.get("error") is None, result.get("error")
    assert result["format"] == "secure"
    assert result["signature"] is not None
    assert len(result["signature"]) == 256
    assert result["raw_payload"] is not None
    assert len(result["raw_payload"]) == len(decompressed) - 256
    assert result["fields"]["name"] == "RAMESH KUMAR"
    assert result["fields"]["dob"] == "01/01/1990"
    assert result["fields"]["gender"] == "M"
    assert result["fields"]["pincode"] == "110005"


def test_secure_qr_bytes_direct_decompressed():
    decompressed = _build_signed_secure_payload(name="SITA DEVI", gender="F")
    result = _parse_secure_qr_bytes(decompressed)
    assert result.get("error") is None, result.get("error")
    assert result["fields"]["name"] == "SITA DEVI"
    assert result["fields"]["gender"] == "F"
    assert len(result["signature"]) == 256


def test_consistency_missing_fields_not_mismatches():
    result = check_qr_ocr_consistency({}, {"name_en": None, "dob": None, "gender": None})
    assert result["consistent"] is None
    assert result["mismatches"] == []
    assert result.get("error") == "insufficient_fields_for_comparison"


def test_consistency_partial_match_ok():
    qr = {"name": "RAMESH KUMAR", "dob": "01/01/1990", "gender": "M"}
    ocr = {"name_en": "RAMESH KUMAR", "dob": "01/01/1990", "gender": "MALE"}
    result = check_qr_ocr_consistency(qr, ocr)
    assert result["consistent"] is True
    assert result["mismatches"] == []


def test_consistency_name_mismatch():
    qr = {"name": "RAMESH KUMAR", "dob": "01/01/1990", "gender": "M"}
    ocr = {"name_en": "SURESH SHARMA", "dob": "01/01/1990", "gender": "MALE"}
    result = check_qr_ocr_consistency(qr, ocr)
    assert result["consistent"] is False
    assert "name" in result["mismatches"]


def test_consistency_none_match_ignored_when_other_fields_ok():
    qr = {"name": "RAMESH KUMAR", "dob": "01/01/1990", "gender": "M"}
    ocr = {"name_en": "RAMESH KUMAR", "dob": "01/01/1990", "gender": None}
    result = check_qr_ocr_consistency(qr, ocr)
    assert result["consistent"] is True
    assert result["mismatches"] == []
    assert result["details"]["gender"]["match"] is None


def test_officer_summary_qr_unreadable_not_mismatch_message():
    check_results = {
        "verification_tier": "QR_UNREADABLE",
        "aadhaar_uidai_signature": {
            "score": None,
            "valid": None,
            "error": "QR unreadable",
        },
        "aadhaar_qr_ocr_consistency": {
            "score": None,
            "consistent": None,
            "error": "qr_data_unavailable",
            "mismatches": [],
        },
        "aadhaar_verhoeff": {"score": 1.0},
        "ela_full_document": {"score": 1.0},
    }
    score_result = {
        "overall_score": 3.0,
        "status": "CLEAR",
        "failed_checks": ["aadhaar_qr_ocr_consistency"],
    }
    summary = _rule_based_summary(check_results, score_result)
    assert "does not match" not in summary.lower()
    assert "unreadable" in summary.lower() or "recapture" in summary.lower()


def test_hindi_slogan_filter():
    from modules.aadhaar.ocr import _extract_name_hindi, _is_hindi_slogan

    assert _is_hindi_slogan("मेरा आधार, मेरी पहचान")
    results = [
        (None, "६ ~प|००० रर ढ मेरा आधार, मेरी पहचान", 0.5),
        (None, "रमेश कुमार", 0.9),
    ]
    name = _extract_name_hindi(results)
    assert name == "रमेश कुमार"


def test_ocr_junk_name_rejected():
    from modules.aadhaar.ocr import _looks_like_ocr_junk

    assert _looks_like_ocr_junk("PAPunAYNN RclOOO") is True
    assert _looks_like_ocr_junk("RAMESH KUMAR") is False
