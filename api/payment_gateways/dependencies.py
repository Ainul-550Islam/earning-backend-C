# api/payment_gateways/dependencies.py
# DRF dependency injection helpers (FastAPI-style)

from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from decimal import Decimal


def get_active_gateway(gateway_name: str):
    """Get active gateway or raise 404."""
    from api.payment_gateways.models.core import PaymentGateway
    try:
        return PaymentGateway.objects.get(name=gateway_name, status='active')
    except PaymentGateway.DoesNotExist:
        raise NotFound(f'Gateway {gateway_name} not found or inactive')


def get_publisher_profile(user):
    """Get publisher profile or raise 403."""
    try:
        from api.payment_gateways.publisher.models import PublisherProfile
        return PublisherProfile.objects.get(user=user, status='active')
    except Exception:
        raise PermissionDenied('Active publisher profile required')


def validate_deposit_payload(data: dict) -> dict:
    """Validate and return clean deposit data."""
    from api.payment_gateways.validators import validate_amount, validate_gateway, validate_currency
    gateway  = validate_gateway(data.get('gateway', ''))
    amount   = validate_amount(data.get('amount', 0))
    currency = validate_currency(data.get('currency', 'BDT'))
    return {'gateway': gateway, 'amount': amount, 'currency': currency}


def get_current_exchange_rates() -> dict:
    """Get cached exchange rates."""
    from api.payment_gateways.services.MultiCurrencyEngine import MultiCurrencyEngine
    return MultiCurrencyEngine().get_all_rates()
