"""
Streamlit Frontend — AI-Based Document Screening System
SIH 2026 | PS-6188 | SSB / Ministry of Home Affairs

Run with:
    streamlit run frontend/app.py

Accessible from phone browser on the same network at:
    http://<your-ip>:8501
"""
import streamlit as st
import numpy as np
import cv2
from PIL import Image
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SSB Document Screening",
    page_icon="🛂",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🛂 AI Document Screening System")
st.caption("Sashastra Seema Bal (SSB) | Ministry of Home Affairs | SIH 2026 — PS-6188")
st.divider()

# ── Document type selector ─────────────────────────────────────────────────────
doc_type = st.radio(
    "Select document type to screen:",
    ["Aadhaar", "Passport", "Visa"],
    horizontal=True,
)

st.divider()

# ── Two-column layout: input left, results right ────────────────────────────────
col_input, col_results = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("📷 Live Document Scanning")
    
    inputs = {}
    
    if doc_type == "Aadhaar":
        st.info("Aadhaar requires scanning both front (biometrics/photo) and back (secure QR/address).")
        
        # Camera inputs
        front_cam = st.camera_input("📷 Step 1: Scan Aadhaar Front (Photo side)")
        back_cam = st.camera_input("📷 Step 2: Scan Aadhaar Back (QR code side)")
        
        if front_cam:
            pil = Image.open(front_cam).convert('RGB')
            inputs['front'] = np.array(pil)[..., ::-1]
        if back_cam:
            pil = Image.open(back_cam).convert('RGB')
            inputs['back'] = np.array(pil)[..., ::-1]
            
        ready_to_screen = 'front' in inputs and 'back' in inputs
        
    elif doc_type == "Passport":
        st.info("Scan the main biographical data page (containing MRZ text at bottom).")
        
        bio_cam = st.camera_input("📷 Step 1: Scan Passport Biographical Page")
        extra_cam = st.camera_input("📷 Step 2: Scan Secondary / Cover Page (Optional for forensics)")
        
        if bio_cam:
            pil = Image.open(bio_cam).convert('RGB')
            inputs['bio'] = np.array(pil)[..., ::-1]
        if extra_cam:
            pil = Image.open(extra_cam).convert('RGB')
            inputs['extra'] = np.array(pil)[..., ::-1]
            
        ready_to_screen = 'bio' in inputs

    elif doc_type == "Visa":
        st.info("Scan the Visa stamp/sticker, plus the traveler's passport biographical page to run automatic binding verification.")
        
        visa_cam = st.camera_input("📷 Step 1: Scan Visa Stamp")
        pass_cam = st.camera_input("📷 Step 2: Scan Passport Biographical Page")
        
        if visa_cam:
            pil = Image.open(visa_cam).convert('RGB')
            inputs['visa'] = np.array(pil)[..., ::-1]
        if pass_cam:
            pil = Image.open(pass_cam).convert('RGB')
            inputs['passport'] = np.array(pil)[..., ::-1]
            
        ready_to_screen = 'visa' in inputs and 'passport' in inputs

    st.divider()
    
    # Live face capture (for face match)
    st.subheader("🤳 Traveler Live Face Verification")
    live_face = st.camera_input("Capture traveler's face")

    # Screen button
    screen_btn = st.button(
        "🔍 Screen Traveler Documents",
        type="primary",
        use_container_width=True,
        disabled=not ready_to_screen,
    )



# ── Screening orchestrator ─────────────────────────────────────────────────────

