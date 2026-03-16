# wallet/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Wallet, WalletTransaction, UserPaymentMethod, Withdrawal, WalletWebhookLog
from decimal import Decimal, InvalidOperation
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ============================================
# BULLETPROOF HELPER FUNCTIONS
# ============================================

def get_safe_value(data, key, default=None, expected_type=None):
    """
    Null-safe value extraction with type validation
    """
    try:
        # Using dictionary get for API data
        if isinstance(data, dict):
            value = data.get(key, default)
        # Using getattr for objects/models
        else:
            value = getattr(data, key, default)
        
        # Sentinel value check
        NOT_FOUND = object()
        if value is NOT_FOUND or value is None:
            return default
        
        # Type validation
        if expected_type and value is not None:
            if expected_type == Decimal:
                try:
                    return Decimal(str(value))
                except (InvalidOperation, ValueError):
                    logger.warning(f"Invalid Decimal conversion for key {key}: {value}")
                    return default
            elif expected_type == datetime:
                if isinstance(value, str):
                    try:
                        from django.utils.dateparse import parse_datetime
                        parsed = parse_datetime(value)
                        if parsed:
                            return parsed
                    except (ValueError, TypeError):
                        pass
                return default if not isinstance(value, datetime) else value
            elif not isinstance(value, expected_type):
                logger.warning(f"Type mismatch for {key}: expected {expected_type}, got {type(value)}")
                return default
        
        return value
    except (AttributeError, KeyError, TypeError) as e:
        logger.debug(f"Safe get failed for {key}: {e}")
        return default


