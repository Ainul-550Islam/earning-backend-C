# api/djoyalty/decorators.py
"""
Custom decorators for Djoyalty views and services।
"""
import logging
import time
from functools import wraps
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('djoyalty.decorators')


def require_tenant(func):
    """
    View decorator: tenant না থাকলে 400 return করো।
    """
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return Response(
                {'error': 'tenant_required', 'message': 'X-Tenant-ID header is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return func(self, request, *args, **kwargs)
    return wrapper


def require_customer(func):
    """
    View decorator: customer_id query param বা request body থেকে customer load করো।
    self.customer set করে।
    """
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from .models.core import Customer
        customer_id = (
            request.data.get('customer_id')
            or request.query_params.get('customer_id')
        )
        if not customer_id:
            return Response(
                {'error': 'customer_required', 'message': 'customer_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            self.customer = get_object_or_404(Customer, pk=customer_id, is_active=True)
        except Exception:
            return Response(
                {'error': 'customer_not_found', 'message': f'Customer {customer_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return func(self, request, *args, **kwargs)
    return wrapper


def fraud_check(func):
    """
    Service decorator: fraud check করে proceed করো।
    LoyaltyFraudService.check_rapid_transactions() call করে।
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Find customer in args (first positional arg after self/cls)
        customer = None
        for arg in args:
            if hasattr(arg, 'loyalty_points'):
                customer = arg
                break
        if customer:
            try:
                from .services.advanced.LoyaltyFraudService import LoyaltyFraudService
                if LoyaltyFraudService.check_rapid_transactions(customer):
                    from .exceptions import FraudDetectedError
                    raise FraudDetectedError()
            except Exception as e:
                if 'FraudDetectedError' in type(e).__name__:
                    raise
                logger.warning('Fraud check error (non-blocking): %s', e)
        return func(*args, **kwargs)
    return wrapper


def log_points_operation(operation_name: str):
    """
    Service decorator: points operation log করো।
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                duration = (time.monotonic() - start) * 1000
                logger.info(
                    'Points operation [%s] completed in %.1fms',
                    operation_name, duration,
                )
                return result
            except Exception as e:
                duration = (time.monotonic() - start) * 1000
                logger.error(
                    'Points operation [%s] failed in %.1fms: %s',
                    operation_name, duration, e,
                )
                raise
        return wrapper
    return decorator


def cache_response(timeout: int = 300, key_prefix: str = 'view'):
    """
    View decorator: response cache করো।
    GET requests only।
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if request.method != 'GET':
                return func(self, request, *args, **kwargs)
            from django.core.cache import cache
            cache_key = f'djoyalty:{key_prefix}:{request.path}:{request.user.id if request.user.is_authenticated else "anon"}'
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)
            response = func(self, request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, response.data, timeout=timeout)
            return response
        return wrapper
    return decorator


def validate_points_amount(min_points=None, max_points=None):
    """
    View action decorator: points amount validate করো।
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            from decimal import Decimal, InvalidOperation
            points_raw = request.data.get('points')
            if points_raw is None:
                return Response(
                    {'error': 'points_required', 'message': 'points field is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                points = Decimal(str(points_raw))
            except (InvalidOperation, TypeError, ValueError):
                return Response(
                    {'error': 'invalid_points', 'message': 'points must be a valid number.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if points <= 0:
                return Response(
                    {'error': 'invalid_points', 'message': 'points must be positive.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if min_points and points < Decimal(str(min_points)):
                return Response(
                    {'error': 'points_too_low', 'message': f'Minimum {min_points} points required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if max_points and points > Decimal(str(max_points)):
                return Response(
                    {'error': 'points_too_high', 'message': f'Maximum {max_points} points allowed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            request._validated_points = points
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator
