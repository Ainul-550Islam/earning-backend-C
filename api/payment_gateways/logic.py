# api/payment_gateways/logic.py
# Business logic helpers shared across all payment_gateways

from decimal import Decimal


def calculate_fee(amount: Decimal, gateway: str, transaction_type: str = 'deposit') -> Decimal:
    """Calculate gateway fee for an amount."""
    try:
        from api.payment_gateways.models.gateway_config import GatewayFeeRule
        from api.payment_gateways.models.core import PaymentGateway
        gw   = PaymentGateway.objects.get(name=gateway)
        rule = GatewayFeeRule.objects.filter(gateway=gw, transaction_type=transaction_type, is_active=True).first()
        if rule:
            return rule.calculate(amount)
        return (amount * gw.transaction_fee_percentage) / 100
    except Exception:
        from api.payment_gateways.constants import GATEWAY_FEES
        rate = Decimal(str(GATEWAY_FEES.get(gateway, 0.015)))
        return (amount * rate).quantize(Decimal('0.01'))


def generate_reference_id(prefix: str, gateway: str = '') -> str:
    """Generate a unique reference ID."""
    import time, secrets
    gw_part = gateway.upper()[:4] if gateway else 'SYS'
    ts      = str(int(time.time() * 1000))[-8:]
    rnd     = secrets.token_hex(3).upper()
    return f'{prefix}-{gw_part}-{ts}-{rnd}'


def get_next_payout_date(schedule_type: str):
    """Get next payout date for a schedule type."""
    from api.payment_gateways.utils.DateUtils import DateUtils
    return DateUtils.next_payout_date(schedule_type)


def is_gateway_available(gateway_name: str) -> bool:
    """Quick check if a gateway is available."""
    try:
        from api.payment_gateways.models.core import PaymentGateway
        return PaymentGateway.objects.filter(name=gateway_name, status='active').exists()
    except Exception:
        return False


def get_geo_payout(amount: Decimal, country: str, gateway: str = '') -> Decimal:
    """Get GEO-adjusted payout amount."""
    from api.payment_gateways.services.GeoPricingEngine import GeoPricingEngine
    return GeoPricingEngine().calculate_geo_payout(amount, country)
