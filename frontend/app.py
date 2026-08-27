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

# Inject scanner styles with scanline animation & focus reticle
st.markdown(
    """
<style>
/* Document Scan Overlay styling */
.doc-scan-container div[data-testid="stCameraInput"] {
    border: 3px solid #00E676 !important;
    border-radius: 16px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 20px rgba(0, 230, 118, 0.25);
}
.doc-scan-container div[data-testid="stCameraInput"]::before {
    content: "🎯 ALIGN DOCUMENT INSIDE FRAME (TAP SCREEN TO FOCUS)";
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.75);
    color: #00E676;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    z-index: 15;
    pointer-events: none;
}
.doc-scan-container div[data-testid="stCameraInput"]::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(90deg, transparent, #00E676, #FFFFFF, #00E676, transparent);
    animation: scanline 2.0s ease-in-out infinite;
    z-index: 10;
    pointer-events: none;
    box-shadow: 0 0 12px #00E676;
}
/* QR Scan Overlay styling (GPay style) */
.qr-scan-container div[data-testid="stCameraInput"] {
    border: 3px solid #FFD600 !important;
    border-radius: 16px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 25px rgba(255, 214, 0, 0.3);
}
.qr-scan-container div[data-testid="stCameraInput"]::before {
    content: "⚡ GPAY STYLE SCANNER - ALIGN QR IN CENTER";
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.8);
    color: #FFD600;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 10px;
    border-radius: 20px;
    z-index: 15;
    pointer-events: none;
}
.qr-scan-container div[data-testid="stCameraInput"]::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(90deg, transparent, #FFD600, #FFFFFF, #FFD600, transparent);
    animation: scanline 1.8s ease-in-out infinite;
    z-index: 10;
    pointer-events: none;
    box-shadow: 0 0 12px #FFD600;
}
/* Face Scan Overlay styling */
.face-scan-container div[data-testid="stCameraInput"] {
    border: 3px solid #2979FF !important;
    border-radius: 50% !important;
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 25px rgba(41, 121, 255, 0.3);
}
.face-scan-container div[data-testid="stCameraInput"]::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 4px;
    background: linear-gradient(90deg, transparent, #2979FF, #FFFFFF, #2979FF, transparent);
    animation: scanline 2.8s ease-in-out infinite;
    z-index: 10;
    pointer-events: none;
}
@keyframes scanline {
    0% { top: 5%; opacity: 0.8; }
    50% { top: 95%; opacity: 1; }
    100% { top: 5%; opacity: 0.8; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Helper for Direct Camera Inputs with Live Focus/Sharpness Meter ────────────


def _render_image_input(
    label: str, key_prefix: str, scan_type: str = "doc"
) -> Optional[np.ndarray]:
    """Direct live camera scanner with autofocus overlay and real-time focus validation."""
    st.markdown(f'<div class="{scan_type}-scan-container">', unsafe_allow_html=True)
    cam_file = st.camera_input(f"📷 {label}", key=f"{key_prefix}_cam")
    st.markdown("</div>", unsafe_allow_html=True)

    img_arr = None
    if cam_file:
        pil = Image.open(cam_file).convert("RGB")
        img_arr = np.array(pil)[..., ::-1]

        from shared.quality_check import check_quality

        q = check_quality(img_arr)
        if q["acceptable"]:
            st.success(
                f"🟢 **In Focus & Sharp** (Sharpness Score: `{q['blur_score']:.1f}` | Optical Resolution: `{q['resolution'][0]}x{q['resolution'][1]}`px)"
            )
        else:
            st.warning(
                f"⚠️ **Focus Warning**: {', '.join(q['issues'])}. *Tap screen on the card to focus and snap steadily.*"
            )

    return img_arr


# ── Screening Pipeline Functions ──────────────────────────────────────────────


def _screen_aadhaar(front_img: np.ndarray, back_img: np.ndarray) -> dict:
    from modules.aadhaar.consistency import check_qr_ocr_consistency
    from modules.aadhaar.ocr import extract_aadhaar_fields
    from modules.aadhaar.qr import decode_aadhaar_qr
    from modules.aadhaar.signature import verify_uidai_signature
    from modules.aadhaar.verhoeff import verhoeff_validate
    from modules.forensics.ela import run_ela

    results = {}

    ocr = extract_aadhaar_fields(front_img)
    # Check back image for QR first; if not found, check front image
    qr = decode_aadhaar_qr(back_img)
    qr_img_source = "back"
    if qr.get("error") and front_img is not None:
        qr_front = decode_aadhaar_qr(front_img)
        if not qr_front.get("error"):
            qr = qr_front
            qr_img_source = "front"

    uid = ocr.get("uid") or qr.get("fields", {}).get("uid_last4", "")

    # 1. Verhoeff validation
    results["aadhaar_verhoeff"] = {
        "score": 1.0 if (uid and verhoeff_validate(uid)) else 0.0,
        "uid": uid,
    }

    # 2. Cryptographic signature check on QR and verification tier
    qr_region = None
    if not qr.get("error"):
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
        else:
            sig_result = verify_uidai_signature(
                qr.get("raw_payload", b""), qr.get("signature", b"")
            )
            is_valid = bool(sig_result and sig_result.get("valid"))
            verification_tier = "QR_VERIFIED"
            results["aadhaar_uidai_signature"] = {
                "score": 1.0 if is_valid else 0.0,
                "valid": is_valid,
                **(sig_result or {}),
                "verification_tier": "QR_VERIFIED",
            }

        # 3. Front OCR vs QR cross-check
        consistency = check_qr_ocr_consistency(qr.get("fields", {}), ocr)
        cons_flag = consistency.get("consistent")
        if cons_flag is True:
            cons_score = 1.0
        elif cons_flag is False:
            cons_score = 0.0
        else:
            cons_score = None  # uncertain / insufficient fields
        results["aadhaar_qr_ocr_consistency"] = {
            "score": cons_score,
            **consistency,
        }
    else:
        verification_tier = "QR_UNREADABLE"
        results["aadhaar_uidai_signature"] = {
            "score": None,
            "valid": None,
            "error": "QR code unreadable due to capture quality (glare, blur, or missing)",
            "verification_tier": "QR_UNREADABLE",
        }
        # Not a content mismatch — QR evidence unavailable
        results["aadhaar_qr_ocr_consistency"] = {
            "score": None,
            "consistent": None,
            "mismatches": [],
            "error": "qr_data_unavailable",
        }

    results["verification_tier"] = verification_tier
    results["expiry_valid"] = {"score": 1.0}  # Aadhaar has no expiry

    # 4. Forensics (Run ELA on both images)
    ela_front = run_ela(front_img)
    ela_back = run_ela(back_img)

    suspicious = bool(ela_front.get("suspicious") or ela_back.get("suspicious"))
    mean_var = max(
        float(ela_front.get("mean_variance", 0.0)),
        float(ela_back.get("mean_variance", 0.0)),
    )

    results["ela_full_document"] = {
        "score": 0.0 if suspicious else 1.0,
        "mean_variance": mean_var,
        "suspicious": suspicious,
        "heatmap": ela_front.get("heatmap"),  # Return front heatmap as display sample
    }

    if qr_region:
        qr_target_img = back_img if qr_img_source == "back" else front_img
        ela_reg = run_ela(qr_target_img, region=qr_region)
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
    from modules.passport.mrz import parse_mrz_from_image
    from modules.passport.passive_auth import authenticate_chip
    from modules.passport.viz import extract_viz_fields

    results = {}

    mrz = parse_mrz_from_image(bio_img)

    # 1. MRZ checksums
    if mrz and mrz.get("valid") is not None:
        results["passport_mrz_checksums"] = {
            "score": 1.0 if mrz["valid"] else 0.0,
            **mrz,
        }
        results["expiry_valid"] = {
            "score": 1.0 if mrz.get("fields", {}).get("expiry") else 1.0
        }
    else:
        results["passport_mrz_checksums"] = {
            "score": 0.0,
            "error": "MRZ parsing failed or missing",
        }
        results["expiry_valid"] = {"score": 1.0}

    # 2. Chip authenticity (simulated via passive auth module)
    chip_auth = authenticate_chip(mrz.get("fields", {}))
    results["passport_chip_authenticity"] = {
        "score": 1.0 if chip_auth.get("valid") else 0.0,
        **chip_auth,
    }

    # 3. MRZ vs VIZ consistency
    from modules.passport.viz import _get_reader

    cached_reader = _get_reader()
    viz = extract_viz_fields(bio_img, reader=cached_reader)
    if mrz and mrz.get("valid") and viz.get("fields"):
        consistency = check_mrz_viz_consistency(mrz["fields"], viz["fields"])
        results["passport_mrz_viz_consistency"] = {
            "score": 1.0 if consistency["consistent"] else 0.0,
            **consistency,
        }
    else:
        results["passport_mrz_viz_consistency"] = {
            "score": 0.0,
            "error": "MRZ or VIZ fields unavailable for cross-check",
        }

    # 4. Forensics
    ela = run_ela(bio_img)
    results["ela_full_document"] = {"score": 0.0 if ela["suspicious"] else 1.0, **ela}

    # Photo region ELA check (approximate passport photo region: top-left quadrant)
    h_sz, w_sz = bio_img.shape[:2]
    photo_region = (
        int(0.05 * w_sz),
        int(0.15 * h_sz),
        int(0.40 * w_sz),
        int(0.70 * h_sz),
    )
    results["ela_region_restricted"] = run_ela(bio_img, region=photo_region)

    results["_ocr"] = viz.get("fields", {})
    results["_mrz_fields"] = mrz.get("fields", {})

    pass_num = (mrz.get("fields", {}) or {}).get("passport_number") or (
        (viz.get("fields", {}) or {}).get("passport_number") or ""
    )
    p_name = (
        f"{(mrz.get('fields', {}) or {}).get('given_names', '')} {(mrz.get('fields', {}) or {}).get('surname', '')}".strip()
        or (viz.get("fields", {}) or {}).get("name", "")
    )
    results["_meta"] = {
        "doc_number": pass_num,
        "name": p_name,
    }

    return results


def _screen_visa(visa_img: np.ndarray, passport_img: np.ndarray) -> dict:
    from modules.forensics.ela import run_ela
    from modules.passport.mrz import parse_mrz_from_image
    from modules.visa.binding import verify_visa_passport_binding
    from modules.visa.ocr import extract_visa_fields
    from modules.visa.rules import validate_visa_rules

    results = {}

    from modules.visa.ocr import _get_reader

    cached_reader = _get_reader()
    visa_ocr = extract_visa_fields(visa_img, reader=cached_reader)
    visa_fields = visa_ocr.get("fields", {})

    # 1. Rule validation
    if visa_fields:
        rule_val = validate_visa_rules(visa_fields)
        results["visa_rule_validation"] = {
            "score": 1.0 if rule_val["valid"] else 0.0,
            **rule_val,
        }
    else:
        results["visa_rule_validation"] = {
            "score": 0.0,
            "error": "Visa OCR extraction returned no fields",
        }

    # 2. Visa-to-Passport binding
    pass_mrz = parse_mrz_from_image(passport_img)
    pass_fields = pass_mrz.get("fields", {}) if pass_mrz else {}

    if visa_fields and pass_fields:
        binding = verify_visa_passport_binding(visa_fields, pass_fields)
        results["visa_passport_binding"] = {
            "score": 1.0 if binding["bound"] else 0.0,
            **binding,
        }
        # Cross-field consistency
        results["visa_cross_field"] = {
            "score": 1.0 if not binding.get("mismatches") else 0.0,
            "mismatches": binding.get("mismatches", []),
        }
    else:
        results["visa_passport_binding"] = {
            "score": 0.0,
            "error": "Passport MRZ or Visa fields missing for binding check",
        }
        results["visa_cross_field"] = {
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
            "error": "Primary document scan quality is insufficient",
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
    if live_face_img is not None:
        from modules.face.embedder import get_embedding
        from modules.face.identity_graph import search_and_store
        from modules.face.match import match_face_to_document

        # Match against biographical page photo
        doc_face_img = inputs["front"] if doc_type == "AADHAAR" else inputs["bio"]

        face_result = match_face_to_document(doc_face_img, live_face_img, doc_type)
        check_results["face_match"] = face_result
        check_results["liveness"] = face_result.get("liveness", {"score": 0.0})

        live_emb = get_embedding(live_face_img)
        if live_emb is not None:
            doc_number = check_results.get("_meta", {}).get("doc_number") or ""
            name = check_results.get("_meta", {}).get("name") or ""
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
    check_results = results.get("check_results", {})
    verification_tier = check_results.get("verification_tier")

    if verification_tier == "QR_UNREADABLE" and risk in ("CLEAR", "REVIEW"):
        st.markdown(
            f"### Risk Level: :orange[**UNVERIFIED (LOW CONFIDENCE)**] &nbsp; Calculated Score: **{total:.0f}/100**"
        )
        st.warning(
            "⚠️ **POLICY ALERT: MANDATORY SECONDARY MANUAL INSPECTION REQUIRED**\n\n"
            "The QR code could not be cryptographically decoded due to capture quality (glare, blur, or missing QR). "
            "A clean printed fake with a fabricated checksum number cannot be authenticated without QR cryptographic validation. "
            "Policy requires mandatory physical inspection and camera recapture."
        )
    else:
        st.markdown(
            f"### Risk Level: :{color}[**{risk}**] &nbsp; Score: **{total:.0f}/100**"
        )

    # LLM summary
    st.info(f"💬 **Officer Summary**: {summary}")

    # Identity Graph Alert
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


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🛂 AI Document Screening System")
st.caption("Sashastra Seema Bal (SSB) | Ministry of Home Affairs | SIH 2026 - PS-6188")
st.divider()

# ── Top-Level Navigation Tabs ──────────────────────────────────────────────────
tab_screening, tab_qr_scanner = st.tabs(
    ["🛂 Full Document Screening", "⚡ Live GPay-Style QR Scanner"]
)

# ── Tab 1: Full Document Screening ─────────────────────────────────────────────

with tab_screening:
    # Document type selector
    doc_type = st.radio(
        "Select document type to screen:",
        ["AADHAAR", "PASSPORT", "VISA"],
        horizontal=True,
    )

    if st.session_state.last_doc_type != doc_type:
        st.session_state.last_doc_type = doc_type
        st.rerun()

    st.divider()

    col_input, col_results = st.columns([1, 1], gap="large")

    with col_input:
        st.subheader("📷 Document Capture")

        inputs = {}
        ready_to_screen = False

        if doc_type == "AADHAAR":
            st.info(
                "Aadhaar requires scanning front (photo side) and back (secure QR/address side)."
            )

            # Front scan
            st.markdown("#### 1. Aadhaar Front (Photo & UID)")
            front_img = _render_image_input("Aadhaar Front", "front", "doc")
            if front_img is not None:
                inputs["front"] = front_img

            # Back scan
            st.markdown("#### 2. Aadhaar Back (Secure QR Code)")
            back_img = _render_image_input("Aadhaar Back", "back", "doc")
            if back_img is not None:
                inputs["back"] = back_img

            ready_to_screen = "front" in inputs and "back" in inputs

        elif doc_type == "PASSPORT":
            st.info(
                "Scan the main biographical data page (containing MRZ lines at bottom)."
            )

            # Bio page
            st.markdown("#### 1. Passport Biographical Page")
            bio_img = _render_image_input("Passport Bio Page", "bio", "doc")
            if bio_img is not None:
                inputs["bio"] = bio_img

            # Optional extra page
            st.markdown("#### 2. Secondary / Cover Page (Optional)")
            extra_img = _render_image_input("Secondary Page", "extra", "doc")
            if extra_img is not None:
                inputs["extra"] = extra_img

            ready_to_screen = "bio" in inputs

        elif doc_type == "VISA":
            st.info(
                "Scan the Visa sticker, plus traveler's passport biographical page for binding."
            )

            # Visa stamp
            st.markdown("#### 1. Visa Stamp / Sticker")
            visa_img = _render_image_input("Visa Stamp", "visa", "doc")
            if visa_img is not None:
                inputs["visa"] = visa_img

            # Passport bio for binding
            st.markdown("#### 2. Passport Bio Page")
            pass_img = _render_image_input("Passport Page", "pass", "doc")
            if pass_img is not None:
                inputs["passport"] = pass_img

            ready_to_screen = "visa" in inputs and "passport" in inputs

        st.divider()

        # Live face capture
        st.subheader("🤳 Traveler Live Face Verification")
        st.caption("Captures live selfie to match against document photo and verify liveness.")
        live_face = _render_image_input("Traveler Face Capture", "live_face", "face")

    with col_results:
        st.subheader("📊 Screening Results")

        if ready_to_screen:
            with st.spinner("Running deep document verification..."):
                results = _run_screening(doc_type, inputs, live_face)

            _display_results(results)
        else:
            st.info("Complete the camera scans on the left to begin screening.")


# ── Tab 2: Dedicated Live GPay-Style QR Scanner & UIDAI Verifier ──────────────

with tab_qr_scanner:
    st.subheader("⚡ Live GPay-Style QR Code Scanner & UIDAI Verifier")
    st.caption(
        "Point your camera directly at the QR code (front or back of Aadhaar) to automatically decode demographics and verify UIDAI RSA-2048 offline cryptographic signatures."
    )

    col_q1, col_q2 = st.columns([1, 1], gap="large")

    with col_q1:
        st.markdown("#### 📷 Live QR Viewfinder")
        qr_input_img = _render_image_input(
            "Align QR Code in Center Frame", "standalone_qr", "qr"
        )

    with col_q2:
        st.markdown("#### Cryptographic & Demographic Results")
        if qr_input_img is not None:
            with st.spinner("Decoding QR code and verifying digital signature..."):
                from modules.aadhaar.qr import decode_aadhaar_qr
                from modules.aadhaar.signature import verify_uidai_signature

                qr_res = decode_aadhaar_qr(qr_input_img)

                if qr_res.get("error"):
                    st.error(f"❌ {qr_res['error']}")
                    st.info(
                        "💡 *Tip: Ensure the entire square QR code is in frame, well lit, and free of plastic reflections.*"
                    )
                else:
                    format_type = qr_res.get("format", "unknown").upper()
                    st.success(f"✅ **QR Code Detected**: Format `{format_type}`")

                    # Verify UIDAI signature
                    sig_res = verify_uidai_signature(
                        qr_res["raw_payload"], qr_res["signature"]
                    )
                    if sig_res.get("valid"):
                        st.success(
                            "🔒 **UIDAI Cryptographic Signature: VALID** (Authentic government-issued QR code)"
                        )
                    else:
                        st.error(
                            f"⚠️ **UIDAI Cryptographic Signature: INVALID** ({sig_res.get('error', 'Tampered payload')})"
                        )

                    st.divider()
                    st.markdown("##### 👤 Decoded Demographics (from Signed Payload)")
                    fields = qr_res.get("fields", {})
                    if fields:
                        for k, v in fields.items():
                            if v:
                                st.markdown(f"**{k.replace('_', ' ').title()}**: `{v}`")
                    else:
                        st.info("No text fields decoded from QR payload.")
        else:
            st.info("Scan a QR code using the camera on the left to view decoded results.")
