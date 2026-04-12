"""
Billing Management Services

This module contains service classes for managing billing operations,
including payments, invoices, billing profiles, and financial transactions.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.billing_model import BillingProfile, PaymentMethod, Invoice, PaymentTransaction
from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class BillingService:
    """Service for managing billing operations."""
    
    @staticmethod
    def create_billing_profile(data: Dict[str, Any], created_by: Optional[User] = None) -> BillingProfile:
        """Create a new billing profile."""
        try:
            with transaction.atomic():
                billing_profile = BillingProfile.objects.create(
                    advertiser=data.get('advertiser'),
                    company_name=data['company_name'],
                    trade_name=data.get('trade_name', ''),
                    billing_email=data['billing_email'],
                    billing_phone=data.get('billing_phone', ''),
                    billing_contact=data.get('billing_contact', ''),
                    billing_title=data.get('billing_title', ''),
                    billing_address_line1=data.get('billing_address_line1', ''),
                    billing_address_line2=data.get('billing_address_line2', ''),
                    billing_city=data.get('billing_city', ''),
                    billing_state=data.get('billing_state', ''),
                    billing_country=data.get('billing_country', ''),
                    billing_postal_code=data.get('billing_postal_code', ''),
                    billing_cycle=data.get('billing_cycle', 'monthly'),
                    payment_terms=data.get('payment_terms', 'net_30'),
                    auto_charge=data.get('auto_charge', False),
                    auto_charge_threshold=data.get('auto_charge_threshold', 0),
                    credit_limit=data.get('credit_limit', 0),
                    credit_available=data.get('credit_available', 0),
                    spending_limit=data.get('spending_limit', 0),
                    tax_exempt=data.get('tax_exempt', False),
                    tax_rate=data.get('tax_rate', 0),
                    tax_region=data.get('tax_region', ''),
                    default_currency=data.get('default_currency', 'USD'),
                    pricing_model=data.get('pricing_model', 'cpc'),
                    is_verified=data.get('is_verified', False),
                    verification_date=data.get('verification_date'),
                    status=data.get('status', 'active'),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=billing_profile.advertiser,
                    user=created_by,
                    title='Billing Profile Created',
                    message=f'Billing profile for {billing_profile.company_name} has been created successfully.',
                    notification_type='system',
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
                
        except Exception as e:
            logger.error(f"Error creating billing profile: {str(e)}")
            raise BillingServiceError(f"Failed to create billing profile: {str(e)}")
    
    @staticmethod
    def update_billing_profile(profile_id: UUID, data: Dict[str, Any],
                                 updated_by: Optional[User] = None) -> BillingProfile:
        """Update billing profile."""
        try:
            billing_profile = BillingService.get_billing_profile(profile_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update fields
                for field in ['company_name', 'trade_name', 'billing_email', 'billing_phone',
                             'billing_contact', 'billing_title', 'billing_address_line1',
                             'billing_address_line2', 'billing_city', 'billing_state',
                             'billing_country', 'billing_postal_code', 'billing_cycle',
                             'payment_terms', 'auto_charge', 'auto_charge_threshold',
                             'credit_limit', 'spending_limit', 'tax_exempt',
                             'tax_rate', 'tax_region', 'default_currency',
                             'pricing_model', 'status']:
                    if field in data:
                        old_value = getattr(billing_profile, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(billing_profile, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                billing_profile.modified_by = updated_by
                billing_profile.save()
                
                # Recalculate credit available if credit limit changed
                if 'credit_limit' in changed_fields:
                    billing_profile.update_credit_available()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        billing_profile,
                        changed_fields,
                        updated_by,
                        description=f"Updated billing profile: {billing_profile.company_name}"
                    )
                
                return billing_profile
                
        except BillingProfile.DoesNotExist:
            raise BillingNotFoundError(f"Billing profile {profile_id} not found")
        except Exception as e:
            logger.error(f"Error updating billing profile {profile_id}: {str(e)}")
            raise BillingServiceError(f"Failed to update billing profile: {str(e)}")
    
    @staticmethod
    def get_billing_profile(profile_id: UUID) -> BillingProfile:
        """Get billing profile by ID."""
        try:
            return BillingProfile.objects.get(id=profile_id)
        except BillingProfile.DoesNotExist:
            raise BillingNotFoundError(f"Billing profile {profile_id} not found")
    
    @staticmethod
    def list_billing_profiles(advertiser_id: Optional[UUID] = None,
                                filters: Optional[Dict[str, Any]] = None,
                                page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List billing profiles with filtering and pagination."""
        try:
            queryset = BillingProfile.objects.all()
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'is_verified' in filters:
                    queryset = queryset.filter(is_verified=filters['is_verified'])
                if 'billing_cycle' in filters:
                    queryset = queryset.filter(billing_cycle=filters['billing_cycle'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(company_name__icontains=search) |
                        Q(trade_name__icontains=search) |
                        Q(billing_email__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            profiles = queryset[offset:offset + page_size]
            
            return {
                'profiles': profiles,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing billing profiles: {str(e)}")
            raise BillingServiceError(f"Failed to list billing profiles: {str(e)}")
    
    @staticmethod
    def verify_billing_profile(profile_id: UUID, verified_by: Optional[User] = None) -> bool:
        """Verify billing profile."""
        try:
            billing_profile = BillingService.get_billing_profile(profile_id)
            
            with transaction.atomic():
                billing_profile.is_verified = True
                billing_profile.verification_date = timezone.now()
                billing_profile.verified_by = verified_by
                billing_profile.save(update_fields=['is_verified', 'verification_date', 'verified_by'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=billing_profile.advertiser,
                    user=billing_profile.advertiser.user,
                    title='Billing Profile Verified',
                    message=f'Your billing profile has been verified successfully.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log verification
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='verify',
                    object_type='BillingProfile',
                    object_id=str(billing_profile.id),
                    user=verified_by,
                    advertiser=billing_profile.advertiser,
                    description=f"Verified billing profile: {billing_profile.company_name}"
                )
                
                return True
                
        except BillingProfile.DoesNotExist:
            raise BillingNotFoundError(f"Billing profile {profile_id} not found")
        except Exception as e:
            logger.error(f"Error verifying billing profile {profile_id}: {str(e)}")
            return False
    
    @staticmethod
    def calculate_tax(profile_id: UUID, amount: Decimal) -> Decimal:
        """Calculate tax amount for billing profile."""
        try:
            billing_profile = BillingService.get_billing_profile(profile_id)
            return billing_profile.calculate_tax(amount)
            
        except BillingProfile.DoesNotExist:
            raise BillingNotFoundError(f"Billing profile {profile_id} not found")
        except Exception as e:
            logger.error(f"Error calculating tax {profile_id}: {str(e)}")
            raise BillingServiceError(f"Failed to calculate tax: {str(e)}")
    
    @staticmethod
    def update_credit_available(profile_id: UUID, amount: Decimal, transaction_type: str = 'spend') -> bool:
        """Update credit available for billing profile."""
        try:
            billing_profile = BillingService.get_billing_profile(profile_id)
            
            with transaction.atomic():
                if transaction_type == 'spend':
                    billing_profile.credit_available -= amount
                elif transaction_type == 'refund':
                    billing_profile.credit_available += amount
                elif transaction_type == 'deposit':
                    billing_profile.credit_available += amount
                else:
                    raise BillingValidationError(f"Invalid transaction type: {transaction_type}")
                
                billing_profile.save(update_fields=['credit_available'])
                
                # Check if credit limit is exceeded
                if billing_profile.credit_available < 0:
                    # Send alert
                    Notification.objects.create(
                        advertiser=billing_profile.advertiser,
                        user=billing_profile.advertiser.user,
                        title='Credit Limit Exceeded',
                        message=f'Your credit limit has been exceeded. Available credit: ${billing_profile.credit_available}',
                        notification_type='system',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                
                return True
                
        except BillingProfile.DoesNotExist:
            raise BillingNotFoundError(f"Billing profile {profile_id} not found")
        except Exception as e:
            logger.error(f"Error updating credit available {profile_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_billing_summary(advertiser_id: UUID) -> Dict[str, Any]:
        """Get billing summary for advertiser."""
        try:
            from ..database_models.advertiser_model import Advertiser
            advertiser = Advertiser.objects.get(id=advertiser_id, is_deleted=False)
            
            billing_profile = advertiser.get_billing_profile()
            if not billing_profile:
                return {'error': 'No billing profile found'}
            
            # Get recent invoices
            recent_invoices = Invoice.objects.filter(
                advertiser=advertiser
            ).order_by('-created_at')[:5]
            
            # Get recent transactions
            recent_transactions = PaymentTransaction.objects.filter(
                advertiser=advertiser
            ).order_by('-created_at')[:5]
            
            return {
                'billing_profile': {
                    'id': str(billing_profile.id),
                    'company_name': billing_profile.company_name,
                    'credit_limit': float(billing_profile.credit_limit),
                    'credit_available': float(billing_profile.credit_available),
                    'spending_limit': float(billing_profile.spending_limit),
                    'auto_charge': billing_profile.auto_charge,
                    'billing_cycle': billing_profile.billing_cycle,
                    'status': billing_profile.status,
                    'is_verified': billing_profile.is_verified
                },
                'recent_invoices': [
                    {
                        'id': str(invoice.id),
                        'invoice_number': invoice.invoice_number,
                        'amount': float(invoice.amount),
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
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise BillingNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting billing summary {advertiser_id}: {str(e)}")
            raise BillingServiceError(f"Failed to get billing summary: {str(e)}")


class PaymentService:
    """Service for managing payment operations."""
    
    @staticmethod
    def create_payment_method(data: Dict[str, Any], created_by: Optional[User] = None) -> PaymentMethod:
        """Create a new payment method."""
        try:
            with transaction.atomic():
                # Encrypt sensitive data
                encrypted_data = PaymentService._encrypt_payment_data(data)
                
                payment_method = PaymentMethod.objects.create(
                    billing_profile=data.get('billing_profile'),
                    method_type=data['method_type'],
                    method_name=data.get('method_name', ''),
                    cardholder_name=data.get('cardholder_name', ''),
                    card_number=encrypted_data.get('card_number'),
                    card_expiry=encrypted_data.get('card_expiry'),
                    card_cvv=encrypted_data.get('card_cvv'),
                    bank_account_number=encrypted_data.get('bank_account_number'),
                    bank_routing_number=encrypted_data.get('bank_routing_number'),
                    bank_account_type=data.get('bank_account_type', 'checking'),
                    paypal_email=data.get('paypal_email', ''),
                    stripe_customer_id=data.get('stripe_customer_id'),
                    stripe_payment_method_id=data.get('stripe_payment_method_id'),
                    is_default=data.get('is_default', False),
                    is_verified=data.get('is_verified', False),
                    verification_date=data.get('verification_date'),
                    status=data.get('status', 'active'),
                    created_by=created_by
                )
                
                # Set as default if requested
                if payment_method.is_default:
                    PaymentService._set_as_default(payment_method)
                
                # Send notification
                Notification.objects.create(
                    advertiser=payment_method.billing_profile.advertiser,
                    user=created_by,
                    title='Payment Method Added',
                    message=f'Payment method "{payment_method.get_method_display()}" has been added successfully.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    payment_method,
                    created_by,
                    description=f"Created payment method: {payment_method.get_method_display()}"
                )
                
                return payment_method
                
        except Exception as e:
            logger.error(f"Error creating payment method: {str(e)}")
            raise BillingServiceError(f"Failed to create payment method: {str(e)}")
    
    @staticmethod
    def _encrypt_payment_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive payment data."""
        encrypted_data = {}
        
        # Encrypt card data
        if 'card_number' in data:
            encrypted_data['card_number'] = PaymentService._encrypt_value(data['card_number'])
        if 'card_expiry' in data:
            encrypted_data['card_expiry'] = PaymentService._encrypt_value(data['card_expiry'])
        if 'card_cvv' in data:
            encrypted_data['card_cvv'] = PaymentService._encrypt_value(data['card_cvv'])
        
        # Encrypt bank data
        if 'bank_account_number' in data:
            encrypted_data['bank_account_number'] = PaymentService._encrypt_value(data['bank_account_number'])
        if 'bank_routing_number' in data:
            encrypted_data['bank_routing_number'] = PaymentService._encrypt_value(data['bank_routing_number'])
        
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
    def _decrypt_value(encrypted_value: str) -> str:
        """Decrypt sensitive value."""
        from cryptography.fernet import Fernet
        from django.conf import settings
        
        try:
            key = getattr(settings, 'ENCRYPTION_KEY', None)
            if key:
                fernet = Fernet(key.encode())
                return fernet.decrypt(encrypted_value.encode()).decode()
        except Exception:
            pass
        
        return encrypted_value  # Return as-is if decryption fails
    
    @staticmethod
    def _set_as_default(payment_method: PaymentMethod) -> None:
        """Set payment method as default for billing profile."""
        # Unset other default methods
        PaymentMethod.objects.filter(
            billing_profile=payment_method.billing_profile
        ).update(is_default=False)
        
        # Set this one as default
        payment_method.is_default = True
        payment_method.save(update_fields=['is_default'])
    
    @staticmethod
    def update_payment_method(method_id: UUID, data: Dict[str, Any],
                                updated_by: Optional[User] = None) -> PaymentMethod:
        """Update payment method."""
        try:
            payment_method = PaymentService.get_payment_method(method_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Encrypt sensitive data if provided
                if any(key in data for key in ['card_number', 'card_expiry', 'card_cvv',
                                           'bank_account_number', 'bank_routing_number']):
                    encrypted_data = PaymentService._encrypt_payment_data(data)
                    data.update(encrypted_data)
                
                # Update fields
                for field in ['method_name', 'cardholder_name', 'bank_account_type',
                             'paypal_email', 'stripe_customer_id', 'stripe_payment_method_id',
                             'is_default', 'status']:
                    if field in data:
                        old_value = getattr(payment_method, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(payment_method, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                payment_method.modified_by = updated_by
                payment_method.save()
                
                # Set as default if requested
                if data.get('is_default', False):
                    PaymentService._set_as_default(payment_method)
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        payment_method,
                        changed_fields,
                        updated_by,
                        description=f"Updated payment method: {payment_method.get_method_display()}"
                    )
                
                return payment_method
                
        except PaymentMethod.DoesNotExist:
            raise BillingNotFoundError(f"Payment method {method_id} not found")
        except Exception as e:
            logger.error(f"Error updating payment method {method_id}: {str(e)}")
            raise BillingServiceError(f"Failed to update payment method: {str(e)}")
    
    @staticmethod
    def get_payment_method(method_id: UUID) -> PaymentMethod:
        """Get payment method by ID."""
        try:
            return PaymentMethod.objects.get(id=method_id)
        except PaymentMethod.DoesNotExist:
            raise BillingNotFoundError(f"Payment method {method_id} not found")
    
    @staticmethod
    def delete_payment_method(method_id: UUID, deleted_by: Optional[User] = None) -> bool:
        """Delete payment method."""
        try:
            payment_method = PaymentService.get_payment_method(method_id)
            
            with transaction.atomic():
                # Log deletion
                from ..database_models.audit_model import AuditLog
                AuditLog.log_deletion(
                    payment_method,
                    deleted_by,
                    description=f"Deleted payment method: {payment_method.get_method_display()}"
                )
                
                # Delete payment method
                payment_method.delete()
                
                # Send notification
                Notification.objects.create(
                    advertiser=payment_method.billing_profile.advertiser,
                    user=deleted_by,
                    title='Payment Method Deleted',
                    message=f'Payment method "{payment_method.get_method_display()}" has been deleted.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                return True
                
        except PaymentMethod.DoesNotExist:
            raise BillingNotFoundError(f"Payment method {method_id} not found")
        except Exception as e:
            logger.error(f"Error deleting payment method {method_id}: {str(e)}")
            return False
    
    @staticmethod
    def verify_payment_method(method_id: UUID, verified_by: Optional[User] = None) -> bool:
        """Verify payment method."""
        try:
            payment_method = PaymentService.get_payment_method(method_id)
            
            with transaction.atomic():
                payment_method.is_verified = True
                payment_method.verification_date = timezone.now()
                payment_method.verified_by = verified_by
                payment_method.save(update_fields=['is_verified', 'verification_date', 'verified_by'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=payment_method.billing_profile.advertiser,
                    user=payment_method.billing_profile.advertiser.user,
                    title='Payment Method Verified',
                    message=f'Your payment method has been verified successfully.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log verification
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='verify',
                    object_type='PaymentMethod',
                    object_id=str(payment_method.id),
                    user=verified_by,
                    advertiser=payment_method.billing_profile.advertiser,
                    description=f"Verified payment method: {payment_method.get_method_display()}"
                )
                
                return True
                
        except PaymentMethod.DoesNotExist:
            raise BillingNotFoundError(f"Payment method {method_id} not found")
        except Exception as e:
            logger.error(f"Error verifying payment method {method_id}: {str(e)}")
            return False
    
    @staticmethod
    def process_payment(payment_data: Dict[str, Any], processed_by: Optional[User] = None) -> Dict[str, Any]:
        """Process payment transaction."""
        try:
            billing_profile_id = payment_data.get('billing_profile_id')
            amount = Decimal(str(payment_data.get('amount', 0)))
            payment_method_id = payment_data.get('payment_method_id')
            
            if not billing_profile_id or not amount or not payment_method_id:
                raise BillingValidationError("billing_profile_id, amount, and payment_method_id are required")
            
            billing_profile = BillingService.get_billing_profile(billing_profile_id)
            payment_method = PaymentService.get_payment_method(payment_method_id)
            
            with transaction.atomic():
                # Create transaction record
                transaction = PaymentTransaction.objects.create(
                    advertiser=billing_profile.advertiser,
                    billing_profile=billing_profile,
                    payment_method=payment_method,
                    transaction_id=PaymentService._generate_transaction_id(),
                    amount=amount,
                    transaction_type='payment',
                    currency=billing_profile.default_currency,
                    status='pending',
                    processed_by=processed_by
                )
                
                # Process payment (this would integrate with payment gateway)
                payment_result = PaymentService._process_with_gateway(
                    transaction,
                    payment_method,
                    payment_data
                )
                
                # Update transaction status
                if payment_result['success']:
                    transaction.status = 'completed'
                    transaction.gateway_transaction_id = payment_result.get('gateway_transaction_id')
                    transaction.gateway_response = payment_result.get('gateway_response')
                    transaction.completed_at = timezone.now()
                    
                    # Update credit available
                    BillingService.update_credit_available(
                        billing_profile.id,
                        amount,
                        'deposit'
                    )
                    
                    # Send notification
                    Notification.objects.create(
                        advertiser=billing_profile.advertiser,
                        user=processed_by,
                        title='Payment Processed',
                        message=f'Payment of ${amount} has been processed successfully.',
                        notification_type='system',
                        priority='medium',
                        channels=['in_app']
                    )
                else:
                    transaction.status = 'failed'
                    transaction.gateway_response = payment_result.get('error_message')
                    transaction.error_message = payment_result.get('error_message')
                    
                    # Send notification
                    Notification.objects.create(
                        advertiser=billing_profile.advertiser,
                        user=processed_by,
                        title='Payment Failed',
                        message=f'Payment of ${amount} has failed. Error: {payment_result.get("error_message", "Unknown error")}',
                        notification_type='system',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                
                transaction.save(update_fields=[
                    'status', 'gateway_transaction_id', 'gateway_response',
                    'completed_at', 'error_message'
                ])
                
                # Log processing
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='process_payment',
                    object_type='PaymentTransaction',
                    object_id=str(transaction.id),
                    user=processed_by,
                    advertiser=billing_profile.advertiser,
                    description=f"Processed payment: ${amount}"
                )
                
                return {
                    'success': payment_result['success'],
                    'transaction_id': str(transaction.id),
                    'status': transaction.status,
                    'error_message': transaction.error_message
                }
                
        except (BillingProfile.DoesNotExist, PaymentMethod.DoesNotExist) as e:
            raise BillingNotFoundError(str(e))
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            raise BillingServiceError(f"Failed to process payment: {str(e)}")
    
    @staticmethod
    def _generate_transaction_id() -> str:
        """Generate unique transaction ID."""
        import secrets
        return f"txn_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def _process_with_gateway(transaction: PaymentTransaction, payment_method: PaymentMethod,
                                 payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment with payment gateway."""
        # This would integrate with actual payment gateway (Stripe, PayPal, etc.)
        # For now, return mock response
        return {
            'success': True,
            'gateway_transaction_id': f"gw_{secrets.token_urlsafe(16)}",
            'gateway_response': 'Payment processed successfully'
        }
    
    @staticmethod
    def get_payment_methods_by_profile(billing_profile_id: UUID) -> List[PaymentMethod]:
        """Get all payment methods for billing profile."""
        try:
            return PaymentMethod.objects.filter(
                billing_profile_id=billing_profile_id,
                status='active'
            ).order_by('-is_default', '-created_at')
            
        except Exception as e:
            logger.error(f"Error getting payment methods {billing_profile_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_default_payment_method(billing_profile_id: UUID) -> Optional[PaymentMethod]:
        """Get default payment method for billing profile."""
        try:
            return PaymentMethod.objects.filter(
                billing_profile_id=billing_profile_id,
                is_default=True,
                status='active'
            ).first()
            
        except Exception as e:
            logger.error(f"Error getting default payment method {billing_profile_id}: {str(e)}")
            return None


class InvoiceService:
    """Service for managing invoice operations."""
    
    @staticmethod
    def create_invoice(data: Dict[str, Any], created_by: Optional[User] = None) -> Invoice:
        """Create a new invoice."""
        try:
            with transaction.atomic():
                # Generate invoice number
                invoice_number = InvoiceService._generate_invoice_number()
                
                invoice = Invoice.objects.create(
                    advertiser=data.get('advertiser'),
                    billing_profile=data.get('billing_profile'),
                    invoice_number=invoice_number,
                    invoice_date=data.get('invoice_date', date.today()),
                    due_date=data.get('due_date'),
                    amount=Decimal(str(data.get('amount', 0))),
                    tax_amount=Decimal(str(data.get('tax_amount', 0))),
                    total_amount=Decimal(str(data.get('total_amount', 0))),
                    currency=data.get('currency', 'USD'),
                    status='draft',
                    line_items=data.get('line_items', []),
                    notes=data.get('notes', ''),
                    recipient_email=data.get('recipient_email'),
                    recipient_name=data.get('recipient_name', ''),
                    recipient_address=data.get('recipient_address', ''),
                    recipient_city=data.get('recipient_city', ''),
                    recipient_state=data.get('recipient_state', ''),
                    recipient_country=data.get('recipient_country', ''),
                    recipient_postal_code=data.get('recipient_postal_code', ''),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=invoice.advertiser,
                    user=created_by,
                    title='Invoice Created',
                    message=f'Invoice #{invoice_number} has been created successfully.',
                    notification_type='system',
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
                
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            raise BillingServiceError(f"Failed to create invoice: {str(e)}")
    
    @staticmethod
    def _generate_invoice_number() -> str:
        """Generate unique invoice number."""
        from ..database_models.billing_model import Invoice
        import datetime
        
        # Get current month and year
        now = datetime.datetime.now()
        month_year = now.strftime('%Y%m')
        
        # Get count for this month
        count = Invoice.objects.filter(
            created_at__year=now.year,
            created_at__month=now.month
        ).count()
        
        return f"INV-{month_year}-{count + 1:04d}"
    
    @staticmethod
    def update_invoice(invoice_id: UUID, data: Dict[str, Any],
                        updated_by: Optional[User] = None) -> Invoice:
        """Update invoice."""
        try:
            invoice = InvoiceService.get_invoice(invoice_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update fields
                for field in ['due_date', 'amount', 'tax_amount', 'total_amount',
                             'currency', 'line_items', 'notes', 'recipient_email',
                             'recipient_name', 'recipient_address', 'recipient_city',
                             'recipient_state', 'recipient_country', 'recipient_postal_code']:
                    if field in data:
                        old_value = getattr(invoice, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(invoice, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                # Recalculate totals if amount or tax changed
                if 'amount' in changed_fields or 'tax_amount' in changed_fields:
                    invoice.total_amount = invoice.amount + invoice.tax_amount
                    changed_fields['total_amount'] = {
                        'old': invoice.total_amount,
                        'new': invoice.total_amount
                    }
                
                invoice.modified_by = updated_by
                invoice.save()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        invoice,
                        changed_fields,
                        updated_by,
                        description=f"Updated invoice: {invoice.invoice_number}"
                    )
                
                return invoice
                
        except Invoice.DoesNotExist:
            raise BillingNotFoundError(f"Invoice {invoice_id} not found")
        except Exception as e:
            logger.error(f"Error updating invoice {invoice_id}: {str(e)}")
            raise BillingServiceError(f"Failed to update invoice: {str(e)}")
    
    @staticmethod
    def get_invoice(invoice_id: UUID) -> Invoice:
        """Get invoice by ID."""
        try:
            return Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            raise BillingNotFoundError(f"Invoice {invoice_id} not found")
    
    @staticmethod
    def list_invoices(advertiser_id: Optional[UUID] = None,
                      filters: Optional[Dict[str, Any]] = None,
                      page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List invoices with filtering and pagination."""
        try:
            queryset = Invoice.objects.all()
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'invoice_date' in filters:
                    queryset = queryset.filter(invoice_date=filters['invoice_date'])
                if 'due_date' in filters:
                    queryset = queryset.filter(due_date=filters['due_date'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(invoice_number__icontains=search) |
                        Q(recipient_name__icontains=search) |
                        Q(recipient_email__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            invoices = queryset[offset:offset + page_size]
            
            return {
                'invoices': invoices,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing invoices: {str(e)}")
            raise BillingServiceError(f"Failed to list invoices: {str(e)}")
    
    @staticmethod
    def send_invoice(invoice_id: UUID, sent_by: Optional[User] = None) -> bool:
        """Send invoice to recipient."""
        try:
            invoice = InvoiceService.get_invoice(invoice_id)
            
            with transaction.atomic():
                # Update status
                invoice.status = 'sent'
                invoice.sent_at = timezone.now()
                invoice.save(update_fields=['status', 'sent_at'])
                
                # Send email (mock implementation)
                # This would integrate with email service
                success = InvoiceService._send_invoice_email(invoice)
                
                if success:
                    # Send notification
                    Notification.objects.create(
                        advertiser=invoice.advertiser,
                        user=sent_by,
                        title='Invoice Sent',
                        message=f'Invoice #{invoice.invoice_number} has been sent to {invoice.recipient_email}.',
                        notification_type='system',
                        priority='medium',
                        channels=['in_app']
                    )
                    
                    # Log sending
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_action(
                        action='send',
                        object_type='Invoice',
                        object_id=str(invoice.id),
                        user=sent_by,
                        advertiser=invoice.advertiser,
                        description=f"Sent invoice: {invoice.invoice_number}"
                    )
                
                return success
                
        except Invoice.DoesNotExist:
            raise BillingNotFoundError(f"Invoice {invoice_id} not found")
        except Exception as e:
            logger.error(f"Error sending invoice {invoice_id}: {str(e)}")
            return False
    
    @staticmethod
    def _send_invoice_email(invoice: Invoice) -> bool:
        """Send invoice email."""
        try:
            # This would implement actual email sending
            # For now, return success
            return True
        except Exception as e:
            logger.error(f"Error sending invoice email: {str(e)}")
            return False
    
    @staticmethod
    def mark_as_paid(invoice_id: UUID, payment_transaction_id: Optional[UUID] = None,
                       paid_by: Optional[User] = None) -> bool:
        """Mark invoice as paid."""
        try:
            invoice = InvoiceService.get_invoice(invoice_id)
            
            with transaction.atomic():
                invoice.status = 'paid'
                invoice.paid_at = timezone.now()
                invoice.payment_transaction_id = payment_transaction_id
                invoice.save(update_fields=['status', 'paid_at', 'payment_transaction_id'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=invoice.advertiser,
                    user=paid_by,
                    title='Invoice Paid',
                    message=f'Invoice #{invoice.invoice_number} has been marked as paid.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log payment
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='mark_paid',
                    object_type='Invoice',
                    object_id=str(invoice.id),
                    user=paid_by,
                    advertiser=invoice.advertiser,
                    description=f"Marked invoice as paid: {invoice.invoice_number}"
                )
                
                return True
                
        except Invoice.DoesNotExist:
            raise BillingNotFoundError(f"Invoice {invoice_id} not found")
        except Exception as e:
            logger.error(f"Error marking invoice as paid {invoice_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_invoice_summary(invoice_id: UUID) -> Dict[str, Any]:
        """Get invoice summary."""
        try:
            invoice = InvoiceService.get_invoice(invoice_id)
            
            return {
                'basic_info': {
                    'id': str(invoice.id),
                    'invoice_number': invoice.invoice_number,
                    'invoice_date': invoice.invoice_date.isoformat(),
                    'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
                    'status': invoice.status
                },
                'amounts': {
                    'amount': float(invoice.amount),
                    'tax_amount': float(invoice.tax_amount),
                    'total_amount': float(invoice.total_amount),
                    'currency': invoice.currency
                },
                'recipient': {
                    'name': invoice.recipient_name,
                    'email': invoice.recipient_email,
                    'address': invoice.recipient_address,
                    'city': invoice.recipient_city,
                    'state': invoice.recipient_state,
                    'country': invoice.recipient_country,
                    'postal_code': invoice.recipient_postal_code
                },
                'line_items': invoice.line_items,
                'notes': invoice.notes,
                'created_at': invoice.created_at.isoformat(),
                'sent_at': invoice.sent_at.isoformat() if invoice.sent_at else None,
                'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None
            }
            
        except Invoice.DoesNotExist:
            raise BillingNotFoundError(f"Invoice {invoice_id} not found")
        except Exception as e:
            logger.error(f"Error getting invoice summary {invoice_id}: {str(e)}")
            raise BillingServiceError(f"Failed to get invoice summary: {str(e)}")


class TransactionService:
    """Service for managing payment transactions."""
    
    @staticmethod
    def get_transaction(transaction_id: UUID) -> PaymentTransaction:
        """Get transaction by ID."""
        try:
            return PaymentTransaction.objects.get(id=transaction_id)
        except PaymentTransaction.DoesNotExist:
            raise BillingNotFoundError(f"Transaction {transaction_id} not found")
    
    @staticmethod
    def list_transactions(advertiser_id: Optional[UUID] = None,
                           filters: Optional[Dict[str, Any]] = None,
                           page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List transactions with filtering and pagination."""
        try:
            queryset = PaymentTransaction.objects.all()
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'transaction_type' in filters:
                    queryset = queryset.filter(transaction_type=filters['transaction_type'])
                if 'payment_method' in filters:
                    queryset = queryset.filter(payment_method=filters['payment_method'])
                if 'created_at' in filters:
                    queryset = queryset.filter(created_at=filters['created_at'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(transaction_id__icontains=search) |
                        Q(gateway_transaction_id__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            transactions = queryset[offset:offset + page_size]
            
            return {
                'transactions': transactions,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing transactions: {str(e)}")
            raise BillingServiceError(f"Failed to list transactions: {str(e)}")
    
    @staticmethod
    def get_transaction_summary(transaction_id: UUID) -> Dict[str, Any]:
        """Get transaction summary."""
        try:
            transaction = TransactionService.get_transaction(transaction_id)
            
            return {
                'basic_info': {
                    'id': str(transaction.id),
                    'transaction_id': transaction.transaction_id,
                    'transaction_type': transaction.transaction_type,
                    'amount': float(transaction.amount),
                    'currency': transaction.currency,
                    'status': transaction.status,
                    'created_at': transaction.created_at.isoformat(),
                    'completed_at': transaction.completed_at.isoformat() if transaction.completed_at else None
                },
                'payment_method': {
                    'id': str(transaction.payment_method.id),
                    'type': transaction.payment_method.method_type,
                    'name': transaction.payment_method.method_name
                } if transaction.payment_method else None,
                'gateway': {
                    'transaction_id': transaction.gateway_transaction_id,
                    'response': transaction.gateway_response
                },
                'billing_profile': {
                    'id': str(transaction.billing_profile.id),
                    'company_name': transaction.billing_profile.company_name
                } if transaction.billing_profile else None,
                'error_message': transaction.error_message
            }
            
        except PaymentTransaction.DoesNotExist:
            raise BillingNotFoundError(f"Transaction {transaction_id} not found")
        except Exception as e:
            logger.error(f"Error getting transaction summary {transaction_id}: {str(e)}")
            raise BillingServiceError(f"Failed to get transaction summary: {str(e)}")
