# SSB-VAJRA: AI-Based Fake Identity & Document Screening System
### Smart India Hackathon | Problem Statement ID: 26188
**Organization**: Ministry of Home Affairs (MHA)  
**Department**: Sashastra Seema Bal (SSB), Police II Division  
**Category**: Software  
**Theme**: Blockchain & Cybersecurity  

---

##  Executive Overview

An AI-powered border document screening platform engineered for **high-throughput land border checkpoints** (such as Indo-Nepal and Indo-Bhutan border posts). The platform provides automated optical character recognition, digital cryptography verification, pixel-level tampering heuristics, and sovereign face biometric matching to assist border security personnel in rapid decision triage.

The system is designed as an **Officer Decision Support System (Level-1 Triage)** to reduce preliminary verification time from 3 to 5 minutes down to under 5 seconds per traveler, generating an explainable, audit-logged **0 to 100 Risk Score** with clear diagnostic pointers for secondary human inspection.

---

## Implementation Status & Roadmap

| Feature / Subsystem | Status | Technical Notes |
| :--- | :--- | :--- |
| **Multi-Document OCR Pipeline** | **Implemented** | OpenBharatOCR (primary for Indian IDs), EasyOCR, PaddleOCR fallback, spaCy NER, and C++ zxing-cpp matrix engine. |
| **Cryptographic & Checksum Validation** | **Implemented** | UIDAI RSA-2048 PKCS#1 v1.5 verification, Verhoeff D5 dihedral checksum, ICAO Doc 9303 7-3-1 Modulo 10 MRZ check digits. |
| **Multi-Generation Certificate Handling** | **Implemented** | Multi-cert chain bundle loader in `shared/certs/` handling post-2022 age-15 UIDAI key rotations. |
| **Cross-Field Consistency Engine** | **Implemented** | Aadhaar Front OCR vs Back QR demographic matching with dynamic V1/V2 anchor alignment; Passport MRZ vs VIZ cross-validation. |
| **Error Level Analysis (ELA) Forensics** | **Implemented** | Multi-region JPEG DCT re-compression variance analysis ($Q=95, \alpha=10.0$) targeting photo frame and text regions. |
| **EXIF Sensor Metadata Forensics** | **Implemented** | Binary header tag auditing for image manipulation software signatures (Photoshop, GIMP, Canva) and stripped camera tags. |
| **1:1 Face Biometric Matching** | **Implemented** | ArcFace ResNet-50 512-dimensional metric embedding backbone with cosine similarity scoring. |
| **Passive Liveness Detection** | **Implemented** | Frequency-domain 2D FFT power spectrum analysis combined with spatial Laplacian texture variance. |
| **Bounded Watchlist Face Search (1:W)** | **Implemented** | Local FAISS vector index scoped strictly to known high-risk watchlists and repeat-alias records (not universal mass tracking). |
| **Deterministic Risk Scoring Engine** | **Implemented** | Transparent 0-100 additive penalty formula with immediate hard overrides for blacklist matches and biometric failures. |
| **LLM Officer Summary Grounding** | **Implemented** | Natural language briefing grounded strictly on deterministic JSON check results without score alteration capability. |
| **Audit Logging & Transaction Store** | **Implemented** | Local SQLite transaction logging with UUIDs, timestamps, raw metric payloads, and officer notes. |
| **Cryptographic Audit Hash-Chaining** | **Roadmap** | SHA-256 Merkle / hash-linked chained logging across sequential screening transactions. |
| **Active Liveness Micro-Challenges** | **Roadmap** | Interactive prompt-based challenges (randomized head turn, blink sequence, gaze tracking) for escalated secondary review. |
| **Generative-AI / Deepfake Detection** | **Roadmap** | Specialized frequency-domain neural detectors (such as Dire / CNN-based artifact classifiers) for synthetic document images. |
| **Demographic ROC & Threshold Calibration** | **Roadmap** | Field-calibrated ROC curve tuning across diverse South Asian demographics (skin tone, aging, rural document degradation). |
| **Live Remote Sync & Key Orchestration** | **Roadmap** | Cryptographically signed delta sync protocols for remote edge kiosks over intermittent SATCOM/encrypted USB tokens. |

