"""
api/ad_networks/feature_flags.py
Feature flags system for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Set
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .helpers import get_cache_key

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== FEATURE FLAG DEFINITIONS ====================

class FeatureFlags:
    """Feature flag definitions"""
    
    # Offer features
    OFFER_RECOMMENDATIONS = "offer_recommendations"
    OFFER_ANALYTICS = "offer_analytics"
    OFFER_A_B_TESTING = "offer_ab_testing"
    OFFER_PERSONALIZATION = "offer_personalization"
    OFFER_GAMIFICATION = "offer_gamification"
    OFFER_SOCIAL_SHARING = "offer_social_sharing"
    OFFER_REVIEWS = "offer_reviews"
    OFFER_RATINGS = "offer_ratings"
    OFFER_FAVORITES = "offer_favorites"
    OFFER_WATCHLIST = "offer_watchlist"
    
    # User features
    USER_PROFILES = "user_profiles"
    USER_ACHIEVEMENTS = "user_achievements"
    USER_LEADERBOARD = "user_leaderboard"
    USER_REFERRALS = "user_referrals"
    USER_NOTIFICATIONS = "user_notifications"
    USER_DASHBOARD = "user_dashboard"
    USER_ANALYTICS = "user_analytics"
    USER_PREFERENCES = "user_preferences"
    USER_MULTI_DEVICE = "user_multi_device"
    
    # Payment features
    PAYMENT_CRYPTO = "payment_crypto"
    PAYMENT_BANK_TRANSFER = "payment_bank_transfer"
    PAYMENT_MOBILE_MONEY = "payment_mobile_money"
    PAYMENT_GIFT_CARDS = "payment_gift_cards"
    PAYMENT_SUBSCRIPTIONS = "payment_subscriptions"
    PAYMENT_RECURRING = "payment_recurring"
    PAYMENT_INSTANT = "payment_instant"
    PAYMENT_SCHEDULED = "payment_scheduled"
    
    # Admin features
    ADMIN_ADVANCED_ANALYTICS = "admin_advanced_analytics"
    ADMIN_BULK_OPERATIONS = "admin_bulk_operations"
    ADMIN_API_ACCESS = "admin_api_access"
    ADMIN_WEBHOOKS = "admin_webhooks"
    ADMIN_AUTOMATION = "admin_automation"
    ADMIN_AUDIT_LOGS = "admin_audit_logs"
    ADMIN_CUSTOM_REPORTS = "admin_custom_reports"
    ADMIN_EXPORT_IMPORT = "admin_export_import"
    
    # Security features
    SECURITY_2FA = "security_2fa"
    SECURITY_DEVICE_FINGERPRINTING = "security_device_fingerprinting"
    SECURITY_IP_WHITELIST = "security_ip_whitelist"
    SECURITY_RATE_LIMITING = "security_rate_limiting"
    SECURITY_ENCRYPTION = "security_encryption"
    SECURITY_AUDIT_TRAIL = "security_audit_trail"
    
    # Integration features
    INTEGRATION_GOOGLE_ANALYTICS = "integration_google_analytics"
    INTEGRATION_FACEBOOK_PIXEL = "integration_facebook_pixel"
    INTEGRATION_SLACK = "integration_slack"
    INTEGRATION_DISCORD = "integration_discord"
    INTEGRATION_TELEGRAM = "integration_telegram"
    INTEGRATION_EMAIL = "integration_email"
    
    # Experimental features
    EXPERIMENTAL_AI_OFFERS = "experimental_ai_offers"
    EXPERIMENTAL_VOICE_COMMANDS = "experimental_voice_commands"
    EXPERIMENTAL_AR_OFFERS = "experimental_ar_offers"
    EXPERIMENTAL_BLOCKCHAIN = "experimental_blockchain"
    EXPERIMENTAL_NFT_REWARDS = "experimental_nft_rewards"


# ==================== FEATURE FLAG CATEGORIES ====================

class FeatureCategories:
    """Feature flag categories"""
    
    OFFERS = "offers"
    USERS = "users"
    PAYMENTS = "payments"
    ADMIN = "admin"
    SECURITY = "security"
    INTEGRATIONS = "integrations"
    EXPERIMENTAL = "experimental"


# ==================== BASE FEATURE FLAG MANAGER ====================

class BaseFeatureFlagManager:
    """Base feature flag manager"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = 3600  # 1 hour cache
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key"""
        return get_cache_key(self.__class__.__name__, self.tenant_id, *args, **kwargs)
    
    def _get_from_cache(self, key: str) -> Any:
        """Get data from cache"""
        return cache.get(key)
    
    def _set_cache(self, key: str, data: Any, timeout: int = None) -> None:
        """Set data in cache"""
        timeout = timeout or self.cache_timeout
        cache.set(key, data, timeout)


# ==================== FEATURE FLAG MANAGER ====================

class FeatureFlagManager(BaseFeatureFlagManager):
    """Main feature flag manager"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self._feature_flags = self._load_feature_flags()
    
    def _load_feature_flags(self) -> Dict[str, Dict[str, Any]]:
        """Load feature flags configuration"""
        cache_key = self._get_cache_key('feature_flags')
        flags = self._get_from_cache(cache_key)
        
        if flags is None:
            flags = self._get_default_feature_flags()
            self._set_cache(cache_key, flags)
        
        return flags
    
    def _get_default_feature_flags(self) -> Dict[str, Dict[str, Any]]:
        """Get default feature flags configuration"""
        return {
            # Offer features
            FeatureFlags.OFFER_RECOMMENDATIONS: {
                'enabled': True,
                'category': FeatureCategories.OFFERS,
                'description': 'AI-powered offer recommendations',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.OFFER_ANALYTICS: {
                'enabled': True,
                'category': FeatureCategories.OFFERS,
                'description': 'Advanced offer analytics',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.OFFER_A_B_TESTING: {
                'enabled': False,
                'category': FeatureCategories.OFFERS,
                'description': 'A/B testing for offers',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['premium'],
                'dependencies': [FeatureFlags.OFFER_ANALYTICS],
                'experimental': True,
            },
            FeatureFlags.OFFER_PERSONALIZATION: {
                'enabled': True,
                'category': FeatureCategories.OFFERS,
                'description': 'Personalized offer recommendations',
                'rollout_percentage': 50,
                'user_segments': ['active_users'],
                'enabled_for_tenants': ['premium', 'enterprise'],
                'dependencies': [FeatureFlags.OFFER_RECOMMENDATIONS],
                'experimental': False,
            },
            FeatureFlags.OFFER_GAMIFICATION: {
                'enabled': False,
                'category': FeatureCategories.OFFERS,
                'description': 'Gamification elements for offers',
                'rollout_percentage': 10,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [FeatureFlags.USER_ACHIEVEMENTS],
                'experimental': True,
            },
            FeatureFlags.OFFER_SOCIAL_SHARING: {
                'enabled': True,
                'category': FeatureCategories.OFFERS,
                'description': 'Social sharing for offers',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.OFFER_REVIEWS: {
                'enabled': True,
                'category': FeatureCategories.OFFERS,
                'description': 'Offer reviews and ratings',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.OFFER_RATINGS: {
                'enabled': True,
                'category': FeatureCategories.OFFERS,
                'description': 'Offer rating system',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.OFFER_FAVORITES: {
                'enabled': True,
                'category': FeatureCategories.OFFERS,
                'description': 'Favorite offers for users',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [FeatureFlags.USER_PROFILES],
                'experimental': False,
            },
            FeatureFlags.OFFER_WATCHLIST: {
                'enabled': False,
                'category': FeatureCategories.OFFERS,
                'description': 'Watchlist for offers',
                'rollout_percentage': 25,
                'user_segments': ['active_users'],
                'enabled_for_tenants': ['premium'],
                'dependencies': [FeatureFlags.USER_PROFILES],
                'experimental': False,
            },
            
            # User features
            FeatureFlags.USER_PROFILES: {
                'enabled': True,
                'category': FeatureCategories.USERS,
                'description': 'User profile system',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.USER_ACHIEVEMENTS: {
                'enabled': True,
                'category': FeatureCategories.USERS,
                'description': 'User achievements and badges',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [FeatureFlags.USER_PROFILES],
                'experimental': False,
            },
            FeatureFlags.USER_LEADERBOARD: {
                'enabled': True,
                'category': FeatureCategories.USERS,
                'description': 'User leaderboard system',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [FeatureFlags.USER_ACHIEVEMENTS],
                'experimental': False,
            },
            FeatureFlags.USER_REFERRALS: {
                'enabled': False,
                'category': FeatureCategories.USERS,
                'description': 'User referral system',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['premium', 'enterprise'],
                'dependencies': [FeatureFlags.USER_PROFILES],
                'experimental': True,
            },
            FeatureFlags.USER_NOTIFICATIONS: {
                'enabled': True,
                'category': FeatureCategories.USERS,
                'description': 'User notification system',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.USER_DASHBOARD: {
                'enabled': True,
                'category': FeatureCategories.USERS,
                'description': 'User dashboard',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [FeatureFlags.USER_PROFILES],
                'experimental': False,
            },
            FeatureFlags.USER_ANALYTICS: {
                'enabled': True,
                'category': FeatureCategories.USERS,
                'description': 'User analytics dashboard',
                'rollout_percentage': 50,
                'user_segments': ['active_users'],
                'enabled_for_tenants': ['premium', 'enterprise'],
                'dependencies': [FeatureFlags.USER_DASHBOARD],
                'experimental': False,
            },
            FeatureFlags.USER_PREFERENCES: {
                'enabled': True,
                'category': FeatureCategories.USERS,
                'description': 'User preferences system',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [FeatureFlags.USER_PROFILES],
                'experimental': False,
            },
            FeatureFlags.USER_MULTI_DEVICE: {
                'enabled': False,
                'category': FeatureCategories.USERS,
                'description': 'Multi-device support',
                'rollout_percentage': 25,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [FeatureFlags.USER_PROFILES],
                'experimental': True,
            },
            
            # Payment features
            FeatureFlags.PAYMENT_CRYPTO: {
                'enabled': False,
                'category': FeatureCategories.PAYMENTS,
                'description': 'Cryptocurrency payments',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.PAYMENT_BANK_TRANSFER: {
                'enabled': True,
                'category': FeatureCategories.PAYMENTS,
                'description': 'Bank transfer payments',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.PAYMENT_MOBILE_MONEY: {
                'enabled': False,
                'category': FeatureCategories.PAYMENTS,
                'description': 'Mobile money payments',
                'rollout_percentage': 10,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['premium'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.PAYMENT_GIFT_CARDS: {
                'enabled': False,
                'category': FeatureCategories.PAYMENTS,
                'description': 'Gift card payments',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['premium'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.PAYMENT_SUBSCRIPTIONS: {
                'enabled': False,
                'category': FeatureCategories.PAYMENTS,
                'description': 'Subscription payments',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.PAYMENT_RECURRING: {
                'enabled': False,
                'category': FeatureCategories.PAYMENTS,
                'description': 'Recurring payments',
                'rollout_percentage': 5,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.PAYMENT_INSTANT: {
                'enabled': True,
                'category': FeatureCategories.PAYMENTS,
                'description': 'Instant payments',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.PAYMENT_SCHEDULED: {
                'enabled': False,
                'category': FeatureCategories.PAYMENTS,
                'description': 'Scheduled payments',
                'rollout_percentage': 10,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['premium'],
                'dependencies': [],
                'experimental': False,
            },
            
            # Admin features
            FeatureFlags.ADMIN_ADVANCED_ANALYTICS: {
                'enabled': True,
                'category': FeatureCategories.ADMIN,
                'description': 'Advanced analytics for admins',
                'rollout_percentage': 100,
                'user_segments': ['admin', 'moderator'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.ADMIN_BULK_OPERATIONS: {
                'enabled': True,
                'category': FeatureCategories.ADMIN,
                'description': 'Bulk operations for admins',
                'rollout_percentage': 100,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.ADMIN_API_ACCESS: {
                'enabled': True,
                'category': FeatureCategories.ADMIN,
                'description': 'API access for admins',
                'rollout_percentage': 100,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.ADMIN_WEBHOOKS: {
                'enabled': False,
                'category': FeatureCategories.ADMIN,
                'description': 'Webhook management for admins',
                'rollout_percentage': 25,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['premium', 'enterprise'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.ADMIN_AUTOMATION: {
                'enabled': False,
                'category': FeatureCategories.ADMIN,
                'description': 'Automation tools for admins',
                'rollout_percentage': 10,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.ADMIN_AUDIT_LOGS: {
                'enabled': True,
                'category': FeatureCategories.ADMIN,
                'description': 'Audit logs for admins',
                'rollout_percentage': 100,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.ADMIN_CUSTOM_REPORTS: {
                'enabled': False,
                'category': FeatureCategories.ADMIN,
                'description': 'Custom reports for admins',
                'rollout_percentage': 25,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['premium', 'enterprise'],
                'dependencies': [FeatureFlags.ADMIN_ADVANCED_ANALYTICS],
                'experimental': False,
            },
            FeatureFlags.ADMIN_EXPORT_IMPORT: {
                'enabled': True,
                'category': FeatureCategories.ADMIN,
                'description': 'Export/import for admins',
                'rollout_percentage': 100,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            
            # Security features
            FeatureFlags.SECURITY_2FA: {
                'enabled': True,
                'category': FeatureCategories.SECURITY,
                'description': 'Two-factor authentication',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.SECURITY_DEVICE_FINGERPRINTING: {
                'enabled': False,
                'category': FeatureCategories.SECURITY,
                'description': 'Device fingerprinting',
                'rollout_percentage': 50,
                'user_segments': ['all'],
                'enabled_for_tenants': ['premium', 'enterprise'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.SECURITY_IP_WHITELIST: {
                'enabled': True,
                'category': FeatureCategories.SECURITY,
                'description': 'IP whitelist for security',
                'rollout_percentage': 100,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.SECURITY_RATE_LIMITING: {
                'enabled': True,
                'category': FeatureCategories.SECURITY,
                'description': 'Rate limiting for security',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.SECURITY_ENCRYPTION: {
                'enabled': True,
                'category': FeatureCategories.SECURITY,
                'description': 'Data encryption',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.SECURITY_AUDIT_TRAIL: {
                'enabled': True,
                'category': FeatureCategories.SECURITY,
                'description': 'Security audit trail',
                'rollout_percentage': 100,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            
            # Integration features
            FeatureFlags.INTEGRATION_GOOGLE_ANALYTICS: {
                'enabled': True,
                'category': FeatureCategories.INTEGRATIONS,
                'description': 'Google Analytics integration',
                'rollout_percentage': 100,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.INTEGRATION_FACEBOOK_PIXEL: {
                'enabled': False,
                'category': FeatureCategories.INTEGRATIONS,
                'description': 'Facebook Pixel integration',
                'rollout_percentage': 25,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['premium', 'enterprise'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.INTEGRATION_SLACK: {
                'enabled': False,
                'category': FeatureCategories.INTEGRATIONS,
                'description': 'Slack integration',
                'rollout_percentage': 10,
                'user_segments': ['admin'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': False,
            },
            FeatureFlags.INTEGRATION_DISCORD: {
                'enabled': False,
                'category': FeatureCategories.INTEGRATIONS,
                'description': 'Discord integration',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.INTEGRATION_TELEGRAM: {
                'enabled': False,
                'category': FeatureCategories.INTEGRATIONS,
                'description': 'Telegram integration',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.INTEGRATION_EMAIL: {
                'enabled': True,
                'category': FeatureCategories.INTEGRATIONS,
                'description': 'Email integration',
                'rollout_percentage': 100,
                'user_segments': ['all'],
                'enabled_for_tenants': ['all'],
                'dependencies': [],
                'experimental': False,
            },
            
            # Experimental features
            FeatureFlags.EXPERIMENTAL_AI_OFFERS: {
                'enabled': False,
                'category': FeatureCategories.EXPERIMENTAL,
                'description': 'AI-generated offers',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [FeatureFlags.OFFER_RECOMMENDATIONS],
                'experimental': True,
            },
            FeatureFlags.EXPERIMENTAL_VOICE_COMMANDS: {
                'enabled': False,
                'category': FeatureCategories.EXPERIMENTAL,
                'description': 'Voice commands for offers',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.EXPERIMENTAL_AR_OFFERS: {
                'enabled': False,
                'category': FeatureCategories.EXPERIMENTAL,
                'description': 'AR-based offers',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [],
                'experimental': True,
            },
            FeatureFlags.EXPERIMENTAL_BLOCKCHAIN: {
                'enabled': False,
                'category': FeatureCategories.EXPERIMENTAL,
                'description': 'Blockchain-based rewards',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [FeatureFlags.PAYMENT_CRYPTO],
                'experimental': True,
            },
            FeatureFlags.EXPERIMENTAL_NFT_REWARDS: {
                'enabled': False,
                'category': FeatureCategories.EXPERIMENTAL,
                'description': 'NFT rewards system',
                'rollout_percentage': 0,
                'user_segments': ['beta_testers'],
                'enabled_for_tenants': ['enterprise'],
                'dependencies': [FeatureFlags.EXPERIMENTAL_BLOCKCHAIN],
                'experimental': True,
            },
        }
    
    def is_enabled(self, feature_flag: str, user_id: int = None, 
                  tenant_plan: str = None) -> bool:
        """Check if feature flag is enabled"""
        flag_config = self._feature_flags.get(feature_flag)
        
        if not flag_config:
            return False
        
        # Check if feature is globally enabled
        if not flag_config['enabled']:
            return False
        
        # Check tenant eligibility
        if not self._is_tenant_eligible(flag_config, tenant_plan):
            return False
        
        # Check user eligibility
        if user_id and not self._is_user_eligible(flag_config, user_id):
            return False
        
        # Check rollout percentage
        if not self._is_in_rollout_percentage(flag_config, user_id):
            return False
        
        # Check dependencies
        if not self._are_dependencies_enabled(flag_config['dependencies'], user_id, tenant_plan):
            return False
        
        return True
    
    def _is_tenant_eligible(self, flag_config: Dict[str, Any], tenant_plan: str) -> bool:
        """Check if tenant is eligible for feature"""
        enabled_tenants = flag_config.get('enabled_for_tenants', ['all'])
        
        if 'all' in enabled_tenants:
            return True
        
        if tenant_plan and tenant_plan in enabled_tenants:
            return True
        
        return False
    
    def _is_user_eligible(self, flag_config: Dict[str, Any], user_id: int) -> bool:
        """Check if user is eligible for feature"""
        user_segments = flag_config.get('user_segments', ['all'])
        
        if 'all' in user_segments:
            return True
        
        # This would typically check user segments
        # For now, return True if user_segments contains 'active_users'
        if 'active_users' in user_segments:
            return True
        
        # Check if user is in specific segments
        try:
            user = User.objects.get(id=user_id)
            
            if 'admin' in user_segments and user.is_staff:
                return True
            
            if 'moderator' in user_segments and hasattr(user, 'is_moderator') and user.is_moderator:
                return True
            
            if 'beta_testers' in user_segments and hasattr(user, 'is_beta_tester') and user.is_beta_tester:
                return True
            
        except User.DoesNotExist:
            return False
        
        return False
    
    def _is_in_rollout_percentage(self, flag_config: Dict[str, Any], user_id: int = None) -> bool:
        """Check if user is in rollout percentage"""
        rollout_percentage = flag_config.get('rollout_percentage', 0)
        
        if rollout_percentage >= 100:
            return True
        
        if rollout_percentage <= 0:
            return False
        
        if not user_id:
            return False
        
        # Use user ID to determine if user is in rollout
        # This ensures consistent rollout for the same user
        user_hash = hash(str(user_id)) % 100
        return user_hash < rollout_percentage
    
    def _are_dependencies_enabled(self, dependencies: List[str], user_id: int = None,
                                 tenant_plan: str = None) -> bool:
        """Check if all dependencies are enabled"""
        for dependency in dependencies:
            if not self.is_enabled(dependency, user_id, tenant_plan):
                return False
        
        return True
    
    def get_enabled_features(self, user_id: int = None, tenant_plan: str = None) -> List[str]:
        """Get all enabled features for user/tenant"""
        enabled_features = []
        
        for feature_flag in self._feature_flags:
            if self.is_enabled(feature_flag, user_id, tenant_plan):
                enabled_features.append(feature_flag)
        
        return enabled_features
    
    def get_feature_config(self, feature_flag: str) -> Optional[Dict[str, Any]]:
        """Get feature configuration"""
        return self._feature_flags.get(feature_flag)
    
    def get_features_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """Get features by category"""
        return {
            flag: config
            for flag, config in self._feature_flags.items()
            if config.get('category') == category
        }
    
    def enable_feature(self, feature_flag: str, tenant_id: str = None) -> bool:
        """Enable feature for tenant"""
        # This would typically update a database table
        # For now, we'll use cache
        cache_key = self._get_cache_key('tenant_feature', tenant_id, feature_flag)
        cache.set(cache_key, True, timeout=self.cache_timeout)
        
        return True
    
    def disable_feature(self, feature_flag: str, tenant_id: str = None) -> bool:
        """Disable feature for tenant"""
        # This would typically update a database table
        # For now, we'll use cache
        cache_key = self._get_cache_key('tenant_feature', tenant_id, feature_flag)
        cache.set(cache_key, False, timeout=self.cache_timeout)
        
        return True


# ==================== FEATURE FLAG UTILITIES ====================

class FeatureFlagUtils:
    """Utilities for feature flags"""
    
    @staticmethod
    def get_feature_description(feature_flag: str) -> str:
        """Get feature description"""
        manager = FeatureFlagManager()
        config = manager.get_feature_config(feature_flag)
        return config.get('description', '') if config else ''
    
    @staticmethod
    def is_experimental(feature_flag: str) -> bool:
        """Check if feature is experimental"""
        manager = FeatureFlagManager()
        config = manager.get_feature_config(feature_flag)
        return config.get('experimental', False) if config else False
    
    @staticmethod
    def get_feature_dependencies(feature_flag: str) -> List[str]:
        """Get feature dependencies"""
        manager = FeatureFlagManager()
        config = manager.get_feature_config(feature_flag)
        return config.get('dependencies', []) if config else []
    
    @staticmethod
    def can_enable_feature(feature_flag: str, tenant_plan: str) -> Tuple[bool, str]:
        """Check if feature can be enabled for tenant"""
        manager = FeatureFlagManager()
        config = manager.get_feature_config(feature_flag)
        
        if not config:
            return False, "Feature not found"
        
        enabled_tenants = config.get('enabled_for_tenants', ['all'])
        
        if 'all' in enabled_tenants:
            return True, "Feature can be enabled"
        
        if tenant_plan in enabled_tenants:
            return True, "Feature can be enabled"
        
        return False, f"Feature not available for {tenant_plan} plan"


# ==================== FEATURE FLAG DECORATOR ====================

def feature_flag_required(feature_flag: str, tenant_plan_param: str = 'tenant_plan'):
    """Decorator to require feature flag"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            tenant_id = getattr(request, 'tenant_id', 'default')
            tenant_plan = kwargs.get(tenant_plan_param, 'basic')
            user_id = request.user.id if request.user.is_authenticated else None
            
            manager = FeatureFlagManager(tenant_id)
            
            if not manager.is_enabled(feature_flag, user_id, tenant_plan):
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden(f"Feature '{feature_flag}' is not enabled")
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ==================== EXPORTS ====================

__all__ = [
    # Feature flags
    'FeatureFlags',
    'FeatureCategories',
    
    # Manager
    'FeatureFlagManager',
    
    # Utilities
    'FeatureFlagUtils',
    
    # Decorator
    'feature_flag_required',
]
