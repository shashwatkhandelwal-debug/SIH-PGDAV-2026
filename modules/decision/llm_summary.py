"""
LLM Plain-Language Summary Generator.

Translates structured check results into one concise sentence
for the border officer  -  focusing only on the most critical finding.

Uses Google Gemini Flash (fast, low-latency, sufficient for this task).
Falls back to a rule-based template summary if the API call fails.
"""
import os
import json
from typing import Optional

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


def generate_summary(check_results: dict, score_result: dict) -> str:
    """
    Generate a plain-language officer summary.

    Args:
        check_results:  Raw check results dict (check_name → result).
        score_result:   Output from scorer.compute_score().

    Returns:
        One sentence (max ~30 words) describing the most critical finding
        and recommended officer action.
    """
    if _GENAI_AVAILABLE and os.getenv('GEMINI_API_KEY'):
        try:
            return _llm_summary(check_results, score_result)
        except Exception:
            pass  # Fall through to rule-based

    return _rule_based_summary(score_result)


# ── LLM path ──────────────────────────────────────────────────────────────────

def _llm_summary(check_results: dict, score_result: dict) -> str:
    genai.configure(api_key=os.environ['GEMINI_API_KEY'])
    model = genai.GenerativeModel('gemini-1.5-flash')

    failed = score_result.get('failed_checks', [])
    risk   = score_result.get('risk_level', 'UNKNOWN')
    total  = score_result.get('total_score', 0)

    prompt = f"""You are a document security assistant at a border checkpoint.
A traveler has presented identity documents. Here is the verification result:

Risk Level: {risk}
Score: {total}/100
Failed checks: {', '.join(failed) if failed else 'None'}
Check details (abbreviated): {json.dumps({k: v.get('score') for k, v in check_results.items() if isinstance(v, dict)}, indent=2)}

Write EXACTLY ONE sentence (maximum 30 words) that:
1. States the most critical finding (if any failure exists)
2. Gives the officer a clear action (proceed / manual check / hold)
Do not use technical jargon. Do not list all checks. Focus on the single most important issue.
"""

    response = model.generate_content(prompt)
    return response.text.strip()


# ── Rule-based fallback ────────────────────────────────────────────────────────

_CRITICAL_CHECK_MESSAGES = {
    "aadhaar_uidai_signature":    "Aadhaar QR signature invalid  -  document not issued by UIDAI.",
    "passport_passive_auth":      "Passport chip data cannot be verified against ICAO  -  possible tampering.",
    "passport_active_auth":       "Passport chip failed anti-clone check  -  possible cloned chip.",
    "face_match":                 "Face does not match document photo  -  possible identity mismatch.",
    "visa_passport_binding":      "Visa is not issued for this passport  -  possible document swap.",
    "aadhaar_qr_ocr_consistency": "Aadhaar printed name does not match QR data  -  possible card alteration.",
    "passport_mrz_viz_consistency": "Passport MRZ and biographical page data do not match.",
    "expiry_valid":               "Document is expired.",
    "liveness":                   "Liveness check failed  -  possible photo presentation attack.",
}


def _rule_based_summary(score_result: dict) -> str:
    failed = score_result.get('failed_checks', [])
    risk   = score_result.get('risk_level', 'PASS')

    if risk == 'PASS':
        return "All checks passed  -  document appears genuine, proceed normally."

    # Find highest-weight failed check
    from modules.decision.scorer import WEIGHTS
    failed_by_weight = sorted(failed, key=lambda c: WEIGHTS.get(c, 0), reverse=True)

    if failed_by_weight:
        top_fail = failed_by_weight[0]
        msg = _CRITICAL_CHECK_MESSAGES.get(top_fail, f"Check '{top_fail}' failed.")
        return f"{msg} Recommend manual secondary inspection."

    return f"Risk level {risk}  -  multiple anomalies detected, recommend manual review."
