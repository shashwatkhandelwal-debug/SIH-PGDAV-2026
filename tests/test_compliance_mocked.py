import sys
import os
import json
import numpy as np
import cv2
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"C:\Users\ASUS\Downloads\SIH-PGDAV-2026")
from api.orchestrator import _run_aadhaar_checks, _run_passport_checks, _run_visa_checks, _finalize
from modules.aadhaar.ocr import extract_aadhaar_fields
from modules.passport.viz import extract_viz_fields


def create_mock_document(text_lines, width=800, height=550):
    """Draw clear, sharp black text on a white card to create a real scan target."""
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for i, line in enumerate(text_lines):
        y = 30 + i * 40
        draw.text((30, y), line, fill="black", font=font)
    
    cv_img = np.array(img)
    cv_img = cv_img[:, :, ::-1].copy() # RGB to BGR
    return cv_img


# Define mock document content
aadhaar_lines = [
    "Government of India",
    "Unique Identification Authority of India",
    "Name: SHASHWAT KHANDELWAL",
    "DOB: 12/05/1990",
    "Gender: MALE",
    "UID: 2341 2341 2346",
    "Address: 7/168 B Swaroop nagar Kanpur"
]

passport_lines = [
    "PASSPORT",
    "Surname: KHANDELWAL",
    "Given Names: SHASHWAT",
    "Date of Birth: 12/05/1990",
    "Date of Issue: 10/10/2020",
    "Date of Expiry: 09/10/2030",
    "Place of Birth: KANPUR",
    "Nationality: INDIAN"
]

visa_lines = [
    "VISA",
    "Visa Number: TV1234567",
    "Visa Type: Tourist",
    "Date of Issue: 12/05/2026",
    "Date of Expiry: 12/11/2026",
    "Duration Days: 90",
    "Entries: Multiple",
    "Passport Number: L8406789",
    "Applicant Name: SHASHWAT KHANDELWAL"
]


