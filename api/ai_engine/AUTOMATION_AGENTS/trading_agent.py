"""
api/ai_engine/AUTOMATION_AGENTS/trading_agent.py
================================================
Trading Agent — virtual currency/reward economy management।
Coin supply, demand balance, inflation control।
Earning platform economy health monitoring।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class TradingAgent:
    """
    Virtual economy trading and balancing agent।
    Earning app এর coin economy optimize করো।
    Supply-demand balance maintain করো।
    """

    # Economy health thresholds
    HEALTHY_VELOCITY_RANGE  = (0.02, 0.15)  # 2-15% daily circulation
    HEALTHY_REDEEM_PRESSURE = (0.30, 0.80)  # 30-80% redeem rate is healthy

    def analyze_economy(self, economy_data: dict) -> dict:
        """Platform economy health analyze করো।"""
        total_circulation = economy_data.get('total_coins_circulation', 0)
        daily_earned      = economy_data.get('daily_earn_volume', 0)
        daily_redeemed    = economy_data.get('daily_redeem_volume', 0)
        active_users      = economy_data.get('active_users', 1)
        avg_balance       = economy_data.get('avg_user_balance', 0)

        velocity          = daily_earned / max(total_circulation, 1)
        redeem_pressure   = daily_redeemed / max(daily_earned, 1)
        inflation_rate    = max(0.0, daily_earned - daily_redeemed) / max(total_circulation, 1)
        arpu              = total_circulation / max(active_users, 1)

        health = self._economy_health(velocity, redeem_pressure, inflation_rate)
        alerts = self._economy_alerts(velocity, redeem_pressure, inflation_rate)

        return {
            'total_circulation':  total_circulation,
            'daily_earned':       daily_earned,
            'daily_redeemed':     daily_redeemed,
            'velocity':           round(velocity, 4),
            'redeem_pressure':    round(redeem_pressure, 4),
            'inflation_rate':     round(inflation_rate, 6),
            'arpu':               round(arpu, 2),
            'health':             health,
            'alerts':             alerts,
            'recommendation':     self._economy_recommendation(health, alerts),
        }

    def _economy_health(self, velocity: float, pressure: float,
                         inflation: float) -> str:
        v_ok = self.HEALTHY_VELOCITY_RANGE[0] <= velocity <= self.HEALTHY_VELOCITY_RANGE[1]
        p_ok = self.HEALTHY_REDEEM_PRESSURE[0] <= pressure <= self.HEALTHY_REDEEM_PRESSURE[1]
        i_ok = inflation < 0.05

        if v_ok and p_ok and i_ok:  return 'healthy'
        if sum([v_ok, p_ok, i_ok]) >= 2: return 'moderate'
        return 'unhealthy'

    def _economy_alerts(self, velocity: float,
                         pressure: float, inflation: float) -> List[str]:
        alerts = []
        if velocity < self.HEALTHY_VELOCITY_RANGE[0]:
            alerts.append('Low coin velocity — users hoarding coins, not spending')
        if velocity > self.HEALTHY_VELOCITY_RANGE[1]:
            alerts.append('High velocity — potential farm/abuse behavior')
        if pressure > 0.90:
            alerts.append('High redeem pressure — risk of coin reserve depletion')
        if pressure < 0.20:
            alerts.append('Low redeem rate — users not finding value in earnings')
        if inflation > 0.10:
            alerts.append('High inflation — earning rate far exceeds redemption')
        return alerts

    def _economy_recommendation(self, health: str, alerts: List[str]) -> str:
        if health == 'healthy':
            return 'Economy is balanced. Monitor weekly.'
        if 'High redeem pressure' in str(alerts):
            return 'Reduce earn rates slightly or add more spending options'
        if 'Low redeem rate' in str(alerts):
            return 'Add more withdrawal options or lower minimum withdrawal'
        if 'High inflation' in str(alerts):
            return 'Reduce earn rates by 10-15% or add coin burn mechanisms'
        return 'Review earn/redeem balance and adjust accordingly'

    def rebalance(self, economy_data: dict) -> dict:
        """Economy rebalancing recommendations।"""
        analysis = self.analyze_economy(economy_data)
        velocity = analysis.get('velocity', 0)
        pressure = analysis.get('redeem_pressure', 0)

        adjustments = {}

        if velocity < 0.02:
            adjustments['earn_rate_multiplier'] = 1.20
            adjustments['reason'] = 'Boost earning to increase velocity'
        elif velocity > 0.15:
            adjustments['earn_rate_multiplier'] = 0.85
            adjustments['reason'] = 'Reduce earning to prevent inflation'
        else:
            adjustments['earn_rate_multiplier'] = 1.00
            adjustments['reason'] = 'Economy balanced — maintain current rates'

        if pressure > 0.85:
            adjustments['min_withdrawal_increase'] = True
            adjustments['add_spending_options']    = True
        elif pressure < 0.25:
            adjustments['min_withdrawal_decrease'] = True
            adjustments['add_withdrawal_methods']  = True

        return {
            'analysis':    analysis,
            'adjustments': adjustments,
            'auto_apply':  analysis['health'] == 'unhealthy',
        }

    def price_offer_reward(self, offer_data: dict,
                            market_data: dict = None) -> dict:
        """Offer reward amount dynamically price করো।"""
        market_data = market_data or {}

        base_reward    = float(offer_data.get('base_reward', 100))
        completion_time = int(offer_data.get('completion_minutes', 5))
        difficulty     = offer_data.get('difficulty', 'medium')
        category       = offer_data.get('category', 'general')

        # Time-value: longer tasks → higher reward
        time_factor = 1.0 + (completion_time - 5) * 0.05

        # Difficulty factor
        difficulty_multipliers = {'easy': 0.80, 'medium': 1.00, 'hard': 1.40}
        diff_factor = difficulty_multipliers.get(difficulty, 1.00)

        # Market demand
        demand_score = market_data.get('demand_score', 0.50)
        market_factor = 0.90 + demand_score * 0.20

        # Category premium
        premium_cats = {'survey': 1.20, 'video': 0.90, 'app_install': 1.30, 'purchase': 1.50}
        cat_factor = premium_cats.get(category, 1.00)

        optimal_reward = round(base_reward * time_factor * diff_factor * market_factor * cat_factor, 2)

        return {
            'base_reward':     base_reward,
            'optimal_reward':  optimal_reward,
            'multipliers': {
                'time':        round(time_factor, 3),
                'difficulty':  round(diff_factor, 3),
                'market':      round(market_factor, 3),
                'category':    round(cat_factor, 3),
            },
            'pct_change':  round((optimal_reward - base_reward) / max(base_reward, 1) * 100, 2),
        }

    def detect_market_manipulation(self, trading_patterns: List[Dict]) -> dict:
        """Economy manipulation attempts detect করো।"""
        if not trading_patterns:
            return {'manipulation_detected': False}

        high_volume_users = [p for p in trading_patterns
                              if p.get('daily_earn', 0) > p.get('avg_earn', 100) * 10]
        circular_patterns = [p for p in trading_patterns
                              if p.get('earn_redeem_ratio', 0) > 0.99]
        bot_patterns      = [p for p in trading_patterns
                              if p.get('bot_score', 0) > 0.70]

        manipulation_score = (
            len(high_volume_users) * 0.3 +
            len(circular_patterns) * 0.4 +
            len(bot_patterns) * 0.5
        ) / max(len(trading_patterns), 1)

        return {
            'manipulation_detected': manipulation_score >= 0.30,
            'manipulation_score':    round(min(1.0, manipulation_score), 4),
            'high_volume_users':     len(high_volume_users),
            'circular_patterns':     len(circular_patterns),
            'bot_patterns':          len(bot_patterns),
            'action':                'Investigate flagged accounts' if manipulation_score >= 0.30 else 'Monitor',
        }
