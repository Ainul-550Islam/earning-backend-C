"""
IP Risk Score Calculator
========================
Aggregates signals from all detection engines into a single risk score.
"""
import logging
from ..detection_engines.vpn_detector import VPNDetector
from ..detection_engines.tor_detector import TorDetector
from ..detection_engines.proxy_detector import ProxyDetector, DatacenterDetector
from ..ip_intelligence.ip_asn_lookup import ASNLookup
from ..enums import RiskLevel

logger = logging.getLogger(__name__)

SIGNAL_WEIGHTS = {
    'tor': 45,
    'vpn': 30,
    'proxy': 20,
    'datacenter': 10,
    'abuse_reports': 15,   # external feed score * 0.15
    'fraud_history': 10,
}


class IPRiskScoreCalculator:
    """
    Calculates a composite 0-100 risk score for an IP address
    by running all available detection engines.
    """

    def __init__(self, ip_address: str, request_headers: dict = None):
        self.ip_address = ip_address
        self.request_headers = request_headers or {}
        self.breakdown = {}

    def calculate(self) -> dict:
        """Run all checks and return score + breakdown."""
        total = 0

        # Tor check (highest weight)
        tor_result = TorDetector.detect(self.ip_address)
        tor_score = SIGNAL_WEIGHTS['tor'] if tor_result['is_tor'] else 0
        self.breakdown['tor'] = {'detected': tor_result['is_tor'], 'score': tor_score}
        total += tor_score

        # VPN check
        vpn_result = VPNDetector(self.ip_address).detect()
        vpn_score = int(SIGNAL_WEIGHTS['vpn'] * vpn_result['confidence'])
        self.breakdown['vpn'] = {'detected': vpn_result['is_vpn'], 'confidence': vpn_result['confidence'], 'score': vpn_score}
        total += vpn_score

        # Proxy check
        proxy_result = ProxyDetector(self.ip_address, self.request_headers).detect()
        proxy_score = int(SIGNAL_WEIGHTS['proxy'] * proxy_result['confidence'])
        self.breakdown['proxy'] = {'detected': proxy_result['is_proxy'], 'score': proxy_score}
        total += proxy_score

        # Datacenter check
        asn_info = ASNLookup.lookup(self.ip_address)
        is_dc = DatacenterDetector.is_datacenter(self.ip_address, asn_info.get('asn', ''))
        dc_score = SIGNAL_WEIGHTS['datacenter'] if is_dc else 0
        self.breakdown['datacenter'] = {'detected': is_dc, 'score': dc_score}
        total += dc_score

        final_score = min(int(total), 100)
        risk_level = self._get_level(final_score)

        return {
            'ip_address': self.ip_address,
            'risk_score': final_score,
            'risk_level': risk_level,
            'is_vpn': vpn_result['is_vpn'],
            'is_proxy': proxy_result['is_proxy'],
            'is_tor': tor_result['is_tor'],
            'is_datacenter': is_dc,
            'vpn_provider': vpn_result.get('vpn_provider', ''),
            'proxy_type': proxy_result.get('proxy_type', ''),
            'asn': asn_info.get('asn', ''),
            'isp': asn_info.get('isp', ''),
            'country_code': asn_info.get('country', ''),
            'city': asn_info.get('city', ''),
            'breakdown': self.breakdown,
        }

    @staticmethod
    def _get_level(score: int) -> str:
        if score <= 20:
            return RiskLevel.VERY_LOW
        elif score <= 40:
            return RiskLevel.LOW
        elif score <= 60:
            return RiskLevel.MEDIUM
        elif score <= 80:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL
