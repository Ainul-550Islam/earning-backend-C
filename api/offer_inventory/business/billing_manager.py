# api/offer_inventory/business/billing_manager.py
"""
Billing Manager.
Handles advertiser billing cycles, invoice generation,
payment tracking, credit management, and dunning (overdue collection).
All financial calculations use Decimal exclusively.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

P2 = Decimal('0.01')


class BillingManager:
    """Complete advertiser billing lifecycle."""

    # ── Credit management ──────────────────────────────────────────

    @staticmethod
    def get_advertiser_balance(advertiser_id: str) -> dict:
        """Current advertiser account balance."""
        from api.offer_inventory.models import Campaign, Invoice
        from django.db.models import Sum

        campaigns = Campaign.objects.filter(advertiser_id=advertiser_id)
        total_budget = (campaigns.aggregate(t=Sum('budget'))['t'] or Decimal('0'))
        total_spent  = (campaigns.aggregate(t=Sum('spent'))['t']  or Decimal('0'))
        total_invoiced = (
            Invoice.objects.filter(advertiser_id=advertiser_id)
            .aggregate(t=Sum('amount'))['t'] or Decimal('0')
        )
        total_paid = (
            Invoice.objects.filter(advertiser_id=advertiser_id, is_paid=True)
            .aggregate(t=Sum('amount'))['t'] or Decimal('0')
        )

        return {
            'total_budget'   : float(total_budget),
            'total_spent'    : float(total_spent),
            'remaining_budget': float(total_budget - total_spent),
            'total_invoiced' : float(total_invoiced),
            'total_paid'     : float(total_paid),
            'outstanding'    : float(total_invoiced - total_paid),
        }

    @staticmethod
    @transaction.atomic
    def add_advertiser_credit(advertiser_id: str, amount: Decimal,
                               reference: str = '', added_by=None) -> object:
        """Top up an advertiser's credit balance."""
        from api.offer_inventory.models import DirectAdvertiser, Campaign
        advertiser = DirectAdvertiser.objects.get(id=advertiser_id)

        # Add credit to most recent active campaign
        campaign = Campaign.objects.filter(
            advertiser=advertiser, status='live'
        ).order_by('-created_at').first()

        if campaign:
            from django.db.models import F
            Campaign.objects.filter(id=campaign.id).update(
                budget=F('budget') + amount
            )
            logger.info(
                f'Credit added: {amount} to advertiser={advertiser.company_name} '
                f'campaign={campaign.name}'
            )
            return campaign
        return None

    # ── Invoice generation ─────────────────────────────────────────

    @classmethod
    def generate_monthly_invoices(cls, month: date = None,
                                   tenant=None) -> list:
        """
        Auto-generate invoices for all advertisers for a billing month.
        """
        from api.offer_inventory.models import DirectAdvertiser, Campaign
        from api.offer_inventory.finance_payment.invoice_generator import InvoiceGenerator
        from django.db.models import Sum

        if month is None:
            now   = timezone.now()
            month = (now - timedelta(days=1)).date().replace(day=1)

        month_end   = (month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        advertisers = DirectAdvertiser.objects.filter(is_active=True, is_verified=True)
        if tenant:
            advertisers = advertisers.filter(tenant=tenant)

        generated = []
        for adv in advertisers:
            # Calculate spend for this month
            spend_agg = Campaign.objects.filter(
                advertiser=adv,
            ).aggregate(monthly_spend=Sum('spent'))
            monthly_spend = Decimal(str(spend_agg['monthly_spend'] or '0'))

            if monthly_spend <= Decimal('0'):
                continue

            try:
                invoice = InvoiceGenerator.generate(
                    advertiser_id=str(adv.id),
                    amount       =monthly_spend,
                    due_days     =15,
                    notes        =f'Monthly billing: {month.strftime("%B %Y")}',
                )
                generated.append({
                    'advertiser': adv.company_name,
                    'amount'    : float(monthly_spend),
                    'invoice_no': invoice.invoice_no,
                })
                logger.info(f'Invoice generated: {invoice.invoice_no} | {adv.company_name} | {monthly_spend}')
            except Exception as e:
                logger.error(f'Invoice generation failed for {adv.company_name}: {e}')

        return generated

    # ── Dunning (overdue collection) ───────────────────────────────

    @classmethod
    def run_dunning(cls) -> dict:
        """
        Process overdue invoices.
        Day 1–7: reminder email.
        Day 8–14: pause campaigns.
        Day 15+: suspend account.
        """
        from api.offer_inventory.models import Invoice, Campaign, DirectAdvertiser
        from api.offer_inventory.marketing.email_marketing import EmailMarketingService

        now     = timezone.now()
        overdue = Invoice.objects.filter(
            is_paid=False, due_at__lt=now
        ).select_related('advertiser')

        results = {'reminders': 0, 'paused': 0, 'suspended': 0}

        for invoice in overdue:
            days_overdue = (now - invoice.due_at).days
            adv          = invoice.advertiser

            if days_overdue <= 7:
                # Send reminder email
                try:
                    EmailMarketingService._send(
                        to      =adv.contact_email,
                        subject =f'⚠️ Invoice {invoice.invoice_no} overdue — {days_overdue} days',
                        template='emails/invoice_overdue_reminder.html',
                        context ={'advertiser': adv, 'invoice': invoice, 'days': days_overdue},
                    )
                    results['reminders'] += 1
                except Exception as e:
                    logger.error(f'Dunning reminder error: {e}')

            elif 7 < days_overdue <= 14:
                # Pause all active campaigns
                paused = Campaign.objects.filter(
                    advertiser=adv, status='live'
                ).update(status='paused')
                if paused:
                    results['paused'] += 1
                    logger.warning(
                        f'Campaigns paused for overdue advertiser: '
                        f'{adv.company_name} | days_overdue={days_overdue}'
                    )

            elif days_overdue > 14:
                # Suspend advertiser
                DirectAdvertiser.objects.filter(id=adv.id).update(is_active=False)
                Campaign.objects.filter(advertiser=adv).update(status='ended')
                results['suspended'] += 1
                logger.error(
                    f'Advertiser suspended: {adv.company_name} | '
                    f'days_overdue={days_overdue}'
                )

        return results

    # ── Budget monitoring ──────────────────────────────────────────

    @staticmethod
    def check_budget_alerts(threshold_pct: float = 80.0) -> list:
        """
        Find campaigns that have consumed >= threshold% of budget.
        Returns list of campaigns needing attention.
        """
        from api.offer_inventory.models import Campaign
        alerts = []
        for campaign in Campaign.objects.filter(status='live', budget__gt=0):
            pct_used = float(campaign.spent / campaign.budget * 100) if campaign.budget else 0
            if pct_used >= threshold_pct:
                alerts.append({
                    'campaign_id'  : str(campaign.id),
                    'name'         : campaign.name,
                    'advertiser'   : campaign.advertiser.company_name if campaign.advertiser else '',
                    'budget'       : float(campaign.budget),
                    'spent'        : float(campaign.spent),
                    'pct_used'     : round(pct_used, 1),
                    'remaining'    : float(campaign.remaining_budget),
                })
        return sorted(alerts, key=lambda x: x['pct_used'], reverse=True)

    @staticmethod
    @transaction.atomic
    def auto_pause_depleted_campaigns() -> int:
        """Auto-pause campaigns that have exhausted their budget."""
        from api.offer_inventory.models import Campaign
        from django.db.models import F
        depleted = Campaign.objects.filter(
            status='live',
            budget__gt=0,
        ).filter(spent__gte=F('budget'))

        count = depleted.count()
        depleted.update(status='paused')

        if count > 0:
            logger.info(f'Auto-paused {count} budget-depleted campaigns')

        return count
