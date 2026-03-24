from rest_framework import serializers
from django.apps import apps # এটি অবশ্যই যোগ করতে হবে
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User, UserActivity, UserRank, UserStatistics


# আপনার লোকাল মডেলগুলো
from .models import OTP, LoginHistory, UserDevice, KYCVerification, UserLevel, SecuritySettings, UserStatistics, UserPreferences, NotificationSettings
User, UserActivity, UserDevice, UserRank
# core থেকে ইমপোর্ট
from core.serializers import BaseSerializer
from api.users.models import UserProfile



User = get_user_model()



class UserProfileSerializer(BaseSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'bio', 'date_of_birth', 'address', 'city', 
            'country', 'postal_code', 'nid_number',
            'created_at', 'modified_at'
        ]


class UserSerializer(BaseSerializer):
    profile = UserProfileSerializer(read_only=True)
    referrals_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone', 'role', 'balance',
            'is_verified', 'is_active', 'referral_code', 'avatar', 
            'profile', 'referrals_count', 'last_login', 'created_at', 'modified_at', 'is_staff', 'is_superuser'
        ]
        read_only_fields = ['id', 'balance', 'referral_code', 'created_at', 'modified_at']
    
    def get_referrals_count(self, obj):
        return obj.referrals_list.count() if hasattr(obj, "referrals_list") else 0
    
    
    
class UserDeviceSerializer(serializers.ModelSerializer):
    """User Device Serializer"""
    class Meta:
        model = UserDevice
        fields = '__all__'
        
        
class UserActivitySerializer(serializers.ModelSerializer):
    """User Activity Serializer"""
    class Meta:
        model = UserActivity
        fields = ['action', 'description', 'ip_address', 'timestamp']
        
        
class UserRankSerializer(serializers.ModelSerializer):
    """User Rank Serializer"""
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = UserRank
        fields = ['rank', 'points', 'next_rank_points', 'badge_icon', 'progress_percentage']
    
    def get_progress_percentage(self, obj):
        if obj.next_rank_points == 0:
            return 100
        return min((obj.points / obj.next_rank_points) * 100, 100)


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password', 'confirm_password', 'referred_by']
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value
    
    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone number already exists")
        return value
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        referred_by = validated_data.pop('referred_by', None)
        
        user = User.objects.create_user(**validated_data)
        
        if referred_by:
            user.referred_by = referred_by
            user.save()
        
        return user


class UserLoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)

    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        # username / email / username_or_email — যেকোনো একটা accept করো
        identifier = (
            attrs.get('username_or_email') or
            attrs.get('username') or
            attrs.get('email') or ''
        ).strip()
        if not identifier:
            raise serializers.ValidationError({'username_or_email': 'This field is required.'})
        attrs['username_or_email'] = identifier
        return attrs


class OTPSerializer(BaseSerializer):
    class Meta:
        model = OTP
        fields = ['id', 'code', 'otp_type', 'expires_at', 'is_used', 'created_at']
        read_only_fields = ['id', 'created_at']


class OTPVerifySerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    otp = serializers.CharField(max_length=6)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data


class LoginHistorySerializer(BaseSerializer):
    class Meta:
        model = LoginHistory
        fields = ['id', 'ip_address', 'user_agent', 'device', 'location', 'is_successful', 'created_at']


class UserDeviceSerializer(BaseSerializer):
    class Meta:
        model = UserDevice
        fields = ['id', 'device_id', 'device_name', 'device_type', 'fcm_token', 'is_active', 'created_at']
        
        
# api/users/serializers.py-তে নিচের serializers গুলো যোগ করুন:

# 1. OTP Verification Serializer (alias)
OTPVerificationSerializer = OTPVerifySerializer  # [OK] Simple alias

# 2. Password Reset Serializer
class PasswordResetSerializer(serializers.Serializer):
    phone = serializers.CharField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data