class CircuitBreaker:
    """
    Simple Circuit Breaker Pattern for external API calls
    """
    def __init__(self, failure_threshold=3, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __enter__(self):
        if self.state == 'OPEN':
            if self.last_failure_time:
                from django.utils import timezone
                elapsed = (timezone.now() - self.last_failure_time).total_seconds()
                if elapsed > self.recovery_timeout:
                    self.state = 'HALF_OPEN'
                else:
                    raise ConnectionError("Circuit breaker is OPEN")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.record_failure()
            return False
        else:
            self.record_success()
            return True
    
    def record_failure(self):
        self.failures += 1
        from django.utils import timezone
        self.last_failure_time = timezone.now()
        
        if self.failures >= self.failure_threshold:
            self.state = 'OPEN'
            logger.error(f"Circuit breaker triggered to OPEN state after {self.failures} failures")
    
    def record_success(self):
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
        self.failures = 0
        self.last_failure_time = None


# ============================================
# MODEL SERIALIZERS
# ============================================

class WalletSerializer(serializers.ModelSerializer):
    """Bulletproof Wallet Serializer"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    # Null-safe calculated fields
    available_balance = serializers.SerializerMethodField()
    is_bonus_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'user', 'user_email', 'user_username',
            'current_balance', 'pending_balance', 'total_earned',
            'total_withdrawn', 'frozen_balance', 'bonus_balance',
            'bonus_expires_at', 'is_locked', 'locked_reason',
            'locked_at', 'currency', 'available_balance',
            'is_bonus_expired', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'current_balance', 'pending_balance', 'total_earned',
            'total_withdrawn', 'frozen_balance', 'created_at',
            'updated_at', 'is_locked', 'locked_at'
        ]
        extra_kwargs = {
            'user': {'write_only': True}
        }
    
    def get_available_balance(self, obj):
        """Null-safe available balance calculation"""
        try:
            current = get_safe_value(obj, 'current_balance', Decimal('0'), Decimal)
            frozen = get_safe_value(obj, 'frozen_balance', Decimal('0'), Decimal)
            return max(current - frozen, Decimal('0'))
        except (ValueError, TypeError, InvalidOperation) as e:
            logger.error(f"Error calculating available balance: {e}")
            return Decimal('0')
    
    def get_is_bonus_expired(self, obj):
        """Check if bonus has expired with null safety"""
        expires_at = get_safe_value(obj, 'bonus_expires_at')
        if not expires_at:
            return False
        
        from django.utils import timezone
        try:
            return expires_at < timezone.now()
        except (TypeError, ValueError):
            return True
    
    def validate(self, data):
        """Bulletproof validation with graceful degradation"""
        validated_data = super().validate(data)
        
        # Safe extraction of values
        currency = get_safe_value(validated_data, 'currency', 'BDT')
        if currency and len(currency) != 3:
            validated_data['currency'] = 'BDT'  # Graceful default
        
        # Ensure bonus balance is positive
        bonus = get_safe_value(validated_data, 'bonus_balance', Decimal('0'), Decimal)
        if bonus and bonus < 0:
            validated_data['bonus_balance'] = Decimal('0')
        
        return validated_data


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Bulletproof WalletTransaction Serializer"""
    wallet_owner = serializers.CharField(source='wallet.user.username', read_only=True)
    transaction_type_display = serializers.CharField(
        source='get_type_display', 
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )

    # ✅ FIX: Model field is `walletTransaction_id` (lowercase w, capital T)
    # Expose it as `transaction_id` so frontend stays clean
    transaction_id = serializers.UUIDField(
        source='walletTransaction_id',
        read_only=True
    )

    # Null-safe display fields
    created_by_email = serializers.SerializerMethodField()
    approved_by_email = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            'transaction_id',          # ✅ alias → walletTransaction_id
            'wallet', 'wallet_owner',
            'type', 'transaction_type_display',
            'amount', 'status', 'status_display',
            'reference_id', 'reference_type',
            'balance_before', 'balance_after',
            'description', 'metadata',
            'debit_account', 'credit_account',
            'is_reversed', 'reversed_by', 'reversed_at',
            'created_by', 'created_by_email',
            'approved_by', 'approved_by_email',
            'created_at', 'updated_at', 'approved_at'
        ]
        read_only_fields = [
            'transaction_id', 'balance_before', 'balance_after',
            'created_at', 'updated_at', 'approved_at',
            'is_reversed', 'reversed_by', 'reversed_at'
        ]

    def get_created_by_email(self, obj):
        """Null-safe email extraction"""
        return get_safe_value(obj.created_by, 'email', 'System') if obj.created_by else 'System'

    def get_approved_by_email(self, obj):
        """Null-safe email extraction"""
        return get_safe_value(obj.approved_by, 'email', '') if obj.approved_by else ''

    def validate_amount(self, value):
        """Bulletproof amount validation"""
        try:
            amount = Decimal(str(value))
            if amount == Decimal('0'):
                raise serializers.ValidationError("Amount cannot be zero")
            return amount
        except (InvalidOperation, ValueError, TypeError):
            logger.error(f"Invalid amount value: {value}")
            raise serializers.ValidationError("Invalid amount format")

    def validate(self, data):
        """Comprehensive validation with null safety"""
        validated_data = super().validate(data)

        # Check wallet lock status
        wallet = get_safe_value(self.instance, 'wallet') if self.instance else None
        if not wallet and validated_data.get('wallet'):
            wallet = validated_data['wallet']

        if wallet and get_safe_value(wallet, 'is_locked', False):
            raise serializers.ValidationError(
                "Wallet is locked. Please contact support."
            )

        # Ensure metadata is a dictionary
        metadata = get_safe_value(validated_data, 'metadata', {})
        if not isinstance(metadata, dict):
            validated_data['metadata'] = {}

        return validated_data


