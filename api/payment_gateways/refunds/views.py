# api/payment_gateways/refunds/views.py
# FILE 61 of 257 — Refund ViewSets and API Views

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from core.views import BaseViewSet

from .models import RefundRequest, RefundPolicy, RefundAuditLog
from .serializers import (
    RefundRequestSerializer,
    RefundRequestListSerializer,
    InitiateRefundSerializer,
    RefundStatusCheckSerializer,
    RefundPolicySerializer,
    RefundAuditLogSerializer,
)
from .RefundFactory import RefundFactory


# ── RefundRequest ViewSet ─────────────────────────────────────────────────────

class RefundRequestViewSet(BaseViewSet):
    """
    Refund requests.
        - Users: can view their own refunds + initiate new ones
        - Admins: full access + approve/reject/cancel actions
    """

    queryset           = RefundRequest.objects.select_related(
        'user', 'original_transaction', 'initiated_by'
    ).all().order_by('-created_at')
    serializer_class   = RefundRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields   = ['status', 'gateway', 'reason']
    search_fields      = ['reference_id', 'gateway_refund_id', 'user__email']
    ordering_fields    = ['created_at', 'amount', 'status']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return RefundRequestListSerializer
        return RefundRequestSerializer

    # ── User: initiate refund ────────────────────────────────────────────────

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def initiate(self, request):
        """
        Initiate a new refund request.

        POST /api/payment/refunds/refunds/initiate/
        {
            "transaction_id": 42,
            "amount": 500.00,
            "reason": "customer_request",
            "notes": "Customer changed their mind"
        }
        """
        serializer = InitiateRefundSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        data        = serializer.validated_data
        transaction = data['transaction']
        amount      = data['amount']
        reason      = data['reason']

        # Verify this transaction belongs to the requesting user
        if not request.user.is_staff and transaction.user != request.user:
            return self.error_response(
                message='You do not have permission to refund this transaction.',
                status_code=status.HTTP_403_FORBIDDEN,
            )

        try:
            processor = RefundFactory.get_processor_for_transaction(transaction)

            # Check if gateway policy requires admin approval
            try:
                from .models import RefundPolicy
                policy = RefundPolicy.objects.get(gateway=transaction.gateway, is_active=True)
                if not policy.auto_approve and not request.user.is_staff:
                    # Create pending refund — admin must approve
                    refund = processor.create_refund_request(
                        transaction, amount, reason,
                        initiated_by=request.user,
                        metadata={'notes': data.get('notes', ''), 'requires_approval': True}
                    )
                    return self.success_response(
                        data=RefundRequestSerializer(refund).data,
                        message='Refund request submitted. Pending admin approval.',
                    )
            except RefundPolicy.DoesNotExist:
                pass

            # Auto-process refund
            result = processor.process_refund(
                transaction, amount, reason,
                initiated_by=request.user,
                metadata={'notes': data.get('notes', '')},
            )

            return self.success_response(
                data=RefundRequestSerializer(result['refund_request']).data,
                message=result.get('message', 'Refund initiated successfully.'),
            )

        except ValueError as e:
            return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.error_response(message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── Admin: approve pending refund ────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: approve a pending refund and send it to the gateway."""
        refund = self.get_object()

        if refund.status != 'pending':
            return self.error_response(
                message=f'Cannot approve refund with status "{refund.status}".',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            processor = RefundFactory.get_processor(refund.gateway)
            result    = processor.process_refund(
                refund.original_transaction,
                refund.amount,
                refund.reason,
                initiated_by=request.user,
            )
            # Replace the old pending refund with the new one from processor
            refund.delete()
            return self.success_response(
                data=RefundRequestSerializer(result['refund_request']).data,
                message=result.get('message', 'Refund approved and processed.'),
            )
        except Exception as e:
            return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

    # ── Admin: reject pending refund ─────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Admin: reject a pending refund request."""
        refund = self.get_object()

        if refund.status != 'pending':
            return self.error_response(
                message=f'Cannot reject refund with status "{refund.status}".',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        refund.status = 'cancelled'
        refund.notes  = request.data.get('reason', 'Rejected by admin')
        refund.save()

        # Audit log
        RefundAuditLog.objects.create(
            refund_request  = refund,
            previous_status = 'pending',
            new_status      = 'cancelled',
            changed_by      = request.user,
            note            = refund.notes,
        )

        return self.success_response(
            data=RefundRequestSerializer(refund).data,
            message='Refund rejected.',
        )

    # ── Cancel refund (gateway) ──────────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def cancel(self, request, pk=None):
        """
        Cancel a refund at the gateway level (only Stripe supports this).
        Only possible while refund status is 'processing' or 'pending'.
        """
        refund = self.get_object()

        if not RefundFactory.supports_refund_cancellation(refund.gateway):
            return self.error_response(
                message=f'Gateway "{refund.gateway}" does not support refund cancellation.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if refund.status not in ('pending', 'processing'):
            return self.error_response(
                message=f'Cannot cancel refund with status "{refund.status}".',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            processor = RefundFactory.get_processor(refund.gateway)
            cancelled = processor.cancel_refund(refund)
            if cancelled:
                return self.success_response(
                    data=RefundRequestSerializer(refund).data,
                    message='Refund cancelled successfully.',
                )
            return self.error_response(message='Refund could not be cancelled.', status_code=400)
        except Exception as e:
            return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

    # ── Check status with gateway ────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def sync_status(self, request, pk=None):
        """
        Sync refund status from the gateway API.
        Available to refund owner or any admin.
        """
        refund = self.get_object()

        if refund.is_final:
            return self.success_response(
                data=RefundRequestSerializer(refund).data,
                message=f'Refund is already in terminal state: {refund.status}.',
            )

        try:
            processor = RefundFactory.get_processor(refund.gateway)
            result    = processor.check_refund_status(refund)
            return self.success_response(
                data=RefundRequestSerializer(refund).data,
                message=f'Status synced: {result.get("gateway_status", "unknown")}',
            )
        except Exception as e:
            return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

    # ── Audit log ────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser])
    def audit_log(self, request, pk=None):
        """Admin: get full audit trail for a refund"""
        refund = self.get_object()
        logs   = RefundAuditLog.objects.filter(refund_request=refund).order_by('created_at')
        return self.success_response(data=RefundAuditLogSerializer(logs, many=True).data)

    # ── Pending list (admin) ─────────────────────────────────────────────────

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending(self, request):
        """Admin: list all pending refunds awaiting approval"""
        qs = self.get_queryset().filter(status='pending')
        return self.success_response(data=RefundRequestListSerializer(qs, many=True).data)

    # ── My refunds (user) ────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_refunds(self, request):
        """User: get all their refund requests"""
        qs   = self.get_queryset().filter(user=request.user)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(RefundRequestListSerializer(page, many=True).data)
        return self.success_response(data=RefundRequestListSerializer(qs, many=True).data)


# ── RefundPolicy ViewSet ──────────────────────────────────────────────────────

class RefundPolicyViewSet(BaseViewSet):
    """Admin: manage per-gateway refund policies"""

    queryset           = RefundPolicy.objects.all().order_by('gateway')
    serializer_class   = RefundPolicySerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['gateway', 'is_active', 'auto_approve']

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        policy            = self.get_object()
        policy.is_active  = not policy.is_active
        policy.save()
        return self.success_response(
            data=RefundPolicySerializer(policy).data,
            message=f'Refund policy {"activated" if policy.is_active else "deactivated"}.',
        )
