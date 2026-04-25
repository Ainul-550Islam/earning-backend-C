"""
Advertiser Wallet ViewSet

ViewSet for advertiser wallet management,
including balance, deposits, and transaction history.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.db import transaction

from ..models.billing import AdvertiserWallet, AdvertiserDeposit, AdvertiserTransaction
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None
try:
    from ..services import AutoRefillService
except ImportError:
    AutoRefillService = None
from ..serializers import AdvertiserWalletSerializer, AdvertiserDepositSerializer, AdvertiserTransactionSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdvertiserWalletViewSet(viewsets.ModelViewSet):
    """
    ViewSet for advertiser wallet management.
    
    Handles balance inquiries, deposits, transactions,
    and auto-refill configuration.
    """
    
    queryset = AdvertiserWallet.objects.all()
    serializer_class = AdvertiserWalletSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all wallets
            return AdvertiserWallet.objects.all()
        else:
            # Advertisers can only see their own wallet
            return AdvertiserWallet.objects.filter(advertiser__user=user)
    
    def get_object(self):
        """Get wallet based on current user or pk."""
        pk = self.kwargs.get('pk')
        
        if pk:
            return get_object_or_404(self.get_queryset(), pk=pk)
        else:
            # Get current user's wallet
            try:
                return AdvertiserWallet.objects.get(advertiser__user=self.request.user)
            except AdvertiserWallet.DoesNotExist:
                return None
    
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """
        Get wallet balance information.
        
        Returns current balance, credit limit, and available funds.
        """
        try:
            billing_service = AdvertiserBillingService()
            balance_info = billing_service.get_wallet_balance(request.user.advertiser)
            
            return Response(balance_info)
            
        except Exception as e:
            logger.error(f"Error getting wallet balance: {e}")
            return Response(
                {'detail': 'Failed to get wallet balance'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def create_wallet(self, request):
        """
        Create advertiser wallet.
        
        Creates new wallet for the advertiser.
        """
        try:
            billing_service = AdvertiserBillingService()
            initial_balance = request.data.get('initial_balance', 0.00)
            
            wallet = billing_service.create_wallet(request.user.advertiser, initial_balance)
            
            serializer = self.get_serializer(wallet)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def deposit(self, request):
        """
        Process deposit to wallet.
        
        Handles payment processing and fund addition.
        """
        try:
            billing_service = AdvertiserBillingService()
            
            amount = request.data.get('amount')
            payment_method = request.data.get('payment_method')
            gateway = request.data.get('gateway')
            gateway_transaction_id = request.data.get('gateway_transaction_id')
            
            if not all([amount, payment_method, gateway]):
                return Response(
                    {'detail': 'Amount, payment method, and gateway are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            deposit = billing_service.process_deposit(
                request.user.advertiser,
                amount,
                payment_method,
                gateway,
                gateway_transaction_id
            )
            
            serializer = AdvertiserDepositSerializer(deposit)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error processing deposit: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def charge(self, request):
        """
        Charge wallet for services.
        
        Deducts funds for campaign spending or fees.
        """
        try:
            billing_service = AdvertiserBillingService()
            
            amount = request.data.get('amount')
            description = request.data.get('description')
            reference_id = request.data.get('reference_id')
            
            if not all([amount, description]):
                return Response(
                    {'detail': 'Amount and description are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            transaction = billing_service.charge_wallet(
                request.user.advertiser,
                amount,
                description,
                reference_id
            )
            
            serializer = AdvertiserTransactionSerializer(transaction)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error charging wallet: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def transaction_history(self, request):
        """
        Get transaction history.
        
        Returns list of wallet transactions with filtering.
        """
        try:
            billing_service = AdvertiserBillingService()
            
            filters = {}
            
            # Apply filters from query parameters
            transaction_type = request.query_params.get('transaction_type')
            status = request.query_params.get('status')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            min_amount = request.query_params.get('min_amount')
            max_amount = request.query_params.get('max_amount')
            
            if transaction_type:
                filters['transaction_type'] = transaction_type
            if status:
                filters['status'] = status
            if date_from:
                filters['date_from'] = date_from
            if date_to:
                filters['date_to'] = date_to
            if min_amount:
                filters['min_amount'] = float(min_amount)
            if max_amount:
                filters['max_amount'] = float(max_amount)
            
            transactions = billing_service.get_transaction_history(request.user.advertiser, filters)
            
            serializer = AdvertiserTransactionSerializer(transactions, many=True)
            
            return Response({
                'transactions': serializer.data,
                'count': len(transactions),
                'filters': filters
            })
            
        except Exception as e:
            logger.error(f"Error getting transaction history: {e}")
            return Response(
                {'detail': 'Failed to get transaction history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def deposit_history(self, request):
        """
        Get deposit history.
        
        Returns list of deposits with filtering.
        """
        try:
            billing_service = AdvertiserBillingService()
            
            filters = {}
            
            # Apply filters from query parameters
            status = request.query_params.get('status')
            gateway = request.query_params.get('gateway')
            payment_method = request.query_params.get('payment_method')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            min_amount = request.query_params.get('min_amount')
            max_amount = request.query_params.get('max_amount')
            
            if status:
                filters['status'] = status
            if gateway:
                filters['gateway'] = gateway
            if payment_method:
                filters['payment_method'] = payment_method
            if date_from:
                filters['date_from'] = date_from
            if date_to:
                filters['date_to'] = date_to
            if min_amount:
                filters['min_amount'] = float(min_amount)
            if max_amount:
                filters['max_amount'] = float(max_amount)
            
            deposits = billing_service.get_deposit_history(request.user.advertiser, filters)
            
            serializer = AdvertiserDepositSerializer(deposits, many=True)
            
            return Response({
                'deposits': serializer.data,
                'count': len(deposits),
                'filters': filters
            })
            
        except Exception as e:
            logger.error(f"Error getting deposit history: {e}")
            return Response(
                {'detail': 'Failed to get deposit history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def billing_summary(self, request):
        """
        Get billing summary.
        
        Returns comprehensive financial overview.
        """
        try:
            days = int(request.query_params.get('days', 30))
            billing_service = AdvertiserBillingService()
            
            summary = billing_service.get_billing_summary(request.user.advertiser, days)
            
            return Response(summary)
            
        except Exception as e:
            logger.error(f"Error getting billing summary: {e}")
            return Response(
                {'detail': 'Failed to get billing summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def configure_auto_refill(self, request):
        """
        Configure auto-refill settings.
        
        Sets up automatic wallet refilling.
        """
        try:
            refill_service = AutoRefillService()
            
            config = {
                'enabled': request.data.get('enabled', False),
                'threshold': request.data.get('threshold', 0.00),
                'amount': request.data.get('amount', 0.00),
                'max_amount': request.data.get('max_amount'),
                'payment_method': request.data.get('payment_method', 'credit_card'),
                'payment_token': request.data.get('payment_token'),
                'billing_address': request.data.get('billing_address'),
            }
            
            result = refill_service.configure_auto_refill(request.user.advertiser, config)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error configuring auto-refill: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def auto_refill_status(self, request):
        """
        Get auto-refill status.
        
        Returns current auto-refill configuration and status.
        """
        try:
            refill_service = AutoRefillService()
            status_info = refill_service.get_auto_refill_status(request.user.advertiser)
            
            return Response(status_info)
            
        except Exception as e:
            logger.error(f"Error getting auto-refill status: {e}")
            return Response(
                {'detail': 'Failed to get auto-refill status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def manual_refill(self, request):
        """
        Process manual refill.
        
        Manually trigger wallet refill.
        """
        try:
            refill_service = AutoRefillService()
            
            amount = request.data.get('amount')
            payment_method = request.data.get('payment_method')
            payment_details = request.data.get('payment_details', {})
            
            if not all([amount, payment_method]):
                return Response(
                    {'detail': 'Amount and payment method are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            result = refill_service.process_manual_refill(
                request.user.advertiser,
                amount,
                payment_method,
                payment_details
            )
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error processing manual refill: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def disable_auto_refill(self, request):
        """
        Disable auto-refill.
        
        Turns off automatic wallet refilling.
        """
        try:
            refill_service = AutoRefillService()
            result = refill_service.disable_auto_refill(request.user.advertiser)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error disabling auto-refill: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def refill_history(self, request):
        """
        Get refill history.
        
        Returns list of auto-refill events.
        """
        try:
            limit = int(request.query_params.get('limit', 50))
            refill_service = AutoRefillService()
            
            history = refill_service.get_refill_history(request.user.advertiser, limit)
            
            return Response({
                'refills': history,
                'count': len(history)
            })
            
        except Exception as e:
            logger.error(f"Error getting refill history: {e}")
            return Response(
                {'detail': 'Failed to get refill history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def payment_methods(self, request):
        """
        Get available payment methods.
        
        Returns list of supported payment options.
        """
        try:
            payment_methods = {
                'credit_card': {
                    'name': 'Credit Card',
                    'description': 'Pay with credit or debit card',
                    'processing_fee': '2.9% + $0.30',
                    'supported_gateways': ['stripe', 'paypal', 'square'],
                },
                'paypal': {
                    'name': 'PayPal',
                    'description': 'Pay with PayPal account',
                    'processing_fee': '3.4% + $0.30',
                    'supported_gateways': ['paypal'],
                },
                'bank_transfer': {
                    'name': 'Bank Transfer',
                    'description': 'Direct bank transfer',
                    'processing_fee': '1% (min $5.00)',
                    'supported_gateways': ['plaid', 'dwolla'],
                },
                'crypto': {
                    'name': 'Cryptocurrency',
                    'description': 'Pay with cryptocurrency',
                    'processing_fee': '1.5%',
                    'supported_gateways': ['coinbase', 'bitpay'],
                },
            }
            
            return Response(payment_methods)
            
        except Exception as e:
            logger.error(f"Error getting payment methods: {e}")
            return Response(
                {'detail': 'Failed to get payment methods'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def currencies(self, request):
        """
        Get supported currencies.
        
        Returns list of supported currency codes.
        """
        try:
            currencies = {
                'USD': {
                    'name': 'US Dollar',
                    'symbol': '$',
                    'code': 'USD',
                    'decimal_places': 2,
                },
                'EUR': {
                    'name': 'Euro',
                    'symbol': 'EUR',
                    'code': 'EUR',
                    'decimal_places': 2,
                },
                'GBP': {
                    'name': 'British Pound',
                    'symbol': '£',
                    'code': 'GBP',
                    'decimal_places': 2,
                },
                'CAD': {
                    'name': 'Canadian Dollar',
                    'symbol': 'C$',
                    'code': 'CAD',
                    'decimal_places': 2,
                },
                'AUD': {
                    'name': 'Australian Dollar',
                    'symbol': 'A$',
                    'code': 'AUD',
                    'decimal_places': 2,
                },
                'JPY': {
                    'name': 'Japanese Yen',
                    'symbol': '¥',
                    'code': 'JPY',
                    'decimal_places': 0,
                },
            }
            
            return Response(currencies)
            
        except Exception as e:
            logger.error(f"Error getting currencies: {e}")
            return Response(
                {'detail': 'Failed to get currencies'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_deposit_config(self, request):
        """
        Validate deposit configuration.
        
        Checks deposit parameters for validity.
        """
        config = request.data.get('config', {})
        
        if not config:
            return Response(
                {'detail': 'No configuration provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            validation_results = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'recommendations': [],
            }
            
            # Check amount
            amount = config.get('amount')
            if amount is None:
                validation_results['errors'].append('Amount is required')
                validation_results['is_valid'] = False
            elif amount <= 0:
                validation_results['errors'].append('Amount must be positive')
                validation_results['is_valid'] = False
            elif amount < 5.00:
                validation_results['warnings'].append('Very small deposit amounts may not be cost-effective')
            elif amount > 10000.00:
                validation_results['warnings'].append('Large deposit amounts may require additional verification')
            
            # Check payment method
            payment_method = config.get('payment_method')
            if not payment_method:
                validation_results['errors'].append('Payment method is required')
                validation_results['is_valid'] = False
            else:
                valid_methods = ['credit_card', 'paypal', 'bank_transfer', 'crypto']
                if payment_method not in valid_methods:
                    validation_results['errors'].append(f'Invalid payment method: {payment_method}')
                    validation_results['is_valid'] = False
            
            # Check gateway
            gateway = config.get('gateway')
            if not gateway:
                validation_results['errors'].append('Payment gateway is required')
                validation_results['is_valid'] = False
            
            # Generate recommendations
            if validation_results['is_valid']:
                if not config.get('gateway_transaction_id'):
                    validation_results['recommendations'].append('Consider providing a transaction ID for tracking')
                
                if amount > 1000.00 and payment_method == 'credit_card':
                    validation_results['recommendations'].append('Consider using bank transfer for large amounts')
            
            return Response(validation_results)
            
        except Exception as e:
            logger.error(f"Error validating deposit config: {e}")
            return Response(
                {'detail': 'Failed to validate configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_auto_refill_config(self, request):
        """
        Validate auto-refill configuration.
        
        Checks auto-refill parameters for validity.
        """
        config = request.data.get('config', {})
        
        if not config:
            return Response(
                {'detail': 'No configuration provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            validation_results = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'recommendations': [],
            }
            
            # Check threshold
            threshold = config.get('threshold')
            if threshold is None:
                validation_results['errors'].append('Threshold is required')
                validation_results['is_valid'] = False
            elif threshold <= 0:
                validation_results['errors'].append('Threshold must be positive')
                validation_results['is_valid'] = False
            elif threshold < 10.00:
                validation_results['warnings'].append('Very low threshold may trigger frequent refills')
            elif threshold > 1000.00:
                validation_results['warnings'].append('Very high threshold may leave insufficient funds')
            
            # Check amount
            amount = config.get('amount')
            if amount is None:
                validation_results['errors'].append('Refill amount is required')
                validation_results['is_valid'] = False
            elif amount <= 0:
                validation_results['errors'].append('Refill amount must be positive')
                validation_results['is_valid'] = False
            elif amount < threshold:
                validation_results['errors'].append('Refill amount must be greater than threshold')
                validation_results['is_valid'] = False
            elif amount > 5000.00:
                validation_results['warnings'].append('Large refill amounts may require additional verification')
            
            # Check max amount
            max_amount = config.get('max_amount')
            if max_amount is not None and max_amount <= 0:
                validation_results['errors'].append('Maximum amount must be positive')
                validation_results['is_valid'] = False
            
            # Check payment method
            payment_method = config.get('payment_method')
            if not payment_method:
                validation_results['errors'].append('Payment method is required')
                validation_results['is_valid'] = False
            else:
                valid_methods = ['credit_card', 'paypal', 'bank_transfer']
                if payment_method not in valid_methods:
                    validation_results['errors'].append(f'Invalid payment method: {payment_method}')
                    validation_results['is_valid'] = False
            
            # Generate recommendations
            if validation_results['is_valid']:
                if not config.get('payment_token'):
                    validation_results['recommendations'].append('Payment token is required for auto-refill')
                
                if not config.get('max_amount'):
                    validation_results['recommendations'].append('Consider setting a maximum refill amount to prevent overspending')
                
                if threshold > amount * 0.5:
                    validation_results['recommendations'].append('Consider setting a lower threshold for better fund availability')
            
            return Response(validation_results)
            
        except Exception as e:
            logger.error(f"Error validating auto-refill config: {e}")
            return Response(
                {'detail': 'Failed to validate configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        advertiser_id = request.query_params.get('advertiser_id')
        is_active = request.query_params.get('is_active')
        is_suspended = request.query_params.get('is_suspended')
        auto_refill_enabled = request.query_params.get('auto_refill_enabled')
        search = request.query_params.get('search')
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if is_suspended is not None:
            queryset = queryset.filter(is_suspended=is_suspended.lower() == 'true')
        
        if auto_refill_enabled is not None:
            queryset = queryset.filter(auto_refill_enabled=auto_refill_enabled.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(advertiser__company_name__icontains=search) |
                Q(advertiser__contact_email__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
