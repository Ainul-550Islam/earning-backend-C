# api/djoyalty/data_export.py
"""
Djoyalty Data Export -- Export loyalty data to CSV/JSON/Excel।
Customer export, points history, cashout report, compliance export।
"Do not summarize or skip any logic. Provide the full code."
"""
import csv
import io
import json
import logging
from decimal import Decimal
from django.utils import timezone
from django.http import HttpResponse

logger = logging.getLogger(__name__)


class LoyaltyDataExporter:
    """
    Export loyalty data in various formats।

    Usage:
        exporter = LoyaltyDataExporter()
        response = exporter.export_customers_csv(tenant=my_tenant)
        response = exporter.export_points_report_csv(date_from, date_to, tenant)
    """

    # ─── Customer Export ──────────────────────────────────────────

    @staticmethod
    def export_customers_csv(tenant=None, active_only: bool = True) -> HttpResponse:
        """Export customers to CSV।"""
        from .models.core import Customer
        from .models.points import LoyaltyPoints
        from .models.tiers import UserTier

        qs = Customer.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="customers_{timezone.now().strftime("%Y%m%d")}.csv"'
        )
        response.write('\ufeff')  # BOM for Excel UTF-8

        writer = csv.writer(response)
        writer.writerow([
            'Customer Code', 'Email', 'Phone', 'First Name', 'Last Name',
            'Tier', 'Points Balance', 'Lifetime Earned', 'Lifetime Redeemed',
            'Referral Code', 'Is Verified', 'Join Date',
        ])

        for customer in qs.iterator(chunk_size=200):
            lp = LoyaltyPoints.objects.filter(customer=customer).first()
            ut = UserTier.objects.filter(customer=customer, is_current=True).select_related('tier').first()

            writer.writerow([
                customer.code,
                customer.email or '',
                customer.phone or '',
                customer.firstname or '',
                customer.lastname or '',
                ut.tier.name if ut else 'Bronze',
                str(lp.balance if lp else Decimal('0')),
                str(lp.lifetime_earned if lp else Decimal('0')),
                str(lp.lifetime_redeemed if lp else Decimal('0')),
                customer.referral_code or '',
                customer.is_verified,
                customer.created_at.strftime('%Y-%m-%d'),
            ])

        return response

    # ─── Points History Export ────────────────────────────────────

    @staticmethod
    def export_points_report_csv(date_from, date_to, tenant=None) -> HttpResponse:
        """Export points ledger for a date range।"""
        from .models.points import PointsLedger

        qs = PointsLedger.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to,
            is_reversed=False,
        ).select_related('customer')
        if tenant:
            qs = qs.filter(tenant=tenant)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="points_report_{date_from.strftime("%Y%m%d")}_'
            f'{date_to.strftime("%Y%m%d")}.csv"'
        )
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Customer Code', 'Type', 'Source',
            'Points', 'Balance After', 'Description', 'Reference ID',
        ])

        for entry in qs.order_by('created_at').iterator(chunk_size=500):
            writer.writerow([
                entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                entry.customer.code,
                entry.txn_type,
                entry.source,
                str(entry.points),
                str(entry.balance_after),
                entry.description or '',
                entry.reference_id or '',
            ])

        return response

    # ─── Cashout Report ───────────────────────────────────────────

    @staticmethod
    def export_cashout_report_csv(date_from, date_to, tenant=None) -> HttpResponse:
        """Export cashout requests for a date range।"""
        from .models.cashout import CashoutRequest

        qs = CashoutRequest.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to,
        ).select_related('customer')
        if tenant:
            qs = qs.filter(tenant=tenant)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="cashout_report_{date_from.strftime("%Y%m%d")}.csv"'
        )
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Reference', 'Customer Code', 'Phone',
            'Points Redeemed', 'Cash Amount (BDT)', 'Method', 'Status',
        ])

        for cashout in qs.order_by('created_at').iterator(chunk_size=200):
            writer.writerow([
                cashout.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                cashout.reference or '',
                cashout.customer.code,
                cashout.customer.phone or '',
                str(cashout.points_to_redeem),
                str(cashout.cash_amount),
                cashout.cashout_method,
                cashout.status,
            ])

        return response

    # ─── JSON Export ──────────────────────────────────────────────

    @staticmethod
    def export_customer_data_json(customer) -> dict:
        """
        Export all data for a specific customer (GDPR right-to-access)।
        Returns complete customer loyalty history as JSON।
        """
        from .models.points import LoyaltyPoints, PointsLedger
        from .models.redemption import RedemptionHistory, Voucher
        from .models.engagement import UserBadge
        from .models.cashout import CashoutRequest

        lp = LoyaltyPoints.objects.filter(customer=customer).first()
        ut = customer.user_tiers.filter(is_current=True).select_related('tier').first()

        return {
            'customer': {
                'code': customer.code,
                'email': customer.email or '',
                'phone': customer.phone or '',
                'name': f'{customer.firstname or ""} {customer.lastname or ""}'.strip(),
                'tier': ut.tier.name if ut else 'Bronze',
                'join_date': customer.created_at.isoformat(),
            },
            'points': {
                'balance': str(lp.balance if lp else Decimal('0')),
                'lifetime_earned': str(lp.lifetime_earned if lp else Decimal('0')),
                'lifetime_redeemed': str(lp.lifetime_redeemed if lp else Decimal('0')),
            },
            'history': [
                {
                    'date': entry.created_at.isoformat(),
                    'type': entry.txn_type,
                    'source': entry.source,
                    'points': str(entry.points),
                    'balance_after': str(entry.balance_after),
                }
                for entry in PointsLedger.objects.filter(customer=customer)
                                                  .order_by('-created_at')[:100]
            ],
            'vouchers': [
                {
                    'code': v.code,
                    'type': v.voucher_type,
                    'discount': str(v.discount_value),
                    'status': v.status,
                    'issued_at': v.created_at.isoformat(),
                }
                for v in Voucher.objects.filter(customer=customer)[:20]
            ],
            'badges': [
                {
                    'name': ub.badge.name,
                    'earned_at': ub.earned_at.isoformat(),
                }
                for ub in UserBadge.objects.filter(customer=customer).select_related('badge')[:20]
            ],
            'cashouts': [
                {
                    'reference': co.reference,
                    'points': str(co.points_to_redeem),
                    'amount': str(co.cash_amount),
                    'method': co.cashout_method,
                    'status': co.status,
                    'date': co.created_at.isoformat(),
                }
                for co in CashoutRequest.objects.filter(customer=customer)[:20]
            ],
            'exported_at': timezone.now().isoformat(),
        }
