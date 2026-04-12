"""
api/ai_engine/PERSONALIZATION/interest_modeling.py
===================================================
Interest Modeling — user interests dynamically learn করো।
Interaction history থেকে implicit ও explicit interests।
Real-time preference update।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class InterestModeler:
    """User interest learning from behavior।"""

    def infer_interests(self, interactions: List[Dict],
                        decay_factor: float = 0.90) -> dict:
        if not interactions: return {'interests': {}, 'top_interests': []}
        interest_scores: Dict[str, float] = {}
        action_weights = {'complete': 1.0, 'click': 0.5, 'view': 0.2, 'skip': -0.3, 'like': 0.8}
        for i, event in enumerate(sorted(interactions, key=lambda x: x.get('timestamp', 0))):
            cat    = event.get('category', 'unknown')
            action = event.get('action', 'view')
            weight = action_weights.get(action, 0.2)
            time_weight = decay_factor ** (len(interactions) - i - 1)
            interest_scores[cat] = interest_scores.get(cat, 0) + weight * time_weight
        # Normalize
        total = sum(abs(v) for v in interest_scores.values()) or 1
        normalized = {k: round(v/total, 4) for k, v in interest_scores.items() if v > 0}
        top = sorted(normalized, key=normalized.get, reverse=True)[:5]
        return {
            'interests':     normalized,
            'top_interests': top,
            'total_interactions': len(interactions),
            'interest_count': len(normalized),
        }

    def update_profile(self, user, interaction: dict) -> dict:
        from ..models import PersonalizationProfile
        from django.utils import timezone
        profile, _ = PersonalizationProfile.objects.get_or_create(user=user)
        cat    = interaction.get('category', '')
        action = interaction.get('action', 'view')
        weights = {'complete': 1.0, 'click': 0.5, 'view': 0.2, 'skip': -0.5}
        w = weights.get(action, 0.2)
        if w > 0 and cat:
            cats = list(profile.preferred_categories or [])
            if cat not in cats: cats.append(cat)
            profile.preferred_categories = cats[:15]
        elif w < 0 and cat:
            cats = list(profile.preferred_categories or [])
            if cat in cats: cats.remove(cat)
            profile.preferred_categories = cats
        profile.last_refreshed = timezone.now()
        profile.save(update_fields=['preferred_categories', 'last_refreshed'])
        return {'updated': True, 'action': action, 'category': cat, 'weight': w}

    def get_interest_vector(self, interests: Dict[str, float],
                             all_categories: List[str]) -> List[float]:
        return [float(interests.get(cat, 0.0)) for cat in all_categories]

    def detect_interest_shift(self, old_interests: Dict[str, float],
                               new_interests: Dict[str, float]) -> dict:
        all_cats = set(list(old_interests.keys()) + list(new_interests.keys()))
        shifts   = []
        for cat in all_cats:
            old_v = old_interests.get(cat, 0)
            new_v = new_interests.get(cat, 0)
            diff  = new_v - old_v
            if abs(diff) > 0.10:
                shifts.append({'category': cat, 'change': round(diff, 4), 'direction': 'increased' if diff > 0 else 'decreased'})
        return {
            'shifted':     len(shifts) > 0,
            'shifts':      sorted(shifts, key=lambda x: abs(x['change']), reverse=True),
            'major_shift': any(abs(s['change']) > 0.30 for s in shifts),
        }

    def cold_start_interests(self, user, signup_data: dict = None) -> dict:
        signup_data = signup_data or {}
        defaults    = ['earn_money', 'offers', 'rewards']
        country     = getattr(user, 'country', 'BD')
        if country == 'BD':
            defaults += ['bkash_cashback', 'mobile_recharge', 'grocery_offers']
        language = getattr(user, 'language', 'bn')
        if language == 'bn':
            defaults += ['bangla_content']
        return {
            'interests':     {cat: 0.5 for cat in defaults},
            'top_interests': defaults[:5],
            'is_cold_start': True,
        }
