"""
MRZ Parser  -  ICAO 9303 TD3 format (full passport, 2 × 44 chars).

Parses both lines, extracts all fields and validates check digits
using the ICAO 7-3-1 cyclic weighting algorithm.
"""

import re
from datetime import datetime
from typing import Optional

WEIGHTS = [7, 3, 1]

CHAR_VALUES = {c: i + 10 for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
CHAR_VALUES.update({str(i): i for i in range(10)})
CHAR_VALUES["<"] = 0


def icao_check_digit(field: str) -> int:
    """Compute ICAO 7-3-1 weighted check digit for a field string."""
    total = sum(CHAR_VALUES.get(c, 0) * WEIGHTS[i % 3] for i, c in enumerate(field))
    return total % 10


def parse_mrz(mrz_line1: str, mrz_line2: str) -> dict:
    """
    Parse a TD3 MRZ (2 × 44 chars) and validate all check digits.

    Returns dict with:
      doc_type, issuing_country, surname, given_names,
      passport_number, nationality, dob, sex, expiry,
      personal_number, check_digits (all pass/fail),
      valid (overall bool), raw (dict of raw field strings)
    """
    l1 = mrz_line1.upper().replace(" ", "<")
    l2 = mrz_line2.upper().replace(" ", "<")

    if len(l1) != 44 or len(l2) != 44:
        return {
            "valid": False,
            "error": f"MRZ line length invalid: {len(l1)}, {len(l2)}",
        }

    # ── Line 1 ──
    doc_type = l1[0:2].replace("<", "").strip()
    issuing_ctry = l1[2:5]
    name_field = l1[5:44]
    surname, *given = name_field.split("<<")
    given_names = " ".join(" ".join(g.split("<")) for g in given).strip()
    surname = surname.replace("<", " ").strip()

    # ── Line 2 ──
    passport_num = l2[0:9]
    cd_pn = int(l2[9])
    nationality = l2[10:13]
    dob_raw = l2[13:19]
    cd_dob = int(l2[19])
    sex = l2[20]
    expiry_raw = l2[21:27]
    cd_expiry = int(l2[27])
    personal_num = l2[28:42]
    cd_personal = int(l2[42])
    cd_overall = int(l2[43])
    overall_field = l2[0:10] + l2[13:20] + l2[21:43]

    # ── Check digit validation ──
    checks = {
        "passport_number": icao_check_digit(passport_num) == cd_pn,
        "dob": icao_check_digit(dob_raw) == cd_dob,
        "expiry": icao_check_digit(expiry_raw) == cd_expiry,
        "personal_number": icao_check_digit(personal_num) == cd_personal,
        "overall": icao_check_digit(overall_field) == cd_overall,
    }
    all_valid = all(checks.values())

    return {
        "valid": all_valid,
        "doc_type": doc_type,
        "issuing_country": issuing_ctry,
        "surname": surname,
        "given_names": given_names,
        "passport_number": passport_num.replace("<", ""),
        "nationality": nationality,
        "dob": _parse_date(dob_raw),
        "sex": sex,
        "expiry": _parse_date(expiry_raw),
        "personal_number": personal_num.replace("<", ""),
        "check_digits": checks,
        "raw": {
            "line1": l1,
            "line2": l2,
            "passport_number": passport_num,
            "dob": dob_raw,
            "expiry": expiry_raw,
        },
    }


def _parse_date(yymmdd: str) -> Optional[str]:
    """Convert YYMMDD to DD/MM/YYYY. Handles century pivot at 30."""
    try:
        yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
        year = 2000 + yy if yy < 30 else 1900 + yy
        return f"{dd:02d}/{mm:02d}/{year}"
    except Exception:
        return None
