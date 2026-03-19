from rest_framework import serializers
from decimal import Decimal
from .models import AdminAction, SystemSettings, Report
from core.serializers import BaseSerializer
from rest_framework import viewsets
from api.users.models import User
from api.users.models import UserProfile 
from django.contrib.auth.password_validation import validate_password
from .models import SystemSettings, SiteNotification, SiteContent
from django.core.mail import send_mail
from django.conf import settings
import requests






class AdminActionSerializer(BaseSerializer):
    admin_username = serializers.CharField(source='admin.username', read_only=True)
    target_username = serializers.CharField(source='target_user.username', read_only=True)
    
    class Meta:
        model = AdminAction
        fields = '__all__'


# class SystemSettingsSerializer(BaseSerializer):
#     class Meta:
#         model = SystemSettings
#         fields = '__all__'


class ReportSerializer(BaseSerializer):
    generated_by_username = serializers.CharField(source='generated_by.username', read_only=True)
    
    class Meta:
        model = Report
        fields = '__all__'
        
        
        from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        extra_kwargs = {
            'email': {'required': True}
        }

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    user = UserSerializer()
    referral_code = serializers.CharField(read_only=True)
    referred_by_code = serializers.CharField(write_only=True, required=False)
    available_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'profile_id', 'user', 'profile_picture', 'phone_number',
            'date_of_birth', 'gender', 'address', 'city', 'state',
            'zip_code', 'country', 'total_points',
            'total_withdrawn', 'available_balance', 'referral_code',
            'referred_by_code', 'email_verified', 'phone_verified',
            'identity_verified', 'account_status', 'is_premium',
            'is_affiliate', 'email_notifications', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'profile_id', 'total_points',
            'total_withdrawn', 'email_verified', 'phone_verified',
            'identity_verified', 'created_at', 'updated_at',
            'last_login_at'
        ]
    
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        referred_by_code = validated_data.pop('referred_by_code', None)
        
        # Create User
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data.get('email', ''),
            password=user_data.get('password', ''),
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', '')
        )
        
        # Create UserProfile
        profile = UserProfile.objects.create(user=user, **validated_data)
        
        # Generate referral code
        profile.generate_referral_code()
        
        # Handle referral
        if referred_by_code:
            try:
                referrer = UserProfile.objects.get(referral_code=referred_by_code)
                profile.referred_by = referrer
                profile.save()
            except UserProfile.DoesNotExist:
                pass
        
        return profile
    
    def update(self, instance, validated_data):
        # Update User fields if provided
        user_data = validated_data.pop('user', None)
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                if attr != 'password':  # Handle password separately
                    setattr(user, attr, value)
            user.save()
        
        # Update Profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class UserProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating UserProfile with User"""
    username = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    first_name = serializers.CharField(write_only=True, required=False)
    last_name = serializers.CharField(write_only=True, required=False)
    referred_by_code = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = UserProfile
        fields = [
            'username', 'email', 'password', 'first_name', 'last_name',
            'phone_number', 'date_of_birth', 'gender', 'referred_by_code'
        ]
    
    def create(self, validated_data):
        # Extract user data
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        referred_by_code = validated_data.pop('referred_by_code', None)
        
        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create UserProfile
        profile = UserProfile.objects.create(user=user, **validated_data)
        
        # Generate referral code
        profile.generate_referral_code()
        
        # Handle referral
        if referred_by_code:
            try:
                referrer = UserProfile.objects.get(referral_code=referred_by_code)
                profile.referred_by = referrer
                profile.save()
            except UserProfile.DoesNotExist:
                pass
        
        return profile


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating UserProfile"""
    class Meta:
        model = UserProfile
        fields = [
            'profile_picture', 'phone_number', 'date_of_birth', 'gender',
            'address', 'city', 'state', 'zip_code', 'country',
            'email_notifications'
        ]


class UserProfilePublicSerializer(serializers.ModelSerializer):
    """Public serializer for UserProfile (limited fields)"""
    username = serializers.CharField(source='user.username')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    
    class Meta:
        model = UserProfile
        fields = [
            'username', 'first_name', 'last_name', 'profile_picture',
            'total_points', 'is_premium', 'is_affiliate', 'created_at'
        ]
        read_only_fields = fields


class ReferralSerializer(serializers.ModelSerializer):
    """Serializer for referral information"""
    username = serializers.CharField(source='user.username')
    email = serializers.CharField(source='user.email')
    joined_at = serializers.DateTimeField(source='created_at')
    is_active = serializers.BooleanField()
    
    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'is_active']


class StatsSerializer(serializers.Serializer):
    """Serializer for profile statistics"""
    total_points = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_withdrawn = serializers.DecimalField(max_digits=12, decimal_places=2)
    available_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    referral_count = serializers.IntegerField()
    is_premium = serializers.BooleanField()
    is_affiliate = serializers.BooleanField()
    account_status = serializers.CharField()
    days_since_joined = serializers.IntegerField()


class VerificationSerializer(serializers.Serializer):
    """Serializer for verification requests"""
    verification_type = serializers.ChoiceField(choices=['email', 'phone'])
    token = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value
    
    

class SystemSettingsPublicSerializer(serializers.ModelSerializer):
    """Public system settings (safe to expose to all users)"""
    
    class Meta:
        model = SystemSettings
        fields = [
            # Site Info
            'site_name',
            'site_tagline',
            'site_description',
            'site_logo',
            'site_favicon',
            'contact_email',
            'support_email',
            
            # Social Links
            'contact_facebook',
            'contact_twitter',
            'contact_instagram',
            'contact_telegram',
            'contact_youtube',
            
            # Currency
            'currency_code',
            'currency_symbol',
            
            # Public Limits
            'min_withdrawal_amount',
            'max_withdrawal_amount',
            'point_value',
            'min_points_withdrawal',
            
            # Bonuses (visible to encourage sign-ups)
            'welcome_bonus_points',
            'daily_login_bonus',
            'referral_bonus_points',
            
            # Referral Info
            'enable_referral',
            'referral_levels',
            'referral_percentage_level1',
            'referral_percentage_level2',
            'referral_percentage_level3',
            
            # Reward Points
            'ad_click_points',
            'video_watch_points',
            'survey_complete_points',
            'task_complete_points',
            
            # Maintenance
            'maintenance_mode',
            'maintenance_message',
            
            # Legal
            'terms_url',
            'privacy_policy_url',
            'refund_policy_url',
            'copyright_text',
        ]
        read_only_fields = fields


class SystemSettingsVersionSerializer(serializers.Serializer):
    """Version check serializer"""
    platform = serializers.ChoiceField(choices=['android', 'ios', 'web'])
    version_code = serializers.IntegerField()
    
    def validate_version_code(self, value):
        if value < 0:
            raise serializers.ValidationError("Version code must be positive")
        return value


class SystemSettingsVersionResponseSerializer(serializers.Serializer):
    """Version check response"""
    is_allowed = serializers.BooleanField()
    update_required = serializers.BooleanField()
    update_available = serializers.BooleanField()
    force_update = serializers.BooleanField()
    message = serializers.CharField()
    app_link = serializers.URLField(allow_blank=True)
    current_version = serializers.CharField()
    current_version_code = serializers.IntegerField()
    min_required_version_code = serializers.IntegerField()


class SystemSettingsAdminSerializer(serializers.ModelSerializer):
    """Full system settings for admin users only"""
    
    last_modified_by_username = serializers.CharField(
        source='last_modified_by.username',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = SystemSettings
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'smtp_password': {'write_only': True},
            'sms_api_key': {'write_only': True},
            'sms_api_secret': {'write_only': True},
            'firebase_server_key': {'write_only': True},
        }


class SystemSettingsUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating specific settings"""
    
    class Meta:
        model = SystemSettings
        fields = [
            'site_name',
            'currency_code',
            'currency_symbol',
            'min_withdrawal_amount',
            'max_withdrawal_amount',
            'withdrawal_fee_percentage',
            'point_value',
            'maintenance_mode',
            'maintenance_message',
        ]
    
    def validate_min_withdrawal_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Minimum withdrawal cannot be negative")
        return value
    
    def validate_max_withdrawal_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Maximum withdrawal must be positive")
        
        # Check if min_withdrawal is being updated
        min_withdrawal = self.initial_data.get(
            'min_withdrawal_amount',
            self.instance.min_withdrawal_amount if self.instance else 0
        )
        
        if value < min_withdrawal:
            raise serializers.ValidationError(
                "Maximum withdrawal must be greater than minimum withdrawal"
            )
        
        return value


