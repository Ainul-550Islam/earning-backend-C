# api/offer_inventory/business/reporting_suite.py
"""
Business Reporting Suite.
Generates CSV, JSON, and structured reports for:
- Platform revenue, conversions, clicks
- Advertiser performance
- User earnings
- Network comparison
- Fraud summary
- Withdrawal reports
All ready for Excel, BI tools, or API consumption.
"""
import csv
import io
import json
import logging
from decimal import Decimal
from datetime import timedelta
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q

logger = logging.getLogger(__name__)


class ReportingEngine:
    """Unified reporting engine — all platform reports."""

    # ── Platform Revenue Report ────────────────────────────────────

    @staticmethod
    def revenue_report(days: int = 30, format: str = 'json',
                        tenant=None) -> object:
        """
        Daily revenue breakdown.
        format: 'json' | 'csv'
        """
        from api.offer_inventory.models import DailyStat

        since = timezone.now().date() - timedelta(days=days)
        stats = DailyStat.objects.filter(date__gte=since)
        if tenant:
            stats = stats.filter(tenant=tenant)
        stats = stats.order_by('date')

        if format == 'csv':
            return ReportingEngine._daily_stats_csv(stats)

        return [{
            'date'               : str(s.date),
            'total_clicks'       : s.total_clicks,
            'unique_clicks'      : s.unique_clicks,
            'total_conversions'  : s.total_conversions,
            'approved_conversions': s.approved_conversions,
            'rejected_conversions': s.rejected_conversions,
            'gross_revenue'      : float(s.total_revenue),
            'user_payouts'       : float(s.user_payouts),
            'platform_profit'    : float(s.platform_profit),
            'new_users'          : s.new_users,
            'active_users'       : s.active_users,
            'fraud_attempts'     : s.fraud_attempts,
            'cvr_pct'            : float(s.cvr),
        } for s in stats]

    @staticmethod
    def _daily_stats_csv(stats) -> HttpResponse:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="revenue_report.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Clicks', 'Unique Clicks', 'Conversions', 'Approved',
            'Rejected', 'Gross Revenue', 'User Payouts', 'Platform Profit',
            'New Users', 'CVR%', 'Fraud Attempts',
        ])
        for s in stats:
            writer.writerow([
                s.date, s.total_clicks, s.unique_clicks,
                s.total_conversions, s.approved_conversions, s.rejected_conversions,
                s.total_revenue, s.user_payouts, s.platform_profit,
                s.new_users, s.cvr, s.fraud_attempts,
            ])
        return response

    # ── Conversion Report ──────────────────────────────────────────

    @staticmethod
    def conversion_report(days: int = 30, status: str = None,
                           format: str = 'json') -> object:
        """Detailed conversion report."""
        from api.offer_inventory.models import Conversion

        since = timezone.now() - timedelta(days=days)
        qs    = Conversion.objects.filter(
            created_at__gte=since
        ).select_related('offer', 'user', 'status', 'offer__network')

        if status:
            qs = qs.filter(status__name=status)

        qs = qs.order_by('-created_at')

        if format == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="conversions.csv"'
            response.write('\ufeff')
            writer = csv.writer(response)
            writer.writerow([
                'ID', 'Date', 'User', 'Offer', 'Network', 'Status',
                'Payout', 'Reward', 'Country', 'Transaction ID', 'Postback Sent',
            ])
            for c in qs[:10000]:
                writer.writerow([
                    str(c.id)[:8], c.created_at.strftime('%Y-%m-%d %H:%M'),
                    c.user.username if c.user else '',
                    c.offer.title if c.offer else '',
                    c.offer.network.name if c.offer and c.offer.network else '',
                    c.status.name if c.status else '',
                    c.payout_amount, c.reward_amount, c.country_code,
                    c.transaction_id, c.postback_sent,
                ])
            return response

        return [{
            'id'           : str(c.id),
            'date'         : c.created_at.isoformat(),
            'user'         : c.user.username if c.user else None,
            'offer'        : c.offer.title if c.offer else None,
            'network'      : c.offer.network.name if c.offer and c.offer.network else None,
            'status'       : c.status.name if c.status else None,
            'payout'       : float(c.payout_amount),
            'reward'       : float(c.reward_amount),
            'country'      : c.country_code,
            'transaction_id': c.transaction_id,
            'postback_sent': c.postback_sent,
            'is_duplicate' : c.is_duplicate,
        } for c in qs[:10000]]

    # ── Withdrawal Report ──────────────────────────────────────────

    @staticmethod
    def withdrawal_report(days: int = 30, status: str = None,
                           format: str = 'json') -> object:
        """Withdrawal request report."""
        from api.offer_inventory.models import WithdrawalRequest

        since = timezone.now() - timedelta(days=days)
        qs    = WithdrawalRequest.objects.filter(
            created_at__gte=since
        ).select_related('user', 'payment_method')
        if status:
            qs = qs.filter(status=status)
        qs = qs.order_by('-created_at')

        if format == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="withdrawals.csv"'
            response.write('\ufeff')
            writer = csv.writer(response)
            writer.writerow([
                'Reference', 'Date', 'User', 'Amount', 'Fee', 'Net',
                'Status', 'Provider', 'Processed At',
            ])
            for wr in qs[:10000]:
                writer.writerow([
                    wr.reference_no,
                    wr.created_at.strftime('%Y-%m-%d %H:%M'),
                    wr.user.username if wr.user else '',
                    wr.amount, wr.fee, wr.net_amount, wr.status,
                    wr.payment_method.provider if wr.payment_method else '',
                    wr.processed_at.strftime('%Y-%m-%d %H:%M') if wr.processed_at else '',
                ])
            return response

        return [{
            'reference'   : wr.reference_no,
            'date'        : wr.created_at.isoformat(),
            'user'        : wr.user.username if wr.user else None,
            'amount'      : float(wr.amount),
            'fee'         : float(wr.fee),
            'net'         : float(wr.net_amount),
            'status'      : wr.status,
            'provider'    : wr.payment_method.provider if wr.payment_method else None,
            'processed_at': wr.processed_at.isoformat() if wr.processed_at else None,
        } for wr in qs[:10000]]

    # ── Fraud Report ───────────────────────────────────────────────

    @staticmethod
    def fraud_report(days: int = 30) -> dict:
        """Fraud summary report."""
        from api.offer_inventory.models import (
            Click, FraudAttempt, BlacklistedIP,
            UserRiskProfile, HoneypotLog
        )

        since = timezone.now() - timedelta(days=days)
        return {
            'fraud_clicks'    : Click.objects.filter(created_at__gte=since, is_fraud=True).count(),
            'fraud_attempts'  : FraudAttempt.objects.filter(created_at__gte=since).count(),
            'ips_blocked'     : BlacklistedIP.objects.filter(created_at__gte=since).count(),
            'users_suspended' : UserRiskProfile.objects.filter(is_suspended=True).count(),
            'honeypot_hits'   : HoneypotLog.objects.filter(created_at__gte=since).count(),
            'top_fraud_ips'   : list(
                Click.objects.filter(created_at__gte=since, is_fraud=True)
                .values('ip_address')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            ),
            'fraud_by_country': list(
                Click.objects.filter(created_at__gte=since, is_fraud=True)
                .exclude(country_code='')
                .values('country_code')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            ),
        }

    # ── Network Comparison ─────────────────────────────────────────

    @staticmethod
    def network_comparison(days: int = 30) -> list:
        """Side-by-side network performance comparison."""
        from api.offer_inventory.models import OfferNetwork, Click, Conversion

        since = timezone.now() - timedelta(days=days)
        networks = OfferNetwork.objects.filter(status='active')
        results  = []

        for net in networks:
            clicks  = Click.objects.filter(offer__network=net, created_at__gte=since, is_fraud=False).count()
            fraud   = Click.objects.filter(offer__network=net, created_at__gte=since, is_fraud=True).count()
            conv_agg = Conversion.objects.filter(
                offer__network=net, created_at__gte=since, status__name='approved'
            ).aggregate(count=Count('id'), rev=Sum('payout_amount'), rew=Sum('reward_amount'))

            count   = conv_agg['count'] or 0
            revenue = Decimal(str(conv_agg['rev'] or 0))
            rewards = Decimal(str(conv_agg['rew'] or 0))

            results.append({
                'network'        : net.name,
                'slug'           : net.slug,
                'clicks'         : clicks,
                'fraud_rate_pct' : round(fraud / max(clicks + fraud, 1) * 100, 2),
                'conversions'    : count,
                'cvr_pct'        : round(count / max(clicks, 1) * 100, 2),
                'gross_revenue'  : float(revenue),
                'user_rewards'   : float(rewards),
                'platform_profit': float(revenue - rewards),
                'epc'            : float((revenue / Decimal(str(max(clicks, 1)))).quantize(Decimal('0.0001'))),
                'revenue_share'  : float(net.revenue_share_pct),
            })

        return sorted(results, key=lambda x: x['gross_revenue'], reverse=True)

    # ── User Earnings Report ───────────────────────────────────────

    @staticmethod
    def user_earnings_report(days: int = 30, top_n: int = 100,
                              format: str = 'json') -> object:
        """Top earners report."""
        from api.offer_inventory.models import Conversion
        from django.contrib.auth import get_user_model

        since = timezone.now() - timedelta(days=days)
        top_users = (
            Conversion.objects.filter(created_at__gte=since, status__name='approved')
            .values('user__username', 'user__email', 'user_id')
            .annotate(
                total_earned  =Sum('reward_amount'),
                total_conversions=Count('id'),
            )
            .order_by('-total_earned')[:top_n]
        )

        if format == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="user_earnings.csv"'
            response.write('\ufeff')
            writer = csv.writer(response)
            writer.writerow(['Username', 'Email', 'Total Earned', 'Conversions'])
            for u in top_users:
                writer.writerow([
                    u['user__username'], u['user__email'],
                    u['total_earned'], u['total_conversions'],
                ])
            return response

        return [{
            'username'    : u['user__username'],
            'email'       : u['user__email'],
            'total_earned': float(u['total_earned'] or 0),
            'conversions' : u['total_conversions'],
        } for u in top_users]
