"""
Advertiser Billing Management

This module handles billing operations, payment processing, and financial
management for advertisers including invoices, payments, and credit management.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
import secrets

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.core.validators import validate_email

from ..database_models.advertiser_model import Advertiser, AdvertiserCredit
from ..database_models.billing_model import BillingProfile, PaymentMethod, Invoice, PaymentTransaction
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserBillingService:
    """Service for managing advertiser billing operations."""
    
    @staticmethod
    def create_billing_profile(advertiser_id: UUID, billing_data: Dict[str, Any],
                               created_by: Optional[User] = None) -> BillingProfile:
        """Create billing profile for advertiser."""
        try:
            advertiser = AdvertiserBillingService.get_advertiser(advertiser_id)
            
            # Check if billing profile already exists
            existing_profile = BillingProfile.objects.filter(advertiser=advertiser).first()
            if existing_profile:
                raise AdvertiserValidationError(f"Billing profile already exists: {existing_profile.id}")
            
            # Validate required fields
            required_fields = ['company_name', 'billing_email']
            for field in required_fields:
                if not billing_data.get(field):
                    raise AdvertiserValidationError(f"{field} is required")
            
            # Validate email
            validate_email(billing_data['billing_email'])
            
            with transaction.atomic():
                # Create billing profile
                billing_profile = BillingProfile.objects.create(
                    advertiser=advertiser,
                    company_name=billing_data['company_name'],
                    trade_name=billing_data.get('trade_name', ''),
                    billing_email=billing_data['billing_email'],
                    billing_phone=billing_data.get('billing_phone', ''),
                    billing_contact=billing_data.get('billing_contact', ''),
                    billing_title=billing_data.get('billing_title', ''),
                    billing_address_line1=billing_data.get('billing_address_line1', ''),
                    billing_address_line2=billing_data.get('billing_address_line2', ''),
                    billing_city=billing_data.get('billing_city', ''),
                    billing_state=billing_data.get('billing_state', ''),
                    billing_country=billing_data.get('billing_country', ''),
                    billing_postal_code=billing_data.get('billing_postal_code', ''),
                    billing_cycle=billing_data.get('billing_cycle', 'monthly'),
                    payment_terms=billing_data.get('payment_terms', 'net_30'),
                    auto_charge=billing_data.get('auto_charge', False),
                    auto_charge_threshold=billing_data.get('auto_charge_threshold', 80),
                    credit_limit=Decimal(str(billing_data.get('credit_limit', 1000.00))),
                    credit_available=Decimal(str(billing_data.get('credit_limit', 1000.00))),
                    spending_limit=Decimal(str(billing_data.get('spending_limit', 0))),
                    tax_exempt=billing_data.get('tax_exempt', False),
                    tax_rate=Decimal(str(billing_data.get('tax_rate', 0))),
                    tax_region=billing_data.get('tax_region', ''),
                    default_currency=billing_data.get('default_currency', 'USD'),
                    pricing_model=billing_data.get('pricing_model', 'cpc'),
                    is_verified=False,
                    verification_date=None,
                    status='active',
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Billing Profile Created',
                    message=f'Billing profile for {billing_profile.company_name} has been created successfully.',
                    notification_type='billing',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    billing_profile,
                    created_by,
                    description=f"Created billing profile: {billing_profile.company_name}"
                )
                
                return billing_profile
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating billing profile {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create billing profile: {str(e)}")
    
    @staticmethod
    def add_payment_method(advertiser_id: UUID, payment_method_data: Dict[str, Any],
                           added_by: Optional[User] = None) -> PaymentMethod:
        """Add payment method for advertiser."""
        try:
            advertiser = AdvertiserBillingService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserBillingService.get_billing_profile(advertiser_id)
            
            # Validate payment method data
            method_type = payment_method_data.get('method_type')
            if not method_type:
                raise AdvertiserValidationError("method_type is required")
            
            with transaction.atomic():
                # Encrypt sensitive data
                encrypted_data = AdvertiserBillingService._encrypt_payment_data(payment_method_data)
                
                # Create payment method
                payment_method = PaymentMethod.objects.create(
                    billing_profile=billing_profile,
                    method_type=method_type,
                    method_name=payment_method_data.get('method_name', f"{method_type.title()} Card"),
                    cardholder_name=payment_method_data.get('cardholder_name', ''),
                    card_number=encrypted_data.get('card_number'),
                    card_expiry=encrypted_data.get('card_expiry'),
                    card_cvv=encrypted_data.get('card_cvv'),
                    bank_account_number=encrypted_data.get('bank_account_number'),
                    bank_routing_number=encrypted_data.get('bank_routing_number'),
                    bank_account_type=payment_method_data.get('bank_account_type', 'checking'),
                    paypal_email=payment_method_data.get('paypal_email', ''),
                    stripe_customer_id=payment_method_data.get('stripe_customer_id'),
                    stripe_payment_method_id=payment_method_data.get('stripe_payment_method_id'),
                    is_default=payment_method_data.get('is_default', False),
                    is_verified=False,
                    verification_date=None,
                    status='active',
                    created_by=added_by
                )
                
                # Set as default if requested
                if payment_method.is_default:
                    AdvertiserBillingService._set_as_default_payment_method(payment_method)
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=added_by,
                    title='Payment Method Added',
                    message=f'Payment method "{payment_method.method_name}" has been added successfully.',
                    notification_type='billing',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log addition
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    payment_method,
                    added_by,
                    description=f"Added payment method: {payment_method.method_name}"
                )
                
                return payment_method
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error adding payment method {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to add payment method: {str(e)}")
    
    @staticmethod
    def create_invoice(advertiser_id: UUID, invoice_data: Dict[str, Any],
                        created_by: Optional[User] = None) -> Invoice:
        """Create invoice for advertiser."""
        try:
            advertiser = AdvertiserBillingService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserBillingService.get_billing_profile(advertiser_id)
            
            # Validate invoice data
            if not invoice_data.get('amount'):
                raise AdvertiserValidationError("amount is required")
            
            amount = Decimal(str(invoice_data['amount']))
            if amount <= 0:
                raise AdvertiserValidationError("amount must be positive")
            
            with transaction.atomic():
                # Generate invoice number
                invoice_number = AdvertiserBillingService._generate_invoice_number()
                
                # Calculate tax
                tax_amount = Decimal('0.00')
                if not billing_profile.tax_exempt:
                    tax_amount = amount * (billing_profile.tax_rate / 100)
                
                total_amount = amount + tax_amount
                
                # Create invoice
                invoice = Invoice.objects.create(
                    advertiser=advertiser,
                    billing_profile=billing_profile,
                    invoice_number=invoice_number,
                    invoice_date=invoice_data.get('invoice_date', date.today()),
                    due_date=invoice_data.get('due_date', date.today() + timezone.timedelta(days=30)),
                    amount=amount,
                    tax_amount=tax_amount,
                    total_amount=total_amount,
                    currency=billing_profile.default_currency,
                    status='draft',
                    line_items=invoice_data.get('line_items', []),
                    notes=invoice_data.get('notes', ''),
                    recipient_email=billing_profile.billing_email,
                    recipient_name=billing_profile.company_name,
                    recipient_address=billing_profile.billing_address_line1,
                    recipient_city=billing_profile.billing_city,
                    recipient_state=billing_profile.billing_state,
                    recipient_country=billing_profile.billing_country,
                    recipient_postal_code=billing_profile.billing_postal_code,
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Invoice Created',
                    message=f'Invoice #{invoice_number} has been created successfully.',
                    notification_type='billing',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    invoice,
                    created_by,
                    description=f"Created invoice: {invoice_number}"
                )
                
                return invoice
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating invoice {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create invoice: {str(e)}")
    
    @staticmethod
    def process_payment(advertiser_id: UUID, payment_data: Dict[str, Any],
                        processed_by: Optional[User] = None) -> Dict[str, Any]:
        """Process payment for advertiser."""
        try:
            advertiser = AdvertiserBillingService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserBillingService.get_billing_profile(advertiser_id)
            
            # Validate payment data
            amount = Decimal(str(payment_data.get('amount', 0)))
            if amount <= 0:
                raise AdvertiserValidationError("amount must be positive")
            
            payment_method_id = payment_data.get('payment_method_id')
            if not payment_method_id:
                raise AdvertiserValidationError("payment_method_id is required")
            
            with transaction.atomic():
                # Get payment method
                payment_method = AdvertiserBillingService.get_payment_method(payment_method_id)
                
                # Create transaction
                transaction_id = AdvertiserBillingService._generate_transaction_id()
                payment_transaction = PaymentTransaction.objects.create(
                    advertiser=advertiser,
                    billing_profile=billing_profile,
                    payment_method=payment_method,
                    transaction_id=transaction_id,
                    amount=amount,
                    transaction_type='payment',
                    currency=billing_profile.default_currency,
                    status='pending',
                    processed_by=processed_by
                )
                
                # Process payment (mock implementation)
                payment_result = AdvertiserBillingService._process_with_payment_gateway(
                    payment_transaction,
                    payment_method
                )
                
                # Update transaction based on result
                if payment_result['success']:
                    payment_transaction.status = 'completed'
                    payment_transaction.gateway_transaction_id = payment_result.get('gateway_transaction_id')
                    payment_transaction.gateway_response = payment_result.get('gateway_response')
                    payment_transaction.completed_at = timezone.now()
                    
                    # Update credit available
                    billing_profile.credit_available += amount
                    billing_profile.save(update_fields=['credit_available'])
                    
                    # Create credit record
                    AdvertiserCredit.objects.create(
                        advertiser=advertiser,
                        credit_type='payment',
                        amount=amount,
                        description=f'Payment processed: {transaction_id}',
                        balance_after=billing_profile.credit_available
                    )
                    
                    # Send notification
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=processed_by,
                        title='Payment Processed',
                        message=f'Payment of {billing_profile.default_currency} {amount} has been processed successfully.',
                        notification_type='billing',
                        priority='medium',
                        channels=['in_app']
                    )
                    
                else:
                    payment_transaction.status = 'failed'
                    payment_transaction.error_message = payment_result.get('error_message')
                    
                    # Send notification
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=processed_by,
                        title='Payment Failed',
                        message=f'Payment of {billing_profile.default_currency} {amount} has failed.',
                        notification_type='billing',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                
                payment_transaction.save(update_fields=[
                    'status', 'gateway_transaction_id', 'gateway_response',
                    'completed_at', 'error_message'
                ])
                
                # Log processing
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='process_payment',
                    object_type='PaymentTransaction',
                    object_id=str(payment_transaction.id),
                    user=processed_by,
                    advertiser=advertiser,
                    description=f"Processed payment: {transaction_id}"
                )
                
                return {
                    'success': payment_result['success'],
                    'transaction_id': transaction_id,
                    'status': payment_transaction.status,
                    'amount': float(amount),
                    'error_message': payment_transaction.error_message
                }
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error processing payment {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to process payment: {str(e)}")
    
    @staticmethod
    def get_billing_summary(advertiser_id: UUID) -> Dict[str, Any]:
        """Get billing summary for advertiser."""
        try:
            advertiser = AdvertiserBillingService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserBillingService.get_billing_profile(advertiser_id)
            
            # Get recent invoices
            recent_invoices = Invoice.objects.filter(
                advertiser=advertiser
            ).order_by('-created_at')[:5]
            
            # Get recent transactions
            recent_transactions = PaymentTransaction.objects.filter(
                advertiser=advertiser
            ).order_by('-created_at')[:5]
            
            # Get credit records
            credit_records = AdvertiserCredit.objects.filter(
                advertiser=advertiser
            ).order_by('-created_at')[:10]
            
            # Calculate totals
            total_invoiced = Invoice.objects.filter(
                advertiser=advertiser
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            
            total_paid = PaymentTransaction.objects.filter(
                advertiser=advertiser,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            total_spent = AdvertiserCredit.objects.filter(
                advertiser=advertiser,
                credit_type='spend'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            return {
                'advertiser_id': str(advertiser_id),
                'billing_profile': {
                    'id': str(billing_profile.id),
                    'company_name': billing_profile.company_name,
                    'billing_email': billing_profile.billing_email,
                    'credit_limit': float(billing_profile.credit_limit),
                    'credit_available': float(billing_profile.credit_available),
                    'spending_limit': float(billing_profile.spending_limit),
                    'auto_charge': billing_profile.auto_charge,
                    'billing_cycle': billing_profile.billing_cycle,
                    'status': billing_profile.status
                },
                'financial_summary': {
                    'total_invoiced': float(total_invoiced),
                    'total_paid': float(total_paid),
                    'total_spent': float(total_spent),
                    'outstanding_balance': float(total_invoiced - total_paid),
                    'credit_utilization': float((billing_profile.credit_limit - billing_profile.credit_available) / billing_profile.credit_limit * 100) if billing_profile.credit_limit > 0 else 0
                },
                'recent_invoices': [
                    {
                        'id': str(invoice.id),
                        'invoice_number': invoice.invoice_number,
                        'amount': float(invoice.total_amount),
                        'status': invoice.status,
                        'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
                        'created_at': invoice.created_at.isoformat()
                    }
                    for invoice in recent_invoices
                ],
                'recent_transactions': [
                    {
                        'id': str(transaction.id),
                        'transaction_id': transaction.transaction_id,
                        'amount': float(transaction.amount),
                        'transaction_type': transaction.transaction_type,
                        'status': transaction.status,
                        'created_at': transaction.created_at.isoformat()
                    }
                    for transaction in recent_transactions
                ],
                'credit_history': [
                    {
                        'id': str(credit.id),
                        'credit_type': credit.credit_type,
                        'amount': float(credit.amount),
                        'description': credit.description,
                        'balance_after': float(credit.balance_after),
                        'created_at': credit.created_at.isoformat()
                    }
                    for credit in credit_records
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting billing summary {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get billing summary: {str(e)}")
    
    @staticmethod
    def get_billing_profile(advertiser_id: UUID) -> BillingProfile:
        """Get billing profile for advertiser."""
        try:
            advertiser = AdvertiserBillingService.get_advertiser(advertiser_id)
            billing_profile = BillingProfile.objects.filter(advertiser=advertiser).first()
            
            if not billing_profile:
                raise AdvertiserNotFoundError(f"Billing profile not found for advertiser {advertiser_id}")
            
            return billing_profile
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting billing profile {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get billing profile: {str(e)}")
    
    @staticmethod
    def get_payment_method(payment_method_id: UUID) -> PaymentMethod:
        """Get payment method by ID."""
        try:
            return PaymentMethod.objects.get(id=payment_method_id)
        except PaymentMethod.DoesNotExist:
            raise AdvertiserNotFoundError(f"Payment method {payment_method_id} not found")
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def _encrypt_payment_data(payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive payment data."""
        encrypted_data = {}
        
        # Encrypt card data
        if 'card_number' in payment_data:
            encrypted_data['card_number'] = AdvertiserBillingService._encrypt_value(payment_data['card_number'])
        if 'card_expiry' in payment_data:
            encrypted_data['card_expiry'] = AdvertiserBillingService._encrypt_value(payment_data['card_expiry'])
        if 'card_cvv' in payment_data:
            encrypted_data['card_cvv'] = AdvertiserBillingService._encrypt_value(payment_data['card_cvv'])
        
        # Encrypt bank data
        if 'bank_account_number' in payment_data:
            encrypted_data['bank_account_number'] = AdvertiserBillingService._encrypt_value(payment_data['bank_account_number'])
        if 'bank_routing_number' in payment_data:
            encrypted_data['bank_routing_number'] = AdvertiserBillingService._encrypt_value(payment_data['bank_routing_number'])
        
        return encrypted_data
    
    @staticmethod
    def _encrypt_value(value: str) -> str:
        """Encrypt sensitive value."""
        from cryptography.fernet import Fernet
        from django.conf import settings
        
        try:
            key = getattr(settings, 'ENCRYPTION_KEY', None)
            if key:
                fernet = Fernet(key.encode())
                return fernet.encrypt(value.encode()).decode()
        except Exception:
            pass
        
        return value  # Return as-is if encryption fails
    
    @staticmethod
    def _set_as_default_payment_method(payment_method: PaymentMethod) -> None:
        """Set payment method as default for billing profile."""
        # Unset other default methods
        PaymentMethod.objects.filter(
            billing_profile=payment_method.billing_profile
        ).update(is_default=False)
        
        # Set this one as default
        payment_method.is_default = True
        payment_method.save(update_fields=['is_default'])
    
    @staticmethod
    def _generate_invoice_number() -> str:
        """Generate unique invoice number."""
        from ..database_models.billing_model import Invoice
        import datetime
        
        now = datetime.datetime.now()
        month_year = now.strftime('%Y%m')
        
        # Get count for this month
        count = Invoice.objects.filter(
            created_at__year=now.year,
            created_at__month=now.month
        ).count()
        
        return f"INV-{month_year}-{count + 1:04d}"
    
    @staticmethod
    def _generate_transaction_id() -> str:
        """Generate unique transaction ID."""
        return f"txn_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def _process_with_payment_gateway(transaction: PaymentTransaction, payment_method: PaymentMethod) -> Dict[str, Any]:
        """Process payment with payment gateway (mock implementation)."""
        # This would integrate with actual payment gateway (Stripe, PayPal, etc.)
        # For now, return mock response
        
        # Simulate payment processing
        import random
        
        # 95% success rate for demo
        success = random.random() < 0.95
        
        if success:
            return {
                'success': True,
                'gateway_transaction_id': f"gw_{secrets.token_urlsafe(16)}",
                'gateway_response': 'Payment processed successfully'
            }
        else:
            return {
                'success': False,
                'error_message': 'Payment declined by gateway'
            }
    
    @staticmethod
    def update_credit_balance(advertiser_id: UUID, amount: Decimal, transaction_type: str,
                                description: str = '', updated_by: Optional[User] = None) -> bool:
        """Update credit balance for advertiser."""
        try:
            advertiser = AdvertiserBillingService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserBillingService.get_billing_profile(advertiser_id)
            
            with transaction.atomic():
                # Update credit based on transaction type
                if transaction_type == 'spend':
                    billing_profile.credit_available -= amount
                    if billing_profile.credit_available < 0:
                        # Handle negative balance
                        pass
                elif transaction_type == 'payment':
                    billing_profile.credit_available += amount
                elif transaction_type == 'refund':
                    billing_profile.credit_available += amount
                elif transaction_type == 'adjustment':
                    billing_profile.credit_available += amount
                else:
                    raise AdvertiserValidationError(f"Invalid transaction type: {transaction_type}")
                
                billing_profile.save(update_fields=['credit_available'])
                
                # Create credit record
                AdvertiserCredit.objects.create(
                    advertiser=advertiser,
                    credit_type=transaction_type,
                    amount=amount,
                    description=description,
                    balance_after=billing_profile.credit_available,
                    created_by=updated_by
                )
                
                # Check credit limit alerts
                if billing_profile.credit_available < 0:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=advertiser.user,
                        title='Credit Limit Exceeded',
                        message=f'Your credit limit has been exceeded by {abs(billing_profile.credit_available)}.',
                        notification_type='billing',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                elif billing_profile.credit_available < billing_profile.credit_limit * 0.2:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=advertiser.user,
                        title='Low Credit Warning',
                        message=f'Your available credit is low: {billing_profile.credit_available}.',
                        notification_type='billing',
                        priority='medium',
                        channels=['in_app']
                    )
                
                return True
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error updating credit balance {advertiser_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_payment_methods(advertiser_id: UUID) -> List[PaymentMethod]:
        """Get all payment methods for advertiser."""
        try:
            billing_profile = AdvertiserBillingService.get_billing_profile(advertiser_id)
            return PaymentMethod.objects.filter(
                billing_profile=billing_profile,
                status='active'
            ).order_by('-is_default', '-created_at')
            
        except Exception as e:
            logger.error(f"Error getting payment methods {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_billing_statistics() -> Dict[str, Any]:
        """Get billing statistics."""
        try:
            # Get billing profile statistics
            total_profiles = BillingProfile.objects.count()
            active_profiles = BillingProfile.objects.filter(status='active').count()
            auto_charge_profiles = BillingProfile.objects.filter(auto_charge=True).count()
            
            # Get payment method statistics
            payment_methods = PaymentMethod.objects.values('method_type').annotate(
                count=Count('id')
            )
            
            # Get invoice statistics
            total_invoices = Invoice.objects.count()
            paid_invoices = Invoice.objects.filter(status='paid').count()
            pending_invoices = Invoice.objects.filter(status='sent').count()
            
            # Get transaction statistics
            total_transactions = PaymentTransaction.objects.count()
            completed_transactions = PaymentTransaction.objects.filter(status='completed').count()
            failed_transactions = PaymentTransaction.objects.filter(status='failed').count()
            
            # Calculate totals
            total_invoiced_amount = Invoice.objects.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0.00')
            
            total_paid_amount = PaymentTransaction.objects.filter(
                status='completed'
            ).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            return {
                'billing_profiles': {
                    'total': total_profiles,
                    'active': active_profiles,
                    'auto_charge': auto_charge_profiles
                },
                'payment_methods': list(payment_methods),
                'invoices': {
                    'total': total_invoices,
                    'paid': paid_invoices,
                    'pending': pending_invoices,
                    'total_amount': float(total_invoiced_amount)
                },
                'transactions': {
                    'total': total_transactions,
                    'completed': completed_transactions,
                    'failed': failed_transactions,
                    'total_amount': float(total_paid_amount)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting billing statistics: {str(e)}")
            return {
                'billing_profiles': {'total': 0, 'active': 0, 'auto_charge': 0},
                'payment_methods': [],
                'invoices': {'total': 0, 'paid': 0, 'pending': 0, 'total_amount': 0},
                'transactions': {'total': 0, 'completed': 0, 'failed': 0, 'total_amount': 0}
            }
