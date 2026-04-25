# api/payment_gateways/decorators.py
import functools
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def require_active_gateway(gateway_param='gateway'):
    """Decorator: ensure gateway is active before processing."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            gateway = kwargs.get(gateway_param) or (args[1] if len(args) > 1 else None)
            if gateway:
                try:
                    from api.payment_gateways.models.core import PaymentGateway
                    gw = PaymentGateway.objects.get(name=gateway)
                    if not gw.is_available:
                        raise Exception(f'{gw.display_name} is currently unavailable')
                except Exception as e:
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator


def validate_amount(min_val=Decimal('1'), max_val=Decimal('9999999')):
    """Decorator: validate amount parameter."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            amount = kwargs.get('amount') or (args[2] if len(args) > 2 else None)
            if amount is not None:
                a = Decimal(str(amount))
                if a < min_val:
                    raise ValueError(f'Amount {a} below minimum {min_val}')
                if a > max_val:
                    raise ValueError(f'Amount {a} exceeds maximum {max_val}')
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_publisher(func):
    """Decorator: ensure user is an active publisher."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        user = getattr(self, 'request', None) and self.request.user
        if user:
            from api.payment_gateways.integration_system.auth_bridge import AuthBridge
            AuthBridge().require_publisher(user)
        return func(self, *args, **kwargs)
    return wrapper


def log_payment_event(event_type):
    """Decorator: auto-log payment events to audit log."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                from api.payment_gateways.integration_system.integ_audit_logs import audit_logger
                audit_logger.log(event_type=event_type, source_module='payment_gateways',
                                  result={'status': 'success'}, success=True)
                return result
            except Exception as e:
                from api.payment_gateways.integration_system.integ_audit_logs import audit_logger
                audit_logger.log(event_type=event_type, source_module='payment_gateways',
                                  success=False, error_message=str(e), severity='error')
                raise
        return wrapper
    return decorator


def idempotent(key_param='reference_id', ttl=86400):
    """Decorator: make a function idempotent using reference_id."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = kwargs.get(key_param, '')
            if not key:
                return func(*args, **kwargs)
            from api.payment_gateways.integration_system.sync_manager import sync_manager
            return sync_manager.idempotent_process(
                f'{func.__name__}:{key}',
                lambda: func(*args, **kwargs),
                ttl=ttl
            )
        return wrapper
    return decorator
