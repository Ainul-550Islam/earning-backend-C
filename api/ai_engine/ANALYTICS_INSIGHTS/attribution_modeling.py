"""
api/ai_engine/ANALYTICS_INSIGHTS/attribution_modeling.py
=========================================================
Attribution Modeling — conversion attribution।
First-touch, last-touch, linear, data-driven।
Marketing channel effectiveness measurement।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class AttributionModeler:
    """Multi-touch attribution modeling engine।"""

    def attribute(self, touchpoints: List[Dict],
                  conversion_value: float,
                  model: str = "linear") -> List[Dict]:
        if not touchpoints or conversion_value <= 0:
            return []

        models = {
            "first_touch":  self._first_touch,
            "last_touch":   self._last_touch,
            "linear":       self._linear,
            "time_decay":   self._time_decay,
            "position":     self._position_based,
        }
        fn = models.get(model, self._linear)
        return fn(touchpoints, conversion_value)

    def _first_touch(self, touchpoints: List[Dict], value: float) -> List[Dict]:
        result = []
        for i, tp in enumerate(touchpoints):
            result.append({**tp, "credit": value if i == 0 else 0.0, "credit_pct": 100.0 if i == 0 else 0.0})
        return result

    def _last_touch(self, touchpoints: List[Dict], value: float) -> List[Dict]:
        last = len(touchpoints) - 1
        result = []
        for i, tp in enumerate(touchpoints):
            result.append({**tp, "credit": value if i == last else 0.0, "credit_pct": 100.0 if i == last else 0.0})
        return result

    def _linear(self, touchpoints: List[Dict], value: float) -> List[Dict]:
        per_touch = value / max(len(touchpoints), 1)
        pct = round(100.0 / max(len(touchpoints), 1), 2)
        return [{**tp, "credit": round(per_touch, 4), "credit_pct": pct} for tp in touchpoints]

    def _time_decay(self, touchpoints: List[Dict], value: float) -> List[Dict]:
        import math
        weights = [math.exp(i * 0.5) for i in range(len(touchpoints))]
        total_w = sum(weights)
        result  = []
        for tp, w in zip(touchpoints, weights):
            credit = round(value * w / total_w, 4)
            result.append({**tp, "credit": credit, "credit_pct": round(credit / value * 100, 2)})
        return result

    def _position_based(self, touchpoints: List[Dict], value: float) -> List[Dict]:
        n = len(touchpoints)
        if n == 0: return []
        if n == 1: return [{**touchpoints[0], "credit": value, "credit_pct": 100.0}]
        if n == 2: return [
            {**touchpoints[0], "credit": round(value * 0.40, 4), "credit_pct": 40.0},
            {**touchpoints[1], "credit": round(value * 0.60, 4), "credit_pct": 60.0},
        ]
        # First 40%, Last 40%, Middle 20% split
        mid_credit = value * 0.20 / (n - 2) if n > 2 else 0
        result = []
        for i, tp in enumerate(touchpoints):
            if i == 0:
                credit = value * 0.40
            elif i == n - 1:
                credit = value * 0.40
            else:
                credit = mid_credit
            result.append({**tp, "credit": round(credit, 4), "credit_pct": round(credit/value*100, 2)})
        return result

    def channel_attribution_summary(self, attributed_data: List[Dict]) -> dict:
        channel_credit: Dict[str, float] = {}
        for item in attributed_data:
            channel = item.get("channel", "unknown")
            credit  = float(item.get("credit", 0))
            channel_credit[channel] = channel_credit.get(channel, 0) + credit
        total = sum(channel_credit.values()) or 1
        return {
            "channel_credits":  {ch: round(cr, 2) for ch, cr in sorted(channel_credit.items(), key=lambda x: x[1], reverse=True)},
            "channel_shares":   {ch: round(cr/total, 4) for ch, cr in channel_credit.items()},
            "top_channel":      max(channel_credit, key=channel_credit.get) if channel_credit else None,
            "total_attributed": round(total, 2),
        }

    def compare_models(self, touchpoints: List[Dict], conversion_value: float) -> dict:
        models   = ["first_touch", "last_touch", "linear", "time_decay", "position"]
        results  = {}
        for model in models:
            attribution = self.attribute(touchpoints, conversion_value, model)
            results[model] = self.channel_attribution_summary(attribution)
        return results
