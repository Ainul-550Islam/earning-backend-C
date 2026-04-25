# api/payment_gateways/context_processors.py
# Django template context processors for payment_gateways
# Add to TEMPLATES[0]['OPTIONS']['context_processors'] in settings.py

from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def payment_gateway_context(request):
    """
    Injects payment gateway data into every template context.

    Add to settings.py:
        TEMPLATES = [{
            'OPTIONS': {
                'context_processors': [
                    ...
                    'api.payment_gateways.context_processors.payment_gateway_context',
                ],
            },
        }]

    Available in templates:
        {{ ACTIVE_GATEWAYS }}         — list of active gateway dicts
        {{ PAYMENT_GATEWAYS }}        — dict keyed by gateway name
        {{ BD_GATEWAYS }}             — BD-only gateways
        {{ GLOBAL_GATEWAYS }}         — International gateways
        {{ USER_BALANCE }}            — Current user's balance (if authenticated)
        {{ GATEWAY_HEALTH }}          — Gateway health status dict
        {{ PENDING_PAYOUTS_COUNT }}   — User's pending payout requests count
    """
    ctx = {
        'ACTIVE_GATEWAYS':      [],
        'PAYMENT_GATEWAYS':     {},
        'BD_GATEWAYS':          [],
        'GLOBAL_GATEWAYS':      [],
        'USER_BALANCE':         Decimal('0'),
        'GATEWAY_HEALTH':       {},
        'PENDING_PAYOUTS_COUNT':0,
        'DEPOSIT_GATEWAYS':     [],
        'WITHDRAWAL_GATEWAYS':  [],
    }

    # Load gateway list (cached)
    try:
        from django.core.cache import cache
        gateways = cache.get('ctx_active_gateways')

        if gateways is None:
            from api.payment_gateways.models.core import PaymentGateway
            qs = PaymentGateway.objects.filter(status='active').values(
                'name', 'display_name', 'color_code', 'health_status',
                'supports_deposit', 'supports_withdrawal', 'region',
                'minimum_amount', 'maximum_amount', 'transaction_fee_percentage',
            )
            gateways = list(qs)
            cache.set('ctx_active_gateways', gateways, 300)  # 5 min cache

        ctx['ACTIVE_GATEWAYS']  = gateways
        ctx['PAYMENT_GATEWAYS'] = {g['name']: g for g in gateways}
        ctx['BD_GATEWAYS']      = [g for g in gateways if g['region'] == 'BD']
        ctx['GLOBAL_GATEWAYS']  = [g for g in gateways if g['region'] != 'BD']
        ctx['DEPOSIT_GATEWAYS'] = [g for g in gateways if g['supports_deposit']]
        ctx['WITHDRAWAL_GATEWAYS'] = [g for g in gateways if g['supports_withdrawal']]

        # Gateway health (from cache)
        ctx['GATEWAY_HEALTH'] = {
            g['name']: g['health_status'] for g in gateways
        }
    except Exception as e:
        logger.debug(f'payment_gateway_context: gateway load error: {e}')

    # User-specific data (only if authenticated)
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            # Balance
            ctx['USER_BALANCE'] = Decimal(str(getattr(request.user, 'balance', '0') or '0'))
        except Exception:
            pass

        try:
            # Pending payouts count
            from api.payment_gateways.models.core import PayoutRequest
            ctx['PENDING_PAYOUTS_COUNT'] = PayoutRequest.objects.filter(
                user=request.user, status='pending'
            ).count()
        except Exception:
            pass

    return ctx


def payment_settings_context(request):
    """
    Injects payment gateway settings into templates.

    Available in templates:
        {{ SITE_URL }}
        {{ SUPPORT_EMAIL }}
        {{ MIN_WITHDRAWAL }}
        {{ PAYOUT_SCHEDULE }}
    """
    from django.conf import settings
    return {
        'SITE_URL':       getattr(settings, 'SITE_URL', 'https://yourdomain.com'),
        'SUPPORT_EMAIL':  getattr(settings, 'SUPPORT_EMAIL', 'support@yourdomain.com'),
        'MIN_WITHDRAWAL': getattr(settings, 'MIN_WITHDRAWAL_AMOUNT', 1),
        'PAYOUT_SCHEDULE':getattr(settings, 'DEFAULT_PAYOUT_SCHEDULE', 'net30'),
        'FAST_PAY_ENABLED':getattr(settings, 'FAST_PAY_ENABLED', True),
        'USDT_FAST_PAY_MIN':getattr(settings, 'USDT_FAST_PAY_MIN', 25),
    }
