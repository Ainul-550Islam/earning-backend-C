# api/publisher_tools/fraud_prevention/geo_validation.py
"""Geo Validation — Geographic fraud detection."""
from typing import Dict


HIGH_RISK_COUNTRIES = ["KP", "CU", "IR", "SY", "SD", "MM"]
KNOWN_VPN_COUNTRIES = ["CH", "SE", "NO", "IS", "NL", "LU"]


def validate_geo(ip_country: str, claimed_country: str = None) -> Dict:
    """IP geo vs claimed geo validate করে।"""
    score = 0
    signals = []
    if ip_country in HIGH_RISK_COUNTRIES:
        score += 40; signals.append(f"high_risk_country:{ip_country}")
    if claimed_country and ip_country and ip_country != claimed_country:
        score += 50; signals.append(f"geo_mismatch:ip={ip_country},claimed={claimed_country}")
    if ip_country in KNOWN_VPN_COUNTRIES:
        score += 10; signals.append(f"vpn_country:{ip_country}")
    return {"score": score, "is_suspicious": score >= 40, "signals": signals, "ip_country": ip_country}


def detect_geo_impossible_travel(user_id: str, current_country: str, prev_country: str, time_diff_hours: float) -> bool:
    """Impossible travel detection — country change too fast।"""
    if not prev_country or prev_country == current_country:
        return False
    # If countries changed in less than 1 hour — likely VPN/fraud
    if time_diff_hours < 1 and prev_country != current_country:
        return True
    return False


def get_country_risk_score(country_code: str) -> int:
    risk_scores = {k: 80 for k in HIGH_RISK_COUNTRIES}
    risk_scores.update({k: 20 for k in KNOWN_VPN_COUNTRIES})
    return risk_scores.get(country_code.upper(), 0)


def is_country_allowed(country_code: str, allowed_list: list) -> bool:
    if not allowed_list or "ALL" in allowed_list:
        return True
    return country_code.upper() in [c.upper() for c in allowed_list]
