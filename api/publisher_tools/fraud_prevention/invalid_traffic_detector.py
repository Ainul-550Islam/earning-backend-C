# api/publisher_tools/fraud_prevention/invalid_traffic_detector.py
"""
Invalid Traffic Detector — Multi-layer IVT detection system।
Bot, click fraud, impression fraud, device farm সব detect করে।
"""
import re
import hashlib
from typing import Dict, List, Tuple
from decimal import Decimal

from django.core.cache import cache


# ──────────────────────────────────────────────────────────────────────────────
# KNOWN BAD PATTERNS
# ──────────────────────────────────────────────────────────────────────────────

BOT_USER_AGENTS = [
    'googlebot', 'bingbot', 'slurp', 'duckduckbot', 'baidu',
    'yandexbot', 'sogou', 'exabot', 'facebot', 'ia_archiver',
    'wget', 'curl', 'python-requests', 'java/', 'scrapy',
    'selenium', 'phantomjs', 'headlesschrome', 'puppeteer',
    'playwright', 'zombie.js', 'casperjs',
]

DATACENTER_IP_RANGES = [
    '104.16.', '104.17.', '104.18.', '104.19.',  # Cloudflare
    '13.', '52.', '54.',  # AWS
    '35.', '34.',  # GCP
    '40.', '20.',  # Azure
]

SUSPICIOUS_CLICK_THRESHOLD = 10   # clicks per minute per IP
VELOCITY_WINDOW_SECONDS    = 60


# ──────────────────────────────────────────────────────────────────────────────
# DETECTION FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def analyze_user_agent(user_agent: str) -> Dict:
    """User agent analyze করে bot কিনা বলে"""
    if not user_agent:
        return {'is_bot': True, 'reason': 'empty_user_agent', 'score': 80}

    ua_lower = user_agent.lower()

    # Known bot check
    for bot in BOT_USER_AGENTS:
        if bot in ua_lower:
            return {'is_bot': True, 'reason': f'known_bot_{bot}', 'score': 95}

    # Suspicious patterns
    suspicious_patterns = [
        (r'bot', 20),
        (r'crawler', 20),
        (r'spider', 20),
        (r'scraper', 20),
        (r'headless', 30),
        (r'automated', 25),
        (r'^mozilla/4\.0 \(compatible\)$', 40),  # Very old/generic UA
    ]

    score = 0
    reasons = []
    for pattern, points in suspicious_patterns:
        if re.search(pattern, ua_lower):
            score += points
            reasons.append(pattern)

    return {
        'is_bot': score >= 50,
        'score': min(100, score),
        'reasons': reasons,
    }


def check_ip_reputation(ip_address: str) -> Dict:
    """
    IP reputation check করে।
    Datacenter IPs, known VPN/proxy ranges check করে।
    Production-এ MaxMind বা ipinfo.io API use করা উচিত।
    """
    if not ip_address:
        return {'score': 50, 'is_suspicious': True, 'reason': 'no_ip'}

    score = 0
    flags = []

    # Datacenter IP check
    for range_prefix in DATACENTER_IP_RANGES:
        if ip_address.startswith(range_prefix):
            score += 40
            flags.append('datacenter_ip')
            break

    # Localhost / private IP
    private_prefixes = ['127.', '10.', '192.168.', '172.16.']
    for prefix in private_prefixes:
        if ip_address.startswith(prefix):
            score += 30
            flags.append('private_ip')
            break

    # Check blocked IPs cache
    if cache.get(f'blocked_ip:{ip_address}'):
        score += 90
        flags.append('manually_blocked')

    # Check abuse list cache
    if cache.get(f'abuse_ip:{ip_address}'):
        score += 60
        flags.append('known_abuser')

    return {
        'ip_address':   ip_address,
        'score':        min(100, score),
        'is_suspicious': score >= 40,
        'flags':        flags,
    }


def check_click_velocity(
    user_identifier: str,
    ad_unit_id: str,
    window_seconds: int = VELOCITY_WINDOW_SECONDS,
) -> Dict:
    """
    Click velocity check করে — rapid clicking detect করে।
    user_identifier: IP + device_id hash
    """
    cache_key = f'click_velocity:{user_identifier}:{ad_unit_id}'
    click_count = cache.get(cache_key, 0)
    click_count += 1
    cache.set(cache_key, click_count, window_seconds)

    is_suspicious = click_count > SUSPICIOUS_CLICK_THRESHOLD
    score = min(100, click_count * 10) if is_suspicious else 0

    return {
        'click_count_in_window': click_count,
        'is_suspicious': is_suspicious,
        'score': score,
        'threshold': SUSPICIOUS_CLICK_THRESHOLD,
    }


