"""
Aadhaar Secure QR Decoder.

Handles both:
  - New binary format (post-2017): packed byte array with length-prefixed fields
  - Old XML format (pre-2017): plain XML string

The QR payload structure (new format):
  [email_mobile_flag: 1B][ref_id: 8B][name: LP][dob: 10B][gender: 1B]
  [care_of: LP][district: LP][landmark: LP][house: LP][location: LP]
  [pincode: 6B][postoffice: LP][state: LP][street: LP][subdistrict: LP]
  [vtc: LP][mobile_last4: 4B if flag set][photo: LP if flag set]
  [signature: 256B]  ← last 256 bytes always

LP = length-prefixed UTF-8 string (2-byte big-endian length header)
"""

import struct
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode


def _detect_and_decode_qr(
    image: np.ndarray,
) -> Tuple[Optional[bytes], Optional[Tuple[int, int, int, int]]]:
    """
    Multi-pass QR code detector:
    Tries raw RGB, grayscale, CLAHE contrast enhancement, Otsu binarization,
    adaptive thresholding, and OpenCV QRCodeDetector.
    """
    if image is None or image.size == 0:
        return None, None

    def try_pyzbar(img_arr):
        try:
            pil_img = Image.fromarray(img_arr)
            objs = pyzbar_decode(pil_img)
            for obj in objs:
                if obj.type == "QRCODE" and obj.data:
                    r = obj.rect
                    reg = (r.left, r.top, r.left + r.width, r.top + r.height)
                    return obj.data, reg
        except Exception:
            pass
        return None, None

    # Pass 1: Raw image
    data, reg = try_pyzbar(image)
    if data:
        return data, reg

    # Convert to grayscale if 3-channel
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Pass 2: Grayscale
    data, reg = try_pyzbar(gray)
    if data:
        return data, reg

    # Pass 3: CLAHE contrast enhancement
    try:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        data, reg = try_pyzbar(enhanced)
        if data:
            return data, reg
    except Exception:
        pass

    # Pass 4: Otsu thresholding
    try:
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        data, reg = try_pyzbar(otsu)
        if data:
            return data, reg
    except Exception:
        pass

    # Pass 5: Adaptive thresholding
    try:
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 11
        )
        data, reg = try_pyzbar(adaptive)
        if data:
            return data, reg
    except Exception:
        pass

    # Pass 6: cv2.QRCodeDetector fallback
    try:
        detector = cv2.QRCodeDetector()
        val, points, _ = detector.detectAndDecode(gray)
        if val:
            reg = None
            if points is not None and len(points) > 0:
                pts = points[0]
                x_min, y_min = int(np.min(pts[:, 0])), int(np.min(pts[:, 1]))
                x_max, y_max = int(np.max(pts[:, 0])), int(np.max(pts[:, 1]))
                reg = (x_min, y_min, x_max, y_max)
            return val.encode("utf-8", errors="replace"), reg
    except Exception:
        pass

    return None, None


def decode_aadhaar_qr(image: np.ndarray) -> dict:
    """
    Detect and decode the Aadhaar Secure QR from a card image.

    Returns:
        dict with keys: format ('xml'|'binary'), fields (dict), raw_payload (bytes),
        signature (bytes), error (str|None)
    """
    print("[DEBUG QR Decoder] Starting QR detection across multi-pass pipeline...")
    qr_data, region = _detect_and_decode_qr(image)

    if qr_data is None:
        print("[DEBUG QR Decoder] RESULT: No QR code detected (Decoder returned None / empty result).")
        return {"error": "No QR code detected", "fields": {}, "region": None}

    payload_len = len(qr_data)
    print(f"[DEBUG QR Decoder] RESULT: QR successfully detected & decoded! Raw payload length: {payload_len} bytes.")

    # Detect format
    res = None
    try:
        text = qr_data.decode("utf-8")
        if text.strip().startswith("<"):
            print("[DEBUG QR Decoder] Detected format: XML format (pre-2017)")
            res = _parse_xml_format(text, qr_data)
    except UnicodeDecodeError:
        pass  # Binary format

    if res is None:
        print("[DEBUG QR Decoder] Detected format: Binary format (Secure QR post-2017)")
        res = _parse_binary_format(qr_data)

    res["region"] = region
    return res


