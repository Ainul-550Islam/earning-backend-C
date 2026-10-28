"""
api/offerwall/management/commands/seed_b2b_plans.py

Creates the 4 default B2B subscription plans.

Run once after migration:
    python manage.py seed_b2b_plans
    python manage.py seed_b2b_plans --reset   (drops and recreates)
"""
from decimal import Decimal
from django.core.management.base import BaseCommand


PLANS = [
    {
        'name':                 'Free',
        'plan_type':            'free',
        'monthly_price_bdt':    Decimal('0'),
        'monthly_price_usd':    Decimal('0'),
        'monthly_api_calls':    1_000,
        'monthly_conversions':  50,
        'max_active_walls':     1,
        'max_api_keys':         1,
        'revenue_share_pct':    Decimal('0'),
        'allow_content_lock':   False,
        'allow_bulk_webhook':   False,
        'allow_custom_domain':  False,
        'allow_white_label':    False,
        'allow_survey_offers':  False,
        'allow_analytics_api':  False,
        'support_level':        'community',
        'is_public':            True,
    },
    {
        'name':                 'Starter',
        'plan_type':            'starter',
        'monthly_price_bdt':    Decimal('2000'),
        'monthly_price_usd':    Decimal('18'),
        'monthly_api_calls':    50_000,
        'monthly_conversions':  500,
        'max_active_walls':     3,
        'max_api_keys':         5,
        'revenue_share_pct':    Decimal('10'),
        'allow_content_lock':   True,
        'allow_bulk_webhook':   False,
        'allow_custom_domain':  False,
        'allow_white_label':    False,
        'allow_survey_offers':  True,
        'allow_analytics_api':  False,
        'support_level':        'email',
        'is_public':            True,
    },
    {
        'name':                 'Pro',
        'plan_type':            'pro',
        'monthly_price_bdt':    Decimal('8000'),
        'monthly_price_usd':    Decimal('72'),
        'monthly_api_calls':    500_000,
        'monthly_conversions':  10_000,
        'max_active_walls':     10,
        'max_api_keys':         20,
        'revenue_share_pct':    Decimal('20'),
        'allow_content_lock':   True,
        'allow_bulk_webhook':   True,
        'allow_custom_domain':  True,
        'allow_white_label':    False,
        'allow_survey_offers':  True,
        'allow_analytics_api':  True,
        'support_level':        'priority',
        'is_public':            True,
    },
    {
        'name':                 'Enterprise',
        'plan_type':            'enterprise',
        'monthly_price_bdt':    Decimal('25000'),
        'monthly_price_usd':    Decimal('225'),
        'monthly_api_calls':    0,           # unlimited
        'monthly_conversions':  0,           # unlimited
        'max_active_walls':     100,
        'max_api_keys':         100,
        'revenue_share_pct':    Decimal('30'),
        'allow_content_lock':   True,
        'allow_bulk_webhook':   True,
        'allow_custom_domain':  True,
        'allow_white_label':    True,
        'allow_survey_offers':  True,
        'allow_analytics_api':  True,
        'support_level':        'dedicated',
        'is_public':            True,
    },
]


class Command(BaseCommand):
    help = 'Create default B2B subscription plans'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete existing plans and recreate')

    def handle(self, *args, **options):
        from api.offerwall.b2b.models import B2BPlan

        if options['reset']:
            deleted, _ = B2BPlan.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing plan(s).'))

        created = updated = 0
        for plan_data in PLANS:
            plan_type = plan_data['plan_type']
            obj, was_created = B2BPlan.objects.update_or_create(
                plan_type=plan_type,
                defaults=plan_data,
            )
            if was_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {obj.name} '
                                       f'(৳{obj.monthly_price_bdt}/mo, '
                                       f'{obj.revenue_share_pct}% rev share)'))
            else:
                updated += 1
                self.stdout.write(f'  ~ Updated: {obj.name}')

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Created: {created}, Updated: {updated}'))
        self.stdout.write(
            f'Total plans: {B2BPlan.objects.count()}')
