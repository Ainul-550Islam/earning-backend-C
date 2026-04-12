"""
Billing Management Serializers

This module contains Django REST Framework serializers for billing
management data validation and serialization.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from rest_framework import serializers
from django.core.exceptions import ValidationError

from ..database_models.billing_model import BillingProfile, PaymentMethod, Invoice, PaymentTransaction
from ..database_models.advertiser_model import Advertiser
from ..enums import *
from ..validators import *


class BillingProfileSerializer(serializers.ModelSerializer):
    """Serializer for BillingProfile model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = BillingProfile
        fields = [
            'id', 'advertiser', 'advertiser_name', 'company_name', 'trade_name',
            'billing_email', 'billing_phone', 'billing_contact', 'billing_title',
            'billing_address_line1', 'billing_address_line2', 'billing_city',
            'billing_state', 'billing_country', 'billing_postal_code',
            'billing_cycle', 'payment_terms', 'auto_charge', 'auto_charge_threshold',
            'credit_limit', 'credit_available', 'spending_limit', 'tax_exempt',
            'tax_rate', 'tax_region', 'default_currency', 'pricing_model',
            'is_verified', 'verification_date', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'credit_available',
            'verification_date', 'created_at', 'updated_at'
        ]


class BillingProfileDetailSerializer(BillingProfileSerializer):
    """Detailed serializer for BillingProfile model with additional fields."""
    
    payment_methods = serializers.SerializerMethodField()
    recent_invoices = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()
    credit_utilization = serializers.SerializerMethodField()
    
    class Meta(BillingProfileSerializer.Meta):
        fields = BillingProfileSerializer.Meta.fields + [
            'payment_methods', 'recent_invoices', 'recent_transactions',
            'credit_utilization'
        ]
    
    def get_payment_methods(self, obj):
        """Get payment methods for billing profile."""
        methods = PaymentMethod.objects.filter(
            billing_profile=obj,
            status='active'
        ).order_by('-is_default', '-created_at')[:5]
        
        return [
            {
                'id': str(method.id),
                'method_type': method.method_type,
                'method_name': method.method_name,
                'is_default': method.is_default,
                'is_verified': method.is_verified,
                'created_at': method.created_at.isoformat()
            }
            for method in methods
        ]
    
    def get_recent_invoices(self, obj):
        """Get recent invoices for billing profile."""
        invoices = Invoice.objects.filter(
            advertiser=obj.advertiser
        ).order_by('-created_at')[:5]
        
        return [
            {
                'id': str(invoice.id),
                'invoice_number': invoice.invoice_number,
                'amount': float(invoice.total_amount),
                'status': invoice.status,
                'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
                'created_at': invoice.created_at.isoformat()
            }
            for invoice in invoices
        ]
    
    def get_recent_transactions(self, obj):
        """Get recent transactions for billing profile."""
        transactions = PaymentTransaction.objects.filter(
            advertiser=obj.advertiser
        ).order_by('-created_at')[:5]
        
        return [
            {
                'id': str(transaction.id),
                'transaction_id': transaction.transaction_id,
                'amount': float(transaction.amount),
                'transaction_type': transaction.transaction_type,
                'status': transaction.status,
                'created_at': transaction.created_at.isoformat()
            }
            for transaction in transactions
        ]
    
    def get_credit_utilization(self, obj):
        """Get credit utilization percentage."""
        if obj.credit_limit > 0:
            utilization = ((obj.credit_limit - obj.credit_available) / obj.credit_limit) * 100
            return float(utilization)
        return 0.0


class BillingProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating BillingProfile."""
    
    class Meta:
        model = BillingProfile
        fields = [
            'advertiser', 'company_name', 'trade_name', 'billing_email',
            'billing_phone', 'billing_contact', 'billing_title',
            'billing_address_line1', 'billing_address_line2', 'billing_city',
            'billing_state', 'billing_country', 'billing_postal_code',
            'billing_cycle', 'payment_terms', 'auto_charge',
            'auto_charge_threshold', 'credit_limit', 'spending_limit',
            'tax_exempt', 'tax_rate', 'tax_region', 'default_currency',
            'pricing_model', 'status'
        ]
    
    def validate(self, attrs):
        """Validate billing profile data."""
        # Validate email format
        billing_email = attrs.get('billing_email')
        if billing_email:
            from django.core.validators import validate_email
            try:
                validate_email(billing_email)
            except ValidationError:
                raise serializers.ValidationError("Invalid email format")
        
        # Validate credit limit
        credit_limit = attrs.get('credit_limit')
        spending_limit = attrs.get('spending_limit')
        
        if credit_limit and credit_limit < 0:
            raise serializers.ValidationError("Credit limit cannot be negative")
        
        if spending_limit and spending_limit < 0:
            raise serializers.ValidationError("Spending limit cannot be negative")
        
        # Validate tax rate
        tax_rate = attrs.get('tax_rate')
        if tax_rate is not None and (tax_rate < 0 or tax_rate > 100):
            raise serializers.ValidationError("Tax rate must be between 0 and 100")
        
        # Validate auto-charge threshold
        auto_charge_threshold = attrs.get('auto_charge_threshold')
        if auto_charge_threshold is not None and (auto_charge_threshold < 0 or auto_charge_threshold > 100):
            raise serializers.ValidationError("Auto-charge threshold must be between 0 and 100")
        
        return attrs
    
    def validate_billing_email(self, value):
        """Validate billing email."""
        if value:
            from django.core.validators import validate_email
            try:
                validate_email(value)
            except ValidationError:
                raise serializers.ValidationError("Invalid email format")
        return value
    
    def validate_credit_limit(self, value):
        """Validate credit limit."""
        if value and value < 0:
            raise serializers.ValidationError("Credit limit cannot be negative")
        return value
    
    def validate_spending_limit(self, value):
        """Validate spending limit."""
        if value and value < 0:
            raise serializers.ValidationError("Spending limit cannot be negative")
        return value
    
    def validate_tax_rate(self, value):
        """Validate tax rate."""
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Tax rate must be between 0 and 100")
        return value
    
    def validate_auto_charge_threshold(self, value):
        """Validate auto-charge threshold."""
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Auto-charge threshold must be between 0 and 100")
        return value


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for PaymentMethod model."""
    
    billing_profile_name = serializers.CharField(source='billing_profile.company_name', read_only=True)
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'billing_profile', 'billing_profile_name', 'method_type',
            'method_name', 'cardholder_name', 'card_number', 'card_expiry',
            'bank_account_type', 'paypal_email', 'stripe_customer_id',
            'stripe_payment_method_id', 'is_default', 'is_verified',
            'verification_date', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'billing_profile', 'billing_profile_name', 'card_number',
            'card_expiry', 'card_cvv', 'bank_account_number',
            'bank_routing_number', 'verification_date', 'created_at', 'updated_at'
        ]
    
    def to_representation(self, instance):
        """Mask sensitive data in representation."""
        data = super().to_representation(instance)
        
        # Mask card number
        if data.get('card_number'):
            card_number = data['card_number']
            if len(card_number) > 4:
                data['card_number'] = f"****-****-****-{card_number[-4:]}"
        
        # Mask card expiry
        if data.get('card_expiry'):
            expiry = data['card_expiry']
            if len(expiry) >= 2:
                data['card_expiry'] = f"**/{expiry[-2:]}"
        
        return data


class PaymentMethodDetailSerializer(PaymentMethodSerializer):
    """Detailed serializer for PaymentMethod model with additional fields."""
    
    billing_profile_details = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()
    
    class Meta(PaymentMethodSerializer.Meta):
        fields = PaymentMethodSerializer.Meta.fields + [
            'billing_profile_details', 'recent_transactions'
        ]
    
    def get_billing_profile_details(self, obj):
        """Get billing profile details."""
        return {
            'id': str(obj.billing_profile.id),
            'company_name': obj.billing_profile.company_name,
            'currency': obj.billing_profile.default_currency
        }
    
    def get_recent_transactions(self, obj):
        """Get recent transactions for payment method."""
        transactions = PaymentTransaction.objects.filter(
            payment_method=obj
        ).order_by('-created_at')[:5]
        
        return [
            {
                'id': str(transaction.id),
                'transaction_id': transaction.transaction_id,
                'amount': float(transaction.amount),
                'transaction_type': transaction.transaction_type,
                'status': transaction.status,
                'created_at': transaction.created_at.isoformat()
            }
            for transaction in transactions
        ]


class PaymentMethodCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating PaymentMethod."""
    
    class Meta:
        model = PaymentMethod
        fields = [
            'billing_profile', 'method_type', 'method_name', 'cardholder_name',
            'card_number', 'card_expiry', 'card_cvv', 'bank_account_number',
            'bank_routing_number', 'bank_account_type', 'paypal_email',
            'stripe_customer_id', 'stripe_payment_method_id',
            'is_default', 'status'
        ]
    
    def validate(self, attrs):
        """Validate payment method data."""
        method_type = attrs.get('method_type')
        
        # Validate required fields based on method type
        if method_type == 'credit_card':
            required_fields = ['card_number', 'card_expiry', 'card_cvv', 'cardholder_name']
            for field in required_fields:
                if not attrs.get(field):
                    raise serializers.ValidationError(f"{field} is required for credit card")
        
        elif method_type == 'debit_card':
            required_fields = ['card_number', 'card_expiry', 'card_cvv', 'cardholder_name']
            for field in required_fields:
                if not attrs.get(field):
                    raise serializers.ValidationError(f"{field} is required for debit card")
        
        elif method_type == 'bank_account':
            required_fields = ['bank_account_number', 'bank_routing_number']
            for field in required_fields:
                if not attrs.get(field):
                    raise serializers.ValidationError(f"{field} is required for bank account")
        
        elif method_type == 'paypal':
            if not attrs.get('paypal_email'):
                raise serializers.ValidationError("paypal_email is required for PayPal")
        
        # Validate card number format
        card_number = attrs.get('card_number')
        if card_number and not PaymentMethodCreateSerializer._validate_card_number(card_number):
            raise serializers.ValidationError("Invalid card number format")
        
        # Validate email for PayPal
        paypal_email = attrs.get('paypal_email')
        if paypal_email:
            from django.core.validators import validate_email
            try:
                validate_email(paypal_email)
            except ValidationError:
                raise serializers.ValidationError("Invalid PayPal email format")
        
        return attrs
    
    @staticmethod
    def _validate_card_number(card_number: str) -> bool:
        """Validate card number using Luhn algorithm."""
        # Remove spaces and dashes
        card_number = card_number.replace(' ', '').replace('-', '')
        
        # Check if all digits
        if not card_number.isdigit():
            return False
        
        # Luhn algorithm
        total = 0
        reverse_digits = card_number[::-1]
        
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n = (n // 10) + (n % 10)
            total += n
        
        return total % 10 == 0
    
    def validate_paypal_email(self, value):
        """Validate PayPal email."""
        if value:
            from django.core.validators import validate_email
            try:
                validate_email(value)
            except ValidationError:
                raise serializers.ValidationError("Invalid email format")
        return value


class PaymentMethodUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating PaymentMethod."""
    
    class Meta:
        model = PaymentMethod
        fields = [
            'method_name', 'cardholder_name', 'bank_account_type', 'paypal_email',
            'stripe_customer_id', 'stripe_payment_method_id',
            'is_default', 'status'
        ]
    
    def validate_paypal_email(self, value):
        """Validate PayPal email."""
        if value:
            from django.core.validators import validate_email
            try:
                validate_email(value)
            except ValidationError:
                raise serializers.ValidationError("Invalid email format")
        return value


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    billing_profile_name = serializers.CharField(source='billing_profile.company_name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'advertiser', 'advertiser_name', 'billing_profile',
            'billing_profile_name', 'invoice_number', 'invoice_date', 'due_date',
            'amount', 'tax_amount', 'total_amount', 'currency', 'status',
            'line_items', 'notes', 'recipient_email', 'recipient_name',
            'recipient_address', 'recipient_city', 'recipient_state',
            'recipient_country', 'recipient_postal_code', 'sent_at',
            'paid_at', 'payment_transaction_id', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'billing_profile',
            'billing_profile_name', 'invoice_number', 'sent_at', 'paid_at',
            'payment_transaction_id', 'created_at', 'updated_at'
        ]


