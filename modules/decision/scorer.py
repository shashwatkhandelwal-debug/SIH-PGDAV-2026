"""
Decision Scorer - Risk assessment calculations.

This module computes the final risk score based on checksum validation,
signature verification, cross field consistency and ELA forensics.
"""
from typing import Any

# ELA normalization threshold constant.
# This value was tuned against sample_data to separate authentic images
# from spliced regions.
ELA_NORMALIZATION_THRESHOLD = 15.0


def compute_score(check_results: dict[str, Any]) -> dict:
    """
    Compute the risk score (0 to 100) based on checked fields.

    Higher score means higher risk.
    """
    # 1. Checksum Failure
    checksum_fail = 0.0
    if "aadhaar_verhoeff" in check_results:
        res = check_results["aadhaar_verhoeff"]
        if res is not None and res.get("score") == 0.0:
            checksum_fail = 1.0
    elif "passport_mrz_checksums" in check_results:
        res = check_results["passport_mrz_checksums"]
        if res is not None and res.get("score") == 0.0:
            checksum_fail = 1.0

    # 2. Signature Failure
    signature_fail = 0.0
    if "aadhaar_uidai_signature" in check_results:
        res = check_results["aadhaar_uidai_signature"]
        if res is not None and res.get("score") == 0.0:
            signature_fail = 1.0
    elif "passport_passive_auth" in check_results or "passport_active_auth" in check_results:
        pa = check_results.get("passport_passive_auth")
        aa = check_results.get("passport_active_auth")
        pa_score = pa.get("score") if isinstance(pa, dict) else None
        aa_score = aa.get("score") if isinstance(aa, dict) else None
        if pa_score == 0.0 or aa_score == 0.0:
            signature_fail = 1.0

    # 3. Cross-field Inconsistency
    cross_field_inconsistent = 0.0
    for key in ["aadhaar_qr_ocr_consistency", "passport_mrz_viz_consistency", "visa_passport_binding"]:
        if key in check_results:
            res = check_results[key]
            if res is not None and res.get("score") == 0.0:
                cross_field_inconsistent = 1.0
                break

    # 4. ELA Anomaly Normalized
    ela_variance = 0.0
    ela_res = check_results.get("ela_full_document")
    if isinstance(ela_res, dict):
        ela_variance = float(ela_res.get("mean_variance", 0.0))
    elif "ela_region_restricted" in check_results:
        reg_res = check_results["ela_region_restricted"]
        if isinstance(reg_res, dict):
            ela_variance = float(reg_res.get("mean_variance", 0.0))

    ela_anomaly_normalized = min(1.0, ela_variance / ELA_NORMALIZATION_THRESHOLD)

    # Compute individual risk terms
    term_checksum = 30.0 * checksum_fail
    term_signature = 30.0 * signature_fail
    term_consistency = 20.0 * cross_field_inconsistent
    term_ela = 20.0 * ela_anomaly_normalized

    raw_score = term_checksum + term_signature + term_consistency + term_ela
    overall_score = min(100.0, max(0.0, raw_score))

    # Determine status based on thresholds
    if overall_score <= 30.0:
        status = "CLEAR"
    elif overall_score <= 60.0:
        status = "REVIEW"
    else:
        status = "FLAGGED"

    component_breakdown = {
        "checksum_contribution": round(term_checksum, 2),
        "signature_contribution": round(term_signature, 2),
        "consistency_contribution": round(term_consistency, 2),
        "ela_contribution": round(term_ela, 2)
    }

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
