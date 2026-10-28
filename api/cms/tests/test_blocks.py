# api/cms/tests/test_blocks.py
"""Tests for ContentBlock system."""
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


class TestContentBlockService(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        self.user = UserFactory.create()
        self.parent_type = 'page'
        self.parent_id = 1

    def test_add_rich_text_block(self):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        block = ContentBlockService.add_block(
            self.parent_type, self.parent_id, 'rich_text',
            data={'content': '<p>Hello World</p>'}, user=self.user
        )
        self.assertIn('id', block)
        self.assertEqual(block['block_type'], 'rich_text')

    def test_get_blocks_empty(self):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        blocks = ContentBlockService.get_blocks('page', 999)
        self.assertIsInstance(blocks, list)
        self.assertEqual(len(blocks), 0)

    def test_add_multiple_blocks_with_order(self):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        b1 = ContentBlockService.add_block('page', 100, 'rich_text', {'content': 'A'})
        b2 = ContentBlockService.add_block('page', 100, 'image', {'url': 'img.jpg'})
        blocks = ContentBlockService.get_blocks('page', 100)
        self.assertEqual(len(blocks), 2)
        orders = [b['order'] for b in blocks]
        self.assertEqual(orders, sorted(orders))

    def test_update_block(self):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        block = ContentBlockService.add_block('page', 200, 'rich_text',
                                               {'content': 'original'})
        updated = ContentBlockService.update_block(block['id'], data={'content': 'updated'})
        self.assertEqual(updated['data']['content'], 'updated')

    def test_delete_block(self):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        block = ContentBlockService.add_block('page', 300, 'divider', {})
        success = ContentBlockService.delete_block(block['id'])
        self.assertTrue(success)
        blocks = ContentBlockService.get_blocks('page', 300)
        self.assertEqual(len(blocks), 0)

    def test_reorder_blocks(self):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        b1 = ContentBlockService.add_block('page', 400, 'rich_text', {'content': 'first'})
        b2 = ContentBlockService.add_block('page', 400, 'image', {'url': 'x.jpg'})
        b3 = ContentBlockService.add_block('page', 400, 'cta', {'text': 'click'})
        new_order = [b3['id'], b1['id'], b2['id']]
        success = ContentBlockService.reorder_blocks('page', 400, new_order)
        self.assertTrue(success)

    def test_render_blocks(self):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        ContentBlockService.add_block('page', 500, 'rich_text',
                                       data={'content': '<p>Test</p>'})
        html = ContentBlockService.render_blocks('page', 500)
        self.assertIn('cms-block', html)
        self.assertIn('Test', html)
