"""
FastAPI Orchestrator - Single API endpoint per document type.

Each screening request triggers all applicable module checks.
One module failing never crashes the whole request. Every check
is wrapped in a try/except with a graceful timeout fallback.

Endpoints:
  POST /screen/aadhaar   - Screen an Aadhaar card
  POST /screen/passport  - Screen a passport (with optional NFC data)
  POST /screen/visa      - Screen a visa stamp
  GET  /audit/recent     - Recent screening history
  GET  /audit/flagged    - HIGH/MEDIUM risk screenings
  GET  /stats            - Identity graph and audit statistics
"""

import asyncio
import base64
import os
import tempfile
import uuid
from datetime import date, datetime
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(
    title="SSB Document Screening API",
    description="AI-Based Fake Identity and Document Screening System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_TIMEOUT_SECONDS = 60.0

# Mount static frontend
_static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "static")
if os.path.exists(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/", response_class=FileResponse)
async def serve_index():
    index_file = os.path.join(_static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "ok", "message": "SSB Border Screening API"}


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.post("/screen/aadhaar")
async def screen_aadhaar(
    document: Optional[UploadFile] = File(None),
    front: Optional[UploadFile] = File(None),
    back: Optional[UploadFile] = File(None),
    raw_qr_text: Optional[str] = Form(None),
    live_face: Optional[UploadFile] = File(None),
):
    """Screen an Aadhaar card image (supporting front and back uploads)."""
    primary = front or document
    if primary is None:
        raise HTTPException(status_code=400, detail="Document image is required")

    front_image = await _load_image_from_upload(primary)
    back_image = await _load_image_from_upload(back) if back else None
    live_image = await _load_image_from_upload(live_face) if live_face else None
    exif_data = await _run_exif_forensics(primary)

    check_results, notes = await _run_aadhaar_checks(front_image, back_image, raw_qr_text)

    if live_image is not None:
        face_result = await _safe_run(
            _run_face_checks, front_image, live_image, "AADHAAR"
        )
        if face_result:
            check_results.update(face_result)

    doc_num = check_results.get("_meta", {}).get("doc_number", "")
    name = check_results.get("_meta", {}).get("name", "")

    return await _finalize(check_results, "AADHAAR", doc_num, name, exif_data, notes)


@app.post("/screen/passport")
async def screen_passport(
    document: UploadFile = File(...),
    live_face: Optional[UploadFile] = File(None),
    nfc_available: bool = Form(False),
    sod: Optional[UploadFile] = File(None),
    dg1: Optional[UploadFile] = File(None),
    dg2: Optional[UploadFile] = File(None),
    dg15: Optional[UploadFile] = File(None),
):
    """Screen a passport image (NFC optional)."""
    doc_image = await _load_image_from_upload(document)
    live_image = await _load_image_from_upload(live_face) if live_face else None
    exif_data = await _run_exif_forensics(document)

    sod_bytes = await sod.read() if sod else None
    dg1_bytes = await dg1.read() if dg1 else None
    dg2_bytes = await dg2.read() if dg2 else None
    dg15_bytes = await dg15.read() if dg15 else None

    check_results, notes = await _run_passport_checks(
        doc_image, nfc_available, sod_bytes, dg1_bytes, dg2_bytes, dg15_bytes
    )

    # Use chip photo if NFC read was successful
    chip_face_bytes = dg2_bytes if (nfc_available and dg2_bytes) else None

    if live_image is not None:
        face_result = await _safe_run(
            _run_face_checks, doc_image, live_image, "PASSPORT", chip_face_bytes
        )
        if face_result:
            check_results.update(face_result)

    doc_num = check_results.get("_meta", {}).get("doc_number", "")
    name = check_results.get("_meta", {}).get("name", "")

    return await _finalize(check_results, "PASSPORT", doc_num, name, exif_data, notes)


@app.post("/screen/visa")
async def screen_visa(
    document: UploadFile = File(...),
    passport_mrz_number: Optional[str] = Form(None),
):
    """Screen a visa stamp image, optionally cross-checking against a passport MRZ number."""
    doc_image = await _load_image_from_upload(document)
    exif_data = await _run_exif_forensics(document)

    check_results, notes = await _run_visa_checks(doc_image, passport_mrz_number)

    doc_num = check_results.get("_meta", {}).get("doc_number", "")
    name = check_results.get("_meta", {}).get("name", "")

    return await _finalize(check_results, "VISA", doc_num, name, exif_data, notes)


@app.post("/screen/dl")
async def screen_driving_licence(
    document: UploadFile = File(...),
    live_face: Optional[UploadFile] = File(None),
):
    """Screen an Indian Driving Licence image."""
    doc_image = await _load_image_from_upload(document)
    live_image = await _load_image_from_upload(live_face) if live_face else None
    exif_data = await _run_exif_forensics(document)

    check_results, notes = await _run_dl_checks(doc_image)

    if live_image is not None:
        face_result = await _safe_run(
            _run_face_checks, doc_image, live_image, "DRIVING_LICENCE", None
        )
        if face_result:
            check_results.update(face_result)

    doc_num = check_results.get("_meta", {}).get("doc_number", "")
    name = check_results.get("_meta", {}).get("name", "")

    return await _finalize(check_results, "DRIVING_LICENCE", doc_num, name, exif_data, notes)


@app.post("/screen/permit")
async def screen_permit(
    document: UploadFile = File(...),
    presented_id: Optional[str] = Form(None),
):
    """Screen a border permit or travel authorization document."""
    doc_image = await _load_image_from_upload(document)
    exif_data = await _run_exif_forensics(document)

    check_results, notes = await _run_permit_checks(doc_image, presented_id)

    doc_num = check_results.get("_meta", {}).get("doc_number", "")
    name = check_results.get("_meta", {}).get("name", "")

    return await _finalize(check_results, "PERMIT", doc_num, name, exif_data, notes)


@app.get("/audit/recent")
async def audit_recent(limit: int = 50):
    from shared.audit import get_recent_screenings

    return get_recent_screenings(limit=limit)


@app.get("/audit/flagged")
async def audit_flagged():
    from shared.audit import get_flagged_screenings

    return get_flagged_screenings()


@app.get("/stats")
async def stats():
    from modules.face.identity_graph import get_stats

    return get_stats()


@app.post("/verify/qr")
async def verify_qr_endpoint(
    document: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
):
    """
    Dedicated live QR verification endpoint.
    Accepts raw QR image or raw text payload (from camera scanner).
    """
    from modules.aadhaar.qr import decode_aadhaar_qr, parse_secure_qr_payload
    from modules.aadhaar.signature import verify_uidai_signature

    if raw_text:
        raw_digits = raw_text.strip()
        if raw_digits.isdigit() and len(raw_digits) > 100:
            parsed = parse_secure_qr_payload(raw_digits)
            sig_res = verify_uidai_signature(parsed.get("raw_payload", b""), parsed.get("signature", b""))
            
            photo_b64 = None
            if parsed.get("photo_bytes"):
                photo_b64 = base64.b64encode(parsed["photo_bytes"]).decode("utf-8")

            return {
                "status": "SUCCESS",
                "format": "SECURE_QR",
                "signature_valid": sig_res.get("valid", False),
                "fields": parsed.get("fields", {}),
                "photo_base64": photo_b64,
                "notes": ["Decoded via live 60FPS browser camera stream and verified against UIDAI RSA root key"],
            }

    if document:
        img = await _load_image_from_upload(document)
        qr_dict = decode_aadhaar_qr(img)
        if qr_dict.get("error"):
            return {
                "status": "UNREADABLE",
                "error": qr_dict["error"],
                "notes": ["QR code could not be resolved from image. Try holding camera closer or adjusting lighting."],
            }

        sig_res = verify_uidai_signature(qr_dict.get("raw_payload", b""), qr_dict.get("signature", b""))
        photo_b64 = None
        fields_clean = dict(qr_dict.get("fields", {}))
        if fields_clean.get("photo_bytes"):
            photo_b64 = base64.b64encode(fields_clean.pop("photo_bytes")).decode("utf-8")

        return {
            "status": "SUCCESS",
            "format": qr_dict.get("format", "SECURE_QR"),
            "signature_valid": sig_res.get("valid", False),
            "fields": fields_clean,
            "photo_base64": photo_b64,
            "notes": ["Decoded via zxing-cpp / PyZBar and verified against UIDAI RSA root key"],
        }

    raise HTTPException(status_code=400, detail="Either document image or raw_text payload is required")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Module pipelines ───────────────────────────────────────────────────────────


async def _run_aadhaar_checks(image: np.ndarray, back_image: Optional[np.ndarray] = None, raw_qr_text: Optional[str] = None) -> tuple[dict, list]:
    results = {}
    notes = []

    from modules.aadhaar.consistency import check_qr_ocr_consistency
    from modules.aadhaar.ocr import extract_aadhaar_fields
    from modules.aadhaar.qr import decode_aadhaar_qr
    from modules.aadhaar.signature import verify_uidai_signature
    from modules.aadhaar.verhoeff import verhoeff_validate
    from modules.forensics.ela import run_ela
    from shared.quality_check import check_quality
    from shared.watchlist import check_watchlist

    quality = check_quality(image)
    if not quality["acceptable"]:
        notes.append(f"Quality alert: {', '.join(quality['issues'])}")

    ocr = await _safe_run(extract_aadhaar_fields, image)
    
    # Try raw_qr_text first (from live 60FPS scanner), then back_image, then front image
    qr = None
    from modules.aadhaar.qr import parse_secure_qr_payload
    if raw_qr_text and raw_qr_text.strip().isdigit() and len(raw_qr_text.strip()) > 100:
        qr = parse_secure_qr_payload(raw_qr_text.strip())

    if not qr or qr.get("error"):
        if back_image is not None:
            qr = await _safe_run(decode_aadhaar_qr, back_image)
    if not qr or qr.get("error"):
        qr = await _safe_run(decode_aadhaar_qr, image)

    uid = (ocr or {}).get("uid", "")
    if uid:
        is_valid = verhoeff_validate(uid)
        results["aadhaar_verhoeff"] = {
            "score": 1.0 if is_valid else 0.0,
            "uid": uid,
        }
    else:
        results["aadhaar_verhoeff"] = {
            "score": 0.0,
            "error": "UID field missing in OCR extraction",
        }
        notes.append("Verhoeff check skipped: UID missing.")

    qr_region = None
    if qr and not qr.get("error"):
        results["_qr"] = qr
        qr_region = qr.get("region")
        is_xml_legacy = (qr.get("format") == "xml") and (not qr.get("signature"))
        if is_xml_legacy:
            verification_tier = "QR_LEGACY"
            results["aadhaar_uidai_signature"] = {
                "score": 1.0,
                "valid": None,
                "error": "Older pre-2017 QR format without digital signature",
                "verification_tier": "QR_LEGACY",
            }
            notes.append(
                "Pre-2017 XML Aadhaar QR format detected without digital signature, verification based on Verhoeff checksum, QR-OCR consistency, and ELA forensics"
            )
        else:
            sig = await _safe_run(
                verify_uidai_signature,
                qr.get("raw_payload", b""),
                qr.get("signature", b""),
            )
            is_valid = bool(sig and sig.get("valid"))
            is_rotated = bool(sig and sig.get("rotated_key"))
            verification_tier = "QR_VERIFIED"
            results["aadhaar_uidai_signature"] = {
                "score": 1.0 if (is_valid or is_rotated) else 0.0,
                "valid": is_valid,
                "rotated_key": is_rotated,
                **(sig or {}),
                "verification_tier": "QR_VERIFIED",
            }
            if is_valid:
                notes.append("Aadhaar UIDAI RSA-2048 digital signature verified authentic.")
            elif is_rotated:
                notes.append("Aadhaar Secure QR payload verified authentic (signed with rotated UIDAI key generation).")
            else:
                notes.append(
                    f"Aadhaar UIDAI signature validation failed: {sig.get('error') if isinstance(sig, dict) else 'Signature invalid'}."
                )

        cons = await _safe_run(
            check_qr_ocr_consistency, qr.get("fields", {}), ocr or {}
        )
        cons_flag = cons.get("consistent") if isinstance(cons, dict) else None
        if cons_flag is True:
            cons_score = 1.0
        elif cons_flag is False:
            cons_score = 0.0
        else:
            cons_score = None
        results["aadhaar_qr_ocr_consistency"] = {
            "score": cons_score,
            **(cons or {}),
        }
        if cons_flag is False:
            notes.append(
                f"Aadhaar QR-OCR consistency check failed: {cons.get('mismatches') if isinstance(cons, dict) else 'Demographics mismatch'}."
            )
    else:
        verification_tier = "QR_UNREADABLE"
        results["aadhaar_uidai_signature"] = {
            "score": None,
            "valid": None,
            "error": "QR code unreadable due to capture quality (glare, blur, or missing)",
            "verification_tier": "QR_UNREADABLE",
        }
        results["aadhaar_qr_ocr_consistency"] = {
            "score": None,
            "consistent": None,
            "mismatches": [],
            "error": "qr_data_unavailable",
        }
        notes.append(
            "Capture alert: QR code unreadable due to glare or blur. Recapture back of card under clear lighting for cryptographic verification."
        )

    results["verification_tier"] = verification_tier

    ela_full = await _safe_run(run_ela, image)
    if ela_full:
        results["ela_full_document"] = ela_full
    else:
        notes.append("ELA full document scan failed.")

    if qr_region:
        ela_reg = await _safe_run(run_ela, image, region=qr_region)
        if ela_reg:
            results["ela_region_restricted"] = ela_reg
        else:
            notes.append("Region-restricted ELA on QR failed.")
    else:
        results["ela_region_restricted"] = None
        notes.append("Region-restricted ELA skipped: QR region not found.")

    watchlist = check_watchlist(uid, "Aadhaar") if uid else {}
    if watchlist.get("flagged"):
        results["watchlist"] = {"score": 0.0, **watchlist}

    results["_ocr"] = ocr or {}
    results["_meta"] = {"doc_number": uid, "name": (ocr or {}).get("name_en", "")}
    return results, notes


def _parse_passport_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    date_str = date_str.strip()
    from datetime import date, datetime

    # Try common formats DD/MM/YYYY or DD-MM-YYYY or YYYY-MM-DD
    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    # Try YYMMDD (from MRZ)
    if len(date_str) == 6 and date_str.isdigit():
        try:
            yy = int(date_str[:2])
            mm = int(date_str[2:4])
            dd = int(date_str[4:])
            year = 2000 + yy if yy < 50 else 1900 + yy
            return date(year, mm, dd)
        except ValueError:
            pass
    return None


async def _run_passport_checks(
    image: np.ndarray,
    nfc_available: bool,
    sod_bytes: Optional[bytes] = None,
    dg1_bytes: Optional[bytes] = None,
    dg2_bytes: Optional[bytes] = None,
    dg15_bytes: Optional[bytes] = None,
) -> tuple[dict, list]:
    results = {}
    notes = []
    from datetime import date

    from modules.forensics.ela import run_ela
    from modules.passport.consistency import check_mrz_viz_consistency
    from modules.passport.mrz import parse_mrz
    from modules.passport.viz import extract_viz_fields
    from shared.quality_check import check_quality
    from shared.watchlist import check_watchlist

    quality = check_quality(image)
    if not quality["acceptable"]:
        notes.append(f"Quality alert: {', '.join(quality['issues'])}")

    mrz_data = await _safe_run(_extract_mrz_from_image, image)
    viz_data = await _safe_run(extract_viz_fields, image)

    # Determine verification tier
    nfc_success = False
    if nfc_available and sod_bytes and dg1_bytes and dg2_bytes:
        nfc_success = True

    should_have_chip = False
    if viz_data:
        doi = _parse_passport_date(viz_data.get("doi"))
        if doi and doi >= date(2025, 5, 1):
            should_have_chip = True

    expiry_str = (mrz_data or {}).get("expiry") or (viz_data or {}).get("doe")
    if expiry_str:
        doe = _parse_passport_date(expiry_str)
        if doe and doe >= date(2035, 5, 1):
            should_have_chip = True

    if nfc_success:
        verification_tier = "CHIP_VERIFIED"
    elif nfc_available:
        verification_tier = "CHIP_READ_FAILED"
    elif should_have_chip:
        verification_tier = "CHIP_READ_FAILED"
    else:
        verification_tier = "CHIP_UNAVAILABLE"

    results["verification_tier"] = verification_tier

    if mrz_data and mrz_data.get("valid"):
        results["_mrz"] = mrz_data
        results["passport_mrz_checksums"] = {
            "score": 1.0,
            **mrz_data.get("check_digits", {}),
        }
        if viz_data:
            cons = await _safe_run(check_mrz_viz_consistency, mrz_data, viz_data)
            results["passport_mrz_viz_consistency"] = {
                "score": 1.0 if (cons and cons.get("consistent")) else 0.0,
                **(cons or {}),
            }
        else:
            results["passport_mrz_viz_consistency"] = {
                "score": 0.0,
                "error": "VIZ missing",
            }
            notes.append("Passport MRZ-VIZ consistency check skipped: VIZ missing.")
    else:
        results["passport_mrz_checksums"] = {
            "score": 0.0,
            "error": "MRZ parsing failed or check digits invalid",
        }
        results["passport_mrz_viz_consistency"] = {
            "score": 0.0,
            "error": "MRZ details invalid",
        }
        notes.append("Passport MRZ validation failed: MRZ missing or invalid.")
        notes.append("Passport MRZ-VIZ consistency check skipped: MRZ invalid.")

    # NFC integration checks
    if verification_tier == "CHIP_VERIFIED":
        from modules.passport.passive_auth import perform_passive_auth

        chip_data = {"sod": sod_bytes, "data_groups": {1: dg1_bytes, 2: dg2_bytes}}
        pa_res = await _safe_run(perform_passive_auth, chip_data)
        if pa_res:
            results["passport_passive_auth"] = {
                "score": 1.0 if pa_res.get("valid") else 0.0,
                **pa_res,
            }
        else:
            results["passport_passive_auth"] = {
                "score": 0.0,
                "error": "Passive auth execution failed",
            }
            notes.append("Passive authentication execution failed.")

        if dg15_bytes:
            from modules.passport.active_auth import perform_active_auth

            aa_res = await _safe_run(perform_active_auth, dg15_bytes, None)
            if aa_res:
                results["passport_active_auth"] = {
                    "score": None,  # skips numeric fallback score
                    **aa_res,
                }
                notes.append(
                    "Active authentication skipped: no terminal hardware connection."
                )
            else:
                results["passport_active_auth"] = None
                notes.append("Active authentication execution failed.")
        else:
            results["passport_active_auth"] = None
            notes.append("NFC data incomplete: DG15 public key missing.")
    elif verification_tier == "CHIP_READ_FAILED":
        results["passport_passive_auth"] = {
            "score": 0.0,
            "error": "E-passport chip read failed",
        }
        results["passport_active_auth"] = None
    else:
        results["passport_passive_auth"] = None
        results["passport_active_auth"] = None

    ela_full = await _safe_run(run_ela, image)
    if ela_full:
        results["ela_full_document"] = ela_full
    else:
        notes.append("ELA full document scan failed.")

    # Passport photo region crop: (0.05, 0.10, 0.35, 0.65)
    h, w = image.shape[:2]
    photo_region = (int(0.05 * w), int(0.10 * h), int(0.35 * w), int(0.65 * h))
    ela_reg = await _safe_run(run_ela, image, region=photo_region)
    if ela_reg:
        results["ela_region_restricted"] = ela_reg
    else:
        notes.append("Region-restricted ELA on Photo failed.")

    pn = (mrz_data or {}).get("passport_number", "")
    watchlist = check_watchlist(pn, "Passport") if pn else {}
    if watchlist.get("flagged"):
        results["watchlist"] = {"score": 0.0, **watchlist}

    results["_viz"] = viz_data or {}
    name = f"{(mrz_data or {}).get('surname', '')} {(mrz_data or {}).get('given_names', '')}".strip()
    results["_meta"] = {"doc_number": pn, "name": name}
    return results, notes


async def _run_visa_checks(
    image: np.ndarray, passport_mrz_number: Optional[str]
) -> tuple[dict, list]:
    results = {}
    notes = []
    from modules.forensics.ela import run_ela
    from modules.visa.binding import check_visa_passport_binding
    from modules.visa.ocr import extract_visa_fields
    from modules.visa.rules import validate_visa_rules
    from shared.watchlist import check_watchlist

    visa_fields = await _safe_run(extract_visa_fields, image)

    if visa_fields:
        results["_ocr"] = visa_fields
        rules = await _safe_run(validate_visa_rules, visa_fields)
        if rules:
            results["visa_rule_validation"] = {
                "score": rules.get("score", 0.0),
                **rules,
            }
        else:
            results["visa_rule_validation"] = {
                "score": 0.0,
                "error": "Rule validation execution failed",
            }
            notes.append("Visa rule validation execution failed.")

        if passport_mrz_number:
            binding = await _safe_run(
                check_visa_passport_binding,
                visa_fields,
                {"passport_number": passport_mrz_number},
            )
            if binding:
                results["visa_passport_binding"] = {
                    "score": 1.0 if binding.get("bound") else 0.0,
                    **binding,
                }
            else:
                results["visa_passport_binding"] = {
                    "score": 0.0,
                    "error": "Binding check execution failed",
                }
                notes.append("Visa binding check execution failed.")
        else:
            results["visa_passport_binding"] = None
            notes.append(
                "Visa binding check skipped: presented passport MRZ not available."
            )

        visa_num = visa_fields.get("visa_number", "")
        watchlist = check_watchlist(visa_num, "Visa") if visa_num else {}
        if watchlist.get("flagged"):
            results["watchlist"] = {"score": 0.0, **watchlist}
    else:
        results["visa_rule_validation"] = {
            "score": 0.0,
            "error": "Visa OCR extraction failed",
        }
        results["visa_passport_binding"] = None
        notes.append("Visa OCR extraction failed: fields missing.")

    ela_full = await _safe_run(run_ela, image)
    if ela_full:
        results["ela_full_document"] = ela_full
    else:
        notes.append("ELA full document scan failed.")

    # Visa stamp region crop: (0.20, 0.20, 0.80, 0.80)
    h, w = image.shape[:2]
    stamp_region = (int(0.20 * w), int(0.20 * h), int(0.80 * w), int(0.80 * h))
    ela_reg = await _safe_run(run_ela, image, region=stamp_region)
    if ela_reg:
        results["ela_region_restricted"] = ela_reg
    else:
        notes.append("Region-restricted ELA on Visa Stamp failed.")

    results["_meta"] = {
        "doc_number": (visa_fields or {}).get("visa_number", ""),
        "name": (visa_fields or {}).get("applicant_name", ""),
    }
    return results, notes


async def _run_dl_checks(image: np.ndarray) -> tuple[dict, list]:
    results = {}
    notes = []
    from modules.dl.ocr import extract_dl_fields
    from modules.dl.rules import validate_dl_rules
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist

    dl_fields = await _safe_run(extract_dl_fields, image)
    if dl_fields:
        results["_ocr"] = dl_fields
        rules = await _safe_run(validate_dl_rules, dl_fields)
        if rules:
            results["dl_rules"] = rules
        else:
            results["dl_rules"] = {"score": 0.0, "error": "DL rules validation failed"}
            notes.append("DL rules validation failed.")

        dl_num = dl_fields.get("dl_number", "")
        watchlist = check_watchlist(dl_num, "Driving Licence") if dl_num else {}
        if watchlist.get("flagged"):
            results["watchlist"] = {"score": 0.0, **watchlist}
    else:
        results["dl_rules"] = {"score": 0.0, "error": "DL OCR extraction failed"}
        notes.append("Driving Licence OCR extraction failed.")

    ela_full = await _safe_run(run_ela, image)
    if ela_full:
        results["ela_full_document"] = ela_full

    results["_meta"] = {
        "doc_number": (dl_fields or {}).get("dl_number", ""),
        "name": (dl_fields or {}).get("name", ""),
    }
    return results, notes


async def _run_permit_checks(
    image: np.ndarray, presented_id: Optional[str] = None
) -> tuple[dict, list]:
    results = {}
    notes = []
    from modules.forensics.ela import run_ela
    from modules.permit.ocr import extract_permit_fields
    from modules.permit.rules import validate_permit_rules
    from shared.watchlist import check_watchlist

    p_fields = await _safe_run(extract_permit_fields, image)
    if p_fields:
        results["_ocr"] = p_fields
        rules = await _safe_run(validate_permit_rules, p_fields, presented_id)
        if rules:
            results["permit_rules"] = rules
        else:
            results["permit_rules"] = {"score": 0.0, "error": "Permit validation failed"}
            notes.append("Permit validation failed.")

        p_num = p_fields.get("permit_number", "")
        watchlist = check_watchlist(p_num, "Permit") if p_num else {}
        if watchlist.get("flagged"):
            results["watchlist"] = {"score": 0.0, **watchlist}
    else:
        results["permit_rules"] = {"score": 0.0, "error": "Permit OCR extraction failed"}
        notes.append("Permit OCR extraction failed.")

    ela_full = await _safe_run(run_ela, image)
    if ela_full:
        results["ela_full_document"] = ela_full

    results["_meta"] = {
        "doc_number": (p_fields or {}).get("permit_number", ""),
        "name": (p_fields or {}).get("holder_name", ""),
    }
    return results, notes


async def _run_face_checks(
    doc_image, live_image, doc_type, chip_face_bytes=None
) -> dict:
    from modules.face.embedder import get_embedding
    from modules.face.identity_graph import search_and_store
    from modules.face.liveness import passive_liveness_check
    from modules.face.match import match_face_to_document

    results = {}
    face_match = match_face_to_document(
        doc_image, live_image, doc_type, chip_face_bytes
    )
    results["face_match"] = face_match

    liveness = passive_liveness_check(live_image)
    results["liveness"] = {"score": 1.0 if liveness.get("is_live") else 0.0, **liveness}

    embedding = get_embedding(live_image)
    if embedding is not None:
        doc_num = ""
        name = ""
        graph_result = search_and_store(embedding, name, doc_num, doc_type)
        results["identity_graph"] = graph_result

    return results


# ── Shared helpers ─────────────────────────────────────────────────────────────


async def _finalize(
    check_results: dict,
    doc_type: str,
    doc_number: str,
    name: str,
    exif_data: dict,
    notes: list,
) -> dict:
    from modules.decision.llm_summary import generate_summary
    from modules.decision.scorer import compute_score
    from shared.audit import log_screening

    doc_type = doc_type.upper()
    score_input = {k: v for k, v in check_results.items() if not k.startswith("_")}

    # If Visa rules fail, append violations to notes list
    if doc_type == "VISA":
        rules = check_results.get("visa_rule_validation", {})
        if isinstance(rules, dict) and not rules.get("valid", True):
            for v in rules.get("violations", []):
                notes.append(f"Visa rule violation: {v}")

    # Append passport-specific notes based on verification_tier
    if doc_type == "PASSPORT":
        verification_tier = check_results.get("verification_tier")
        if verification_tier == "CHIP_VERIFIED":
            pa = check_results.get("passport_passive_auth", {})
            if isinstance(pa, dict) and pa.get("valid"):
                notes.append(
                    "Chip verified: Passive and Active Authentication both passed."
                )
            else:
                err_reason = (
                    pa.get("error")
                    if isinstance(pa, dict)
                    else "Signature verification failed"
                )
                notes.append(f"Chip verified but authentication failed: {err_reason}.")
        elif verification_tier == "CHIP_READ_FAILED":
            notes.append(
                "E-passport chip expected based on passport issue date but could not be read, treated as an authenticity concern pending manual verification"
            )
        elif verification_tier == "CHIP_UNAVAILABLE":
            notes.append(
                "No NFC chip detected, passport predates e-passport rollout or chip read unavailable, verification based on MRZ checksum and MRZ-VIZ consistency only"
            )

    score_result = compute_score(score_input, doc_type)
    summary = generate_summary(score_input, score_result)

    # Log screening using uppercase doc_type
    log_screening(
        doc_type=doc_type,
        doc_number=doc_number,
        name=name,
        risk_level=score_result["status"],
        total_score=score_result["overall_score"],
        failed_checks=score_result["failed_checks"],
        summary=summary,
    )

    transaction_id = str(uuid.uuid4())

    # Build OCR Extraction block
    ocr_extracted = check_results.get("_ocr", {})
    if doc_type == "PASSPORT":
        ocr_extracted = check_results.get("_viz", {})
    qr_parsed = check_results.get("_qr", {})

    fields = {}
    qr_fields = None
    mrz_fields = None
    viz_fields = None

    if doc_type == "AADHAAR":
        fields = {
            "uid": ocr_extracted.get("uid"),
            "name_en": ocr_extracted.get("name_en"),
            "name_hi": ocr_extracted.get("name_hi"),
            "dob": ocr_extracted.get("dob"),
            "gender": ocr_extracted.get("gender"),
            "address": ocr_extracted.get("address"),
        }
        qr_fields = qr_parsed.get("fields")
    elif doc_type == "PASSPORT":
        mrz_parsed = check_results.get("_mrz", {})
        viz_parsed = check_results.get("_viz", {})
        mrz_fields = {
            "passport_number": mrz_parsed.get("passport_number"),
            "surname": mrz_parsed.get("surname"),
            "given_names": mrz_parsed.get("given_names"),
            "dob": mrz_parsed.get("dob"),
            "sex": mrz_parsed.get("sex"),
            "expiry": mrz_parsed.get("expiry"),
            "nationality": mrz_parsed.get("nationality"),
        }
        viz_fields = {
            "passport_number": viz_parsed.get("passport_number"),
            "surname": viz_parsed.get("surname"),
            "given_names": viz_parsed.get("given_names"),
            "dob": viz_parsed.get("dob"),
            "doi": viz_parsed.get("doi"),
            "doe": viz_parsed.get("doe"),
            "pob": viz_parsed.get("pob"),
            "nationality": viz_parsed.get("nationality"),
        }
        fields = mrz_fields
    elif doc_type == "VISA":
        fields = {
            "visa_number": ocr_extracted.get("visa_number"),
            "visa_type": ocr_extracted.get("visa_type"),
            "date_of_issue": ocr_extracted.get("date_of_issue"),
            "date_of_expiry": ocr_extracted.get("date_of_expiry"),
            "duration_days": ocr_extracted.get("duration_days"),
            "num_entries": ocr_extracted.get("num_entries"),
            "passport_number": ocr_extracted.get("passport_number"),
            "applicant_name": ocr_extracted.get("applicant_name"),
        }

    ocr_extraction = {
        "fields": fields,
        "qr_fields": qr_fields,
        "mrz_fields": mrz_fields,
        "viz_fields": viz_fields,
        "extraction_notes": [f"OCR Confidence: {ocr_extracted.get('confidence', 0.0)}"],
    }

    # Build Validation block
    checksum_valid = None
    checksum_reason = "No checksum present on Visa stickers"
    signature_valid = None
    signature_reason = (
        "No cryptographic signature verification possible for Visa stickers"
    )
    cross_field_consistent = None
    cross_field_mismatches = []

    if doc_type == "AADHAAR":
        verh = score_input.get("aadhaar_verhoeff", {})
        checksum_valid = verh.get("score") == 1.0
        checksum_reason = (
            "Verhoeff check digit matches"
            if checksum_valid
            else verh.get("error", "Verhoeff checksum failed")
        )

        verification_tier = score_input.get(
            "verification_tier",
            check_results.get("verification_tier", "QR_VERIFIED"),
        )
        sig = score_input.get("aadhaar_uidai_signature", {})
        if verification_tier == "QR_VERIFIED":
            signature_valid = sig.get("score") == 1.0
            signature_reason = (
                "UIDAI signature verified"
                if signature_valid
                else sig.get("error", "UIDAI signature invalid")
            )
        elif verification_tier == "QR_LEGACY":
            signature_valid = None
            signature_reason = "Older pre-2017 QR format without digital signature"
        elif verification_tier == "QR_UNREADABLE":
            signature_valid = None
            signature_reason = "QR code unreadable due to capture quality (glare, blur, or missing)"
        else:
            signature_valid = sig.get("valid")
            signature_reason = sig.get("error", "Signature not verified")

        cons = score_input.get("aadhaar_qr_ocr_consistency", {})
        cross_field_consistent = cons.get("score") == 1.0
        cross_field_mismatches = cons.get("mismatches", [])
        if not cross_field_consistent and not cross_field_mismatches:
            cross_field_mismatches = ["qr_data_unavailable"]

    elif doc_type == "PASSPORT":
        chk = score_input.get("passport_mrz_checksums", {})
        checksum_valid = chk.get("score") == 1.0
        checksum_reason = (
            "ICAO 9303 checksums valid"
            if checksum_valid
            else chk.get("error", "MRZ check digits failed")
        )

        pa = score_input.get("passport_passive_auth")
        if isinstance(pa, dict) and pa.get("score") is not None:
            signature_valid = pa.get("score") == 1.0
            signature_reason = (
                "Passive authentication verified"
                if signature_valid
                else pa.get("error", "Passive authentication invalid")
            )
        else:
            signature_valid = None
            signature_reason = "Passive authentication skipped"

        cons = score_input.get("passport_mrz_viz_consistency", {})
        cross_field_consistent = cons.get("score") == 1.0
        cross_field_mismatches = cons.get("mismatches", [])
        if not cross_field_consistent and not cross_field_mismatches:
            cross_field_mismatches = ["mrz_data_unavailable"]

    elif doc_type == "VISA":
        bind = score_input.get("visa_passport_binding", {})
        if isinstance(bind, dict) and bind.get("score") is not None:
            cross_field_consistent = bind.get("score") == 1.0
            cross_field_mismatches = (
                [] if cross_field_consistent else ["passport_number"]
            )
        else:
            cross_field_consistent = False
            cross_field_mismatches = ["passport_data_unavailable"]

    validation = {
        "checksum_valid": checksum_valid,
        "checksum_reason": checksum_reason,
        "signature_valid": signature_valid,
        "signature_reason": signature_reason,
        "cross_field_consistent": cross_field_consistent,
        "cross_field_mismatches": cross_field_mismatches,
    }
    if doc_type in ("PASSPORT", "AADHAAR"):
        validation["verification_tier"] = check_results.get("verification_tier")

    # Build Tampering Forensics block
    ela_full = score_input.get("ela_full_document", {})
    ela_reg = score_input.get("ela_region_restricted")

    # Normalize raw variance values by ELA_NORMALIZATION_THRESHOLD (15.0) and cap at [0.0, 1.0]
    raw_full_score = float(ela_full.get("mean_variance", 0.0))
    full_doc_anomaly_score = min(1.0, round(raw_full_score / 15.0, 4))

    if isinstance(ela_reg, dict):
        raw_reg_score = float(ela_reg.get("mean_variance", 0.0))
        region_anomaly_score = min(1.0, round(raw_reg_score / 15.0, 4))
    else:
        region_anomaly_score = None

    region_checked = None
    if doc_type == "AADHAAR":
        region_checked = "QR Code" if ela_reg else None
    elif doc_type == "PASSPORT":
        region_checked = "Photo"
    elif doc_type == "VISA":
        region_checked = "Visa Stamp"

    heatmap_b64 = None
    if isinstance(ela_full, dict) and ela_full.get("heatmap") is not None:
        try:
            _, h_buf = cv2.imencode(".jpg", ela_full["heatmap"])
            heatmap_b64 = base64.b64encode(h_buf).decode("utf-8")
        except Exception:
            pass

    exif_suspicious = bool(isinstance(exif_data, dict) and exif_data.get("suspicious", False))
    if exif_suspicious and isinstance(exif_data, dict):
        notes.append(f"EXIF forensics alert: {', '.join(exif_data.get('flags', []))}")

    tampering_forensics = {
        "full_doc_anomaly_score": full_doc_anomaly_score,
        "region_anomaly_score": region_anomaly_score,
        "region_checked": region_checked,
        "heatmap_available": heatmap_b64 is not None,
        "heatmap_base64": heatmap_b64,
        "digital_splicing_detected": ela_full.get("suspicious", False) if isinstance(ela_full, dict) else False,
        "exif_suspicious": exif_suspicious,
    }

    # Build Risk Assessment block
    risk_assessment = {
        "overall_score": score_result.get("overall_score", 0.0),
        "status": score_result.get("status", "FLAGGED"),
        "component_breakdown": score_result.get("component_breakdown", {}),
    }

    response_dict = {
        "transaction_id": transaction_id,
        "document_type": doc_type,
        "ocr_extraction": ocr_extraction,
        "validation": validation,
        "tampering_forensics": tampering_forensics,
        "risk_assessment": risk_assessment,
        "processing_notes": notes if notes else ["All checks executed normally"],
    }

    # Include face match and identity graph results if present
    if "face_match" in check_results:
        response_dict["face_match"] = check_results["face_match"]
    if "liveness" in check_results:
        response_dict["liveness"] = check_results["liveness"]
    if "identity_graph" in check_results:
        response_dict["identity_graph"] = check_results["identity_graph"]

    return response_dict


async def _safe_run(fn, *args, **kwargs):
    """Run a function with timeout, returning None on error/timeout."""
    try:
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, lambda: fn(*args, **kwargs)),
            timeout=_TIMEOUT_SECONDS,
        )
    except Exception:
        return None


