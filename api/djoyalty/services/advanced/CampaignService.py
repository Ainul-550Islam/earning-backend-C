# api/djoyalty/services/advanced/CampaignService.py
import logging

# FIXED: ab_testing.py (ABTestVariant, LoyaltyABTest) was orphaned
# Now used in CampaignService to assign customers to A/B test variants
try:
    from ...ab_testing import LoyaltyABTest, ABTestVariant
    _ab_testing_available = True
except ImportError:
    _ab_testing_available = False
from decimal import Decimal
from ...models.campaigns import LoyaltyCampaign, CampaignParticipant

logger = logging.getLogger(__name__)

class CampaignService:
    @staticmethod
    def get_active_campaigns(tenant=None):
        return LoyaltyCampaign.active_campaigns.filter(tenant=tenant) if tenant else LoyaltyCampaign.active_campaigns.all()

    @staticmethod
    def get_campaign_multiplier(customer, tenant=None) -> Decimal:
        campaigns = CampaignService.get_active_campaigns(tenant=tenant)
        max_multiplier = Decimal('1.0')
        for campaign in campaigns:
            if campaign.campaign_type in ('points_multiplier', 'double_points', 'flash_earn'):
                m = campaign.multiplier or Decimal('1.0')
                if m > max_multiplier:
                    max_multiplier = m
        return max_multiplier

    @staticmethod
    def join_campaign(customer, campaign_id: int):
        campaign = LoyaltyCampaign.objects.get(id=campaign_id)
        from ...exceptions import CampaignInactiveError, CampaignAlreadyJoinedError
        if campaign.status != 'active':
            raise CampaignInactiveError()
        if CampaignParticipant.objects.filter(campaign=campaign, customer=customer).exists():
            raise CampaignAlreadyJoinedError()
        return CampaignParticipant.objects.create(campaign=campaign, customer=customer)

    @staticmethod
    def get_ab_variant(campaign_id: int, customer) -> str:
        """
        Get A/B test variant for a customer in a campaign।
        FIXED: ab_testing.py LoyaltyABTest was orphaned -- now called here।
        Returns variant name ('control', 'variant_a', 'variant_b') or 'control' if disabled।
        """
        if not _ab_testing_available:
            return 'control'
        try:
            test = LoyaltyABTest.get_active_test(campaign_id=campaign_id)
            if not test:
                return 'control'
            return test.get_variant_for_customer(customer)
        except Exception:
            return 'control'
