"""
api/ai_engine/ANOMALY_DETECTION/fraud_anomaly_detector.py
==========================================================
Fraud Anomaly Detector — comprehensive multi-signal fraud detection।
Click fraud, conversion fraud, account takeover, payment fraud।
Real-time scoring + pattern analysis + network analysis।
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FraudAnomalyDetector:
    """
    Comprehensive fraud detection engine।
    Combines multiple anomaly detectors for maximum coverage।
    """

    def detect(self, event_data: dict, user=None,
               tenant_id=None) -> dict:
        """
        Multi-signal fraud detection।
        Returns overall fraud score + breakdown by signal type।
        """
        scores = {
            'ip_signals':       self._ip_score(event_data),
            'device_signals':   self._device_score(event_data),
            'behavior_signals': self._behavior_score(event_data),
            'velocity_signals': self._velocity_score(event_data),
            'network_signals':  self._network_score(event_data),
        }

        weights = {
            'ip_signals':       0.25,
            'device_signals':   0.20,
            'behavior_signals': 0.25,
            'velocity_signals': 0.20,
            'network_signals':  0.10,
        }

        overall = sum(scores[k] * weights[k] for k in scores)
        overall = min(1.0, overall)

        severity = (
            'critical' if overall >= 0.90 else
            'high'     if overall >= 0.75 else
            'medium'   if overall >= 0.50 else
            'low'
        )

        flags    = self._generate_flags(scores, event_data)
        action   = self._recommend_action(overall, severity)

        # Log high-confidence fraud
        if overall >= 0.75:
            self._log_anomaly(overall, severity, flags, event_data, user, tenant_id)

        return {
            'fraud_score':        round(overall, 4),
            'is_fraud':           overall >= 0.70,
            'severity':           severity,
            'signal_scores':      {k: round(v, 4) for k, v in scores.items()},
            'flags':              flags,
            'recommended_action': action,
            'threshold':          0.70,
        }

    def _ip_score(self, d: dict) -> float:
        score = 0.0
        if d.get('is_vpn'):          score += 0.35
        if d.get('is_proxy'):        score += 0.40
        if d.get('is_tor'):          score += 0.60
        if d.get('ip_blacklisted'):  score += 0.80
        if d.get('ip_reputation', 0) < 0.3: score += 0.20
        return min(1.0, score)

    def _device_score(self, d: dict) -> float:
        score = 0.0
        device_count = int(d.get('device_count', 1))
        if device_count >= 10:       score += 0.60
        elif device_count >= 5:      score += 0.35
        elif device_count >= 3:      score += 0.15
        if d.get('emulator'):        score += 0.55
        if d.get('rooted'):          score += 0.30
        if d.get('cloned_app'):      score += 0.70
        return min(1.0, score)

    def _behavior_score(self, d: dict) -> float:
        score = 0.0
        account_age = int(d.get('account_age_days', 30))
        if account_age < 1:          score += 0.50
        elif account_age < 7:        score += 0.25
        elif account_age < 30:       score += 0.10

        if d.get('same_ip_multi_accounts'): score += 0.50
        if d.get('referral_abuse'):         score += 0.40
        if d.get('task_repeat_same'):       score += 0.30
        return min(1.0, score)

    def _velocity_score(self, d: dict) -> float:
        score = 0.0
        clicks_1h = int(d.get('clicks_per_hour', 0))
        if clicks_1h > 500:    score += 0.70
        elif clicks_1h > 200:  score += 0.50
        elif clicks_1h > 100:  score += 0.30
        elif clicks_1h > 50:   score += 0.15

        tasks_today = int(d.get('tasks_completed_today', 0))
        if tasks_today > 100:  score += 0.50
        elif tasks_today > 50: score += 0.25

        rps = float(d.get('requests_per_second', 0))
        if rps > 20:           score += 0.60
        elif rps > 10:         score += 0.35
        return min(1.0, score)

    def _network_score(self, d: dict) -> float:
        score = 0.0
        if d.get('ip_country') != d.get('account_country') and d.get('account_country'):
            score += 0.30
        if d.get('known_bad_asn'):      score += 0.50
        if d.get('datacenter_ip'):      score += 0.35
        if d.get('shared_hosting'):     score += 0.20
        return min(1.0, score)

    def _generate_flags(self, scores: dict, data: dict) -> List[str]:
        flags = []
        if scores['ip_signals'] >= 0.5:
            if data.get('is_tor'):         flags.append('tor_detected')
            elif data.get('is_proxy'):     flags.append('proxy_detected')
            elif data.get('is_vpn'):       flags.append('vpn_detected')
        if scores['device_signals'] >= 0.5:
            if data.get('emulator'):       flags.append('emulator_detected')
            if data.get('cloned_app'):     flags.append('cloned_app')
        if scores['behavior_signals'] >= 0.5:
            flags.append('suspicious_behavior_pattern')
        if scores['velocity_signals'] >= 0.5:
            flags.append('high_velocity_activity')
        if data.get('account_age_days', 30) < 1:
            flags.append('new_account_high_activity')
        return flags

    def _recommend_action(self, score: float, severity: str) -> str:
        actions = {
            'critical': 'block_immediately',
            'high':     'flag_and_restrict',
            'medium':   'require_additional_verification',
            'low':      'monitor_closely',
        }
        return actions.get(severity, 'monitor_closely')

    def _log_anomaly(self, score, severity, flags, data, user, tenant_id):
        try:
            from ..models import AnomalyDetectionLog
            AnomalyDetectionLog.objects.create(
                anomaly_type='fraud_detection',
                severity=severity,
                user=user,
                anomaly_score=score,
                threshold=0.70,
                evidence_data={'flags': flags, 'signals': data},
                auto_action_taken=self._recommend_action(score, severity),
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error(f"Fraud anomaly log error: {e}")

    def batch_detect(self, events: List[Dict], tenant_id=None) -> List[Dict]:
        """Multiple events এর fraud detection एकसाथे।"""
        results = []
        for event in events:
            result = self.detect(event, tenant_id=tenant_id)
            results.append({'event': event, **result})
        return sorted(results, key=lambda x: x['fraud_score'], reverse=True)

    def explain(self, event_data: dict) -> dict:
        """Fraud decision explain করো।"""
        result   = self.detect(event_data)
        signals  = result['signal_scores']
        top_signal = max(signals, key=signals.get)

        explanations = {
            'ip_signals':       f"IP/Network risk (VPN/Proxy/Tor): {signals['ip_signals']:.1%}",
            'device_signals':   f"Device risk (emulator/clone): {signals['device_signals']:.1%}",
            'behavior_signals': f"Behavioral anomaly: {signals['behavior_signals']:.1%}",
            'velocity_signals': f"Activity velocity too high: {signals['velocity_signals']:.1%}",
            'network_signals':  f"Network location risk: {signals['network_signals']:.1%}",
        }

        return {
            'fraud_score':     result['fraud_score'],
            'primary_reason':  explanations[top_signal],
            'all_reasons':     explanations,
            'flags':           result['flags'],
            'human_readable':  f"Fraud probability {result['fraud_score']:.1%} — primarily due to {top_signal.replace('_', ' ')}.",
        }
