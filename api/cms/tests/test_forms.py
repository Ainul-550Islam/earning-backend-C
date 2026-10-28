# api/cms/tests/test_forms.py
"""Tests for FormBuilder."""
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


class TestFormBuilderService(TestCase):
    def setUp(self):
        from api.cms.factories import DynamicFormFactory, UserFactory
        self.user = UserFactory.create()
        self.form = DynamicFormFactory.create(num_fields=3)

    def test_get_form_by_slug(self):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        form = FormBuilderService.get_form(self.form.slug)
        self.assertIsNotNone(form)
        self.assertEqual(form.id, self.form.id)

    def test_get_form_not_found(self):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        form = FormBuilderService.get_form('nonexistent-slug')
        self.assertIsNone(form)

    def test_form_schema_has_fields(self):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        schema = FormBuilderService.get_form_schema(self.form)
        self.assertIn('fields', schema)
        self.assertEqual(len(schema['fields']), 3)
        self.assertIn('submit_text', schema)

    def test_submit_form_success(self):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        schema = FormBuilderService.get_form_schema(self.form)
        data = {f['name']: 'test value' for f in schema['fields'] if f['name']}
        result = FormBuilderService.submit_form(
            self.form.id, data=data,
            user=self.user, ip='127.0.0.1',
        )
        self.assertTrue(result['success'])
        self.assertIn('submission_id', result)

    def test_validation_required_field(self):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        # Submit empty data — first field is required
        result = FormBuilderService.submit_form(self.form.id, data={}, user=self.user)
        self.assertFalse(result['success'])
        self.assertIn('errors', result)

    def test_get_submissions(self):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        schema = FormBuilderService.get_form_schema(self.form)
        data = {f['name']: 'value' for f in schema['fields']}
        FormBuilderService.submit_form(self.form.id, data=data, user=self.user)
        subs = FormBuilderService.get_submissions(self.form.id)
        self.assertIsInstance(subs, list)
        self.assertGreater(len(subs), 0)