def check_device_fingerprint(device_data: dict) -> Dict:
    """
    Device fingerprint analyze করে।
    Device farm, emulator, rooted device detect করে।
    """
    score = 0
    flags = []

    # Check for emulator indicators
    device_model = device_data.get('device_model', '').lower()
    device_name  = device_data.get('device_name', '').lower()

    emulator_patterns = ['emulator', 'sdk', 'genymotion', 'vbox', 'virtual', 'bluestacks']
    for pattern in emulator_patterns:
        if pattern in device_model or pattern in device_name:
            score += 60
            flags.append('emulator_detected')
            break

    # Missing device info
    if not device_data.get('device_model'):
        score += 20
        flags.append('missing_device_model')

    if not device_data.get('device_os'):
        score += 15
        flags.append('missing_os')

    # VPN/Proxy flags
    if device_data.get('is_vpn_detected'):
        score += 30
        flags.append('vpn_detected')

    if device_data.get('is_proxy_detected'):
        score += 40
        flags.append('proxy_detected')

    if device_data.get('is_tor_detected'):
        score += 70
        flags.append('tor_detected')

    return {
        'score': min(100, score),
        'is_suspicious': score >= 50,
        'flags': flags,
    }


def calculate_composite_fraud_score(
    ua_result: Dict,
    ip_result: Dict,
    velocity_result: Dict = None,
    device_result: Dict = None,
) -> Tuple[int, str]:
    """
    সব signals combine করে composite fraud score calculate করে।
    Returns: (score 0-100, primary_reason)
    """
    weights = {
        'ua':       0.25,
        'ip':       0.30,
        'velocity': 0.25,
        'device':   0.20,
    }

    weighted_score = (
        ua_result.get('score', 0) * weights['ua'] +
        ip_result.get('score', 0) * weights['ip'] +
        (velocity_result.get('score', 0) if velocity_result else 0) * weights['velocity'] +
        (device_result.get('score', 0) if device_result else 0) * weights['device']
    )

    composite = min(100, round(weighted_score))

    # Primary reason
    max_score = max(
        ua_result.get('score', 0),
        ip_result.get('score', 0),
        velocity_result.get('score', 0) if velocity_result else 0,
        device_result.get('score', 0) if device_result else 0,
    )

    if max_score == ua_result.get('score', 0):
        primary_reason = ua_result.get('reason', ua_result.get('reasons', ['bot'])[0] if ua_result.get('reasons') else 'bot')
    elif max_score == ip_result.get('score', 0):
        primary_reason = ip_result.get('flags', ['suspicious_ip'])[0] if ip_result.get('flags') else 'suspicious_ip'
    elif velocity_result and max_score == velocity_result.get('score', 0):
        primary_reason = 'click_fraud'
    else:
        primary_reason = 'suspicious_device'

    return composite, primary_reason


def detect_invalid_traffic(request_data: dict) -> Dict:
    """
    Full IVT detection pipeline।
    সব signals analyze করে final verdict দেয়।
    """
    user_agent   = request_data.get('user_agent', '')
    ip_address   = request_data.get('ip_address', '')
    device_data  = request_data.get('device', {})
    ad_unit_id   = request_data.get('ad_unit_id', '')
    event_type   = request_data.get('event_type', 'impression')  # impression/click

    # Run individual checks
    ua_result      = analyze_user_agent(user_agent)
    ip_result      = check_ip_reputation(ip_address)
    device_result  = check_device_fingerprint(device_data)

    velocity_result = None
    if event_type == 'click':
        user_key = hashlib.md5(f"{ip_address}:{device_data.get('device_id', '')}".encode()).hexdigest()
        velocity_result = check_click_velocity(user_key, ad_unit_id)

    # Composite score
    fraud_score, primary_reason = calculate_composite_fraud_score(
        ua_result, ip_result, velocity_result, device_result
    )

    # Determine traffic type
    traffic_type = 'suspicious'
    if ua_result.get('is_bot'):
        traffic_type = 'bot'
    elif device_result.get('flags') and 'emulator_detected' in device_result.get('flags', []):
        traffic_type = 'emulator'
    elif device_result.get('flags') and 'vpn_detected' in device_result.get('flags', []):
        traffic_type = 'vpn'
    elif device_result.get('flags') and 'proxy_detected' in device_result.get('flags', []):
        traffic_type = 'proxy'
    elif velocity_result and velocity_result.get('is_suspicious'):
        traffic_type = 'click_fraud'
    elif ip_result.get('flags') and 'datacenter_ip' in ip_result.get('flags', []):
        traffic_type = 'bot'

    # Severity
    if fraud_score >= 80:
        severity = 'critical'
    elif fraud_score >= 60:
        severity = 'high'
    elif fraud_score >= 40:
        severity = 'medium'
    else:
        severity = 'low'

    return {
        'fraud_score':    fraud_score,
        'traffic_type':   traffic_type,
        'severity':       severity,
        'primary_reason': primary_reason,
        'is_invalid':     fraud_score >= 50,
        'should_block':   fraud_score >= 80,
        'signals': {
            'user_agent': ua_result,
            'ip':         ip_result,
            'velocity':   velocity_result,
            'device':     device_result,
        },
        'confidence_score': min(100, fraud_score + 10),  # Slight boost for confidence
    }