class DailyLimitsSerializer(serializers.Serializer):
    """User's daily limits status"""
    action_type = serializers.ChoiceField(
        choices=['ads', 'videos', 'tasks', 'surveys', 'earning']
    )
    current_count = serializers.IntegerField(read_only=True)
    daily_limit = serializers.IntegerField(read_only=True)
    remaining = serializers.IntegerField(read_only=True)
    percentage_used = serializers.FloatField(read_only=True)
    is_exceeded = serializers.BooleanField(read_only=True)


class PaymentGatewayStatusSerializer(serializers.Serializer):
    """Payment gateway availability status"""
    bkash = serializers.BooleanField(source='enable_bkash')
    nagad = serializers.BooleanField(source='enable_nagad')
    rocket = serializers.BooleanField(source='enable_rocket')
    stripe = serializers.BooleanField(source='enable_stripe')
    paypal = serializers.BooleanField(source='enable_paypal')
    bank_transfer = serializers.BooleanField(source='enable_bank_transfer')


class SecuritySettingsSerializer(serializers.Serializer):
    """Security settings status for users"""
    two_factor_enabled = serializers.BooleanField(source='enable_2fa')
    email_verification_required = serializers.BooleanField(source='enable_email_verification')
    phone_verification_required = serializers.BooleanField(source='enable_phone_verification')
    withdrawal_pin_required = serializers.BooleanField(source='enable_withdrawal_pin')
    withdrawal_pin_length = serializers.IntegerField()
    max_login_attempts = serializers.IntegerField()
    session_timeout_minutes = serializers.IntegerField()


