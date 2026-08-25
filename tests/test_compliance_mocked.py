import sys
import os
import json
import numpy as np
import cv2
from unittest.mock import patch

sys.path.insert(0, r"C:\Users\ASUS\Downloads\SIH-PGDAV-2026")
from api.orchestrator import _run_aadhaar_checks, _run_passport_checks, _run_visa_checks, _finalize


def get_mock_image():
    # Generate a pattern with random Gaussian noise to ensure blur check succeeds with non-zero score
    img = np.zeros((550, 800, 3), dtype=np.uint8)
    cv2.randn(img, 127, 40)
    return img


async def test_aadhaar_genuine():
    # 12-digit UID with correct check digit (6)
    ocr_mock = {
        "uid": "234123412346",
        "name_en": "Shashwat Khandelwal",
        "name_hi": "शाश्वत खंडेलवाल",
        "dob": "12/05/1990",
        "gender": "MALE",
        "address": "7/168 B Swaroop nagar Kanpur",
        "confidence": 0.95
    }
    qr_mock = {
        "format": "binary",
        "fields": {
            "name": "Shashwat Khandelwal",
            "dob": "12/05/1990",
            "gender": "M"
        },
        "raw_payload": b"signed_payload",
        "signature": b"sig_bytes",
        "region": (100, 200, 300, 400),
        "error": None
    }
    
    img = get_mock_image()
    
    with patch("modules.aadhaar.ocr.extract_aadhaar_fields", return_value=ocr_mock), \
         patch("modules.aadhaar.qr.decode_aadhaar_qr", return_value=qr_mock), \
         patch("modules.aadhaar.signature.verify_uidai_signature", return_value={"valid": True}), \
         patch("modules.aadhaar.consistency.check_qr_ocr_consistency", return_value={"consistent": True, "mismatches": []}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 1.2, "heatmap": np.zeros((10,10,3)), "suspicious": False}):
         
         results, notes = await _run_aadhaar_checks(img)
         resp = await _finalize(results, "AADHAAR", ocr_mock["uid"], ocr_mock["name_en"], {}, notes)
         print("\n========================================")
         print("GENUINE AADHAAR JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_aadhaar_tampered():
    # 12-digit UID with invalid check digit (1 instead of 6)
    ocr_mock = {
        "uid": "234123412341",
        "name_en": "Shashwat Khandelwal",
        "name_hi": "शाश्वत खंडेलवाल",
        "dob": "12/05/1990",
        "gender": "MALE",
        "address": "7/168 B Swaroop nagar Kanpur",
        "confidence": 0.95
    }
    qr_mock = {
        "format": "binary",
        "fields": {
            "name": "Fake Name",
            "dob": "12/05/1990",
            "gender": "M"
        },
        "raw_payload": b"signed_payload",
        "signature": b"sig_bytes",
        "region": (100, 200, 300, 400),
        "error": None
    }
    
    img = get_mock_image()
    
    with patch("modules.aadhaar.ocr.extract_aadhaar_fields", return_value=ocr_mock), \
         patch("modules.aadhaar.qr.decode_aadhaar_qr", return_value=qr_mock), \
         patch("modules.aadhaar.signature.verify_uidai_signature", return_value={"valid": False, "error": "Signature mismatch"}), \
         patch("modules.aadhaar.consistency.check_qr_ocr_consistency", return_value={"consistent": False, "mismatches": ["name"]}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 22.5, "heatmap": np.zeros((10,10,3)), "suspicious": True}):
         
         results, notes = await _run_aadhaar_checks(img)
         resp = await _finalize(results, "AADHAAR", ocr_mock["uid"], ocr_mock["name_en"], {}, notes)
         print("\n========================================")
         print("TAMPERED AADHAAR JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_passport_genuine():
    mrz_mock = {
        "valid": True,
        "passport_number": "L8406789",
        "surname": "KHANDELWAL",
        "given_names": "SHASHWAT",
        "nationality": "IND",
        "dob": "12/05/1990",
        "sex": "M",
        "expiry": "01/01/2035",
        "check_digits": {
            "passport_number": True,
            "dob": True,
            "expiry": True,
            "personal_number": True,
            "overall": True
        }
    }
    viz_mock = {
        "passport_number": "L8406789",
        "surname": "KHANDELWAL",
        "given_names": "SHASHWAT",
        "dob": "12/05/1990",
        "nationality": "IND",
        "doe": "01/01/2035",
        "confidence": 0.95
    }
    
    img = get_mock_image()
    
    with patch("api.orchestrator._extract_mrz_from_image", return_value=mrz_mock), \
         patch("modules.passport.viz.extract_viz_fields", return_value=viz_mock), \
         patch("modules.passport.consistency.check_mrz_viz_consistency", return_value={"consistent": True, "mismatches": []}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 1.4, "heatmap": np.zeros((10,10,3)), "suspicious": False}):
         
         results, notes = await _run_passport_checks(img, nfc_available=False)
         resp = await _finalize(results, "PASSPORT", "L8406789", "KHANDELWAL SHASHWAT", {}, notes)
         print("\n========================================")
         print("GENUINE PASSPORT JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_passport_tampered():
    # MRZ check digits fail
    mrz_mock = {
        "valid": False,
        "passport_number": "L8406789",
        "surname": "KHANDELWAL",
        "given_names": "SHASHWAT",
        "nationality": "IND",
        "dob": "12/05/1990",
        "sex": "M",
        "expiry": "01/01/2035",
        "check_digits": {
            "passport_number": False,  # Failed check digit
            "dob": True,
            "expiry": True,
            "personal_number": True,
            "overall": True
        }
    }
    viz_mock = {
        "passport_number": "L8406789",
        "surname": "FAKE_NAME",
        "given_names": "SHASHWAT",
        "dob": "12/05/1990",
        "nationality": "IND",
        "doe": "01/01/2035",
        "confidence": 0.95
    }
    
    img = get_mock_image()
    
    with patch("api.orchestrator._extract_mrz_from_image", return_value=mrz_mock), \
         patch("modules.passport.viz.extract_viz_fields", return_value=viz_mock), \
         patch("modules.passport.consistency.check_mrz_viz_consistency", return_value={"consistent": False, "mismatches": ["surname"]}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 28.5, "heatmap": np.zeros((10,10,3)), "suspicious": True}):
         
         results, notes = await _run_passport_checks(img, nfc_available=False)
         resp = await _finalize(results, "PASSPORT", "L8406789", "KHANDELWAL SHASHWAT", {}, notes)
         print("\n========================================")
         print("TAMPERED PASSPORT JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_visa_genuine():
    visa_mock = {
        "visa_number": "TV1234567",
        "visa_type": "Tourist",
        "date_of_issue": "12/05/2026",
        "date_of_expiry": "12/11/2026",
        "duration_days": 90,
        "num_entries": "Multiple",
        "passport_number": "L8406789",
        "applicant_name": "Shashwat Khandelwal",
        "confidence": 0.95
    }
    
    img = get_mock_image()
    
    with patch("modules.visa.ocr.extract_visa_fields", return_value=visa_mock), \
         patch("modules.visa.rules.validate_visa_rules", return_value={"valid": True, "score": 1.0, "violations": []}), \
         patch("modules.visa.binding.check_visa_passport_binding", return_value={"bound": True, "score": 1.0}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 1.1, "heatmap": np.zeros((10,10,3)), "suspicious": False}):
         
         results, notes = await _run_visa_checks(img, passport_mrz_number="L8406789")
         resp = await _finalize(results, "VISA", "TV1234567", "Shashwat Khandelwal", {}, notes)
         print("\n========================================")
         print("GENUINE VISA JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_visa_tampered():
    # Rules violate transit visa length
    visa_mock = {
        "visa_number": "TV1234567",
        "visa_type": "Transit",
        "date_of_issue": "12/05/2026",
        "date_of_expiry": "12/11/2026",
        "duration_days": 90,  # Transit is max 3 days
        "num_entries": "Single",
        "passport_number": "L8406789",
        "applicant_name": "Shashwat Khandelwal",
        "confidence": 0.95
    }
    
    img = get_mock_image()
    
    with patch("modules.visa.ocr.extract_visa_fields", return_value=visa_mock), \
         patch("modules.visa.rules.validate_visa_rules", return_value={"valid": False, "score": 0.2, "violations": ["Stay duration 90 days exceeds max 3 days for Transit"]}), \
         patch("modules.visa.binding.check_visa_passport_binding", return_value={"bound": False, "score": 0.0}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 19.8, "heatmap": np.zeros((10,10,3)), "suspicious": True}):
         
         results, notes = await _run_visa_checks(img, passport_mrz_number="X9999999")  # different passport
         resp = await _finalize(results, "VISA", "TV1234567", "Shashwat Khandelwal", {}, notes)
         print("\n========================================")
         print("TAMPERED VISA JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_visa_duration_rule_only_fail():
    # Stay duration exceeds transit rules, but binding is clean and ELA is clean
    visa_mock = {
        "visa_number": "TV1234567",
        "visa_type": "Transit",
        "date_of_issue": "12/05/2026",
        "date_of_expiry": "12/11/2026",
        "duration_days": 90,  # Transit is max 3 days
        "num_entries": "Single",
        "passport_number": "L8406789",
        "applicant_name": "Shashwat Khandelwal",
        "confidence": 0.95
    }
    
    img = get_mock_image()
    
    with patch("modules.visa.ocr.extract_visa_fields", return_value=visa_mock), \
         patch("modules.visa.rules.validate_visa_rules", return_value={"valid": False, "score": 0.2, "violations": ["Stay duration 90 days exceeds max 3 days for Transit"]}), \
         patch("modules.visa.binding.check_visa_passport_binding", return_value={"bound": True, "score": 1.0}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 1.1, "heatmap": np.zeros((10,10,3)), "suspicious": False}):
         
         results, notes = await _run_visa_checks(img, passport_mrz_number="L8406789")  # correct passport binding
         resp = await _finalize(results, "VISA", "TV1234567", "Shashwat Khandelwal", {}, notes)
         print("\n========================================")
         print("VISA DURATION-ONLY RULE VIOLATION JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def main():
    await test_aadhaar_genuine()
    await test_aadhaar_tampered()
    await test_passport_genuine()
    await test_passport_tampered()
    await test_visa_genuine()
    await test_visa_tampered()
    await test_visa_duration_rule_only_fail()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
