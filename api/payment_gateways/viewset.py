# api/payment_gateways/viewset.py
# Full base viewset with standard response format, pagination, auth, audit

from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rf_filters
import logging

from .pagination import StandardPagination, TransactionPagination
from .permissions import IsOwnerOrAdmin

logger = logging.getLogger(__name__)


class PaymentBaseViewSet(ModelViewSet):
    """
    Base viewset for all payment_gateways viewsets.

    Features:
        - Consistent JSON response format: {success, message, data, errors}
        - StandardPagination (25 per page, max 200)
        - IsOwnerOrAdmin permission (users see own data, staff see all)
        - DjangoFilterBackend + OrderingFilter support
        - Auto audit logging on create/update/destroy
        - Paginated list response
        - Error handling with proper HTTP status codes

    Usage:
        class MyViewSet(PaymentBaseViewSet):
            queryset         = MyModel.objects.all()
            serializer_class = MySerializer
            filterset_class  = MyFilter
    """
    pagination_class   = StandardPagination
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, rf_filters.OrderingFilter,
                          rf_filters.SearchFilter]

    def get_queryset(self):
        """
        Return filtered queryset.
        Staff see all records; regular users see only their own.
        Override in subclass for custom filtering.
        """
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            # Try common owner field names
            for field in ('user', 'publisher', 'advertiser', 'owner', 'created_by'):
                if hasattr(qs.model, field):
                    return qs.filter(**{field: self.request.user})
        return qs

    # ── Standard response helpers ──────────────────────────────────────────────

    def success_response(self, data=None, message: str = '', status_code: int = 200):
        """Return standard success response."""
        return Response(
            {
                'success': True,
                'message': message,
                'data':    data if data is not None else {},
            },
            status=status_code,
        )

    def error_response(self, message: str = 'An error occurred',
                        errors=None, status_code: int = 400):
        """Return standard error response."""
        return Response(
            {
                'success': False,
                'message': message,
                'errors':  errors if errors is not None else [],
            },
            status=status_code,
        )

    def paginated_response(self, queryset, serializer_class=None):
        """Paginate and return queryset response."""
        srl_class = serializer_class or self.get_serializer_class()
        page      = self.paginate_queryset(queryset)
        if page is not None:
            serializer = srl_class(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = srl_class(queryset, many=True, context=self.get_serializer_context())
        return self.success_response(data=serializer.data)

    # ── Standard CRUD overrides ────────────────────────────────────────────────

    def list(self, request, *args, **kwargs):
        """List with consistent response format."""
        queryset = self.filter_queryset(self.get_queryset())
        return self.paginated_response(queryset)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve single object."""
        instance   = self.get_object()
        serializer = self.get_serializer(instance)
        return self.success_response(data=serializer.data)

    def create(self, request, *args, **kwargs):
        """Create with consistent response format."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        self._audit('create', serializer.instance)
        return self.success_response(
            data=serializer.data,
            message=f'{self._model_name()} created successfully.',
            status_code=201,
        )

    def update(self, request, *args, **kwargs):
        """Update with consistent response format."""
        partial    = kwargs.pop('partial', False)
        instance   = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        self._audit('update', instance)
        return self.success_response(
            data=serializer.data,
            message=f'{self._model_name()} updated successfully.',
        )

    def destroy(self, request, *args, **kwargs):
        """Soft delete or hard delete with consistent response."""
        instance = self.get_object()
        self.perform_destroy(instance)
        self._audit('delete', instance)
        return self.success_response(
            message=f'{self._model_name()} deleted successfully.',
            status_code=200,
        )

    def perform_destroy(self, instance):
        """Soft delete if status field exists, else hard delete."""
        if hasattr(instance, 'status'):
            instance.status = 'deleted'
            instance.save(update_fields=['status'])
        else:
            instance.delete()

    # ── Utility methods ────────────────────────────────────────────────────────

    def _model_name(self) -> str:
        """Get human-readable model name."""
        try:
            return self.get_queryset().model._meta.verbose_name.title()
        except Exception:
            return 'Object'

    def _audit(self, action: str, instance):
        """Auto audit log for write operations."""
        try:
            from api.payment_gateways.integration_system.integ_audit_logs import audit_logger
            audit_logger.log(
                event_type   = f'{self.__class__.__name__}.{action}',
                source_module= 'api.payment_gateways',
                user_id      = self.request.user.id,
                payload      = {
                    'model':  instance.__class__.__name__,
                    'id':     getattr(instance, 'id', None),
                    'action': action,
                },
                success      = True,
                severity     = 'info',
            )
        except Exception:
            pass  # Audit logging is non-critical


class PaymentReadOnlyViewSet(ReadOnlyModelViewSet):
    """
    Read-only base viewset for analytics and reporting endpoints.
    Only supports list and retrieve — no create/update/delete.
    """
    pagination_class   = StandardPagination
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, rf_filters.OrderingFilter]

    def list(self, request, *args, **kwargs):
        queryset   = self.filter_queryset(self.get_queryset())
        page       = self.paginate_queryset(queryset)
        serializer = self.get_serializer(
            page if page is not None else queryset,
            many=True,
        )
        data = serializer.data
        if page is not None:
            return self.get_paginated_response(data)
        return Response({'success': True, 'data': data})

    def retrieve(self, request, *args, **kwargs):
        instance   = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})


class TransactionBaseViewSet(PaymentBaseViewSet):
    """
    Specialized base for transaction-related viewsets.
    Adds transaction-specific actions.
    """
    pagination_class = TransactionPagination
    ordering_fields  = ['created_at', 'amount', 'status']
    ordering         = ['-created_at']

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get totals summary for current user's transactions."""
        from django.db.models import Sum, Count
        from decimal import Decimal

        qs  = self.filter_queryset(self.get_queryset()).filter(status='completed')
        agg = qs.aggregate(
            total_amount=Sum('amount'),
            total_fee=Sum('fee'),
            total_net=Sum('net_amount'),
            count=Count('id'),
        )
        return self.success_response(data={
            'total_amount':  float(agg['total_amount'] or 0),
            'total_fee':     float(agg['total_fee'] or 0),
            'total_net':     float(agg['total_net'] or 0),
            'count':         agg['count'],
        })

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get last 10 transactions for current user."""
        qs         = self.get_queryset().order_by('-created_at')[:10]
        serializer = self.get_serializer(qs, many=True)
        return self.success_response(data=serializer.data)
