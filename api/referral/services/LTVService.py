# api/referral/services/LTVService.py
# Lifetime Value (LTV) calculation for referred users
# ============================================================

from decimal import Decimal
from django.utils import timezone
from django.db import transaction
import logging
from api.referral.models.analytics import ReferralLTV

logger = logging.getLogger(__name__)


class LTVService:
    """
    Referred user lifetime value calculation।
    Referrer কে তার referred users এর LTV দেখাতে পারবে।
    Weekly Celery task দিয়ে recalculate হয়।
    """

    @staticmethod
    @transaction.atomic
    def calculate_ltv(referrer, referred_user) -> 'ReferralLTV':
        """
        Specific referred user এর LTV calculate করো।
        """
        from api.referral.models import ReferralLTV, ReferralEarning
        from django.db.models import Sum, Count, Q

        ltv, created = ReferralLTV.objects.get_or_create(
            user=referred_user,
            referred_by=referrer,
        )

        # Commission earned by referrer from this user
        earnings = ReferralEarning.objects.filter(
            referrer=referrer,
            referred_user=referred_user,
        ).aggregate(
            total=Sum('amount'),
            source_total=Sum('source_amount'),
            task_count=Count('id', filter=__import__(
                'django.db.models', fromlist=['Q']
            ).Q(source_type='task')),
            offer_count=Count('id', filter=__import__(
                'django.db.models', fromlist=['Q']
            ).Q(source_type='offer')),
        )

        ltv.lifetime_value = earnings['total'] or Decimal('0')
        ltv.total_user_earnings = earnings['source_total'] or Decimal('0')
        ltv.task_count = earnings['task_count'] or 0
        ltv.offer_count = earnings['offer_count'] or 0

        # Activity dates
        first = ReferralEarning.objects.filter(
            referrer=referrer, referred_user=referred_user
        ).order_by('created_at').first()

        last = ReferralEarning.objects.filter(
            referrer=referrer, referred_user=referred_user
        ).order_by('-created_at').first()

        if first:
            ltv.first_activity_at = first.created_at
        if last:
            ltv.last_activity = last.created_at

        # Days active
        if ltv.first_activity_at and ltv.last_activity:
            ltv.days_active = (
                ltv.last_activity - ltv.first_activity_at
            ).days + 1

        # Churn risk
        ltv.churn_risk = ltv.calculate_churn_risk()

        # Value category
        ltv.value_category = ltv.calculate_value_category()

        # Engagement score (simple formula)
        ltv.engagement_score = LTVService._calculate_engagement_score(ltv)

        ltv.save()

        return ltv

    @staticmethod
    def _calculate_engagement_score(ltv) -> int:
        """
        Engagement score calculate করো (0-100)।
        """
        score = 0

        # Active days contributes up to 30 points
        score += min(30, ltv.days_active)

        # Task count contributes up to 30 points
        score += min(30, ltv.task_count * 2)

        # Offer count contributes up to 20 points
        score += min(20, ltv.offer_count * 4)

        # LTV value contributes up to 20 points
        ltv_float = float(ltv.lifetime_value)
        if ltv_float >= 500:
            score += 20
        elif ltv_float >= 100:
            score += 10
        elif ltv_float >= 10:
            score += 5

        return min(100, score)

    @staticmethod
    def recalculate_all_for_referrer(referrer) -> dict:
        """
        Referrer এর সব referred users এর LTV recalculate।
        """
        from api.referral.models import Referral

        referrals = Referral.objects.filter(
            referrer=referrer
        ).select_related('referred_user')

        updated = 0
        errors = 0

        for referral in referrals:
            try:
                LTVService.calculate_ltv(
                    referrer=referrer,
                    referred_user=referral.referred_user,
                )
                updated += 1
            except Exception as e:
                logger.error(
                    f"LTV calc error for "
                    f"{referrer.username}/{referral.referred_user.username}: {e}"
                )
                errors += 1

        return {'updated': updated, 'errors': errors}

    @staticmethod
    def recalculate_all(batch_size: int = 200) -> dict:
        """
        সব referrers এর LTV recalculate।
        Weekly Celery task দিয়ে call করা হয়।
        """
        from api.referral.models import Referral

        referrer_ids = Referral.objects.values_list(
            'referrer_id', flat=True
        ).distinct()

        from django.contrib.auth import get_user_model
        User = get_user_model()

        total_updated = 0
        total_errors = 0

        for i in range(0, len(referrer_ids), batch_size):
            batch = referrer_ids[i:i + batch_size]
            referrers = User.objects.filter(id__in=batch)

            for referrer in referrers:
                result = LTVService.recalculate_all_for_referrer(referrer)
                total_updated += result['updated']
                total_errors += result['errors']

        logger.info(
            f"LTV recalculation complete: "
            f"{total_updated} updated, {total_errors} errors"
        )
        return {'updated': total_updated, 'errors': total_errors}

    @staticmethod
    def get_ltv_report(referrer, limit: int = 50) -> dict:
        """
        Referrer এর LTV report।
        Top referred users by LTV।
        """
        from api.referral.models import ReferralLTV
        from django.db.models import Sum, Avg, Count

        ltvs = ReferralLTV.objects.filter(
            referred_by=referrer
        ).select_related('user').order_by('-lifetime_value')[:limit]

        summary = ReferralLTV.objects.filter(referred_by=referrer).aggregate(
            total_ltv=Sum('lifetime_value'),
            avg_ltv=Avg('lifetime_value'),
            high_value=Count('id', filter=__import__(
                'django.db.models', fromlist=['Q']
            ).Q(value_category='high_value')),
            churned=Count('id', filter=__import__(
                'django.db.models', fromlist=['Q']
            ).Q(churn_risk='churned')),
            total=Count('id'),
        )

        return {
            'summary': {
                'total_ltv': float(summary['total_ltv'] or 0),
                'avg_ltv': float(summary['avg_ltv'] or 0),
                'high_value_users': summary['high_value'] or 0,
                'churned_users': summary['churned'] or 0,
                'total_referred': summary['total'] or 0,
            },
            'top_users': [{
                'user_id': ltv.user.id,
                'username': ltv.user.username,
                'lifetime_value': float(ltv.lifetime_value),
                'total_user_earnings': float(ltv.total_user_earnings),
                'task_count': ltv.task_count,
                'offer_count': ltv.offer_count,
                'days_active': ltv.days_active,
                'engagement_score': ltv.engagement_score,
                'churn_risk': ltv.churn_risk,
                'value_category': ltv.value_category,
                'last_activity': (
                    ltv.last_activity.strftime('%Y-%m-%d')
                    if ltv.last_activity else None
                ),
            } for ltv in ltvs],
        }

    @staticmethod
    def get_churn_at_risk(referrer, risk_level: str = 'high') -> list:
        """
        Churn risk এ থাকা referred users।
        """
        from api.referral.models import ReferralLTV

        ltvs = ReferralLTV.objects.filter(
            referred_by=referrer,
            churn_risk__in=[risk_level, 'churned'] if risk_level == 'high' else [risk_level],
        ).select_related('user').order_by('-lifetime_value')

        return [{
            'username': ltv.user.username,
            'lifetime_value': float(ltv.lifetime_value),
            'churn_risk': ltv.churn_risk,
            'days_since_activity': (
                (timezone.now() - ltv.last_activity).days
                if ltv.last_activity else None
            ),
            'engagement_score': ltv.engagement_score,
        } for ltv in ltvs]