class ReferralSettingsSerializer(serializers.Serializer):
    """Referral system settings"""
    enabled = serializers.BooleanField(source='enable_referral')
    levels = serializers.IntegerField(source='referral_levels')
    level_1_percentage = serializers.DecimalField(
        source='referral_percentage_level1',
        max_digits=5,
        decimal_places=2
    )
    level_2_percentage = serializers.DecimalField(
        source='referral_percentage_level2',
        max_digits=5,
        decimal_places=2
    )
    level_3_percentage = serializers.DecimalField(
        source='referral_percentage_level3',
        max_digits=5,
        decimal_places=2
    )
    level_4_percentage = serializers.DecimalField(
        source='referral_percentage_level4',
        max_digits=5,
        decimal_places=2
    )
    level_5_percentage = serializers.DecimalField(
        source='referral_percentage_level5',
        max_digits=5,
        decimal_places=2
    )
    bonus_points = serializers.IntegerField(source='referral_bonus_points')
    expiry_days = serializers.IntegerField(source='referral_expiry_days')


class RewardPointsSerializer(serializers.Serializer):
    """Reward points for different actions"""
    ad_click = serializers.IntegerField(source='ad_click_points')
    video_watch = serializers.IntegerField(source='video_watch_points')
    survey_complete = serializers.IntegerField(source='survey_complete_points')
    task_complete = serializers.IntegerField(source='task_complete_points')
    daily_login = serializers.IntegerField(source='daily_login_bonus')
    welcome_bonus = serializers.IntegerField(source='welcome_bonus_points')
    referral_bonus = serializers.IntegerField(source='referral_bonus_points')


class WithdrawalSettingsSerializer(serializers.Serializer):
    """Withdrawal settings and limits"""
    min_amount = serializers.DecimalField(
        source='min_withdrawal_amount',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.00')
    )
    max_amount = serializers.DecimalField(
        source='max_withdrawal_amount',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.00')
    )
    fee_percentage = serializers.DecimalField(
        source='withdrawal_fee_percentage',
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.00')
    )
    fee_fixed = serializers.DecimalField(
        source='withdrawal_fee_fixed',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.00')
    )
    processing_time_hours = serializers.IntegerField(source='withdrawal_processing_time')
    cooldown_hours = serializers.IntegerField(source='withdrawal_cooldown_hours')
    max_pending = serializers.IntegerField(source='max_pending_withdrawals')
    review_required = serializers.BooleanField(source='withdrawal_review_required')
    auto_approve_limit = serializers.DecimalField(
        source='withdrawal_auto_approve_limit',
        max_digits=10,
        decimal_places=2
    )


