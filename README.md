# AI-Based Fake Identity & Document Screening System
### Smart India Hackathon | Problem Statement ID: 26188
**Organization**: Ministry of Home Affairs (MHA)  
**Department**: Sashastra Seema Bal (SSB), Police II Division  
**Category**: Software  
**Theme**: Blockchain & Cybersecurity  

---

## 🎯 Executive Overview

An AI-powered border document screening platform engineered for **high-throughput land border checkpoints** (e.g. Indo-Nepal and Indo-Bhutan borders). It brings real-time optical character recognition, digital cryptography, pixel-level forensic tampering analysis, and sovereign deep face biometric verification to border posts that lack bulky laboratory infrastructure.

The system reduces traveler verification time from **3-5 minutes to under 5 seconds** while generating an explainable, audit-logged **0 to 100 Risk Score**.

---

## 📑 Supported Documents Matrix

| Document | Module 1: OCR Extraction | Module 2: Document Validation | Module 3: Tampering Detection | Module 4: Face Biometrics |
| :--- | :--- | :--- | :--- | :--- |
| **Aadhaar** | OpenBharatOCR + EasyOCR + spaCy NER | Verhoeff Dihedral Checksum + UIDAI RSA-2048 Digital Signature | QR-OCR Cross-Consistency + ELA Compression Forensics | 1:1 Live Face Match + FAISS Identity Graph |
| **Passport** | ICAO Doc 9303 2-Line TD3 MRZ Parsing | Triple 7-3-1 Modulo 10 Check Digits + e-Passport NFC (PA/AA) | VIZ-MRZ Consistency + ELA Photo Forensics | ICAO Biometric Face Match + FAISS Graph |
| **Visa** | Visa OCR Field Extraction | Passport Binding Validation + Stay Duration & Validity Rules | ELA Guilloche Intaglio Pattern Forensics | Immigration Blacklist Check |
| **Driving Licence** | 15-Digit MoRTH Format & 36 State RTO Registry Check | Active Validity Window & Legal Age Rule (DOB >= 18) | ELA Splicing Forensics + EXIF Metadata | 1:1 Live Face Match + FAISS Identity Graph |
| **Voter ID (EPIC)** | 10-Character ECI Series Code Validation | OpenBharatOCR + Devanagari Noise Filtering | Photo Replacement ELA Forensics + Splicing Heatmap | 1:1 Live Face Match + FAISS Identity Graph |
| **Border Permit** | Entry Permit OCR (ILP/CBP/PAP) | Active Date Window & Mandatory ID Binding Check | Seal/Stamp ELA Forensics + Blacklist Check | 1:1 Live Face Match + FAISS Identity Graph |

---

## 🔍 Deep Technical Breakdown by Module

### 🔤 Module 1: OCR Extraction & High-Speed Decoding Pipeline

```
[Document Input] ──► Preprocessing (CLAHE + Otsu) ──► Multi-Engine OCR / C++ Matrix Engine ──► Structured JSON Schema
```

1. **Multi-Engine Optical Pipeline**:
   - **`OpenBharatOCR`**: Specialized deep neural model trained specifically on Indian identity documents (Aadhaar cards, Voter IDs, and bilingual regional formats).
   - **`EasyOCR` + `PaddleOCR`**: Sub-pixel text recognition with DBNet detection and CRNN/SVTR recognition backbones for Latin and Devanagari scripts.
   - **`spaCy NER` (`en_core_web_sm`)**: Custom entity extraction pipeline for Indian personal names, father/husband parentage names, and multi-line addresses.
2. **High-Speed C++ Barcode Matrix Engine (`zxing-cpp`)**:
   - C++ sub-pixel interpolation and Reed-Solomon polynomial math running at **60 FPS** directly in browser/backend.
   - Decodes dense Aadhaar Secure QR codes and MoRTH Driving Licence 2D barcodes in **< 80 milliseconds**.
3. **Adaptive Image Preprocessing**:
   - Dynamic contrast adjustment using **CLAHE** (Contrast Limited Adaptive Histogram Equalization).
   - Adaptive Otsu binarization and perspective deskewing to ensure high extraction accuracy even under poor border lighting and camera glare.

