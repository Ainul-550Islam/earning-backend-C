from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, DatabaseError
from django.db.models import F, Q, Sum
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, Tuple
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
    UserPaymentMethodSerializer
)

# Logger setup
logger = logging.getLogger(__name__)


# ==========================================
# Helper Functions (Defensive)
# ==========================================

def safe_decimal(value: Any, default: Decimal = Decimal('0.00')) -> Decimal:
    """
    Safely convert any value to Decimal
    """
    try:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError):
        logger.warning(f"Failed to convert {value} to Decimal, using default {default}")
        return default


def get_or_create_wallet(user) -> Tuple[Wallet, bool]:
    """
    Get or create wallet for user (Defensive)
    Returns: (wallet, created)
    """
    try:
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={
                'current_balance': Decimal('0.00'),
                'pending_balance': Decimal('0.00'),
                'total_earned': Decimal('0.00'),
                'total_withdrawn': Decimal('0.00'),
                'frozen_balance': Decimal('0.00'),
                'bonus_balance': Decimal('0.00'),
                'currency': 'BDT',
                'is_locked': False,
            }
        )
        return wallet, created
    except DatabaseError as e:
        logger.error(f"Database error creating wallet for user {user.id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating wallet for user {user.id}: {e}")
        raise


def validate_amount(amount: Any, min_amount: Decimal = Decimal('1.00')) -> Tuple[bool, str, Optional[Decimal]]:
    """
    Validate transaction amount
    Returns: (is_valid, error_message, decimal_amount)
    """
    try:
        decimal_amount = safe_decimal(amount)
        
        if decimal_amount <= 0:
            return False, "Amount must be greater than 0", None
        
        if decimal_amount < min_amount:
            return False, f"Minimum amount is {min_amount}", None
        
        return True, "", decimal_amount
    
    except Exception as e:
        logger.error(f"Error validating amount {amount}: {e}")
        return False, "Invalid amount format", None


