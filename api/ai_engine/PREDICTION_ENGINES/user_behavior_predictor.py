"""
api/ai_engine/PREDICTION_ENGINES/user_behavior_predictor.py
============================================================
User Behavior Predictor — ইউজারের পরবর্তী কার্যক্রম predict করো।
Next action, session duration, engagement prediction।
Marketing automation ও personalization এর core।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class UserBehaviorPredictor:
    """
    User behavioral prediction engine।
    Next action, churn signal, engagement level, purchase intent।
    """

    ACTIONS = [
        "complete_offer",
        "start_new_offer",
        "withdraw_earnings",
        "refer_friend",
        "check_notifications",
        "view_leaderboard",
        "go_inactive",
        "upgrade_account",
    ]

    def predict_next_action(self, user, context: dict = None) -> dict:
        """
        User এর সম্ভাব্য next action predict করো।
        Markov chain inspired heuristics।
        """
        context = context or {}
        from ..utils import days_since

        # User signals
        coin_balance      = float(getattr(user, "coin_balance", 0))
        total_earned      = float(getattr(user, "total_earned", 0))
        days_since_login  = days_since(user.last_login)
        referral_count    = context.get("referral_count", 0)
        offers_completed  = context.get("offers_completed", 0)
        streak_days       = context.get("streak_days", 0)
        has_pending_offer = context.get("has_pending_offer", False)

        # Action probability scoring
        scores = {
            "complete_offer":     0.0,
            "start_new_offer":    0.0,
            "withdraw_earnings":  0.0,
            "refer_friend":       0.0,
            "check_notifications": 0.0,
            "view_leaderboard":   0.0,
            "go_inactive":        0.0,
            "upgrade_account":    0.0,
        }

        # Complete pending offer
        if has_pending_offer:
            scores["complete_offer"] += 0.50

        # Start new offer — engaged users
        if days_since_login <= 1 and offers_completed < 10:
            scores["start_new_offer"] += 0.40
        elif days_since_login <= 3:
            scores["start_new_offer"] += 0.25

        # Withdraw — balance threshold
        if coin_balance >= 1000:
            scores["withdraw_earnings"] += min(0.45, coin_balance / 10000)
        elif coin_balance >= 500:
            scores["withdraw_earnings"] += 0.20

        # Refer friend — experienced users
        if offers_completed >= 5 and referral_count < 3:
            scores["refer_friend"] += 0.20
        if referral_count >= 3:
            scores["refer_friend"] += 0.10  # Habitual referrers

        # Check notifications — recent login
        if days_since_login <= 1:
            scores["check_notifications"] += 0.30
        if streak_days >= 3:
            scores["check_notifications"] += 0.15

        # View leaderboard — competitive users
        if offers_completed >= 10 and streak_days >= 5:
            scores["view_leaderboard"] += 0.25

        # Go inactive signals
        if days_since_login >= 7:
            scores["go_inactive"] += 0.35
        if days_since_login >= 14:
            scores["go_inactive"] += 0.25
        if coin_balance == 0 and offers_completed == 0:
            scores["go_inactive"] += 0.20

        # Upgrade account — high earners
        if total_earned >= 5000 and getattr(user, "account_level", "normal") == "normal":
            scores["upgrade_account"] += 0.30

        # Normalize
        total = sum(max(0, v) for v in scores.values()) or 1.0
        scores = {k: round(max(0, v) / total, 4) for k, v in scores.items()}

        predicted_action    = max(scores, key=scores.get)
        predicted_confidence = scores[predicted_action]

        return {
            "user_id":           str(user.id),
            "predicted_action":  predicted_action,
            "confidence":        predicted_confidence,
            "all_action_scores": scores,
            "top_3_actions":     dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]),
            "context_signals": {
                "coin_balance":     coin_balance,
                "days_since_login": days_since_login,
                "offers_completed": offers_completed,
                "streak_days":      streak_days,
            },
        }

    def predict_session_duration(self, user, context: dict = None) -> dict:
        """User এর এই session কতক্ষণ চলবে predict করো।"""
        context = context or {}
        from ..utils import days_since

        days_inactive    = days_since(user.last_login)
        offers_completed = context.get("offers_completed", 0)
        device           = context.get("device", "mobile")
        hour             = context.get("hour", 12)
        has_pending      = context.get("has_pending_offer", False)

        # Base duration by engagement level
        if offers_completed >= 20:  base_minutes = 25.0
        elif offers_completed >= 5: base_minutes = 15.0
        elif offers_completed >= 1: base_minutes = 8.0
        else:                       base_minutes = 4.0

        # Modifiers
        modifiers = 1.0

        # Desktop users stay longer
        if device == "desktop":   modifiers *= 1.4
        elif device == "tablet":  modifiers *= 1.2

        # Evening sessions are longer
        if 18 <= hour <= 22:      modifiers *= 1.3
        elif 12 <= hour <= 14:    modifiers *= 1.1

        # Returning users after absence
        if days_inactive >= 7:    modifiers *= 0.70  # Rusty/shorter session
        elif days_inactive == 0:  modifiers *= 1.20  # Active user

        # Pending offer increases engagement
        if has_pending:           modifiers *= 1.40

        predicted_minutes = round(base_minutes * modifiers, 1)
        predicted_seconds = int(predicted_minutes * 60)

        return {
            "predicted_duration_minutes":  predicted_minutes,
            "predicted_duration_seconds":  predicted_seconds,
            "engagement_bucket":           self._engagement_bucket(predicted_minutes),
            "device":                      device,
            "confidence":                  0.65,
        }

    def _engagement_bucket(self, minutes: float) -> str:
        if minutes >= 30: return "deep_session"
        if minutes >= 15: return "moderate_session"
        if minutes >= 5:  return "light_session"
        return "bounce"

    def predict_purchase_intent(self, user, item_data: dict,
                                  context: dict = None) -> dict:
        """User এই item কিনবে বা complete করবে কিনা predict করো।"""
        context = context or {}
        from ..utils import days_since

        coin_balance  = float(getattr(user, "coin_balance", 0))
        item_cost     = float(item_data.get("cost", 0))
        item_reward   = float(item_data.get("reward", 0))
        difficulty    = item_data.get("difficulty", "medium")
        category      = item_data.get("category", "")

        # Affordability
        can_afford = coin_balance >= item_cost if item_cost > 0 else True

        # Difficulty preference match
        diff_scores = {"easy": 0.80, "medium": 0.55, "hard": 0.30}
        diff_score  = diff_scores.get(difficulty, 0.55)

        # Category interest
        preferred_cats = context.get("preferred_categories", [])
        cat_match = 1.20 if category in preferred_cats else 1.0

        # Reward attractiveness
        reward_score = min(1.0, item_reward / 500) if item_reward > 0 else 0.30

        intent_score = diff_score * cat_match * reward_score
        if not can_afford:
            intent_score *= 0.10

        intent_score = min(1.0, max(0.0, intent_score))

        return {
            "item_id":         item_data.get("id", ""),
            "intent_score":    round(intent_score, 4),
            "will_engage":     intent_score >= 0.40,
            "will_complete":   intent_score >= 0.65,
            "can_afford":      can_afford,
            "difficulty_match": diff_score >= 0.60,
            "reward_attractive": reward_score >= 0.40,
            "recommendation":  self._intent_recommendation(intent_score, can_afford),
        }

    def _intent_recommendation(self, score: float, can_afford: bool) -> str:
        if not can_afford:
            return "Show earning opportunities to build balance first."
        if score >= 0.80:
            return "High intent — show this prominently as top recommendation."
        if score >= 0.50:
            return "Moderate intent — include in recommendations with social proof."
        if score >= 0.30:
            return "Low intent — highlight reward and ease to overcome hesitation."
        return "Poor match — suggest alternative offers better suited to this user."

    def predict_reengagement_probability(self, user, days_since_last_activity: int) -> dict:
        """Dormant user এর reengagement probability predict করো।"""
        from ..utils import days_since

        account_age       = days_since(user.date_joined)
        total_earned      = float(getattr(user, "total_earned", 0))
        coin_balance      = float(getattr(user, "coin_balance", 0))

        # Base reengagement probability — decays with inactivity
        if days_since_last_activity <= 7:    base = 0.75
        elif days_since_last_activity <= 14: base = 0.55
        elif days_since_last_activity <= 30: base = 0.35
        elif days_since_last_activity <= 60: base = 0.18
        elif days_since_last_activity <= 90: base = 0.08
        else:                                base = 0.03

        # Boost factors
        boost = 1.0
        if total_earned >= 1000:   boost *= 1.30  # Invested user
        if coin_balance >= 500:    boost *= 1.25  # Has unclaimed balance
        if account_age >= 90:      boost *= 1.15  # Long-time user

        probability = min(1.0, base * boost)

        # Best reengagement channel
        if probability >= 0.50:   channel = "push_notification"
        elif probability >= 0.30: channel = "email_with_offer"
        elif probability >= 0.15: channel = "sms_with_bonus"
        else:                     channel = "paid_retargeting_ad"

        return {
            "user_id":                str(user.id),
            "days_inactive":          days_since_last_activity,
            "reengagement_probability": round(probability, 4),
            "best_channel":           channel,
            "optimal_timing":         "evening_7pm_to_9pm",
            "incentive_needed":       probability < 0.40,
            "recommended_incentive":  "bonus_coins_100" if coin_balance == 0 else "streak_recovery_bonus",
            "worth_retargeting":      probability >= 0.10,
        }
