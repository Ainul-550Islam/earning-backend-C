# =============================================================================
# promotions/traffic_quality/quality_scorer.py
# 🟡 MEDIUM — Publisher Traffic Quality Scoring
# CPAlead: "We only work with publishers who have traffic"
# Protect advertisers from low-quality traffic
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response


class TrafficQualityScorer:
    """
    Score publisher traffic quality 0-100.
    Used to: unlock premium offers, restrict low-quality publishers,
    determine payout tiers, identify fraud risk.
    """
    SCORE_KEY = 'traffic_quality:'
    SCORE_TTL = 3600 * 24  # Recalculate daily

    def calculate_quality_score(self, publisher_id: int) -> dict:
        """Calculate comprehensive traffic quality score."""
        from api.promotions.models import TaskSubmission, UserReputation, FraudReport

        # 1. Approval rate (40% weight)
        subs = TaskSubmission.objects.filter(user_id=publisher_id)
        total = subs.count()
        approved = subs.filter(status='approved').count()
        rejected = subs.filter(status='rejected').count()
        approval_rate = (approved / total) if total > 0 else 0
        approval_score = approval_rate * 40  # Max 40 points

        # 2. Fraud flags (30% weight)
        fraud_count = FraudReport.objects.filter(
            reported_user_id=publisher_id,
            created_at__gte=timezone.now() - timezone.timedelta(days=30),
        ).count()
        fraud_score = max(0, 30 - (fraud_count * 10))  # Max 30 points

        # 3. Activity level (15% weight)
        recent_activity = subs.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        activity_score = min(15, recent_activity * 0.5)  # Max 15 points

        # 4. Account age (10% weight)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=publisher_id)
            days_old = (timezone.now() - user.date_joined).days
            age_score = min(10, days_old / 30)  # Max 10 points
        except Exception:
            age_score = 0

        # 5. Diversity (5% weight)
        distinct_campaigns = subs.values('campaign').distinct().count()
        diversity_score = min(5, distinct_campaigns * 0.5)  # Max 5 points

        total_score = approval_score + fraud_score + activity_score + age_score + diversity_score
        total_score = min(100, round(total_score, 1))

        quality_tier = self._get_tier(total_score)

        result = {
            'publisher_id': publisher_id,
            'quality_score': total_score,
            'quality_tier': quality_tier['tier'],
            'tier_label': quality_tier['label'],
            'tier_color': quality_tier['color'],
            'breakdown': {
                'approval_rate': round(approval_rate * 100, 1),
                'approval_score': round(approval_score, 1),
                'fraud_flags_30d': fraud_count,
                'fraud_score': round(fraud_score, 1),
                'activity_score': round(activity_score, 1),
                'age_score': round(age_score, 1),
                'diversity_score': round(diversity_score, 1),
            },
            'perks': quality_tier['perks'],
            'calculated_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.SCORE_KEY}{publisher_id}', result, timeout=self.SCORE_TTL)
        return result

    def get_cached_score(self, publisher_id: int) -> dict:
        cached = cache.get(f'{self.SCORE_KEY}{publisher_id}')
        if cached:
            return cached
        return self.calculate_quality_score(publisher_id)

    def _get_tier(self, score: float) -> dict:
        if score >= 90:
            return {
                'tier': 'elite', 'label': '👑 Elite Publisher',
                'color': '#FFD700',
                'perks': ['Premium offers access', 'Daily payouts', 'Dedicated AM', 'Max bonus rate'],
            }
        elif score >= 75:
            return {
                'tier': 'gold', 'label': '🥇 Gold Publisher',
                'color': '#FFA500',
                'perks': ['High-value offers', 'Weekly payouts', 'Priority support', '10% bonus rate'],
            }
        elif score >= 55:
            return {
                'tier': 'silver', 'label': '🥈 Silver Publisher',
                'color': '#C0C0C0',
                'perks': ['Standard offers', 'Bi-weekly payouts', 'Email support'],
            }
        elif score >= 35:
            return {
                'tier': 'bronze', 'label': '🥉 Bronze Publisher',
                'color': '#CD7F32',
                'perks': ['Basic offers', 'Monthly payouts'],
            }
        else:
            return {
                'tier': 'starter', 'label': '🌱 New Publisher',
                'color': '#808080',
                'perks': ['Getting started — improve quality to unlock more'],
            }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_quality_score_view(request):
    scorer = TrafficQualityScorer()
    return Response(scorer.get_cached_score(request.user.id))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def publisher_quality_score_view(request, publisher_id):
    scorer = TrafficQualityScorer()
    return Response(scorer.calculate_quality_score(publisher_id))