# ── XML format (pre-2017) ──────────────────────────────────────────────────────


def _parse_xml_format(text: str, raw: bytes) -> dict:
    """Parse old-format Aadhaar QR (XML string + appended signature)."""
    try:
        root = ET.fromstring(text)
        fields = {
            "uid_last4": root.get("uid", ""),
            "name": root.get("name", ""),
            "dob": root.get("dob", ""),
            "gender": root.get("gender", ""),
            "co": root.get("co", ""),
            "house": root.get("house", ""),
            "street": root.get("street", ""),
            "lm": root.get("lm", ""),
            "loc": root.get("loc", ""),
            "vtc": root.get("vtc", ""),
            "subdist": root.get("subdist", ""),
            "dist": root.get("dist", ""),
            "state": root.get("state", ""),
            "pc": root.get("pc", ""),
            "po": root.get("po", ""),
        }
        # Signature is appended after the XML, last 256 bytes
        signature = raw[-256:]
        payload = raw[:-256]
        return {
            "format": "xml",
            "fields": fields,
            "raw_payload": payload,
            "signature": signature,
            "error": None,
        }
    except ET.ParseError as e:
        return {"format": "xml", "fields": {}, "error": str(e)}


# ── Binary format (post-2017) ──────────────────────────────────────────────────


def _parse_binary_format(data: bytes) -> dict:
    """Parse new-format Aadhaar QR (packed binary payload)."""
    try:
        signature = data[-256:]
        payload = data[:-256]

        offset = 0
        email_mobile_flag = data[offset]
        offset += 1
        ref_id = data[offset : offset + 8].decode("ascii", errors="replace")
        offset += 8

        name, offset = _read_lp_string(data, offset)
        dob = data[offset : offset + 10].decode("ascii", errors="replace")
        offset += 10
        gender_byte = data[offset]
        offset += 1
        gender = {1: "M", 2: "F", 3: "T"}.get(gender_byte, "U")

        care_of, offset = _read_lp_string(data, offset)
        district, offset = _read_lp_string(data, offset)
        landmark, offset = _read_lp_string(data, offset)
        house, offset = _read_lp_string(data, offset)
        location, offset = _read_lp_string(data, offset)
        pincode = data[offset : offset + 6].decode("ascii", errors="replace")
        offset += 6
        postoffice, offset = _read_lp_string(data, offset)
        state, offset = _read_lp_string(data, offset)
        street, offset = _read_lp_string(data, offset)
        subdistrict, offset = _read_lp_string(data, offset)
        vtc, offset = _read_lp_string(data, offset)

        mobile_last4 = None
        if email_mobile_flag in (1, 3):
            mobile_last4 = data[offset : offset + 4].decode("ascii", errors="replace")
            offset += 4

        fields = {
            "ref_id": ref_id,
            "name": name,
            "dob": dob,
            "gender": gender,
            "care_of": care_of,
            "district": district,
            "landmark": landmark,
            "house": house,
            "location": location,
            "pincode": pincode,
            "postoffice": postoffice,
            "state": state,
            "street": street,
            "subdistrict": subdistrict,
            "vtc": vtc,
            "mobile_last4": mobile_last4,
        }

        return {
            "format": "binary",
            "fields": fields,
            "raw_payload": payload,
            "signature": signature,
            "error": None,
        }

    except Exception as e:
        return {"format": "binary", "fields": {}, "error": f"Parse error: {e}"}


def _read_lp_string(data: bytes, offset: int) -> tuple[str, int]:
    """Read a 2-byte big-endian length-prefixed UTF-8 string."""
    length = struct.unpack_from(">H", data, offset)[0]
    offset += 2
    text = data[offset : offset + length].decode("utf-8", errors="replace")
    return text, offset + length
