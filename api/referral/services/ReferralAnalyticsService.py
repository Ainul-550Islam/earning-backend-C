# api/referral/services/ReferralAnalyticsService.py
# Daily analytics, top referrers, insights calculation
# ============================================================

from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
import logging
from api.referral.models.analytics import ReferralInsight

logger = logging.getLogger(__name__)


class ReferralAnalyticsService:
    """
    Analytics calculation service।
    Celery tasks দিয়ে daily/weekly trigger হয়।
    """

    @staticmethod
    @transaction.atomic
    def calculate_daily_insight(date=None) -> 'ReferralInsight':
        """
        Specific date এর daily insight calculate করো।
        Default: আজকের।
        """
        from api.referral.models import (
            ReferralInsight, Referral, ReferralEarning, ReferralCode
        )
        from django.db.models import Sum, Count, Q

        if not date:
            date = timezone.now().date()

        day_start = timezone.datetime.combine(date, timezone.datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = timezone.datetime.combine(date, timezone.datetime.max.time()).replace(tzinfo=timezone.utc)

        # New referrals
        new_refs = Referral.objects.filter(
            created_at__date=date
        )
        new_count = new_refs.count()

        # Commission paid
        earnings_qs = ReferralEarning.objects.filter(
            created_at__date=date
        )
        earnings_agg = earnings_qs.aggregate(
            total=Sum('amount'),
            l1=Sum('amount', filter=Q(level=1)),
            l2=Sum('amount', filter=Q(level=2)),
            l3=Sum('amount', filter=Q(level=3)),
        )

        # Conversion (clicks → signups)
        code_stats = ReferralCode.objects.aggregate(
            total_clicks=Sum('clicks'),
        )
        total_clicks = code_stats.get('total_clicks') or 0
        conversion_rate = (
            round((new_count / total_clicks) * 100, 2)
            if total_clicks > 0 else 0
        )

        # Fraud
        flagged = Referral.objects.filter(
            created_at__date=date, is_suspicious=True
        ).count()
        fraud_rate = round((flagged / new_count) * 100, 2) if new_count > 0 else 0

        # Active referrers (who had activity today)
        active_referrers = ReferralEarning.objects.filter(
            created_at__date=date
        ).values('referrer').distinct().count()

        insight, _ = ReferralInsight.objects.update_or_create(
            date=date,
            defaults={
                'new_referrals': new_count,
                'commission_paid': earnings_agg['total'] or Decimal('0'),
                'commission_l1': earnings_agg['l1'] or Decimal('0'),
                'commission_l2': earnings_agg['l2'] or Decimal('0'),
                'commission_l3': earnings_agg['l3'] or Decimal('0'),
                'total_clicks': total_clicks,
                'total_signups': new_count,
                'conversion_rate': Decimal(str(conversion_rate)),
                'flagged_referrals': flagged,
                'fraud_rate': Decimal(str(fraud_rate)),
                'active_referrers': active_referrers,
            }
        )

        logger.info(f"Daily insight calculated for {date}: {new_count} refs")
        return insight

    @staticmethod
    @transaction.atomic
    def snapshot_top_referrers(period: str = 'daily', date=None) -> int:
        """
        Top referrers snapshot নাও।
        Celery task দিয়ে daily/weekly call করা হয়।
        """
        from api.referral.models import TopReferrer, Referral, ReferralEarning
        from django.db.models import Count, Sum, Q
        from django.contrib.auth import get_user_model

        if not date:
            date = timezone.now().date()

        User = get_user_model()

        # Period cutoff
        if period == 'daily':
            cutoff = timezone.now() - timedelta(days=1)
        elif period == 'weekly':
            cutoff = timezone.now() - timedelta(days=7)
        elif period == 'monthly':
            cutoff = timezone.now() - timedelta(days=30)
        else:
            cutoff = None  # alltime

        ref_qs = Referral.objects.all()
        if cutoff:
            ref_qs = ref_qs.filter(created_at__gte=cutoff)

        top = ref_qs.values('referrer').annotate(
            count=Count('id'),
            active=Count('id', filter=Q(referred_user__is_active=True)),
        ).order_by('-count')[:50]

        earn_qs = ReferralEarning.objects.all()
        if cutoff:
            earn_qs = earn_qs.filter(created_at__gte=cutoff)

        created = 0

        for rank, item in enumerate(top, start=1):
            try:
                user = User.objects.get(id=item['referrer'])
            except User.DoesNotExist:
                continue

            earnings = earn_qs.filter(referrer=user).aggregate(
                total=Sum('amount'),
                l1=Sum('amount', filter=Q(level=1)),
                l2=Sum('amount', filter=Q(level=2)),
                l3=Sum('amount', filter=Q(level=3)),
            )

            TopReferrer.objects.update_or_create(
                date=date,
                period=period,
                user=user,
                defaults={
                    'rank': rank,
                    'referral_count': item['count'],
                    'active_referral_count': item['active'],
                    'commission_earned': earnings['total'] or Decimal('0'),
                    'l1_count': item['count'],
                    'l1_commission': earnings['l1'] or Decimal('0'),
                    'l2_commission': earnings['l2'] or Decimal('0'),
                    'l3_commission': earnings['l3'] or Decimal('0'),
                }
            )
            created += 1

        logger.info(
            f"Top referrers snapshot: {created} entries [{period}] for {date}"
        )
        return created

    @staticmethod
    def get_dashboard_summary(days: int = 30) -> dict:
        """Admin dashboard summary।"""
        from api.referral.models import ReferralInsight, Referral, ReferralEarning
        from django.db.models import Sum, Count, Avg

        cutoff = timezone.now() - timedelta(days=days)

        insights = ReferralInsight.objects.filter(
            date__gte=cutoff.date()
        ).aggregate(
            total_refs=Sum('new_referrals'),
            total_commission=Sum('commission_paid'),
            avg_conversion=Avg('conversion_rate'),
            total_clicks=Sum('total_clicks'),
            flagged=Sum('flagged_referrals'),
        )

        # Total all-time
        total_referrals_alltime = Referral.objects.count()
        total_commission_alltime = ReferralEarning.objects.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        # Today
        today = ReferralInsight.objects.filter(
            date=timezone.now().date()
        ).first()

        return {
            'period_days': days,
            'period': {
                'total_referrals': insights['total_refs'] or 0,
                'total_commission': float(insights['total_commission'] or 0),
                'avg_conversion_rate': float(insights['avg_conversion'] or 0),
                'total_clicks': insights['total_clicks'] or 0,
                'flagged_referrals': insights['flagged'] or 0,
            },
            'alltime': {
                'total_referrals': total_referrals_alltime,
                'total_commission': float(total_commission_alltime),
            },
            'today': {
                'new_referrals': today.new_referrals if today else 0,
                'commission_paid': float(today.commission_paid) if today else 0,
                'active_referrers': today.active_referrers if today else 0,
            } if today else None,
        }

    @staticmethod
    def get_insight_chart_data(days: int = 30) -> list:
        """Chart data for admin dashboard।"""
        from api.referral.models import ReferralInsight

        cutoff = timezone.now().date() - timedelta(days=days)
        insights = ReferralInsight.objects.filter(
            date__gte=cutoff
        ).order_by('date')

        return [{
            'date': str(i.date),
            'new_referrals': i.new_referrals,
            'commission_paid': float(i.commission_paid),
            'conversion_rate': float(i.conversion_rate),
            'active_referrers': i.active_referrers,
            'flagged': i.flagged_referrals,
        } for i in insights]

    @staticmethod
    @transaction.atomic
    def update_code_conversion_rates(date=None) -> int:
        """
        সব active codes এর conversion rate update করো।
        """
        from api.referral.models import ReferralCode, ReferralConversionRate, Referral
        from django.db.models import Count

        if not date:
            date = timezone.now().date()

        codes = ReferralCode.objects.filter(is_active=True)
        updated = 0

        for code in codes:
            # Signups via this code
            signups = Referral.objects.filter(
                created_at__date=date,
                referrer=code.user,
            ).count()

            rate, _ = ReferralConversionRate.objects.get_or_create(
                code=code,
                date=date,
            )
            rate.clicks = code.clicks
            rate.unique_clicks = code.unique_clicks
            rate.signups += signups
            rate.save(update_fields=['clicks', 'unique_clicks', 'signups'])
            rate.calculate_rates()
            updated += 1

        return updated