# api/djoyalty/dependencies.py
"""
Djoyalty DRF Dependencies -- FastAPI-style dependency injection for DRF।
Reusable request dependencies: get_customer, require_tenant, etc.
"""
import logging
from functools import wraps
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

logger = logging.getLogger(__name__)


def get_customer_from_request(request, id_field='customer_id', raise_404=True):
    """
    Extract and validate customer from request data।
    Usage: customer = get_customer_from_request(request)
    """
    from .models.core import Customer

    customer_id = (
        request.data.get(id_field) or
        request.query_params.get(id_field) or
        request.query_params.get('customer_id')
    )

    if not customer_id:
        if raise_404:
            raise ValidationError({id_field: 'This field is required.'})
        return None

    try:
        return Customer.objects.get(id=customer_id, is_active=True)
    except Customer.DoesNotExist:
        if raise_404:
            raise NotFound(f'Customer #{customer_id} not found.')
        return None


def get_tenant_from_request(request):
    """Extract tenant from request (set by TenantMiddleware)।"""
    return getattr(request, 'tenant', None)


def require_customer(view_func):
    """Decorator: inject customer into view kwargs।"""
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        customer = get_customer_from_request(request)
        kwargs['customer'] = customer
        return view_func(self, request, *args, **kwargs)
    return wrapper


def require_points_balance(min_points: float = 0):
    """Decorator: ensure customer has enough points।"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            customer = kwargs.get('customer') or get_customer_from_request(request)
            from .models.points import LoyaltyPoints
            from decimal import Decimal
            lp = LoyaltyPoints.objects.filter(customer=customer).first()
            balance = lp.balance if lp else Decimal('0')
            if balance < Decimal(str(min_points)):
                raise PermissionDenied(
                    f'Insufficient points: {balance} / {min_points} required.'
                )
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator


class LoyaltyDependencies:
    """Reusable dependency bundle for loyalty views।"""

    @staticmethod
    def get_customer_or_404(pk):
        from .models.core import Customer
        try:
            return Customer.objects.get(id=pk, is_active=True)
        except Customer.DoesNotExist:
            raise NotFound(f'Customer #{pk} not found.')

    @staticmethod
    def get_active_tier(customer):
        ut = customer.user_tiers.filter(is_current=True).select_related('tier').first()
        return ut.tier if ut else None

    @staticmethod
    def get_points_balance(customer):
        from decimal import Decimal
        from .models.points import LoyaltyPoints
        lp = LoyaltyPoints.objects.filter(customer=customer).first()
        return lp.balance if lp else Decimal('0')
