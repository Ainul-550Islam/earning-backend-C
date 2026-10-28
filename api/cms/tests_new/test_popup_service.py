# api/cms/tests_new/test_popup_service.py
"""Tests for PopupService."""
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
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class TestPopupServiceCRUD(TestCase):

    def test_create_popup(self):
        from api.cms.services_new.PopupService import PopupService
        popup = PopupService.create_popup({
            'name': 'Test Popup',
            'title': 'Hello!',
            'body': 'Welcome to our site.',
            'popup_type': 'modal',
            'status': 'active',
        })
        self.assertIsNotNone(popup)
        self.assertEqual(popup.name, 'Test Popup')
        self.assertEqual(popup.popup_type, 'modal')

    def test_update_popup(self):
        from api.cms.services_new.PopupService import PopupService
        popup = PopupService.create_popup({'name': 'Update Me', 'title': 'T', 'body': 'B', 'popup_type': 'toast', 'status': 'draft'})
        success = PopupService.update_popup(popup, {'title': 'Updated Title'})
        popup.refresh_from_db()
        self.assertTrue(success)
        self.assertEqual(popup.title, 'Updated Title')

    def test_soft_delete_popup(self):
        from api.cms.services_new.PopupService import PopupService
        from api.cms.models_new.popup import Popup
        popup = PopupService.create_popup({'name': 'Del', 'title': 'T', 'body': 'B', 'popup_type': 'modal', 'status': 'active'})
        pid = popup.id
        PopupService.delete_popup(popup, hard=False)
        popup.refresh_from_db()
        self.assertEqual(popup.status, 'archived')
        self.assertFalse(popup.is_active)

    def test_hard_delete_popup(self):
        from api.cms.services_new.PopupService import PopupService
        from api.cms.models_new.popup import Popup
        popup = PopupService.create_popup({'name': 'HardDel', 'title': 'T', 'body': 'B', 'popup_type': 'modal', 'status': 'active'})
        pid = popup.id
        PopupService.delete_popup(popup, hard=True)
        self.assertFalse(Popup.objects.filter(id=pid).exists())


class TestPopupServiceStats(TestCase):

    def setUp(self):
        from api.cms.services_new.PopupService import PopupService
        self.popup = PopupService.create_popup({
            'name': 'Stats Popup', 'title': 'T', 'body': 'B',
            'popup_type': 'modal', 'status': 'active', 'is_active': True,
        })

    def test_record_view(self):
        from api.cms.services_new.PopupService import PopupService
        PopupService.record_view(self.popup)
        self.popup.refresh_from_db()
        self.assertEqual(self.popup.total_views, 1)

    def test_record_click(self):
        from api.cms.services_new.PopupService import PopupService
        PopupService.record_click(self.popup)
        self.popup.refresh_from_db()
        self.assertEqual(self.popup.total_clicks, 1)

    def test_record_dismissal(self):
        from api.cms.services_new.PopupService import PopupService
        PopupService.record_dismissal(self.popup)
        self.popup.refresh_from_db()
        self.assertEqual(self.popup.total_dismissals, 1)

    def test_get_popup_stats(self):
        from api.cms.services_new.PopupService import PopupService
        stats = PopupService.get_popup_stats(self.popup, days=7)
        self.assertIn('popup_id', stats)
        self.assertIn('all_time', stats)
        self.assertEqual(stats['popup_id'], self.popup.id)

    def test_ctr_calculation(self):
        from api.cms.services_new.PopupService import PopupService
        for _ in range(10):
            PopupService.record_view(self.popup)
        for _ in range(3):
            PopupService.record_click(self.popup)
        self.popup.refresh_from_db()
        self.assertAlmostEqual(self.popup.click_through_rate, 30.0, places=0)


class TestPopupABTest(TestCase):

    def setUp(self):
        from api.cms.services_new.PopupService import PopupService
        self.popup = PopupService.create_popup({
            'name': 'AB Popup', 'title': 'T', 'body': 'B',
            'popup_type': 'modal', 'status': 'active',
        })

    def test_create_ab_test(self):
        from api.cms.services_new.PopupService import PopupService
        test = PopupService.create_ab_test(
            popup=self.popup,
            name='Test A vs B',
            variant_a='<h1>Hello A</h1>',
            variant_b='<h1>Hello B</h1>',
            split_pct=50.0,
        )
        self.assertIsNotNone(test)
        self.assertEqual(test.status, 'running')
        self.assertEqual(test.split_pct, 50.0)

    def test_end_ab_test(self):
        from api.cms.services_new.PopupService import PopupService
        test = PopupService.create_ab_test(
            popup=self.popup, name='Test End', variant_a='A', variant_b='B'
        )
        success = PopupService.end_ab_test(test, winner='B')
        test.refresh_from_db()
        self.assertTrue(success)
        self.assertEqual(test.status, 'completed')
        self.assertEqual(test.winner, 'B')

    def test_ab_test_result(self):
        from api.cms.services_new.PopupService import PopupService
        test = PopupService.create_ab_test(
            popup=self.popup, name='Test Result', variant_a='A', variant_b='B'
        )
        result = PopupService.get_ab_test_result(test)
        self.assertIn('variant_a', result)
        self.assertIn('variant_b', result)
        self.assertIn('test_id', result)
