# api/offer_inventory/marketing/__init__.py
"""
Marketing Automation Package.
Campaigns, email, push, loyalty, referral, promo codes.
"""
from .campaign_manager    import MarketingCampaignService
from .email_marketing     import EmailMarketingService
from .push_notifications  import PushNotificationService
from .loyalty_program     import LoyaltyManager
from .referral_program    import ReferralProgramManager
from .promotional_codes   import PromoCodeManager

__all__ = [
    'MarketingCampaignService',
    'EmailMarketingService',
    'PushNotificationService',
    'LoyaltyManager',
    'ReferralProgramManager',
    'PromoCodeManager',
]
