"""
api/ai_engine/PREDICTION_ENGINES/click_predictor.py
====================================================
Click-Through Rate (CTR) Predictor।
P(click | user, item, position, context)।
"""
import logging
logger = logging.getLogger(__name__)

class ClickPredictor:
    """CTR prediction engine।"""

    POSITION_DECAY = {1: 1.0, 2: 0.85, 3: 0.70, 4: 0.55, 5: 0.45}

    def predict(self, user, item_data: dict, position: int = 1, context: dict = None) -> dict:
        context = context or {}
        item_type = item_data.get("type", "offer")
        base_ctrs = {"offer": 0.08, "ad": 0.03, "product": 0.05, "content": 0.06}
        base_ctr  = base_ctrs.get(item_type, 0.05)
        pos_factor = self.POSITION_DECAY.get(min(position, 5), 0.35)
        engagement = context.get("engagement_score", 0.5)
        user_factor = 0.7 + engagement * 0.6
        pref_categories = context.get("preferred_categories", [])
        item_category   = item_data.get("category", "")
        pref_boost = 0.15 if item_category in pref_categories else 0.0
        device = context.get("device", "mobile")
        device_factor = {"mobile": 1.0, "desktop": 0.85, "tablet": 0.90}.get(device, 1.0)
        ctr = base_ctr * pos_factor * user_factor * device_factor + pref_boost
        ctr = max(0.001, min(0.99, ctr))
        return {
            "click_probability": round(ctr, 4),
            "confidence":        0.68,
            "base_ctr":          base_ctr,
            "position":          position,
            "personalization_boost": pref_boost > 0,
        }

    def predict_batch(self, user, items: list, context: dict = None) -> list:
        return [self.predict(user, item, i+1, context) for i, item in enumerate(items)]

    def estimate_impressions_needed(self, target_clicks: int, predicted_ctr: float) -> int:
        if predicted_ctr <= 0:
            return 0
        return int(target_clicks / predicted_ctr)
