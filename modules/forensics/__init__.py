"""
Forensics Module
----------------
ela.py   - Error Level Analysis (full doc, region-restricted, visa stamp)
exif.py  - EXIF metadata inspection for editing tool signatures
"""

from .ela import run_ela
from .exif import inspect_exif