---

### 🛡️ Module 2: Document Validation & Cryptographic Verification

```
[Extracted Demographics] ──► Cryptographic & Checksum Math ──► Cross-Field Consistency ──► Rule Engine Verdict
```

1. **UIDAI Aadhaar Cryptographic Engine**:
   - **RSA-2048 PKCS#1 v1.5 Digital Signatures**: Verifies the 256-byte digital signature block over the SHA-256 hash of the 0xFF-delimited GZIP demographic payload.
   - **Multi-Certificate Chain Bundle (`shared/certs/`)**: Automatically checks against all bundled UIDAI public key generations, handling mandatory post-2022 age-15 key rotations seamlessly.
   - **Verhoeff Checksum**: Computes non-commutative dihedral group D5 arithmetic (F permutation table and D multiplication table) on 12-digit UIDs to catch 100% of single-digit errors and adjacent transpositions.
   - **Dynamic Anchor Parsing**: Distinguishes between Version 1 (pre-2018) and Version 2 (post-2018 Reference ID) QR payloads using dynamic date-anchor alignment.
2. **ICAO Doc 9303 Passport & Visa Engine**:
   - **TD3 Machine Readable Zone (MRZ)**: Parses 2 lines x 44 characters.
   - **ICAO Cyclic 7-3-1 Modulo 10 Algorithm**: Validates 4 independent check digits across Passport Number, Date of Birth, Expiry Date, and Composite Checksum.
   - **LDS1 e-Passport Passive & Active Authentication**: Cryptographically validates Data Group 1 (MRZ) and Data Group 2 (Biometric Face) against the ICAO Country Signing CA (CSCA) Master List.
3. **Driving Licence (MoRTH Sarathi) Rule Engine**:
   - **15-Digit Format Validation**: Enforces SS-RR-YYYY-NNNNNNN across all 36 Indian State and Union Territory RTO registries.
   - **Legal Driving Age**: Enforces minimum 18 years for private motor vehicles (MCWG, LMV) and 20 years for commercial transport (TRANS, HMV).
   - **20-Year / Age 50 Rule**: Validates legacy pre-2019 validity limits.
4. **Voter ID (EPIC) & Border Permit Validation**:
   - **EPIC Series Validation**: Enforces standard 10-character pattern (3 uppercase letters + 7 digits).
   - **Permit-to-ID Binding**: Legally binds the travel permit to the presented Aadhaar or Passport number.
   - **Active Validity Window & Gate Validation**: Verifies authorized port of entry (e.g. Raxaul, Banbasa, Sonauli).

---

### 🔬 Module 3: Tampering Detection & Pixel Forensics (Core AI Innovation)

```
[Raw Document Image] ──► JPEG Re-compression (Q=95) ──► Error Level Analysis (ELA) ──► EXIF Sensor Audit ──► Forensic Heatmap
```

1. **Error Level Analysis (ELA - JPEG Quantization Variance)**:
   - **Physical Principle**: When a JPEG image is saved, all 8x8 Discrete Cosine Transform (DCT) blocks reach uniform quantization error. If a fraudster pastes a new face photo or modifies text, the spliced region has a divergent compression potential.
   - **Mathematical Algorithm**:
     1. Re-compresses image at a fixed baseline quality Q = 95.
     2. Computes the absolute difference matrix: Delta(x, y) = |I_orig(x, y) - I_recomp(x, y)|.
     3. Amplifies difference by scaling factor alpha = 10.0: Heatmap(x, y) = min(255, Delta(x, y) * 10.0).
     4. Computes statistical variance across 4 critical regions: Photo Frame, Document Number, Date of Birth, and Full Background. If localized variance exceeds adaptive baseline -> flags digital splicing.
2. **EXIF Sensor & Camera Metadata Forensics**:
   - Scans binary header markers for editing software signatures (Photoshop, GIMP, Canva, CorelDraw).
   - Detects missing camera sensor parameters, stripped timestamps, and artificial re-encoding signatures.
