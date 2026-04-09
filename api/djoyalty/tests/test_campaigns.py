# api/djoyalty/tests/test_campaigns.py
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .factories import make_customer, make_campaign


class CampaignServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='CAMPCUST01')
        self.campaign = make_campaign(name='Double Points')

    def test_get_active_campaigns_returns_active(self):
        from djoyalty.services.advanced.CampaignService import CampaignService
        campaigns = CampaignService.get_active_campaigns()
        self.assertIn(self.campaign, list(campaigns))

    def test_get_active_campaigns_excludes_inactive(self):
        from djoyalty.services.advanced.CampaignService import CampaignService
        self.campaign.status = 'ended'
        self.campaign.save()
        campaigns = CampaignService.get_active_campaigns()
        self.assertNotIn(self.campaign, list(campaigns))

    def test_get_campaign_multiplier(self):
        from djoyalty.services.advanced.CampaignService import CampaignService
        multiplier = CampaignService.get_campaign_multiplier(self.customer)
        self.assertGreaterEqual(multiplier, Decimal('1'))

    def test_join_campaign(self):
        from djoyalty.services.advanced.CampaignService import CampaignService
        from djoyalty.models.campaigns import CampaignParticipant
        CampaignService.join_campaign(self.customer, self.campaign.id)
        self.assertTrue(
            CampaignParticipant.objects.filter(campaign=self.campaign, customer=self.customer).exists()
        )

    def test_join_inactive_campaign_raises_error(self):
        from djoyalty.services.advanced.CampaignService import CampaignService
        from djoyalty.exceptions import CampaignInactiveError
        self.campaign.status = 'draft'
        self.campaign.save()
        with self.assertRaises(CampaignInactiveError):
            CampaignService.join_campaign(self.customer, self.campaign.id)

    def test_join_campaign_twice_raises_error(self):
        from djoyalty.services.advanced.CampaignService import CampaignService
        from djoyalty.exceptions import CampaignAlreadyJoinedError
        CampaignService.join_campaign(self.customer, self.campaign.id)
        with self.assertRaises(CampaignAlreadyJoinedError):
            CampaignService.join_campaign(self.customer, self.campaign.id)
