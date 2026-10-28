# api/referral/background_jobs.py
# Long-running background job definitions
# These are Celery tasks designed for heavy processing (>1 minute)
# Use separate queue: 'referral_background'
# ============================================================

import logging

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(
        name='referral.bg.full_ltv_recalculation',
        bind=True,
        soft_time_limit=300,
        time_limit=600,
        queue='referral_low',
    )
    def full_ltv_recalculation(self) -> dict:
        """
        Recalculate LTV for ALL referred users.
        Long-running — may take several minutes for large datasets.
        Run weekly.
        """
        from api.referral.models import Referral, ReferralLTV
        from api.referral.logic import calculate_ltv, categorize_ltv_value, estimate_churn_risk
        from decimal import Decimal
        from django.utils import timezone

        referrals = Referral.objects.select_related(
            'referrer', 'referred_user'
        ).iterator(chunk_size=100)

        updated = 0
        errors = 0

        for referral in referrals:
            try:
                user = referral.referred_user
                from api.referral.models import ReferralEarning
                from django.db.models import Sum, Count
                from datetime import timedelta

                earnings = ReferralEarning.objects.filter(
                    referred_user=user, status='released'
                )
                total_earnings = earnings.aggregate(t=Sum('source_amount'))['t'] or Decimal('0')
                task_count = earnings.filter(source_type='task').count()
                offer_count = earnings.filter(source_type='offer').count()
                last_activity = earnings.order_by('-created_at').values_list('created_at', flat=True).first()
                days_since = (timezone.now() - last_activity).days if last_activity else 9999
                days_active = max(0, (timezone.now() - user.date_joined).days - days_since)

                ltv = calculate_ltv(total_earnings, days_active, task_count, offer_count)
                category = categorize_ltv_value(ltv)
                churn_risk = estimate_churn_risk(days_since)

                ReferralLTV.objects.update_or_create(
                    user=user, referred_by=referral.referrer,
                    defaults={
                        'lifetime_value': ltv,
                        'total_user_earnings': total_earnings,
                        'task_count': task_count,
                        'offer_count': offer_count,
                        'days_active': days_active,
                        'churn_risk': churn_risk,
                        'value_category': category,
                        'last_activity': last_activity,
                    }
                )
                updated += 1
            except Exception as e:
                errors += 1
                logger.error(f'[BgJob] LTV calc failed for {referral.id}: {e}')

        return {'updated': updated, 'errors': errors}


    @shared_task(
        name='referral.bg.full_tree_rebuild',
        bind=True,
        soft_time_limit=600,
        time_limit=1200,
        queue='referral_low',
    )
    def full_tree_rebuild(self) -> dict:
        """
        Rebuild ALL referral trees from scratch.
        Very long-running — emergency repair only.
        """
        from api.referral.services.ReferralTreeService import ReferralTreeService
        from api.referral.models import Referral

        referrer_ids = list(
            Referral.objects.values_list('referrer_id', flat=True).distinct()
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()

        rebuilt = 0
        errors = 0

        for user in User.objects.filter(id__in=referrer_ids):
            try:
                ReferralTreeService.rebuild_tree(user)
                rebuilt += 1
            except Exception as e:
                errors += 1
                logger.error(f'[BgJob] Tree rebuild failed for {user.id}: {e}')

        return {'rebuilt': rebuilt, 'errors': errors}


    @shared_task(
        name='referral.bg.sync_all_user_counts',
        bind=True,
        soft_time_limit=300,
        time_limit=600,
        queue='referral_low',
    )
    def sync_all_user_counts(self) -> dict:
        """
        Sync user.total_referrals and user.referral_earnings for ALL users.
        One-time fix or weekly maintenance.
        """
        from api.referral.INTEGRATION_SYSTEM.sync_manager import ReferralSyncManager
        sm = ReferralSyncManager()
        return sm.sync_user_referral_counts(dry_run=False)


    @shared_task(
        name='referral.bg.generate_monthly_report',
        bind=True,
        queue='referral_low',
    )
    def generate_monthly_report(self, year: int = None, month: int = None) -> dict:
        """
        Generate comprehensive monthly referral report.
        Saves to file or sends via email.
        """
        from django.utils import timezone
        now = timezone.now()
        year = year or now.year
        month = month or now.month

        from api.referral.analytics import ReferralAnalytics
        from api.referral.data_export import ReferralDataExport

        funnel    = ReferralAnalytics.get_referral_funnel(days=30)
        cohorts   = ReferralAnalytics.get_cohort_data(cohort_months=3)
        campaigns = ReferralAnalytics.get_campaign_performance()

        report = {
            'period':    f'{year}-{month:02d}',
            'funnel':    funnel,
            'cohorts':   cohorts,
            'campaigns': campaigns,
            'generated': timezone.now().isoformat(),
        }

        logger.info(f'[BgJob] Monthly report generated: {year}-{month:02d}')
        return report


    @shared_task(
        name='referral.bg.expire_old_email_invitations',
        queue='referral_low',
    )
    def expire_old_email_invitations() -> dict:
        """Mark expired email invitations."""
        from api.referral.models import ReferralEmailInvitation
        from django.utils import timezone

        expired = ReferralEmailInvitation.objects.filter(
            expires_at__lt=timezone.now(),
            status__in=['pending', 'sent', 'opened'],
        )
        count = expired.count()
        expired.update(status='expired')
        return {'expired': count}


    @shared_task(
        name='referral.bg.warm_all_caches',
        queue='referral_low',
    )
    def warm_all_caches() -> dict:
        """Pre-warm all referral caches."""
        from api.referral.caching import warm_referral_caches
        return warm_referral_caches()

except ImportError:
    logger.debug('[BgJobs] Celery not available')