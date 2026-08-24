import os
import sys
import io
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient

sys.path.insert(0, r"C:\Users\ASUS\Downloads\SIH-PGDAV-2026")
from api.orchestrator import app

client = TestClient(app)


def create_synthetic_image(text_lines, width=800, height=500, font_size=24, mrz_y_start=None):
    """Create a white image with specified text lines drawn on it."""
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    
    # Try to load a default font
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
        
    for i, line in enumerate(text_lines):
        if mrz_y_start is not None and i >= len(text_lines) - 2:
            # Draw MRZ lines at the bottom
            y = mrz_y_start + (i - (len(text_lines) - 2)) * 35
        else:
            y = 20 + i * 35
        draw.text((20, y), line, fill="black", font=font)
        
    # Convert to BGR numpy array
    open_cv_image = np.array(img)
    # Convert RGB to BGR
    open_cv_image = open_cv_image[:, :, ::-1].copy()
    return open_cv_image


def to_jpeg_bytes(cv_img):
    is_success, buffer = cv2.imencode(".jpg", cv_img)
    return io.BytesIO(buffer)


import cv2

print("Creating synthetic test images...")

# 1. Genuine Aadhaar (Valid Verhoeff UID)
gen_aadhaar_text = [
    "Government of India",
    "Unique Identification Authority of India",
    "Name: Shashwat Khandelwal",
    "DOB: 12/05/1990",
    "Gender: MALE",
    "UID: 2341 2341 2346",
    "Address: 7/168 B Swaroop nagar Kanpur"
]
img_gen_aadhaar = create_synthetic_image(gen_aadhaar_text)

# 2. Tampered Aadhaar (Invalid Verhoeff UID)
tam_aadhaar_text = [
    "Government of India",
    "Unique Identification Authority of India",
    "Name: Shashwat Khandelwal",
    "DOB: 12/05/1990",
    "Gender: MALE",
    "UID: 2341 2341 2341",  # Invalid check digit (1 instead of 6)
    "Address: 7/168 B Swaroop nagar Kanpur"
]
img_tam_aadhaar = create_synthetic_image(tam_aadhaar_text)

# 3. Genuine Passport (Valid MRZ check digits)
gen_pass_text = [
    "PASSPORT",
    "Type: P, Code: IND",
    "Passport No: L8406789",
    "Surname: KHANDELWAL",
    "Given Names: SHASHWAT",
    "Nationality: IND",
    "DOB: 12/05/1990",
    "Sex: M",
    "Date of Expiry: 01/01/2035",
    "Place of Birth: KANPUR",
    # MRZ lines at the bottom (bottom 20% of 500px is >=400px)
    "P<IND<KHANDELWAL<<SHASHWAT<<<<<<<<<<<<<<<<<<<<",
    "L8406789<1IND9005126M3501019<<<<<<<<<<<<<<02"
]
img_gen_pass = create_synthetic_image(gen_pass_text, mrz_y_start=410)

# 4. Tampered Passport (Invalid MRZ check digit)
tam_pass_text = [
    "PASSPORT",
    "Type: P, Code: IND",
    "Passport No: L8406789",
    "Surname: KHANDELWAL",
    "Given Names: SHASHWAT",
    "Nationality: IND",
    "DOB: 12/05/1990",
    "Sex: M",
    "Date of Expiry: 01/01/2035",
    "Place of Birth: KANPUR",
    # MRZ lines at the bottom (L8406789 check digit is 0 instead of 1)
    "P<IND<KHANDELWAL<<SHASHWAT<<<<<<<<<<<<<<<<<<<<",
    "L8406789<0IND9005126M3501019<<<<<<<<<<<<<<02"
]
img_tam_pass = create_synthetic_image(tam_pass_text, mrz_y_start=410)

# 5. Genuine Visa (Valid Rules and bound to passport L8406789)
gen_visa_text = [
    "REPUBLIC OF INDIA VISA",
    "Visa No: TV1234567",
    "Type: Tourist",
    "Issued Date: 12/05/2026",
    "Valid Until: 12/11/2026",
    "Duration: 90 days",
    "Entries: Multiple",
    "Passport No: L8406789",
    "Name: Shashwat Khandelwal"
]
img_gen_visa = create_synthetic_image(gen_visa_text)

# 6. Tampered Visa (Transit Visa with stay duration of 90 days - exceeds limit of 3 days)
tam_visa_text = [
    "REPUBLIC OF INDIA VISA",
    "Visa No: TV1234567",
    "Type: Transit",  # Transit cap is 3 days
    "Issued Date: 12/05/2026",
    "Valid Until: 12/11/2026",
    "Duration: 90 days",  # Violates Transit type stay duration
    "Entries: Single",
    "Passport No: L8406789",
    "Name: Shashwat Khandelwal"
]
img_tam_visa = create_synthetic_image(tam_visa_text)


def run_screening_test(name, cv_img, url, extra_params=None):
    print(f"\n========================================\nTEST: {name}\n========================================")
    bio_bytes = to_jpeg_bytes(cv_img)
    files = {"document": ("doc.jpg", bio_bytes, "image/jpeg")}
    
    response = client.post(url, files=files, data=extra_params)
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error {response.status_code}: {response.text}")


# Run tests
run_screening_test("Genuine Aadhaar", img_gen_aadhaar, "/screen/aadhaar")
run_screening_test("Tampered Aadhaar", img_tam_aadhaar, "/screen/aadhaar")

run_screening_test("Genuine Passport", img_gen_pass, "/screen/passport")
run_screening_test("Tampered Passport", img_tam_pass, "/screen/passport")

run_screening_test("Genuine Visa", img_gen_visa, "/screen/visa", {"passport_mrz_number": "L8406789"})
run_screening_test("Tampered Visa", img_tam_visa, "/screen/visa", {"passport_mrz_number": "L8406789"})