---

## Tiered Verification Design: Cryptographic vs Optical

To prevent worn, sun-damaged, or legitimately aged documents from being falsely penalized as forgeries, the system implements a strict **two-tier architecture**:

```
[Presented Document]
        │
        ├─► TIER 1: Cryptographic Layer (Immune to Physical Wear)
        │    • Encoded payload read digitally via 2D Barcode (Aadhaar QR) or Machine Readable Zone (Passport MRZ).
        │    • Validated via RSA-2048 PKCS#1 v1.5 digital signature or ICAO Doc 9303 Modulo 10 check digits.
        │    • Zero degradation on faded ink: mathematical validity remains 100% intact if barcode/MRZ is readable.
        │
        └─► TIER 2: Optical & Surface Layer (Graceful Degradation)
             • Visual Inspection Zone (VIZ) extracted via multi-engine OCR.
             • Evaluated for physical tampering (ELA) and surface consistency.
             • Rule on Degradation: If physical wear or ink fading causes low OCR confidence, the engine flags
               an informational note (LOW_OCR_CONFIDENCE) and routes to manual inspection with ZERO fraud penalty.
```

---

## Supported Documents Matrix

| Document | Module 1: OCR Extraction | Module 2: Document Validation | Module 3: Tampering Detection | Module 4: Face Biometrics |
| :--- | :--- | :--- | :--- | :--- |
| **Aadhaar** | OpenBharatOCR + EasyOCR + spaCy NER | Verhoeff Dihedral Checksum + UIDAI RSA-2048 Digital Signature | QR-OCR Cross-Consistency + ELA Compression Forensics | 1:1 Live Face Match + Bounded 1:W Watchlist Search |
| **Passport** | ICAO Doc 9303 2-Line TD3 MRZ Parsing | Triple 7-3-1 Modulo 10 Check Digits + e-Passport NFC (PA/AA) | VIZ-MRZ Consistency + ELA Photo Forensics | ICAO Biometric Face Match + Bounded 1:W Watchlist Search |
| **Visa** | Visa OCR Field Extraction | Passport Binding Validation + Stay Duration & Validity Rules | ELA Guilloche Intaglio Pattern Forensics | Immigration Blacklist Check |
| **Driving Licence** | 15-Digit MoRTH Format & 36 State RTO Registry Check | Active Validity Window & Legal Age Rule (DOB >= 18) | ELA Splicing Forensics + EXIF Metadata | 1:1 Live Face Match + Bounded 1:W Watchlist Search |
| **Voter ID (EPIC)** | 10-Character ECI Series Code Validation | OpenBharatOCR + Devanagari Noise Filtering | Photo Replacement ELA Forensics + Splicing Heatmap | 1:1 Live Face Match + Bounded 1:W Watchlist Search |
| **Border Permit** | Entry Permit OCR (ILP/CBP/PAP) | Active Date Window & Mandatory ID Binding Check | Seal/Stamp ELA Forensics + Blacklist Check | 1:1 Live Face Match + Bounded 1:W Watchlist Search |

---

##  Deep Technical Breakdown by Module

### Module 1: OCR Extraction & Deep Decoding Pipeline

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

### Module 2: Document Validation & Cryptographic Verification

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
   - **ICAO Cyclic 7-3-1 Modulo 10 Algorithm**: Validates 4 independent check digits across Passport Number, Date of Birth, Expiry Date, and Composite Checksum:
     $$\text{Check Digit} = \left( \sum_{i=0}^{n-1} \text{char\_val}(c_i) \times w_{i \bmod 3} \right) \bmod 10, \quad w \in \{7, 3, 1\}$$
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

### Module 3: Tampering Detection & Pixel Forensics (Core AI Innovation)

```
[Raw Document Image] ──► JPEG Re-compression (Q=95) ──► Error Level Analysis (ELA) ──► EXIF Sensor Audit ──► Forensic Heatmap
```

