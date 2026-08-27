# AI-Based Fake Identity & Document Screening System
### SIH 2026 - Problem Statement 6188 | Ministry of Home Affairs - Sashastra Seema Bal (SSB)

An AI-powered document screening platform for **land border checkpoints** - bringing camera-based, cryptographically-backed document verification to posts that currently have no automated infrastructure.

---

## What It Screens

| Document | Checks |
|---|---|
| **Aadhaar** | OCR extraction · Verhoeff checksum · UIDAI QR signature (RSA) · QR↔OCR cross-check |
| **Passport** | MRZ parsing · ICAO checksums · VIZ OCR · MRZ↔VIZ cross-check · NFC chip (BAC + Passive Auth + Active Auth) |
| **Visa** | OCR extraction · Rule validation · Visa↔Passport binding check |

## Modules

```
Module 1  →  OCR Extraction          (Aadhaar, Passport MRZ+VIZ, Visa)
Module 2  →  Document Validation     (Verhoeff, ICAO checksums, rule validation, crypto verification)
Module 3  →  Tampering Detection     (ELA, EXIF, region-restricted forensics)
Module 4  →  Face Verification       (ArcFace embeddings, liveness, identity graph)
Module 5  →  Decision Layer          (Explainable weighted score + LLM plain-language summary)
```

## Architecture

```
modules/
├── aadhaar/        # OCR, QR decode, Verhoeff, UIDAI signature, cross-check
├── passport/       # MRZ, VIZ, NFC BAC, Passive Auth, Active Auth
├── visa/           # OCR, rule validation, passport binding
├── face/           # Embedder, liveness, face match, identity graph
├── forensics/      # ELA (3 modes), EXIF inspection
└── decision/       # Weighted scorer, LLM summary

shared/             # Preprocessing, quality check, watchlist, audit log
api/                # FastAPI orchestrator
frontend/           # Streamlit UI (phone-browser compatible)
```

## Key Technical Highlights

- **Cryptographic authenticity**: UIDAI RSA-2048 signature verification on Aadhaar QR; ICAO Passive Authentication against ICAO Master List; Active Authentication (anti-chip-cloning challenge-response)
- **Cross-source consistency**: QR↔OCR, MRZ↔VIZ, Visa↔Passport binding: defends against copy-paste attacks on genuine signed elements
- **Identity graph**: ArcFace embeddings stored in FAISS, flags same face screened under multiple identities across visits
- **Explainable scoring**: Weighted formula (not black-box ML) with LLM plain-language officer summary
- **Zero image storage**: Only 512-dim embedding vectors stored, never photos

## Setup

```bash
git clone https://github.com/shashwatkhandelwal-debug/SIH-PGDAV-2026.git
cd SIH-PGDAV-2026
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # required for Aadhaar name NER
streamlit run frontend/app.py
```

**Aadhaar OCR:** OpenBharatOCR is primary; EasyOCR + spaCy NER is the fallback if OpenBharatOCR is unavailable. On Windows, install the ZBar DLL for PyZBar (`libzbar`); on Linux/Streamlit Cloud, `libzbar0` is listed in `packages.txt`.

## Deliberate Scope Boundaries

- ❌ Enrollment-time fraud (issuance-level problem, not checkpoint-level)
- ❌ Physical UV/IR hologram verification (requires hardware)
- ❌ Live government database cross-checks (requires institutional API access)
- ✅ Everything above is stated upfront, not discovered under questioning

---

**Organization**: Ministry of Home Affairs · **Department**: Sashastra Seema Bal (SSB), Police II Division  
**Category**: Software · **Theme**: Miscellaneous · **PS ID**: 6188