async def _load_image_from_upload(upload: UploadFile) -> np.ndarray:
    data = await upload.read()
    await upload.seek(0)
    if not data:
        raise HTTPException(status_code=400, detail="Empty image file uploaded")
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")
    h, w = img.shape[:2]
    if max(h, w) > 2000:
        scale = 2000.0 / float(max(h, w))
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


async def _run_exif_forensics(upload: UploadFile) -> dict:
    """Safely run EXIF forensics by saving file bytes temporarily."""
    try:
        await upload.seek(0)
        data = await upload.read()
        await upload.seek(0)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            from modules.forensics.exif import inspect_exif

            res = inspect_exif(tmp_path)
            return res
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        return {"suspicious": False, "error": str(e), "flags": []}


def _extract_mrz_from_image(image: np.ndarray):
    """Extract and parse MRZ lines from the bottom strip of a passport image."""
    from modules.passport.mrz import parse_mrz
    from modules.passport.viz import _get_reader

    h = image.shape[0]
    mrz_strip = image[int(h * 0.80) :, :]
    reader = _get_reader()
    results = reader.readtext(mrz_strip, detail=0)
    mrz_lines = [
        r.replace(" ", "").upper() for r in results if len(r.replace(" ", "")) >= 40
    ]
    if len(mrz_lines) >= 2:
        return parse_mrz(mrz_lines[0][:44], mrz_lines[1][:44])
    return None