1. **Error Level Analysis (ELA - JPEG Quantization Variance)**:
   - **Physical Principle**: When a JPEG image is saved, all 8x8 Discrete Cosine Transform (DCT) blocks reach uniform quantization error. If a fraudster pastes a new face photo or modifies text, the spliced region has a divergent compression potential.
   - **Mathematical Algorithm**:
     1. Re-compresses image at a fixed baseline quality $Q = 95$: $I_{\text{recomp}} = \text{JPEG}(I_{\text{orig}}, 95)$.
     2. Computes the absolute difference matrix: $\Delta(x, y) = |I_{\text{orig}}(x, y) - I_{\text{recomp}}(x, y)|$.
     3. Amplifies difference by scaling factor $\alpha = 10.0$: $\text{Heatmap}(x, y) = \min(255, \Delta(x, y) \times 10.0)$.
     4. Computes statistical variance across 4 critical regions: Photo Frame, Document Number, Date of Birth, and Full Background.
   - **Operational Role**: ELA serves as a rapid secondary triage heuristic for amateur digital alterations; it is not treated as standalone proof of forgery without supporting cryptographic or cross-field anomalies.
2. **EXIF Sensor & Camera Metadata Forensics**:
   - Scans binary header markers for editing software signatures (Photoshop, GIMP, Canva, CorelDraw).
   - Detects missing camera sensor parameters, stripped timestamps, and artificial re-encoding signatures.
3. **Guilloche & Intaglio Security Pattern Auditing**:
   - Audits high-frequency microprinting backgrounds on visas and passports to catch flat inkjet reproductions and chemical washing.

---

### Module 4: Sovereign Edge Face Biometrics & Bounded 1:W Watchlist Search

```
[Document Photo] ──► ArcFace ResNet-50 (512-D Vector) ──┐
                                                        ├─► Cosine Similarity (1:1 Verification)
[Live Camera]   ──► Passive Liveness (FFT + Laplacian)  ──┤
                     └─► ArcFace ResNet-50 (512-D)     ──┘
                                │
                                ▼
                   Bounded FAISS Watchlist Index (1:W Search)
                                │
                   ┌────────────┴────────────┐
                   ▼                         ▼
         No Watchlist Match            Watchlist / Alias Interception Alert!
         (Proceed to Triage)          (Biometric match found on high-risk record)
```

1. **NIST-Benchmark Metric Learning (ArcFace Backbone)**:
   - Deep ResNet-50 backbone trained with **Additive Angular Margin Loss (ArcFace)** ($m = 0.5, s = 64$), demonstrating **99.83% accuracy on the benchmark LFW dataset**.
   - Generates normalized 512-dimensional metric embedding vectors ($||\mathbf{v}||_2 = 1$) robust to aging, lighting variations, and low-resolution legacy card photos.
   - Computes angular cosine similarity: $\cos(\theta) = \mathbf{u} \cdot \mathbf{v}$. A baseline threshold of $\ge 0.65$ is utilized for Level-1 screening.
2. **Bounded 1:W Watchlist Search (FAISS Index)**:
   - **Scope Definition**: Biometric 1:N searching is strictly scoped to a **Bounded High-Risk Watchlist Index ($1:W$)** containing active fugitives, border deserters, and flagged cross-border syndicate profiles.
   - It is **not** used as a universal surveillance index over the general traveling public.
3. **National Data Sovereignty & Offline Edge Execution**:
   - Zero dependence on commercial third-party cloud APIs. All face embeddings and liveness checks execute 100% on-device in **under 200 milliseconds** on standard CPUs.
4. **Dual-Domain Passive Liveness Detection**:
   - **Frequency-Domain**: 2D Fast Fourier Transform (FFT) high-frequency power spectrum analysis to detect digital screen pixel grids.
   - **Spatial-Domain**: Laplacian convolution variance to detect flat paper mask cutouts and defocus blurs.
5. **Data Minimization (Privacy by Design)**:
   - Raw face photographs and live camera frames are processed in ephemeral memory and discarded immediately after vector generation.
   - Only one-way, irreversible 512-dimensional mathematical vectors are indexed.

