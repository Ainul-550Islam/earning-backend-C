"""
api/adapters/payment_gateways.py
Payment gateway adapters for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_methods(request):
    """Get available payment methods for user."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user context for payment eligibility
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        payment_methods = {
            'available_methods': [
                {
                    'id': 'paypal',
                    'name': 'PayPal',
                    'icon': 'paypal-icon.png',
                    'enabled': True,
                    'min_amount': '1.00',
                    'max_amount': '10000.00',
                    'currency': 'USD',
                    'fees': {
                        'percentage': 2.9,
                        'fixed': '0.30'
                    },
                    'processing_time': '1-3 business days'
                },
                {
                    'id': 'stripe',
                    'name': 'Stripe',
                    'icon': 'stripe-icon.png',
                    'enabled': True,
                    'min_amount': '1.00',
                    'max_amount': '10000.00',
                    'currency': 'USD',
                    'fees': {
                        'percentage': 2.9,
                        'fixed': '0.30'
                    },
                    'processing_time': '1-2 business days'
                },
                {
                    'id': 'crypto',
                    'name': 'Cryptocurrency',
                    'icon': 'crypto-icon.png',
                    'enabled': ctx.is_eligible_for_payout,
                    'min_amount': '10.00',
                    'max_amount': '50000.00',
                    'currency': 'USD',
                    'fees': {
                        'percentage': 1.5,
                        'fixed': '0.00'
                    },
                    'processing_time': '1-24 hours'
                },
                {
                    'id': 'wire_transfer',
                    'name': 'Wire Transfer',
                    'icon': 'wire-icon.png',
                    'enabled': ctx.is_eligible_for_payout,
                    'min_amount': '100.00',
                    'max_amount': '100000.00',
                    'currency': 'USD',
                    'fees': {
                        'percentage': 0.0,
                        'fixed': '25.00'
                    },
                    'processing_time': '2-5 business days'
                }
            ],
            'preferred_method': ctx.preferred_payment_method,
            'kyc_restrictions': {
                'paypal': ctx.kyc_tier in ['standard', 'full'],
                'stripe': ctx.kyc_tier in ['standard', 'full'],
                'crypto': ctx.kyc_tier == 'full',
                'wire_transfer': ctx.kyc_tier in ['standard', 'full']
            },
            'tenant_id': tenant_id
        }
        
        return Response({
            'success': True,
            'data': payment_methods,
            'message': 'Payment methods retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PaymentGateway] Error getting payment methods: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve payment methods',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_withdrawal(request):
    """Create withdrawal request."""
    try:
        user = request.user
        data = request.data
        
        # Validate withdrawal data
        amount = Decimal(str(data.get('amount', '0')))
        payment_method = data.get('payment_method')
        
        if amount <= 0:
            return Response({
                'success': False,
                'error': 'Invalid amount',
                'details': 'Amount must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not payment_method:
            return Response({
                'success': False,
                'error': 'Payment method required',
                'details': 'Please select a payment method'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check user eligibility
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if not ctx.is_eligible_for_payout:
            return Response({
                'success': False,
                'error': 'Not eligible for withdrawal',
                'details': 'Complete KYC verification to enable withdrawals'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if amount > ctx.withdrawal_limit:
            return Response({
                'success': False,
                'error': 'Amount exceeds limit',
                'details': f'Maximum withdrawal amount is ${ctx.withdrawal_limit}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check minimum withdrawal
        min_amount = Decimal('10.00')
        if amount < min_amount:
            return Response({
                'success': False,
                'error': 'Amount below minimum',
                'details': f'Minimum withdrawal amount is ${min_amount}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create withdrawal request
        from wallet.models import WithdrawalRequest
        withdrawal = WithdrawalRequest.objects.create(
            user=user,
            amount=amount,
            payment_method=payment_method,
            status='pending',
            tenant_id=getattr(request, 'tenant_id', None),
            metadata=data.get('metadata', {}),
            created_at=timezone.now()
        )
        
        # Emit withdrawal event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('payment.withdrawal_requested', {
            'user_id': user.id,
            'withdrawal_id': withdrawal.id,
            'amount': str(amount),
            'payment_method': payment_method,
            'tenant_id': getattr(request, 'tenant_id', None)
        })
        
        return Response({
            'success': True,
            'data': {
                'withdrawal_id': withdrawal.id,
                'amount': str(amount),
                'payment_method': payment_method,
                'status': 'pending',
                'estimated_processing': '2-5 business days'
            },
            'message': 'Withdrawal request created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[PaymentGateway] Error creating withdrawal: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create withdrawal request',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def withdrawal_history(request):
    """Get user withdrawal history."""
    try:
        user = request.user
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        # Get withdrawal requests
        from wallet.models import WithdrawalRequest
        withdrawals = WithdrawalRequest.objects.filter(
            user=user,
            tenant_id=getattr(request, 'tenant_id', None)
        ).order_by('-created_at')[offset:offset+limit]
        
        withdrawal_data = {
            'withdrawals': [
                {
                    'id': withdrawal.id,
                    'amount': str(withdrawal.amount),
                    'payment_method': withdrawal.payment_method,
                    'status': withdrawal.status,
                    'created_at': withdrawal.created_at.isoformat(),
                    'processed_at': withdrawal.processed_at.isoformat() if withdrawal.processed_at else None,
                    'transaction_id': withdrawal.transaction_id,
                    'fees': str(withdrawal.fees) if withdrawal.fees else '0.00',
                    'metadata': withdrawal.metadata
                }
                for withdrawal in withdrawals
            ],
            'pagination': {
                'limit': limit,
                'offset': offset,
                'total': WithdrawalRequest.objects.filter(user=user).count(),
                'has_more': len(withdrawals) == limit
            }
        }
        
        return Response({
            'success': True,
            'data': withdrawal_data,
            'message': 'Withdrawal history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PaymentGateway] Error getting withdrawal history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve withdrawal history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transaction_history(request):
    """Get user transaction history."""
    try:
        user = request.user
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        # Get transactions
        from wallet.models import WalletTransaction
        transactions = WalletTransaction.objects.filter(
            user=user,
            tenant_id=getattr(request, 'tenant_id', None)
        ).order_by('-created_at')[offset:offset+limit]
        
        transaction_data = {
            'transactions': [
                {
                    'id': transaction.id,
                    'type': transaction.transaction_type,
                    'amount': str(transaction.amount),
                    'balance_after': str(transaction.balance_after),
                    'reference': transaction.reference,
                    'description': transaction.description,
                    'created_at': transaction.created_at.isoformat(),
                    'metadata': transaction.metadata
                }
                for transaction in transactions
            ],
            'pagination': {
                'limit': limit,
                'offset': offset,
                'total': WalletTransaction.objects.filter(user=user).count(),
                'has_more': len(transactions) == limit
            }
        }
        
        return Response({
            'success': True,
            'data': transaction_data,
            'message': 'Transaction history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PaymentGateway] Error getting transaction history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve transaction history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_payment_method(request):
    """Update user's preferred payment method."""
    try:
        user = request.user
        data = request.data
        
        payment_method = data.get('payment_method')
        if not payment_method:
            return Response({
                'success': False,
                'error': 'Payment method required',
                'details': 'Please select a payment method'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update user's preferred payment method
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        ctx.set('payment_method', payment_method, ttl=86400)  # Cache for 24 hours
        
        # Log payment method update
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('user.payment_method_updated', {
            'user_id': user.id,
            'old_method': ctx.preferred_payment_method,
            'new_method': payment_method,
            'tenant_id': getattr(request, 'tenant_id', None)
        })
        
        return Response({
            'success': True,
            'data': {'payment_method': payment_method},
            'message': 'Payment method updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PaymentGateway] Error updating payment method: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update payment method',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
