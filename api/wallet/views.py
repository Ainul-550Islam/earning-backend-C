from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.views import APIView
from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import render
from django.http import JsonResponse
from decimal import Decimal
import logging

from .models import (
    Wallet, 
    WalletTransaction, 
    Withdrawal, 
    UserPaymentMethod,
    WalletWebhookLog
)
from .serializers import (
    WalletSerializer,
    WalletTransactionSerializer,
    WithdrawalSerializer,
    UserPaymentMethodSerializer,
    WalletWebhookLogSerializer
)

logger = logging.getLogger(__name__)


# ==========================================
# 1. Wallet ViewSet
# ==========================================
class WalletViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Wallet CRUD operations
    """
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Wallet.objects.none()
        return Wallet.objects.filter(user=self.request.user, user__tenant=tenant)
    
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Lock a wallet"""
        try:
            wallet = self.get_object()
            reason = request.data.get('reason', 'Locked by admin')
            wallet.lock(reason)
            return Response({
                'success': True,
                'message': 'Wallet locked successfully'
            })
        except Exception as e:
            logger.error(f"Error locking wallet {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """Unlock a wallet"""
        try:
            wallet = self.get_object()
            wallet.unlock()
            return Response({
                'success': True,
                'message': 'Wallet unlocked successfully'
            })
        except Exception as e:
            logger.error(f"Error unlocking wallet {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def freeze_balance(self, request, pk=None):
        """Freeze specific amount"""
        try:
            wallet = self.get_object()
            amount = Decimal(str(request.data.get('amount', 0)))
            reason = request.data.get('reason', 'Frozen by admin')
            
            wallet.freeze(amount, reason)
            
            return Response({
                'success': True,
                'message': f'Frozen {amount} successfully',
                'data': WalletSerializer(wallet).data
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error freezing balance for wallet {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def unfreeze_balance(self, request, pk=None):
        """Unfreeze specific amount"""
        try:
            wallet = self.get_object()
            amount = Decimal(str(request.data.get('amount', 0)))
            reason = request.data.get('reason', 'Unfrozen by admin')
            
            wallet.unfreeze(amount, reason)
            
            return Response({
                'success': True,
                'message': f'Unfrozen {amount} successfully',
                'data': WalletSerializer(wallet).data
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error unfreezing balance for wallet {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 2. WalletTransaction ViewSet
# ==========================================
class WalletTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for WalletTransaction CRUD operations
    """
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return WalletTransaction.objects.all()
        return WalletTransaction.objects.select_related('wallet','wallet__user','created_by','approved_by').filter(wallet__user=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve a pending transaction"""
        try:
            transaction_obj = self.get_object()
            transaction_obj.approve(approved_by=request.user)
            
            return Response({
                'success': True,
                'message': 'Transaction approved successfully',
                'data': WalletTransactionSerializer(transaction_obj).data
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error approving transaction {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Reject a pending transaction"""
        try:
            transaction_obj = self.get_object()
            reason = request.data.get('reason', 'Rejected by admin')
            transaction_obj.reject(reason)
            
            return Response({
                'success': True,
                'message': 'Transaction rejected successfully',
                'data': WalletTransactionSerializer(transaction_obj).data
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error rejecting transaction {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reverse(self, request, pk=None):
        """Reverse a completed transaction"""
        try:
            transaction_obj = self.get_object()
            reason = request.data.get('reason', 'Reversed by admin')
            reversal = transaction_obj.reverse(reason=reason, reversed_by=request.user)
            
            return Response({
                'success': True,
                'message': 'Transaction reversed successfully',
                'data': {
                    'original': WalletTransactionSerializer(transaction_obj).data,
                    'reversal': WalletTransactionSerializer(reversal).data
                }
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error reversing transaction {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 3. UserPaymentMethod ViewSet
# ==========================================
class UserPaymentMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UserPaymentMethod CRUD operations
    """
    serializer_class = UserPaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserPaymentMethod.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set as primary payment method"""
        try:
            payment_method = self.get_object()
            
            # Unset other primary methods
            UserPaymentMethod.objects.filter(
                user=request.user,
                is_primary=True
            ).update(is_primary=False)
            
            # Set this as primary
            payment_method.is_primary = True
            payment_method.save()
            
            return Response({
                'success': True,
                'message': 'Payment method set as primary',
                'data': UserPaymentMethodSerializer(payment_method).data
            })
        except Exception as e:
            logger.error(f"Error setting primary payment method {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """Verify payment method (admin only)"""
        try:
            payment_method = self.get_object()
            payment_method.is_verified = True
            payment_method.verified_at = timezone.now()
            payment_method.save()
            
            return Response({
                'success': True,
                'message': 'Payment method verified',
                'data': UserPaymentMethodSerializer(payment_method).data
            })
        except Exception as e:
            logger.error(f"Error verifying payment method {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 4. Withdrawal ViewSet
# ==========================================
class WithdrawalViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Withdrawal CRUD operations
    """
    serializer_class = WithdrawalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Withdrawal.objects.all()
        return Withdrawal.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def process(self, request, pk=None):
        """Process withdrawal (admin only)"""
        try:
            with transaction.atomic():
                withdrawal = self.get_object()
                
                if withdrawal.status != 'pending':
                    return Response({
                        'success': False,
                        'error': f'Cannot process withdrawal with status: {withdrawal.status}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Update withdrawal status
                withdrawal.status = 'processing'
                withdrawal.processed_by = request.user
                withdrawal.processed_at = timezone.now()
                withdrawal.save()
                
                # Update wallet transaction
                wallet_txn = withdrawal.WalletTransaction
                wallet_txn.approve(approved_by=request.user)
                
                return Response({
                    'success': True,
                    'message': 'Withdrawal processing started',
                    'data': WithdrawalSerializer(withdrawal).data
                })
        except Exception as e:
            logger.error(f"Error processing withdrawal {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def complete(self, request, pk=None):
        """Complete withdrawal (admin only)"""
        try:
            with transaction.atomic():
                withdrawal = self.get_object()
                
                if withdrawal.status != 'processing':
                    return Response({
                        'success': False,
                        'error': f'Cannot complete withdrawal with status: {withdrawal.status}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Update withdrawal
                withdrawal.status = 'completed'
                withdrawal.gateway_reference = request.data.get('gateway_reference', '')
                withdrawal.gateway_response = request.data.get('gateway_response', {})
                withdrawal.save()
                
                # Update wallet
                wallet = withdrawal.wallet
                wallet.pending_balance = F('pending_balance') - withdrawal.amount
                wallet.total_withdrawn = F('total_withdrawn') + withdrawal.amount
                wallet.save()
                
                return Response({
                    'success': True,
                    'message': 'Withdrawal completed successfully',
                    'data': WithdrawalSerializer(withdrawal).data
                })
        except Exception as e:
            logger.error(f"Error completing withdrawal {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Reject withdrawal (admin only)"""
        try:
            with transaction.atomic():
                withdrawal = self.get_object()
                
                if withdrawal.status not in ['pending', 'processing']:
                    return Response({
                        'success': False,
                        'error': f'Cannot reject withdrawal with status: {withdrawal.status}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Update withdrawal
                withdrawal.status = 'rejected'
                withdrawal.rejection_reason = request.data.get('reason', 'Rejected by admin')
                withdrawal.rejected_at = timezone.now()
                withdrawal.processed_by = request.user
                withdrawal.processed_at = timezone.now()
                withdrawal.save()
                
                # Refund to wallet
                wallet = withdrawal.wallet
                wallet.current_balance = F('current_balance') + withdrawal.amount
                wallet.pending_balance = F('pending_balance') - withdrawal.amount
                wallet.save()
                
                # Update transaction
                wallet_txn = withdrawal.WalletTransaction
                wallet_txn.reject(withdrawal.rejection_reason)
                
                return Response({
                    'success': True,
                    'message': 'Withdrawal rejected and refunded',
                    'data': WithdrawalSerializer(withdrawal).data
                })
        except Exception as e:
            logger.error(f"Error rejecting withdrawal {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 5. WalletWebhookLog ViewSet
# ==========================================
class WalletWebhookLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for WalletWebhookLog CRUD operations
    """
    serializer_class = WalletWebhookLogSerializer
    permission_classes = [IsAdminUser]
    queryset = WalletWebhookLog.objects.all()
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def handle_webhook(self, request):
        """Handle incoming webhook"""
        try:
            # Determine webhook type from URL or headers
            webhook_type = request.data.get('gateway', 'unknown')
            event_type = request.data.get('event_type', 'unknown')
            
            # Create webhook log
            webhook_log = WalletWebhookLog.objects.create(
                webhook_type=webhook_type,
                event_type=event_type,
                payload=request.data,
                headers=dict(request.headers),
                is_processed=False
            )
            
            # Process webhook (implement your logic here)
            # Example: Update withdrawal status based on payment gateway response
            
            webhook_log.is_processed = True
            webhook_log.processed_at = timezone.now()
            webhook_log.save()
            
            return Response({
                'success': True,
                'message': 'Webhook received and processed'
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            
            if 'webhook_log' in locals():
                webhook_log.processing_error = str(e)
                webhook_log.save()
            
            return Response({
                'success': False,
                'error': 'Webhook processing failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 7. Bulk Wallet Operations API
# ==========================================
class BulkWalletOperationAPIView(APIView):
    """
    POST /api/wallet/bulk-operations/
    Admin-only bulk operations
    """
    permission_classes = [IsAdminUser]
    
    @transaction.atomic
    def post(self, request):
        try:
            operation = request.data.get('operation')
            user_ids = request.data.get('user_ids', [])
            
            if not operation or not user_ids:
                return Response({
                    'success': False,
                    'error': 'Operation and user_ids are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            wallets = Wallet.objects.filter(user_id__in=user_ids)
            
            if operation == 'lock':
                reason = request.data.get('reason', 'Bulk lock by admin')
                count = 0
                for wallet in wallets:
                    wallet.lock(reason)
                    count += 1
                
                return Response({
                    'success': True,
                    'message': f'Locked {count} wallets'
                })
            
            elif operation == 'unlock':
                count = 0
                for wallet in wallets:
                    wallet.unlock()
                    count += 1
                
                return Response({
                    'success': True,
                    'message': f'Unlocked {count} wallets'
                })
            
            else:
                return Response({
                    'success': False,
                    'error': 'Invalid operation'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error performing bulk operation: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 8. Task APIs (Automated Tasks)
# ==========================================

class ExpireBonusBalancesAPIView(APIView):
    """Expire bonus balances that have passed expiry date"""
    permission_classes = [IsAdminUser]
    
    @transaction.atomic
    def post(self, request):
        try:
            now = timezone.now()
            expired_wallets = Wallet.objects.filter(
                bonus_balance__gt=0,
                bonus_expires_at__lte=now
            )
            
            count = 0
            total_expired = Decimal('0.00')
            
            for wallet in expired_wallets:
                expired_amount = wallet.bonus_balance
                wallet.bonus_balance = Decimal('0.00')
                wallet.bonus_expires_at = None
                wallet.save()
                
                # Log transaction
                WalletTransaction.objects.create(
                    wallet=wallet,
                    type='admin_debit',
                    amount=-expired_amount,
                    status='approved',
                    description=f'Bonus expired',
                    approved_by=request.user,
                    approved_at=now
                )
                
                count += 1
                total_expired += expired_amount
            
            return Response({
                'success': True,
                'message': f'Expired {count} bonus balances',
                'total_amount': float(total_expired)
            })
        
        except Exception as e:
            logger.error(f"Error expiring bonuses: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessWithdrawalsAPIView(APIView):
    """Auto-process pending withdrawals (for automation)"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            # Get pending withdrawals older than X hours
            hours = int(request.data.get('hours', 24))
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            pending_withdrawals = Withdrawal.objects.filter(
                status='pending',
                created_at__lte=cutoff_time
            )
            
            processed = 0
            for withdrawal in pending_withdrawals[:10]:  # Process in batches
                # Add your auto-processing logic here
                # For now, just log
                logger.info(f"Auto-processing withdrawal: {withdrawal.withdrawal_id}")
                processed += 1
            
            return Response({
                'success': True,
                'message': f'Processed {processed} withdrawals'
            })
        
        except Exception as e:
            logger.error(f"Error auto-processing withdrawals: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CleanupLogsAPIView(APIView):
    """Cleanup old webhook logs"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            days = int(request.data.get('days', 30))
            cutoff_date = timezone.now() - timedelta(days=days)
            
            deleted_count, _ = WalletWebhookLog.objects.filter(
                received_at__lte=cutoff_date,
                is_processed=True
            ).delete()
            
            return Response({
                'success': True,
                'message': f'Deleted {deleted_count} old webhook logs'
            })
        
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GenerateReportAPIView(APIView):
    """Generate wallet reports"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            report_type = request.data.get('report_type', 'daily')
            
            # Implement your report generation logic
            # For now, return sample data
            
            return Response({
                'success': True,
                'message': f'{report_type.capitalize()} report generated',
                'data': {
                    'report_type': report_type,
                    'generated_at': timezone.now().isoformat()
                }
            })
        
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SyncPaymentsAPIView(APIView):
    """Sync payment gateway statuses"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            # Implement payment gateway sync logic
            
            return Response({
                'success': True,
                'message': 'Payment sync completed'
            })
        
        except Exception as e:
            logger.error(f"Error syncing payments: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 9. User Task APIs
# ==========================================

class UserRequestWithdrawalAPIView(APIView):
    """User request withdrawal"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        try:
            # Get wallet
            wallet = Wallet.objects.get(user=request.user)
            
            # Validate amount
            amount = Decimal(str(request.data.get('amount', 0)))
            payment_method_id = request.data.get('payment_method_id')
            
            if amount <= 0:
                return Response({
                    'success': False,
                    'error': 'Invalid amount'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if amount > wallet.available_balance:
                return Response({
                    'success': False,
                    'error': 'Insufficient balance'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get payment method
            payment_method = UserPaymentMethod.objects.get(
                id=payment_method_id,
                user=request.user
            )
            
            # Calculate fee
            fee = (amount * Decimal('0.02')).quantize(Decimal('0.01'))
            net_amount = amount - fee
            
            # Create transaction
            wallet_txn = WalletTransaction.objects.create(
                wallet=wallet,
                type='withdrawal',
                amount=-amount,
                status='pending',
                description=f'Withdrawal to {payment_method.get_method_type_display()}',
                created_by=request.user
            )
            
            # Create withdrawal
            withdrawal = Withdrawal.objects.create(
                user=request.user,
                wallet=wallet,
                payment_method=payment_method,
                amount=amount,
                fee=fee,
                net_amount=net_amount,
                status='pending',
                WalletTransaction=wallet_txn
            )
            
            # Update wallet
            wallet.current_balance -= amount
            wallet.pending_balance += amount
            wallet.save()
            
            return Response({
                'success': True,
                'message': 'Withdrawal request created',
                'data': WithdrawalSerializer(withdrawal).data
            }, status=status.HTTP_201_CREATED)
        
        except Wallet.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Wallet not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except UserPaymentMethod.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Payment method not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Error creating withdrawal request: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserAddFundsAPIView(APIView):
    """User add funds (for testing/demo)"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        try:
            # This is typically handled by payment gateway
            # For demo purposes only
            
            wallet, _ = Wallet.objects.get_or_create(user=request.user)
            amount = Decimal(str(request.data.get('amount', 0)))
            
            if amount <= 0:
                return Response({
                    'success': False,
                    'error': 'Invalid amount'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create transaction
            WalletTransaction.objects.create(
                wallet=wallet,
                type='admin_credit',
                amount=amount,
                status='approved',
                description='Funds added',
                created_by=request.user,
                approved_by=request.user,
                approved_at=timezone.now()
            )
            
            # Update wallet
            wallet.current_balance += amount
            wallet.total_earned += amount
            wallet.save()
            
            return Response({
                'success': True,
                'message': 'Funds added successfully',
                'new_balance': float(wallet.current_balance)
            })
        
        except Exception as e:
            logger.error(f"Error adding funds: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
            
# api/wallet/views.py তে যোগ করুন



def handler404(request, exception):
    """Custom 404 handler"""
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Not Found',
            'message': 'The requested URL was not found on this server.'
        }, status=404)
    return render(request, '404.html', status=404)

def handler500(request):
    """Custom 500 handler"""
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Server Error',
            'message': 'An internal server error occurred.'
        }, status=500)
    return render(request, '500.html', status=500)





# ==========================================
# 6. Wallet Summary API  (FIXED)
# ==========================================
class WalletSummaryAPIView(APIView):
    """
    GET /api/wallet/summary/
    Returns dashboard stats shaped exactly for the frontend Wallet.jsx
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            now  = timezone.now()

            # ── Wallet queryset (admin sees all, user sees own) ───────────────
            if user.is_staff:
                wallets_qs = Wallet.objects.all()
                txn_qs     = WalletTransaction.objects.all()
                wd_qs      = Withdrawal.objects.all()
            else:
                wallets_qs = Wallet.objects.filter(user=user)
                txn_qs     = WalletTransaction.objects.select_related('wallet','wallet__user','created_by','approved_by').filter(wallet__user=user)
                wd_qs      = Withdrawal.objects.filter(user=user)

            # ── Total balance ─────────────────────────────────────────────────
            total_balance = wallets_qs.aggregate(
                total=Sum('current_balance')
            )['total'] or Decimal('0.00')

            # ── Balance change % (compare last 30 days vs previous 30 days) ──
            last_30   = now - timedelta(days=30)
            prev_30   = now - timedelta(days=60)

            recent_earned = txn_qs.filter(
                created_at__gte=last_30, status='approved', amount__gt=0
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

            prev_earned = txn_qs.filter(
                created_at__gte=prev_30, created_at__lt=last_30,
                status='approved', amount__gt=0
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

            if prev_earned > 0:
                balance_change_pct = float(
                    ((recent_earned - prev_earned) / prev_earned) * 100
                )
            else:
                balance_change_pct = 0.0

            # ── Currency breakdown (one row per wallet currency) ──────────────
            currency_breakdown = {}
            for w in wallets_qs.values('currency', 'current_balance'):
                cur = w['currency'] or 'USD'
                currency_breakdown[cur] = currency_breakdown.get(cur, 0) + float(
                    w['current_balance'] or 0
                )

            # ── Monthly growth (last 6 months income vs expense) ─────────────
            monthly_growth = []
            for i in range(5, -1, -1):          # 5 months ago → current month
                month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                month_end = (month_start + timedelta(days=32)).replace(day=1)

                income = txn_qs.filter(
                    created_at__gte=month_start,
                    created_at__lt=month_end,
                    status='approved',
                    amount__gt=0
                ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

                expense = txn_qs.filter(
                    created_at__gte=month_start,
                    created_at__lt=month_end,
                    status='approved',
                    amount__lt=0
                ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

                monthly_growth.append({
                    'month': month_start.strftime('%b'),   # "Jan", "Feb" …
                    'income':  float(income),
                    'expense': float(abs(expense)),
                })

            # ── Mining bars (last 12 approved transactions — amount as height) 
            recent_txns = txn_qs.filter(
                status='approved'
            ).order_by('-created_at').values('amount')[:12]

            raw_amounts = [float(abs(t['amount'])) for t in recent_txns]
            if raw_amounts:
                max_amt = max(raw_amounts) or 1
                # Normalise to 1-12 range for bar heights
                mining_bars = [
                    max(1, round((a / max_amt) * 11)) for a in reversed(raw_amounts)
                ]
            else:
                mining_bars = [4, 7, 5, 8, 6, 9, 7, 10, 8, 11, 9, 8]

            # ── Withdrawal request counts ─────────────────────────────────────
            pending_wd    = wd_qs.filter(status='pending').count()
            processing_wd = wd_qs.filter(status='processing').count()
            completed_wd  = wd_qs.filter(status='completed').count()

            # ── User info ─────────────────────────────────────────────────────
            profile = getattr(user, 'profile', None)
            user_data = {
                'name':   user.get_full_name() or user.username,
                'id':    user.id,
                'avatar': getattr(profile, 'avatar_url', '') or
                          getattr(profile, 'profile_picture', '') or '',
                'plan':   getattr(profile, 'membership', None) or
                          getattr(profile, 'plan', None) or
                          ('Admin' if user.is_staff else 'Member'),
            }

            # ── Mining stats (from stats fields if present, else sensible defaults)
            # You can replace these with real mining model queries if you have one
            mining_speed     = 0.0
            mining_gauge_pct = 0.0

            return Response({
                # ── Core balance ──────────────────────────────────────────────
                'total_balance':      float(total_balance),
                'balance_change_pct': round(balance_change_pct, 1),

                # ── Currency breakdown ────────────────────────────────────────
                'currency_breakdown': currency_breakdown,

                # ── Chart data ────────────────────────────────────────────────
                'monthly_growth': monthly_growth,

                # ── Mining ───────────────────────────────────────────────────
                'mining_speed':     mining_speed,
                'mining_gauge_pct': mining_gauge_pct,
                'mining_bars':      mining_bars,

                # ── Withdrawal counts (for Withdrawal Requests widget) ────────
                'withdrawal_counts': {
                    'pending':    pending_wd,
                    'processing': processing_wd,
                    'completed':  completed_wd,
                },

                # ── Investment packages ───────────────────────────────────────
                # Return empty list — add your InvestmentPackage model query here
                # e.g. InvestmentPackage.objects.filter(is_active=True).values(...)
                'investment_packages': [],

                # ── User ──────────────────────────────────────────────────────
                'user': user_data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching wallet summary: {e}", exc_info=True)
            return Response({
                'error': 'An error occurred fetching wallet summary',
                'detail': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as MR

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wallet_transfer(request):
    from .services import WalletService
    try:
        recipient = request.data.get('recipient')
        amount    = request.data.get('amount')
        currency  = request.data.get('currency', 'BDT')
        result = WalletService.transfer(request.user, recipient, amount, currency)
        return MR({'detail': 'Transfer successful', 'result': result})
    except Exception as e:
        return MR({'detail': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mining_start(request):
    return MR({'detail': 'Mining started', 'status': 'mining'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mining_stop(request):
    return MR({'detail': 'Mining stopped', 'status': 'idle'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mining_status(request):
    return MR({'status': 'idle', 'mining_speed': 0.0, 'mining_gauge_pct': 0.0})
