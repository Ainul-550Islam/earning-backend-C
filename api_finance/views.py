# api_finance/views.py
"""
DRF ViewSets for the Finance app.

Endpoints:
  GET  /finance/wallet/                         — my wallet
  GET  /finance/transactions/                   — my transaction history
  POST /finance/payout-requests/                — create payout request
  GET  /finance/payout-requests/                — my payout requests
  GET  /finance/admin/wallets/                  — admin: all wallets
  POST /finance/admin/wallets/{id}/lock/        — admin: lock wallet
  POST /finance/admin/wallets/{id}/unlock/      — admin: unlock wallet
  GET  /finance/admin/transactions/             — admin: all transactions
  GET  /finance/admin/payout-requests/          — admin: all payout requests
  POST /finance/admin/payout-requests/{id}/approve/ — admin: approve payout
  POST /finance/admin/payout-requests/{id}/reject/  — admin: reject payout
  POST /finance/admin/reconcile/                — admin: run reconciliation
  GET  /finance/admin/reconciliations/          — admin: reconciliation history
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend

from .models import Wallet, Transaction, PayoutRequest, ReconciliationLog
from .serializers import (
    WalletSerializer, TransactionSerializer, TransactionAdminSerializer,
    PayoutRequestSerializer, PayoutRequestAdminSerializer,
    ReconciliationLogSerializer,
)

logger = logging.getLogger('api_finance')


class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    """User: read own wallet."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WalletSerializer

    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """GET /finance/wallet/me/ — retrieve own wallet, create if missing."""
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        return Response(WalletSerializer(wallet).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Summary including pending payout amount."""
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        pending_payout = PayoutRequest.objects.filter(
            user=request.user,
            status__in=[PayoutRequest.STATUS_PENDING, PayoutRequest.STATUS_APPROVED]
        ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('amount_requested'))
        return Response({
            'wallet': WalletSerializer(wallet).data,
            'pending_payout_usd': pending_payout['total'] or 0,
        })


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """User: browse own transaction history."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'source', 'status']
    ordering = ['-created_at']
    ordering_fields = ['created_at', 'amount_usd']

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


class PayoutRequestViewSet(viewsets.ModelViewSet):
    """User: create and view own payout requests."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'method']
    ordering = ['-created_at']

    def get_serializer_class(self):
        return PayoutRequestSerializer

    def get_queryset(self):
        return PayoutRequest.objects.filter(user=self.request.user)

    def create(self, request):
        """Create a payout request via WithdrawalService in CMS."""
        amount = Decimal(str(request.data.get('amount', 0)))
        method = request.data.get('method', '')
        destination = request.data.get('destination', '')

        if amount <= 0:
            return Response({'error': 'Amount must be positive'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not method or not destination:
            return Response({'error': 'method and destination are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Delegate to CMS WithdrawalService for validation + fraud check
        try:
            from api.cms.services_new.WithdrawalService import WithdrawalService
            result = WithdrawalService.create_withdrawal_request(
                user=request.user,
                amount=amount,
                method=method,
                destination=destination,
            )
            if not result.get('success', False):
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        # Create the PayoutRequest record
        fee = amount * Decimal('0.02')
        pr = PayoutRequest.objects.create(
            user=request.user,
            amount_requested=amount,
            fee=fee,
            method=method,
            destination=destination,
        )
        return Response(PayoutRequestSerializer(pr).data,
                        status=status.HTTP_201_CREATED)


class AdminWalletViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin: view all wallets."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    serializer_class = WalletSerializer
    queryset = Wallet.objects.select_related('user').order_by('-balance_usd')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['user__username', 'user__email']
    filterset_fields = ['is_locked']

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        wallet = self.get_object()
        wallet.is_locked = True
        wallet.locked_reason = request.data.get('reason', 'Admin lock')
        wallet.save(update_fields=['is_locked', 'locked_reason'])
        logger.info(f"Wallet {wallet.id} locked by {request.user.username}")
        return Response({'status': 'locked', 'wallet_id': str(wallet.id)})

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        wallet = self.get_object()
        wallet.is_locked = False
        wallet.locked_reason = ''
        wallet.save(update_fields=['is_locked', 'locked_reason'])
        logger.info(f"Wallet {wallet.id} unlocked by {request.user.username}")
        return Response({'status': 'unlocked', 'wallet_id': str(wallet.id)})

    @action(detail=True, methods=['post'])
    def adjust_balance(self, request, pk=None):
        """Admin credit/debit adjustment."""
        wallet = self.get_object()
        amount = Decimal(str(request.data.get('amount', 0)))
        tx_type = request.data.get('type', 'credit')
        note = request.data.get('note', 'Admin adjustment')
        if amount == 0:
            return Response({'error': 'Amount cannot be zero'},
                            status=status.HTTP_400_BAD_REQUEST)
        with db_transaction.atomic():
            balance_before = wallet.balance_usd
            if tx_type == 'credit':
                wallet.balance_usd += amount
                wallet.total_earned_usd += amount
            else:
                if wallet.balance_usd < amount:
                    return Response({'error': 'Insufficient balance'},
                                    status=status.HTTP_400_BAD_REQUEST)
                wallet.balance_usd -= amount
            wallet.save(update_fields=['balance_usd', 'total_earned_usd'])
            Transaction.objects.create(
                wallet=wallet,
                user=wallet.user,
                amount=amount,
                amount_usd=amount,
                transaction_type=tx_type,
                source=Transaction.SOURCE_ADMIN,
                status=Transaction.STATUS_COMPLETED,
                balance_before=balance_before,
                balance_after=wallet.balance_usd,
                description=note,
                completed_at=timezone.now(),
            )
        return Response({'status': 'adjusted', 'new_balance': str(wallet.balance_usd)})


class AdminTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin: view all transactions."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    serializer_class = TransactionAdminSerializer
    queryset = Transaction.objects.select_related('user').order_by('-created_at')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'source', 'status']
    search_fields = ['user__username', 'reference_id']
    ordering_fields = ['created_at', 'amount_usd']


class AdminPayoutRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin: manage payout requests."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    serializer_class = PayoutRequestAdminSerializer
    queryset = PayoutRequest.objects.select_related('user').order_by('-created_at')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'method']
    search_fields = ['user__username', 'destination', 'external_ref']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        pr = self.get_object()
        if pr.status != PayoutRequest.STATUS_PENDING:
            return Response({'error': 'Only pending requests can be approved'},
                            status=status.HTTP_400_BAD_REQUEST)
        pr.status = PayoutRequest.STATUS_APPROVED
        pr.processed_at = timezone.now()
        pr.admin_notes = request.data.get('notes', '')
        pr.save(update_fields=['status', 'processed_at', 'admin_notes'])
        logger.info(f"PayoutRequest {pr.id} approved by {request.user.username}")
        return Response({'status': 'approved', 'payout_id': str(pr.id)})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        pr = self.get_object()
        if pr.status not in [PayoutRequest.STATUS_PENDING, PayoutRequest.STATUS_APPROVED]:
            return Response({'error': 'Cannot reject a processed payout'},
                            status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get('reason', '')
        if not reason:
            return Response({'error': 'reason is required for rejection'},
                            status=status.HTTP_400_BAD_REQUEST)
        with db_transaction.atomic():
            pr.status = PayoutRequest.STATUS_REJECTED
            pr.rejection_reason = reason
            pr.processed_at = timezone.now()
            pr.save(update_fields=['status', 'rejection_reason', 'processed_at'])
            # Refund the held amount back to wallet
            wallet = Wallet.objects.filter(user=pr.user).first()
            if wallet:
                balance_before = wallet.balance_usd
                wallet.balance_usd += pr.amount_requested
                wallet.save(update_fields=['balance_usd'])
                Transaction.objects.create(
                    wallet=wallet,
                    user=pr.user,
                    amount=pr.amount_requested,
                    amount_usd=pr.amount_requested,
                    transaction_type=Transaction.TYPE_CREDIT,
                    source=Transaction.SOURCE_REFUND,
                    status=Transaction.STATUS_COMPLETED,
                    balance_before=balance_before,
                    balance_after=wallet.balance_usd,
                    description=f'Payout rejected: {reason}',
                    reference_id=str(pr.id),
                    completed_at=timezone.now(),
                )
        logger.info(f"PayoutRequest {pr.id} rejected by {request.user.username}: {reason}")
        return Response({'status': 'rejected', 'payout_id': str(pr.id)})

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark an approved payout as actually paid."""
        pr = self.get_object()
        if pr.status != PayoutRequest.STATUS_APPROVED:
            return Response({'error': 'Only approved payouts can be marked paid'},
                            status=status.HTTP_400_BAD_REQUEST)
        pr.status = PayoutRequest.STATUS_PAID
        pr.external_ref = request.data.get('external_ref', '')
        pr.processed_at = timezone.now()
        pr.save(update_fields=['status', 'external_ref', 'processed_at'])
        return Response({'status': 'paid', 'payout_id': str(pr.id)})


class ReconciliationViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin: run and view financial reconciliations."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ReconciliationLogSerializer
    queryset = ReconciliationLog.objects.order_by('-date')

    @action(detail=False, methods=['post'])
    def run(self, request):
        """Run a reconciliation for a given date (defaults to today)."""
        from django.db.models import Sum
        date_str = request.data.get('date', str(timezone.now().date()))
        from datetime import date as dt
        try:
            rec_date = dt.fromisoformat(date_str)
        except ValueError:
            return Response({'error': 'Invalid date format (YYYY-MM-DD)'},
                            status=status.HTTP_400_BAD_REQUEST)

        qs = Transaction.objects.filter(
            created_at__date=rec_date,
            status=Transaction.STATUS_COMPLETED,
        )
        credits  = qs.filter(transaction_type=Transaction.TYPE_CREDIT).aggregate(
            t=Sum('amount_usd'))['t'] or Decimal('0')
        debits   = qs.filter(transaction_type=Transaction.TYPE_DEBIT).aggregate(
            t=Sum('amount_usd'))['t'] or Decimal('0')
        fees     = qs.aggregate(t=Sum('fee_usd'))['t'] or Decimal('0')
        tx_count = qs.count()

        payout_qs = PayoutRequest.objects.filter(
            processed_at__date=rec_date,
            status=PayoutRequest.STATUS_PAID,
        )
        total_payouts = payout_qs.aggregate(t=Sum('amount_net'))['t'] or Decimal('0')
        payout_count  = payout_qs.count()

        discrepancy = credits - debits - total_payouts
        is_balanced = abs(discrepancy) < Decimal('0.01')

        log, _ = ReconciliationLog.objects.update_or_create(
            date=rec_date,
            defaults={
                'total_credited': credits,
                'total_debited': debits,
                'total_fees': fees,
                'total_payouts': total_payouts,
                'transaction_count': tx_count,
                'payout_count': payout_count,
                'discrepancy_usd': discrepancy,
                'is_balanced': is_balanced,
                'run_by': request.user,
            },
        )
        return Response(ReconciliationLogSerializer(log).data)