class AppConfigSerializer(serializers.Serializer):
    """Complete app configuration for mobile apps"""
    
    # Site Info
    site = serializers.SerializerMethodField()
    
    # Currency
    currency = serializers.SerializerMethodField()
    
    # Version
    version = serializers.SerializerMethodField()
    
    # Features
    features = serializers.SerializerMethodField()
    
    # Limits
    limits = serializers.SerializerMethodField()
    
    # Rewards
    rewards = serializers.SerializerMethodField()
    
    # Referral
    referral = serializers.SerializerMethodField()
    
    # Withdrawal
    withdrawal = serializers.SerializerMethodField()
    
    # Payment Gateways
    payment_gateways = serializers.SerializerMethodField()
    
    # Maintenance
    maintenance = serializers.SerializerMethodField()
    
    def get_site(self, obj):
        return {
            'name': obj.site_name,
            'tagline': obj.site_tagline,
            'logo': obj.site_logo.url if obj.site_logo else None,
            'favicon': obj.site_favicon.url if obj.site_favicon else None,
            'contact_email': obj.contact_email,
            'support_email': obj.support_email,
        }
    
    def get_currency(self, obj):
        return {
            'code': obj.currency_code,
            'symbol': obj.currency_symbol,
        }
    
    def get_version(self, obj):
        request = self.context.get('request')
        platform = self.context.get('platform', 'android')
        
        if platform == 'android':
            return {
                'current': obj.android_version,
                'code': obj.android_version_code,
                'min_required': obj.android_min_version,
                'min_code': obj.android_min_version_code,
                'force_update': obj.android_force_update,
                'update_message': obj.android_update_message,
                'app_link': obj.android_app_link,
                'apk_link': obj.android_apk_link,
            }
        elif platform == 'ios':
            return {
                'current': obj.ios_version,
                'code': obj.ios_version_code,
                'min_required': obj.ios_min_version,
                'min_code': obj.ios_min_version_code,
                'force_update': obj.ios_force_update,
                'update_message': obj.ios_update_message,
                'app_link': obj.ios_app_link,
            }
        else:
            return {
                'current': obj.web_version,
                'force_reload': obj.web_force_reload,
            }
    
    def get_features(self, obj):
        return {
            'referral': obj.enable_referral,
            'leaderboard': obj.enable_leaderboard,
            'badges': obj.enable_badges,
            'achievements': obj.enable_achievements,
            'daily_streak': obj.enable_daily_streak,
            'social_sharing': obj.enable_social_sharing,
            'user_profiles': obj.enable_user_profiles,
            'chat': obj.enable_chat,
        }
    
    def get_limits(self, obj):
        return {
            'daily_earning': float(obj.max_daily_earning_limit),
            'daily_withdrawal': float(obj.max_daily_withdrawal_limit),
            'daily_ads': obj.max_daily_ads,
            'daily_videos': obj.max_daily_videos,
            'daily_tasks': obj.max_daily_tasks,
            'daily_surveys': obj.max_daily_surveys,
            'min_ad_watch_time': obj.min_ad_watch_time,
            'min_video_watch_time': obj.min_video_watch_time,
            'click_delay': obj.click_delay_seconds,
        }
    
    def get_rewards(self, obj):
        return {
            'point_value': float(obj.point_value),
            'min_points_withdrawal': obj.min_points_withdrawal,
            'ad_click': obj.ad_click_points,
            'video_watch': obj.video_watch_points,
            'survey_complete': obj.survey_complete_points,
            'task_complete': obj.task_complete_points,
            'daily_login': obj.daily_login_bonus,
            'welcome_bonus': obj.welcome_bonus_points,
            'first_withdrawal_bonus': obj.first_withdrawal_bonus,
        }
    
    def get_referral(self, obj):
        if not obj.enable_referral:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'levels': obj.referral_levels,
            'percentages': {
                'level_1': float(obj.referral_percentage_level1),
                'level_2': float(obj.referral_percentage_level2),
                'level_3': float(obj.referral_percentage_level3),
                'level_4': float(obj.referral_percentage_level4),
                'level_5': float(obj.referral_percentage_level5),
            },
            'bonus_points': obj.referral_bonus_points,
            'expiry_days': obj.referral_expiry_days,
            'min_referrals_for_withdrawal': obj.min_referral_withdrawal,
        }
    
    def get_withdrawal(self, obj):
        return {
            'min_amount': float(obj.min_withdrawal_amount),
            'max_amount': float(obj.max_withdrawal_amount),
            'fee_percentage': float(obj.withdrawal_fee_percentage),
            'fee_fixed': float(obj.withdrawal_fee_fixed),
            'processing_time_hours': obj.withdrawal_processing_time,
            'cooldown_hours': obj.withdrawal_cooldown_hours,
            'max_pending': obj.max_pending_withdrawals,
            'review_required': obj.withdrawal_review_required,
            'pin_required': obj.enable_withdrawal_pin,
            'pin_length': obj.withdrawal_pin_length,
            'new_user_delay_days': obj.new_user_withdrawal_delay_days,
        }
    
    def get_payment_gateways(self, obj):
        return {
            'bkash': obj.enable_bkash,
            'nagad': obj.enable_nagad,
            'rocket': obj.enable_rocket,
            'stripe': obj.enable_stripe,
            'paypal': obj.enable_paypal,
            'bank_transfer': obj.enable_bank_transfer,
        }
    
    def get_maintenance(self, obj):
        return {
            'active': obj.maintenance_mode,
            'message': obj.maintenance_message if obj.maintenance_mode else '',
            'start': obj.maintenance_start,
            'end': obj.maintenance_end,
        }