class UserPaymentMethodSerializer(serializers.ModelSerializer):
    """Bulletproof Payment Method Serializer"""
    method_display = serializers.CharField(source='get_method_type_display', read_only=True)
    
    class Meta:
        model = UserPaymentMethod
        fields = [
            'id', 'user', 'method_type', 'method_display',
            'account_number', 'account_name', 'is_verified',
            'is_primary', 'bank_name', 'branch_name',
            'routing_number', 'card_last_four', 'card_expiry',
            'created_at', 'updated_at', 'verified_at'
        ]
        extra_kwargs = {
            'user': {'required': False, 'read_only': True},  # ← এই line
        }
        read_only_fields = ['is_verified', 'verified_at', 'created_at', 'updated_at']
    
    def validate_account_number(self, value):
        """Safe account number validation"""
        if not value or not str(value).strip():
            raise serializers.ValidationError("Account number is required")
        
        # Remove spaces and special characters for validation
        cleaned = ''.join(filter(str.isalnum, str(value)))
        if len(cleaned) < 8:
            raise serializers.ValidationError("Invalid account number")
        
        return cleaned
    
    def validate(self, data):
        """Context-aware validation"""
        validated_data = super().validate(data)
        
        method_type = get_safe_value(validated_data, 'method_type', '')
        
        # Bank account validation
        if method_type == 'bank':
            if not get_safe_value(validated_data, 'bank_name', ''):
                raise serializers.ValidationError({
                    'bank_name': 'Bank name is required for bank accounts'
                })
        
        # Card validation
        elif method_type == 'card':
            card_expiry = get_safe_value(validated_data, 'card_expiry', '')
            if card_expiry:
                try:
                    month, year = map(int, card_expiry.split('/'))
                    from datetime import datetime
                    current_year = datetime.now().year % 100
                    current_month = datetime.now().month
                    
                    if year < current_year or (year == current_year and month < current_month):
                        raise serializers.ValidationError({
                            'card_expiry': 'Card has expired'
                        })
                except (ValueError, AttributeError):
                    raise serializers.ValidationError({
                        'card_expiry': 'Invalid expiry format (MM/YYYY)'
                    })
        
        return validated_data


class WithdrawalSerializer(serializers.ModelSerializer):
    """Bulletproof Withdrawal Serializer"""
    withdrawal_id = serializers.UUIDField(format='hex', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    payment_method_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Calculated fields with null safety
    processing_fee_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Withdrawal
        fields = [
            'id', 'withdrawal_id', 'user', 'user_email', 'wallet',
            'payment_method', 'payment_method_display',
            'amount', 'fee', 'net_amount',
            'status', 'status_display',
            'transaction', 'processed_by', 'processed_at',
            'rejection_reason', 'rejected_at',
            'gateway_reference', 'gateway_response',
            'processing_fee_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'withdrawal_id', 'net_amount', 'status',
            'processed_by', 'processed_at', 'rejected_at',
            'gateway_reference', 'gateway_response',
            'created_at', 'updated_at'
        ]
    
    def get_payment_method_display(self, obj):
        """Null-safe payment method display"""
        if obj.payment_method:
            return get_safe_value(obj.payment_method, 'account_number', 'N/A')
        return 'N/A'
    
    def get_processing_fee_percentage(self, obj):
        """Calculate fee percentage safely"""
        try:
            amount = get_safe_value(obj, 'amount', Decimal('0'), Decimal)
            fee = get_safe_value(obj, 'fee', Decimal('0'), Decimal)
            
            if amount > 0:
                return (fee / amount * 100).quantize(Decimal('0.01'))
            return Decimal('0')
        except (ZeroDivisionError, InvalidOperation, TypeError):
            return Decimal('0')
    
    def validate_amount(self, value):
        """Amount validation with circuit breaker for external checks"""
        try:
            amount = Decimal(str(value))
            
            # Minimum withdrawal amount
            if amount < Decimal('100'):
                raise serializers.ValidationError("Minimum withdrawal amount is 100")
            
            # Maximum withdrawal amount
            if amount > Decimal('50000'):
                raise serializers.ValidationError("Maximum withdrawal amount is 50,000")
            
            # Check wallet balance (simulated - in real app, check against user's wallet)
            request = self.context.get('request')
            if request and request.user:
                try:
                    wallet = request.user.wallet
                    available = get_safe_value(wallet, 'available_balance', Decimal('0'), Decimal)
                    if amount > available:
                        raise serializers.ValidationError(
                            f"Insufficient balance. Available: {available}"
                        )
                except AttributeError:
                    pass
            
            return amount
        except (InvalidOperation, ValueError, TypeError) as e:
            logger.error(f"Withdrawal amount validation failed: {e}")
            raise serializers.ValidationError("Invalid amount")
    
    def validate(self, data):
        """Comprehensive withdrawal validation"""
        validated_data = super().validate(data)
        
        # Check if payment method is verified
        payment_method = get_safe_value(validated_data, 'payment_method')
        if payment_method and not get_safe_value(payment_method, 'is_verified', False):
            raise serializers.ValidationError({
                'payment_method': 'Payment method must be verified'
            })
        
        return validated_data


class WalletWebhookLogSerializer(serializers.ModelSerializer):
    """Bulletproof Webhook Log Serializer"""
    webhook_type_display = serializers.CharField(source='get_webhook_type_display', read_only=True)
    is_successful = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletWebhookLog
        fields = [
            'id', 'webhook_type', 'webhook_type_display',
            'event_type', 'payload', 'headers',
            'is_processed', 'is_successful',
            'processing_error', 'reference_id',
            'transaction_reference', 'received_at',
            'processed_at'
        ]
        read_only_fields = ['received_at', 'processed_at']
    
    def get_is_successful(self, obj):
        """Null-safe success check"""
        return get_safe_value(obj, 'is_processed', False) and not get_safe_value(obj, 'processing_error', '')
    
    def validate_payload(self, value):
        """Ensure payload is valid JSON/dict"""
        if not isinstance(value, (dict, list)):
            raise serializers.ValidationError("Payload must be a valid JSON object or array")
        return value


# ============================================
# REQUEST/RESPONSE SERIALIZERS (API SPECIFIC)
# ============================================

class WithdrawalRequestSerializer(serializers.Serializer):
    """Bulletproof withdrawal request serializer"""
    amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2,
        min_value=Decimal('100'),
        max_value=Decimal('50000')
    )
    payment_method_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate(self, data):
        """Circuit breaker pattern for withdrawal validation"""
        with CircuitBreaker(failure_threshold=3, recovery_timeout=300) as breaker:
            # Your validation logic here
            validated_data = super().validate(data)
            
            # Simulate external API check
            if not self._check_withdrawal_limit(validated_data['amount']):
                raise serializers.ValidationError("Daily withdrawal limit exceeded")
            
            return validated_data
    
    def _check_withdrawal_limit(self, amount):
        """Simulated external API call with circuit breaker"""
        # This would be an actual API call in production
        return True