def _run_screening(doc_type: str, inputs: dict, live_face_img=None) -> dict:
    """Route to the appropriate module pipeline."""
    from shared.quality_check import check_quality

    # Validate image quality for primary inputs
    primary_key = 'front' if doc_type == 'Aadhaar' else ('bio' if doc_type == 'Passport' else 'visa')
    primary_img = inputs[primary_key]
    
    quality = check_quality(primary_img)
    if not quality['acceptable']:
        return {
            "error": f"Primary document scan quality is insufficient",
            "issues": quality['issues'],
            "score_result": {"total_score": 0, "risk_level": "HIGH", "failed_checks": [], "breakdown": {}},
        }

    check_results = {}

    if doc_type == "Aadhaar":
        check_results = _screen_aadhaar(inputs['front'], inputs['back'])
    elif doc_type == "Passport":
        check_results = _screen_passport(inputs['bio'], inputs.get('extra'))
    elif doc_type == "Visa":
        check_results = _screen_visa(inputs['visa'], inputs['passport'])

    # Face match (if live face capture provided)
    if live_face_img:
        from modules.face.match import match_face_to_document
        pil = Image.open(live_face_img).convert('RGB')
        live_arr = np.array(pil)[..., ::-1]
        
        # Match against biographical page photo
        doc_face_img = inputs['front'] if doc_type == 'Aadhaar' else inputs['bio']
        
        face_result = match_face_to_document(doc_face_img, live_arr, doc_type)
        check_results['face_match'] = face_result
        check_results['liveness'] = face_result.get('liveness', {'score': 0.5})

    # Scorer
    from modules.decision.scorer import compute_score
    score_result = compute_score(check_results)

    # LLM summary
    from modules.decision.llm_summary import generate_summary
    summary = generate_summary(check_results, score_result)

    return {
        "doc_type": doc_type,
        "check_results": check_results,
        "score_result": score_result,
        "summary": summary,
        "error": None,
    }


def _screen_aadhaar(front_img: np.ndarray, back_img: np.ndarray) -> dict:
    from modules.aadhaar.ocr import extract_aadhaar_fields
    from modules.aadhaar.qr import decode_aadhaar_qr
    from modules.aadhaar.verhoeff import verhoeff_validate
    from modules.aadhaar.signature import verify_uidai_signature
    from modules.aadhaar.consistency import check_qr_ocr_consistency
    from modules.forensics.ela import run_ela
    
    results = {}

    ocr = extract_aadhaar_fields(front_img)
    qr  = decode_aadhaar_qr(back_img)

    uid = ocr.get('uid') or qr.get('fields', {}).get('uid_last4', '')
    
    # 1. Verhoeff validation
    results['aadhaar_verhoeff'] = {
        'score': 1.0 if (uid and verhoeff_validate(uid)) else 0.0,
        'uid': uid,
    }

    # 2. Cryptographic signature check on back-page QR
    if not qr.get('error'):
        sig_result = verify_uidai_signature(qr['raw_payload'], qr['signature'])
        results['aadhaar_uidai_signature'] = {
            'score': 1.0 if sig_result['valid'] else 0.0,
            **sig_result,
        }
        # 3. Front OCR vs Back QR cross-check
        consistency = check_qr_ocr_consistency(qr['fields'], ocr)
        results['aadhaar_qr_ocr_consistency'] = {
            'score': 1.0 if consistency['consistent'] else 0.0,
            **consistency,
        }
    else:
        results['aadhaar_uidai_signature'] = {'score': 0.0, 'error': 'Aadhaar Back Secure QR not detected'}
        results['aadhaar_qr_ocr_consistency'] = {'score': 0.5, 'error': 'Secure QR missing'}

    results['expiry_valid'] = {'score': 1.0}  # Aadhaar has no expiry

    # 4. Forensics (Run ELA on both images)
    ela_front = run_ela(front_img)
    ela_back  = run_ela(back_img)
    
    results['ela_full_document'] = {
        'score': 0.0 if (ela_front['suspicious'] or ela_back['suspicious']) else 1.0,
        'front_suspicious': ela_front['suspicious'],
        'back_suspicious': ela_back['suspicious'],
        'heatmap': ela_front['heatmap'],  # Return front heatmap as display sample
    }
    results['ela_region_restricted'] = {'score': 0.5}

    results['_ocr'] = ocr
    results['_qr_fields'] = qr.get('fields', {})

    return results