class SiteNotificationSerializer(serializers.ModelSerializer):
    """Serializer for SiteNotification"""
    is_current = serializers.BooleanField(read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    
    class Meta:
        model = SiteNotification
        fields = [
            'id', 'title', 'message', 'notification_type',
            'notification_type_display', 'is_active', 'show_on_login',
            'start_date', 'end_date', 'priority', 'is_current',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SiteContentSerializer(serializers.ModelSerializer):
    """Serializer for SiteContent"""
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    
    class Meta:
        model = SiteContent
        fields = [
            'id', 'identifier', 'title', 'content', 'content_type',
            'content_type_display', 'is_active', 'language',
            'meta_title', 'meta_description', 'meta_keywords',
            'order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PublicSystemSettingsSerializer(serializers.ModelSerializer):
    """Public serializer for SystemSettings (limited fields)"""
    class Meta:
        model = SystemSettings
        fields = [
            'site_name', 'site_logo', 'site_favicon', 'site_url',
            'contact_email', 'support_email', 'contact_phone',
            'contact_address', 'currency_code', 'currency_symbol',
            'min_withdrawal_amount', 'max_withdrawal_amount',
            'withdrawal_fee_percentage', 'tax_percentage',
            'point_value', 'referral_bonus_points',
            'maintenance_mode', 'maintenance_message',
            'terms_url', 'privacy_policy_url', 'refund_policy_url',
            'copyright_text'
        ]


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications"""
    class Meta:
        model = SiteNotification
        fields = ['title', 'message', 'notification_type', 'show_on_login', 
                 'start_date', 'end_date', 'priority']
    
    def validate(self, data):
        """Validate notification dates"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })
        
        return data


class EmailTestSerializer(serializers.Serializer):
    """Serializer for email test"""
    email_to = serializers.EmailField(required=True)
    subject = serializers.CharField(default="Test Email from System")
    message = serializers.CharField(default="This is a test email from the system settings.")


class SMSTestSerializer(serializers.Serializer):
    """Serializer for SMS test"""
    phone_number = serializers.CharField(required=True)
    message = serializers.CharField(default="Test SMS from system")


class MaintenanceModeSerializer(serializers.Serializer):
    """Serializer for maintenance mode toggle"""
    maintenance_mode = serializers.BooleanField(required=True)
    maintenance_message = serializers.CharField(required=False)
    maintenance_start = serializers.DateTimeField(required=False)
    maintenance_end = serializers.DateTimeField(required=False)


class CacheClearSerializer(serializers.Serializer):
    """Serializer for cache clearing"""
    cache_type = serializers.ChoiceField(
        choices=['all', 'settings', 'notifications', 'content'],
        default='all'
    )


class SystemStatsSerializer(serializers.Serializer):
    """Serializer for system statistics"""
    total_users = serializers.IntegerField()
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_withdrawals = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_users_today = serializers.IntegerField()
    total_notifications = serializers.IntegerField()
    system_uptime = serializers.FloatField()
    last_backup = serializers.DateTimeField()