"""
api/adapters/wallet.py
Wallet adapter for earning backend platform
"""
from django.db.models import Q
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wallet_balance(request):
    """Get user's wallet balance."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's wallet
        from wallet.models import Wallet
        try:
            wallet = Wallet.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except Wallet.DoesNotExist:
            # Create default wallet
            wallet = Wallet.objects.create(
                user=user,
                balance=Decimal('0'),
                currency='USD',
                status='active',
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
        
        # Get wallet summary
        balance_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'wallet': {
                'id': wallet.id,
                'balance': str(wallet.balance),
                'currency': wallet.currency,
                'status': wallet.status,
                'created_at': wallet.created_at.isoformat(),
                'last_updated': wallet.updated_at.isoformat() if wallet.updated_at else None,
            },
            'balance_breakdown': _get_balance_breakdown(wallet, tenant_id),
            'transaction_summary': _get_transaction_summary(wallet, tenant_id),
            'pending_transactions': _get_pending_transactions(wallet, tenant_id),
            'withdrawal_info': _get_withdrawal_info(wallet, tenant_id),
            'earnings_summary': _get_earnings_summary(wallet, tenant_id),
            'spending_summary': _get_spending_summary(wallet, tenant_id),
        }
        
        return Response({
            'success': True,
            'data': balance_data,
            'message': 'Wallet balance retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[WalletAdapter] Error getting wallet balance: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve wallet balance',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transaction_history(request):
    """Get user's transaction history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        transaction_type = request.GET.get('type')  # 'all', 'credit', 'debit', 'withdrawal', 'deposit'
        status = request.GET.get('status')  # 'all', 'pending', 'completed', 'failed', 'cancelled'
        category = request.GET.get('category')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get user's wallet
        from wallet.models import Wallet, WalletTransaction
        try:
            wallet = Wallet.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except Wallet.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Wallet not found',
                'details': 'Please create a wallet first'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get transactions
        queryset = WalletTransaction.objects.filter(
            wallet=wallet
        ).order_by('-created_at')
        
        # Apply filters
        if transaction_type and transaction_type != 'all':
            queryset = queryset.filter(transaction_type=transaction_type)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category=category)
        
        # Paginate
        transactions = queryset[offset:offset+limit]
        
        # Serialize transactions
        transaction_data = []
        for transaction in transactions:
            transaction_data.append({
                'id': transaction.id,
                'transaction_type': transaction.transaction_type,
                'amount': str(transaction.amount),
                'balance_before': str(transaction.balance_before),
                'balance_after': str(transaction.balance_after),
                'status': transaction.status,
                'category': transaction.category,
                'description': transaction.description,
                'reference_id': transaction.reference_id,
                'reference_type': transaction.reference_type,
                'created_at': transaction.created_at.isoformat(),
                'completed_at': transaction.completed_at.isoformat() if transaction.completed_at else None,
                'metadata': transaction.metadata,
                'is_pending': transaction.status == 'pending',
                'is_credit': transaction.transaction_type == 'credit',
                'is_debit': transaction.transaction_type == 'debit',
                'is_withdrawal': transaction.category == 'withdrawal',
                'is_deposit': transaction.category == 'deposit',
                'external_reference': transaction.external_reference,
                'fee_amount': str(transaction.fee_amount) if transaction.fee_amount else '0.00',
                'exchange_rate': transaction.exchange_rate,
                'original_amount': str(transaction.original_amount) if transaction.original_amount else None,
                'original_currency': transaction.original_currency,
            })
        
        return Response({
            'success': True,
            'data': {
                'transactions': transaction_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(transaction_data) == limit
                },
                'filters': {
                    'type': transaction_type,
                    'status': status,
                    'category': category
                },
                'summary': _get_transaction_summary(wallet, tenant_id, queryset),
                'wallet_balance': str(wallet.balance),
                'currency': wallet.currency
            },
            'message': 'Transaction history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[WalletAdapter] Error getting transaction history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve transaction history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_withdrawal_request(request):
    """Create a withdrawal request."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['amount', 'payment_method']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user's wallet
        from wallet.models import Wallet, WithdrawalRequest
        try:
            wallet = Wallet.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except Wallet.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Wallet not found',
                'details': 'Please create a wallet first'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate withdrawal amount
        amount = Decimal(str(data['amount']))
        if amount <= 0:
            return Response({
                'success': False,
                'error': 'Invalid amount',
                'details': 'Amount must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if amount > wallet.balance:
            return Response({
                'success': False,
                'error': 'Insufficient balance',
                'details': f'You have {wallet.balance} but requested {amount}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check withdrawal limits
        if not _check_withdrawal_limits(user, amount, tenant_id):
            return Response({
                'success': False,
                'error': 'Withdrawal limit exceeded',
                'details': 'Withdrawal amount exceeds your limits'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create withdrawal request
        withdrawal = WithdrawalRequest.objects.create(
            wallet=wallet,
            amount=amount,
            payment_method=data['payment_method'],
            status='pending',
            fees=Decimal(str(data.get('fees', '0'))),
            payout_address=data.get('payout_address', ''),
            payout_details=data.get('payout_details', {}),
            notes=data.get('notes', ''),
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Create pending transaction
        from wallet.models import WalletTransaction
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='debit',
            amount=amount + withdrawal.fees,
            balance_before=wallet.balance,
            balance_after=wallet.balance - amount - withdrawal.fees,
            status='pending',
            category='withdrawal',
            description=f'Withdrawal request - {data["payment_method"]}',
            reference_id=str(withdrawal.id),
            reference_type='withdrawal_request',
            fee_amount=withdrawal.fees,
            metadata={
                'withdrawal_request_id': withdrawal.id,
                'payment_method': data['payment_method']
            },
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Update wallet balance (will be processed when approved)
        # wallet.balance -= amount
        # wallet.save()
        
        # Emit withdrawal request event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('wallet.withdrawal_requested', {
            'user_id': user.id,
            'withdrawal_id': withdrawal.id,
            'amount': str(amount),
            'payment_method': data['payment_method'],
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'withdrawal_id': withdrawal.id,
                'amount': str(amount),
                'fees': str(withdrawal.fees),
                'total_amount': str(amount + withdrawal.fees),
                'payment_method': withdrawal.payment_method,
                'status': withdrawal.status,
                'created_at': withdrawal.created_at.isoformat(),
                'estimated_processing_time': _get_withdrawal_processing_time(withdrawal.payment_method),
                'wallet_balance': str(wallet.balance),
                'pending_balance': str(wallet.balance - amount - withdrawal.fees),
            },
            'message': 'Withdrawal request created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[WalletAdapter] Error creating withdrawal request: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create withdrawal request',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_withdrawal_history(request):
    """Get user's withdrawal history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        status = request.GET.get('status')  # 'all', 'pending', 'processing', 'completed', 'cancelled', 'rejected'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get user's wallet
        from wallet.models import Wallet, WithdrawalRequest
        try:
            wallet = Wallet.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except Wallet.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Wallet not found',
                'details': 'Please create a wallet first'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get withdrawal requests
        queryset = WithdrawalRequest.objects.filter(
            wallet=wallet
        ).order_by('-created_at')
        
        # Apply status filter
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        # Paginate
        withdrawals = queryset[offset:offset+limit]
        
        # Serialize withdrawals
        withdrawal_data = []
        for withdrawal in withdrawals:
            withdrawal_data.append({
                'id': withdrawal.id,
                'amount': str(withdrawal.amount),
                'fees': str(withdrawal.fees),
                'total_amount': str(withdrawal.amount + withdrawal.fees),
                'payment_method': withdrawal.payment_method,
                'status': withdrawal.status,
                'payout_address': withdrawal.payout_address,
                'payout_details': withdrawal.payout_details,
                'notes': withdrawal.notes,
                'created_at': withdrawal.created_at.isoformat(),
                'processed_at': withdrawal.processed_at.isoformat() if withdrawal.processed_at else None,
                'completed_at': withdrawal.completed_at.isoformat() if withdrawal.completed_at else None,
                'rejected_at': withdrawal.rejected_at.isoformat() if withdrawal.rejected_at else None,
                'rejection_reason': withdrawal.rejection_reason,
                'transaction_id': withdrawal.transaction_id,
                'external_reference': withdrawal.external_reference,
                'metadata': withdrawal.metadata,
                'estimated_processing_time': _get_withdrawal_processing_time(withdrawal.payment_method),
                'is_pending': withdrawal.status == 'pending',
                'is_processing': withdrawal.status == 'processing',
                'is_completed': withdrawal.status == 'completed',
                'is_cancelled': withdrawal.status == 'cancelled',
                'is_rejected': withdrawal.status == 'rejected',
            })
        
        return Response({
            'success': True,
            'data': {
                'withdrawals': withdrawal_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(withdrawal_data) == limit
                },
                'filters': {
                    'status': status
                },
                'summary': _get_withdrawal_summary(queryset),
                'wallet_balance': str(wallet.balance),
                'currency': wallet.currency
            },
            'message': 'Withdrawal history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[WalletAdapter] Error getting withdrawal history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve withdrawal history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_methods(request):
    """Get available payment methods."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get available payment methods
        from wallet.models import PaymentMethod
        payment_methods = PaymentMethod.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('sort_order', 'name')
        
        # Get user's preferred methods
        from wallet.models import UserPaymentMethod
        user_methods = UserPaymentMethod.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_active=True
        ).select_related('payment_method')
        
        # Serialize payment methods
        method_data = []
        for method in payment_methods:
            user_method = user_methods.filter(payment_method=method).first()
            
            method_data.append({
                'id': method.id,
                'name': method.name,
                'display_name': method.display_name,
                'method_type': method.method_type,
                'description': method.description,
                'icon': method.icon,
                'currencies': method.currencies,
                'min_amount': str(method.min_amount),
                'max_amount': str(method.max_amount),
                'fees': method.fees,
                'processing_time': method.processing_time,
                'is_available': _is_method_available(method, user, tenant_id),
                'is_user_setup': user_method is not None,
                'user_setup': {
                    'id': user_method.id if user_method else None,
                    'account_identifier': user_method.account_identifier if user_method else None,
                    'is_default': user_method.is_default if user_method else False,
                    'setup_date': user_method.created_at.isoformat() if user_method else None,
                    'last_used': user_method.last_used.isoformat() if user_method and user_method.last_used else None,
                } if user_method else None,
                'requirements': method.requirements,
                'supported_countries': method.supported_countries,
                'verification_required': method.verification_required,
                'metadata': method.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'payment_methods': method_data,
                'user_setup_count': user_methods.count(),
                'default_method': user_methods.filter(is_default=True).first().payment_method.name if user_methods.filter(is_default=True).exists() else None,
                'currency': _get_user_currency(user, tenant_id),
                'withdrawal_limits': _get_user_withdrawal_limits(user, tenant_id),
            },
            'message': 'Payment methods retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[WalletAdapter] Error getting payment methods: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve payment methods',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_payment_method(request):
    """Setup a payment method for user."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['payment_method_id', 'account_identifier']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get payment method
        from wallet.models import PaymentMethod, UserPaymentMethod
        try:
            payment_method = PaymentMethod.objects.get(
                id=data['payment_method_id'],
                tenant_id=tenant_id,
                is_active=True
            )
        except PaymentMethod.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Payment method not found',
                'details': f'Payment method with ID {data["payment_method_id"]} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if method is already setup
        existing_method = UserPaymentMethod.objects.filter(
            user=user,
            payment_method=payment_method,
            tenant_id=tenant_id
        ).first()
        
        if existing_method:
            return Response({
                'success': False,
                'error': 'Payment method already setup',
                'details': 'This payment method is already configured for your account'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create user payment method
        user_payment_method = UserPaymentMethod.objects.create(
            user=user,
            payment_method=payment_method,
            account_identifier=data['account_identifier'],
            is_default=data.get('is_default', False),
            setup_details=data.get('setup_details', {}),
            verification_status='pending',
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # If setting as default, unset other defaults
        if data.get('is_default', False):
            UserPaymentMethod.objects.filter(
                user=user,
                tenant_id=tenant_id,
                is_default=True
            ).exclude(id=user_payment_method.id).update(is_default=False)
        
        # Emit payment method setup event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('wallet.payment_method_setup', {
            'user_id': user.id,
            'payment_method_id': payment_method.id,
            'user_payment_method_id': user_payment_method.id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'user_payment_method_id': user_payment_method.id,
                'payment_method': {
                    'id': payment_method.id,
                    'name': payment_method.name,
                    'method_type': payment_method.method_type,
                },
                'account_identifier': data['account_identifier'],
                'is_default': user_payment_method.is_default,
                'verification_status': user_payment_method.verification_status,
                'created_at': user_payment_method.created_at.isoformat(),
                'setup_requirements': payment_method.requirements,
                'next_steps': _get_payment_method_setup_steps(payment_method, user_payment_method)
            },
            'message': 'Payment method setup initiated successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[WalletAdapter] Error setting up payment method: {e}")
        return Response({
            'success': False,
            'error': 'Failed to setup payment method',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_wallet_analytics(request):
    """Get wallet analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get wallet analytics
        from wallet.models import Wallet, WalletTransaction, WithdrawalRequest
        wallets = Wallet.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        transactions = WalletTransaction.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('wallet__user')
        
        withdrawals = WithdrawalRequest.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('wallet__user')
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'wallet_metrics': {
                'total_wallets': wallets.count(),
                'active_wallets': wallets.filter(status='active').count(),
                'total_balance': wallets.aggregate(
                    total=Sum(F('balance'))
                )['total'] or Decimal('0'),
                'average_balance': wallets.aggregate(
                    avg_balance=Avg(F('balance'))
                )['avg_balance'] or Decimal('0'),
                'new_wallets': wallets.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count(),
            },
            'transaction_metrics': {
                'total_transactions': transactions.count(),
                'credit_transactions': transactions.filter(transaction_type='credit').count(),
                'debit_transactions': transactions.filter(transaction_type='debit').count(),
                'total_credits': transactions.filter(
                    transaction_type='credit'
                ).aggregate(
                    total=Sum(F('amount'))
                )['total'] or Decimal('0'),
                'total_debits': transactions.filter(
                    transaction_type='debit'
                ).aggregate(
                    total=Sum(F('amount'))
                )['total'] or Decimal('0'),
                'net_flow': transactions.aggregate(
                    net=Sum(F('amount'))
                )['net'] or Decimal('0'),
                'transaction_types': list(transactions.values('transaction_type').annotate(
                    count=Count('id'),
                    total_amount=Sum(F('amount'))
                ).order_by('-total_amount')),
                'daily_trends': _get_transaction_trends(transactions, days)
            },
            'withdrawal_metrics': {
                'total_withdrawals': withdrawals.count(),
                'pending_withdrawals': withdrawals.filter(status='pending').count(),
                'processing_withdrawals': withdrawals.filter(status='processing').count(),
                'completed_withdrawals': withdrawals.filter(status='completed').count(),
                'cancelled_withdrawals': withdrawals.filter(status='cancelled').count(),
                'rejected_withdrawals': withdrawals.filter(status='rejected').count(),
                'total_withdrawal_amount': withdrawals.filter(
                    status='completed'
                ).aggregate(
                    total=Sum(F('amount'))
                )['total'] or Decimal('0'),
                'total_fees': withdrawals.filter(
                    status='completed'
                ).aggregate(
                    total=Sum(F('fees'))
                )['total'] or Decimal('0'),
                'average_withdrawal_amount': withdrawals.filter(
                    status='completed'
                ).aggregate(
                    avg_amount=Avg(F('amount'))
                )['avg_amount'] or Decimal('0'),
                'withdrawal_methods': list(withdrawals.values('payment_method').annotate(
                    count=Count('id'),
                    total_amount=Sum(F('amount'))
                ).order_by('-total_amount')),
                'daily_trends': _get_withdrawal_trends(withdrawals, days)
            },
            'user_metrics': {
                'total_users_with_balance': wallets.filter(
                    balance__gt=0
                ).values('user').distinct().count(),
                'active_users': wallets.filter(
                    status='active',
                    updated_at__gte=timezone.now() - timedelta(days=30)
                ).values('user').distinct().count(),
                'top_balances': wallets.order_by('-balance')[:10],
                'most_active_users': transactions.values(
                    'wallet__user__username',
                    'wallet__user__first_name',
                    'wallet__user__last_name'
                ).annotate(
                    transaction_count=Count('id')
                ).order_by('-transaction_count')[:10]
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Wallet analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[WalletAdapter] Error getting wallet analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve wallet analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_balance_breakdown(wallet, tenant_id) -> Dict:
    """Get balance breakdown by category."""
    try:
        from wallet.models import WalletTransaction
        
        # Get breakdown by category
        breakdown = WalletTransaction.objects.filter(
            wallet=wallet,
            status='completed'
        ).values('category').annotate(
            amount=Sum(F('amount')),
            count=Count('id')
        ).order_by('-amount')
        
        return {
            'by_category': list(breakdown),
            'total_categories': breakdown.count(),
            'largest_category': breakdown.first()['category'] if breakdown.exists() else None
        }
    except Exception:
        return {}


def _get_transaction_summary(wallet, tenant_id, queryset=None) -> Dict:
    """Get transaction summary."""
    try:
        from wallet.models import WalletTransaction
        
        if queryset is None:
            queryset = WalletTransaction.objects.filter(wallet=wallet)
        
        # Calculate summary
        total_transactions = queryset.count()
        completed_transactions = queryset.filter(status='completed').count()
        pending_transactions = queryset.filter(status='pending').count()
        
        total_credits = queryset.filter(
            transaction_type='credit',
            status='completed'
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
        
        total_debits = queryset.filter(
            transaction_type='debit',
            status='completed'
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
        
        return {
            'total_transactions': total_transactions,
            'completed_transactions': completed_transactions,
            'pending_transactions': pending_transactions,
            'total_credits': str(total_credits),
            'total_debits': str(total_debits),
            'net_flow': str(total_credits - total_debits),
            'success_rate': round((completed_transactions / max(total_transactions, 1)) * 100, 2)
        }
    except Exception:
        return {}


def _get_pending_transactions(wallet, tenant_id) -> List[Dict]:
    """Get pending transactions."""
    try:
        from wallet.models import WalletTransaction
        pending = WalletTransaction.objects.filter(
            wallet=wallet,
            status='pending'
        ).order_by('-created_at')[:5]
        
        return [
            {
                'id': transaction.id,
                'transaction_type': transaction.transaction_type,
                'amount': str(transaction.amount),
                'description': transaction.description,
                'created_at': transaction.created_at.isoformat(),
                'category': transaction.category
            }
            for transaction in pending
        ]
    except Exception:
        return []


def _get_withdrawal_info(wallet, tenant_id) -> Dict:
    """Get withdrawal information."""
    try:
        from wallet.models import WithdrawalRequest
        
        # Get pending withdrawals
        pending_withdrawals = WithdrawalRequest.objects.filter(
            wallet=wallet,
            status='pending'
        ).order_by('-created_at')
        
        # Get last completed withdrawal
        last_completed = WithdrawalRequest.objects.filter(
            wallet=wallet,
            status='completed'
        ).order_by('-completed_at').first()
        
        return {
            'pending_count': pending_withdrawals.count(),
            'pending_amount': pending_withdrawals.aggregate(
                total=Sum(F('amount'))
            )['total'] or Decimal('0'),
            'pending_fees': pending_withdrawals.aggregate(
                total=Sum(F('fees'))
            )['total'] or Decimal('0'),
            'last_completed': {
                'amount': str(last_completed.amount) if last_completed else '0.00',
                'date': last_completed.completed_at.isoformat() if last_completed else None,
                'payment_method': last_completed.payment_method if last_completed else None,
            } if last_completed else None,
            'withdrawal_limits': _get_user_withdrawal_limits(wallet.user, tenant_id)
        }
    except Exception:
        return {}


def _get_earnings_summary(wallet, tenant_id) -> Dict:
    """Get earnings summary."""
    try:
        from wallet.models import WalletTransaction
        
        # Get credit transactions
        credits = WalletTransaction.objects.filter(
            wallet=wallet,
            transaction_type='credit',
            status='completed'
        )
        
        # Calculate earnings by category
        by_category = credits.values('category').annotate(
            amount=Sum(F('amount')),
            count=Count('id')
        ).order_by('-amount')
        
        # Calculate time-based earnings
        from django.utils import timezone
        from datetime import timedelta
        
        last_30_days = timezone.now() - timedelta(days=30)
        last_7_days = timezone.now() - timedelta(days=7)
        
        earnings_30_days = credits.filter(
            created_at__gte=last_30_days
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
        
        earnings_7_days = credits.filter(
            created_at__gte=last_7_days
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
        
        return {
            'total_earnings': str(credits.aggregate(
                total=Sum(F('amount'))
            )['total'] or Decimal('0')),
            'by_category': list(by_category),
            'last_30_days': str(earnings_30_days),
            'last_7_days': str(earnings_7_days),
            'daily_average_30_days': str(earnings_30_days / 30),
            'daily_average_7_days': str(earnings_7_days / 7),
            'growth_rate': round(((earnings_7_days - (earnings_30_days / 30 * 7)) / max((earnings_30_days / 30 * 7), 1)) * 100, 2) if earnings_30_days > 0 else 0
        }
    except Exception:
        return {}


def _get_spending_summary(wallet, tenant_id) -> Dict:
    """Get spending summary."""
    try:
        from wallet.models import WalletTransaction
        
        # Get debit transactions
        debits = WalletTransaction.objects.filter(
            wallet=wallet,
            transaction_type='debit',
            status='completed'
        )
        
        # Calculate spending by category
        by_category = debits.values('category').annotate(
            amount=Sum(F('amount')),
            count=Count('id')
        ).order_by('-amount')
        
        # Calculate time-based spending
        from django.utils import timezone
        from datetime import timedelta
        
        last_30_days = timezone.now() - timedelta(days=30)
        last_7_days = timezone.now() - timedelta(days=7)
        
        spending_30_days = debits.filter(
            created_at__gte=last_30_days
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
        
        spending_7_days = debits.filter(
            created_at__gte=last_7_days
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
        
        return {
            'total_spending': str(debits.aggregate(
                total=Sum(F('amount'))
            )['total'] or Decimal('0')),
            'by_category': list(by_category),
            'last_30_days': str(spending_30_days),
            'last_7_days': str(spending_7_days),
            'daily_average_30_days': str(spending_30_days / 30),
            'daily_average_7_days': str(spending_7_days / 7),
            'withdrawal_spending': debits.filter(
                category='withdrawal'
            ).aggregate(
                total=Sum(F('amount'))
            )['total'] or Decimal('0')
        }
    except Exception:
        return {}


def _check_withdrawal_limits(user, amount, tenant_id) -> bool:
    """Check if withdrawal amount is within limits."""
    try:
        limits = _get_user_withdrawal_limits(user, tenant_id)
        
        # Check daily limit
        daily_limit = limits.get('daily_limit', Decimal('1000'))
        daily_withdrawn = _get_daily_withdrawn(user, tenant_id)
        
        if daily_withdrawn + amount > daily_limit:
            return False
        
        # Check weekly limit
        weekly_limit = limits.get('weekly_limit', Decimal('5000'))
        weekly_withdrawn = _get_weekly_withdrawn(user, tenant_id)
        
        if weekly_withdrawn + amount > weekly_limit:
            return False
        
        # Check monthly limit
        monthly_limit = limits.get('monthly_limit', Decimal('10000'))
        monthly_withdrawn = _get_monthly_withdrawn(user, tenant_id)
        
        if monthly_withdrawn + amount > monthly_limit:
            return False
        
        return True
    except Exception:
        return False


def _get_user_withdrawal_limits(user, tenant_id) -> Dict:
    """Get user's withdrawal limits."""
    try:
        from wallet.models import WithdrawalLimit
        try:
            limits = WithdrawalLimit.objects.get(
                user=user,
                tenant_id=tenant_id
            )
            return {
                'daily_limit': limits.daily_limit,
                'weekly_limit': limits.weekly_limit,
                'monthly_limit': limits.monthly_limit,
                'min_amount': limits.min_amount,
                'max_amount': limits.max_amount,
                'fees': limits.fees
            }
        except WithdrawalLimit.DoesNotExist:
            # Return default limits
            from api.tasks.integration.shared_context import SharedContext
            ctx = SharedContext.for_user(user.id)
            
            if ctx.kyc_tier == 'full':
                return {
                    'daily_limit': Decimal('1000'),
                    'weekly_limit': Decimal('5000'),
                    'monthly_limit': Decimal('10000'),
                    'min_amount': Decimal('10'),
                    'max_amount': Decimal('5000'),
                    'fees': {'bank_transfer': Decimal('5.00'), 'paypal': Decimal('3.00')},
                }
            elif ctx.kyc_tier == 'standard':
                return {
                    'daily_limit': Decimal('500'),
                    'weekly_limit': Decimal('2000'),
                    'monthly_limit': Decimal('5000'),
                    'min_amount': Decimal('10'),
                    'max_amount': Decimal('1000'),
                    'fees': {'bank_transfer': Decimal('7.50'), 'paypal': Decimal('4.50')},
                }
            else:
                return {
                    'daily_limit': Decimal('100'),
                    'weekly_limit': Decimal('500'),
                    'monthly_limit': Decimal('1000'),
                    'min_amount': Decimal('10'),
                    'max_amount': Decimal('500'),
                    'fees': {'bank_transfer': Decimal('10.00'), 'paypal': Decimal('6.00')},
                }
    except Exception:
        return {}


def _get_daily_withdrawn(user, tenant_id) -> Decimal:
    """Get amount withdrawn today."""
    try:
        from wallet.models import WithdrawalRequest
        from django.utils import timezone
        from datetime import timedelta
        
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        return WithdrawalRequest.objects.filter(
            wallet__user=user,
            tenant_id=tenant_id,
            created_at__gte=today_start,
            status='completed'
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
    except Exception:
        return Decimal('0')


def _get_weekly_withdrawn(user, tenant_id) -> Decimal:
    """Get amount withdrawn this week."""
    try:
        from wallet.models import WithdrawalRequest
        from django.utils import timezone
        from datetime import timedelta
        
        week_start = timezone.now() - timedelta(days=timezone.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return WithdrawalRequest.objects.filter(
            wallet__user=user,
            tenant_id=tenant_id,
            created_at__gte=week_start,
            status='completed'
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
    except Exception:
        return Decimal('0')


def _get_monthly_withdrawn(user, tenant_id) -> Decimal:
    """Get amount withdrawn this month."""
    try:
        from wallet.models import WithdrawalRequest
        from django.utils import timezone
        from datetime import timedelta
        
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return WithdrawalRequest.objects.filter(
            wallet__user=user,
            tenant_id=tenant_id,
            created_at__gte=month_start,
            status='completed'
        ).aggregate(
            total=Sum(F('amount'))
        )['total'] or Decimal('0')
    except Exception:
        return Decimal('0')


def _get_withdrawal_processing_time(payment_method) -> str:
    """Get estimated processing time for payment method."""
    processing_times = {
        'bank_transfer': '2-3 business days',
        'paypal': '1-2 business days',
        'crypto': '1-6 hours',
        'wire_transfer': '3-5 business days'
    }
    return processing_times.get(payment_method, '2-3 business days')


def _get_user_currency(user, tenant_id) -> str:
    """Get user's preferred currency."""
    try:
        from wallet.models import Wallet
        wallet = Wallet.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).first()
        return wallet.currency if wallet else 'USD'
    except Exception:
        return 'USD'


def _is_method_available(payment_method, user, tenant_id) -> bool:
    """Check if payment method is available for user."""
    try:
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Check KYC requirements
        if payment_method.requirements.get('kyc_required', False):
            return ctx.kyc_tier == 'full'
        
        # Check user level
        min_level = payment_method.requirements.get('min_user_level', 1)
        if ctx.user_level < min_level:
            return False
        
        # Check account age
        min_age_days = payment_method.requirements.get('min_account_age_days', 0)
        if ctx.account_age_days < min_age_days:
            return False
        
        return True
    except Exception:
        return False


def _get_payment_method_setup_steps(payment_method, user_method) -> List[str]:
    """Get next steps for payment method setup."""
    steps = []
    
    if payment_method.method_type == 'bank_transfer':
        steps.extend([
            'Upload bank statement',
            'Verify bank account',
            'Confirm micro-deposits'
        ])
    elif payment_method.method_type == 'paypal':
        steps.extend([
            'Connect PayPal account',
            'Confirm email address',
            'Verify identity'
        ])
    elif payment_method.method_type == 'crypto':
        steps.extend([
            'Provide wallet address',
            'Verify ownership',
            'Complete test transaction'
        ])
    
    if user_method and user_method.verification_status == 'pending':
        steps.append('Complete verification process')
    
    return steps


def _get_transaction_trends(transactions, days) -> List[Dict]:
    """Get transaction trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = transactions.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            credit_count=Count('id', filter=Q(transaction_type='credit')),
            debit_count=Count('id', filter=Q(transaction_type='debit')),
            credit_amount=Sum(F('amount'), filter=Q(transaction_type='credit')),
            debit_amount=Sum(F('amount'), filter=Q(transaction_type='debit'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'credit_count': trend['credit_count'],
                'debit_count': trend['debit_count'],
                'credit_amount': str(trend['credit_amount'] or Decimal('0')),
                'debit_amount': str(trend['debit_amount'] or Decimal('0')),
                'net_amount': str((trend['credit_amount'] or Decimal('0')) - (trend['debit_amount'] or Decimal('0')))
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_withdrawal_trends(withdrawals, days) -> List[Dict]:
    """Get withdrawal trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = withdrawals.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            count=Count('id'),
            total_amount=Sum(F('amount')),
            total_fees=Sum(F('fees'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'withdrawal_count': trend['count'],
                'total_amount': str(trend['total_amount'] or Decimal('0')),
                'total_fees': str(trend['total_fees'] or Decimal('0')),
                'net_amount': str((trend['total_amount'] or Decimal('0')) - (trend['total_fees'] or Decimal('0')))
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_withdrawal_summary(queryset) -> Dict:
    """Get withdrawal summary statistics."""
    try:
        total_withdrawals = queryset.count()
        completed_withdrawals = queryset.filter(status='completed').count()
        
        return {
            'total_withdrawals': total_withdrawals,
            'completed_withdrawals': completed_withdrawals,
            'pending_withdrawals': queryset.filter(status='pending').count(),
            'processing_withdrawals': queryset.filter(status='processing').count(),
            'cancelled_withdrawals': queryset.filter(status='cancelled').count(),
            'rejected_withdrawals': queryset.filter(status='rejected').count(),
            'success_rate': round((completed_withdrawals / max(total_withdrawals, 1)) * 100, 2),
            'total_amount': queryset.filter(
                status='completed'
            ).aggregate(
                total=Sum(F('amount'))
            )['total'] or Decimal('0'),
            'total_fees': queryset.filter(
                status='completed'
            ).aggregate(
                total=Sum(F('fees'))
            )['total'] or Decimal('0'),
            'net_amount': queryset.filter(
                status='completed'
            ).aggregate(
                net=Sum(F('amount') - F('fees'))
            )['net'] or Decimal('0'),
            'average_amount': queryset.filter(
                status='completed'
            ).aggregate(
                avg_amount=Avg(F('amount'))
            )['avg_amount'] or Decimal('0')
        }
    except Exception:
        return {}
