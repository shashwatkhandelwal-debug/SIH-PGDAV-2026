"""
FastAPI Orchestrator — Single API endpoint per document type.

Each screening request triggers all applicable module checks.
One module failing never crashes the whole request — every check
is wrapped in a try/except with a graceful timeout fallback.

Endpoints:
  POST /screen/aadhaar   — Screen an Aadhaar card
  POST /screen/passport  — Screen a passport (with optional NFC data)
  POST /screen/visa      — Screen a visa stamp
  GET  /audit/recent     — Recent screening history
  GET  /audit/flagged    — HIGH/MEDIUM risk screenings
  GET  /stats            — Identity graph and audit statistics

Run with:
  uvicorn api.orchestrator:app --host 0.0.0.0 --port 8000 --reload
"""
import asyncio
import base64
import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="SSB Document Screening API",
    description="AI-Based Fake Identity & Document Screening System — SIH 2026 PS-6188",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_TIMEOUT_SECONDS = 10.0


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/screen/aadhaar")
async def screen_aadhaar(
    document: UploadFile = File(...),
    live_face: Optional[UploadFile] = File(None),
):
    """Screen an Aadhaar card image."""
    doc_image = await _load_image_from_upload(document)
    live_image = await _load_image_from_upload(live_face) if live_face else None

    check_results = await _run_aadhaar_checks(doc_image)

    if live_image is not None:
        face_result = await _safe_run(
            _run_face_checks, doc_image, live_image, 'Aadhaar'
        )
        check_results.update(face_result)

    return await _finalize(check_results, 'Aadhaar',
                           check_results.get('_meta', {}).get('doc_number', ''),
                           check_results.get('_meta', {}).get('name', ''))


@app.post("/screen/passport")
async def screen_passport(
    document: UploadFile = File(...),
    live_face: Optional[UploadFile] = File(None),
    nfc_available: bool = Form(False),
):
    """Screen a passport image (NFC optional)."""
    doc_image = await _load_image_from_upload(document)
    live_image = await _load_image_from_upload(live_face) if live_face else None

    check_results = await _run_passport_checks(doc_image, nfc_available)

    if live_image is not None:
        face_result = await _safe_run(
            _run_face_checks, doc_image, live_image, 'Passport'
        )
        check_results.update(face_result)

    return await _finalize(check_results, 'Passport',
                           check_results.get('_meta', {}).get('doc_number', ''),
                           check_results.get('_meta', {}).get('name', ''))


@app.post("/screen/visa")
async def screen_visa(
    document: UploadFile = File(...),
    passport_mrz_number: Optional[str] = Form(None),
):
    """Screen a visa stamp image, optionally cross-checking against a passport MRZ number."""
    doc_image = await _load_image_from_upload(document)
    check_results = await _run_visa_checks(doc_image, passport_mrz_number)

    return await _finalize(check_results, 'Visa',
                           check_results.get('_meta', {}).get('doc_number', ''),
                           check_results.get('_meta', {}).get('name', ''))


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


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Module pipelines ───────────────────────────────────────────────────────────

