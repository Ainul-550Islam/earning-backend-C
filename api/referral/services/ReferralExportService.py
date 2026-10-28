# api/referral/services/ReferralExportService.py
# CSV export for referral reports
# ============================================================

import csv
import io
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ReferralExportService:
    """
    CSV export service for referral reports।
    Admin এবং user উভয়ের জন্য।
    """

    @staticmethod
    def export_referrals_csv(
        referrer=None,
        date_from=None,
        date_to=None,
        include_suspicious: bool = True,
    ) -> str:
        """
        Referral list export করো CSV হিসেবে।
        referrer=None → সব referrals (admin only)।
        """
        from api.referral.models import Referral

        qs = Referral.objects.select_related(
            'referrer', 'referred_user'
        ).order_by('-created_at')

        if referrer:
            qs = qs.filter(referrer=referrer)

        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        if not include_suspicious:
            qs = qs.filter(is_suspicious=False)

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'ID', 'Referrer', 'Referred User',
            'Level', 'Signup Bonus Given',
            'Total Commission Earned',
            'Is Suspicious', 'Suspicious Reason',
            'Registration IP', 'Joined Date',
        ])

        for r in qs:
            writer.writerow([
                r.id,
                r.referrer.username,
                r.referred_user.username,
                r.level,
                'Yes' if r.signup_bonus_given else 'No',
                float(r.total_commission_earned),
                'Yes' if r.is_suspicious else 'No',
                r.suspicious_reason or '',
                r.registration_ip or '',
                r.created_at.strftime('%Y-%m-%d %H:%M'),
            ])

        return output.getvalue()

    @staticmethod
    def export_earnings_csv(
        referrer=None,
        date_from=None,
        date_to=None,
        level: int = None,
    ) -> str:
        """
        ReferralEarning list export।
        """
        from api.referral.models import ReferralEarning

        qs = ReferralEarning.objects.select_related(
            'referrer', 'referred_user'
        ).order_by('-created_at')

        if referrer:
            qs = qs.filter(referrer=referrer)

        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        if level:
            qs = qs.filter(level=level)

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'ID', 'Referrer', 'From User',
            'Level', 'Amount', 'Commission Rate %',
            'Source Amount', 'Source Type', 'Status',
            'Campaign Multiplier', 'Date',
        ])

        for e in qs:
            writer.writerow([
                e.id,
                e.referrer.username,
                e.referred_user.username,
                e.level,
                float(e.amount or 0),
                float(e.commission_rate or 0),
                float(e.source_amount or 0),
                e.source_type,
                e.status,
                float(e.campaign_multiplier or 1),
                e.created_at.strftime('%Y-%m-%d %H:%M'),
            ])

        return output.getvalue()

    @staticmethod
    def export_commission_logs_csv(
        user=None,
        date_from=None,
        date_to=None,
        status: str = None,
    ) -> str:
        """CommissionLog export।"""
        from api.referral.models import CommissionLog

        qs = CommissionLog.objects.select_related(
            'user', 'referred_user', 'rule'
        ).order_by('-created_at')

        if user:
            qs = qs.filter(user=user)

        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        if status:
            qs = qs.filter(status=status)

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'ID', 'User', 'From User',
            'Amount', 'Base Amount', 'Commission Rate %',
            'Level', 'Action Type', 'Status',
            'Source Reference', 'Date',
        ])

        for c in qs:
            writer.writerow([
                c.id,
                c.user.username,
                c.referred_user.username,
                float(c.amount),
                float(c.base_amount),
                float(c.commission_rate),
                c.level,
                c.action_type,
                c.status,
                c.source_reference,
                c.created_at.strftime('%Y-%m-%d %H:%M'),
            ])

        return output.getvalue()

    @staticmethod
    def export_top_referrers_csv(period: str = 'alltime', limit: int = 100) -> str:
        """Top referrers export।"""
        from api.referral.models import Referral, ReferralEarning
        from django.db.models import Sum, Count, Q
        from django.contrib.auth import get_user_model

        User = get_user_model()

        top = Referral.objects.values('referrer').annotate(
            total=Count('id'),
            active=Count('id', filter=Q(referred_user__is_active=True)),
            commission=Sum('total_commission_earned'),
        ).order_by('-total')[:limit]

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Rank', 'Username', 'Email',
            'Total Referrals', 'Active Referrals',
            'Total Commission Earned',
        ])

        for rank, item in enumerate(top, start=1):
            try:
                user = User.objects.get(id=item['referrer'])
            except User.DoesNotExist:
                continue

            writer.writerow([
                rank,
                user.username,
                getattr(user, 'email', ''),
                item['total'],
                item['active'],
                float(item['commission'] or 0),
            ])

        return output.getvalue()

    @staticmethod
    def export_ltv_report_csv(referrer) -> str:
        """LTV report CSV export।"""
        from api.referral.models import ReferralLTV

        ltvs = ReferralLTV.objects.filter(
            referred_by=referrer
        ).select_related('user').order_by('-lifetime_value')

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Username', 'Lifetime Value (৳)',
            'Total User Earnings (৳)',
            'Task Count', 'Offer Count',
            'Days Active', 'Engagement Score',
            'Churn Risk', 'Value Category',
            'Last Activity',
        ])

        for ltv in ltvs:
            writer.writerow([
                ltv.user.username,
                float(ltv.lifetime_value),
                float(ltv.total_user_earnings),
                ltv.task_count,
                ltv.offer_count,
                ltv.days_active,
                ltv.engagement_score,
                ltv.churn_risk,
                ltv.value_category,
                ltv.last_activity.strftime('%Y-%m-%d') if ltv.last_activity else '',
            ])

        return output.getvalue()

    @staticmethod
    def export_fraud_log_csv(date_from=None, date_to=None) -> str:
        """Fraud log export (admin only)।"""
        from api.referral.models import SuspiciousReferral

        qs = SuspiciousReferral.objects.select_related(
            'referral', 'referral__referrer', 'referral__referred_user',
            'reviewed_by'
        ).order_by('-detected_at')

        if date_from:
            qs = qs.filter(detected_at__date__gte=date_from)

        if date_to:
            qs = qs.filter(detected_at__date__lte=date_to)

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Referral ID', 'Referrer', 'Referred User',
            'Fraud Score', 'Status', 'Flags',
            'Reviewed By', 'Detected At', 'Reviewed At',
        ])

        for sr in qs:
            writer.writerow([
                sr.referral.id,
                sr.referral.referrer.username,
                sr.referral.referred_user.username,
                sr.fraud_score,
                sr.status,
                ', '.join(sr.get_flag_list()),
                sr.reviewed_by.username if sr.reviewed_by else '',
                sr.detected_at.strftime('%Y-%m-%d %H:%M'),
                sr.reviewed_at.strftime('%Y-%m-%d %H:%M') if sr.reviewed_at else '',
            ])

        return output.getvalue()

    @staticmethod
    def get_filename(report_type: str, suffix: str = '') -> str:
        """Export filename generate করো।"""
        date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
        suffix_str = f'_{suffix}' if suffix else ''
        return f"referral_{report_type}{suffix_str}_{date_str}.csv"