# api/cms/tests/test_smartlink.py
"""Tests for SmartLink geo+device routing."""
from django.test import TestCase
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate as Survey, SurveyCompletion, SurveyCategory, SurveyQuestion
    )
    from api.cms.models_new.survey_rewards import (
        SurveyReward, RewardTransaction as Transaction, RewardPool
    )
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
    )
except Exception:
    pass


class TestSmartLinkService(TestCase):
    def setUp(self):
        from api.cms.factories import SmartLinkFactory
        from django.core.cache import cache
        cache.clear()
        self.smartlink = SmartLinkFactory.create(
            name='Test SL',
            offers=[
                {'url': 'https://offer.com/us', 'payout': 1.00},
                {'url': 'https://offer.com/global', 'payout': 0.50},
            ]
        )

    def test_resolve_returns_url(self):
        from api.cms.services_new.SmartLinkService import SmartLinkService
        result = SmartLinkService.resolve(slug=self.smartlink.slug, ip='8.8.8.8')
        self.assertIn('redirect_url', result)
        self.assertNotIn('error', result)

    def test_resolve_invalid_slug(self):
        from api.cms.services_new.SmartLinkService import SmartLinkService
        result = SmartLinkService.resolve(slug='does-not-exist')
        self.assertIn('error', result)

    def test_detect_device_mobile(self):
        from api.cms.services_new.SmartLinkService import SmartLinkService
        ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)'
        device = SmartLinkService._detect_device(ua)
        self.assertEqual(device, 'mobile')

    def test_detect_device_desktop(self):
        from api.cms.services_new.SmartLinkService import SmartLinkService
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        device = SmartLinkService._detect_device(ua)
        self.assertEqual(device, 'desktop')

    def test_get_analytics(self):
        from api.cms.services_new.SmartLinkService import SmartLinkService
        data = SmartLinkService.get_analytics(self.smartlink.slug)
        self.assertIn('total_clicks', data)

    def test_best_offer_rotation(self):
        """Best payout rotation should return highest payout rule."""
        from api.cms.models_new.smartlink import SmartLinkRule
        best = self.smartlink.get_best_offer()
        self.assertIsNotNone(best)
        # highest payout should be selected
        rules = list(self.smartlink.routing_rules.filter(is_active=True).order_by('-payout_usd'))
        if rules:
            self.assertEqual(best.id, rules[0].id)
