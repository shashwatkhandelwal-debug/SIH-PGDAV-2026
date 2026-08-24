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
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SSB Document Screening",
    page_icon="🛂",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state ──────────────────────────────────────────────────────────────
if 'screening_history' not in st.session_state:
    st.session_state.screening_history = []

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
    st.subheader("📷 Document Input")

    upload_tab, camera_tab = st.tabs(["Upload File", "Use Camera"])

    with upload_tab:
        uploaded_file = st.file_uploader(
            "Upload document image",
            type=["jpg", "jpeg", "png"],
            label_visibility="collapsed",
        )
        doc_image = None
        if uploaded_file:
            pil_img = Image.open(uploaded_file).convert('RGB')
            doc_image = np.array(pil_img)[..., ::-1]  # RGB → BGR
            st.image(pil_img, caption="Uploaded document", use_column_width=True)

    with camera_tab:
        camera_image = st.camera_input("Point camera at document")
        if camera_image:
            pil_img = Image.open(camera_image).convert('RGB')
            doc_image = np.array(pil_img)[..., ::-1]

    # Live face capture (for face match)
    st.subheader("🤳 Live Face Capture")
    live_face = st.camera_input("Capture traveler's face for verification")

    # Screen button
    screen_btn = st.button(
        "🔍 Screen Document",
        type="primary",
        use_container_width=True,
        disabled=(doc_image is None),
    )

with col_results:
    st.subheader("📊 Screening Results")

    if screen_btn and doc_image is not None:
        with st.spinner("Running checks..."):
            results = _run_screening(doc_type, doc_image, live_face)

        _display_results(results)
    else:
        st.info("Upload or photograph a document and press **Screen Document** to begin.")


# ── Screening orchestrator ─────────────────────────────────────────────────────

def _run_screening(doc_type: str, image: np.ndarray, live_face_img=None) -> dict:
    """Route to the appropriate module pipeline."""
    from shared.quality_check import check_quality

    quality = check_quality(image)
    if not quality['acceptable']:
        return {
            "error": "Document quality insufficient",
            "issues": quality['issues'],
            "score_result": {"total_score": 0, "risk_level": "HIGH", "failed_checks": [], "breakdown": {}},
        }

    check_results = {}

    if doc_type == "Aadhaar":
        check_results = _screen_aadhaar(image)
    elif doc_type == "Passport":
        check_results = _screen_passport(image)
    elif doc_type == "Visa":
        check_results = _screen_visa(image)

    # Face match (if live face provided)
    if live_face_img:
        from modules.face.match import match_face_to_document
        pil = Image.open(live_face_img).convert('RGB')
        live_arr = np.array(pil)[..., ::-1]
        face_result = match_face_to_document(image, live_arr, doc_type)
        check_results['face_match'] = face_result
        check_results['liveness'] = face_result.get('liveness', {'score': 0.5})

    # Score
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


def _screen_aadhaar(image: np.ndarray) -> dict:
    from modules.aadhaar.ocr import extract_aadhaar_fields
    from modules.aadhaar.qr import decode_aadhaar_qr
    from modules.aadhaar.verhoeff import verhoeff_validate
    from modules.aadhaar.signature import verify_uidai_signature
    from modules.aadhaar.consistency import check_qr_ocr_consistency
    from modules.forensics.ela import run_ela
    from modules.forensics.exif import inspect_exif
    from datetime import datetime

    results = {}

    ocr = extract_aadhaar_fields(image)
    qr  = decode_aadhaar_qr(image)

    uid = ocr.get('uid') or ''
    results['aadhaar_verhoeff'] = {
        'score': 1.0 if verhoeff_validate(uid) else 0.0,
        'uid': uid,
    }

    if not qr.get('error'):
        sig_result = verify_uidai_signature(qr['raw_payload'], qr['signature'])
        results['aadhaar_uidai_signature'] = {
            'score': 1.0 if sig_result['valid'] else 0.0,
            **sig_result,
        }
        consistency = check_qr_ocr_consistency(qr['fields'], ocr)
        results['aadhaar_qr_ocr_consistency'] = {
            'score': 1.0 if consistency['consistent'] else 0.0,
            **consistency,
        }
    else:
        results['aadhaar_uidai_signature'] = {'score': 0.0, 'error': 'QR not detected'}
        results['aadhaar_qr_ocr_consistency'] = {'score': 0.5, 'error': 'QR not detected'}

    # Expiry
    dob = ocr.get('dob')
    results['expiry_valid'] = {'score': 1.0}  # Aadhaar has no expiry

    # Forensics
    ela = run_ela(image)
    results['ela_full_document'] = {'score': 0.0 if ela['suspicious'] else 1.0, **ela}
    results['ela_region_restricted'] = {'score': 0.5}  # TODO: detect QR region bbox

    results['_ocr'] = ocr
    results['_qr_fields'] = qr.get('fields', {})

    return results


def _screen_passport(image: np.ndarray) -> dict:
    # Placeholder — full implementation in modules/passport/
    return {"passport_mrz_checksums": {"score": 0.5, "note": "Implementation in progress"}}


def _screen_visa(image: np.ndarray) -> dict:
    # Placeholder — full implementation in modules/visa/
    return {"visa_rule_validation": {"score": 0.5, "note": "Implementation in progress"}}


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
    if ocr or qr:
        st.divider()
        st.subheader("📋 Extracted Fields")
        c1, c2 = st.columns(2)
        with c1:
            st.caption("OCR (Printed Text)")
            for k, v in ocr.items():
                if k not in ('raw_text', 'confidence') and v:
                    st.text(f"{k}: {v}")
        with c2:
            st.caption("QR Payload (UIDAI Signed)")
            for k, v in qr.items():
                if v:
                    st.text(f"{k}: {v}")
