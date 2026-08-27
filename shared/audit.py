"""
Audit Log  -  Digital Trail of Screening Events.

Addresses PS requirement: "Create a digital trail for investigations
and intelligence analysis."

Stores a timestamped record of every document screening event including:
  - Document type and number
  - Extracted name
  - Risk score and level
  - Which checks failed
  - Checkpoint identifier

Does NOT store:
  - Document photos
  - Live face captures
  - Biometric images of any kind

Only field values and scores are stored, consistent with the zero-image-
storage principle and avoiding biometric data regulation requirements.
"""

import json
import os
import sqlite3
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "audit.db")


def log_screening(
    doc_type: str,
    doc_number: str,
    name: str,
    risk_level: str,
    total_score: float,
    failed_checks: list,
    checkpoint_id: str = "default",
    officer_id: str = "unknown",
    summary: str = "",
) -> int:
    """
    Log a completed screening event to the audit database.

    Args:
        doc_type:      'Aadhaar' | 'Passport' | 'Visa'
        doc_number:    Document identifier number.
        name:          Traveler name from document.
        risk_level:    'HIGH' | 'MEDIUM' | 'LOW' | 'PASS'
        total_score:   Weighted risk score (0–100).
        failed_checks: List of check names that failed.
        checkpoint_id: Identifier for the screening post.
        officer_id:    Officer who conducted the screening.
        summary:       LLM-generated plain-language summary.

    Returns:
        Audit record ID (int).
    """
    db = _get_db()
    cur = db.execute(
        """
        INSERT INTO audit_log
          (timestamp, doc_type, doc_number, name, risk_level, total_score,
           failed_checks, checkpoint_id, officer_id, summary)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """,
        (
            datetime.utcnow().isoformat(),
            doc_type,
            doc_number,
            name,
            risk_level,
            round(total_score, 1),
            json.dumps(failed_checks),
            checkpoint_id,
            officer_id,
            summary,
        ),
    )
    db.commit()
    record_id = cur.lastrowid
    db.close()
    return record_id


def get_recent_screenings(limit: int = 50, checkpoint_id: str = None) -> list:
    """Retrieve recent screening records for display/analysis."""
    db = _get_db()
    if checkpoint_id:
        cur = db.execute(
            "SELECT * FROM audit_log WHERE checkpoint_id=? ORDER BY timestamp DESC LIMIT ?",
            (checkpoint_id, limit),
        )
    else:
        cur = db.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    db.close()
    return rows


def get_flagged_screenings(risk_levels: list = None) -> list:
    """Retrieve all FLAGGED/REVIEW risk screenings for investigation."""
    if risk_levels is None:
        risk_levels = ["FLAGGED", "REVIEW", "HIGH", "MEDIUM"]
    placeholders = ",".join("?" * len(risk_levels))
    db = _get_db()
    cur = db.execute(
        f"SELECT * FROM audit_log WHERE risk_level IN ({placeholders}) ORDER BY timestamp DESC",
        risk_levels,
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    db.close()
    return rows


def _get_db() -> sqlite3.Connection:
    db = sqlite3.connect(_DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT NOT NULL,
            doc_type      TEXT NOT NULL,
            doc_number    TEXT,
            name          TEXT,
            risk_level    TEXT NOT NULL,
            total_score   REAL NOT NULL,
            failed_checks TEXT,
            checkpoint_id TEXT,
            officer_id    TEXT,
            summary       TEXT
        )
    """)
    db.commit()
    # Migrate existing entries to uppercase doc_types
    try:
        db.execute("UPDATE audit_log SET doc_type = UPPER(doc_type)")
        db.commit()
    except Exception:
        pass
    return db
