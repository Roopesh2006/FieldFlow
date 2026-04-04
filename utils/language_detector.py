"""
KisanVaani — Language Detector
Auto-detects Indian language from text using script analysis
"""

import re
import logging

logger = logging.getLogger(__name__)

# Unicode script ranges for Indian languages
SCRIPT_PATTERNS = {
    "hi": re.compile(r'[\u0900-\u097F]'),      # Devanagari (Hindi/Marathi)
    "ta": re.compile(r'[\u0B80-\u0BFF]'),      # Tamil
    "te": re.compile(r'[\u0C00-\u0C7F]'),      # Telugu
    "kn": re.compile(r'[\u0C80-\u0CFF]'),      # Kannada
    "bn": re.compile(r'[\u0980-\u09FF]'),      # Bengali
    "gu": re.compile(r'[\u0A80-\u0AFF]'),      # Gujarati
    "pa": re.compile(r'[\u0A00-\u0A7F]'),      # Punjabi (Gurmukhi)
    "mr": re.compile(r'[\u0900-\u097F]'),      # Marathi (also Devanagari)
}

# Hindi keywords to distinguish Hindi vs Marathi in Devanagari
HINDI_MARKERS = ["मेरे", "क्या", "कैसे", "आज", "फसल", "पत्ते", "कीड़े"]
MARATHI_MARKERS = ["माझ्या", "काय", "कसे", "आज", "पीक", "पाने", "किडे"]


async def detect_language(text: str, fallback: str = "hi") -> str:
    """
    Detect language from text using Unicode script analysis.
    Falls back to farmer's saved language preference.
    """
    if not text:
        return fallback

    # Check each script
    for lang, pattern in SCRIPT_PATTERNS.items():
        if lang in ("hi", "mr"):
            continue  # Handle Devanagari separately
        if pattern.search(text):
            logger.info(f"Detected language: {lang}")
            return lang

    # Devanagari — distinguish Hindi vs Marathi
    if SCRIPT_PATTERNS["hi"].search(text):
        marathi_score = sum(1 for m in MARATHI_MARKERS if m in text)
        hindi_score = sum(1 for m in HINDI_MARKERS if m in text)
        detected = "mr" if marathi_score > hindi_score else "hi"
        logger.info(f"Detected Devanagari language: {detected}")
        return detected

    # Latin script — English
    if re.search(r'[a-zA-Z]', text) and len(re.findall(r'[a-zA-Z]', text)) > len(text) * 0.5:
        return "en"

    return fallback
