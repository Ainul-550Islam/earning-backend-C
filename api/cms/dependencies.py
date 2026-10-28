# api/cms/dependencies.py
"""FastAPI-style dependency injection for DRF views."""
from functools import lru_cache
from django.core.cache import cache


def get_site_config(domain: str = ''):
    """Get active site config (injectable dependency)."""
    try:
        from api.cms.services_new.WithdrawalService import SiteConfigService
        return SiteConfigService.get_config(domain)
    except Exception:
        return {}


def get_cpalead_config():
    """Get active CPAlead config."""
    try:
        from api.cms.models_new.extras import CPALeadConfig
        return CPALeadConfig.get_active()
    except Exception:
        return None


def get_virtual_currency():
    """Get active virtual currency."""
    try:
        from api.cms.models_new.cpalead import VirtualCurrency
        return VirtualCurrency.get_active()
    except Exception:
        return None


def get_offerwall_config():
    """Get active offerwall config."""
    try:
        from api.cms.models_new.cpalead import OfferWallConfig
        return OfferWallConfig.objects.filter(is_active=True).first()
    except Exception:
        return None


def get_user_virtual_balance(user):
    """Get user's virtual balance."""
    try:
        from api.cms.models_new.cpalead import UserVirtualBalance
        return UserVirtualBalance.objects.get(user=user)
    except Exception:
        return None


def get_user_profile(user):
    """Get user's profile."""
    try:
        from api.cms.services_new.WithdrawalService import UserProfileService
        return UserProfileService.get_or_create(user)
    except Exception:
        return None


def get_leaderboard_service():
    from api.cms.services_new.LeaderboardService import LeaderboardService
    return LeaderboardService


def get_referral_service():
    from api.cms.services_new.ReferralService import ReferralService
    return ReferralService


def get_cpalead_service():
    from api.cms.services_new.CPALeadService import CPALeadService
    return CPALeadService


def get_survey_analytics_service():
    """Get survey analytics service."""
    from api.cms.services_new.SurveyAnalyticsService import SurveyAnalyticsService
    return SurveyAnalyticsService()


def get_user_segment_service():
    """Get user segment service."""
    from api.cms.services_new.UserSegmentService import UserSegmentService
    return UserSegmentService()


def get_profile_survey_manager():
    """Get profile survey manager."""
    from api.cms.services_new.ProfileSurveyService import ProfileSurveyManager
    return ProfileSurveyManager()


def get_survey_reward_service():
    """Get survey reward service."""
    from api.cms.services_new.SurveyRewardService import SurveyRewardService
    return SurveyRewardService()


def get_task_management_service():
    """Get task management service."""
    from api.cms.services_new.TaskManagementService import TaskManagementService
    return TaskManagementService()


def get_notification_service():
    """Get notification service."""
    from api.cms.services_new.NotificationService import NotificationService
    return NotificationService()


def get_user_profile_service():
    """Get user profile service."""
    from api.cms.services_new.UserProfileService import UserProfileService
    return UserProfileService()


def get_celery_task_service():
    """Get celery task service for task management."""
    from .tasks import task_management_tasks
    return task_management_tasks


def get_reward_task_service():
    """Get reward management task service."""
    from .tasks import reward_management_tasks
    return reward_management_tasks


def get_survey_task_service():
    """Get survey task service."""
    from .tasks import survey_tasks
    return survey_tasks


def get_analytics_service():
    """Get analytics service."""
    from .analytics import get_analytics_service
    return get_analytics_service()


def get_email_service():
    """Get email service."""
    from .email_service import send_email_notification
    return send_email_notification


def get_cache_service():
    """Get cache service."""
    from django.core.cache import cache
    return cache


def get_logger_service(name: str):
    """Get logger service."""
    import logging
    return logging.getLogger(name)


def get_webhook_service():
    """Get webhook service."""
    from .webhooks import WebhookService
    return WebhookService()


def get_payment_gateway_service():
    """Get payment gateway service."""
    from .payment_gateway_bridge import PaymentGatewayService
    return PaymentGatewayService()


def get_wallet_service():
    """Get wallet service."""
    from .wallet_bridge import WalletService
    return WalletService()
