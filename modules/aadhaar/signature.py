"""
UIDAI RSA Signature Verification.

Verifies the cryptographic signature on an Aadhaar Secure QR payload
against UIDAI's officially published public certificate.

Algorithm: RSA-2048 with PKCS#1 v1.5 padding and SHA-256 digest.

UIDAI certificate source:
  https://resident.uidai.gov.in/uidai_qr_offline_cert
  (Bundle the .cer/.pem file locally  -  see shared/certs/)
"""

import os
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_der_x509_certificate, load_pem_x509_certificate

# Path to bundled UIDAI certificate (relative to project root)
_CERT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "shared", "certs", "uidai_offline_pub.cer"
)


def verify_uidai_signature(raw_payload: bytes, signature: bytes) -> dict:
    """
    Verify the UIDAI RSA-2048 signature on the Aadhaar QR payload.

    Args:
        raw_payload: QR bytes excluding the last 256 signature bytes.
        signature:   Last 256 bytes of the QR data.

    Returns:
        dict with keys:
          valid (bool), error (str|None), cert_expired (bool)
    """
    try:
        cert = _load_uidai_cert()
    except FileNotFoundError:
        return {
            "valid": False,
            "error": "UIDAI certificate not found at shared/certs/",
            "cert_expired": None,
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Certificate load error: {e}",
            "cert_expired": None,
        }

    # Check certificate validity period (recorded for telemetry, not blocking)
    now = datetime.now(timezone.utc)
    cert_expired = now > cert.not_valid_after_utc

    public_key = cert.public_key()

    try:
        public_key.verify(
            signature,
            raw_payload,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return {"valid": True, "error": None, "cert_expired": cert_expired}
    except InvalidSignature:
        return {
            "valid": False,
            "error": "Signature mismatch - QR data not signed by UIDAI root key",
            "cert_expired": cert_expired,
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Verification error: {e}",
            "cert_expired": cert_expired,
        }


def _load_uidai_cert():
    """Load UIDAI certificate from the bundled file (PEM or DER)."""
    with open(_CERT_PATH, "rb") as f:
        cert_data = f.read()
    if cert_data.startswith(b"-----BEGIN"):
        return load_pem_x509_certificate(cert_data)
    else:
        return load_der_x509_certificate(cert_data)
