"""
api/ai_engine/ANOMALY_DETECTION/network_anomaly_detector.py
============================================================
Network Traffic Anomaly Detector।
DDoS, bot traffic, scraping, API abuse detection।
Marketing site protection এবং API security।
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class NetworkAnomalyDetector:
    """
    Network-level anomaly detection।
    IP reputation, traffic patterns, request signatures।
    """

    # Known attack patterns
    BOT_USER_AGENTS = [
        'bot', 'crawler', 'spider', 'scraper', 'python-requests',
        'curl/', 'wget/', 'Go-http-client', 'libwww',
    ]

    def detect(self, traffic_data: dict) -> dict:
        """Network traffic analyze করো।"""
        rps         = traffic_data.get('requests_per_second', 0)
        unique_ips  = traffic_data.get('unique_ips_per_min', 100)
        error_rate  = traffic_data.get('error_rate_pct', 0)
        bot_score   = traffic_data.get('bot_score', 0.0)
        geo_anomaly = traffic_data.get('geo_anomaly', False)
        ua          = traffic_data.get('user_agent', '').lower()

        score  = 0.0
        flags  = []
        attack_type = None

        # DDoS detection
        if rps > 10000:
            score += 0.8; flags.append('ddos_suspected'); attack_type = 'ddos'
        elif rps > 5000:
            score += 0.6; flags.append('high_traffic_spike')
        elif rps > 1000:
            score += 0.3; flags.append('elevated_traffic')

        # Bot detection
        if bot_score > 0.80:
            score += 0.5; flags.append('bot_traffic_high'); attack_type = attack_type or 'bot'
        elif bot_score > 0.50:
            score += 0.3; flags.append('bot_traffic_suspected')

        # User agent check
        if any(bot_ua in ua for bot_ua in self.BOT_USER_AGENTS):
            score += 0.4; flags.append('bot_user_agent')

        # Error rate spike (scraping/fuzzing)
        if error_rate > 50:
            score += 0.4; flags.append('high_error_rate_attack')
        elif error_rate > 20:
            score += 0.2; flags.append('elevated_error_rate')

        # Geo anomaly (traffic from unusual countries)
        if geo_anomaly:
            score += 0.2; flags.append('geographic_anomaly')

        # Concentrated traffic (low unique IPs)
        if rps > 100 and unique_ips < 5:
            score += 0.5; flags.append('concentrated_source')

        score = min(1.0, score)
        return {
            'anomaly_score':   round(score, 4),
            'is_attack':       score >= 0.70,
            'attack_type':     attack_type,
            'flags':           flags,
            'severity':        self._severity(score),
            'recommended_action': self._action(score, attack_type),
            'metrics': {
                'rps':        rps,
                'unique_ips': unique_ips,
                'error_rate': error_rate,
                'bot_score':  bot_score,
            }
        }

    def _severity(self, score: float) -> str:
        if score >= 0.90: return 'critical'
        if score >= 0.70: return 'high'
        if score >= 0.40: return 'medium'
        return 'low'

    def _action(self, score: float, attack_type: str) -> str:
        if score >= 0.90:
            return 'Block IP range immediately + enable rate limiting'
        if attack_type == 'ddos':
            return 'Enable CDN DDoS protection + notify ops team'
        if attack_type == 'bot':
            return 'Enable CAPTCHA + block suspicious user agents'
        if score >= 0.50:
            return 'Increase rate limiting + monitor closely'
        return 'Log and monitor'

    def analyze_ip_reputation(self, ip_address: str,
                               known_bad_ips: List[str] = None) -> dict:
        """IP address reputation check।"""
        known_bad_ips = known_bad_ips or []

        if ip_address in known_bad_ips:
            return {'reputation': 'malicious', 'score': 0.95, 'block': True}

        # Check reserved/private ranges
        import ipaddress
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            if ip_obj.is_private:
                return {'reputation': 'private', 'score': 0.0, 'block': False}
            if ip_obj.is_loopback:
                return {'reputation': 'loopback', 'score': 0.0, 'block': False}
        except ValueError:
            return {'reputation': 'invalid', 'score': 0.5, 'block': False}

        return {'reputation': 'unknown', 'score': 0.1, 'block': False}

    def rate_limit_decision(self, user_id: str, action: str,
                              requests_count: int, window_seconds: int = 60) -> dict:
        """Rate limiting decision।"""
        limits = {
            'api_call':       100,
            'login_attempt':  5,
            'offer_click':    200,
            'withdrawal':     3,
            'recommendation': 50,
            'prediction':     100,
        }

        limit = limits.get(action, 60)
        is_exceeded = requests_count > limit

        return {
            'user_id':       user_id,
            'action':        action,
            'requests':      requests_count,
            'limit':         limit,
            'window_sec':    window_seconds,
            'rate_exceeded': is_exceeded,
            'block':         requests_count > limit * 3,
            'retry_after_s': window_seconds if is_exceeded else 0,
        }

    def detect_credential_stuffing(self, login_data: dict) -> dict:
        """Credential stuffing attack detection।"""
        failed_rate     = login_data.get('failed_login_rate', 0)
        unique_usernames = login_data.get('unique_usernames', 1)
        requests_per_min = login_data.get('login_requests_per_min', 0)
        distributed_ips  = login_data.get('source_ip_count', 1)

        score  = 0.0
        flags  = []

        if failed_rate > 0.80:
            score += 0.5; flags.append('high_failure_rate')
        if unique_usernames > 100 and requests_per_min > 50:
            score += 0.4; flags.append('mass_credential_testing')
        if distributed_ips > 50 and requests_per_min > 100:
            score += 0.3; flags.append('distributed_attack')

        return {
            'is_credential_stuffing': score >= 0.60,
            'score':   round(min(1.0, score), 4),
            'flags':   flags,
            'action':  'Block + force password reset for affected accounts' if score >= 0.60 else 'Monitor',
        }