# 3. KYC Verification Serializer
class KYCVerificationSerializer(BaseSerializer):
    class Meta:
        model = KYCVerification  # [OK] আপনার model import করতে হবে
        fields = ['id', 'document_type', 'front_image', 'back_image', 
                 'selfie_image', 'verification_status', 'submitted_at', 
                 'reviewed_at', 'rejection_reason']
        read_only_fields = ['id', 'submitted_at', 'reviewed_at', 'verification_status']

# 4. User Level Serializer
class UserLevelSerializer(BaseSerializer):
    class Meta:
        model = UserLevel  # [OK] আপনার model import করতে হবে
        fields = ['id', 'current_level', 'level_type', 'experience_points', 
                 'xp_to_next_level', 'total_xp_earned']
        read_only_fields = ['id', 'created_at']

# 5. Notification Settings Serializer
class NotificationSettingsSerializer(BaseSerializer):
    class Meta:
        model = NotificationSettings  # [OK] আপনার model import করতে হবে
        fields = ['id', 'email_task_approved', 'email_task_rejected', 
                 'email_withdrawal_processed', 'push_task_completed', 'sms_withdrawal_otp']
        read_only_fields = ['id', 'created_at']

# 6. Security Settings Serializer
class SecuritySettingsSerializer(BaseSerializer):
    class Meta:
        model = SecuritySettings  # [OK] আপনার model import করতে হবে
        fields = ['id', 'two_factor_enabled', 'two_factor_method', 
                 'require_login_verification', 'login_verification_method']
        read_only_fields = ['id', 'created_at']

# 7. User Statistics Serializer
class UserStatisticsSerializer(BaseSerializer):
    class Meta:
        model = UserStatistics  # [OK] আপনার model import করতে হবে
        fields = ['id', 'total_earned', 'total_withdrawn', 'total_tasks_completed', 
                 'total_referrals', 'current_streak']
        read_only_fields = ['id', 'created_at']

# 8. User Preferences Serializer
class UserPreferencesSerializer(BaseSerializer):
    class Meta:
        model = UserPreferences  # [OK] আপনার model import করতে হবে
        fields = ['id', 'language', 'theme', 
                 'show_quick_stats', 'show_recent_activity']
        read_only_fields = ['id', 'created_at']

# 9. Support Ticket Serializer
# class SupportTicketSerializer(BaseSerializer):
#     class Meta:
#         model = SupportTicket  # [OK] আপনার model import করতে হবে
#         fields = ['id', 'ticket_id', 'subject', 'category', 'description', 
#                  'status', 'priority', 'created_at', 'resolved_at']
#         read_only_fields = ['id', 'ticket_id', 'created_at', 'resolved_at']

# # 10. Ticket Message Serializer
# class TicketMessageSerializer(BaseSerializer):
#     class Meta:
#         model = TicketMessage  # [OK] আপনার model import করতে হবে
#         fields = ['id', 'message', 'sender_type', 'created_at']
#         read_only_fields = ['id', 'created_at']

# 11. User Detail Serializer
# class UserDetailSerializer(UserSerializer):
#     """Extended user serializer with more details"""
#     class Meta(UserSerializer.Meta):
#         fields = UserSerializer.Meta.fields + ['referred_by', 'date_joined']
        




class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user information for nested serialization"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone']
        read_only_fields = ['id', 'username', 'email']


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user information with balance"""
    
    class Meta:
        model = User
        fields = [
            'id', 
            'username', 
            'email', 
            'first_name', 
            'last_name', 
            'phone',
            'balance',
            'is_active'
        ]
        read_only_fields = ['id', 'username', 'email', 'balance']


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user information"""
    
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'balance',
            'is_active',
            'is_staff',
            'date_joined',
            'last_login'
        ]
        read_only_fields = [
            'id', 
            'username', 
            'email', 
            'balance', 
            'is_staff', 
            'date_joined', 
            'last_login'
        ]


class UserRegistrationSerializer(serializers.ModelSerializer):
    """User registration serializer"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'phone'
        ]
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords do not match")
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user