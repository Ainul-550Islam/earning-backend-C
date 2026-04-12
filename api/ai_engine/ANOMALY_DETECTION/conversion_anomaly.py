"""
api/ai_engine/ANOMALY_DETECTION/conversion_anomaly.py
======================================================
Conversion Rate Anomaly Detector।
Normal CVR pattern থেকে deviation detect করো।
Fraud conversion, bot traffic, offer abuse identify করো।
Marketing campaigns ও offer performance monitoring।
"""

import logging
import math
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ConversionAnomalyDetector:
    """
    Conversion rate anomaly detection engine।
    Signals: CVR spike, mass conversion, suspicious patterns।
    """

    # Thresholds
    CVR_SPIKE_THRESHOLD    = 3.0    # 3x normal CVR = suspicious
    EXTREME_CVR_THRESHOLD  = 5.0    # 5x = highly suspicious
    MAX_NORMAL_CVR         = 0.50   # >50% CVR is rarely organic
    MIN_VOLUME_FOR_STAT    = 50     # Statistical significance minimum
    ANOMALY_SCORE_THRESHOLD = 0.60

    def detect(self, conversion_data: dict) -> dict:
        """Conversion anomaly detect করো।"""
        cvr      = float(conversion_data.get('conversion_rate', 0))
        avg_cvr  = float(conversion_data.get('avg_cvr', 0.10))
        volume   = int(conversion_data.get('volume', 0))
        offer_id = conversion_data.get('offer_id', '')
        network  = conversion_data.get('network', '')

        score  = 0.0
        flags  = []

        # CVR ratio vs baseline
        if avg_cvr > 0 and volume >= self.MIN_VOLUME_FOR_STAT:
            ratio = cvr / avg_cvr
            if ratio >= self.EXTREME_CVR_THRESHOLD:
                score += 0.60; flags.append(f'cvr_spike_{ratio:.1f}x_extreme')
            elif ratio >= self.CVR_SPIKE_THRESHOLD:
                score += 0.40; flags.append(f'cvr_spike_{ratio:.1f}x_high')
            elif ratio >= 2.0:
                score += 0.20; flags.append(f'cvr_spike_{ratio:.1f}x_moderate')
            elif ratio <= 0.10:
                score += 0.25; flags.append('cvr_collapse_90pct')
            elif ratio <= 0.20:
                score += 0.15; flags.append('cvr_drop_80pct')

        # Absolute CVR too high
        if cvr > self.MAX_NORMAL_CVR and volume >= 100:
            score += 0.30; flags.append(f'unrealistic_cvr_{cvr:.1%}')

        # Mass conversion (high volume + high CVR)
        if volume > 10000 and cvr > 0.70:
            score += 0.40; flags.append('mass_conversion_bot_likely')

        # Low volume + high CVR (easy to fake)
        if 5 <= volume <= 30 and cvr >= 0.80:
            score += 0.25; flags.append('low_volume_high_cvr_suspicious')

        # Velocity check
        conversions_per_hour = conversion_data.get('conversions_per_hour', 0)
        if conversions_per_hour > 500:
            score += 0.35; flags.append('conversion_velocity_extreme')
        elif conversions_per_hour > 200:
            score += 0.20; flags.append('conversion_velocity_high')

        # Same device multiple conversions
        if conversion_data.get('same_device_count', 0) > 5:
            score += 0.30; flags.append('same_device_multi_conversion')

        # VPN/proxy users converting
        vpn_pct = float(conversion_data.get('vpn_user_pct', 0))
        if vpn_pct > 0.40:
            score += 0.25; flags.append(f'high_vpn_conversion_{vpn_pct:.0%}')

        score = min(1.0, score)
        severity = (
            'critical' if score >= 0.85 else
            'high'     if score >= 0.65 else
            'medium'   if score >= 0.45 else
            'low'
        )

        return {
            'anomaly_score':       round(score, 4),
            'is_anomaly':          score >= self.ANOMALY_SCORE_THRESHOLD,
            'severity':            severity,
            'flags':               flags,
            'cvr':                 round(cvr, 4),
            'avg_cvr':             round(avg_cvr, 4),
            'cvr_ratio':           round(cvr / max(avg_cvr, 0.001), 3),
            'volume':              volume,
            'offer_id':            offer_id,
            'network':             network,
            'threshold':           self.ANOMALY_SCORE_THRESHOLD,
            'recommended_action':  self._action(score, flags),
        }

    def _action(self, score: float, flags: List[str]) -> str:
        if score >= 0.85: return 'immediately_pause_offer_and_investigate'
        if score >= 0.65: return 'flag_for_manual_review_and_withhold_payout'
        if score >= 0.45: return 'monitor_closely_and_request_additional_verification'
        return 'log_and_continue_monitoring'

    def detect_batch(self, offers_data: List[Dict]) -> List[Dict]:
        """Multiple offers এর conversion anomaly একসাথে check করো।"""
        results = []
        for offer in offers_data:
            result = self.detect(offer)
            results.append(result)

        # Sort by anomaly score (highest first)
        return sorted(results, key=lambda x: x['anomaly_score'], reverse=True)

    def baseline_update(self, offer_id: str, new_cvr: float,
                         history: List[float]) -> dict:
        """
        Offer baseline CVR আপডেট করো।
        Exponential moving average ব্যবহার করো।
        """
        if not history:
            return {'new_baseline': new_cvr, 'method': 'first_observation'}

        alpha    = 0.1  # Slow update to avoid manipulation
        baseline = history[-1]
        updated  = alpha * new_cvr + (1 - alpha) * baseline

        return {
            'offer_id':     offer_id,
            'old_baseline': round(baseline, 4),
            'new_baseline': round(updated, 4),
            'new_observation': round(new_cvr, 4),
            'alpha':         alpha,
        }

    def statistical_significance(self, test_conversions: int, test_clicks: int,
                                   control_conversions: int, control_clicks: int) -> dict:
        """
        Test vs Control CVR statistical significance।
        Z-test for proportions।
        """
        if test_clicks == 0 or control_clicks == 0:
            return {'significant': False, 'reason': 'No clicks in one group'}

        p1 = test_conversions / test_clicks
        p2 = control_conversions / control_clicks

        p_pool = (test_conversions + control_conversions) / (test_clicks + control_clicks)
        se     = math.sqrt(p_pool * (1 - p_pool) * (1 / test_clicks + 1 / control_clicks))

        if se == 0:
            return {'significant': False, 'reason': 'Zero standard error'}

        z     = (p1 - p2) / se
        p_val = 2 * (1 - self._normal_cdf(abs(z)))

        return {
            'test_cvr':      round(p1, 4),
            'control_cvr':   round(p2, 4),
            'z_score':       round(z, 4),
            'p_value':       round(p_val, 6),
            'significant':   p_val < 0.05,
            'confidence':    round(1 - p_val, 4),
            'lift_pct':      round((p1 - p2) / max(p2, 0.001) * 100, 2),
        }

    def _normal_cdf(self, z: float) -> float:
        """Standard normal CDF approximation।"""
        t = 1 / (1 + 0.2316419 * abs(z))
        d = 0.3989423 * math.exp(-z * z / 2)
        prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.7814779 + t * (-1.8212560 + t * 1.3302744))))
        return 1 - prob if z > 0 else prob

    def offer_health_report(self, offer_id: str,
                             daily_stats: List[Dict]) -> dict:
        """
        Offer এর সপ্তাহিক conversion health report।
        daily_stats: [{'date': '2024-01-01', 'cvr': 0.12, 'volume': 500}]
        """
        if not daily_stats:
            return {'offer_id': offer_id, 'status': 'no_data'}

        cvrs    = [d.get('cvr', 0) for d in daily_stats if d.get('volume', 0) >= 10]
        volumes = [d.get('volume', 0) for d in daily_stats]

        if not cvrs:
            return {'offer_id': offer_id, 'status': 'insufficient_data'}

        avg_cvr = sum(cvrs) / len(cvrs)
        max_cvr = max(cvrs)
        min_cvr = min(cvrs)
        std_cvr = math.sqrt(sum((c - avg_cvr) ** 2 for c in cvrs) / max(len(cvrs) - 1, 1))
        total_vol = sum(volumes)

        # Detect anomalies across all days
        anomaly_days = []
        for stat in daily_stats:
            result = self.detect({
                'conversion_rate': stat.get('cvr', 0),
                'avg_cvr':         avg_cvr,
                'volume':          stat.get('volume', 0),
                'offer_id':        offer_id,
            })
            if result['is_anomaly']:
                anomaly_days.append({'date': stat.get('date'), **result})

        health = (
            'critical' if len(anomaly_days) >= 3 else
            'warning'  if len(anomaly_days) >= 1 else
            'healthy'
        )

        return {
            'offer_id':     offer_id,
            'health':       health,
            'avg_cvr':      round(avg_cvr, 4),
            'max_cvr':      round(max_cvr, 4),
            'min_cvr':      round(min_cvr, 4),
            'std_cvr':      round(std_cvr, 4),
            'total_volume': total_vol,
            'anomaly_days': len(anomaly_days),
            'anomaly_details': anomaly_days,
            'recommendation': 'Investigate and pause if pattern continues' if anomaly_days else 'Normal operation',
        }
