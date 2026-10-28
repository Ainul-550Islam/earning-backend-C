# api/cms/tests_new/test_menu_service.py
"""Tests for MenuService."""
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


class TestMenuServiceCRUD(TestCase):

    def test_create_menu(self):
        from api.cms.services_new.MenuService import MenuService
        menu = MenuService.create_menu(name='Header Nav', location='header')
        self.assertIsNotNone(menu)
        self.assertEqual(menu.location, 'header')
        self.assertEqual(menu.slug, 'header-nav')

    def test_create_menu_item(self):
        from api.cms.services_new.MenuService import MenuService
        menu = MenuService.create_menu(name='Footer', location='footer')
        item = MenuService.create_menu_item(menu=menu, label='Home', url='/')
        self.assertIsNotNone(item)
        self.assertEqual(item.label, 'Home')
        self.assertEqual(item.url, '/')
        self.assertEqual(item.menu, menu)

    def test_create_nested_menu_item(self):
        from api.cms.services_new.MenuService import MenuService
        menu = MenuService.create_menu(name='Main', location='header')
        parent = MenuService.create_menu_item(menu=menu, label='Products', url='/products/')
        child = MenuService.create_menu_item(menu=menu, label='Software', url='/software/', parent=parent)
        self.assertEqual(child.parent, parent)

    def test_reorder_items(self):
        from api.cms.services_new.MenuService import MenuService
        menu = MenuService.create_menu(name='Reorder', location='sidebar')
        item1 = MenuService.create_menu_item(menu=menu, label='A', url='/a/', sort_order=0)
        item2 = MenuService.create_menu_item(menu=menu, label='B', url='/b/', sort_order=1)
        success = MenuService.reorder_items([
            {'id': item1.id, 'sort_order': 5},
            {'id': item2.id, 'sort_order': 3},
        ])
        self.assertTrue(success)
        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertEqual(item1.sort_order, 5)
        self.assertEqual(item2.sort_order, 3)

    def test_build_menu_tree(self):
        from api.cms.services_new.MenuService import MenuService
        menu = MenuService.create_menu(name='Tree Test', location='mobile')
        parent = MenuService.create_menu_item(menu=menu, label='Parent', url='/p/')
        MenuService.create_menu_item(menu=menu, label='Child', url='/c/', parent=parent)
        tree = MenuService.build_menu_tree(menu)
        self.assertIsInstance(tree, list)
        self.assertGreater(len(tree), 0)

    def test_get_menu_by_location(self):
        from api.cms.services_new.MenuService import MenuService
        MenuService.create_menu(name='Location Test', location='dashboard')
        found = MenuService.get_menu(location='dashboard')
        self.assertIsNotNone(found)
        self.assertEqual(found.location, 'dashboard')

    def test_delete_menu_item(self):
        from api.cms.services_new.MenuService import MenuService
        from api.cms.models_new.menu import MenuItem
        menu = MenuService.create_menu(name='Del Menu', location='social')
        item = MenuService.create_menu_item(menu=menu, label='Delete Me', url='/del/')
        item_id = item.id
        success = MenuService.delete_menu_item(item)
        self.assertTrue(success)
        self.assertFalse(MenuItem.objects.filter(id=item_id).exists())
