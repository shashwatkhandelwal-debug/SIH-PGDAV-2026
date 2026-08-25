import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"C:\Users\ASUS\Downloads\SIH-PGDAV-2026")
from modules.aadhaar.ocr import extract_aadhaar_fields
from modules.passport.viz import extract_viz_fields


def create_clean_document(text_lines):
    img = Image.new("RGB", (800, 500), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for i, line in enumerate(text_lines):
        y = 30 + i * 40
        draw.text((30, y), line, fill="black", font=font)

    cv_img = np.array(img)
    cv_img = cv_img[:, :, ::-1].copy()  # RGB to BGR
    return cv_img


def main():
    print("Initializing EasyOCR Readers (this might take a few seconds)...")

    aadhaar_text = [
        "Government of India",
        "Unique Identification Authority of India",
        "Name: SHASHWAT KHANDELWAL",
        "DOB: 12/05/1990",
        "Gender: MALE",
        "UID: 2341 2341 2346",
        "Address: 7/168 B Swaroop nagar Kanpur",
    ]

    passport_text = [
        "PASSPORT",
        "Surname: KHANDELWAL",
        "Given Names: SHASHWAT",
        "Date of Birth: 12/05/1990",
        "Date of Issue: 10/10/2020",
        "Date of Expiry: 09/10/2030",
        "Place of Birth: KANPUR",
        "Nationality: INDIAN",
    ]

    # 1. Generate clean/sharp images
    aadhaar_clean = create_clean_document(aadhaar_text)
    passport_clean = create_clean_document(passport_text)

    # 2. Generate degraded (blurred) images
    aadhaar_blurry = cv2.GaussianBlur(aadhaar_clean, (15, 15), 0)
    passport_blurry = cv2.GaussianBlur(passport_clean, (15, 15), 0)

    # 3. Test Aadhaar OCR
    print("\nRunning Aadhaar OCR...")
    aadhaar_clean_res = extract_aadhaar_fields(aadhaar_clean)
    aadhaar_blurry_res = extract_aadhaar_fields(aadhaar_blurry)

    # 4. Test Passport VIZ OCR
    print("Running Passport VIZ OCR...")
    passport_clean_res = extract_viz_fields(passport_clean)
    passport_blurry_res = extract_viz_fields(passport_blurry)

    print("\n==================================================")
    print("OCR CONFIDENCE DISCRIMINATION TEST RESULTS:")
    print("==================================================")
    print(f"Aadhaar Sharp OCR Confidence:    {aadhaar_clean_res['confidence']}")
    print(f"Aadhaar Blurry OCR Confidence:   {aadhaar_blurry_res['confidence']}")
    print(
        f"Aadhaar Gap:                     {round(aadhaar_clean_res['confidence'] - aadhaar_blurry_res['confidence'], 4)}"
    )
    print("--------------------------------------------------")
    print(f"Passport Sharp OCR Confidence:   {passport_clean_res['confidence']}")
    print(f"Passport Blurry OCR Confidence:  {passport_blurry_res['confidence']}")
    print(
        f"Passport Gap:                    {round(passport_clean_res['confidence'] - passport_blurry_res['confidence'], 4)}"
    )
    print("==================================================\n")


if __name__ == "__main__":
    main()
