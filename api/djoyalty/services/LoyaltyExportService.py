# api/djoyalty/services/LoyaltyExportService.py
"""
LoyaltyExportService -- CSV/JSON data export।
GDPR compliance সহ customer data export।
"""
import csv
import io
import json
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class LoyaltyExportService:

    @staticmethod
    def export_customers_csv(tenant=None, is_active: bool = None) -> str:
        """All customers CSV export।"""
        try:
            from ..models.core import Customer
            qs = Customer.objects.all().order_by('code')
            if tenant:
                qs = qs.filter(tenant=tenant)
            if is_active is not None:
                qs = qs.filter(is_active=is_active)

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Code', 'Loyalty Number', 'First Name', 'Last Name', 'Email', 'Phone',
                'City', 'Country', 'Is Active', 'Newsletter', 'Points Balance',
                'Lifetime Earned', 'Current Tier', 'Member Since',
            ])
            for c in qs.prefetch_related('loyalty_points', 'user_tiers__tier'):
                lp = c.loyalty_points.first()
                ut = c.user_tiers.filter(is_current=True).first()
                writer.writerow([
                    c.code, c.loyalty_number or '',
                    c.firstname or '', c.lastname or '',
                    c.email or '', c.phone or '',
                    c.city or '', c.country or '',
                    c.is_active, c.newsletter,
                    str(lp.balance if lp else 0),
                    str(lp.lifetime_earned if lp else 0),
                    ut.tier.name if ut and ut.tier else 'bronze',
                    c.created_at.strftime('%Y-%m-%d'),
                ])
            return output.getvalue()
        except Exception as e:
            logger.error('LoyaltyExportService.export_customers_csv error: %s', e)
            return ''

    @staticmethod
    def export_ledger_csv(customer=None, tenant=None, days: int = 90) -> str:
        """Points ledger CSV export।"""
        try:
            from ..models.points import PointsLedger
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=days)
            qs = PointsLedger.objects.filter(created_at__gte=cutoff).order_by('-created_at')
            if customer:
                qs = qs.filter(customer=customer)
            elif tenant:
                qs = qs.filter(tenant=tenant)

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Date', 'Customer Code', 'Type', 'Source', 'Points', 'Balance After',
                'Description', 'Reference', 'Expires At',
            ])
            for entry in qs.select_related('customer'):
                writer.writerow([
                    entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    entry.customer.code if entry.customer else '',
                    entry.txn_type, entry.source,
                    str(entry.points), str(entry.balance_after),
                    entry.description or '',
                    entry.reference_id or '',
                    entry.expires_at.strftime('%Y-%m-%d') if entry.expires_at else '',
                ])
            return output.getvalue()
        except Exception as e:
            logger.error('LoyaltyExportService.export_ledger_csv error: %s', e)
            return ''

    @staticmethod
    def export_customer_gdpr(customer) -> dict:
        """
        GDPR compliant full customer data export।
        Customer সব data একটি JSON dict এ।
        """
        try:
            from ..models.points import LoyaltyPoints, PointsLedger
            from ..models.redemption import RedemptionRequest, Voucher
            from ..models.tiers import UserTier, TierHistory

            lp = customer.loyalty_points.first()
            ledger = list(PointsLedger.objects.filter(customer=customer).order_by('-created_at').values(
                'txn_type', 'source', 'points', 'balance_after', 'description', 'created_at'
            ))
            for entry in ledger:
                entry['created_at'] = entry['created_at'].isoformat()

            redemptions = list(RedemptionRequest.objects.filter(customer=customer).values(
                'points_used', 'redemption_type', 'reward_value', 'status', 'created_at'
            ))
            for r in redemptions:
                r['created_at'] = r['created_at'].isoformat()
                r['points_used'] = str(r['points_used'])
                r['reward_value'] = str(r['reward_value'])

            tier_history = list(TierHistory.objects.filter(customer=customer).select_related(
                'from_tier', 'to_tier'
            ).order_by('-changed_at').values(
                'change_type', 'points_at_change', 'changed_at'
            ))
            for t in tier_history:
                t['changed_at'] = t['changed_at'].isoformat()
                t['points_at_change'] = str(t['points_at_change'])

            return {
                'export_date': timezone.now().isoformat(),
                'customer': {
                    'code': customer.code,
                    'loyalty_number': customer.loyalty_number,
                    'firstname': customer.firstname,
                    'lastname': customer.lastname,
                    'email': customer.email,
                    'phone': customer.phone,
                    'city': customer.city,
                    'country': customer.country,
                    'date_of_birth': customer.date_of_birth.isoformat() if customer.date_of_birth else None,
                    'newsletter': customer.newsletter,
                    'member_since': customer.created_at.isoformat(),
                },
                'points': {
                    'current_balance': str(lp.balance if lp else 0),
                    'lifetime_earned': str(lp.lifetime_earned if lp else 0),
                    'lifetime_redeemed': str(lp.lifetime_redeemed if lp else 0),
                },
                'ledger_history': ledger,
                'redemption_history': redemptions,
                'tier_history': tier_history,
                'badges': list(customer.user_badges.select_related('badge').values(
                    'badge__name', 'points_awarded', 'earned_at'
                )),
            }
        except Exception as e:
            logger.error('LoyaltyExportService.export_customer_gdpr error: %s', e)
            return {}

    @staticmethod
    def export_insights_csv(tenant=None, period: str = 'daily') -> str:
        """Insights CSV export।"""
        try:
            from ..models.advanced import LoyaltyInsight
            qs = LoyaltyInsight.objects.filter(period=period).order_by('-report_date')
            if tenant:
                qs = qs.filter(tenant=tenant)

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Report Date', 'Period', 'Total Customers', 'Active Customers', 'New Customers',
                'Points Issued', 'Points Redeemed', 'Points Expired',
                'Total Transactions', 'Total Revenue', 'Redemption Rate',
            ])
            for insight in qs:
                writer.writerow([
                    insight.report_date.strftime('%Y-%m-%d'), insight.period,
                    insight.total_customers, insight.active_customers, insight.new_customers,
                    str(insight.total_points_issued), str(insight.total_points_redeemed),
                    str(insight.total_points_expired), insight.total_transactions,
                    str(insight.total_revenue), str(insight.redemption_rate),
                ])
            return output.getvalue()
        except Exception as e:
            logger.error('LoyaltyExportService.export_insights_csv error: %s', e)
            return ''