class WalletBalanceUpdateSerializer(serializers.Serializer):
    """Bulletproof balance update serializer"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    type = serializers.ChoiceField(choices=[
        'credit', 'debit', 'bonus', 'penalty'
    ])
    reference = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        """Null-safe amount validation"""
        try:
            amount = Decimal(str(value))
            if amount <= 0:
                raise serializers.ValidationError("Amount must be positive")
            return amount
        except (InvalidOperation, ValueError, TypeError):
            raise serializers.ValidationError("Invalid amount")


# ============================================
# BULK OPERATION SERIALIZERS
# ============================================

class BulkWalletUpdateSerializer(serializers.Serializer):
    """Bulletproof bulk update serializer"""
    updates = serializers.ListField(
        child=serializers.DictField(),
        max_length=100  # Prevent DoS with too many updates
    )
    
    def validate_updates(self, value):
        """Validate each update in bulk operation"""
        if not value:
            raise serializers.ValidationError("Updates list cannot be empty")
        
        validated_updates = []
        for idx, update in enumerate(value):
            try:
                # Null-safe extraction
                wallet_id = get_safe_value(update, 'wallet_id')
                amount = get_safe_value(update, 'amount')
                
                if not wallet_id or not amount:
                    logger.warning(f"Invalid update at index {idx}: {update}")
                    continue
                
                validated_updates.append({
                    'wallet_id': wallet_id,
                    'amount': Decimal(str(amount)),
                    'type': get_safe_value(update, 'type', 'credit'),
                    'description': get_safe_value(update, 'description', '')
                })
            except (ValueError, InvalidOperation, TypeError) as e:
                logger.error(f"Failed to validate update {idx}: {e}")
                continue
        
        if not validated_updates:
            raise serializers.ValidationError("No valid updates found")
        
        return validated_updates