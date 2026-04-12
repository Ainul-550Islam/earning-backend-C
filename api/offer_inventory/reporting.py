# api/offer_inventory/reporting.py
"""
Unified Reporting Module.
Central entry point for all platform reports.
Delegates to business/reporting_suite.py for implementation.
"""
import csv
import io
import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.http import HttpResponse

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Master report generator.
    Single entry point for all report types.
    """

    # ── Offer Reports ─────────────────────────────────────────────

    @staticmethod
    def offer_performance(days: int = 30, offer_id: str = None,
                           format: str = 'json') -> object:
        """Per-offer performance report."""
        from api.offer_inventory.analytics import OfferAnalytics

        if offer_id:
            data = OfferAnalytics.get_offer_stats(offer_id, days=days)
        else:
            data = OfferAnalytics.get_top_performers(metric='revenue', days=days, limit=50)

        if format == 'csv':
            return ReportGenerator._to_csv(
                data if isinstance(data, list) else [data],
                filename='offer_performance.csv'
            )
        return data

    @staticmethod
    def offer_cap_usage(format: str = 'json') -> object:
        """Current offer cap utilization."""
        from api.offer_inventory.models import OfferCap
        from django.db.models import F

        caps = list(
            OfferCap.objects.select_related('offer')
            .values(
                'offer__title', 'cap_type', 'cap_limit',
                'current_count', 'pause_on_hit'
            )
            .order_by('-current_count')[:100]
        )
        for cap in caps:
            limit = cap.get('cap_limit', 1) or 1
            cap['usage_pct'] = round(cap.get('current_count', 0) / limit * 100, 1)

        if format == 'csv':
            return ReportGenerator._to_csv(caps, filename='offer_cap_usage.csv')
        return caps

    # ── Conversion Reports ────────────────────────────────────────

    @staticmethod
    def conversion_summary(days: int = 30, tenant=None) -> dict:
        """High-level conversion summary."""
        from api.offer_inventory.models import Conversion
        from django.db.models import Count, Sum

        since = timezone.now() - timedelta(days=days)
        qs    = Conversion.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)

        agg = qs.aggregate(
            total     =Count('id'),
            approved  =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status__name='approved')),
            rejected  =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status__name='rejected')),
            duplicates=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_duplicate=True)),
            revenue   =Sum('payout_amount', filter=__import__('django.db.models', fromlist=['Q']).Q(status__name='approved')),
            rewards   =Sum('reward_amount', filter=__import__('django.db.models', fromlist=['Q']).Q(status__name='approved')),
        )
        return {
            'period_days'       : days,
            'total'             : agg['total'] or 0,
            'approved'          : agg['approved'] or 0,
            'rejected'          : agg['rejected'] or 0,
            'duplicates_blocked': agg['duplicates'] or 0,
            'approval_rate_pct' : round((agg['approved'] or 0) / max(agg['total'] or 1, 1) * 100, 2),
            'gross_revenue'     : float(agg['revenue'] or 0),
            'user_rewards'      : float(agg['rewards'] or 0),
            'platform_profit'   : float((agg['revenue'] or Decimal('0')) - (agg['rewards'] or Decimal('0'))),
        }

    @staticmethod
    def postback_delivery_report(days: int = 7) -> dict:
        """Postback delivery success/failure rates."""
        from api.offer_inventory.models import PostbackLog
        from django.db.models import Count

        since = timezone.now() - timedelta(days=days)
        agg   = PostbackLog.objects.filter(created_at__gte=since).aggregate(
            total  =Count('id'),
            success=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_success=True)),
            failed =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_success=False)),
        )
        return {
            'total'        : agg['total'] or 0,
            'success'      : agg['success'] or 0,
            'failed'       : agg['failed'] or 0,
            'success_rate' : round((agg['success'] or 0) / max(agg['total'] or 1, 1) * 100, 1),
            'period_days'  : days,
        }

    # ── User Reports ──────────────────────────────────────────────

    @staticmethod
    def user_growth(days: int = 30) -> list:
        """Daily new user registrations."""
        from django.contrib.auth import get_user_model
        from django.db.models.functions import TruncDate
        from django.db.models import Count

        User  = get_user_model()
        since = timezone.now() - timedelta(days=days)
        return list(
            User.objects.filter(date_joined__gte=since)
            .annotate(date=TruncDate('date_joined'))
            .values('date')
            .annotate(new_users=Count('id'))
            .order_by('date')
        )

    @staticmethod
    def user_lifetime_value_distribution() -> dict:
        """LTV distribution across user segments."""
        from api.offer_inventory.models import Conversion
        from django.db.models import Sum, Count

        user_ltv = list(
            Conversion.objects.filter(status__name='approved')
            .values('user_id')
            .annotate(ltv=Sum('reward_amount'))
            .values_list('ltv', flat=True)
        )

        if not user_ltv:
            return {}

        values = sorted([float(v) for v in user_ltv])
        n      = len(values)
        return {
            'total_users' : n,
            'avg_ltv'     : round(sum(values) / n, 2),
            'median_ltv'  : round(values[n // 2], 2),
            'p90_ltv'     : round(values[int(n * 0.9)], 2) if n > 10 else 0,
            'p99_ltv'     : round(values[int(n * 0.99)], 2) if n > 100 else 0,
            'max_ltv'     : round(max(values), 2),
            'tiers'       : {
                'zero'  : len([v for v in values if v == 0]),
                'low'   : len([v for v in values if 0 < v < 100]),
                'medium': len([v for v in values if 100 <= v < 1000]),
                'high'  : len([v for v in values if v >= 1000]),
            },
        }

    # ── Financial Reports ─────────────────────────────────────────

    @staticmethod
    def payout_reconciliation(month: str = None) -> dict:
        """
        Monthly payout reconciliation.
        month: 'YYYY-MM' format (default: current month)
        """
        from api.offer_inventory.models import WalletAudit
        from django.db.models import Sum, Count

        if month:
            year, mo = month.split('-')
            from django.utils.dateparse import parse_date
            start = parse_date(f'{year}-{mo}-01')
        else:
            now   = timezone.now()
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        from dateutil.relativedelta import relativedelta
        try:
            end = start + relativedelta(months=1)
        except ImportError:
            import calendar
            _, last_day = calendar.monthrange(start.year, start.month)
            end = start.replace(day=last_day, hour=23, minute=59, second=59)

        agg = WalletAudit.objects.filter(
            created_at__gte=start,
            created_at__lt =end,
        ).aggregate(
            total_credits =Sum('amount', filter=__import__('django.db.models', fromlist=['Q']).Q(transaction_type__in=['credit', 'conversion_payout'])),
            total_debits  =Sum('amount', filter=__import__('django.db.models', fromlist=['Q']).Q(transaction_type__in=['debit', 'withdrawal'])),
            credit_count  =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(transaction_type='conversion_payout')),
            withdrawal_count=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(transaction_type='withdrawal')),
        )

        return {
            'period'            : str(start)[:7],
            'total_credits'     : float(agg['total_credits'] or 0),
            'total_debits'      : float(agg['total_debits'] or 0),
            'net'               : float((agg['total_credits'] or 0) - (agg['total_debits'] or 0)),
            'conversion_payouts': agg['credit_count'] or 0,
            'withdrawals'       : agg['withdrawal_count'] or 0,
        }

    # ── Utilities ─────────────────────────────────────────────────

    @staticmethod
    def _to_csv(data: list, filename: str = 'report.csv') -> HttpResponse:
        """Convert list of dicts to CSV response."""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')   # UTF-8 BOM for Excel

        if not data:
            return response

        writer = csv.DictWriter(response, fieldnames=data[0].keys())
        writer.writeheader()
        for row in data:
            writer.writerow({k: str(v) for k, v in row.items()})
        return response

    @staticmethod
    def get_available_reports() -> list:
        """List all available report types."""
        return [
            {'name': 'offer_performance',    'description': 'Per-offer clicks, conversions, revenue'},
            {'name': 'offer_cap_usage',       'description': 'Offer cap utilization percentage'},
            {'name': 'conversion_summary',    'description': 'High-level conversion metrics'},
            {'name': 'postback_delivery',     'description': 'Postback success/failure rates'},
            {'name': 'user_growth',           'description': 'Daily new user registrations'},
            {'name': 'user_ltv_distribution', 'description': 'Lifetime value distribution'},
            {'name': 'payout_reconciliation', 'description': 'Monthly payout reconciliation'},
            {'name': 'revenue_report',        'description': 'Daily revenue breakdown (CSV/JSON)'},
            {'name': 'fraud_report',          'description': 'Fraud summary and top fraud sources'},
            {'name': 'network_comparison',    'description': 'Side-by-side network ROI comparison'},
        ]
