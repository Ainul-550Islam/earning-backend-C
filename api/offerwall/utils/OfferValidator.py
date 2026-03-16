"""
Offer validation utility
"""
import logging
from django.utils import timezone
from decimal import Decimal
from ..constants import *
from ..exceptions import *

logger = logging.getLogger(__name__)


class OfferValidator:
    """Validator for offer-related operations"""
    
    def __init__(self, offer=None):
        self.offer = offer
    
    def validate_offer_availability(self, user=None):
        """
        Validate if offer is available
        
        Args:
            user: User instance (optional)
        
        Returns:
            bool: True if available
        
        Raises:
            Various exceptions if not available
        """
        if not self.offer:
            raise OfferNotFoundException()
        
        # Check offer status
        if self.offer.status != STATUS_ACTIVE:
            if self.offer.status == STATUS_EXPIRED:
                raise OfferExpiredException()
            else:
                raise OfferInactiveException()
        
        # Check dates
        now = timezone.now()
        
        if self.offer.start_date and now < self.offer.start_date:
            raise OfferInactiveException("This offer hasn't started yet")
        
        if self.offer.end_date and now > self.offer.end_date:
            raise OfferExpiredException()
        
        # Check total cap
        if self.offer.total_cap > 0 and self.offer.conversion_count >= self.offer.total_cap:
            raise OfferCapReachedException()
        
        # Check daily cap
        if self.offer.daily_cap > 0:
            from ..models import OfferConversion
            today_conversions = OfferConversion.objects.filter(
                offer=self.offer,
                status=CONVERSION_APPROVED,
                converted_at__date=timezone.now().date()
            ).count()
            
            if today_conversions >= self.offer.daily_cap:
                raise OfferCapReachedException("Daily limit reached for this offer")
        
        # User-specific checks
        if user:
            self._validate_user_eligibility(user)
        
        return True
    
    def _validate_user_eligibility(self, user):
        """Validate user eligibility for offer"""
        from ..models import OfferConversion
        
        # Check if user is active
        if not user.is_active:
            raise AccountSuspendedException()
        
        # Check user age
        if hasattr(user, 'age') and user.age < self.offer.min_age:
            raise OfferNotAvailableException(
                f"You must be at least {self.offer.min_age} years old"
            )
        
        # Check user completion limit
        if self.offer.user_limit > 0:
            user_completions = OfferConversion.objects.filter(
                user=user,
                offer=self.offer,
                status__in=[CONVERSION_APPROVED, CONVERSION_PENDING]
            ).count()
            
            if user_completions >= self.offer.user_limit:
                raise OfferLimitReachedException()
        
        # Check country availability
        if self.offer.countries:
            user_country = self._get_user_country(user)
            if user_country and user_country not in self.offer.countries:
                raise CountryNotSupportedException()
        
        # Check excluded countries
        if self.offer.excluded_countries:
            user_country = self._get_user_country(user)
            if user_country and user_country in self.offer.excluded_countries:
                raise CountryNotSupportedException()
        
        # Check platform compatibility
        user_platform = self._get_user_platform(user)
        if not self._is_platform_compatible(user_platform):
            raise PlatformNotSupportedException()
        
        return True
    
    def validate_conversion_data(self, data):
        """
        Validate conversion data
        
        Args:
            data: Dictionary with conversion data
        
        Returns:
            bool: True if valid
        
        Raises:
            InvalidConversionException if invalid
        """
        required_fields = ['user_id', 'offer_id', 'transaction_id', 'payout']
        
        for field in required_fields:
            if field not in data:
                raise InvalidConversionException(f"Missing required field: {field}")
        
        # Validate payout
        try:
            payout = Decimal(str(data['payout']))
            if payout <= 0:
                raise InvalidConversionException("Payout must be greater than 0")
        except (ValueError, TypeError):
            raise InvalidConversionException("Invalid payout amount")
        
        # Validate user exists
        from api.users.models import User
        try:
            User.objects.get(id=data['user_id'])
        except User.DoesNotExist:
            raise InvalidConversionException("User not found")
        
        # Check for duplicate conversion
        from ..models import OfferConversion
        if OfferConversion.objects.filter(
            external_transaction_id=data['transaction_id']
        ).exists():
            raise DuplicateConversionException()
        
        return True
    
    def validate_provider_data(self, provider):
        """
        Validate provider configuration
        
        Args:
            provider: OfferProvider instance
        
        Returns:
            bool: True if valid
        
        Raises:
            InvalidProviderConfigException if invalid
        """
        if not provider.is_active():
            raise ProviderInactiveException()
        
        # Check required credentials
        if not provider.api_key:
            raise InvalidProviderConfigException("API key is missing")
        
        if provider.provider_type in [PROVIDER_TAPJOY, PROVIDER_ADGEM]:
            if not provider.app_id:
                raise InvalidProviderConfigException("App ID is missing")
        
        # Check URLs
        if not provider.api_base_url:
            raise InvalidProviderConfigException("API base URL is missing")
        
        return True
    
    def validate_click_data(self, data):
        """
        Validate click tracking data
        
        Args:
            data: Dictionary with click data
        
        Returns:
            bool: True if valid
        """
        if 'offer_id' not in data:
            raise InvalidParameterException("Offer ID is required")
        
        return True
    
    def validate_user_daily_limit(self, user):
        """
        Check if user has reached daily earning limit
        
        Args:
            user: User instance
        
        Returns:
            bool: True if within limit
        
        Raises:
            DailyLimitReachedException if exceeded
        """
        from ..models import OfferConversion
        
        today_earnings = OfferConversion.objects.filter(
            user=user,
            status=CONVERSION_APPROVED,
            converted_at__date=timezone.now().date()
        ).aggregate(
            total=models.Sum('reward_amount')
        )['total'] or Decimal('0')
        
        if today_earnings >= Decimal(str(MAX_DAILY_EARNINGS)):
            raise DailyLimitReachedException()
        
        return True
    
    def validate_payout_amount(self, payout):
        """
        Validate payout amount
        
        Args:
            payout: Decimal payout amount
        
        Returns:
            bool: True if valid
        
        Raises:
            InvalidRewardException if invalid
        """
        payout = Decimal(str(payout))
        
        if payout < Decimal(str(MIN_PAYOUT_AMOUNT)):
            raise InvalidRewardException(
                f"Payout must be at least {MIN_PAYOUT_AMOUNT}"
            )
        
        if payout > Decimal(str(MAX_PAYOUT_AMOUNT)):
            raise InvalidRewardException(
                f"Payout cannot exceed {MAX_PAYOUT_AMOUNT}"
            )
        
        return True
    
    def _get_user_country(self, user):
        """Get user's country code"""
        # Try to get from user profile
        if hasattr(user, 'profile') and hasattr(user.profile, 'country'):
            return user.profile.country
        
        # Try to get from recent activity
        from api.fraud_detection.models import DeviceFingerprint
        fingerprint = DeviceFingerprint.objects.filter(user=user).first()
        if fingerprint and fingerprint.location_data:
            return fingerprint.location_data.get('country_code')
        
        return None
    
    def _get_user_platform(self, user):
        """Get user's current platform"""
        from api.fraud_detection.models import DeviceFingerprint
        
        fingerprint = DeviceFingerprint.objects.filter(user=user).order_by('-last_seen').first()
        if fingerprint:
            if fingerprint.is_mobile:
                if 'android' in fingerprint.os.lower():
                    return PLATFORM_ANDROID
                elif 'ios' in fingerprint.os.lower():
                    return PLATFORM_IOS
                return PLATFORM_MOBILE
            return PLATFORM_DESKTOP
        
        return PLATFORM_ALL
    
    def _is_platform_compatible(self, user_platform):
        """Check if user's platform is compatible with offer"""
        if self.offer.platform == PLATFORM_ALL:
            return True
        
        if self.offer.platform == PLATFORM_MOBILE:
            return user_platform in [PLATFORM_ANDROID, PLATFORM_IOS, PLATFORM_MOBILE]
        
        return self.offer.platform == user_platform
    
    @staticmethod
    def validate_webhook_signature(data, signature, secret_key):
        """
        Validate webhook signature
        
        Args:
            data: Raw webhook data
            signature: Provided signature
            secret_key: Secret key for validation
        
        Returns:
            bool: True if valid
        
        Raises:
            InvalidWebhookSignatureException if invalid
        """
        import hmac
        import hashlib
        
        if not secret_key:
            logger.warning("No secret key provided for webhook validation")
            return True
        
        # Calculate expected signature
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            data,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            raise InvalidWebhookSignatureException()
        
        return True
    
    @staticmethod
    def validate_webhook_timestamp(timestamp, max_age=WEBHOOK_MAX_AGE_SECONDS):
        """
        Validate webhook timestamp
        
        Args:
            timestamp: Unix timestamp
            max_age: Maximum age in seconds
        
        Returns:
            bool: True if valid
        
        Raises:
            WebhookTimestampException if too old
        """
        import time
        
        try:
            timestamp = int(timestamp)
        except (ValueError, TypeError):
            raise WebhookTimestampException("Invalid timestamp format")
        
        current_time = int(time.time())
        age = current_time - timestamp
        
        if age > max_age:
            raise WebhookTimestampException(
                f"Webhook is too old (age: {age}s, max: {max_age}s)"
            )
        
        if age < -60:  # Allow 60 seconds clock skew
            raise WebhookTimestampException("Webhook timestamp is in the future")
        
        return True
    
    @staticmethod
    def validate_ip_whitelist(ip_address, whitelist):
        """
        Validate IP against whitelist
        
        Args:
            ip_address: IP address to check
            whitelist: List of allowed IPs
        
        Returns:
            bool: True if allowed
        
        Raises:
            ValidationException if not allowed
        """
        if not whitelist:
            return True
        
        if ip_address not in whitelist:
            raise ValidationException(f"IP {ip_address} is not whitelisted")
        
        return True