class InvoiceDetailSerializer(InvoiceSerializer):
    """Detailed serializer for Invoice model with additional fields."""
    
    payment_transaction = serializers.SerializerMethodField()
    billing_profile_details = serializers.SerializerMethodField()
    
    class Meta(InvoiceSerializer.Meta):
        fields = InvoiceSerializer.Meta.fields + [
            'payment_transaction', 'billing_profile_details'
        ]
    
    def get_payment_transaction(self, obj):
        """Get payment transaction details."""
        if obj.payment_transaction_id:
            try:
                transaction = PaymentTransaction.objects.get(id=obj.payment_transaction_id)
                return {
                    'id': str(transaction.id),
                    'transaction_id': transaction.transaction_id,
                    'amount': float(transaction.amount),
                    'status': transaction.status
                }
            except PaymentTransaction.DoesNotExist:
                pass
        return None
    
    def get_billing_profile_details(self, obj):
        """Get billing profile details."""
        if obj.billing_profile:
            return {
                'id': str(obj.billing_profile.id),
                'company_name': obj.billing_profile.company_name,
                'billing_email': obj.billing_profile.billing_email
            }
        return None


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Invoice."""
    
    class Meta:
        model = Invoice
        fields = [
            'advertiser', 'billing_profile', 'invoice_date', 'due_date',
            'amount', 'tax_amount', 'currency', 'line_items', 'notes',
            'recipient_email', 'recipient_name', 'recipient_address',
            'recipient_city', 'recipient_state', 'recipient_country',
            'recipient_postal_code'
        ]
    
    def validate(self, attrs):
        """Validate invoice data."""
        # Validate date range
        invoice_date = attrs.get('invoice_date')
        due_date = attrs.get('due_date')
        
        if invoice_date and due_date:
            if invoice_date >= due_date:
                raise serializers.ValidationError("Invoice date must be before due date")
        
        # Validate amounts
        amount = attrs.get('amount')
        tax_amount = attrs.get('tax_amount')
        
        if amount and amount < 0:
            raise serializers.ValidationError("Amount cannot be negative")
        
        if tax_amount and tax_amount < 0:
            raise serializers.ValidationError("Tax amount cannot be negative")
        
        # Validate email
        recipient_email = attrs.get('recipient_email')
        if recipient_email:
            from django.core.validators import validate_email
            try:
                validate_email(recipient_email)
            except ValidationError:
                raise serializers.ValidationError("Invalid recipient email format")
        
        return attrs
    
    def validate_invoice_date(self, value):
        """Validate invoice date."""
        if value and value > date.today():
            raise serializers.ValidationError("Invoice date cannot be in the future")
        return value
    
    def validate_amount(self, value):
        """Validate amount."""
        if value and value < 0:
            raise serializers.ValidationError("Amount cannot be negative")
        return value
    
    def validate_tax_amount(self, value):
        """Validate tax amount."""
        if value and value < 0:
            raise serializers.ValidationError("Tax amount cannot be negative")
        return value
    
    def validate_recipient_email(self, value):
        """Validate recipient email."""
        if value:
            from django.core.validators import validate_email
            try:
                validate_email(value)
            except ValidationError:
                raise serializers.ValidationError("Invalid email format")
        return value


class InvoiceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Invoice."""
    
    class Meta:
        model = Invoice
        fields = [
            'due_date', 'amount', 'tax_amount', 'line_items', 'notes',
            'recipient_email', 'recipient_name', 'recipient_address',
            'recipient_city', 'recipient_state', 'recipient_country',
            'recipient_postal_code'
        ]
    
    def validate(self, attrs):
        """Validate invoice update data."""
        # Validate date range
        due_date = attrs.get('due_date')
        if due_date:
            instance = self.instance
            if instance and instance.invoice_date >= due_date:
                raise serializers.ValidationError("Due date must be after invoice date")
        
        # Validate amounts
        amount = attrs.get('amount')
        tax_amount = attrs.get('tax_amount')
        
        if amount and amount < 0:
            raise serializers.ValidationError("Amount cannot be negative")
        
        if tax_amount and tax_amount < 0:
            raise serializers.ValidationError("Tax amount cannot be negative")
        
        return attrs
    
    def validate_amount(self, value):
        """Validate amount."""
        if value and value < 0:
            raise serializers.ValidationError("Amount cannot be negative")
        return value
    
    def validate_tax_amount(self, value):
        """Validate tax amount."""
        if value and value < 0:
            raise serializers.ValidationError("Tax amount cannot be negative")
        return value


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """Serializer for PaymentTransaction model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    billing_profile_name = serializers.CharField(source='billing_profile.company_name', read_only=True)
    payment_method_type = serializers.CharField(source='payment_method.method_type', read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'advertiser', 'advertiser_name', 'billing_profile',
            'billing_profile_name', 'payment_method', 'payment_method_type',
            'transaction_id', 'gateway_transaction_id', 'amount',
            'transaction_type', 'currency', 'status', 'gateway_response',
            'error_message', 'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'billing_profile',
            'billing_profile_name', 'transaction_id', 'gateway_transaction_id',
            'completed_at', 'created_at', 'updated_at'
        ]


# Request serializers

class PaymentRequestSerializer(serializers.Serializer):
    """Serializer for payment requests."""
    
    billing_profile_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    payment_method_id = serializers.UUIDField()
    
    def validate_billing_profile_id(self, value):
        """Validate billing profile exists."""
        try:
            BillingProfile.objects.get(id=value)
        except BillingProfile.DoesNotExist:
            raise serializers.ValidationError("Billing profile not found")
        return value
    
    def validate_payment_method_id(self, value):
        """Validate payment method exists."""
        try:
            PaymentMethod.objects.get(id=value)
        except PaymentMethod.DoesNotExist:
            raise serializers.ValidationError("Payment method not found")
        return value


class TaxCalculationRequestSerializer(serializers.Serializer):
    """Serializer for tax calculation requests."""
    
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    
    def validate_amount(self, value):
        """Validate amount."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value


