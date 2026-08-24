"""
Aadhaar Module
--------------
ocr.py          - Extract printed fields via EasyOCR
qr.py           - Decode Secure QR, parse binary payload
verhoeff.py     - Verhoeff checksum validation (dihedral group D5)
signature.py    - UIDAI RSA-2048 QR signature verification
consistency.py  - QR fields vs OCR printed fields cross-check
"""
from .ocr import extract_aadhaar_fields
from .qr import decode_aadhaar_qr
from .verhoeff import verhoeff_validate
from .signature import verify_uidai_signature
from .consistency import check_qr_ocr_consistency
