"""
Decision Scorer - Risk assessment calculations.

This module computes the final risk score based on checksum validation,
signature verification, cross field consistency and ELA forensics.
"""

from typing import Any, Optional

# ELA normalization threshold constant.
# This value was tuned against sample_data to separate authentic images
# from spliced regions.
ELA_NORMALIZATION_THRESHOLD = 15.0


def compute_score(
    check_results: dict[str, Any], doc_type: Optional[str] = None
) -> dict:
    """
    Compute the risk score (0 to 100) based on checked fields.

    Higher score means higher risk.
    """
    # Infer doc_type if not provided explicitly
    if not doc_type:
        if (
            "visa_rule_validation" in check_results
            or "visa_passport_binding" in check_results
        ):
            doc_type = "VISA"
        elif (
            "passport_mrz_checksums" in check_results
            or "passport_mrz_viz_consistency" in check_results
        ):
            doc_type = "PASSPORT"
        else:
            doc_type = "AADHAAR"

    doc_type = doc_type.upper()

    # Common ELA Anomaly calculation (shared across all document types)
    ela_variance = 0.0
    ela_res = check_results.get("ela_full_document")
    if isinstance(ela_res, dict):
        ela_variance = float(ela_res.get("mean_variance", 0.0))
    elif "ela_region_restricted" in check_results:
        reg_res = check_results["ela_region_restricted"]
        if isinstance(reg_res, dict):
            ela_variance = float(reg_res.get("mean_variance", 0.0))

    ela_anomaly_normalized = min(1.0, ela_variance / ELA_NORMALIZATION_THRESHOLD)
    term_ela = 20.0 * ela_anomaly_normalized

    if doc_type == "VISA":
        # Document-specific scoring logic for Visa.
        # Since Visa stickers do not contain printed check digits or signed QR codes,
        # the standard checksum and signature checks are replaced.
        # Component 13 rule validation and Component 14 passport binding are used instead.

        # Component 13: Visa Rule Validation
        rule_val = check_results.get("visa_rule_validation", {})
        rule_violation_fail = (
            1.0
            if (isinstance(rule_val, dict) and not rule_val.get("valid", True))
            else 0.0
        )

        # Component 14: Visa Passport Binding
        bind = check_results.get("visa_passport_binding", {})
        binding_fail = (
            1.0 if (isinstance(bind, dict) and bind.get("score") == 0.0) else 0.0
        )

        # Cross-field Inconsistency
        cross_field_inconsistent = binding_fail

        term_rule_violation = 30.0 * rule_violation_fail
        term_binding = 30.0 * binding_fail
        term_cross_field = 20.0 * cross_field_inconsistent

        raw_score = term_rule_violation + term_binding + term_cross_field + term_ela
        overall_score = min(100.0, max(0.0, raw_score))

        component_breakdown = {
            "rule_violation_contribution": round(term_rule_violation, 2),
            "binding_contribution": round(term_binding, 2),
            "cross_field_contribution": round(term_cross_field, 2),
            "ela_contribution": round(term_ela, 2),
        }
    elif doc_type == "PASSPORT":
        # 1. Checksum Failure
        checksum_fail = 0.0
        if "passport_mrz_checksums" in check_results:
            res = check_results["passport_mrz_checksums"]
            if res is not None and res.get("score") == 0.0:
                checksum_fail = 1.0

        # 2. Cross-field Inconsistency
        cross_field_inconsistent = 0.0
        if "passport_mrz_viz_consistency" in check_results:
            res = check_results["passport_mrz_viz_consistency"]
            if res is not None and res.get("score") == 0.0:
                cross_field_inconsistent = 1.0

        # 3. Authenticity Failure (based on verification_tier)
        verification_tier = check_results.get("verification_tier", "CHIP_UNAVAILABLE")
        authenticity_fail = 0.0

        if verification_tier == "CHIP_VERIFIED":
            pa = check_results.get("passport_passive_auth")
            aa = check_results.get("passport_active_auth")
            pa_score = pa.get("score") if isinstance(pa, dict) else None
            aa_score = aa.get("score") if isinstance(aa, dict) else None
            if pa_score == 0.0 or aa_score == 0.0:
                authenticity_fail = 1.0
        elif verification_tier == "CHIP_READ_FAILED":
            authenticity_fail = 1.0

        term_checksum = 30.0 * checksum_fail
        term_cross_field = 20.0 * cross_field_inconsistent
        term_authenticity = 30.0 * authenticity_fail

        if verification_tier == "CHIP_UNAVAILABLE":
            # Rescale the remaining three terms (checksum, cross-field, ELA) proportionally to still cap at 100.
            # Max possible pre-rescale sum is 30 (checksum) + 20 (cross-field) + 20 (ELA) = 70.
            raw_score = term_checksum + term_cross_field + term_ela
            overall_score = min(100.0, max(0.0, raw_score * (100.0 / 70.0)))

            component_breakdown = {
                "checksum_contribution": round(term_checksum * (100.0 / 70.0), 2),
                "cross_field_contribution": round(term_cross_field * (100.0 / 70.0), 2),
                "ela_contribution": round(term_ela * (100.0 / 70.0), 2),
            }
        else:
            raw_score = term_checksum + term_cross_field + term_authenticity + term_ela
            overall_score = min(100.0, max(0.0, raw_score))

            component_breakdown = {
                "checksum_contribution": round(term_checksum, 2),
                "chip_authenticity_contribution": round(term_authenticity, 2),
                "cross_field_contribution": round(term_cross_field, 2),
                "ela_contribution": round(term_ela, 2),
            }
    else:
        # AADHAAR
        # 1. Checksum Failure (Verhoeff)
        checksum_fail = 0.0
        if "aadhaar_verhoeff" in check_results:
            res = check_results["aadhaar_verhoeff"]
            if res is not None and res.get("score") == 0.0:
                checksum_fail = 1.0

        # Determine verification tier
        verification_tier = check_results.get(
            "verification_tier",
            check_results.get("aadhaar_uidai_signature", {}).get(
                "verification_tier", "QR_VERIFIED"
            ),
        )

        # 2. Cryptographic Signature Failure
        # Only evaluated in QR_VERIFIED tier (when a digital signature block is present).
        signature_fail = 0.0
        if verification_tier == "QR_VERIFIED":
            if "aadhaar_uidai_signature" in check_results:
                res = check_results["aadhaar_uidai_signature"]
                if res is not None and res.get("score") == 0.0:
                    signature_fail = 1.0

        # 3. Cross-field Inconsistency
        # Evaluated in QR_VERIFIED and QR_LEGACY tiers where QR fields are available.
        cross_field_inconsistent = 0.0
        if verification_tier in ("QR_VERIFIED", "QR_LEGACY"):
            if "aadhaar_qr_ocr_consistency" in check_results:
                res = check_results["aadhaar_qr_ocr_consistency"]
                if res is not None and res.get("score") == 0.0:
                    cross_field_inconsistent = 1.0

        term_checksum = 30.0 * checksum_fail
        term_signature = 30.0 * signature_fail
        term_cross_field = 20.0 * cross_field_inconsistent

        if verification_tier == "QR_LEGACY":
            # QR_LEGACY Tier:
            # Pre-2017 XML format QR card with structural absence of an RSA digital signature block.
            # Cryptographic signature check is not applicable (signature_valid = null).
            # Cross-field consistency (XML QR fields vs Front OCR) is available and validated.
            # Available terms: Verhoeff (weight 30) + Cross-field (weight 20) + ELA (weight 20) = sum 70.
            # Rescale available terms to 100 using the 100/70 multiplier (mirroring Passport CHIP_UNAVAILABLE).
            raw_score = term_checksum + term_cross_field + term_ela
            overall_score = min(100.0, max(0.0, raw_score * (100.0 / 70.0)))

            component_breakdown = {
                "checksum_contribution": round(term_checksum * (100.0 / 70.0), 2),
                "cross_field_contribution": round(
                    term_cross_field * (100.0 / 70.0), 2
                ),
                "ela_contribution": round(term_ela * (100.0 / 70.0), 2),
            }
        elif verification_tier == "QR_UNREADABLE":
            # QR_UNREADABLE Tier:
            # Capture-quality failure: QR unreadable due to glare, motion blur, angle, or damage.
            # Signature is marked signature_valid = null (lack of evidence, not proof of tampering).
            # Because QR could not be decoded, both signature (30) and cross-field (20) checks are unavailable.
            # Available terms: Verhoeff (weight 30) + ELA (weight 20) = sum 50.
            # Rescaled using 100/50 = 2.0 multiplier so that genuine physical/mathematical tampering
            # (e.g. invalid Verhoeff + ELA anomaly) reaches FLAGGED (100.0) rather than being artificially capped low.
            raw_score = term_checksum + term_ela
            overall_score = min(100.0, max(0.0, raw_score * (100.0 / 50.0)))

            component_breakdown = {
                "checksum_contribution": round(term_checksum * (100.0 / 50.0), 2),
                "ela_contribution": round(term_ela * (100.0 / 50.0), 2),
            }
        else:
            # QR_VERIFIED Tier (Standard Secure QR):
            # All four checks active: Verhoeff (30) + Signature (30) + Cross-field (20) + ELA (20) = 100.
            raw_score = term_checksum + term_signature + term_cross_field + term_ela
            overall_score = min(100.0, max(0.0, raw_score))

            component_breakdown = {
                "checksum_contribution": round(term_checksum, 2),
                "signature_contribution": round(term_signature, 2),
                "cross_field_contribution": round(term_cross_field, 2),
                "ela_contribution": round(term_ela, 2),
            }

    # Determine status based on thresholds
    if overall_score <= 30.0:
        status = "CLEAR"
    elif overall_score <= 60.0:
        status = "REVIEW"
    else:
        status = "FLAGGED"

    # Identify failed and uncertain checks
    failed_checks = []
    uncertain_checks = []

    for name, result in check_results.items():
        if isinstance(result, dict):
            score = result.get("score")
            if score == 0.0:
                failed_checks.append(name)
            elif score == 0.5:
                uncertain_checks.append(name)

    return {
        "overall_score": round(overall_score, 1),
        "status": status,
        "component_breakdown": component_breakdown,
        "failed_checks": failed_checks,
        "uncertain_checks": uncertain_checks,
    }
