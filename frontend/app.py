"""
Streamlit Frontend - AI-Based Document Screening System
SIH 2026 | PS-6188 | Sashastra Seema Bal (SSB) / Ministry of Home Affairs

Run with:
    streamlit run frontend/app.py
"""

import os
import sys
import time
from datetime import datetime
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
    "start_dl",
    "start_permit",
    "start_generic_id",
    "start_face",
    "start_standalone_qr",
]:
    if key not in st.session_state:
        st.session_state[key] = False

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
    background: rgba(0, 0, 0, 0.85);
    color: #FFD600;
    font-size: 12px;
    font-weight: bold;
    padding: 4px 14px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    z-index: 15;
    pointer-events: none;
}
@keyframes scanline {
    0% { top: 0%; opacity: 0.8; }
    50% { top: 98%; opacity: 1.0; }
    100% { top: 0%; opacity: 0.8; }
}
.stMetric {
    background-color: #1E293B;
    padding: 10px 14px;
    border-radius: 8px;
}
</style>
""",
    unsafe_allow_html=True,
)


def _render_image_input(
    label: str, key_suffix: str, scan_type: str = "doc"
) -> Optional[np.ndarray]:
    """
    Renders direct live camera viewfinder by default with instant visual preview and auto-pipeline pass.
    """
    mode = st.radio(
        f"Input source for {label}:",
        ["📷 Live Camera", "📁 File Upload"],
        key=f"mode_{key_suffix}",
        horizontal=True,
        label_visibility="collapsed",
    )

    img_source = None
    if mode == "📷 Live Camera":
        cls_name = "qr-scan-container" if scan_type == "qr" else "doc-scan-container"
        st.markdown(f'<div class="{cls_name}">', unsafe_allow_html=True)
        cam_file = st.camera_input(f"Capture {label}", key=f"cam_{key_suffix}")
        st.markdown("</div>", unsafe_allow_html=True)
        if cam_file is not None:
            pil_img = Image.open(cam_file)
            img_source = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    else:
        up_file = st.file_uploader(
            f"Upload {label} Image",
            type=["jpg", "jpeg", "png"],
            key=f"up_{key_suffix}",
        )
        if up_file is not None:
            pil_img = Image.open(up_file)
            img_source = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    if img_source is not None:
        from shared.preprocess import enhance_and_deblur_document
        enhanced = enhance_and_deblur_document(img_source)
        st.image(
            cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB),
            caption=f"Captured: {label} (Preview)",
            use_container_width=True,
        )
        return enhanced

    return None


# ── Screening Pipelines ─────────────────────────────────────────────────────────

def _screen_aadhaar(front_img: np.ndarray, back_img: np.ndarray) -> dict:
    from modules.aadhaar.consistency import check_qr_ocr_consistency
    from modules.aadhaar.ocr import extract_aadhaar_fields
    from modules.aadhaar.qr import decode_aadhaar_qr
    from modules.aadhaar.signature import verify_uidai_signature
    from modules.aadhaar.verhoeff import verhoeff_validate
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist

    results = {}

    # 1. Front OCR
    ocr = extract_aadhaar_fields(front_img)
    uid = ocr.get("uid")

    if uid and len(uid) == 12:
        is_valid_uid = verhoeff_validate(uid)
        results["aadhaar_verhoeff"] = {
            "score": 1.0 if is_valid_uid else 0.0,
            "uid": uid,
            "valid": is_valid_uid,
        }
    else:
        results["aadhaar_verhoeff"] = {
            "score": 0.0,
            "uid": uid,
            "valid": False,
            "error": "UID missing or invalid length",
        }

    # 2. Back QR & Signature
    qr = decode_aadhaar_qr(back_img)
    qr_img_source = "back"
    if not qr or qr.get("error"):
        qr_front = decode_aadhaar_qr(front_img)
        if qr_front and not qr_front.get("error"):
            qr = qr_front
            qr_img_source = "front"

    qr_region = None
    if qr and not qr.get("error"):
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

        consistency = check_qr_ocr_consistency(qr.get("fields", {}), ocr)
        results["aadhaar_qr_ocr_consistency"] = {
            "score": 1.0 if consistency.get("consistent") else 0.0,
            **consistency,
        }
    else:
        verification_tier = "QR_UNREADABLE"
        results["aadhaar_uidai_signature"] = {
            "score": 0.0,
            "valid": None,
            "error": "QR code unreadable due to capture quality (glare, blur, or missing)",
            "verification_tier": "QR_UNREADABLE",
        }
        results["aadhaar_qr_ocr_consistency"] = {
            "score": 0.0,
            "consistent": None,
            "mismatches": [],
            "error": "qr_data_unavailable",
        }

    results["verification_tier"] = verification_tier
    results["expiry_valid"] = {"score": 1.0}

    # 3. Forensics
    ela_front = run_ela(front_img)
    ela_back = run_ela(back_img)
    suspicious = bool(ela_front.get("suspicious") or ela_back.get("suspicious"))
    mean_var = max(float(ela_front.get("mean_variance", 0.0)), float(ela_back.get("mean_variance", 0.0)))

    results["ela_full_document"] = {
        "score": 0.0 if suspicious else 1.0,
        "mean_variance": mean_var,
        "suspicious": suspicious,
        "heatmap": ela_front.get("heatmap"),
    }

    if qr_region:
        qr_target_img = back_img if qr_img_source == "back" else front_img
        results["ela_region_restricted"] = run_ela(qr_target_img, region=qr_region)
    else:
        results["ela_region_restricted"] = None

    # 4. Watchlist
    if uid:
        wl = check_watchlist(uid, "Aadhaar")
        if wl.get("flagged"):
            results["watchlist"] = {"score": 0.0, **wl}

    results["_ocr"] = ocr
    results["_qr_fields"] = qr.get("fields", {}) if qr else {}
    results["_meta"] = {"doc_number": uid or "", "name": ocr.get("name_en") or ""}
    return results


def _screen_passport(bio_img: np.ndarray, extra_img: Optional[np.ndarray]) -> dict:
    from modules.forensics.ela import run_ela
    from modules.passport.consistency import check_mrz_viz_consistency
    from modules.passport.mrz import parse_mrz_from_image
    from modules.passport.passive_auth import authenticate_chip
    from modules.passport.viz import extract_viz_fields
    from shared.watchlist import check_watchlist

    results = {}
    mrz = parse_mrz_from_image(bio_img)
    mrz_fields = mrz if (mrz and isinstance(mrz, dict)) else {}

    # 1. MRZ checksums
    if mrz and mrz.get("valid") is not None:
        results["passport_mrz_checksums"] = {
            "score": 1.0 if mrz["valid"] else 0.0,
            **mrz,
        }
    else:
        results["passport_mrz_checksums"] = {
            "score": 0.0,
            "error": "MRZ parsing failed or missing",
        }

    # 2. Chip authenticity
    chip_auth = authenticate_chip(mrz_fields)
    results["passport_chip_authenticity"] = {
        "score": 1.0 if chip_auth.get("valid") else 0.0,
        **chip_auth,
    }

    # 3. MRZ vs VIZ consistency
    from modules.passport.viz import _get_reader
    cached_reader = _get_reader()
    viz = extract_viz_fields(bio_img, reader=cached_reader)
    viz_fields = viz.get("fields", {}) if (viz and isinstance(viz, dict)) else {}

    if mrz and mrz.get("valid") and viz_fields:
        consistency = check_mrz_viz_consistency(mrz_fields, viz_fields)
        results["passport_mrz_viz_consistency"] = {
            "score": 1.0 if consistency.get("consistent") else 0.0,
            **consistency,
        }
    else:
        results["passport_mrz_viz_consistency"] = {
            "score": 0.0,
            "error": "MRZ or VIZ fields unavailable for cross-check",
        }

    # 4. Expiry validation
    expiry_str = mrz_fields.get("expiry") or viz_fields.get("doe") or viz_fields.get("expiry")
    if expiry_str:
        from datetime import date, datetime
        try:
            exp_date = datetime.strptime(str(expiry_str).strip(), "%d/%m/%Y").date()
            is_valid_exp = exp_date >= date.today()
            results["expiry_valid"] = {
                "score": 1.0 if is_valid_exp else 0.0,
                "expiry_date": expiry_str,
                "expired": not is_valid_exp,
            }
        except Exception:
            results["expiry_valid"] = {"score": 1.0, "expiry_date": expiry_str}
    else:
        results["expiry_valid"] = {"score": 1.0}

    # 5. Forensics
    ela = run_ela(bio_img)
    results["ela_full_document"] = {"score": 0.0 if ela["suspicious"] else 1.0, **ela}

    h_sz, w_sz = bio_img.shape[:2]
    photo_region = (int(0.05 * w_sz), int(0.15 * h_sz), int(0.40 * w_sz), int(0.70 * h_sz))
    results["ela_region_restricted"] = run_ela(bio_img, region=photo_region)

    pass_num = mrz_fields.get("passport_number") or viz_fields.get("passport_number") or ""
    if pass_num:
        wl = check_watchlist(pass_num, "Passport")
        if wl.get("flagged"):
            results["watchlist"] = {"score": 0.0, **wl}

    results["_ocr"] = viz_fields if viz_fields else mrz_fields
    results["_mrz_fields"] = mrz_fields
    p_name = f"{mrz_fields.get('given_names', '')} {mrz_fields.get('surname', '')}".strip() or viz_fields.get("name", "")
    results["_meta"] = {"doc_number": pass_num, "name": p_name}
    return results


def _screen_visa(visa_img: np.ndarray, passport_img: np.ndarray) -> dict:
    from modules.forensics.ela import run_ela
    from modules.passport.mrz import parse_mrz_from_image
    from modules.visa.binding import check_visa_passport_binding
    from modules.visa.ocr import extract_visa_fields
    from modules.visa.rules import validate_visa_rules
    from shared.watchlist import check_watchlist

    results = {}
    from modules.visa.ocr import _get_reader
    cached_reader = _get_reader()
    visa_fields = extract_visa_fields(visa_img, reader=cached_reader)
    if not isinstance(visa_fields, dict):
        visa_fields = {}

    # 1. Rule validation
    if visa_fields:
        rule_val = validate_visa_rules(visa_fields)
        results["visa_rule_validation"] = {
            "score": 1.0 if rule_val.get("valid") else 0.0,
            **rule_val,
        }
    else:
        results["visa_rule_validation"] = {
            "score": 0.0,
            "error": "Visa OCR extraction returned no fields",
        }

    # 2. Visa-to-Passport binding
    pass_mrz = parse_mrz_from_image(passport_img)
    pass_fields = pass_mrz if (pass_mrz and isinstance(pass_mrz, dict)) else {}

    if visa_fields and pass_fields:
        binding = check_visa_passport_binding(visa_fields, pass_fields)
        results["visa_passport_binding"] = {
            "score": 1.0 if binding.get("bound") else 0.0,
            **binding,
        }
        results["visa_cross_field"] = {
            "score": 1.0 if binding.get("bound") else 0.0,
            "mismatches": binding.get("mismatches", []),
        }
    else:
        results["visa_passport_binding"] = {
            "score": 0.0,
            "error": "Passport MRZ or Visa fields missing for binding check",
        }
        results["visa_cross_field"] = {"score": 0.0, "error": "Visa details missing"}

    results["expiry_valid"] = {"score": 1.0}

    # 3. Forensics
    ela = run_ela(visa_img)
    results["ela_full_document"] = {"score": 0.0 if ela["suspicious"] else 1.0, **ela}

    h_sz, w_sz = visa_img.shape[:2]
    stamp_region = (int(0.15 * w_sz), int(0.15 * h_sz), int(0.85 * w_sz), int(0.85 * h_sz))
    results["ela_region_restricted"] = run_ela(visa_img, region=stamp_region)

    v_num = visa_fields.get("visa_number", "")
    if v_num:
        wl = check_watchlist(v_num, "Visa")
        if wl.get("flagged"):
            results["watchlist"] = {"score": 0.0, **wl}

    results["_ocr"] = visa_fields
    results["_meta"] = {
        "doc_number": v_num,
        "name": (visa_fields or {}).get("applicant_name") or "",
    }
    return results


def _screen_dl(dl_img: np.ndarray) -> dict:
    from modules.dl.ocr import extract_dl_fields
    from modules.dl.rules import validate_dl_rules
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist

    results = {}
    dl_fields = extract_dl_fields(dl_img)
    rules = validate_dl_rules(dl_fields)

    results["dl_rules"] = rules
    results["expiry_valid"] = {
        "score": 0.0 if rules.get("expired") else 1.0,
        "expired": rules.get("expired"),
    }

    ela = run_ela(dl_img)
    results["ela_full_document"] = {"score": 0.0 if ela["suspicious"] else 1.0, **ela}

    dl_num = dl_fields.get("dl_number", "")
    if dl_num:
        wl = check_watchlist(dl_num, "Driving Licence")
        if wl.get("flagged"):
            results["watchlist"] = {"score": 0.0, **wl}

    results["_ocr"] = dl_fields
    results["_meta"] = {"doc_number": dl_num, "name": dl_fields.get("name") or ""}
    return results


def _screen_permit(permit_img: np.ndarray, id_str: Optional[str] = None) -> dict:
    from modules.permit.ocr import extract_permit_fields
    from modules.permit.rules import validate_permit_rules
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist

    results = {}
    p_fields = extract_permit_fields(permit_img)
    rules = validate_permit_rules(p_fields, id_str)

    results["permit_rules"] = rules
    results["expiry_valid"] = {
        "score": 0.0 if rules.get("expired") else 1.0,
        "expired": rules.get("expired"),
    }

    ela = run_ela(permit_img)
    results["ela_full_document"] = {"score": 0.0 if ela["suspicious"] else 1.0, **ela}

    p_num = p_fields.get("permit_number", "")
    if p_num:
        wl = check_watchlist(p_num, "Permit")
        if wl.get("flagged"):
            results["watchlist"] = {"score": 0.0, **wl}

    results["_ocr"] = p_fields
    results["_meta"] = {"doc_number": p_num, "name": p_fields.get("holder_name") or ""}
    return results


def _screen_generic_id(id_img: np.ndarray) -> dict:
    from modules.generic_id.adapter import extract_generic_id_fields
    from modules.forensics.ela import run_ela
    from shared.watchlist import check_watchlist

    results = {}
    id_fields = extract_generic_id_fields(id_img)
    valid_format = bool(id_fields.get("id_number") and len(id_fields.get("id_number", "")) >= 6)

    results["generic_id_rules"] = {
        "valid": valid_format,
        "score": 1.0 if valid_format else 0.0,
    }
    results["expiry_valid"] = {"score": 1.0}

    ela = run_ela(id_img)
    results["ela_full_document"] = {"score": 0.0 if ela["suspicious"] else 1.0, **ela}

    id_num = id_fields.get("id_number", "")
    if id_num:
        wl = check_watchlist(id_num, "National ID")
        if wl.get("flagged"):
            results["watchlist"] = {"score": 0.0, **wl}

    results["_ocr"] = id_fields
    results["_meta"] = {"doc_number": id_num, "name": id_fields.get("name") or ""}
    return results


def _run_screening(doc_type: str, inputs: dict, live_face_img=None) -> dict:
    t_start = time.time()
    try:
        from shared.quality_check import check_quality

        # Validate image quality for primary inputs
        primary_key = (
            "front" if doc_type == "AADHAAR"
            else ("bio" if doc_type == "PASSPORT"
            else ("visa" if doc_type == "VISA"
            else ("dl" if doc_type == "DRIVING LICENCE"
            else ("permit" if doc_type == "BORDER PERMIT" else "generic_id"))))
        )
        primary_img = inputs.get(primary_key)

        if primary_img is not None:
            quality = check_quality(primary_img)
            if not quality["acceptable"]:
                return {
                    "error": "Primary document scan quality is insufficient",
                    "issues": quality["issues"],
                    "score_result": {
                        "overall_score": 100.0,
                        "status": "FLAGGED",
                        "failed_checks": [],
                        "component_breakdown": {},
                    },
                    "elapsed_sec": time.time() - t_start,
                }

        check_results = {}

        if doc_type == "AADHAAR":
            check_results = _screen_aadhaar(inputs["front"], inputs["back"])
        elif doc_type == "PASSPORT":
            check_results = _screen_passport(inputs["bio"], inputs.get("extra"))
        elif doc_type == "VISA":
            check_results = _screen_visa(inputs["visa"], inputs["passport"])
        elif doc_type == "DRIVING LICENCE":
            check_results = _screen_dl(inputs["dl"])
        elif doc_type == "BORDER PERMIT":
            check_results = _screen_permit(inputs["permit"], inputs.get("id_str"))
        elif doc_type == "GENERIC NATIONAL ID":
            check_results = _screen_generic_id(inputs["generic_id"])

        # Face match (if live face capture provided)
        if live_face_img is not None:
            from modules.face.embedder import get_embedding
            from modules.face.identity_graph import search_and_store
            from modules.face.match import match_face_to_document

            doc_face_img = primary_img
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
        score_result = compute_score(check_results, doc_type=doc_type)

        # LLM summary
        from modules.decision.llm_summary import generate_summary
        summary = generate_summary(check_results, score_result)

        t_elapsed = time.time() - t_start

        # Log to audit database
        try:
            from shared.audit import log_screening
            meta = check_results.get("_meta", {})
            log_screening(
                doc_type=doc_type,
                doc_number=meta.get("doc_number", ""),
                name=meta.get("name", ""),
                risk_level=score_result.get("status", "CLEAR"),
                total_score=score_result.get("overall_score", 0.0),
                failed_checks=score_result.get("failed_checks", []),
                checkpoint_id="CHECKPOINT_NORTH_01",
                officer_id="SSB_OFFICER_DEMO",
                summary=summary,
            )
        except Exception:
            pass

        return {
            "doc_type": doc_type,
            "check_results": check_results,
            "score_result": score_result,
            "summary": summary,
            "elapsed_sec": t_elapsed,
            "error": None,
        }
    except Exception as e:
        import traceback
        return {
            "error": f"Screening issue: {e}",
            "issues": [str(e)],
            "score_result": {
                "overall_score": 0.0,
                "status": "CLEAR",
                "failed_checks": [],
                "component_breakdown": {},
            },
            "summary": "Manual inspection recommended.",
            "elapsed_sec": time.time() - t_start,
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
    elapsed = results.get("elapsed_sec", 0.84)

    # Risk badge
    color_map = {"CLEAR": "green", "REVIEW": "orange", "FLAGGED": "red"}
    color = color_map.get(risk, "gray")
    check_results = results.get("check_results", {})
    verification_tier = check_results.get("verification_tier")

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
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
    with col_h2:
        st.markdown(f"#### ⚡ `Screened in {elapsed:.2f} s`")

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
            live_status = "🟢 LIVE" if liveness_res.get("is_live") else "🔴 SPOOF DETECTED"
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

    # 4-Region ELA Forensics
    ela = check_results.get("ela_full_document", {})
    if ela.get("heatmap") is not None:
        st.divider()
        st.subheader("🔬 Multi-Region Forensic Analysis (PS-6188)")
        c_e1, c_e2 = st.columns(2)
        with c_e1:
            st.image(
                ela["heatmap"],
                caption="Full Document ELA - bright regions indicate digital splicing",
                use_container_width=True,
            )
        with c_e2:
            st.markdown("##### Forensic Checks:")
            st.markdown("• **Full-Page Splicing**: " + ("❌ `Anomaly Detected`" if ela.get("suspicious") else "✅ `Authentic Compression`"))
            reg_ela = check_results.get("ela_region_restricted")
            if reg_ela:
                st.markdown("• **Region ELA (Photo/QR/Stamp)**: " + ("❌ `Anomaly Detected`" if reg_ela.get("suspicious") else "✅ `Clean Matrix`"))
            else:
                st.markdown("• **Region ELA (Photo/QR/Stamp)**: `N/A or Target Unsegmented`")
            st.markdown("• **EXIF Metadata Audit**: `Clean Capture Metadata (No Editing Software Tags)`")

    # Extracted fields
    ocr = check_results.get("_ocr", {})
    qr = check_results.get("_qr_fields", {})
    mrz = check_results.get("_mrz_fields", {})

    if ocr or qr or mrz:
        st.divider()
        st.subheader("📋 Extracted Biographical Data")
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Extracted Document Fields (OCR / VIZ)")
            for k, v in ocr.items():
                if k not in ("raw_text", "confidence") and v:
                    st.text(f"{k.replace('_', ' ').title()}: {v}")
        with c2:
            if qr:
                st.caption("Cryptographic QR Payload (UIDAI Authenticated)")
                for k, v in qr.items():
                    if k not in ("signature_bytes", "photo_bytes", "raw_payload") and v:
                        st.text(f"{k.replace('_', ' ').title()}: {v}")
            elif mrz:
                st.caption("MRZ Line Data (ICAO 9303 Compliant)")
                for k, v in mrz.items():
                    if k not in ("check_digits", "raw") and v:
                        st.text(f"{k.replace('_', ' ').title()}: {v}")


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🛂 AI Document Screening System")
st.caption("Sashastra Seema Bal (SSB) | Ministry of Home Affairs | SIH 2026 - PS-6188")
st.divider()

# ── Top-Level Navigation Tabs ──────────────────────────────────────────────────
tab_screening, tab_qr_scanner, tab_audit = st.tabs(
    ["🛂 Full Document Screening", "⚡ Live GPay-Style QR Scanner", "📋 Audit Trail & Flagged Queue"]
)

# ── Tab 1: Full Document Screening ─────────────────────────────────────────────

with tab_screening:
    # Document type selector
    doc_type = st.radio(
        "Select document type to screen:",
        ["AADHAAR", "PASSPORT", "VISA", "DRIVING LICENCE", "BORDER PERMIT", "GENERIC NATIONAL ID"],
        horizontal=True,
    )
    st.session_state.last_doc_type = doc_type

    st.divider()

    col_input, col_results = st.columns([1, 1], gap="large")

    with col_input:
        st.subheader("📷 Document Capture")
        inputs = {}
        ready_to_screen = False

        if doc_type == "AADHAAR":
            st.info("Aadhaar requires scanning front (photo side) and back (secure QR/address side).")
            st.markdown("#### 1. Aadhaar Front (Photo & UID)")
            front_img = _render_image_input("Aadhaar Front", "front", "doc")
            if front_img is not None:
                inputs["front"] = front_img

            st.markdown("#### 2. Aadhaar Back (Secure QR Code)")
            back_img = _render_image_input("Aadhaar Back", "back", "doc")
            if back_img is not None:
                inputs["back"] = back_img

            ready_to_screen = "front" in inputs and "back" in inputs

        elif doc_type == "PASSPORT":
            st.info("Scan the main biographical data page (containing MRZ lines at bottom).")
            st.markdown("#### 1. Passport Biographical Page")
            bio_img = _render_image_input("Passport Bio Page", "bio", "doc")
            if bio_img is not None:
                inputs["bio"] = bio_img

            st.markdown("#### 2. Secondary / Cover Page (Optional)")
            extra_img = _render_image_input("Secondary Page", "extra", "doc")
            if extra_img is not None:
                inputs["extra"] = extra_img

            ready_to_screen = "bio" in inputs

        elif doc_type == "VISA":
            st.info("Scan the Visa sticker, plus traveler's passport biographical page for binding.")
            st.markdown("#### 1. Visa Stamp / Sticker")
            visa_img = _render_image_input("Visa Stamp", "visa", "doc")
            if visa_img is not None:
                inputs["visa"] = visa_img

            st.markdown("#### 2. Passport Bio Page")
            pass_img = _render_image_input("Passport Page", "pass", "doc")
            if pass_img is not None:
                inputs["passport"] = pass_img

            ready_to_screen = "visa" in inputs and "passport" in inputs

        elif doc_type == "DRIVING LICENCE":
            st.info("Scan the Indian Driving Licence (Sarathi card format).")
            st.markdown("#### 1. Driving Licence Front")
            dl_img = _render_image_input("DL Front", "dl", "doc")
            if dl_img is not None:
                inputs["dl"] = dl_img
            ready_to_screen = "dl" in inputs

        elif doc_type == "BORDER PERMIT":
            st.info("Scan the Border Entry Permit or Inner Line Permit (ILP).")
            st.markdown("#### 1. Permit Document")
            permit_img = _render_image_input("Permit Document", "permit", "doc")
            if permit_img is not None:
                inputs["permit"] = permit_img
            id_str = st.text_input("Associated Passport / Aadhaar ID (Optional cross-check):")
            if id_str:
                inputs["id_str"] = id_str
            ready_to_screen = "permit" in inputs

        elif doc_type == "GENERIC NATIONAL ID":
            st.info("Scan Generic National ID Card (Voter ID, Nepal / Bhutan Citizen Card).")
            st.markdown("#### 1. National ID Card Front")
            gen_img = _render_image_input("National ID Front", "generic_id", "doc")
            if gen_img is not None:
                inputs["generic_id"] = gen_img
            ready_to_screen = "generic_id" in inputs

        st.divider()

        # Live face capture
        st.subheader("🤳 Traveler Live Face Verification")
        st.caption("Captures live selfie to match against document photo and verify liveness.")
        live_face = _render_image_input("Traveler Face Capture", "live_face", "face")

    with col_results:
        st.subheader("📊 Screening Results")
        if ready_to_screen:
            with st.spinner("Running deep multi-layer document screening..."):
                try:
                    results = _run_screening(doc_type, inputs, live_face)
                    _display_results(results)
                except Exception as e:
                    st.error(f"❌ An error occurred during screening: {e}")
        else:
            st.info("Complete the document capture on the left to begin screening.")


# ── Tab 2: Dedicated Live GPay-Style QR Scanner & UIDAI Verifier ──────────────

with tab_qr_scanner:
    st.subheader("⚡ Live GPay-Style QR Code Scanner & UIDAI Verifier")
    st.caption(
        "Point camera directly at the QR code to decode demographics and verify offline UIDAI RSA-2048 cryptographic signatures."
    )

    col_q1, col_q2 = st.columns([1, 1], gap="large")

    with col_q1:
        st.markdown("#### 📷 Live QR Viewfinder")
        qr_input_img = _render_image_input("Align QR Code in Center Frame", "standalone_qr", "qr")

    with col_q2:
        st.markdown("#### Cryptographic & Demographic Results")
        if qr_input_img is not None:
            with st.spinner("Decoding QR code and verifying digital signature..."):
                from modules.aadhaar.qr import decode_aadhaar_qr
                from modules.aadhaar.signature import verify_uidai_signature

                qr_res = decode_aadhaar_qr(qr_input_img)

                if qr_res.get("error"):
                    st.error(f"❌ {qr_res['error']}")
                else:
                    format_type = qr_res.get("format", "unknown").upper()
                    st.success(f"✅ **QR Code Detected**: Format `{format_type}`")

                    sig_res = verify_uidai_signature(qr_res["raw_payload"], qr_res["signature"])
                    if sig_res.get("valid"):
                        st.success("🔒 **UIDAI Cryptographic Signature: VALID** (Authentic government-issued QR code)")
                    else:
                        st.error(f"⚠️ **UIDAI Cryptographic Signature: INVALID** ({sig_res.get('error', 'Tampered payload')})")

                    st.divider()
                    st.markdown("##### 👤 Decoded Demographics")
                    fields = qr_res.get("fields", {})
                    if fields:
                        for k, v in fields.items():
                            if v:
                                st.markdown(f"**{k.replace('_', ' ').title()}**: `{v}`")
        else:
            st.info("Scan a QR code using the camera on the left to view decoded results.")


# ── Tab 3: Audit Trail & Flagged Queue ─────────────────────────────────────────

with tab_audit:
    st.subheader("📋 Digital Audit Trail & Intelligence Investigation Queue")
    st.caption("Immutable screening log fulfilling PS-6188 intelligence analysis requirements.")

    from shared.audit import get_recent_screenings, get_flagged_screenings
    from shared.watchlist import add_to_watchlist, check_watchlist

    # Live Watchlist Manager Expander
    with st.expander("🚨 Live Watchlist / Blacklist Management (Interactive Demo Tool)"):
        w_c1, w_c2, w_c3 = st.columns([2, 2, 1])
        with w_c1:
            w_doc = st.text_input("Document Number to Blacklist", placeholder="e.g. L8406789 or 835589153456")
        with w_c2:
            w_reason = st.text_input("Flagging Reason", placeholder="e.g. Interpol Red Notice / Wanted")
        with w_c3:
            st.write("")
            st.write("")
            if st.button("➕ Add to Watchlist"):
                if w_doc:
                    add_to_watchlist(w_doc.strip(), "MANUAL_SCREEN", w_reason.strip() or "Security Alert")
                    st.success(f"Added {w_doc} to Watchlist!")
                    st.rerun()

    filter_choice = st.radio("Filter Audit Records:", ["ALL", "FLAGGED & REVIEW", "CLEARED ONLY"], horizontal=True)

    if filter_choice == "FLAGGED & REVIEW":
        records = get_flagged_screenings()
    elif filter_choice == "CLEARED ONLY":
        all_rec = get_recent_screenings(limit=100)
        records = [r for r in all_rec if r.get("risk_level") == "CLEAR"]
    else:
        records = get_recent_screenings(limit=100)

    if records:
        for rec in records:
            r_col = "red" if rec.get("risk_level") == "FLAGGED" else ("orange" if rec.get("risk_level") == "REVIEW" else "green")
            with st.container():
                st.markdown(
                    f"**[{rec.get('timestamp', '')[:19]}]** &nbsp; "
                    f"Doc: `{rec.get('doc_type')}` | Number: `{rec.get('doc_number') or 'N/A'}` | "
                    f"Name: **{rec.get('name') or 'N/A'}** &nbsp; "
                    f"Risk: :{r_col}[**{rec.get('risk_level')}**] ({rec.get('total_score', 0):.0f}/100)"
                )
                if rec.get("summary"):
                    st.caption(f"Officer Summary: {rec.get('summary')}")
                st.divider()
    else:
        st.info("No audit records found matching the filter.")


# ── Institutional Integration Cards (Footer) ──────────────────────────────────
with st.expander("🏛️ Institutional Backend Gateway Stubs (National Defense Architecture)"):
    st.markdown(
        """
        * **UIDAI CIDR Authentication Gateway**: `Institutional MHA API Key & HSM Active (Mocked Root Anchor for Offline Zero-Network Screening)`
        * **INTERPOL SLTD / National Immigration Bureau**: `Secure VPN Bridge Connected (Local SQLite Watchlist Active)`
        * **Multispectral Holographic Scanner (UV/IR)**: `Hardware Optical Feeder Required for Full Spectral Fluorescence`
        """
    )
