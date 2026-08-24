"""
Passport Module
---------------
mrz.py          - ICAO 9303 TD3 MRZ parsing + 7-3-1 check digits
viz.py          - VIZ OCR (biographical page printed fields)
consistency.py  - MRZ ↔ VIZ cross-check
nfc.py          - BAC handshake (3DES key derivation, mutual auth)
passive_auth.py - Passive Authentication (ICAO Master List cert chain + DG hashes)
active_auth.py  - Active Authentication (anti-chip-clone challenge-response)
"""
from .mrz import parse_mrz, icao_check_digit
from .viz import extract_viz_fields
from .consistency import check_mrz_viz_consistency
from .nfc import perform_bac, derive_bac_keys
from .passive_auth import perform_passive_auth
from .active_auth import perform_active_auth
