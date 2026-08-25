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
from typing import Optional

import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode


def decode_aadhaar_qr(image: np.ndarray) -> dict:
    """
    Detect and decode the Aadhaar Secure QR from a card image.

    Returns:
        dict with keys: format ('xml'|'binary'), fields (dict), raw_payload (bytes),
        signature (bytes), error (str|None)
    """
    pil_image = Image.fromarray(image)
    decoded_objects = pyzbar_decode(pil_image)

    qr_data: Optional[bytes] = None
    region = None
    for obj in decoded_objects:
        if obj.type == "QRCODE":
            qr_data = obj.data
            r = obj.rect
            region = (r.left, r.top, r.left + r.width, r.top + r.height)
            break

    if qr_data is None:
        return {"error": "No QR code detected", "fields": {}, "region": None}

    # Detect format
    res = None
    try:
        text = qr_data.decode("utf-8")
        if text.strip().startswith("<"):
            res = _parse_xml_format(text, qr_data)
    except UnicodeDecodeError:
        pass  # Binary format

    if res is None:
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
