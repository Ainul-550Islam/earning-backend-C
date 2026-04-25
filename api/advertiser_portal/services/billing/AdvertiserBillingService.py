"""
Advertiser Billing Service

Service for managing advertiser billing operations,
including deposits, charges, and invoice management.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.billing import AdvertiserWallet, AdvertiserDeposit, AdvertiserInvoice, AdvertiserTransaction
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserBillingService:
    """
    Service for managing advertiser billing operations.
    
    Handles deposits, charges, invoices, and
    financial transactions.
    """
    
    def __init__(self):
        self.logger = logger
    
    def create_wallet(self, advertiser, initial_balance: float = 0.00) -> AdvertiserWallet:
        """
        Create advertiser wallet.
        
        Args:
            advertiser: Advertiser instance
            initial_balance: Initial wallet balance
            
        Returns:
            AdvertiserWallet: Created wallet instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Check if wallet already exists
                if hasattr(advertiser, 'wallet'):
                    raise ValidationError("Advertiser already has a wallet")
                
                # Create wallet
                wallet = AdvertiserWallet.objects.create(
                    advertiser=advertiser,
                    balance=initial_balance,
                    credit_limit=0.00,
                    available_credit=0.00,
                    auto_refill_enabled=False,
                    auto_refill_threshold=0.00,
                    auto_refill_amount=0.00,
                    auto_refill_max=None,
                    default_payment_method='credit_card',
                    is_active=True,
                    is_suspended=False,
                    daily_spend_limit=None,
                    weekly_spend_limit=None,
                    monthly_spend_limit=None,
                    currency='USD',
                )
                
                self.logger.info(f"Created wallet for {advertiser.company_name}")
                return wallet
                
        except Exception as e:
            self.logger.error(f"Error creating wallet: {e}")
            raise ValidationError(f"Failed to create wallet: {str(e)}")
    
    def process_deposit(self, advertiser, amount: float, payment_method: str, gateway: str, gateway_transaction_id: str = None) -> AdvertiserDeposit:
        """
        Process deposit to advertiser wallet.
        
        Args:
            advertiser: Advertiser instance
            amount: Deposit amount
            payment_method: Payment method
            gateway: Payment gateway
            gateway_transaction_id: Gateway transaction ID
            
        Returns:
            AdvertiserDeposit: Created deposit instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate amount
                if amount <= 0:
                    raise ValidationError("Deposit amount must be positive")
                
                # Get or create wallet
                wallet, created = AdvertiserWallet.objects.get_or_create(
                    advertiser=advertiser,
                    defaults={
                        'balance': 0.00,
                        'credit_limit': 0.00,
                        'available_credit': 0.00,
                        'currency': 'USD',
                    }
                )
                
                # Calculate processing fee
                processing_fee = self._calculate_processing_fee(amount, payment_method)
                net_amount = amount - processing_fee
                
                # Create deposit record
                deposit = AdvertiserDeposit.objects.create(
                    advertiser=advertiser,
                    amount=amount,
                    currency='USD',
                    gateway=gateway,
                    payment_method=payment_method,
                    gateway_transaction_id=gateway_transaction_id,
                    status='completed',
                    processing_fee=processing_fee,
                    net_amount=net_amount,
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                    completed_at=timezone.now(),
                )
                
                # Add funds to wallet
                wallet.add_funds(net_amount, f"Deposit via {gateway}")
                
                # Send notification
                self._send_deposit_notification(advertiser, deposit)
                
                self.logger.info(f"Processed deposit: ${amount:.2f} for {advertiser.company_name}")
                return deposit
                
        except Exception as e:
            self.logger.error(f"Error processing deposit: {e}")
            raise ValidationError(f"Failed to process deposit: {str(e)}")
    
    def charge_wallet(self, advertiser, amount: float, description: str, reference_id: str = None) -> AdvertiserTransaction:
        """
        Charge advertiser wallet.
        
        Args:
            advertiser: Advertiser instance
            amount: Amount to charge
            description: Charge description
            reference_id: Reference ID
            
        Returns:
            AdvertiserTransaction: Created transaction instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate amount
                if amount <= 0:
                    raise ValidationError("Charge amount must be positive")
                
                # Get wallet
                try:
                    wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
                except AdvertiserWallet.DoesNotExist:
                    raise ValidationError("Advertiser wallet not found")
                
                # Check if wallet is suspended
                if wallet.is_suspended:
                    raise ValidationError("Wallet is suspended")
                
                # Check available balance
                if not wallet.spend_funds(amount, description):
                    raise ValidationError("Insufficient balance")
                
                # Create transaction record
                transaction = AdvertiserTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='spend',
                    amount=amount,
                    description=description,
                    reference_id=reference_id,
                    status='completed',
                    balance_before=wallet.balance + amount,
                    balance_after=wallet.balance,
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                
                self.logger.info(f"Charged wallet: ${amount:.2f} for {advertiser.company_name}")
                return transaction
                
        except Exception as e:
            self.logger.error(f"Error charging wallet: {e}")
            raise ValidationError(f"Failed to charge wallet: {str(e)}")
    
    def create_invoice(self, advertiser, period: str, start_date, end_date, items: List[Dict[str, Any]]) -> AdvertiserInvoice:
        """
        Create invoice for advertiser.
        
        Args:
            advertiser: Advertiser instance
            period: Billing period
            start_date: Invoice start date
            end_date: Invoice end date
            items: Invoice items
            
        Returns:
            AdvertiserInvoice: Created invoice instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Calculate totals
                subtotal = sum(item.get('amount', 0) for item in items)
                tax_amount = subtotal * 0.10  # 10% tax
                fee_amount = subtotal * 0.02  # 2% fee
                total_amount = subtotal + tax_amount + fee_amount
                
                # Generate invoice number
                invoice_number = self._generate_invoice_number(advertiser)
                
                # Create invoice
                invoice = AdvertiserInvoice.objects.create(
                    advertiser=advertiser,
                    invoice_number=invoice_number,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    subtotal=subtotal,
                    tax_amount=tax_amount,
                    fee_amount=fee_amount,
                    total_amount=total_amount,
                    currency='USD',
                    status='sent',
                    due_date=end_date + timezone.timedelta(days=30),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                    sent_at=timezone.now(),
                )
                
                # Send invoice notification
                self._send_invoice_notification(advertiser, invoice)
                
                self.logger.info(f"Created invoice: {invoice_number} for {advertiser.company_name}")
                return invoice
                
        except Exception as e:
            self.logger.error(f"Error creating invoice: {e}")
            raise ValidationError(f"Failed to create invoice: {str(e)}")
    
    def get_wallet_balance(self, advertiser) -> Dict[str, Any]:
        """
        Get advertiser wallet balance information.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Wallet balance information
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            try:
                wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
            except AdvertiserWallet.DoesNotExist:
                return {
                    'has_wallet': False,
                    'balance': 0.00,
                    'credit_limit': 0.00,
                    'available_credit': 0.00,
                    'available_balance': 0.00,
                }
            
            return {
                'has_wallet': True,
                'balance': float(wallet.balance),
                'credit_limit': float(wallet.credit_limit),
                'available_credit': float(wallet.available_credit),
                'available_balance': float(wallet.available_balance),
                'is_suspended': wallet.is_suspended,
                'auto_refill_enabled': wallet.auto_refill_enabled,
                'auto_refill_threshold': float(wallet.auto_refill_threshold),
                'auto_refill_amount': float(wallet.auto_refill_amount),
                'currency': wallet.currency,
            }
            
        except Exception as e:
            self.logger.error(f"Error getting wallet balance: {e}")
            raise ValidationError(f"Failed to get wallet balance: {str(e)}")
    
    def get_transaction_history(self, advertiser, filters: Dict[str, Any] = None) -> List[AdvertiserTransaction]:
        """
        Get transaction history for advertiser.
        
        Args:
            advertiser: Advertiser instance
            filters: Optional filters
            
        Returns:
            List[AdvertiserTransaction]: Transaction history
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            try:
                wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
            except AdvertiserWallet.DoesNotExist:
                return []
            
            queryset = AdvertiserTransaction.objects.filter(wallet=wallet).order_by('-created_at')
            
            if filters:
                if 'transaction_type' in filters:
                    queryset = queryset.filter(transaction_type=filters['transaction_type'])
                
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                
                if 'date_from' in filters:
                    queryset = queryset.filter(created_at__date__gte=filters['date_from'])
                
                if 'date_to' in filters:
                    queryset = queryset.filter(created_at__date__lte=filters['date_to'])
                
                if 'min_amount' in filters:
                    queryset = queryset.filter(amount__gte=filters['min_amount'])
                
                if 'max_amount' in filters:
                    queryset = queryset.filter(amount__lte=filters['max_amount'])
            
            return list(queryset)
            
        except Exception as e:
            self.logger.error(f"Error getting transaction history: {e}")
            raise ValidationError(f"Failed to get transaction history: {str(e)}")
    
    def get_deposit_history(self, advertiser, filters: Dict[str, Any] = None) -> List[AdvertiserDeposit]:
        """
        Get deposit history for advertiser.
        
        Args:
            advertiser: Advertiser instance
            filters: Optional filters
            
        Returns:
            List[AdvertiserDeposit]: Deposit history
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            queryset = AdvertiserDeposit.objects.filter(advertiser=advertiser).order_by('-created_at')
            
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                
                if 'gateway' in filters:
                    queryset = queryset.filter(gateway=filters['gateway'])
                
                if 'payment_method' in filters:
                    queryset = queryset.filter(payment_method=filters['payment_method'])
                
                if 'date_from' in filters:
                    queryset = queryset.filter(created_at__date__gte=filters['date_from'])
                
                if 'date_to' in filters:
                    queryset = queryset.filter(created_at__date__lte=filters['date_to'])
                
                if 'min_amount' in filters:
                    queryset = queryset.filter(amount__gte=filters['min_amount'])
                
                if 'max_amount' in filters:
                    queryset = queryset.filter(amount__lte=filters['max_amount'])
            
            return list(queryset)
            
        except Exception as e:
            self.logger.error(f"Error getting deposit history: {e}")
            raise ValidationError(f"Failed to get deposit history: {str(e)}")
    
    def get_invoice_history(self, advertiser, filters: Dict[str, Any] = None) -> List[AdvertiserInvoice]:
        """
        Get invoice history for advertiser.
        
        Args:
            advertiser: Advertiser instance
            filters: Optional filters
            
        Returns:
            List[AdvertiserInvoice]: Invoice history
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            queryset = AdvertiserInvoice.objects.filter(advertiser=advertiser).order_by('-created_at')
            
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                
                if 'period' in filters:
                    queryset = queryset.filter(period=filters['period'])
                
                if 'date_from' in filters:
                    queryset = queryset.filter(start_date__gte=filters['date_from'])
                
                if 'date_to' in filters:
                    queryset = queryset.filter(end_date__lte=filters['date_to'])
                
                if 'min_amount' in filters:
                    queryset = queryset.filter(total_amount__gte=filters['min_amount'])
                
                if 'max_amount' in filters:
                    queryset = queryset.filter(total_amount__lte=filters['max_amount'])
            
            return list(queryset)
            
        except Exception as e:
            self.logger.error(f"Error getting invoice history: {e}")
            raise ValidationError(f"Failed to get invoice history: {str(e)}")
    
    def get_billing_summary(self, advertiser, days: int = 30) -> Dict[str, Any]:
        """
        Get billing summary for advertiser.
        
        Args:
            advertiser: Advertiser instance
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Billing summary
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            from django.db.models import Sum, Count
            
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            # Get wallet info
            wallet_info = self.get_wallet_balance(advertiser)
            
            # Get deposits
            deposits = AdvertiserDeposit.objects.filter(
                advertiser=advertiser,
                created_at__gte=start_date,
                status='completed'
            ).aggregate(
                total_deposits=Sum('net_amount'),
                deposit_count=Count('id')
            )
            
            # Get charges
            try:
                wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
                charges = AdvertiserTransaction.objects.filter(
                    wallet=wallet,
                    created_at__gte=start_date,
                    transaction_type='spend'
                ).aggregate(
                    total_charges=Sum('amount'),
                    charge_count=Count('id')
                )
            except AdvertiserWallet.DoesNotExist:
                charges = {'total_charges': 0, 'charge_count': 0}
            
            # Get invoices
            invoices = AdvertiserInvoice.objects.filter(
                advertiser=advertiser,
                created_at__gte=start_date
            ).aggregate(
                total_invoiced=Sum('total_amount'),
                invoice_count=Count('id'),
                paid_amount=Sum(models.Case(
                    When(status='paid', then=models.F('total_amount')),
                    default=0,
                ))
            )
            
            # Fill missing values
            for key, value in deposits.items():
                if value is None:
                    deposits[key] = 0
            
            for key, value in charges.items():
                if value is None:
                    charges[key] = 0
            
            for key, value in invoices.items():
                if value is None:
                    invoices[key] = 0
            
            return {
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': timezone.now().date().isoformat(),
                    'days': days,
                },
                'wallet': wallet_info,
                'deposits': {
                    'total_deposits': float(deposits['total_deposits']),
                    'deposit_count': deposits['deposit_count'],
                },
                'charges': {
                    'total_charges': float(charges['total_charges']),
                    'charge_count': charges['charge_count'],
                },
                'invoices': {
                    'total_invoiced': float(invoices['total_invoiced']),
                    'invoice_count': invoices['invoice_count'],
                    'paid_amount': float(invoices['paid_amount']),
                },
                'net_flow': float(deposits['total_deposits'] - charges['total_charges']),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting billing summary: {e}")
            raise ValidationError(f"Failed to get billing summary: {str(e)}")
    
    def _calculate_processing_fee(self, amount: float, payment_method: str) -> float:
        """Calculate processing fee based on amount and payment method."""
        # Simple fee calculation
        if payment_method == 'credit_card':
            return amount * 0.029 + 0.30  # 2.9% + $0.30
        elif payment_method == 'paypal':
            return amount * 0.034 + 0.30  # 3.4% + $0.30
        elif payment_method == 'bank_transfer':
            return max(5.00, amount * 0.01)  # 1% min $5
        else:
            return 0.00
    
    def _generate_invoice_number(self, advertiser) -> str:
        """Generate unique invoice number."""
        timestamp = timezone.now().strftime('%Y%m%d')
        advertiser_id = str(advertiser.id).zfill(4)
        
        # Get last invoice number for this advertiser
        last_invoice = AdvertiserInvoice.objects.filter(
            advertiser=advertiser
        ).order_by('-created_at').first()
        
        if last_invoice and last_invoice.invoice_number:
            # Extract sequence number
            parts = last_invoice.invoice_number.split('-')
            if len(parts) >= 3:
                try:
                    sequence = int(parts[2]) + 1
                    return f"INV-{timestamp}-{advertiser_id}-{sequence:04d}"
                except ValueError:
                    pass
        
        return f"INV-{timestamp}-{advertiser_id}-0001"
    
    def _send_deposit_notification(self, advertiser, deposit: AdvertiserDeposit):
        """Send deposit notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='payment_received',
            title=_('Deposit Received'),
            message=_(
                'Your deposit of ${amount:.2f} has been processed successfully. '
                'Available balance: ${balance:.2f}'
            ).format(
                amount=float(deposit.net_amount),
                balance=float(self.get_wallet_balance(advertiser)['available_balance'])
            ),
            priority='medium',
            action_url='/advertiser/billing/transactions/',
            action_text=_('View Transactions')
        )
    
    def _send_invoice_notification(self, advertiser, invoice: AdvertiserInvoice):
        """Send invoice notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='invoice_created',
            title=_('Invoice Created'),
            message=_(
                'Invoice {invoice_number} for {period} has been created. '
                'Total amount: ${total_amount:.2f} - Due: {due_date}'
            ).format(
                invoice_number=invoice.invoice_number,
                period=invoice.period,
                total_amount=float(invoice.total_amount),
                due_date=invoice.due_date.strftime('%B %d, %Y')
            ),
            priority='high',
            action_url=f'/advertiser/billing/invoices/{invoice.id}/',
            action_text=_('View Invoice')
        )