# ==========================================
# 1. Get Wallet Balance
# ==========================================
class WalletBalanceView(APIView):
    """
    GET /api/wallet/balance/
    Get current user's wallet balance
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request) -> Response:
        try:
            # Get or create wallet (defensive)
            wallet, created = get_or_create_wallet(request.user)
            
            if created:
                logger.info(f"Created new wallet for user {request.user.id}")
            
            # Serialize wallet data
            serializer = WalletSerializer(wallet)
            
            # Additional computed fields
            data = serializer.data
            data['available_for_withdrawal'] = float(wallet.available_balance)
            data['is_wallet_locked'] = wallet.is_locked
            
            return Response({
                'success': True,
                'data': data
            }, status=status.HTTP_200_OK)
        
        except DatabaseError as e:
            logger.error(f"Database error fetching wallet for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'Database error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            logger.error(f"Unexpected error fetching wallet for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 2. Transaction History
# ==========================================
class TransactionHistoryView(APIView):
    """
    GET /api/wallet/transactions/
    Get user's transaction history with pagination
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request) -> Response:
        try:
            # Get or create wallet
            wallet, _ = get_or_create_wallet(request.user)
            
            # Query parameters (defensive)
            page = max(1, int(request.GET.get('page', 1)))
            page_size = min(100, max(10, int(request.GET.get('page_size', 20))))
            transaction_type = request.GET.get('type', None)
            transaction_status = request.GET.get('status', None)
            
            # Build query
            queryset = WalletTransaction.objects.filter(wallet=wallet)
            
            # Filters
            if transaction_type:
                queryset = queryset.filter(type=transaction_type)
            
            if transaction_status:
                queryset = queryset.filter(status=transaction_status)
            
            # Count total
            total_count = queryset.count()
            
            # Pagination
            start = (page - 1) * page_size
            end = start + page_size
            transactions = queryset[start:end]
            
            # Serialize
            serializer = WalletTransactionSerializer(transactions, many=True)
            
            return Response({
                'success': True,
                'data': {
                    'transactions': serializer.data,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': total_count,
                        'total_pages': (total_count + page_size - 1) // page_size
                    }
                }
            }, status=status.HTTP_200_OK)
        
        except ValueError as e:
            logger.warning(f"Invalid pagination parameters: {e}")
            return Response({
                'success': False,
                'error': 'Invalid pagination parameters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error fetching transactions for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'An error occurred while fetching transactions'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 3. Add Money (Admin/System)
# ==========================================
class AddMoneyView(APIView):
    """
    POST /api/wallet/add-money/
    Add money to wallet (Admin or Task completion)
    Body: {
        "amount": 100.00,
        "type": "earning",
        "description": "Task completion reward",
        "reference_id": "task_123"
    }
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request) -> Response:
        try:
            # Get wallet
            wallet, _ = get_or_create_wallet(request.user)
            
            # Check if wallet is locked
            if wallet.is_locked:
                return Response({
                    'success': False,
                    'error': f'Wallet is locked: {wallet.locked_reason}'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate amount
            amount = request.data.get('amount')
            is_valid, error_msg, decimal_amount = validate_amount(amount)
            
            if not is_valid:
                return Response({
                    'success': False,
                    'error': error_msg
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get transaction type
            transaction_type = request.data.get('type', 'earning')
            allowed_types = ['earning', 'reward', 'referral', 'bonus', 'admin_credit']
            
            if transaction_type not in allowed_types:
                return Response({
                    'success': False,
                    'error': f'Invalid transaction type. Allowed: {", ".join(allowed_types)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get balance before
            balance_before = wallet.current_balance
            
            # Create transaction
            wallet_transaction = WalletTransaction.objects.create(
                wallet=wallet,
                type=transaction_type,
                amount=decimal_amount,
                status='approved',
                description=request.data.get('description', ''),
                reference_id=request.data.get('reference_id', ''),
                reference_type=request.data.get('reference_type', ''),
                balance_before=balance_before,
                balance_after=balance_before + decimal_amount,
                created_by=request.user,
                approved_by=request.user,
                approved_at=timezone.now(),
                metadata=request.data.get('metadata', {})
            )
            
            # Update wallet balance
            wallet.current_balance = F('current_balance') + decimal_amount
            wallet.total_earned = F('total_earned') + decimal_amount
            wallet.save()
            
            # Refresh from DB
            wallet.refresh_from_db()
            
            # Log success
            logger.info(f"Added {decimal_amount} to wallet {wallet.id} for user {request.user.id}")
            
            return Response({
                'success': True,
                'message': 'Money added successfully',
                'data': {
                    'transaction_id': str(wallet_transaction.walletTransaction_id),
                    'amount': float(decimal_amount),
                    'new_balance': float(wallet.current_balance),
                    'transaction': WalletTransactionSerializer(wallet_transaction).data
                }
            }, status=status.HTTP_201_CREATED)
        
        except DatabaseError as e:
            logger.error(f"Database error adding money for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'Database error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            logger.error(f"Unexpected error adding money for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 4. Withdraw Money
# ==========================================
class WithdrawMoneyView(APIView):
    """
    POST /api/wallet/withdraw/
    Create withdrawal request
    Body: {
        "amount": 500.00,
        "payment_method_id": 1
    }
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request) -> Response:
        try:
            # Get wallet
            wallet, _ = get_or_create_wallet(request.user)
            
            # Check if wallet is locked
            if wallet.is_locked:
                return Response({
                    'success': False,
                    'error': f'Wallet is locked: {wallet.locked_reason}'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate amount
            amount = request.data.get('amount')
            min_withdrawal = Decimal('100.00')  # Minimum withdrawal amount
            is_valid, error_msg, decimal_amount = validate_amount(amount, min_withdrawal)
            
            if not is_valid:
                return Response({
                    'success': False,
                    'error': error_msg
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check available balance
            if decimal_amount > wallet.available_balance:
                return Response({
                    'success': False,
                    'error': f'Insufficient balance. Available: {wallet.available_balance}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get payment method
            payment_method_id = request.data.get('payment_method_id')
            
            if not payment_method_id:
                return Response({
                    'success': False,
                    'error': 'Payment method is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                payment_method = UserPaymentMethod.objects.get(
                    id=payment_method_id,
                    user=request.user
                )
            except UserPaymentMethod.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Payment method not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Calculate fee (2% example)
            fee_percentage = Decimal('0.02')  # 2%
            fee = (decimal_amount * fee_percentage).quantize(Decimal('0.01'))
            net_amount = decimal_amount - fee
            
            # Get balance before
            balance_before = wallet.current_balance
            
            # Create wallet transaction
            wallet_transaction = WalletTransaction.objects.create(
                wallet=wallet,
                type='withdrawal',
                amount=-decimal_amount,  # Negative for withdrawal
                status='pending',
                description=f'Withdrawal request to {payment_method.get_method_type_display()}',
                reference_type='withdrawal',
                balance_before=balance_before,
                balance_after=balance_before - decimal_amount,
                created_by=request.user,
            )
            
            # Create withdrawal request
            withdrawal = Withdrawal.objects.create(
                user=request.user,
                wallet=wallet,
                payment_method=payment_method,
                amount=decimal_amount,
                fee=fee,
                net_amount=net_amount,
                status='pending',
                WalletTransaction=wallet_transaction
            )
            
            # Deduct from wallet (pending withdrawal)
            wallet.current_balance = F('current_balance') - decimal_amount
            wallet.pending_balance = F('pending_balance') + decimal_amount
            wallet.save()
            
            # Refresh from DB
            wallet.refresh_from_db()
            
            # Log success
            logger.info(f"Withdrawal request created: {withdrawal.withdrawal_id} for user {request.user.id}")
            
            return Response({
                'success': True,
                'message': 'Withdrawal request created successfully',
                'data': {
                    'withdrawal_id': str(withdrawal.withdrawal_id),
                    'amount': float(decimal_amount),
                    'fee': float(fee),
                    'net_amount': float(net_amount),
                    'status': withdrawal.status,
                    'withdrawal': WithdrawalSerializer(withdrawal).data
                }
            }, status=status.HTTP_201_CREATED)
        
        except DatabaseError as e:
            logger.error(f"Database error creating withdrawal for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'Database error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            logger.error(f"Unexpected error creating withdrawal for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 5. Payment Methods Management
# ==========================================
class PaymentMethodsView(APIView):
    """
    GET /api/wallet/payment-methods/
    POST /api/wallet/payment-methods/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request) -> Response:
        """Get all payment methods for user"""
        try:
            payment_methods = UserPaymentMethod.objects.filter(user=request.user)
            serializer = UserPaymentMethodSerializer(payment_methods, many=True)
            
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error fetching payment methods for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'An error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @transaction.atomic
    def post(self, request) -> Response:
        """Add new payment method"""
        try:
            serializer = UserPaymentMethodSerializer(data=request.data)
            
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if setting as primary
            is_primary = request.data.get('is_primary', False)
            
            if is_primary:
                # Unset other primary methods
                UserPaymentMethod.objects.filter(
                    user=request.user,
                    is_primary=True
                ).update(is_primary=False)
            
            # Create payment method
            payment_method = serializer.save(user=request.user)
            
            return Response({
                'success': True,
                'message': 'Payment method added successfully',
                'data': UserPaymentMethodSerializer(payment_method).data
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Error adding payment method for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'An error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 6. Withdrawal History
# ==========================================
class WithdrawalHistoryView(APIView):
    """
    GET /api/wallet/withdrawals/
    Get user's withdrawal history
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request) -> Response:
        try:
            # Query parameters
            page = max(1, int(request.GET.get('page', 1)))
            page_size = min(100, max(10, int(request.GET.get('page_size', 20))))
            withdrawal_status = request.GET.get('status', None)
            
            # Build query
            queryset = Withdrawal.objects.filter(user=request.user)
            
            if withdrawal_status:
                queryset = queryset.filter(status=withdrawal_status)
            
            # Count total
            total_count = queryset.count()
            
            # Pagination
            start = (page - 1) * page_size
            end = start + page_size
            withdrawals = queryset[start:end]
            
            # Serialize
            serializer = WithdrawalSerializer(withdrawals, many=True)
            
            return Response({
                'success': True,
                'data': {
                    'withdrawals': serializer.data,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': total_count,
                        'total_pages': (total_count + page_size - 1) // page_size
                    }
                }
            }, status=status.HTTP_200_OK)
        
        except ValueError as e:
            logger.warning(f"Invalid pagination parameters: {e}")
            return Response({
                'success': False,
                'error': 'Invalid pagination parameters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error fetching withdrawals for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'An error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 7. Wallet Statistics
# ==========================================
class WalletStatisticsView(APIView):
    """
    GET /api/wallet/statistics/
    Get wallet statistics and summary
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request) -> Response:
        try:
            # Get wallet
            wallet, _ = get_or_create_wallet(request.user)
            
            # Get transaction stats
            transaction_stats = WalletTransaction.objects.filter(
                wallet=wallet,
                status='approved'
            ).aggregate(
                total_earnings=Sum('amount', filter=Q(type__in=['earning', 'reward', 'referral', 'bonus'])),
                total_withdrawals=Sum('amount', filter=Q(type='withdrawal')),
                total_transactions=Sum('amount')
            )
            
            # Get withdrawal stats
            withdrawal_stats = Withdrawal.objects.filter(user=request.user).aggregate(
                pending_withdrawals=Sum('amount', filter=Q(status='pending')),
                completed_withdrawals=Sum('amount', filter=Q(status='completed')),
                total_fees_paid=Sum('fee', filter=Q(status='completed'))
            )
            
            # Safely handle None values
            stats = {
                'current_balance': float(wallet.current_balance or 0),
                'available_balance': float(wallet.available_balance or 0),
                'pending_balance': float(wallet.pending_balance or 0),
                'frozen_balance': float(wallet.frozen_balance or 0),
                'bonus_balance': float(wallet.bonus_balance or 0),
                'total_earned': float(wallet.total_earned or 0),
                'total_withdrawn': float(wallet.total_withdrawn or 0),
                'total_earnings_from_transactions': float(transaction_stats.get('total_earnings') or 0),
                'total_withdrawals_amount': abs(float(transaction_stats.get('total_withdrawals') or 0)),
                'pending_withdrawals': float(withdrawal_stats.get('pending_withdrawals') or 0),
                'completed_withdrawals': float(withdrawal_stats.get('completed_withdrawals') or 0),
                'total_fees_paid': float(withdrawal_stats.get('total_fees_paid') or 0),
                'is_wallet_locked': wallet.is_locked,
                'currency': wallet.currency,
            }
            
            return Response({
                'success': True,
                'data': stats
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error fetching wallet statistics for user {request.user.id}: {e}")
            return Response({
                'success': False,
                'error': 'An error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)