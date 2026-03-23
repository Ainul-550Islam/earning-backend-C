from decimal import Decimal
# profile/serializers.py
from rest_framework import serializers
from api.wallet.models import Wallet
from api.kyc.models import KYC
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from .models import (
    Wallet, Transaction, Offer, UserOffer, 
    Referral, DailyStats, Withdrawal
)

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    wallet_balance = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'wallet_balance', 'kyc_status', 'is_active',
            'date_joined', 'last_login'
        ]
        read_only_fields = [
            'id', 'username', 'email', 'wallet_balance', 'kyc_status', 'is_active',
            'date_joined', 'last_login'
        ]
    
    def get_wallet_balance(self, obj):
        try:
            wallet = obj.wallet
            return {
                'current_balance': float(wallet.current_balance),
                'pending_balance': float(wallet.pending_balance),
                'total_earned': float(wallet.total_earned),
                'total_withdrawn': float(wallet.total_withdrawn)
            }
        except:
            return None
    
    def get_kyc_status(self, obj):
        try:
            kyc = obj.kyc
            return kyc.status
        except:
            return 'not_submitted'


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'profile_picture', 'date_of_birth', 'gender', 'language']
    
    def validate_phone_number(self, value):
        # Phone update requires re-verification
        raise serializers.ValidationError(
            "Phone number changes require verification. Use /api/profile/change-phone/ endpoint."
        )
        
        
# auth/serializers.py

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    referral_code = serializers.CharField(required=False, allow_blank=True)
    agree_to_terms = serializers.BooleanField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 
                  'referral_code', 'agree_to_terms']
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        
        if not data.get('agree_to_terms'):
            raise serializers.ValidationError("You must agree to terms")
        
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        validated_data.pop('agree_to_terms')
        referral_code = validated_data.pop('referral_code', None)
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        
        # Handle referral
        if referral_code:
            try:
                referrer = User.objects.get(refer_code=referral_code)
                user.referred_by = referrer
                user.save()
                
                # Process referral bonus
                from referral.services import ReferralService
                ReferralService.process_signup_bonus(user, referrer)
            except User.DoesNotExist:
                pass
        
        return user


class LoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        from django.contrib.auth import authenticate
        
        username_or_email = data['username_or_email']
        password = data['password']
        
        # Try username first
        user = authenticate(username=username_or_email, password=password)
        
        # Try email
        if not user:
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled")
        
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    """User serializer with wallet info"""
    
    referral_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'uid', 'username', 'email', 'first_name', 'last_name',
            'balance', 'total_earned', 'referral_code', 'tier', 'phone',
            'country', 'is_verified', 'referral_count', 'created_at', 'last_activity'
        ]
        read_only_fields = ['uid', 'balance', 'total_earned', 'referral_code', 'created_at']
    
    def get_referral_count(self, obj):
        return obj.referrals.count()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """User registration serializer"""
    
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    referred_by_code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone', 'country',
            'referred_by_code'
        ]
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        referred_by_code = validated_data.pop('referred_by_code', None)
        
        user = User.objects.create_user(**validated_data)
        
        # Create wallet
        Wallet.objects.create(user=user)
        
        # Handle referral
        if referred_by_code:
            try:
                referrer = User.objects.get(referral_code=referred_by_code)
                user.referred_by = referrer
                user.save()
                
                Referral.objects.create(
                    referrer=referrer,
                    referred=user
                )
                
                # Bonus for both
                from api.wallet.models import Wallet
                referrer_wallet, _ = Wallet.objects.get_or_create(user=referrer)
                referrer_wallet.add_funds(5.00, "New referral bonus")
                user_wallet, _ = Wallet.objects.get_or_create(user=user)
                user_wallet.add_funds(Decimal("1.00"), "Welcome bonus")
            except User.DoesNotExist:
                pass
        else:
            # Welcome bonus
            from api.wallet.models import Wallet
            user_wallet, _ = Wallet.objects.get_or_create(user=user)
            user_wallet.add_funds(Decimal("1.00"), "Welcome bonus")
        
        return user


class WalletSerializer(serializers.ModelSerializer):
    """Wallet serializer"""
    
    class Meta:
        model = Wallet
        fields = [
            'available_balance', 'pending_balance', 'lifetime_earnings',
            'total_withdrawn', 'min_withdrawal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    """Transaction serializer"""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'transaction_id', 'user', 'user_name', 'amount', 'transaction_type',
            'description', 'status', 'reference_id', 'metadata', 'created_at'
        ]
        read_only_fields = ['transaction_id', 'created_at']