def _screen_passport(bio_img: np.ndarray, extra_img: Optional[np.ndarray]) -> dict:
    from modules.passport.mrz import parse_mrz
    from modules.passport.viz import extract_viz_fields
    from modules.passport.consistency import check_mrz_viz_consistency
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist
    
    results = {}

    # Parse MRZ lines from bottom of biographical page
    h = bio_img.shape[0]
    mrz_strip = bio_img[int(h * 0.80):, :]
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False)
    mrz_res = reader.readtext(mrz_strip, detail=0)
    mrz_lines = [r.replace(' ', '').upper() for r in mrz_res if len(r.replace(' ', '')) >= 40]

    viz = extract_viz_fields(bio_img)
    mrz = None

    if len(mrz_lines) >= 2:
        mrz = parse_mrz(mrz_lines[0][:44], mrz_lines[1][:44])
        results['passport_mrz_checksums'] = {
            'score': 1.0 if mrz['valid'] else 0.0,
            **mrz['check_digits']
        }
    else:
        results['passport_mrz_checksums'] = {
            'score': 0.0, 'error': 'Could not read or parse MRZ lines at bottom of passport page'
        }

    # Cross check
    if mrz and mrz.get('valid') and viz:
        consistency = check_mrz_viz_consistency(mrz, viz)
        results['passport_mrz_viz_consistency'] = {
            'score': 1.0 if consistency['consistent'] else 0.0,
            **consistency
        }
    else:
        results['passport_mrz_viz_consistency'] = {'score': 0.5, 'error': 'MRZ details missing'}

    # Expiry
    if mrz and mrz.get('expiry'):
        from datetime import datetime
        try:
            exp_date = datetime.strptime(mrz['expiry'], "%d/%m/%Y").date()
            results['expiry_valid'] = {'score': 1.0 if exp_date >= datetime.now().date() else 0.0}
        except Exception:
            results['expiry_valid'] = {'score': 0.5}
    else:
        results['expiry_valid'] = {'score': 0.5}

    # Watchlist check
    pn = (mrz or {}).get('passport_number', '') if mrz else ''
    watchlist = check_watchlist(pn, 'Passport') if pn else {}
    if watchlist.get('flagged'):
        results['watchlist'] = {'score': 0.0, **watchlist}

    # e-Passport chip fallback (since mobile browser can't read physical NFC directly)
    results['passport_passive_auth'] = {'score': 0.5, 'note': 'NFC hardware not present on client terminal'}
    results['passport_active_auth'] = {'score': 0.5, 'note': 'NFC hardware not present on client terminal'}

    # Forensics
    ela = run_ela(bio_img)
    results['ela_full_document'] = {'score': 0.0 if ela['suspicious'] else 1.0, **ela}
    results['ela_region_restricted'] = {'score': 0.5}

    results['_ocr'] = viz
    results['_mrz_fields'] = mrz if mrz else {}

    return results


def _screen_visa(visa_img: np.ndarray, passport_img: np.ndarray) -> dict:
    from modules.visa.ocr import extract_visa_fields
    from modules.visa.rules import validate_visa_rules
    from modules.visa.binding import check_visa_passport_binding
    from modules.passport.mrz import parse_mrz
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist
    
    results = {}

    visa_fields = extract_visa_fields(visa_img)
    
    # Parse MRZ from passport page to bind automatically
    h = passport_img.shape[0]
    mrz_strip = passport_img[int(h * 0.80):, :]
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False)
    mrz_res = reader.readtext(mrz_strip, detail=0)
    mrz_lines = [r.replace(' ', '').upper() for r in mrz_res if len(r.replace(' ', '')) >= 40]
    
    mrz = None
    if len(mrz_lines) >= 2:
        mrz = parse_mrz(mrz_lines[0][:44], mrz_lines[1][:44])

    if visa_fields:
        # 1. Visa logical rules
        rules = validate_visa_rules(visa_fields)
        results['visa_rule_validation'] = {'score': rules['score'], **rules}

        # 2. Visa-to-Passport binding check
        if mrz and mrz.get('valid'):
            binding = check_visa_passport_binding(visa_fields, mrz)
            results['visa_passport_binding'] = {
                'score': 1.0 if binding['bound'] else 0.0,
                **binding
            }
        else:
            results['visa_passport_binding'] = {'score': 0.5, 'error': 'Could not read passport MRZ for binding'}
            
        # Watchlist
        visa_num = visa_fields.get('visa_number', '')
        watchlist = check_watchlist(visa_num, 'Visa') if visa_num else {}
        if watchlist.get('flagged'):
            results['watchlist'] = {'score': 0.0, **watchlist}
    else:
        results['visa_rule_validation'] = {'score': 0.0, 'error': 'Visa OCR extraction failed'}
        results['visa_passport_binding'] = {'score': 0.5, 'error': 'Visa details missing'}

    results['expiry_valid'] = {'score': 1.0}  # Verified in visa_rule_validation

    # 3. Forensics
    ela = run_ela(visa_img)
    results['ela_full_document'] = {'score': 0.0 if ela['suspicious'] else 1.0, **ela}
    results['ela_region_restricted'] = {'score': 0.5}

    results['_ocr'] = visa_fields

    return results


