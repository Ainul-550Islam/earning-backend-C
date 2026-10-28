"""
tests/factories.py — Test factories for offerwall models.

Used by all test files. Provides simple create() helpers that
don't require factory_boy so the test suite has zero extra dependencies.
"""
import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# Core model factories
# ─────────────────────────────────────────────────────────────

class OfferProviderFactory:
    _counter = 0

    def __new__(cls, **kwargs):
        from api.offerwall.models import OfferProvider
        cls._counter += 1
        defaults = dict(
            name          = kwargs.pop('name', f'Provider-{cls._counter}'),
            provider_type = kwargs.pop('provider_type', 'tapjoy'),
            status        = kwargs.pop('status', 'active'),
            api_key       = kwargs.pop('api_key', f'key-{cls._counter}'),
            api_secret    = kwargs.pop('api_secret', f'secret-{cls._counter}'),
            secret_key    = kwargs.pop('secret_key', f'wh-secret-{cls._counter}'),
            revenue_share = kwargs.pop('revenue_share', Decimal('70.00')),
        )
        defaults.update(kwargs)
        return OfferProvider.objects.create(**defaults)


class OfferCategoryFactory:
    _counter = 0

    def __new__(cls, **kwargs):
        from api.offerwall.models import OfferCategory
        cls._counter += 1
        defaults = dict(
            name         = kwargs.pop('name', f'Category-{cls._counter}'),
            slug         = kwargs.pop('slug', f'category-{cls._counter}'),
            is_active    = kwargs.pop('is_active', True),
            display_order= kwargs.pop('display_order', cls._counter),
        )
        defaults.update(kwargs)
        return OfferCategory.objects.create(**defaults)


class OfferFactory:
    _counter = 0

    def __new__(cls, **kwargs):
        from api.offerwall.models import Offer
        cls._counter += 1
        provider = kwargs.pop('provider', None) or OfferProviderFactory()
        defaults = dict(
            provider           = provider,
            external_offer_id  = kwargs.pop('external_offer_id',
                                            f'ext-{cls._counter}'),
            title              = kwargs.pop('title', f'Offer {cls._counter}'),
            description        = kwargs.pop('description', 'Test offer description'),
            offer_type         = kwargs.pop('offer_type', 'app_install'),
            platform           = kwargs.pop('platform', 'all'),
            payout             = kwargs.pop('payout', Decimal('0.50')),
            currency           = kwargs.pop('currency', 'USD'),
            reward_amount      = kwargs.pop('reward_amount', Decimal('55')),
            reward_currency    = kwargs.pop('reward_currency', 'BDT'),
            status             = kwargs.pop('status', 'active'),
            is_featured        = kwargs.pop('is_featured', False),
            is_trending        = kwargs.pop('is_trending', False),
            is_recommended     = kwargs.pop('is_recommended', False),
            is_high_risk       = kwargs.pop('is_high_risk', False),
            quality_score      = kwargs.pop('quality_score', 50.0),
        )
        defaults.update(kwargs)
        return Offer.objects.create(**defaults)


class OfferClickFactory:
    _counter = 0

    def __new__(cls, **kwargs):
        from api.offerwall.models import OfferClick
        cls._counter += 1
        offer = kwargs.pop('offer', None) or OfferFactory()
        user  = kwargs.pop('user', None)
        defaults = dict(
            offer      = offer,
            user       = user,
            click_id   = kwargs.pop('click_id', f'click-{cls._counter}'),
            ip_address = kwargs.pop('ip_address', '127.0.0.1'),
            user_agent = kwargs.pop('user_agent', 'Mozilla/5.0 (test)'),
        )
        defaults.update(kwargs)
        return OfferClick.objects.create(**defaults)


class OfferConversionFactory:
    _counter = 0

    def __new__(cls, **kwargs):
        from api.offerwall.models import OfferConversion
        cls._counter += 1
        offer = kwargs.pop('offer', None) or OfferFactory()
        user  = kwargs.pop('user', None) or User.objects.create_user(
            f'conv_user_{cls._counter}', password='pw')
        defaults = dict(
            offer           = offer,
            user            = user,
            conversion_id   = kwargs.pop('conversion_id',
                                         f'conv-{cls._counter}-{uuid.uuid4().hex[:8]}'),
            payout_amount   = kwargs.pop('payout_amount', Decimal('0.50')),
            payout_currency = kwargs.pop('payout_currency', 'USD'),
            reward_amount   = kwargs.pop('reward_amount', Decimal('55')),
            reward_currency = kwargs.pop('reward_currency', 'BDT'),
            bonus_amount    = kwargs.pop('bonus_amount', Decimal('0')),
            status          = kwargs.pop('status', 'pending'),
        )
        defaults.update(kwargs)
        return OfferConversion.objects.create(**defaults)


class ContentLockFactory:
    _counter = 0

    def __new__(cls, **kwargs):
        from api.offerwall.content_lock import ContentLock
        cls._counter += 1
        publisher = kwargs.pop('publisher', None) or User.objects.create_user(
            f'lock_pub_{cls._counter}', password='pw')
        defaults = dict(
            publisher            = publisher,
            title                = kwargs.pop('title', f'Lock {cls._counter}'),
            lock_type            = kwargs.pop('lock_type', 'offerwall'),
            required_conversions = kwargs.pop('required_conversions', 1),
            is_active            = kwargs.pop('is_active', True),
        )
        defaults.update(kwargs)
        return ContentLock.objects.create(**defaults)