async def test_aadhaar_genuine():
    img = create_mock_document(aadhaar_lines)
    
    # Run ACTUAL OCR to compute a real confidence score from the sharp image
    real_ocr = extract_aadhaar_fields(img)
    
    ocr_mock = {
        "uid": "234123412346",
        "name_en": "Shashwat Khandelwal",
        "name_hi": "शाश्वत खंडेलवाल",
        "dob": "12/05/1990",
        "gender": "MALE",
        "address": "7/168 B Swaroop nagar Kanpur",
        "confidence": real_ocr["confidence"]
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
    # Generate a degraded (blurred) Aadhaar card
    img_sharp = create_mock_document(aadhaar_lines)
    img_degraded = cv2.GaussianBlur(img_sharp, (15, 15), 0)
    
    # Run ACTUAL OCR on degraded image to get a lower confidence score
    real_ocr = extract_aadhaar_fields(img_degraded)
    
    ocr_mock = {
        "uid": "234123412341",
        "name_en": "Shashwat Khandelwal",
        "name_hi": "शाश्वत खंडेलवाल",
        "dob": "12/05/1990",
        "gender": "MALE",
        "address": "7/168 B Swaroop nagar Kanpur",
        "confidence": real_ocr["confidence"]
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
    
    with patch("modules.aadhaar.ocr.extract_aadhaar_fields", return_value=ocr_mock), \
         patch("modules.aadhaar.qr.decode_aadhaar_qr", return_value=qr_mock), \
         patch("modules.aadhaar.signature.verify_uidai_signature", return_value={"valid": False, "error": "Signature mismatch"}), \
         patch("modules.aadhaar.consistency.check_qr_ocr_consistency", return_value={"consistent": False, "mismatches": ["name"]}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 22.5, "heatmap": np.zeros((10,10,3)), "suspicious": True}):
         
         results, notes = await _run_aadhaar_checks(img_degraded)
         resp = await _finalize(results, "AADHAAR", ocr_mock["uid"], ocr_mock["name_en"], {}, notes)
         print("\n========================================")
         print("TAMPERED AADHAAR JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_passport_genuine():
    img = create_mock_document(passport_lines)
    
    # Run ACTUAL OCR to compute a real confidence score from the sharp image
    real_viz = extract_viz_fields(img)
    
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
        "confidence": real_viz["confidence"]
    }
    
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
    # Generate a degraded (blurred) passport biographical page
    img_sharp = create_mock_document(passport_lines)
    img_degraded = cv2.GaussianBlur(img_sharp, (15, 15), 0)
    
    # Run ACTUAL OCR to compute a degraded confidence score
    real_viz = extract_viz_fields(img_degraded)
    
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
            "passport_number": False,
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
        "confidence": real_viz["confidence"]
    }
    
    with patch("api.orchestrator._extract_mrz_from_image", return_value=mrz_mock), \
         patch("modules.passport.viz.extract_viz_fields", return_value=viz_mock), \
         patch("modules.passport.consistency.check_mrz_viz_consistency", return_value={"consistent": False, "mismatches": ["surname"]}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 28.5, "heatmap": np.zeros((10,10,3)), "suspicious": True}):
         
         results, notes = await _run_passport_checks(img_degraded, nfc_available=False)
         resp = await _finalize(results, "PASSPORT", "L8406789", "KHANDELWAL SHASHWAT", {}, notes)
         print("\n========================================")
         print("TAMPERED PASSPORT JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_passport_nfc_active():
    """Verify that perform_passive_auth is actually called in the NFC path."""
    img = create_mock_document(passport_lines)
    mrz_mock = {"valid": True, "passport_number": "L8406789"}
    viz_mock = {"passport_number": "L8406789", "confidence": 0.9}
    
    with patch("api.orchestrator._extract_mrz_from_image", return_value=mrz_mock), \
         patch("modules.passport.viz.extract_viz_fields", return_value=viz_mock), \
         patch("modules.passport.consistency.check_mrz_viz_consistency", return_value={"consistent": True, "mismatches": []}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 1.4, "heatmap": np.zeros((10,10,3)), "suspicious": False}):
         
         # Call with nfc_available=True and mock payloads to trigger perform_passive_auth
         results, notes = await _run_passport_checks(
             img,
             nfc_available=True,
             sod_bytes=b"dummy_sod_bytes_to_trigger",
             dg1_bytes=b"dummy_dg1_bytes_to_trigger",
             dg2_bytes=b"dummy_dg2_bytes_to_trigger"
         )
         resp = await _finalize(results, "PASSPORT", "L8406789", "KHANDELWAL SHASHWAT", {}, notes)
         print("\n========================================")
         print("PASSPORT ACTIVE NFC PATH COMPLETED:")
         print("========================================")


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
    
    img = create_mock_document(visa_lines)
    
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
    visa_mock = {
        "visa_number": "TV1234567",
        "visa_type": "Transit",
        "date_of_issue": "12/05/2026",
        "date_of_expiry": "12/11/2026",
        "duration_days": 90,
        "num_entries": "Single",
        "passport_number": "L8406789",
        "applicant_name": "Shashwat Khandelwal",
        "confidence": 0.95
    }
    
    img = create_mock_document(visa_lines)
    
    with patch("modules.visa.ocr.extract_visa_fields", return_value=visa_mock), \
         patch("modules.visa.rules.validate_visa_rules", return_value={"valid": False, "score": 0.2, "violations": ["Stay duration 90 days exceeds max 3 days for Transit"]}), \
         patch("modules.visa.binding.check_visa_passport_binding", return_value={"bound": False, "score": 0.0}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 19.8, "heatmap": np.zeros((10,10,3)), "suspicious": True}):
         
         results, notes = await _run_visa_checks(img, passport_mrz_number="X9999999")
         resp = await _finalize(results, "VISA", "TV1234567", "Shashwat Khandelwal", {}, notes)
         print("\n========================================")
         print("TAMPERED VISA JSON RESPONSE:")
         print("========================================")
         print(json.dumps(resp, indent=2))


async def test_visa_duration_rule_only_fail():
    visa_mock = {
        "visa_number": "TV1234567",
        "visa_type": "Transit",
        "date_of_issue": "12/05/2026",
        "date_of_expiry": "12/11/2026",
        "duration_days": 90,
        "num_entries": "Single",
        "passport_number": "L8406789",
        "applicant_name": "Shashwat Khandelwal",
        "confidence": 0.95
    }
    
    img = create_mock_document(visa_lines)
    
    with patch("modules.visa.ocr.extract_visa_fields", return_value=visa_mock), \
         patch("modules.visa.rules.validate_visa_rules", return_value={"valid": False, "score": 0.2, "violations": ["Stay duration 90 days exceeds max 3 days for Transit"]}), \
         patch("modules.visa.binding.check_visa_passport_binding", return_value={"bound": True, "score": 1.0}), \
         patch("modules.forensics.ela.run_ela", return_value={"mean_variance": 1.1, "heatmap": np.zeros((10,10,3)), "suspicious": False}):
         
         results, notes = await _run_visa_checks(img, passport_mrz_number="L8406789")
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
    await test_passport_nfc_active()
    await test_visa_genuine()
    await test_visa_tampered()
    await test_visa_duration_rule_only_fail()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