async def _run_aadhaar_checks(image: np.ndarray) -> dict:
    results = {}

    from modules.aadhaar.ocr import extract_aadhaar_fields
    from modules.aadhaar.qr import decode_aadhaar_qr
    from modules.aadhaar.verhoeff import verhoeff_validate
    from modules.aadhaar.signature import verify_uidai_signature
    from modules.aadhaar.consistency import check_qr_ocr_consistency
    from modules.forensics.ela import run_ela
    from modules.forensics.exif import inspect_exif
    from shared.quality_check import check_quality
    from shared.watchlist import check_watchlist

    quality = check_quality(image)
    if not quality['acceptable']:
        return {"_quality_error": quality}

    ocr = await _safe_run(extract_aadhaar_fields, image)
    qr  = await _safe_run(decode_aadhaar_qr, image)

    uid = (ocr or {}).get('uid', '')
    results['aadhaar_verhoeff'] = {
        'score': 1.0 if (uid and verhoeff_validate(uid)) else 0.0,
        'uid': uid,
    }

    if qr and not qr.get('error'):
        sig = await _safe_run(verify_uidai_signature, qr['raw_payload'], qr['signature'])
        results['aadhaar_uidai_signature'] = {'score': 1.0 if (sig and sig.get('valid')) else 0.0, **(sig or {})}
        cons = await _safe_run(check_qr_ocr_consistency, qr.get('fields', {}), ocr or {})
        results['aadhaar_qr_ocr_consistency'] = {'score': 1.0 if (cons and cons.get('consistent')) else 0.0, **(cons or {})}
    else:
        results['aadhaar_uidai_signature'] = {'score': 0.0, 'error': 'QR not detected'}
        results['aadhaar_qr_ocr_consistency'] = {'score': 0.5, 'error': 'QR not detected'}

    results['expiry_valid'] = {'score': 1.0}  # Aadhaar has no expiry

    ela = await _safe_run(run_ela, image)
    results['ela_full_document'] = {'score': 0.0 if (ela and ela.get('suspicious')) else 1.0, **(ela or {})}
    results['ela_region_restricted'] = {'score': 0.5}

    watchlist = check_watchlist(uid, 'Aadhaar') if uid else {}
    if watchlist.get('flagged'):
        results['watchlist'] = {'score': 0.0, **watchlist}

    results['_meta'] = {'doc_number': uid, 'name': (ocr or {}).get('name_en', '')}
    return results


async def _run_passport_checks(image: np.ndarray, nfc_available: bool) -> dict:
    results = {}
    from modules.passport.mrz import parse_mrz
    from modules.passport.viz import extract_viz_fields
    from modules.passport.consistency import check_mrz_viz_consistency
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist
    from shared.quality_check import check_quality

    quality = check_quality(image)
    if not quality['acceptable']:
        return {"_quality_error": quality}

    # MRZ extraction — detect two-line MRZ at bottom of image
    mrz_data = await _safe_run(_extract_mrz_from_image, image)
    viz_data = await _safe_run(extract_viz_fields, image)

    if mrz_data and mrz_data.get('valid'):
        results['passport_mrz_checksums'] = {'score': 1.0, **mrz_data.get('check_digits', {})}
        if viz_data:
            cons = await _safe_run(check_mrz_viz_consistency, mrz_data, viz_data)
            results['passport_mrz_viz_consistency'] = {
                'score': 1.0 if (cons and cons.get('consistent')) else 0.0,
                **(cons or {})
            }
    else:
        results['passport_mrz_checksums'] = {'score': 0.0, 'error': 'MRZ parse failed or invalid check digits'}
        results['passport_mrz_viz_consistency'] = {'score': 0.5, 'error': 'MRZ not available'}

    # NFC checks (fallback to 0.5 if hardware unavailable)
    if nfc_available:
        results['passport_passive_auth'] = {'score': 0.5, 'error': 'NFC read pending'}
        results['passport_active_auth']  = {'score': 0.5, 'error': 'NFC read pending'}
    else:
        results['passport_passive_auth'] = {'score': 0.5, 'note': 'NFC hardware not available — skipped'}
        results['passport_active_auth']  = {'score': 0.5, 'note': 'NFC hardware not available — skipped'}

    ela = await _safe_run(run_ela, image)
    results['ela_full_document'] = {'score': 0.0 if (ela and ela.get('suspicious')) else 1.0, **(ela or {})}

    pn = (mrz_data or {}).get('passport_number', '')
    watchlist = check_watchlist(pn, 'Passport') if pn else {}
    if watchlist.get('flagged'):
        results['watchlist'] = {'score': 0.0, **watchlist}

    name = f"{(mrz_data or {}).get('surname', '')} {(mrz_data or {}).get('given_names', '')}".strip()
    results['_meta'] = {'doc_number': pn, 'name': name, 'mrz': mrz_data, 'viz': viz_data}
    return results


