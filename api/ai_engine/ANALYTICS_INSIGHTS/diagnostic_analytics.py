"""
api/ai_engine/ANALYTICS_INSIGHTS/diagnostic_analytics.py
=========================================================
Diagnostic Analytics — কেন metric পরিবর্তন হল।
Root cause analysis, anomaly explanation, attribution।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DiagnosticAnalytics:
    """
    Diagnostic analytics — WHY did the metric change?
    Root cause identification ও explanation।
    """

    def diagnose(self, metric_name: str, before: float, after: float,
                  factors: Dict[str, float]) -> dict:
        """Metric change এর root cause identify করো।"""
        if before == 0:
            return {'metric': metric_name, 'change': after, 'direction': 'new', 'contributions': {}}

        change      = after - before
        pct_change  = (change / abs(before)) * 100
        direction   = 'increased' if change > 0 else 'decreased'

        total_factor = sum(abs(v) for v in factors.values()) or 1
        contributions = {
            factor: {
                'value':        round(val, 4),
                'contribution': round((abs(val) / total_factor) * change, 4),
                'contribution_pct': round(abs(val) / total_factor * 100, 2),
            }
            for factor, val in factors.items()
        }

        top_factor = max(contributions, key=lambda k: abs(contributions[k]['contribution'])) if contributions else 'unknown'

        return {
            'metric':      metric_name,
            'before':      round(before, 4),
            'after':       round(after, 4),
            'change':      round(change, 4),
            'pct_change':  round(pct_change, 2),
            'direction':   direction,
            'top_driver':  top_factor,
            'contributions': contributions,
            'summary':     f"{metric_name} {direction} {abs(pct_change):.1f}% — primarily driven by {top_factor}.",
        }

    def root_cause_analysis(self, symptom: str, data: dict) -> dict:
        """Symptom থেকে root cause identify করো।"""
        causes = {
            'revenue_drop': [
                {'cause': 'Offer fill rate decreased', 'probability': data.get('fill_rate_change', 0) < -0.10},
                {'cause': 'User churn increased', 'probability': data.get('churn_rate', 0) > 0.20},
                {'cause': 'Conversion rate dropped', 'probability': data.get('cvr_change', 0) < -0.05},
                {'cause': 'High-value users became inactive', 'probability': data.get('vip_inactive', False)},
            ],
            'engagement_drop': [
                {'cause': 'Push notification disabled by users', 'probability': data.get('notif_opt_out_rate', 0) > 0.20},
                {'cause': 'App update broke user experience', 'probability': data.get('crash_rate', 0) > 0.05},
                {'cause': 'Offer quality decreased', 'probability': data.get('offer_rating', 5) < 3.5},
            ],
            'fraud_spike': [
                {'cause': 'VPN abuse surge', 'probability': data.get('vpn_rate', 0) > 0.15},
                {'cause': 'Bot traffic from specific IP range', 'probability': data.get('bot_score', 0) > 0.50},
                {'cause': 'New exploit in offer completion', 'probability': data.get('exploit_detected', False)},
            ],
        }

        relevant = causes.get(symptom, [])
        confirmed = [c for c in relevant if c['probability']]
        suspected = [c for c in relevant if not c['probability']]

        return {
            'symptom':          symptom,
            'confirmed_causes': confirmed,
            'suspected_causes': suspected,
            'primary_cause':    confirmed[0]['cause'] if confirmed else 'Under investigation',
            'data_evidence':    data,
            'action_required':  len(confirmed) > 0,
        }

    def explain_prediction(self, prediction: dict, feature_contributions: dict) -> str:
        """ML prediction কেন এই value দিয়েছে সেটা plain English এ explain করো।"""
        pred_type = prediction.get('prediction_type', 'score')
        value     = prediction.get('predicted_value', 0)

        top_features = sorted(feature_contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:3]

        reasons = []
        for feat, contrib in top_features:
            direction = 'increasing' if contrib > 0 else 'decreasing'
            reasons.append(f"{feat.replace('_', ' ')} ({direction} factor)")

        explanation = f"The {pred_type} score is {value:.2f} mainly because of: {', '.join(reasons)}."
        return explanation

    def attribution_waterfall(self, conversions: List[Dict]) -> dict:
        """Conversion attribution waterfall analysis।"""
        channel_conversions: Dict[str, int] = {}
        channel_revenue: Dict[str, float]   = {}

        for conv in conversions:
            channel = conv.get('channel', 'direct')
            revenue = float(conv.get('revenue', 0))
            channel_conversions[channel] = channel_conversions.get(channel, 0) + 1
            channel_revenue[channel]     = channel_revenue.get(channel, 0) + revenue

        total_conv  = sum(channel_conversions.values()) or 1
        total_rev   = sum(channel_revenue.values()) or 1

        waterfall = []
        for ch in sorted(channel_conversions, key=channel_conversions.get, reverse=True):
            waterfall.append({
                'channel':      ch,
                'conversions':  channel_conversions[ch],
                'revenue':      round(channel_revenue.get(ch, 0), 2),
                'conv_share':   round(channel_conversions[ch] / total_conv * 100, 2),
                'rev_share':    round(channel_revenue.get(ch, 0) / total_rev * 100, 2),
            })

        return {
            'waterfall':       waterfall,
            'total_conversions': total_conv,
            'total_revenue':   round(total_rev, 2),
            'top_channel':     waterfall[0]['channel'] if waterfall else 'unknown',
        }
