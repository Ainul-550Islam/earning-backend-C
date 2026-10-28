# api/admin_panel/viewsets/WalletWithdrawalAdminViewSet.py
"""
Full Wallet & Withdrawal Admin Control.
PostgreSQL-optimized. Controls withdrawals, wallet balances, earnings,
manual adjustments, gateway reconciliation, batch payouts.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Sum, Q, Avg, F
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class WalletWithdrawalAdminViewSet(viewsets.ViewSet):
    """Complete Wallet & Withdrawal management from Admin Panel."""
    permission_classes = [IsAdminUser]

    # ─── OVERVIEW ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Full wallet system overview with PostgreSQL aggregations."""
        cache_key = 'admin:wallet:overview'
        cached = cache.get(cache_key)
        if cached:
            return Response({'success': True, 'data': cached})
        try:
            from api.wallet.models.core import Wallet, WalletTransaction
            from api.wallet.models.core import WithdrawalRequest
            today = timezone.now().date()
            week_ago = timezone.now() - timedelta(days=7)

            wallet_stats = Wallet.objects.aggregate(
                total_wallets=Count('id'),
                total_balance=Sum('balance'),
                total_bonus=Sum('bonus_balance'),
                total_locked=Sum('locked_balance'),
                active_wallets=Count('id', filter=Q(is_active=True)),
            )
            withdrawal_stats = WithdrawalRequest.objects.aggregate(
                pending_count=Count('id', filter=Q(status='pending')),
                pending_amount=Sum('amount', filter=Q(status='pending')),
                approved_today=Count('id', filter=Q(status='approved', created_at__date=today)),
                approved_today_amount=Sum('amount', filter=Q(status='approved', created_at__date=today)),
                rejected_count=Count('id', filter=Q(status='rejected')),
                processing_count=Count('id', filter=Q(status='processing')),
            )
            txn_week = WalletTransaction.objects.filter(created_at__gte=week_ago).aggregate(
                total_txns=Count('id'),
                total_volume=Sum('amount'),
                earning_volume=Sum('amount', filter=Q(transaction_type='earning')),
                withdrawal_volume=Sum('amount', filter=Q(transaction_type='withdrawal')),
            )
            data = {
                'wallet': {k: float(v) if v else 0 for k, v in wallet_stats.items()},
                'withdrawal': {k: float(v) if v else 0 for k, v in withdrawal_stats.items()},
                'weekly_transactions': {k: float(v) if v else 0 for k, v in txn_week.items()},
            }
            cache.set(cache_key, data, 60)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ─── PENDING WITHDRAWALS ───────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def pending_withdrawals(self, request):
        """List all pending withdrawal requests — sorted by amount desc."""
        try:
            from api.wallet.models.core import WithdrawalRequest
            page = int(request.query_params.get('page', 1))
            per_page = int(request.query_params.get('per_page', 50))
            min_amount = request.query_params.get('min_amount')
            gateway = request.query_params.get('gateway')

            qs = WithdrawalRequest.objects.filter(status='pending').select_related('user')
            if min_amount:
                qs = qs.filter(amount__gte=float(min_amount))
            if gateway:
                qs = qs.filter(gateway=gateway)

            total = qs.count()
            items = list(qs.order_by('-amount').values(
                'id', 'user_id', 'user__username', 'user__email',
                'amount', 'gateway', 'account_number', 'account_name',
                'status', 'created_at', 'ip_address', 'notes',
            )[(page-1)*per_page:page*per_page])
            return Response({'success': True, 'total': total, 'page': page, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_withdrawal(self, request):
        """Approve a single withdrawal request."""
        try:
            from api.wallet.models.core import WithdrawalRequest
            wr_id = request.data.get('withdrawal_id')
            note = request.data.get('note', '')
            wr = WithdrawalRequest.objects.get(pk=wr_id, status='pending')
            wr.status = 'approved'
            wr.reviewed_by_id = request.user.pk
            wr.reviewed_at = timezone.now()
            wr.admin_note = note
            wr.save(update_fields=['status', 'reviewed_by_id', 'reviewed_at', 'admin_note'])
            cache.delete('admin:wallet:overview')
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='approve_withdrawal',
                                  model_name='WithdrawalRequest', object_id=str(wr_id),
                                  changes={'amount': float(wr.amount), 'gateway': wr.gateway})
            except Exception: pass
            return Response({'success': True, 'withdrawal_id': wr_id, 'status': 'approved'})
        except WithdrawalRequest.DoesNotExist:
            return Response({'error': 'Withdrawal not found or not pending'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_withdrawal(self, request):
        """Reject a withdrawal with reason."""
        try:
            from api.wallet.models.core import WithdrawalRequest
            wr_id = request.data.get('withdrawal_id')
            reason = request.data.get('reason', 'Rejected by admin')
            wr = WithdrawalRequest.objects.get(pk=wr_id, status='pending')
            wr.status = 'rejected'
            wr.rejection_reason = reason
            wr.reviewed_by_id = request.user.pk
            wr.reviewed_at = timezone.now()
            wr.save(update_fields=['status', 'rejection_reason', 'reviewed_by_id', 'reviewed_at'])
            # Refund balance
            try:
                from api.wallet.models.core import Wallet
                Wallet.objects.filter(user_id=wr.user_id).update(balance=F('balance') + wr.amount)
            except Exception: pass
            cache.delete('admin:wallet:overview')
            return Response({'success': True, 'withdrawal_id': wr_id, 'status': 'rejected'})
        except WithdrawalRequest.DoesNotExist:
            return Response({'error': 'Withdrawal not found or not pending'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """Bulk approve multiple withdrawals at once."""
        try:
            from api.wallet.models.core import WithdrawalRequest
            ids = request.data.get('withdrawal_ids', [])
            if not ids:
                return Response({'error': 'withdrawal_ids required'}, status=400)
            updated = WithdrawalRequest.objects.filter(
                pk__in=ids, status='pending'
            ).update(
                status='approved',
                reviewed_by_id=request.user.pk,
                reviewed_at=timezone.now(),
            )
            cache.delete('admin:wallet:overview')
            return Response({'success': True, 'approved_count': updated, 'total_requested': len(ids)})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ─── MANUAL BALANCE ADJUSTMENT ────────────────────────────────────────────

    @action(detail=False, methods=['post'])
    def adjust_balance(self, request):
        """Manually adjust a user's wallet balance (credit/debit)."""
        try:
            from api.wallet.models.core import Wallet, WalletTransaction
            user_id = request.data.get('user_id')
            amount = float(request.data.get('amount', 0))
            tx_type = request.data.get('type', 'credit')  # credit | debit
            reason = request.data.get('reason', 'Admin adjustment')
            if not user_id or amount <= 0:
                return Response({'error': 'user_id and amount required'}, status=400)

            wallet = Wallet.objects.get(user_id=user_id)
            if tx_type == 'credit':
                wallet.balance = F('balance') + amount
            elif tx_type == 'debit':
                if float(wallet.balance) < amount:
                    return Response({'error': 'Insufficient balance'}, status=400)
                wallet.balance = F('balance') - amount
            wallet.save(update_fields=['balance'])
            wallet.refresh_from_db()

            # Create transaction record
            try:
                WalletTransaction.objects.create(
                    wallet=wallet, user_id=user_id,
                    amount=amount,
                    transaction_type='admin_credit' if tx_type == 'credit' else 'admin_debit',
                    description=reason, status='completed',
                )
            except Exception: pass

            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='adjust_balance',
                                  model_name='Wallet', object_id=str(wallet.pk),
                                  changes={'type': tx_type, 'amount': amount, 'reason': reason})
            except Exception: pass
            cache.delete('admin:wallet:overview')
            return Response({'success': True, 'user_id': user_id, 'type': tx_type,
                             'amount': amount, 'new_balance': float(wallet.balance)})
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ─── WALLET SEARCH ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def user_wallet(self, request):
        """Get full wallet details for a specific user."""
        try:
            from api.wallet.models.core import Wallet, WalletTransaction
            from api.wallet.models.core import WithdrawalRequest
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({'error': 'user_id required'}, status=400)
            wallet = Wallet.objects.filter(user_id=user_id).values(
                'id', 'balance', 'bonus_balance', 'locked_balance',
                'total_earned', 'total_withdrawn', 'is_active', 'is_frozen',
                'freeze_reason', 'created_at',
            ).first()
            if not wallet:
                return Response({'error': 'Wallet not found'}, status=404)
            recent_txns = list(WalletTransaction.objects.filter(
                user_id=user_id
            ).values(
                'id', 'amount', 'transaction_type', 'description', 'status', 'created_at'
            ).order_by('-created_at')[:20])
            withdrawals = list(WithdrawalRequest.objects.filter(
                user_id=user_id
            ).values(
                'id', 'amount', 'gateway', 'status', 'created_at', 'reviewed_at'
            ).order_by('-created_at')[:10])
            return Response({'success': True, 'wallet': wallet,
                             'recent_transactions': recent_txns, 'withdrawals': withdrawals})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def freeze_wallet(self, request):
        """Freeze/unfreeze a user wallet."""
        try:
            from api.wallet.models.core import Wallet
            user_id = request.data.get('user_id')
            freeze = bool(request.data.get('freeze', True))
            reason = request.data.get('reason', 'Frozen by admin')
            updated = Wallet.objects.filter(user_id=user_id).update(
                is_frozen=freeze,
                freeze_reason=reason if freeze else '',
            )
            if not updated:
                return Response({'error': 'Wallet not found'}, status=404)
            cache.delete(f'wallet:user:{user_id}')
            return Response({'success': True, 'user_id': user_id, 'frozen': freeze})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ─── STATS & REPORTS ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def withdrawal_stats(self, request):
        """Daily withdrawal stats for chart — last 30 days."""
        try:
            from api.wallet.models.core import WithdrawalRequest
            from django.db.models.functions import TruncDate
            stats = (
                WithdrawalRequest.objects
                .filter(created_at__gte=timezone.now() - timedelta(days=30))
                .annotate(date=TruncDate('created_at'))
                .values('date', 'status')
                .annotate(count=Count('id'), total=Sum('amount'))
                .order_by('date')
            )
            return Response({'success': True, 'data': list(stats)})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def gateway_breakdown(self, request):
        """Breakdown of withdrawals by gateway."""
        try:
            from api.wallet.models.core import WithdrawalRequest
            data = list(
                WithdrawalRequest.objects
                .values('gateway', 'status')
                .annotate(count=Count('id'), total_amount=Sum('amount'))
                .order_by('gateway', 'status')
            )
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})