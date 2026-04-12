# kyc/utils/risk_utils.py  ── WORLD #1
"""Risk scoring utility functions"""
import logging

logger = logging.getLogger(__name__)


def calculate_name_similarity(name1: str, name2: str) -> float:
    """SequenceMatcher-based name similarity 0.0–1.0"""
    if not name1 or not name2:
        return 0.0
    from difflib import SequenceMatcher
    return round(SequenceMatcher(None, name1.strip().lower(), name2.strip().lower()).ratio(), 4)


def is_under_age(date_of_birth, min_age: int = 18) -> bool:
    """Return True if user is under min_age."""
    if not date_of_birth:
        return False
    from datetime import date
    age = (date.today() - date_of_birth).days / 365.25
    return age < min_age


def score_from_factors(factors: dict) -> int:
    """
    Compute overall risk score 0-100 from a factor dict.
    factors = {'name_mismatch': True, 'age_under_18': False, ...}
    """
    WEIGHTS = {
        'name_mismatch':        30,
        'age_under_18':         50,
        'duplicate_kyc':        40,
        'low_ocr_confidence':   20,
        'face_mismatch':        35,
        'low_image_clarity':    20,
        'blacklisted':          60,
        'vpn_detected':         25,
        'multiple_attempts':    15,
        'suspicious_document':  45,
        'liveness_failure':     30,
    }
    score = sum(WEIGHTS.get(key, 0) for key, val in factors.items() if val)
    return min(score, 100)


def risk_level_from_score(score: int) -> str:
    if score <= 30:   return 'low'
    elif score <= 60: return 'medium'
    elif score <= 80: return 'high'
    return 'critical'


def risk_color(level: str) -> str:
    return {'low': '#4CAF50', 'medium': '#FF9800', 'high': '#F44336', 'critical': '#B71C1C'}.get(level, '#9E9E9E')


def build_risk_summary(kyc) -> dict:
    """Build a complete risk summary dict for a KYC object."""
    factors = {}

    # Name check
    if kyc.extracted_name and kyc.full_name:
        sim = calculate_name_similarity(kyc.extracted_name, kyc.full_name)
        factors['name_mismatch'] = sim < 0.80

    # Age check
    if kyc.date_of_birth:
        factors['age_under_18'] = is_under_age(kyc.date_of_birth)

    # Duplicate
    factors['duplicate_kyc'] = kyc.is_duplicate

    # OCR confidence
    factors['low_ocr_confidence'] = kyc.ocr_confidence < 0.70

    # Face verified
    factors['face_mismatch'] = not kyc.is_face_verified

    score = score_from_factors(factors)
    level = risk_level_from_score(score)

    return {
        'score':   score,
        'level':   level,
        'color':   risk_color(level),
        'factors': [k for k, v in factors.items() if v],
        'details': factors,
    }
