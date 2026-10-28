"""
b2b/tests/factories.py — B2B model factories
"""
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()


class B2BPlanFactory:
    _counter = 0

    def __new__(cls, **kwargs):
        from api.offerwall.b2b.models import B2BPlan
        cls._counter += 1
        defaults = dict(
            name                 = kwargs.pop('name', f'Plan {cls._counter}'),
            plan_type            = kwargs.pop('plan_type', 'starter'),
            monthly_price_bdt    = kwargs.pop('monthly_price_bdt', Decimal('2000')),
            monthly_price_usd    = kwargs.pop('monthly_price_usd', Decimal('20')),
            monthly_api_calls    = kwargs.pop('monthly_api_calls', 50000),
            monthly_conversions  = kwargs.pop('monthly_conversions', 500),
            max_active_walls     = kwargs.pop('max_active_walls', 3),
            max_api_keys         = kwargs.pop('max_api_keys', 5),
            revenue_share_pct    = kwargs.pop('revenue_share_pct', Decimal('10')),
            allow_content_lock   = kwargs.pop('allow_content_lock', True),
            allow_bulk_webhook   = kwargs.pop('allow_bulk_webhook', True),
            allow_custom_domain  = kwargs.pop('allow_custom_domain', False),
            allow_white_label    = kwargs.pop('allow_white_label', False),
            allow_survey_offers  = kwargs.pop('allow_survey_offers', False),
            allow_analytics_api  = kwargs.pop('allow_analytics_api', False),
            support_level        = kwargs.pop('support_level', 'email'),
            is_active            = kwargs.pop('is_active', True),
            is_public            = kwargs.pop('is_public', True),
        )
        defaults.update(kwargs)
        return B2BPlan.objects.create(**defaults)


class B2BClientFactory:
    _counter = 0

    def __new__(cls, **kwargs):
        from api.offerwall.b2b.models import B2BClient
        cls._counter += 1
        owner = kwargs.pop('owner', None) or User.objects.create_user(
            f'b2b_owner_{cls._counter}', f'b2b{cls._counter}@test.com', 'pw')
        plan  = kwargs.pop('plan', None) or B2BPlanFactory()
        defaults = dict(
            owner         = owner,
            company_name  = kwargs.pop('company_name', f'Company {cls._counter}'),
            contact_email = kwargs.pop('contact_email', f'b2b{cls._counter}@co.com'),
            business_type = kwargs.pop('business_type', 'web_app'),
            country       = kwargs.pop('country', 'BD'),
            plan          = plan,
            status        = kwargs.pop('status', 'active'),
        )
        defaults.update(kwargs)
        return B2BClient.objects.create(**defaults)
