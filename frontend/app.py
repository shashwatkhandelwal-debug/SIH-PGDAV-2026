"""
Streamlit Frontend - AI-Based Document Screening System
SIH 2026 | PS-6188 | SSB / Ministry of Home Affairs

Run with:
    streamlit run frontend/app.py

Accessible from phone browser on the same network at:
    http://<your-ip>:8501
"""

import os
import sys
from typing import Optional

import cv2
import numpy as np
import streamlit as st
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SSB Document Screening",
    page_icon="🛂",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize session states for camera buttons
for key in [
    "start_front",
    "start_back",
    "start_bio",
    "start_extra",
    "start_visa",
    "start_passport",
    "start_face",
]:
    if key not in st.session_state:
        st.session_state[key] = False

# Reset state on doc_type change to avoid camera conflicts
if "last_doc_type" not in st.session_state:
    st.session_state.last_doc_type = "AADHAAR"

# Inject scanner styles with scanline animation
st.markdown(
    """
<style>
/* Document Scan Overlay styling */
.doc-scan-container div[data-testid="stCameraInput"] {
    border: 3px dashed #00FF00 !important;
    border-radius: 12px;
    position: relative;
    overflow: hidden;
}
.doc-scan-container div[data-testid="stCameraInput"]::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 4px;
    background: linear-gradient(to bottom, rgba(0, 255, 0, 0), #00FF00);
    animation: scanline 2.5s linear infinite;
    z-index: 10;
    pointer-events: none;
}
/* Face Scan Overlay styling */
.face-scan-container div[data-testid="stCameraInput"] {
    border: 3px dashed #0088FF !important;
    border-radius: 50% !important;
    position: relative;
    overflow: hidden;
}
.face-scan-container div[data-testid="stCameraInput"]::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 4px;
    background: linear-gradient(to bottom, rgba(0, 136, 255, 0), #0088FF);
    animation: scanline 3.5s linear infinite;
    z-index: 10;
    pointer-events: none;
}
@keyframes scanline {
    0% { top: 0%; }
    50% { top: 100%; }
    100% { top: 0%; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🛂 AI Document Screening System")
st.caption("Sashastra Seema Bal (SSB) | Ministry of Home Affairs | SIH 2026 - PS-6188")
st.divider()

# ── Document type selector ─────────────────────────────────────────────────────
doc_type = st.radio(
    "Select document type to screen:",
    ["AADHAAR", "PASSPORT", "VISA"],
    horizontal=True,
)

# Handle manual tab switches
if st.session_state.last_doc_type != doc_type:
    st.session_state.last_doc_type = doc_type
    for key in [
        "start_front",
        "start_back",
        "start_bio",
        "start_extra",
        "start_visa",
        "start_passport",
        "start_face",
    ]:
        st.session_state[key] = False
    st.rerun()

st.divider()

# ── Two-column layout: input left, results right ────────────────────────────────
col_input, col_results = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("📷 Live Document Scanning")

    inputs = {}
    ready_to_screen = False

    if doc_type == "AADHAAR":
        st.info(
            "Aadhaar requires scanning both front (biometrics/photo) and back (secure QR/address)."
        )

        # Step 1: Front Page
        front_cam = None
        if not st.session_state.start_front:
            if st.button(
                "📸 Scan Aadhaar Front (Photo side)", use_container_width=True
            ):
                st.session_state.start_front = True
                st.rerun()
        else:
            st.markdown('<div class="doc-scan-container">', unsafe_allow_html=True)
            front_cam = st.camera_input("📷 Scan Aadhaar Front (Photo side)")
            st.markdown("</div>", unsafe_allow_html=True)

        # Step 2: Back Page
        back_cam = None
        if not st.session_state.start_back:
            if st.button(
                "📸 Scan Aadhaar Back (QR code side)", use_container_width=True
            ):
                st.session_state.start_back = True
                st.rerun()
        else:
            st.markdown('<div class="doc-scan-container">', unsafe_allow_html=True)
            back_cam = st.camera_input("📷 Scan Aadhaar Back (QR code side)")
            st.markdown("</div>", unsafe_allow_html=True)

        if front_cam:
            pil = Image.open(front_cam).convert("RGB")
            inputs["front"] = np.array(pil)[..., ::-1]
        if back_cam:
            pil = Image.open(back_cam).convert("RGB")
            inputs["back"] = np.array(pil)[..., ::-1]

        ready_to_screen = "front" in inputs and "back" in inputs

    elif doc_type == "PASSPORT":
        st.info("Scan the main biographical data page (containing MRZ text at bottom).")

        # Step 1: Bio page
        bio_cam = None
        if not st.session_state.start_bio:
            if st.button(
                "📸 Scan Passport Biographical Page", use_container_width=True
            ):
                st.session_state.start_bio = True
                st.rerun()
        else:
            st.markdown('<div class="doc-scan-container">', unsafe_allow_html=True)
            bio_cam = st.camera_input("📷 Scan Passport Biographical Page")
            st.markdown("</div>", unsafe_allow_html=True)

        # Step 2: Secondary cover page
        extra_cam = None
        if not st.session_state.start_extra:
            if st.button(
                "📸 Scan Secondary / Cover Page (Optional)", use_container_width=True
            ):
                st.session_state.start_extra = True
                st.rerun()
        else:
            st.markdown('<div class="doc-scan-container">', unsafe_allow_html=True)
            extra_cam = st.camera_input("📷 Scan Secondary / Cover Page")
            st.markdown("</div>", unsafe_allow_html=True)

        if bio_cam:
            pil = Image.open(bio_cam).convert("RGB")
            inputs["bio"] = np.array(pil)[..., ::-1]
        if extra_cam:
            pil = Image.open(extra_cam).convert("RGB")
            inputs["extra"] = np.array(pil)[..., ::-1]

        ready_to_screen = "bio" in inputs

    elif doc_type == "VISA":
        st.info(
            "Scan the Visa stamp/sticker, plus the traveler's passport biographical page to run automatic binding verification."
        )

        # Step 1: Visa stamp
        visa_cam = None
        if not st.session_state.start_visa:
            if st.button("📸 Scan Visa Stamp", use_container_width=True):
                st.session_state.start_visa = True
                st.rerun()
        else:
            st.markdown('<div class="doc-scan-container">', unsafe_allow_html=True)
            visa_cam = st.camera_input("📷 Scan Visa Stamp")
            st.markdown("</div>", unsafe_allow_html=True)

        # Step 2: Passport bio
        pass_cam = None
        if not st.session_state.start_passport:
            if st.button("📸 Scan Passport Page for binding", use_container_width=True):
                st.session_state.start_passport = True
                st.rerun()
        else:
            st.markdown('<div class="doc-scan-container">', unsafe_allow_html=True)
            pass_cam = st.camera_input("📷 Scan Passport Page")
            st.markdown("</div>", unsafe_allow_html=True)

        if visa_cam:
            pil = Image.open(visa_cam).convert("RGB")
            inputs["visa"] = np.array(pil)[..., ::-1]
        if pass_cam:
            pil = Image.open(pass_cam).convert("RGB")
            inputs["passport"] = np.array(pil)[..., ::-1]

        ready_to_screen = "visa" in inputs and "passport" in inputs

    st.divider()

    # Live face capture (for face match)
    st.subheader("🤳 Traveler Live Face Verification")
    live_face = None
    if not st.session_state.start_face:
        if st.button("📸 Open Face Selfie Camera", use_container_width=True):
            st.session_state.start_face = True
            st.rerun()
    else:
        st.markdown('<div class="face-scan-container">', unsafe_allow_html=True)
        live_face = st.camera_input("Capture traveler's face")
        st.markdown("</div>", unsafe_allow_html=True)


# ── Screening orchestrator ─────────────────────────────────────────────────────


def _run_screening(doc_type: str, inputs: dict, live_face_img=None) -> dict:
    """Route to the appropriate module pipeline."""
    from shared.quality_check import check_quality

    # Validate image quality for primary inputs
    primary_key = (
        "front"
        if doc_type == "AADHAAR"
        else ("bio" if doc_type == "PASSPORT" else "visa")
    )
    primary_img = inputs[primary_key]

    quality = check_quality(primary_img)
    if not quality["acceptable"]:
        return {
            "error": f"Primary document scan quality is insufficient",
            "issues": quality["issues"],
            "score_result": {
                "overall_score": 100.0,
                "status": "FLAGGED",
                "failed_checks": [],
                "breakdown": {},
            },
        }

    check_results = {}

    if doc_type == "AADHAAR":
        check_results = _screen_aadhaar(inputs["front"], inputs["back"])
    elif doc_type == "PASSPORT":
        check_results = _screen_passport(inputs["bio"], inputs.get("extra"))
    elif doc_type == "VISA":
        check_results = _screen_visa(inputs["visa"], inputs["passport"])

    # Face match (if live face capture provided)
    if live_face_img:
        from modules.face.embedder import get_embedding
        from modules.face.identity_graph import search_and_store
        from modules.face.match import match_face_to_document

        pil = Image.open(live_face_img).convert("RGB")
        live_arr = np.array(pil)[..., ::-1]

        # Match against biographical page photo
        doc_face_img = inputs["front"] if doc_type == "AADHAAR" else inputs["bio"]

        face_result = match_face_to_document(doc_face_img, live_arr, doc_type)
        check_results["face_match"] = face_result
        check_results["liveness"] = face_result.get("liveness", {"score": 0.0})

        live_emb = get_embedding(live_arr)
        if live_emb is not None:
            doc_number = (check_results.get("_meta", {}).get("doc_number") or "")
            name = (check_results.get("_meta", {}).get("name") or "")
            graph_res = search_and_store(live_emb, name, doc_number, doc_type)
            check_results["identity_graph"] = graph_res

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
    from modules.aadhaar.consistency import check_qr_ocr_consistency
    from modules.aadhaar.ocr import extract_aadhaar_fields
    from modules.aadhaar.qr import decode_aadhaar_qr
    from modules.aadhaar.signature import verify_uidai_signature
    from modules.aadhaar.verhoeff import verhoeff_validate
    from modules.forensics.ela import run_ela

    results = {}

    ocr = extract_aadhaar_fields(front_img)
    qr = decode_aadhaar_qr(back_img)

    uid = ocr.get("uid") or qr.get("fields", {}).get("uid_last4", "")

    # 1. Verhoeff validation
    results["aadhaar_verhoeff"] = {
        "score": 1.0 if (uid and verhoeff_validate(uid)) else 0.0,
        "uid": uid,
    }

    # 2. Cryptographic signature check on back-page QR
    qr_region = None
    if not qr.get("error"):
        qr_region = qr.get("region")
        sig_result = verify_uidai_signature(qr["raw_payload"], qr["signature"])
        results["aadhaar_uidai_signature"] = {
            "score": 1.0 if sig_result["valid"] else 0.0,
            **sig_result,
        }
        # 3. Front OCR vs Back QR cross-check
        consistency = check_qr_ocr_consistency(qr["fields"], ocr)
        results["aadhaar_qr_ocr_consistency"] = {
            "score": 1.0 if consistency["consistent"] else 0.0,
            **consistency,
        }
    else:
        results["aadhaar_uidai_signature"] = {
            "score": 0.0,
            "error": "Aadhaar Back Secure QR not detected",
        }
        results["aadhaar_qr_ocr_consistency"] = {
            "score": 0.0,
            "error": "Secure QR missing",
        }

    results["expiry_valid"] = {"score": 1.0}  # Aadhaar has no expiry

    # 4. Forensics (Run ELA on both images)
    ela_front = run_ela(front_img)
    ela_back = run_ela(back_img)

    results["ela_full_document"] = {
        "score": 0.0 if (ela_front["suspicious"] or ela_back["suspicious"]) else 1.0,
        "front_suspicious": ela_front["suspicious"],
        "back_suspicious": ela_back["suspicious"],
        "mean_variance": ela_front["mean_variance"],
        "heatmap": ela_front["heatmap"],  # Return front heatmap as display sample
    }

    if qr_region:
        ela_reg = run_ela(back_img, region=qr_region)
        results["ela_region_restricted"] = ela_reg
    else:
        results["ela_region_restricted"] = None

    results["_ocr"] = ocr
    results["_qr_fields"] = qr.get("fields", {})
    results["_meta"] = {
        "doc_number": uid or "",
        "name": ocr.get("name_en") or "",
    }

    return results


def _screen_passport(bio_img: np.ndarray, extra_img: Optional[np.ndarray]) -> dict:
    from modules.forensics.ela import run_ela
    from modules.passport.consistency import check_mrz_viz_consistency
    from modules.passport.mrz import parse_mrz
    from modules.passport.viz import extract_viz_fields
    from shared.watchlist import check_watchlist

    results = {}

    # Parse MRZ lines from bottom of biographical page
    h = bio_img.shape[0]
    mrz_strip = bio_img[int(h * 0.80) :, :]
    from modules.passport.viz import _get_reader

    reader = _get_reader()
    mrz_res = reader.readtext(mrz_strip, detail=0)
    mrz_lines = [
        r.replace(" ", "").upper() for r in mrz_res if len(r.replace(" ", "")) >= 40
    ]

    viz = extract_viz_fields(bio_img)
    mrz = None

    if len(mrz_lines) >= 2:
        mrz = parse_mrz(mrz_lines[0][:44], mrz_lines[1][:44])
        results["passport_mrz_checksums"] = {
            "score": 1.0 if mrz["valid"] else 0.0,
            **mrz["check_digits"],
        }
    else:
        results["passport_mrz_checksums"] = {
            "score": 0.0,
            "error": "Could not read or parse MRZ lines at bottom of passport page",
        }

    # Cross check
    if mrz and mrz.get("valid") and viz:
        consistency = check_mrz_viz_consistency(mrz, viz)
        results["passport_mrz_viz_consistency"] = {
            "score": 1.0 if consistency["consistent"] else 0.0,
            **consistency,
        }
    else:
        results["passport_mrz_viz_consistency"] = {
            "score": 0.0,
            "error": "MRZ details missing",
        }

    # Expiry
    if mrz and mrz.get("expiry"):
        from datetime import datetime

        try:
            exp_date = datetime.strptime(mrz["expiry"], "%d/%m/%Y").date()
            results["expiry_valid"] = {
                "score": 1.0 if exp_date >= datetime.now().date() else 0.0
            }
        except Exception:
            results["expiry_valid"] = {"score": 0.0}
    else:
        results["expiry_valid"] = {"score": 0.0}

    # Watchlist check
    pn = (mrz or {}).get("passport_number", "") if mrz else ""
    watchlist = check_watchlist(pn, "Passport") if pn else {}
    if watchlist.get("flagged"):
        results["watchlist"] = {"score": 0.0, **watchlist}

    # e-Passport chip fallback (since mobile browser can't read physical NFC directly)
    results["passport_passive_auth"] = None
    results["passport_active_auth"] = None

    # Forensics
    ela = run_ela(bio_img)
    results["ela_full_document"] = {"score": 0.0 if ela["suspicious"] else 1.0, **ela}

    h_sz, w_sz = bio_img.shape[:2]
    photo_region = (
        int(0.05 * w_sz),
        int(0.10 * h_sz),
        int(0.35 * w_sz),
        int(0.65 * h_sz),
    )
    results["ela_region_restricted"] = run_ela(bio_img, region=photo_region)

    results["_ocr"] = viz
    results["_mrz_fields"] = mrz if mrz else {}

    name = (
        f"{(mrz or {}).get('surname', '')} {(mrz or {}).get('given_names', '')}".strip()
    )
    results["_meta"] = {"doc_number": pn or "", "name": name or ""}

    return results


def _screen_visa(visa_img: np.ndarray, passport_img: np.ndarray) -> dict:
    from modules.forensics.ela import run_ela
    from modules.passport.mrz import parse_mrz
    from modules.visa.binding import check_visa_passport_binding
    from modules.visa.ocr import extract_visa_fields
    from modules.visa.rules import validate_visa_rules
    from shared.watchlist import check_watchlist

    results = {}

    visa_fields = extract_visa_fields(visa_img)

    # Parse MRZ from passport page to bind automatically
    h = passport_img.shape[0]
    mrz_strip = passport_img[int(h * 0.80) :, :]
    from modules.passport.viz import _get_reader

    reader = _get_reader()
    mrz_res = reader.readtext(mrz_strip, detail=0)
    mrz_lines = [
        r.replace(" ", "").upper() for r in mrz_res if len(r.replace(" ", "")) >= 40
    ]

    mrz = None
    if len(mrz_lines) >= 2:
        mrz = parse_mrz(mrz_lines[0][:44], mrz_lines[1][:44])

    if visa_fields:
        # 1. Visa logical rules
        rules = validate_visa_rules(visa_fields)
        results["visa_rule_validation"] = {"score": rules["score"], **rules}

        # 2. Visa-to-Passport binding check
        if mrz and mrz.get("valid"):
            binding = check_visa_passport_binding(visa_fields, mrz)
            results["visa_passport_binding"] = {
                "score": 1.0 if binding["bound"] else 0.0,
                **binding,
            }
        else:
            results["visa_passport_binding"] = {
                "score": 0.0,
                "error": "Could not read passport MRZ for binding",
            }

        # Watchlist
        visa_num = visa_fields.get("visa_number", "")
        watchlist = check_watchlist(visa_num, "Visa") if visa_num else {}
        if watchlist.get("flagged"):
            results["watchlist"] = {"score": 0.0, **watchlist}
    else:
        results["visa_rule_validation"] = {
            "score": 0.0,
            "error": "Visa OCR extraction failed",
        }
        results["visa_passport_binding"] = {
            "score": 0.0,
            "error": "Visa details missing",
        }

    results["expiry_valid"] = {"score": 1.0}  # Verified in visa_rule_validation

    # 3. Forensics
    ela = run_ela(visa_img)
    results["ela_full_document"] = {"score": 0.0 if ela["suspicious"] else 1.0, **ela}

    h_sz, w_sz = visa_img.shape[:2]
    stamp_region = (
        int(0.20 * w_sz),
        int(0.20 * h_sz),
        int(0.80 * w_sz),
        int(0.80 * h_sz),
    )
    results["ela_region_restricted"] = run_ela(visa_img, region=stamp_region)

    results["_ocr"] = visa_fields

    results["_meta"] = {
        "doc_number": (visa_fields or {}).get("visa_number") or "",
        "name": (visa_fields or {}).get("applicant_name") or "",
    }

    return results


# ── Results display ────────────────────────────────────────────────────────────


def _display_results(results: dict):
    if results.get("error"):
        st.error(f"❌ {results['error']}")
        for issue in results.get("issues", []):
            st.warning(issue)
        return

    score_result = results.get("score_result", {})
    total = score_result.get("overall_score", 0)
    risk = score_result.get("status", "UNKNOWN")
    summary = results.get("summary", "")

    # Risk badge
    color_map = {"CLEAR": "green", "REVIEW": "orange", "FLAGGED": "red"}
    color = color_map.get(risk, "gray")
    st.markdown(
        f"### Risk Level: :{color}[**{risk}**] &nbsp; Score: **{total:.0f}/100**"
    )

    # LLM summary
    st.info(f"💬 **Officer Summary**: {summary}")

    # Identity Graph Alert
    check_results = results.get("check_results", {})
    id_graph = check_results.get("identity_graph", {})
    if id_graph and id_graph.get("identity_conflict"):
        st.error("⚠️ **Identity Conflict Detected (Cross-Document Match)**")
        for conflict in id_graph.get("conflict_details", []):
            st.warning(
                f"Face matched previous record: **{conflict['previous_name']}** "
                f"({conflict['previous_doc_number']}) on {conflict['previous_timestamp']}. "
                f"Similarity: **{conflict['similarity'] * 100:.1f}%**"
            )

    # Face Match Results
    face_match = check_results.get("face_match")
    if face_match:
        st.divider()
        st.subheader("🤳 Face Verification Results")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            match_status = "✅ MATCHED" if face_match.get("matched") else "❌ MISMATCH"
            color = "green" if face_match.get("matched") else "red"
            st.markdown(f"Status: :{color}[**{match_status}**]")
            sim = face_match.get("similarity")
            if sim is not None:
                st.metric("Similarity", f"{float(sim) * 100:.1f}%")
            else:
                st.metric("Similarity", "N/A")
        with col_f2:
            liveness_res = check_results.get("liveness", {})
            live_status = (
                "🟢 LIVE" if liveness_res.get("is_live") else "🔴 SPOOF DETECTED"
            )
            l_color = "green" if liveness_res.get("is_live") else "red"
            st.markdown(f"Liveness Check: :{l_color}[**{live_status}**]")
            live_s = liveness_res.get("score")
            if live_s is not None:
                st.metric("Liveness Score", f"{float(live_s) * 100:.1f}%")
            else:
                st.metric("Liveness Score", "N/A")

    st.divider()

    # Check breakdown
    st.subheader("Check Breakdown")
    breakdown = score_result.get("component_breakdown", {})
    for check_name, contribution in breakdown.items():
        icon = "❌" if contribution > 0.0 else "✅"
        label = check_name.replace("_", " ").title()
        st.markdown(f"{icon} **{label}** - contribution: `{contribution:.1f}`")

    # ELA heatmap
    ela = check_results.get("ela_full_document", {})
    if ela.get("heatmap") is not None:
        st.divider()
        st.subheader("🔬 ELA Heatmap (Tamper Analysis)")
        st.image(
            ela["heatmap"],
            caption="Error Level Analysis - bright regions indicate inconsistent compression history",
            use_container_width=True,
        )

    # Extracted fields
    ocr = check_results.get("_ocr", {})
    qr = check_results.get("_qr_fields", {})
    mrz = check_results.get("_mrz_fields", {})

    if ocr or qr or mrz:
        st.divider()
        st.subheader("📋 Extracted Fields")
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Biographical data (OCR)")
            for k, v in ocr.items():
                if k not in ("raw_text", "confidence") and v:
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
                    if k not in ("check_digits", "raw") and v:
                        st.text(f"{k.replace('_', ' ').title()}: {v}")


# ── Render results column ──────────────────────────────────────────────────────

with col_results:
    st.subheader("📊 Screening Results")

    if ready_to_screen:
        with st.spinner("Running deep document verification..."):
            results = _run_screening(doc_type, inputs, live_face)

        _display_results(results)
    else:
        st.info("Complete the camera scans on the left to begin screening.")