---

### Module 5: Decision Orchestration, Explainable Scoring & Audit Logging

1. **Deterministic 0 to 100 Risk Score Formula**:
   $$\text{Risk Score} = 30 \times (\text{Checksum Fail}) + 30 \times (\text{Signature Fail}) + 20 \times (\text{Cross-Field Inconsistency}) + 20 \times (\text{ELA Tampering})$$
2. **Immediate Overrides**:
   - **Watchlist / Blacklist Hit**: Automatic **100 / 100 FLAGGED (THREAT)**.
   - **Face Biometric Mismatch ($< 45\%$)**: Automatic **+40 pts Penalty**.
3. **Tiers & Verdicts**:
   - `0 - 30 pts` $\to$ **`CLEAR (PASSED)`** 
   - `31 - 69 pts` $\to$ **`REVIEW (SUSPICIOUS)`** 
   - `70 - 100 pts` $\to$ **`FLAGGED (THREAT)`** 
4. **Natural Language LLM Officer Summary**:
   - Translates complex cryptographic and pixel metrics into plain-language actionable briefs for border officers.
   - Strictly grounded on underlying JSON values without the capability to hallucinate or modify calculated risk scores.
5. **Audit Log Integrity**:
   - Current implementation logs all screening transactions with UUIDs, timestamps, risk scores, and check breakdown into local SQLite storage.
   - Cryptographic SHA-256 sequential hash-chaining is specified on the project roadmap.

---

## Known Limitations & Design Boundaries

This software is an **academic prototype and engineering Proof-of-Concept (PoC)** developed for the Smart India Hackathon. It is not currently deployed border infrastructure. The following limitations are explicitly documented:

1. **No Live Production Database Integration**:
   - Operates on bundled cryptographic public certificates (UIDAI certificate chains and ICAO Master Lists). Does not maintain real-time bidirectional integration with live government database backends (CIDR, CCTNS, or Parivahan production APIs).
2. **Secondary Nature of Pixel Forensics**:
   - Error Level Analysis (ELA) and EXIF metadata checks are secondary heuristics. They can be degraded by physical print-scan cycles and do not replace cryptographic signatures or physical security features (UV holograms, microprinting under magnification).
3. **Generative-AI Forgeries**:
   - Advanced synthetic document forgeries generated via modern Diffusion or GAN pipelines do not exhibit classical JPEG recompression artifacts and are not currently detected by the baseline ELA heuristic.
4. **Field Validation & Demographic Calibration**:
   - Reported model accuracies reflect standard public benchmark datasets (such as LFW for ArcFace). Formal field-trial False Acceptance Rate (FAR) and False Rejection Rate (FRR) curves across rural Indian demographics require dedicated calibration during pilot deployments.
5. **Human-in-the-Loop Requirement**:
   - The platform is designed exclusively for decision support. No individual can be denied entry or detained solely based on an automated risk score without formal secondary human inspection.

---

## Legal & Privacy Considerations (DPDP Act 2023)

* **Processing Scope**: While national security and law enforcement agencies carry specific statutory processing exemptions under Section 17 of the Digital Personal Data Protection (DPDP) Act 2023 for border control and crime prevention, this platform independently enforces strict **Data Minimization Principles**:
  * **Zero Raw Image Retention**: Document scans and live selfies are held in volatile RAM only during active inference and are not persistently written to disk.
  * **Irreversible Mathematical Vectors**: Only 512-dimensional numerical embeddings are retained for high-risk watchlist comparisons.
  * **Secondary Human Review Workflow**: Provides clear audit trails to support administrative appeals and manual verification.
* **Deployment Notice**: Formal legal sign-off and compliance review by designated departmental legal counsel is mandatory prior to any operational deployment.

---

## System Architecture & Codebase Map

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

## Quickstart & Deployment

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

Access dashboard on any smartphone, tablet, or workstation browser at `http://<YOUR_LOCAL_IP>:8000`.
