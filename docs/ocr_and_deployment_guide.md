# OCR Architecture & Deployment Guide

## Overview

The document screening system uses a **resilient dual-tier OCR pipeline** designed to achieve maximum accuracy on Indian identity documents while ensuring rock-solid zero-crash stability across both resource-constrained cloud sandboxes (like Streamlit Cloud) and high-performance local/production checkpoints.

---

## 1. Dual-Tier OCR Architecture

Every document parsing module implements dynamic engine resolution:

```
                  ┌──────────────────────────────┐
                  │   Input Document Capture     │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                   Is OpenBharatOCR available
                   & Tesseract binary in PATH?
                                 │
                 ┌───────────────┴───────────────┐
                 │ YES                           │ NO (Cloud Fallback)
                 ▼                               ▼
     ┌────────────────────────┐      ┌────────────────────────┐
     │     OpenBharatOCR      │      │     EasyOCR Engine     │
     │  (Government Specialized│      │  + Multi-Stage Preproc │
     │       Pipelines)       │      │  + Regex State Parsers │
     └───────────┬────────────┘      └───────────┬────────────┘
                 │                               │
                 └───────────────┬───────────────┘
                                 │
                                 ▼
                  Structured Field Dictionary
          (UID, Name, DOB, Validity, Checksums)
```

### Module Mappings:

| Document Type | Primary Engine (`openbharatocr`) | Fallback Engine (`easyocr` + OpenCV) |
| :--- | :--- | :--- |
| **Aadhaar Card** | `openbharatocr.front_aadhaar()` & `back_aadhaar()` | Multi-pass EasyOCR + Verhoeff check digit recovery |
| **Passport Bio Page** | `openbharatocr.passport()` | ICAO 9303 MRZ parser + VIZ regular expressions |
| **Driving Licence** | `openbharatocr.driving_licence()` | Sarathi DL format parser + 36 State RTO validation |
| **Voter ID / Generic ID** | `openbharatocr.voter_id_front()` | EPIC pattern extractor + visual text analyzer |
| **Visa & Permits** | `openbharatocr.ocr()` | EasyOCR + border gate validity rule engine |

---

## 2. Why OpenBharatOCR is Managed via Dynamic Loading

`openbharatocr` relies on the system-level C++ `tesseract` binary and language packs (`tesseract-ocr`, `tesseract-ocr-hin`). 

* **Streamlit Cloud Free Tier Limitation**: Free-tier cloud instances operate within a strict **1GB RAM memory ceiling** without pre-configured C++ Tesseract binaries in their standard build sandbox. Hardcoding `openbharatocr` in `requirements.txt` causes pip build timeouts and container faults ("Oh no" crash screen).
* **Dynamic Resolution Solution**: The codebase imports `openbharatocr` inside a `try...except ImportError` block. When running on cloud tiers without Tesseract, the system automatically falls back to `easyocr` and OpenCV with zero crashes.

---

## 3. How to Run with Full OpenBharatOCR Locally

To enable native `openbharatocr` extraction on your local machine or presentation laptop:

### Step 1: Install System Tesseract
* **Windows**: Download and install the [Tesseract-OCR Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki).
  * Ensure `C:\Program Files\Tesseract-OCR` is added to your System `PATH`.
* **Ubuntu / Debian**:
  ```bash
  sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-hin
  ```
* **macOS**:
  ```bash
  brew install tesseract tesseract-lang
  ```

### Step 2: Install OpenBharatOCR in the Python Environment
```bash
# Windows PowerShell
.\venv\Scripts\pip install openbharatocr

# Linux / macOS
source venv/bin/activate
pip install openbharatocr
```

### Step 3: Run the Screening Server
```bash
# Start Streamlit UI
.\venv\Scripts\streamlit run frontend/app.py

# Start FastAPI Backend
.\venv\Scripts\uvicorn api.orchestrator:app --host 0.0.0.0 --port 8000
```

---

## 4. Production Docker Deployment

For Land Border Checkpoint Kiosks (SSB field deployment), use the included container recipe:

```dockerfile
FROM python:3.11-slim

# Install system dependencies & Tesseract C++ binary
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libzbar0 \
    tesseract-ocr \
    tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir openbharatocr

COPY . .
EXPOSE 8501 8000

CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```