3. **Guilloche & Intaglio Security Pattern Auditing**:
   - Audits high-frequency microprinting backgrounds on visas and passports to catch flat inkjet reproductions and chemical washing.

---

### 👤 Module 4: Sovereign Edge Face Biometrics & 1:N Identity Graph

```
[Document Photo] ──► ArcFace ResNet-50 (512-D Vector) ──┐
                                                        ├─► Cosine Similarity (1:1 Match)
[Live Camera]   ──► Passive Liveness (FFT + Laplacian)  ──┤
                     └─► ArcFace ResNet-50 (512-D)     ──┘
                                │
                                ▼
                   FAISS Vector Database (1:N Search)
                                │
                   ┌────────────┴────────────┐
                   ▼                         ▼
         Single Identity Confirmed     Multi-Identity Impersonation Alert!
         (Traveler Cleared)           (Same face found under alias name/ID)
```

1. **NIST Benchmark Accuracy (ArcFace Backbone)**:
   - Deep ResNet-50 backbone trained with **Additive Angular Margin Loss (ArcFace)** (m = 0.5, s = 64), achieving **99.83% accuracy on LFW**.
   - Generates normalized 512-dimensional metric embedding vectors robust to aging, lighting variations, and low-resolution legacy card photos.
   - Computes angular cosine similarity. Match threshold >= 0.65 indicates authentic traveler.
2. **1:N Cross-Border Identity Graph (FAISS Vector Index)**:
   - While standard KYC tools only perform isolated 1:1 checks, our engine indexes embeddings in a local **FAISS vector database**.
   - Instantly intercepts criminals or traffickers attempting to use different names and stolen IDs across different border posts.
3. **National Data Sovereignty & Offline Edge Execution**:
   - Zero dependence on commercial third-party cloud APIs. All face embeddings and liveness checks execute 100% on-device in **under 200 milliseconds** on standard CPUs.
4. **Dual-Domain Passive Liveness Detection**:
   - **Frequency-Domain**: 2D Fast Fourier Transform (FFT) high-frequency power spectrum analysis to detect digital screen pixel grids.
   - **Spatial-Domain**: Laplacian convolution variance to detect flat paper mask cutouts and defocus blurs.
5. **Privacy by Design (DPDP Act 2023 Compliant)**:
   - Zero raw photographs or face images are stored in persistent databases. Only one-way, irreversible 512-dimensional mathematical vectors are retained.

---

### ⚖️ Module 5: Decision Orchestration, Explainable Scoring & Audit Logging

1. **Deterministic 0 to 100 Risk Score Formula**:
   Risk Score = 30 * (Checksum Fail) + 30 * (Signature Fail) + 20 * (Cross-Field Inconsistency) + 20 * (ELA Tampering)
2. **Immediate Overrides**:
   - **Watchlist / Blacklist Hit**: Automatic **100 / 100 FLAGGED (THREAT)**.
   - **Face Biometric Mismatch (< 45%)**: Automatic **+40 pts Penalty**.
3. **Tiers & Verdicts**:
   - `0 - 30 pts` -> **`CLEAR (PASSED)`** 🟢
   - `31 - 69 pts` -> **`REVIEW (SUSPICIOUS)`** 🟡
   - `70 - 100 pts` -> **`FLAGGED (THREAT)`** 🔴
4. **Natural Language LLM Officer Summary**:
   - Translates complex cryptographic and pixel metrics into plain-language actionable officer briefs.
5. **Immutable Audit Trail**:
   - Logs all screening transactions with UUIDs, timestamps, risk scores, and check breakdown into tamper-evident SQLite storage for forensic investigations.

---

## 🏗️ System Architecture & Codebase Map

```
SIH-PGDAV-2026/
├── api/
│   └── orchestrator.py      # High-performance FastAPI asynchronous orchestrator
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
```

---

## ⚡ Quickstart & Deployment

```bash
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
```

Access dashboard on any smartphone or tablet at `http://<YOUR_LOCAL_IP>:8000`.