async def _run_visa_checks(image: np.ndarray, passport_mrz_number: Optional[str]) -> dict:
    results = {}
    from modules.visa.ocr import extract_visa_fields
    from modules.visa.rules import validate_visa_rules
    from modules.visa.binding import check_visa_passport_binding
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist

    visa_fields = await _safe_run(extract_visa_fields, image)

    if visa_fields:
        rules = await _safe_run(validate_visa_rules, visa_fields)
        results['visa_rule_validation'] = {'score': (rules or {}).get('score', 0.5), **(rules or {})}

        if passport_mrz_number:
            binding = await _safe_run(
                check_visa_passport_binding,
                visa_fields,
                {'passport_number': passport_mrz_number}
            )
            results['visa_passport_binding'] = {
                'score': 1.0 if (binding and binding.get('bound')) else 0.0,
                **(binding or {})
            }

        visa_num = visa_fields.get('visa_number', '')
        watchlist = check_watchlist(visa_num, 'Visa') if visa_num else {}
        if watchlist.get('flagged'):
            results['watchlist'] = {'score': 0.0, **watchlist}
    else:
        results['visa_rule_validation'] = {'score': 0.0, 'error': 'OCR failed'}

    ela = await _safe_run(run_ela, image)
    results['ela_region_restricted'] = {'score': 0.0 if (ela and ela.get('suspicious')) else 1.0, **(ela or {})}

    results['_meta'] = {
        'doc_number': (visa_fields or {}).get('visa_number', ''),
        'name': (visa_fields or {}).get('applicant_name', '')
    }
    return results


async def _run_face_checks(doc_image, live_image, doc_type) -> dict:
    from modules.face.match import match_face_to_document
    from modules.face.liveness import passive_liveness_check
    from modules.face.identity_graph import search_and_store
    from modules.face.embedder import get_embedding

    results = {}
    face_match = match_face_to_document(doc_image, live_image, doc_type)
    results['face_match'] = face_match

    liveness = passive_liveness_check(live_image)
    results['liveness'] = {'score': 1.0 if liveness.get('is_live') else 0.0, **liveness}

    embedding = get_embedding(live_image)
    if embedding is not None:
        graph_result = search_and_store(embedding, '', '', doc_type)
        results['identity_graph'] = graph_result

    return results


# ── Shared helpers ─────────────────────────────────────────────────────────────

async def _finalize(check_results: dict, doc_type: str, doc_number: str, name: str) -> dict:
    from modules.decision.scorer import compute_score
    from modules.decision.llm_summary import generate_summary
    from shared.audit import log_screening

    # Remove internal _meta keys before scoring
    score_input = {k: v for k, v in check_results.items() if not k.startswith('_')}
    score_result = compute_score(score_input)
    summary = generate_summary(score_input, score_result)

    log_screening(
        doc_type=doc_type,
        doc_number=doc_number,
        name=name,
        risk_level=score_result['risk_level'],
        total_score=score_result['total_score'],
        failed_checks=score_result['failed_checks'],
        summary=summary,
    )

    return {
        "doc_type": doc_type,
        "check_results": score_input,
        "score": score_result,
        "summary": summary,
    }


async def _safe_run(fn, *args, **kwargs):
    """Run a function with timeout, returning None on error/timeout."""
    try:
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, lambda: fn(*args, **kwargs)),
            timeout=_TIMEOUT_SECONDS
        )
    except Exception:
        return None


async def _load_image_from_upload(upload: UploadFile) -> np.ndarray:
    data = await upload.read()
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")
    return img


def _extract_mrz_from_image(image: np.ndarray):
    """Extract and parse MRZ lines from the bottom strip of a passport image."""
    from modules.passport.mrz import parse_mrz
    import easyocr
    # MRZ is in the bottom ~20% of the bio page
    h = image.shape[0]
    mrz_strip = image[int(h * 0.80):, :]
    reader = easyocr.Reader(['en'], gpu=False)
    results = reader.readtext(mrz_strip, detail=0)
    # Filter for 44-char lines (TD3 MRZ)
    mrz_lines = [r.replace(' ', '').upper() for r in results if len(r.replace(' ', '')) >= 40]
    if len(mrz_lines) >= 2:
        return parse_mrz(mrz_lines[0][:44], mrz_lines[1][:44])
    return None