# ── Results display ────────────────────────────────────────────────────────────

def _display_results(results: dict):
    if results.get('error'):
        st.error(f"❌ {results['error']}")
        for issue in results.get('issues', []):
            st.warning(issue)
        return

    score_result = results.get('score_result', {})
    total = score_result.get('total_score', 0)
    risk  = score_result.get('risk_level', 'UNKNOWN')
    summary = results.get('summary', '')

    # Risk badge
    color_map = {"PASS": "green", "LOW": "blue", "MEDIUM": "orange", "HIGH": "red"}
    color = color_map.get(risk, "gray")
    st.markdown(f"### Risk Level: :{color}[**{risk}**] &nbsp; Score: **{total:.0f}/100**")

    # LLM summary
    st.info(f"💬 **Officer Summary**: {summary}")

    st.divider()

    # Check breakdown
    st.subheader("Check Breakdown")
    breakdown = score_result.get('breakdown', {})
    for check_name, detail in breakdown.items():
        if check_name.startswith('_'):
            continue
        score = detail.get('score', 0.5)
        icon  = "✅" if score >= 0.8 else ("⚠️" if score >= 0.4 else "❌")
        label = check_name.replace('_', ' ').title()
        st.markdown(f"{icon} **{label}** — score: `{score:.1f}` (weight: {detail.get('weight')})")

    # ELA heatmap
    check_results = results.get('check_results', {})
    ela = check_results.get('ela_full_document', {})
    if ela.get('heatmap') is not None:
        st.divider()
        st.subheader("🔬 ELA Heatmap (Tamper Analysis)")
        st.image(ela['heatmap'], caption="Error Level Analysis — bright regions indicate inconsistent compression history", use_column_width=True)

    # Extracted fields
    ocr = check_results.get('_ocr', {})
    qr  = check_results.get('_qr_fields', {})
    mrz = check_results.get('_mrz_fields', {})
    
    if ocr or qr or mrz:
        st.divider()
        st.subheader("📋 Extracted Fields")
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Biographical data (OCR)")
            for k, v in ocr.items():
                if k not in ('raw_text', 'confidence') and v:
                    st.text(f"{k.replace('_', ' ').title()}: {v}")
        with c2:
            if qr:
                st.caption("QR Code Data (Signed)")
                for k, v in qr.items():
                    if v:
                        st.text(f"{k.replace('_', ' ').title()}: {v}")
            elif mrz:
                st.caption("MRZ Line Data (Machine Readable)")
                for k, v in mrz.items():
                    if k not in ('check_digits', 'raw') and v:
                        st.text(f"{k.replace('_', ' ').title()}: {v}")


# ── Render results column ──────────────────────────────────────────────────────

with col_results:
    st.subheader("📊 Screening Results")

    if screen_btn and ready_to_screen:
        with st.spinner("Running deep document verification..."):
            results = _run_screening(doc_type, inputs, live_face)

        _display_results(results)
    else:
        st.info("Complete the camera scans on the left and tap **Screen Traveler Documents** to begin.")

