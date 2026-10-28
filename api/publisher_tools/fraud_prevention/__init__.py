# publisher_tools/fraud_prevention/__init__.py
# ============================================================
# Exports all fraud detection helpers so services.py can import
# cleanly:
#   from .fraud_prevention import detect_invalid_traffic, block_ip
# ============================================================
from .invalid_traffic_detector import (
    analyze_user_agent,
    check_ip_reputation,
    check_click_velocity,
    check_device_fingerprint,
    calculate_composite_fraud_score,
    detect_invalid_traffic,
    BOT_USER_AGENTS,
    DATACENTER_IP_RANGES,
    SUSPICIOUS_CLICK_THRESHOLD,
)
from .ip_blacklist import (
    is_ip_blocked,
    block_ip,
    unblock_ip,
    get_ip_reputation,
)
from .fraud_alert import (
    create_fraud_alert,
    resolve_fraud_alert,
    get_active_fraud_alerts,
)

# Optional heavy modules — import lazily to avoid circular dep
def get_hypothesis_tester():
    from .hypothesis_tester import HypothesisTester
    return HypothesisTester

def get_network_tester():
    from .network_testing import NetworkTester
    return NetworkTester

__all__ = [
    'analyze_user_agent',
    'check_ip_reputation',
    'check_click_velocity',
    'check_device_fingerprint',
    'calculate_composite_fraud_score',
    'detect_invalid_traffic',
    'BOT_USER_AGENTS',
    'DATACENTER_IP_RANGES',
    'SUSPICIOUS_CLICK_THRESHOLD',
    'is_ip_blocked',
    'block_ip',
    'unblock_ip',
    'get_ip_reputation',
    'create_fraud_alert',
    'resolve_fraud_alert',
    'get_active_fraud_alerts',
]
