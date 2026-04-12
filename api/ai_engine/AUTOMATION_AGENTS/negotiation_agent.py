"""
api/ai_engine/AUTOMATION_AGENTS/negotiation_agent.py
=====================================================
Negotiation Agent — automated price/rate negotiation।
Ad network commission, offer reward, payout rate negotiate করার জন্য।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class NegotiationAgent:
    """
    Automated negotiation engine।
    Rule + AI based counter-offer generation।
    Use cases: ad network rates, publisher commissions, bulk deals।
    """

    DEFAULT_TOLERANCE = 0.05   # 5% tolerance মানে deal accept করো
    MAX_ROUNDS        = 7

    def negotiate(
        self,
        our_target_rate: float,
        their_opening_ask: float,
        our_walkaway:  float,
        strategy: str = 'balanced',
        max_rounds: int = None,
    ) -> dict:
        """
        Negotiate price between our_target_rate and their_opening_ask।
        Returns final agreed rate or 'no_deal'।
        """
        max_rounds = max_rounds or self.MAX_ROUNDS

        strategies = {
            'aggressive': 0.70,   # opener কাছে যাই
            'balanced':   0.50,   # মাঝামাঝি
            'concessive': 0.30,   # তাদের দিকে বেশি move করি
        }
        concession_rate = strategies.get(strategy, 0.50)

        my_offer   = our_target_rate
        their_ask  = their_opening_ask
        rounds: List[Dict] = []

        for r in range(1, max_rounds + 1):
            gap      = their_ask - my_offer
            movement = gap * concession_rate * (1 - r / (max_rounds * 2))
            my_offer = round(my_offer + movement, 4)

            # Walkaway check
            if my_offer > our_walkaway:
                return self._no_deal(rounds, reason='walkaway_limit_exceeded')

            gap_pct = abs(their_ask - my_offer) / max(abs(their_ask), 0.001)
            rounds.append({
                'round':    r,
                'my_offer': my_offer,
                'their_ask': their_ask,
                'gap':      round(abs(their_ask - my_offer), 4),
                'gap_pct':  round(gap_pct * 100, 2),
            })

            if gap_pct <= self.DEFAULT_TOLERANCE:
                final = round((my_offer + their_ask) / 2, 4)
                return {
                    'agreed':      True,
                    'final_rate':  final,
                    'our_target':  our_target_rate,
                    'their_ask':   their_opening_ask,
                    'rounds':      rounds,
                    'strategy':    strategy,
                    'saving_vs_ask': round(their_opening_ask - final, 4),
                }

            # Simulate counter from other side (they move 20% toward us)
            their_ask = round(their_ask - (their_ask - my_offer) * 0.20, 4)

        return self._no_deal(rounds, reason='max_rounds_reached')

    def _no_deal(self, rounds: list, reason: str) -> dict:
        return {
            'agreed':  False,
            'final_rate': None,
            'rounds':  rounds,
            'reason':  reason,
        }

    def batch_negotiate(self, deals: List[Dict]) -> List[Dict]:
        """
        Multiple deals একসাথে negotiate করো।
        deals: [{'name': 'NetworkA', 'target': 0.30, 'ask': 0.50, 'walkaway': 0.45}]
        """
        results = []
        for deal in deals:
            result = self.negotiate(
                our_target_rate=deal.get('target', 0.30),
                their_opening_ask=deal.get('ask', 0.50),
                our_walkaway=deal.get('walkaway', 0.45),
                strategy=deal.get('strategy', 'balanced'),
            )
            results.append({'deal': deal.get('name', 'unknown'), **result})
        return results

    def evaluate_offer(self, offered_rate: float, market_rate: float,
                       our_cost: float) -> dict:
        """Incoming offer কতটা ভালো সেটা evaluate করো।"""
        vs_market  = round((offered_rate - market_rate) / max(market_rate, 0.001) * 100, 2)
        margin     = round((offered_rate - our_cost) / max(offered_rate, 0.001) * 100, 2)
        verdict    = 'accept' if margin >= 20 and vs_market >= -5 else 'counter' if margin >= 5 else 'reject'

        return {
            'offered_rate':  offered_rate,
            'market_rate':   market_rate,
            'margin_pct':    margin,
            'vs_market_pct': vs_market,
            'verdict':       verdict,
            'explanation':   self._verdict_explanation(verdict, margin, vs_market),
        }

    def _verdict_explanation(self, verdict: str, margin: float, vs_market: float) -> str:
        if verdict == 'accept':
            return f"Good deal — {margin:.1f}% margin, {vs_market:+.1f}% vs market."
        if verdict == 'counter':
            return f"Counter offer needed — margin only {margin:.1f}%."
        return f"Reject — margin {margin:.1f}% too low, {vs_market:+.1f}% vs market."
