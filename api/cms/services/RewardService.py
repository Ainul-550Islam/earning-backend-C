# api/cms/services/RewardService.py
"""Legacy RewardService — delegates to services_new layer."""
from decimal import Decimal

class RewardService:
    @staticmethod
    def process_reward(user, amount, reward_type='earned', source_id=''):
        """Process a reward for a user."""
        try:
            from api.cms.services_new.SurveyRewardService import SurveyRewardService
            return SurveyRewardService().award_virtual_currency(
                user=user, amount=Decimal(str(amount)), source=reward_type
            )
        except Exception as e:
            import logging; logging.getLogger(__name__).warning(f"reward error: {e}")
            return False

    @staticmethod
    def get_user_rewards(user, limit=50):
        """Get reward history for user."""
        try:
            from api.cms.models_new.survey_rewards import RewardTransaction
            return RewardTransaction.objects.filter(user=user).order_by('-created_at')[:limit]
        except Exception:
            return []

    @staticmethod
    def calculate_total_earned(user):
        """Calculate total earned for user."""
        try:
            from api.cms.models_new.survey_rewards import RewardTransaction
            from django.db.models import Sum
            result = RewardTransaction.objects.filter(
                user=user, transaction_type='earned', status='approved'
            ).aggregate(total=Sum('amount'))['total']
            return Decimal(str(result or 0))
        except Exception:
            return Decimal('0')
