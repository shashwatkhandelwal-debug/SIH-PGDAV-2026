# AI-Based Fake Identity & Document Screening System
### Smart India Hackathon | Problem Statement ID: 26188
**Organization**: Ministry of Home Affairs  
**Department**: Sashastra Seema Bal (SSB), Police II Division  
**Category**: Software  
**Theme**: Blockchain & Cybersecurity  

---

## 🎯 Executive Overview

An AI-powered border document screening platform engineered for **high-throughput land border checkpoints** (e.g. Indo-Nepal and Indo-Bhutan borders). It brings real-time optical recognition, digital cryptography, pixel-level forensic tampering analysis, and deep face biometric verification to border posts that lack bulky laboratory infrastructure.

The system reduces traveler verification time from **3-5 minutes to under 5 seconds** while generating an explainable, audit-logged **0 to 100 Risk Score**.

---

## 📑 Supported Documents & Verification Modules

| Document | Primary Verification Layer | Secondary Verification Layer | Tampering / Biometric Layer |
| :--- | :--- | :--- | :--- |
| **Aadhaar** | OpenBharatOCR + EasyOCR + spaCy NER | Verhoeff Dihedral Checksum + UIDAI RSA-2048 Digital Signature | QR-OCR Cross-Consistency + ELA Compression Forensics |
| **Passport** | ICAO Doc 9303 2-Line TD3 MRZ Parsing | Triple 7-3-1 Modulo 10 Check Digits + e-Passport NFC (PA/AA) | VIZ-MRZ Consistency + ELA Photo Forensics |
| **Visa** | Visa OCR Field Extraction | Passport Binding Validation + Stay Duration & Validity Rules | ELA Guilloche Intaglio Pattern Forensics |
| **Driving Licence** | 15-Digit MoRTH Format & 36 State RTO Registry Check | Active Validity Window & Legal Age Rule (DOB >= 18) | ELA Splicing Forensics + Biometric Face Match |
| **Voter ID (EPIC)** | 10-Character ECI Series Code Validation | OpenBharatOCR + Devanagari Noise Filtering | Photo Replacement ELA Forensics + Face Match |
| **Border Permit** | Entry Permit OCR (ILP/CBP/PAP) | Active Date Window & Mandatory ID Binding Check | Seal/Stamp ELA Forensics + Blacklist Check |

---

## 🔬 Core AI & Mathematical Algorithms

1. **OCR & Text Extraction Pipeline**:
   - OpenBharatOCR: Pre-trained neural models optimized for Indian national identity documents.
   - EasyOCR + PaddleOCR: Deep learning text recognition with sub-pixel interpolation.
   - spaCy NER (en_core_web_sm): Named Entity Recognition for Indian demographic parsing.
   - zxing-cpp: C++ high-speed Reed-Solomon QR matrix decoder.

2. **Cryptographic Validation Engine**:
   - **UIDAI RSA-2048 Signature Verification**: PKCS#1 v1.5 with SHA-256 over GZIP compressed demographic payload using multi-generation UIDAI public certificate chains.
   - **Verhoeff Checksum**: Permutation tables (F) and multiplication tables (D) over Dihedral group D5 for Aadhaar UID validation.
   - **ICAO Doc 9303 Checksum**: Modulo 10 cyclic weighting (7, 3, 1) over Passport MRZ fields.
   - **ICAO LDS1 Passive Authentication**: X.509 Country Signing CA (CSCA) certificate validation.

3. **Tampering & Image Forensics (Core Innovation)**:
   - **Error Level Analysis (ELA)**: Computes local JPEG compression error divergence to expose digitally spliced faces, altered dates, and cut-and-paste text.
   - **EXIF Sensor Integrity**: Detects image editing software signatures (Photoshop, GIMP, Canva) and missing camera metadata.

4. **Biometric Face Verification & Identity Graph**:
   - **ArcFace / InsightFace**: Deep ResNet-50 backbone extracting 512-dimensional facial embedding vectors.
   - **Passive Liveness Detection**: Frequency-domain texture analysis (FFT + Laplacian variance) to detect printed paper and screen presentation attacks.
   - **FAISS Identity Graph**: Nearest-neighbor vector index to intercept travelers attempting to use different identities across border visits.

5. **Decision & Risk Scoring**:
   - **Deterministic Weighted Formula**:
     Risk Score = 30 * (Checksum) + 30 * (Signature) + 20 * (Cross-Consistency) + 20 * (Tampering)
   - Generates instant verdicts: CLEAR (0-30) | REVIEW (31-69) | FLAGGED (70-100).

---

## 🏗️ System Architecture

`
SIH-PGDAV-2026/
├── api/
│   └── orchestrator.py      # High-performance FastAPI asynchronous pipeline
├── modules/
│   ├── aadhaar/             # OCR, QR decode, Verhoeff, UIDAI RSA-2048, Consistency
│   ├── passport/            # TD3 MRZ, 7-3-1 Checksum, VIZ, NFC Passive/Active Auth
│   ├── visa/                # OCR, Rule Validation, Passport Binding
│   ├── dl/                  # 15-digit MoRTH format, 36 State RTO Registry, Age Rules
│   ├── permit/              # Border Permit OCR, Active Window, ID Binding
│   ├── generic_id/          # ECI EPIC Voter ID Adapter, Devanagari Noise Filter
│   ├── forensics/           # ELA (JPEG Quantization Variance), EXIF Inspection
│   ├── face/                # ArcFace Embedder, Liveness, 1:1 Match, FAISS Graph
│   └── decision/            # Weighted Scorer, LLM Plain-Language Summary
├── shared/                  # Preprocessing, Watchlist Interception, Audit Logger
├── frontend/
│   └── static/              # Zero-dependency Mobile PWA UI (HTML5, Tailwind, JS)
└── requirements.txt
`

---

## ⚡ Quickstart & Deployment

`ash
# 1. Clone repository
git clone https://github.com/shashwatkhandelwal-debug/SIH-PGDAV-2026.git
cd SIH-PGDAV-2026

# 2. Set up virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 4. Launch FastAPI Server & Mobile PWA
uvicorn api.orchestrator:app --host 0.0.0.0 --port 8000
`

Access dashboard on any smartphone or tablet at http://<YOUR_LOCAL_IP>:8000.

---

## 🔒 Privacy by Design
- **Zero Image Storage**: Raw photographs and identity scans are processed strictly in memory and discarded. Only irreversible 512-dimensional vector embeddings are stored.
- **Offline Edge Capability**: Can run completely offline on edge laptops / tablets at remote border posts without internet connectivity.
