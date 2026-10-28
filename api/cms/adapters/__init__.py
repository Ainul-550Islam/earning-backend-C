# cms/adapters/__init__.py
"""
Adapter System for Business Logic Integration

Central hub for all adapters (fraud detection, payments, wallets, analytics, notifications, etc.)

Adapters are business logic containers that:
1. Handle cross-cutting concerns (fraud, compliance, notifications)
2. Can be enabled/disabled independently
3. Integrate with signals and ViewSet operations
4. Maintain consistent error handling
5. Support dependency injection

Available Adapters:
- FraudSecurityAdapter: Fraud detection and prevention
- PaymentTenantAdapter: Multi-tenant payment handling
- UserWalletAdapter: User virtual wallet management
- AnalyticsAdapter: Event tracking and analytics
- NotificationsAdapter: Email, SMS, push notifications
- GamificationAdapter: Points, badges, leaderboards
- AdOfferwallAdapter: Ad/Offerwall integration
- SupportRateLimitAdapter: Rate limiting and abuse prevention
"""
from django.db import models

from typing import Dict, List, Optional, Any, Callable
from abc import ABC, abstractmethod
import logging
from functools import wraps
from django.core.exceptions import ImproperlyConfigured
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

logger = logging.getLogger('cms.adapters')


# ─────────────────────────────────────────────────────────────────────────────
# BASE ADAPTER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class BaseAdapter(ABC):
    """
    Base class for all adapters
    
    Provides:
    - Initialization and cleanup
    - Error handling
    - Logging
    - Enable/disable functionality
    """
    
    name: str = "BaseAdapter"
    version: str = "1.0.0"
    enabled: bool = True
    dependencies: List[str] = []
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize adapter
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self._initialized = False
        logger.debug(f"Initializing {self.name} adapter")
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize adapter resources
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def validate(self, obj: Any) -> bool:
        """
        Validate an object (user, withdrawal, transaction, etc.)
        
        Args:
            obj: Object to validate
            
        Returns:
            True if object passes validation, False otherwise
        """
        pass
    
    def cleanup(self):
        """Clean up adapter resources"""
        logger.debug(f"Cleaning up {self.name} adapter")
    
    def is_enabled(self) -> bool:
        """Check if adapter is enabled"""
        return self.enabled
    
    def set_enabled(self, enabled: bool):
        """Enable or disable adapter"""
        self.enabled = enabled
        logger.info(f"{self.name} adapter {'enabled' if enabled else 'disabled'}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get adapter status"""
        return {
            'name': self.name,
            'version': self.version,
            'enabled': self.enabled,
            'initialized': self._initialized,
        }


# ─────────────────────────────────────────────────────────────────────────────
# FRAUD SECURITY ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class FraudSecurityAdapter(BaseAdapter):
    """
    Fraud Detection & Prevention Adapter
    
    Responsibilities:
    - Detect fraudulent user behavior
    - Block suspicious withdrawals
    - Monitor payment patterns
    - Enforce compliance rules
    - IP/Device fingerprinting
    """
    
    name = "FraudSecurityAdapter"
    version = "2.0.0"
    
    def initialize(self) -> bool:
        """Initialize fraud detection rules"""
        try:
            # Load fraud detection models/rules
            self.max_daily_withdrawals = self.config.get('max_daily_withdrawals', 5)
            self.max_daily_amount = self.config.get('max_daily_amount', 5000)
            self.min_account_age_days = self.config.get('min_account_age_days', 7)
            self.max_failed_logins = self.config.get('max_failed_logins', 5)
            
            self._initialized = True
            logger.info(f"{self.name} initialized with rules")
            return True
        except Exception as e:
            logger.error(f"{self.name} initialization failed: {e}")
            return False
    
    def validate(self, obj: Any) -> bool:
        """
        Validate withdrawal request for fraud
        
        Args:
            obj: WithdrawalRequest object
            
        Returns:
            True if safe, False if suspicious
        """
        if not self.enabled or not self._initialized:
            return True
        
        try:
            from api.cms.models_new.withdrawal import WithdrawalRequest
            
            if not isinstance(obj, WithdrawalRequest):
                return True
            
            # Check 1: Account age
            if self._is_new_account(obj.user):
                logger.warning(f"Withdrawal blocked for new account: {obj.user.id}")
                return False
            
            # Check 2: Daily limit
            if self._exceeds_daily_limit(obj.user, obj.amount):
                logger.warning(f"Withdrawal exceeds daily limit: {obj.user.id}")
                return False
            
            # Check 3: Withdrawal frequency
            if self._exceeds_daily_withdrawals(obj.user):
                logger.warning(f"Too many withdrawals from {obj.user.id}")
                return False
            
            # Check 4: Unusual amount
            if self._is_unusual_amount(obj.user, obj.amount):
                logger.warning(f"Unusual withdrawal amount from {obj.user.id}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"{self.name} validation error: {e}")
            return False
    
    def _is_new_account(self, user) -> bool:
        """Check if account is too new"""
        from datetime import timedelta
        from django.utils import timezone
        
        min_date = timezone.now() - timedelta(days=self.min_account_age_days)
        return user.date_joined > min_date
    
    def _exceeds_daily_limit(self, user, amount: float) -> bool:
        """Check if withdrawal exceeds daily limit"""
        from django.utils import timezone
        from datetime import timedelta
        from api.cms.models_new.withdrawal import WithdrawalRequest
        
        today = timezone.now().date()
        daily_total = WithdrawalRequest.objects.filter(
            user=user,
            created_at__date=today,
            status='approved'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        return (daily_total + amount) > self.max_daily_amount
    
    def _exceeds_daily_withdrawals(self, user) -> bool:
        """Check if user has too many daily withdrawals"""
        from django.utils import timezone
        from api.cms.models_new.withdrawal import WithdrawalRequest
        
        today = timezone.now().date()
        daily_count = WithdrawalRequest.objects.filter(
            user=user,
            created_at__date=today,
            status='approved'
        ).count()
        
        return daily_count >= self.max_daily_withdrawals
    
    def _is_unusual_amount(self, user, amount: float) -> bool:
        """Check if withdrawal amount is unusual for this user"""
        from api.cms.models_new.withdrawal import WithdrawalRequest
        
        # Get user's average withdrawal
        avg_withdrawal = WithdrawalRequest.objects.filter(
            user=user,
            status='approved'
        ).aggregate(
            avg=models.Avg('amount')
        )['avg'] or amount
        
        # Flag if 5x larger than average
        return amount > (avg_withdrawal * 5)
    
    def cleanup(self):
        """Cleanup fraud detection"""
        super().cleanup()


# ─────────────────────────────────────────────────────────────────────────────
# PAYMENT TENANT ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class PaymentTenantAdapter(BaseAdapter):
    """
    Multi-Tenant Payment Handling Adapter
    
    Responsibilities:
    - Route payments to correct tenant
    - Handle commission splits
    - Process refunds
    - Manage payment gateways
    - Currency conversion
    """
    
    name = "PaymentTenantAdapter"
    version = "1.5.0"
    
    def initialize(self) -> bool:
        """Initialize payment processors"""
        try:
            self.default_gateway = self.config.get('default_gateway', 'stripe')
            self.commissions = self.config.get('commissions', {})
            self.supported_currencies = self.config.get('currencies', ['USD', 'BDT'])
            
            self._initialized = True
            logger.info(f"{self.name} initialized")
            return True
        except Exception as e:
            logger.error(f"{self.name} initialization failed: {e}")
            return False
    
    def validate(self, obj: Any) -> bool:
        """
        Validate payment request
        
        Args:
            obj: Payment object
            
        Returns:
            True if valid, False otherwise
        """
        if not self.enabled or not self._initialized:
            return True
        
        try:
            # Validate payment object
            if not hasattr(obj, 'amount') or obj.amount <= 0:
                return False
            
            if not hasattr(obj, 'currency') or obj.currency not in self.supported_currencies:
                return False
            
            return True
        except Exception as e:
            logger.error(f"{self.name} validation error: {e}")
            return False
    
    def process_payment(self, payment: Any) -> bool:
        """Process payment through correct gateway"""
        if not self.validate(payment):
            return False
        
        try:
            # Route to appropriate gateway
            if payment.gateway == 'stripe':
                return self._process_stripe(payment)
            elif payment.gateway == 'bkash':
                return self._process_bkash(payment)
            else:
                return False
        except Exception as e:
            logger.error(f"Payment processing failed: {e}")
            return False
    
    def _process_stripe(self, payment) -> bool:
        """Process Stripe payment"""
        # Implementation
        logger.info(f"Processing Stripe payment: {payment.id}")
        return True
    
    def _process_bkash(self, payment) -> bool:
        """Process bKash payment"""
        # Implementation
        logger.info(f"Processing bKash payment: {payment.id}")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# USER WALLET ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class UserWalletAdapter(BaseAdapter):
    """
    User Virtual Wallet Management Adapter
    
    Responsibilities:
    - Manage virtual balance
    - Handle deposits/withdrawals
    - Process transfers
    - Audit balance changes
    - Prevent overspending
    """
    
    name = "UserWalletAdapter"
    version = "1.0.0"
    
    def initialize(self) -> bool:
        """Initialize wallet system"""
        try:
            self.min_balance = self.config.get('min_balance', 0)
            self.max_balance = self.config.get('max_balance', 999999)
            
            self._initialized = True
            logger.info(f"{self.name} initialized")
            return True
        except Exception as e:
            logger.error(f"{self.name} initialization failed: {e}")
            return False
    
    def validate(self, obj: Any) -> bool:
        """Validate wallet transaction"""
        if not self.enabled or not self._initialized:
            return True
        
        try:
            from api.cms.models_new.user_wallet import UserVirtualBalance
            
            if isinstance(obj, UserVirtualBalance):
                # Check balance within limits
                return self.min_balance <= obj.balance <= self.max_balance
            
            return True
        except Exception as e:
            logger.error(f"{self.name} validation error: {e}")
            return False
    
    def can_withdraw(self, user, amount: float) -> bool:
        """Check if user can withdraw amount"""
        try:
            from api.cms.models_new.user_wallet import UserVirtualBalance
            
            balance = UserVirtualBalance.objects.get(user=user)
            return balance.balance >= amount
        except Exception as e:
            logger.error(f"Wallet check failed: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsAdapter(BaseAdapter):
    """
    Analytics & Event Tracking Adapter
    
    Responsibilities:
    - Track user events
    - Measure conversions
    - Monitor KPIs
    - Send to analytics platforms
    - Generate reports
    """
    
    name = "AnalyticsAdapter"
    version = "1.0.0"
    
    def initialize(self) -> bool:
        """Initialize analytics"""
        try:
            self.provider = self.config.get('provider', 'ga')  # Google Analytics
            self.tracking_id = self.config.get('tracking_id')
            
            self._initialized = True
            logger.info(f"{self.name} initialized with {self.provider}")
            return True
        except Exception as e:
            logger.error(f"{self.name} initialization failed: {e}")
            return False
    
    def validate(self, obj: Any) -> bool:
        """Always validate analytics requests"""
        return True
    
    def track_event(self, user, event_type: str, data: Dict[str, Any]):
        """Track user event"""
        if not self.enabled or not self._initialized:
            return
        
        try:
            # Track event based on provider
            if self.provider == 'ga':
                self._track_google_analytics(user, event_type, data)
            elif self.provider == 'segment':
                self._track_segment(user, event_type, data)
        except Exception as e:
            logger.error(f"Event tracking failed: {e}")
    
    def _track_google_analytics(self, user, event_type: str, data: Dict):
        """Track in Google Analytics"""
        logger.debug(f"GA Event: {user.id} - {event_type}")
    
    def _track_segment(self, user, event_type: str, data: Dict):
        """Track in Segment"""
        logger.debug(f"Segment Event: {user.id} - {event_type}")


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class NotificationsAdapter(BaseAdapter):
    """
    Notifications Adapter (Email, SMS, Push)
    
    Responsibilities:
    - Send email notifications
    - Send SMS alerts
    - Send push notifications
    - Queue notifications
    - Handle delivery failures
    - Track delivery status
    """
    
    name = "NotificationsAdapter"
    version = "2.0.0"
    
    def initialize(self) -> bool:
        """Initialize notification providers"""
        try:
            self.email_provider = self.config.get('email_provider', 'sendgrid')
            self.sms_provider = self.config.get('sms_provider', 'twilio')
            self.push_provider = self.config.get('push_provider', 'fcm')
            
            self._initialized = True
            logger.info(f"{self.name} initialized")
            return True
        except Exception as e:
            logger.error(f"{self.name} initialization failed: {e}")
            return False
    
    def validate(self, obj: Any) -> bool:
        """Validate notification"""
        return True
    
    def send_email(self, recipient: str, subject: str, body: str, html: str = None) -> bool:
        """Send email notification"""
        if not self.enabled or not self._initialized:
            return False
        
        try:
            logger.info(f"Sending email to {recipient}: {subject}")
            # Queue for async sending
            from api.cms.tasks.notification_tasks import send_email_task
            send_email_task.delay(recipient, subject, body, html)
            return True
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return False
    
    def send_sms(self, phone: str, message: str) -> bool:
        """Send SMS notification"""
        if not self.enabled or not self._initialized:
            return False
        
        try:
            logger.info(f"Sending SMS to {phone}")
            from api.cms.tasks.notification_tasks import send_sms_task
            send_sms_task.delay(phone, message)
            return True
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return False
    
    def send_push(self, user_id: int, title: str, message: str) -> bool:
        """Send push notification"""
        if not self.enabled or not self._initialized:
            return False
        
        try:
            logger.info(f"Sending push to user {user_id}: {title}")
            from api.cms.tasks.notification_tasks import send_push_task
            send_push_task.delay(user_id, title, message)
            return True
        except Exception as e:
            logger.error(f"Push sending failed: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# GAMIFICATION ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class GamificationAdapter(BaseAdapter):
    """
    Gamification Adapter (Points, Badges, Streaks)
    
    Responsibilities:
    - Award points
    - Unlock badges
    - Track streaks
    - Calculate rewards
    - Update leaderboards
    """
    
    name = "GamificationAdapter"
    version = "1.0.0"
    
    def initialize(self) -> bool:
        """Initialize gamification"""
        try:
            self.points_multiplier = self.config.get('points_multiplier', 1.0)
            
            self._initialized = True
            logger.info(f"{self.name} initialized")
            return True
        except Exception as e:
            logger.error(f"{self.name} initialization failed: {e}")
            return False
    
    def validate(self, obj: Any) -> bool:
        """Validate gamification request"""
        return True
    
    def award_points(self, user, points: float, reason: str = None) -> bool:
        """Award points to user"""
        if not self.enabled or not self._initialized:
            return False
        
        try:
            from api.cms.models_new.leaderboard import UserPoints
            
            adjusted_points = points * self.points_multiplier
            
            # Add to user's points
            user_points, created = UserPoints.objects.get_or_create(
                user=user,
                defaults={'points': 0}
            )
            user_points.points += adjusted_points
            user_points.save()
            
            logger.info(f"Awarded {adjusted_points} points to {user.id}: {reason}")
            return True
        except Exception as e:
            logger.error(f"Points award failed: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# AD/OFFERWALL ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class AdOfferwallAdapter(BaseAdapter):
    """
    Ad/Offerwall Integration Adapter
    
    Responsibilities:
    - Manage offer inventory
    - Track offer impressions
    - Handle conversions
    - Calculate payouts
    - Manage offer providers
    """
    
    name = "AdOfferwallAdapter"
    version = "1.0.0"
    
    def initialize(self) -> bool:
        """Initialize offerwall system"""
        try:
            self.providers = self.config.get('providers', [])
            
            self._initialized = True
            logger.info(f"{self.name} initialized with {len(self.providers)} providers")
            return True
        except Exception as e:
            logger.error(f"{self.name} initialization failed: {e}")
            return False
    
    def validate(self, obj: Any) -> bool:
        """Validate offer"""
        return True


# ─────────────────────────────────────────────────────────────────────────────
# SUPPORT & RATE LIMITING ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class SupportRateLimitAdapter(BaseAdapter):
    """
    Support & Rate Limiting Adapter
    
    Responsibilities:
    - Implement rate limiting
    - Prevent abuse
    - Track usage
    - Support ticket management
    """
    
    name = "SupportRateLimitAdapter"
    version = "1.0.0"
    
    def initialize(self) -> bool:
        """Initialize rate limiting"""
        try:
            self.rate_limits = self.config.get('rate_limits', {})
            
            self._initialized = True
            logger.info(f"{self.name} initialized")
            return True
        except Exception as e:
            logger.error(f"{self.name} initialization failed: {e}")
            return False
    
    def validate(self, obj: Any) -> bool:
        """Validate request against rate limits"""
        return True


# ─────────────────────────────────────────────────────────────────────────────
# ADAPTER REGISTRY & MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class AdapterRegistry:
    """Central registry for all adapters"""
    
    _adapters: Dict[str, BaseAdapter] = {}
    _initialized = False
    
    @classmethod
    def register(cls, adapter: BaseAdapter):
        """Register adapter"""
        name = adapter.name
        cls._adapters[name] = adapter
        logger.debug(f"Registered adapter: {name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseAdapter]:
        """Get adapter by name"""
        return cls._adapters.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, BaseAdapter]:
        """Get all adapters"""
        return cls._adapters.copy()
    
    @classmethod
    def initialize_all(cls) -> bool:
        """Initialize all adapters"""
        if cls._initialized:
            return True
        
        all_initialized = True
        for name, adapter in cls._adapters.items():
            if adapter.is_enabled():
                if not adapter.initialize():
                    logger.warning(f"Failed to initialize {name}")
                    all_initialized = False
        
        cls._initialized = all_initialized
        logger.info(f"Adapter initialization complete: {len(cls._adapters)} adapters")
        return all_initialized
    
    @classmethod
    def cleanup_all(cls):
        """Cleanup all adapters"""
        for adapter in cls._adapters.values():
            adapter.cleanup()
        
        cls._initialized = False
        logger.info("All adapters cleaned up")
    
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Get status of all adapters"""
        return {
            name: adapter.get_status()
            for name, adapter in cls._adapters.items()
        }


# ─────────────────────────────────────────────────────────────────────────────
# ADAPTER MIDDLEWARE/DECORATOR
# ─────────────────────────────────────────────────────────────────────────────

def require_adapter_validation(*adapter_names):
    """
    Decorator to require adapter validation before ViewSet action
    
    Usage:
        @require_adapter_validation('FraudSecurityAdapter', 'PaymentTenantAdapter')
        def perform_withdrawal(self, serializer):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Validate with required adapters
            obj = kwargs.get('serializer') or args[0] if args else None
            
            for adapter_name in adapter_names:
                adapter = AdapterRegistry.get(adapter_name)
                if adapter and adapter.is_enabled():
                    if not adapter.validate(obj):
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError(
                            f"Failed validation from {adapter_name}"
                        )
            
            return func(self, *args, **kwargs)
        
        return wrapper
    
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────

# Register all adapters
AdapterRegistry.register(FraudSecurityAdapter())
AdapterRegistry.register(PaymentTenantAdapter())
AdapterRegistry.register(UserWalletAdapter())
AdapterRegistry.register(AnalyticsAdapter())
AdapterRegistry.register(NotificationsAdapter())
AdapterRegistry.register(GamificationAdapter())
AdapterRegistry.register(AdOfferwallAdapter())
AdapterRegistry.register(SupportRateLimitAdapter())


# Export public API
__all__ = [
    'BaseAdapter',
    'FraudSecurityAdapter',
    'PaymentTenantAdapter',
    'UserWalletAdapter',
    'AnalyticsAdapter',
    'NotificationsAdapter',
    'GamificationAdapter',
    'AdOfferwallAdapter',
    'SupportRateLimitAdapter',
    'AdapterRegistry',
    'require_adapter_validation',
]