class CreditUpdateRequestSerializer(serializers.Serializer):
    """Serializer for credit update requests."""
    
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = serializers.ChoiceField(
        choices=['spend', 'refund', 'deposit']
    )
    
    def validate_amount(self, value):
        """Validate amount."""
        if value == 0:
            raise serializers.ValidationError("Amount cannot be zero")
        return value


# Response serializers

class BillingSummarySerializer(serializers.Serializer):
    """Serializer for billing summary response."""
    
    billing_profile = serializers.DictField(read_only=True)
    recent_invoices = serializers.ListField(read_only=True)
    recent_transactions = serializers.ListField(read_only=True)


class TaxCalculationResponseSerializer(serializers.Serializer):
    """Serializer for tax calculation response."""
    
    amount = serializers.FloatField(read_only=True)
    tax_amount = serializers.FloatField(read_only=True)
    total_amount = serializers.FloatField(read_only=True)
    tax_rate = serializers.FloatField(read_only=True)


class PaymentResponseSerializer(serializers.Serializer):
    """Serializer for payment response."""
    
    success = serializers.BooleanField(read_only=True)
    transaction_id = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    error_message = serializers.CharField(read_only=True, required=False)


class InvoiceSummarySerializer(serializers.Serializer):
    """Serializer for invoice summary response."""
    
    basic_info = serializers.DictField(read_only=True)
    amounts = serializers.DictField(read_only=True)
    recipient = serializers.DictField(read_only=True)
    line_items = serializers.ListField(read_only=True)
    notes = serializers.CharField(read_only=True)
    created_at = serializers.CharField(read_only=True)
    sent_at = serializers.CharField(read_only=True)
    paid_at = serializers.CharField(read_only=True)


class TransactionSummarySerializer(serializers.Serializer):
    """Serializer for transaction summary response."""
    
    basic_info = serializers.DictField(read_only=True)
    payment_method = serializers.DictField(read_only=True)
    gateway = serializers.DictField(read_only=True)
    billing_profile = serializers.DictField(read_only=True)
    error_message = serializers.CharField(read_only=True)


class ActionResponseSerializer(serializers.Serializer):
    """Serializer for action responses."""
    
    message = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)


class BillingAlertSerializer(serializers.Serializer):
    """Serializer for billing alerts."""
    
    type = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    created_at = serializers.CharField(read_only=True)


class BillingAlertsResponseSerializer(serializers.Serializer):
    """Serializer for billing alerts response."""
    
    alerts = BillingAlertSerializer(many=True, read_only=True)
    has_alerts = serializers.BooleanField(read_only=True)