class OfferSerializer(serializers.ModelSerializer):
    """Offer serializer"""
    
    is_completed = serializers.SerializerMethodField()
    completion_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Offer
        fields = [
            'offer_id', 'title', 'description', 'offer_type', 'reward_amount',
            'estimated_time', 'difficulty', 'category', 'featured', 'icon',
            'url', 'terms', 'max_completions', 'total_completions',
            'success_rate', 'status', 'expires_at', 'is_completed',
            'completion_status', 'created_at'
        ]
        read_only_fields = ['offer_id', 'total_completions', 'created_at']
    
    def get_is_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserOffer.objects.filter(
                user=request.user,
                offer=obj,
                status='COMPLETED'
            ).exists()
        return False
    
    def get_completion_status(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                user_offer = UserOffer.objects.get(user=request.user, offer=obj)
                return user_offer.status
            except UserOffer.DoesNotExist:
                return None
        return None


class UserOfferSerializer(serializers.ModelSerializer):
    """User offer completion serializer"""
    
    offer_details = OfferSerializer(source='offer', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserOffer
        fields = [
            'id', 'user', 'user_name', 'offer', 'offer_details', 'status',
            'reward_earned', 'started_at', 'completed_at', 'verified_at',
            'proof_data', 'rejection_reason'
        ]
        read_only_fields = ['started_at', 'completed_at', 'verified_at', 'reward_earned']


class UserOfferCreateSerializer(serializers.ModelSerializer):
    """Serializer for starting an offer"""
    
    class Meta:
        model = UserOffer
        fields = ['offer', 'proof_data']
    
    def validate_offer(self, value):
        user = self.context['request'].user
        
        # Check if offer is available
        if not value.is_available_for_user(user):
            raise serializers.ValidationError("This offer is not available for you")
        
        # Check if already completed
        if UserOffer.objects.filter(user=user, offer=value, status='COMPLETED').exists():
            raise serializers.ValidationError("You have already completed this offer")
        
        # Check if already started
        if UserOffer.objects.filter(user=user, offer=value, status='STARTED').exists():
            raise serializers.ValidationError("You have already started this offer")
        
        return value
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ReferralSerializer(serializers.ModelSerializer):
    """Referral serializer"""
    
    referrer_name = serializers.CharField(source='referrer.username', read_only=True)
    referred_name = serializers.CharField(source='referred.username', read_only=True)
    
    class Meta:
        model = Referral
        fields = [
            'id', 'referrer', 'referrer_name', 'referred', 'referred_name',
            'commission_rate', 'total_earned', 'is_active', 'created_at'
        ]
        read_only_fields = ['total_earned', 'created_at']


class DailyStatsSerializer(serializers.ModelSerializer):
    """Daily statistics serializer"""
    
    class Meta:
        model = DailyStats
        fields = [
            'id', 'user', 'date', 'clicks', 'conversions', 'earnings',
            'offers_completed', 'time_spent'
        ]
        read_only_fields = ['id']


class WithdrawalSerializer(serializers.ModelSerializer):
    """Withdrawal serializer"""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Withdrawal
        fields = [
            'withdrawal_id', 'user', 'user_name', 'amount', 'payment_method',
            'payment_details', 'status', 'processing_fee', 'net_amount',
            'rejection_reason', 'requested_at', 'processed_at'
        ]
        read_only_fields = ['withdrawal_id', 'status', 'requested_at', 'processed_at', 'net_amount']
    
    def validate_amount(self, value):
        user = self.context['request'].user
        wallet = user.wallet
        
        if value < wallet.min_withdrawal:
            raise serializers.ValidationError(
                f"Minimum withdrawal amount is ${wallet.min_withdrawal}"
            )
        
        if value > wallet.available_balance:
            raise serializers.ValidationError(
                f"Insufficient balance. Available: ${wallet.available_balance}"
            )
        
        return value
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        
        # Calculate processing fee (2%)
        amount = validated_data['amount']
        fee = amount * 0.02
        validated_data['processing_fee'] = fee
        validated_data['net_amount'] = amount - fee
        
        return super().create(validated_data)


class WithdrawalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating withdrawal requests"""
    
    class Meta:
        model = Withdrawal
        fields = ['amount', 'payment_method', 'payment_details']
    
    def validate(self, data):
        user = self.context['request'].user
        
        # Check pending withdrawals
        pending_count = Withdrawal.objects.filter(
            user=user,
            status__in=['PENDING', 'PROCESSING']
        ).count()
        
        if pending_count >= 3:
            raise serializers.ValidationError(
                "You have too many pending withdrawals. Please wait for them to be processed."
            )
        
        return data


# class NotificationSerializer(serializers.ModelSerializer):
#     """Notification serializer"""
    
#     class Meta:
#         model = Notification
#         fields = [
#             'id', 'notification_type', 'title', 'message', 'icon',
#             'link', 'is_read', 'created_at'
#         ]
#         read_only_fields = ['created_at']


class DashboardStatsSerializer(serializers.Serializer):
    """Dashboard statistics serializer"""
    
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    today_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    today_change = serializers.DecimalField(max_digits=5, decimal_places=2)
    clicks = serializers.IntegerField()
    clicks_change = serializers.DecimalField(max_digits=5, decimal_places=2)
    conversions = serializers.IntegerField()
    conversions_change = serializers.DecimalField(max_digits=5, decimal_places=2)
    active_users = serializers.IntegerField()
    active_change = serializers.DecimalField(max_digits=5, decimal_places=2)
    referrals = serializers.IntegerField()
    referral_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    recent_activities = TransactionSerializer(many=True)
    available_offers = OfferSerializer(many=True)
    weekly_earnings = serializers.ListField()


class EarningsChartSerializer(serializers.Serializer):
    """Earnings chart data serializer"""
    
    day = serializers.CharField()
    value = serializers.DecimalField(max_digits=10, decimal_places=2)
    clicks = serializers.IntegerField()
    conversions = serializers.IntegerField()