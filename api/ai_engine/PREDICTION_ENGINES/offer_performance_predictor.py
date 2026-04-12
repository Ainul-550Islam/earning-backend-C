"""
api/ai_engine/PREDICTION_ENGINES/offer_performance_predictor.py
================================================================
Offer Performance Predictor।
"""

import logging
logger = logging.getLogger(__name__)


class OfferPerformancePredictor:
    """Predict offer performance before launch।"""

    def predict(self, offer_data: dict, tenant_id=None) -> dict:
        reward_amount   = float(offer_data.get('reward_amount', 0))
        difficulty      = offer_data.get('difficulty', 'medium')
        category        = offer_data.get('category', '')
        target_country  = offer_data.get('country', 'BD')

        # Base estimates by difficulty
        base = {'easy': {'ctr': 0.12, 'cvr': 0.35}, 'medium': {'ctr': 0.08, 'cvr': 0.20}, 'hard': {'ctr': 0.05, 'cvr': 0.10}}
        rates = base.get(difficulty, base['medium'])

        reward_boost = min(0.05, reward_amount / 500)

        return {
            'predicted_ctr':       round(rates['ctr'] + reward_boost, 4),
            'predicted_cvr':       round(rates['cvr'] + reward_boost * 0.5, 4),
            'predicted_roi':       round((reward_amount * rates['cvr']) / max(reward_amount, 1), 4),
            'difficulty':          difficulty,
            'confidence':          0.65,
            'recommendation':      'launch' if rates['ctr'] >= 0.05 else 'optimize_first',
        }


"""
api/ai_engine/PREDICTION_ENGINES/user_behavior_predictor.py
============================================================
User Behavior Predictor — next action prediction।
"""


class UserBehaviorPredictor:
    """Predict user's next action/behavior।"""

    ACTIONS = ['complete_offer', 'withdraw', 'refer_friend', 'go_inactive', 'upgrade_level']

    def predict_next_action(self, user, context: dict = None) -> dict:
        context = context or {}
        balance         = float(getattr(user, 'coin_balance', 0))
        days_inactive   = context.get('days_since_login', 0)
        referral_count  = context.get('referral_count', 0)

        # Simple heuristic scoring
        scores = {
            'complete_offer':  0.40 - days_inactive * 0.01,
            'withdraw':        0.15 if balance > 1000 else 0.05,
            'refer_friend':    0.10 + referral_count * 0.02,
            'go_inactive':     0.10 + days_inactive * 0.02,
            'upgrade_level':   0.05,
        }

        # Normalize
        total = sum(max(0, v) for v in scores.values())
        if total > 0:
            scores = {k: round(max(0, v) / total, 4) for k, v in scores.items()}

        predicted = max(scores, key=scores.get)
        return {
            'predicted_action': predicted,
            'confidence':       scores.get(predicted, 0.5),
            'all_actions':      scores,
        }


"""
api/ai_engine/PREDICTION_ENGINES/demand_forecast.py
====================================================
Demand Forecasting — offer/product demand prediction।
"""


class DemandForecaster:
    """Time-series demand forecasting।"""

    def forecast(self, historical_data: list, days_ahead: int = 7) -> dict:
        if not historical_data:
            return {'forecast': [], 'method': 'no_data'}

        avg = sum(historical_data) / len(historical_data)
        trend = (historical_data[-1] - historical_data[0]) / max(len(historical_data), 1)

        forecast = []
        for i in range(1, days_ahead + 1):
            point = avg + trend * i
            forecast.append(round(max(0, point), 2))

        return {
            'forecast':     forecast,
            'trend':        'increasing' if trend > 0 else 'decreasing' if trend < 0 else 'stable',
            'avg_demand':   round(avg, 2),
            'days_ahead':   days_ahead,
            'confidence':   0.60,
            'method':       'linear_trend',
        }


"""
api/ai_engine/PREDICTION_ENGINES/inventory_predictor.py
========================================================
Inventory Predictor — offer/budget availability prediction।
"""


class InventoryPredictor:
    """Offer inventory ও budget depletion prediction।"""

    def predict_depletion(self, current_inventory: float, daily_burn_rate: float,
                           refill_threshold: float = 0.20) -> dict:
        if daily_burn_rate <= 0:
            return {'days_remaining': 999, 'needs_refill': False}

        days_remaining = current_inventory / daily_burn_rate
        depletion_pct  = 1.0 - (current_inventory / max(current_inventory + 1, 1))
        needs_refill   = current_inventory <= (refill_threshold * (current_inventory + daily_burn_rate * 7))

        return {
            'days_remaining':  round(days_remaining, 1),
            'needs_refill':    needs_refill,
            'depletion_pct':   round(depletion_pct, 4),
            'daily_burn_rate': daily_burn_rate,
            'recommendation':  'refill_now' if days_remaining < 3 else 'monitor' if days_remaining < 7 else 'ok',
        }


"""
api/ai_engine/PREDICTION_ENGINES/trend_predictor.py
====================================================
Trend Predictor — emerging trends detection।
"""


class TrendPredictor:
    """Detect and predict emerging trends।"""

    def predict_trend(self, time_series: list, window: int = 7) -> dict:
        if len(time_series) < window:
            return {'trend': 'insufficient_data', 'confidence': 0.0}

        recent  = time_series[-window:]
        earlier = time_series[-window * 2: -window] if len(time_series) >= window * 2 else time_series[:window]

        avg_recent  = sum(recent) / len(recent)
        avg_earlier = sum(earlier) / len(earlier) if earlier else avg_recent

        pct_change = ((avg_recent - avg_earlier) / max(abs(avg_earlier), 0.001)) * 100

        if pct_change > 15:   trend, strength = 'strong_uptrend', 'strong'
        elif pct_change > 5:  trend, strength = 'uptrend', 'moderate'
        elif pct_change < -15: trend, strength = 'strong_downtrend', 'strong'
        elif pct_change < -5: trend, strength = 'downtrend', 'moderate'
        else:                  trend, strength = 'sideways', 'weak'

        return {
            'trend':       trend,
            'strength':    strength,
            'pct_change':  round(pct_change, 2),
            'avg_recent':  round(avg_recent, 4),
            'confidence':  0.70,
        }


"""
api/ai_engine/PREDICTION_ENGINES/seasonality_detector.py
=========================================================
Seasonality Detector — periodic patterns detection।
"""


class SeasonalityDetector:
    """Detect weekly/monthly seasonality patterns।"""

    def detect_weekly_pattern(self, daily_data: dict) -> dict:
        """
        daily_data: {'Monday': 100, 'Tuesday': 120, ...}
        """
        if not daily_data:
            return {'has_seasonality': False}

        values = list(daily_data.values())
        avg    = sum(values) / len(values)

        patterns = {}
        for day, val in daily_data.items():
            relative = round(val / max(avg, 0.001), 3)
            patterns[day] = {
                'value':    val,
                'relative': relative,
                'type':     'peak' if relative > 1.15 else 'trough' if relative < 0.85 else 'normal',
            }

        peak_days   = [d for d, v in patterns.items() if v['type'] == 'peak']
        trough_days = [d for d, v in patterns.items() if v['type'] == 'trough']

        return {
            'has_seasonality': len(peak_days) > 0 or len(trough_days) > 0,
            'peak_days':       peak_days,
            'trough_days':     trough_days,
            'patterns':        patterns,
            'recommendation':  f"Best to launch on: {', '.join(peak_days)}" if peak_days else 'No clear pattern',
        }
