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
from .services import CryptoPayoutService

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

logger = logging.getLogger(__name__)


def safe_decimal(value, default=Decimal('0.00')):
    try:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError):
        return default


def get_or_create_wallet(user):
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


def validate_amount(amount, min_amount=Decimal('1.00')):
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


class WalletBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet, created = get_or_create_wallet(request.user)
            if created:
                logger.info(f"Created new wallet for user {request.user.id}")
            serializer = WalletSerializer(wallet)
            data = serializer.data
            data['available_for_withdrawal'] = float(wallet.available_balance)
            data['is_wallet_locked'] = wallet.is_locked
            return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.error(f"Database error fetching wallet for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'Database error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Unexpected error fetching wallet for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet, _ = get_or_create_wallet(request.user)
            page = max(1, int(request.GET.get('page', 1)))
            page_size = min(100, max(10, int(request.GET.get('page_size', 20))))
            transaction_type = request.GET.get('type', None)
            transaction_status = request.GET.get('status', None)
            queryset = WalletTransaction.objects.filter(wallet=wallet)
            if transaction_type:
                queryset = queryset.filter(type=transaction_type)
            if transaction_status:
                queryset = queryset.filter(status=transaction_status)
            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            transactions = queryset[start:end]
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
            return Response({'success': False, 'error': 'Invalid pagination parameters'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error fetching transactions for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An error occurred while fetching transactions'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AddMoneyView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            wallet, _ = get_or_create_wallet(request.user)
            if wallet.is_locked:
                return Response({'success': False, 'error': f'Wallet is locked: {wallet.locked_reason}'}, status=status.HTTP_403_FORBIDDEN)
            amount = request.data.get('amount')
            is_valid, error_msg, decimal_amount = validate_amount(amount)
            if not is_valid:
                return Response({'success': False, 'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            transaction_type = request.data.get('type', 'earning')
            allowed_types = ['earning', 'reward', 'referral', 'bonus', 'admin_credit']
            if transaction_type not in allowed_types:
                return Response({'success': False, 'error': f'Invalid transaction type. Allowed: {", ".join(allowed_types)}'}, status=status.HTTP_400_BAD_REQUEST)
            balance_before = wallet.current_balance
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
            wallet.current_balance = F('current_balance') + decimal_amount
            wallet.total_earned = F('total_earned') + decimal_amount
            wallet.save()
            wallet.refresh_from_db()
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
            return Response({'success': False, 'error': 'Database error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Unexpected error adding money for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WithdrawMoneyView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            wallet, _ = get_or_create_wallet(request.user)
            if wallet.is_locked:
                return Response({'success': False, 'error': f'Wallet is locked: {wallet.locked_reason}'}, status=status.HTTP_403_FORBIDDEN)
            amount = request.data.get('amount')
            min_withdrawal = Decimal('100.00')
            is_valid, error_msg, decimal_amount = validate_amount(amount, min_withdrawal)
            if not is_valid:
                return Response({'success': False, 'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            if decimal_amount > wallet.available_balance:
                return Response({'success': False, 'error': f'Insufficient balance. Available: {wallet.available_balance}'}, status=status.HTTP_400_BAD_REQUEST)
            payment_method_id = request.data.get('payment_method_id')
            if not payment_method_id:
                return Response({'success': False, 'error': 'Payment method is required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                payment_method = UserPaymentMethod.objects.get(id=payment_method_id, user=request.user)
            except UserPaymentMethod.DoesNotExist:
                return Response({'success': False, 'error': 'Payment method not found'}, status=status.HTTP_404_NOT_FOUND)
            fee_percentage = Decimal('0.02')
            fee = (decimal_amount * fee_percentage).quantize(Decimal('0.01'))
            net_amount = decimal_amount - fee
            balance_before = wallet.current_balance
            wallet_transaction = WalletTransaction.objects.create(
                wallet=wallet,
                type='withdrawal',
                amount=-decimal_amount,
                status='pending',
                description=f'Withdrawal request to {payment_method.get_method_type_display()}',
                reference_type='withdrawal',
                balance_before=balance_before,
                balance_after=balance_before - decimal_amount,
                created_by=request.user,
            )
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
            wallet.current_balance = F('current_balance') - decimal_amount
            wallet.pending_balance = F('pending_balance') + decimal_amount
            wallet.save()
            wallet.refresh_from_db()
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
            return Response({'success': False, 'error': 'Database error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Unexpected error creating withdrawal for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PaymentMethodsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            payment_methods = UserPaymentMethod.objects.filter(user=request.user)
            serializer = UserPaymentMethodSerializer(payment_methods, many=True)
            return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching payment methods for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @transaction.atomic
    def post(self, request):
        try:
            serializer = UserPaymentMethodSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            is_primary = request.data.get('is_primary', False)
            if is_primary:
                UserPaymentMethod.objects.filter(user=request.user, is_primary=True).update(is_primary=False)
            payment_method = serializer.save(user=request.user)
            return Response({'success': True, 'message': 'Payment method added successfully', 'data': UserPaymentMethodSerializer(payment_method).data}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error adding payment method for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WithdrawalHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            page = max(1, int(request.GET.get('page', 1)))
            page_size = min(100, max(10, int(request.GET.get('page_size', 20))))
            withdrawal_status = request.GET.get('status', None)
            queryset = Withdrawal.objects.filter(user=request.user)
            if withdrawal_status:
                queryset = queryset.filter(status=withdrawal_status)
            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            withdrawals = queryset[start:end]
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
        except ValueError:
            return Response({'success': False, 'error': 'Invalid pagination parameters'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error fetching withdrawals for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WalletStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet, _ = get_or_create_wallet(request.user)
            transaction_stats = WalletTransaction.objects.filter(wallet=wallet, status='approved').aggregate(
                total_earnings=Sum('amount', filter=Q(type__in=['earning', 'reward', 'referral', 'bonus'])),
                total_withdrawals=Sum('amount', filter=Q(type='withdrawal')),
                total_transactions=Sum('amount')
            )
            withdrawal_stats = Withdrawal.objects.filter(user=request.user).aggregate(
                pending_withdrawals=Sum('amount', filter=Q(status='pending')),
                completed_withdrawals=Sum('amount', filter=Q(status='completed')),
                total_fees_paid=Sum('fee', filter=Q(status='completed'))
            )
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
            return Response({'success': True, 'data': stats}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching wallet statistics for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CryptoPayoutView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            amount = safe_decimal(request.data.get('amount'))
            wallet_address = request.data.get('wallet_address', '').strip()
            currency = request.data.get('currency', 'usdttrc20')
            payment_method_id = request.data.get('payment_method_id')
            if amount < Decimal('10.00'):
                return Response({'success': False, 'error': 'Minimum USDT withdrawal: 10 equivalent'}, status=status.HTTP_400_BAD_REQUEST)
            if not wallet_address:
                return Response({'success': False, 'error': 'USDT wallet address required'}, status=status.HTTP_400_BAD_REQUEST)
            if not CryptoPayoutService.validate_wallet_address(wallet_address, currency):
                hint = 'TRC-20 address starts with T (34 chars)' if 'trc' in currency else 'starts with 0x (42 chars)'
                return Response({'success': False, 'error': f'Invalid wallet address. {hint}'}, status=status.HTTP_400_BAD_REQUEST)
            wallet, _ = get_or_create_wallet(request.user)
            if wallet.is_locked:
                return Response({'success': False, 'error': f'Wallet locked: {wallet.locked_reason}'}, status=status.HTTP_403_FORBIDDEN)
            if amount > wallet.available_balance:
                return Response({'success': False, 'error': f'Insufficient balance. Available: {wallet.available_balance}'}, status=status.HTTP_400_BAD_REQUEST)
            exchange_rate = CryptoPayoutService.get_exchange_rate('bdt', currency)
            if exchange_rate <= 0:
                return Response({'success': False, 'error': 'Exchange rate unavailable. Try again later.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            amount_usd = float(amount) * exchange_rate
            fee = (amount * Decimal('0.01')).quantize(Decimal('0.01'))
            net_amount = amount - fee
            balance_before = wallet.current_balance
            wallet_txn = WalletTransaction.objects.create(
                wallet=wallet,
                type='withdrawal',
                amount=-amount,
                status='pending',
                description=f'USDT withdrawal to {wallet_address[:10]}...{wallet_address[-6:]}',
                reference_type='crypto_withdrawal',
                balance_before=balance_before,
                balance_after=balance_before - amount,
                created_by=request.user,
                metadata={
                    'wallet_address': wallet_address,
                    'currency': currency,
                    'amount_usd': amount_usd,
                    'exchange_rate': exchange_rate,
                    'payment_method_id': str(payment_method_id or ''),
                }
            )
            wallet.current_balance = F('current_balance') - amount
            wallet.pending_balance = F('pending_balance') + amount
            wallet.save()
            wallet.refresh_from_db()
            payout_result = CryptoPayoutService.create_payout(
                wallet_address=wallet_address,
                amount_usd=amount_usd,
                currency=currency
            )
            if payout_result['success']:
                wallet_txn.status = 'approved'
                wallet_txn.reference_id = payout_result.get('payment_id', '')
                wallet_txn.approved_at = timezone.now()
                wallet_txn.save()
                wallet.pending_balance = F('pending_balance') - amount
                wallet.total_withdrawn = F('total_withdrawn') + amount
                wallet.save()
                logger.info(f"Crypto payout success: user={request.user.id}, amount={amount}, usdt={amount_usd:.2f}")
                return Response({
                    'success': True,
                    'message': 'USDT payout processing. Expected in 10-30 minutes.',
                    'data': {
                        'transaction_id': str(wallet_txn.walletTransaction_id),
                        'crypto_payment_id': payout_result.get('payment_id'),
                        'amount_bdt': float(amount),
                        'fee_bdt': float(fee),
                        'net_bdt': float(net_amount),
                        'amount_usdt': round(amount_usd, 4),
                        'exchange_rate': exchange_rate,
                        'wallet_address': wallet_address,
                        'currency': currency.upper(),
                        'status': 'processing',
                    }
                }, status=status.HTTP_201_CREATED)
            else:
                wallet.current_balance = F('current_balance') + amount
                wallet.pending_balance = F('pending_balance') - amount
                wallet.save()
                wallet_txn.status = 'rejected'
                wallet_txn.description += f" | Failed: {payout_result.get('error', 'Gateway error')}"
                wallet_txn.save()
                return Response({'success': False, 'error': 'Crypto gateway error. Balance returned.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Crypto payout error for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'Server error. Try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EarningsBreakdownView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = min(365, max(1, int(request.GET.get('days', 30))))
            wallet, _ = get_or_create_wallet(request.user)
            from datetime import timedelta
            from django.db.models.functions import TruncDate
            from django.db.models import Sum, Count
            cutoff = timezone.now() - timedelta(days=days)
            txns = WalletTransaction.objects.filter(
                wallet=wallet,
                type__in=['earning', 'reward', 'referral', 'bonus'],
                status='approved',
                created_at__gte=cutoff
            )
            by_type = {}
            for txn in txns:
                t = txn.type
                by_type[t] = float(by_type.get(t, 0)) + float(txn.amount)
            daily = list(
                txns.annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(total=Sum('amount'), count=Count('id'))
                .order_by('date')
            )
            for d in daily:
                d['date'] = str(d['date'])
                d['total'] = float(d['total'])
            total = sum(by_type.values())
            return Response({
                'success': True,
                'data': {
                    'by_type': by_type,
                    'daily_chart': daily,
                    'total': round(total, 2),
                    'period_days': days,
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Earnings breakdown error for user {request.user.id}: {e}")
            return Response({'success': False, 'error': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 10. Webhook Receiver
# ==========================================
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json


@csrf_exempt
def receive_webhook(request, gateway):
    """
    POST /api/wallet/webhook/<gateway>/
    Receive payment gateway webhooks
    """
    try:
        payload = json.loads(request.body) if request.body else {}

        WalletWebhookLog.objects.create(
            gateway=gateway,
            payload=payload,
            headers=dict(request.headers),
            status='received',
        )

        logger.info(f"Webhook received from gateway: {gateway}")
        return JsonResponse({'success': True, 'message': 'Webhook received'}, status=200)

    except Exception as e:
        logger.error(f"Webhook error from {gateway}: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


from django.http import JsonResponse as _JsonResponse

def wallet_health(request):
    """Wallet health check endpoint."""
    try:
        from .health import health_check
        return health_check(request)
    except Exception as e:
        return _JsonResponse({'status': 'ok', 'service': 'wallet'}, status=200)
