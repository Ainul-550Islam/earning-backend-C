"""
api/offerwall/b2b/services.py

B2B Service Layer — "One task, one owner."

Architecture fix: b2b/views.py had direct model ops scattered inline
(client.save(), B2BInvoice.objects.create(), B2BOnboarding.objects.create()).
These are now centralised here. Views become thin dispatch layers.
"""
import logging
from decimal import Decimal
from django.utils import timezone
from .models import B2BClient, B2BPlan, B2BUsageRecord, B2BInvoice, B2BOnboarding

logger = logging.getLogger(__name__)


class B2BClientService:

    @staticmethod
    def upgrade_plan(client: B2BClient, plan_type: str) -> dict:
        new_plan = B2BPlan.objects.filter(
            plan_type=plan_type, is_active=True).first()
        if not new_plan:
            available = list(B2BPlan.objects.filter(
                is_active=True).values_list('plan_type', flat=True))
            return {'success': False, 'error': 'invalid_plan',
                    'available': available}

        old_type = client.plan.plan_type if client.plan else 'none'
        client.plan            = new_plan
        client.plan_started_at = timezone.now()
        client.save(update_fields=['plan', 'plan_started_at', 'updated_at'])

        if hasattr(client, 'onboarding'):
            client.onboarding.complete_step('plan')

        logger.info(f'[B2BService] plan upgrade: {client.company_name} '
                    f'{old_type} → {new_plan.plan_type}')
        return {'success': True, 'plan': new_plan}

    @staticmethod
    def verify_client(client: B2BClient, admin_user=None) -> dict:
        client.status     = 'verified'
        client.verified_at = timezone.now()
        client.save(update_fields=['status', 'verified_at', 'updated_at'])
        logger.info(f'[B2BService] verified: {client.company_name}')
        return {'success': True, 'status': 'verified'}

    @staticmethod
    def activate_client(client: B2BClient) -> dict:
        client.activate()
        logger.info(f'[B2BService] activated: {client.company_name}')
        return {'success': True, 'status': 'active'}

    @staticmethod
    def suspend_client(client: B2BClient, reason: str = '') -> dict:
        client.suspend(reason)
        logger.info(f'[B2BService] suspended: {client.company_name}')
        return {'success': True, 'status': 'suspended'}

    @staticmethod
    def complete_onboarding_step(client: B2BClient, step: str) -> dict:
        if not hasattr(client, 'onboarding'):
            B2BOnboarding.objects.create(client=client)
            client.refresh_from_db()

        if step not in B2BOnboarding.STEP_ORDER:
            return {'success': False, 'error': 'invalid_step',
                    'valid': B2BOnboarding.STEP_ORDER}

        client.onboarding.complete_step(step)

        if step == 'profile' and client.status == 'pending':
            client.status      = 'verified'
            client.verified_at = timezone.now()
            client.save(update_fields=['status', 'verified_at', 'updated_at'])

        return {
            'success':        True,
            'step':           step,
            'completion_pct': client.onboarding.completion_pct(),
            'next_step':      client.onboarding.next_step_display(),
            'is_complete':    client.onboarding.is_complete,
        }

    @staticmethod
    def get_dashboard_data(client: B2BClient) -> dict:
        usage        = client.get_current_usage()
        can_call, reason = client.can_make_api_call()
        return {
            'quota': {
                'api_calls_used':    usage.api_calls,
                'api_calls_limit':   client.plan.monthly_api_calls if client.plan else 0,
                'quota_pct':         usage.quota_pct(),
                'can_make_api_call': can_call,
                'block_reason':      reason,
            },
            'revenue': {
                'gross_usd':              str(usage.gross_revenue_usd),
                'your_share_usd':         str(usage.publisher_share_usd),
                'your_share_pct':         str(client.effective_revenue_share),
                'conversions_this_month': usage.conversions,
            },
            'onboarding': {
                'pct':         client.onboarding.completion_pct()
                               if hasattr(client, 'onboarding') else 0,
                'next_step':   client.onboarding.next_step_display()
                               if hasattr(client, 'onboarding') else '',
                'is_complete': client.onboarding.is_complete
                               if hasattr(client, 'onboarding') else False,
            },
        }


class B2BInvoiceService:

    @staticmethod
    def generate_for_period(year: int, month: int) -> dict:
        """Generate invoices for all active clients. Idempotent."""
        created = skipped = errors = 0
        results = []
        usd_to_bdt = Decimal('110')

        for client in B2BClient.objects.filter(
                status='active').select_related('plan'):
            try:
                if B2BInvoice.objects.filter(
                        client=client, period_year=year,
                        period_month=month).exists():
                    skipped += 1
                    continue

                usage = B2BUsageRecord.objects.filter(
                    client=client, period_year=year,
                    period_month=month).first()

                plan_fee      = client.plan.monthly_price_bdt if client.plan else Decimal('0')
                rev_share_usd = usage.publisher_share_usd if usage else Decimal('0')
                rev_share_bdt = (rev_share_usd * usd_to_bdt).quantize(Decimal('0.01'))
                tax           = (plan_fee * Decimal('0.15')).quantize(Decimal('0.01'))
                total_due     = (plan_fee + tax).quantize(Decimal('0.01'))
                total_payable = max(Decimal('0'), total_due - rev_share_bdt)

                inv = B2BInvoice.objects.create(
                    client=client,
                    invoice_number=B2BInvoice.generate_number(client, year, month),
                    period_year=year, period_month=month,
                    plan_fee_bdt=plan_fee,
                    revenue_share_usd=rev_share_usd,
                    revenue_share_bdt=rev_share_bdt,
                    tax_bdt=tax,
                    total_due_bdt=total_due,
                    total_payable_bdt=total_payable,
                    status='issued',
                    issued_at=timezone.now(),
                )
                created += 1
                results.append({'client': client.company_name,
                                 'invoice': inv.invoice_number,
                                 'total_payable_bdt': str(total_payable)})
            except Exception as e:
                errors += 1
                logger.error(f'[B2BInvoice] {client.company_name}: {e}')

        return {
            'period':   f'{year}/{month:02d}',
            'created':  created,
            'skipped':  skipped,
            'errors':   errors,
            'invoices': results,
        }
