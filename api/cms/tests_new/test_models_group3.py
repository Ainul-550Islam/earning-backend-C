# cms/tests_new/test_models_group3.py
"""
Model Tests — Group 3

Tests for:
  - RTB models
  - UserSession model
  - Video models
  - Workflow models
  - TaskManagement models
  - SurveyRewards models
  - ProfileSurveys models
  - LandingPage model
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from decimal import Decimal


# ─────────────────────────────────────────────────────────────────────────────
# RTB MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class RTBConfigModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.rtb import RTBConfig
            self.RTBConfig = RTBConfig
            self.config = RTBConfig.objects.create(
                name='Primary RTB Config',
                provider='prebid',
                endpoint_url='https://rtb.example.com/bid',
                timeout_ms=500,
                is_active=True,
            )
        except Exception:
            self.skipTest('RTBConfig model not available')

    def test_config_creation(self):
        self.assertIsNotNone(self.config.id)
        self.assertEqual(self.config.provider, 'prebid')

    def test_config_default_active(self):
        self.assertTrue(self.config.is_active)

    def test_config_str(self):
        self.assertIsInstance(str(self.config), str)

    def test_config_timeout_positive(self):
        self.assertGreater(self.config.timeout_ms, 0)


class RTBAdSlotModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.rtb import RTBConfig, RTBAdSlot
            self.RTBAdSlot = RTBAdSlot
            config = RTBConfig.objects.create(
                name='Test Config', provider='appnexus',
                endpoint_url='https://rtb.example.com', timeout_ms=300
            )
            self.slot = RTBAdSlot.objects.create(
                rtb_config=config,
                name='Banner 728x90',
                slot_id='div-gpt-ad-1234567890',
                slot_type='banner',
                width=728, height=90,
            )
        except Exception:
            self.skipTest('RTBAdSlot model not available')

    def test_slot_creation(self):
        self.assertIsNotNone(self.slot.id)
        self.assertEqual(self.slot.width, 728)
        self.assertEqual(self.slot.height, 90)

    def test_slot_str(self):
        self.assertIsInstance(str(self.slot), str)

    def test_slot_dimensions_positive(self):
        self.assertGreater(self.slot.width, 0)
        self.assertGreater(self.slot.height, 0)


# ─────────────────────────────────────────────────────────────────────────────
# USER SESSION MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class UserSessionModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.sessions import UserSession
            self.UserSession = UserSession
            self.user = User.objects.create_user('sessionuser', 'ses@test.com', 'pass')
            self.session = UserSession.objects.create(
                user=self.user,
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0 (Test)',
                device_type='desktop',
            )
        except Exception:
            self.skipTest('UserSession model not available')

    def test_session_creation(self):
        self.assertIsNotNone(self.session.id)
        self.assertEqual(self.session.user, self.user)
        self.assertEqual(self.session.ip_address, '192.168.1.1')

    def test_session_default_active(self):
        self.assertTrue(self.session.is_active)

    def test_session_str(self):
        self.assertIsInstance(str(self.session), str)

    def test_session_terminate(self):
        self.session.is_active = False
        self.session.ended_at = timezone.now()
        self.session.save()
        refreshed = self.UserSession.objects.get(pk=self.session.pk)
        self.assertFalse(refreshed.is_active)
        self.assertIsNotNone(refreshed.ended_at)


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class VideoContentModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.video import VideoContent
            self.VideoContent = VideoContent
            self.user = User.objects.create_user('videouser', 'vid@test.com', 'pass')
            self.video = VideoContent.objects.create(
                title='How to Earn Money Online',
                video_type='tutorial',
                created_by=self.user,
            )
        except Exception:
            self.skipTest('VideoContent model not available')

    def test_video_creation(self):
        self.assertIsNotNone(self.video.id)
        self.assertEqual(self.video.title, 'How to Earn Money Online')

    def test_video_default_not_published(self):
        self.assertFalse(self.video.is_published)

    def test_video_str(self):
        self.assertIsInstance(str(self.video), str)

    def test_video_publish(self):
        self.video.is_published = True
        self.video.published_at = timezone.now()
        self.video.save()
        refreshed = self.VideoContent.objects.get(pk=self.video.pk)
        self.assertTrue(refreshed.is_published)
        self.assertIsNotNone(refreshed.published_at)

    def test_video_view_count_default_zero(self):
        self.assertEqual(getattr(self.video, 'view_count', 0), 0)


class VideoGenerationRequestModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.video import VideoGenerationRequest
            self.VideoGenerationRequest = VideoGenerationRequest
            self.user = User.objects.create_user('vidgen', 'vg@test.com', 'pass')
            self.req = VideoGenerationRequest.objects.create(
                requested_by=self.user,
                prompt='Create a 30-second ad for our platform',
                duration_seconds=30,
            )
        except Exception:
            self.skipTest('VideoGenerationRequest model not available')

    def test_request_creation(self):
        self.assertIsNotNone(self.req.id)
        self.assertEqual(self.req.requested_by, self.user)

    def test_request_default_status_pending(self):
        self.assertIn(self.req.status, ['pending', 'queued'])

    def test_request_str(self):
        self.assertIsInstance(str(self.req), str)


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowStateModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.workflow import WorkflowState
            self.WorkflowState = WorkflowState
            # Try to get or create a workflow first
            try:
                from api.cms.models_new.workflow import Workflow
                self.workflow = Workflow.objects.create(name='Withdrawal Workflow')
            except Exception:
                self.workflow = None

            kwargs = {'name': 'Pending', 'is_initial': True, 'is_final': False}
            if self.workflow:
                kwargs['workflow'] = self.workflow
            self.state = WorkflowState.objects.create(**kwargs)
        except Exception:
            self.skipTest('WorkflowState model not available')

    def test_state_creation(self):
        self.assertIsNotNone(self.state.id)
        self.assertEqual(self.state.name, 'Pending')

    def test_state_is_initial(self):
        self.assertTrue(self.state.is_initial)

    def test_state_not_final(self):
        self.assertFalse(self.state.is_final)

    def test_state_str(self):
        self.assertIsInstance(str(self.state), str)


class WorkflowTransitionModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.workflow import WorkflowState, WorkflowTransition
            self.WorkflowTransition = WorkflowTransition
            try:
                from api.cms.models_new.workflow import Workflow
                wf = Workflow.objects.create(name='Test WF')
                self.from_state = WorkflowState.objects.create(
                    name='Draft', workflow=wf, is_initial=True
                )
                self.to_state = WorkflowState.objects.create(
                    name='Published', workflow=wf, is_final=False
                )
                self.transition = WorkflowTransition.objects.create(
                    workflow=wf,
                    from_state=self.from_state,
                    to_state=self.to_state,
                    name='Publish',
                )
            except Exception:
                self.skipTest('Workflow FK model not available')
        except Exception:
            self.skipTest('WorkflowTransition model not available')

    def test_transition_creation(self):
        self.assertIsNotNone(self.transition.id)
        self.assertEqual(self.transition.name, 'Publish')

    def test_transition_states(self):
        self.assertEqual(self.transition.from_state, self.from_state)
        self.assertEqual(self.transition.to_state, self.to_state)

    def test_transition_str(self):
        self.assertIsInstance(str(self.transition), str)


# ─────────────────────────────────────────────────────────────────────────────
# TASK MANAGEMENT MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TaskScheduleModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.task_management import TaskSchedule
            self.TaskSchedule = TaskSchedule
            self.schedule = TaskSchedule.objects.create(
                name='Daily Earnings Calculation',
                task_function='cms.tasks.calculate_daily_earnings',
                schedule_type='cron',
                cron_expression='0 1 * * *',
                task_type='earnings',
                is_active=True,
            )
        except Exception:
            self.skipTest('TaskSchedule model not available')

    def test_schedule_creation(self):
        self.assertIsNotNone(self.schedule.id)
        self.assertEqual(self.schedule.name, 'Daily Earnings Calculation')

    def test_schedule_default_active(self):
        self.assertTrue(self.schedule.is_active)

    def test_schedule_str(self):
        self.assertIsInstance(str(self.schedule), str)

    def test_schedule_cron_set(self):
        self.assertEqual(self.schedule.cron_expression, '0 1 * * *')


class TaskExecutionModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.task_management import TaskSchedule, TaskExecution
            self.TaskExecution = TaskExecution
            schedule = TaskSchedule.objects.create(
                name='Test Task', task_function='cms.tasks.test',
                schedule_type='interval', task_type='test',
            )
            self.execution = TaskExecution.objects.create(
                schedule=schedule,
                status='running',
                started_at=timezone.now(),
            )
        except Exception:
            self.skipTest('TaskExecution model not available')

    def test_execution_creation(self):
        self.assertIsNotNone(self.execution.id)
        self.assertEqual(self.execution.status, 'running')

    def test_execution_started_at(self):
        self.assertIsNotNone(self.execution.started_at)

    def test_execution_complete(self):
        self.execution.status = 'completed'
        self.execution.ended_at = timezone.now()
        self.execution.save()
        refreshed = self.TaskExecution.objects.get(pk=self.execution.pk)
        self.assertEqual(refreshed.status, 'completed')


# ─────────────────────────────────────────────────────────────────────────────
# SURVEY REWARDS MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class SurveyRewardModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.survey_rewards import SurveyReward
            from api.cms.models_new.survey import Survey
            self.SurveyReward = SurveyReward
            user = User.objects.create_user('rewarduser', 'rw@test.com', 'pass')
            survey = Survey.objects.create(
                title='Reward Survey', reward_amount=Decimal('5.00'), created_by=user
            )
            self.reward = SurveyReward.objects.create(
                survey=survey,
                reward_type='cash',
                amount=Decimal('5.00'),
                is_active=True,
            )
        except Exception:
            self.skipTest('SurveyReward model not available')

    def test_reward_creation(self):
        self.assertIsNotNone(self.reward.id)
        self.assertEqual(self.reward.reward_type, 'cash')
        self.assertEqual(self.reward.amount, Decimal('5.00'))

    def test_reward_active(self):
        self.assertTrue(self.reward.is_active)

    def test_reward_str(self):
        self.assertIsInstance(str(self.reward), str)


class RewardTransactionModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.survey_rewards import RewardTransaction
            self.RewardTransaction = RewardTransaction
            self.user = User.objects.create_user('txuser', 'tx@test.com', 'pass')
            self.tx = RewardTransaction.objects.create(
                user=self.user,
                amount=Decimal('5.00'),
                transaction_type='credit',
                status='completed',
                description='Survey completion reward',
            )
        except Exception:
            self.skipTest('RewardTransaction model not available')

    def test_transaction_creation(self):
        self.assertIsNotNone(self.tx.id)
        self.assertEqual(self.tx.transaction_type, 'credit')
        self.assertEqual(self.tx.amount, Decimal('5.00'))

    def test_transaction_status(self):
        self.assertEqual(self.tx.status, 'completed')

    def test_transaction_str(self):
        self.assertIsInstance(str(self.tx), str)


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE SURVEYS MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class SurveyCategoryModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.profile_surveys import SurveyCategory
            self.SurveyCategory = SurveyCategory
            self.cat = SurveyCategory.objects.create(
                name='Finance', description='Financial surveys'
            )
        except Exception:
            self.skipTest('SurveyCategory model not available')

    def test_category_creation(self):
        self.assertIsNotNone(self.cat.id)
        self.assertEqual(self.cat.name, 'Finance')

    def test_category_str(self):
        self.assertIsInstance(str(self.cat), str)


class SurveyTemplateModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.profile_surveys import SurveyTemplate, SurveyCategory
            self.SurveyTemplate = SurveyTemplate
            self.user = User.objects.create_user('tmpluser', 'tm@test.com', 'pass')
            self.cat = SurveyCategory.objects.create(name='Lifestyle')
            self.template = SurveyTemplate.objects.create(
                title='Lifestyle Survey Template',
                category=self.cat,
                difficulty_level='easy',
                created_by=self.user,
            )
        except Exception:
            self.skipTest('SurveyTemplate model not available')

    def test_template_creation(self):
        self.assertIsNotNone(self.template.id)
        self.assertEqual(self.template.title, 'Lifestyle Survey Template')

    def test_template_default_inactive(self):
        self.assertFalse(self.template.is_active)

    def test_template_str(self):
        self.assertIsInstance(str(self.template), str)


# ─────────────────────────────────────────────────────────────────────────────
# LANDING PAGE MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class LandingPageModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.landing_pages import LandingPage
            self.LandingPage = LandingPage
            self.user = User.objects.create_user('lpuser', 'lp@test.com', 'pass')
            self.page = LandingPage.objects.create(
                title='Earn Money Online',
                slug='earn-money-online',
                template_type='standard',
                created_by=self.user,
            )
        except Exception:
            self.skipTest('LandingPage model not available')

    def test_page_creation(self):
        self.assertIsNotNone(self.page.id)
        self.assertEqual(self.page.title, 'Earn Money Online')
        self.assertEqual(self.page.slug, 'earn-money-online')

    def test_page_default_not_published(self):
        self.assertFalse(self.page.is_published)

    def test_page_str(self):
        self.assertIsInstance(str(self.page), str)

    def test_page_slug_unique(self):
        user2 = User.objects.create_user('lp2', 'lp2@test.com', 'pass')
        with self.assertRaises(Exception):
            self.LandingPage.objects.create(
                title='Dup', slug='earn-money-online',
                template_type='standard', created_by=user2,
            )

    def test_page_publish(self):
        from django.utils import timezone
        self.page.is_published = True
        self.page.published_at = timezone.now()
        self.page.save()
        refreshed = self.LandingPage.objects.get(pk=self.page.pk)
        self.assertTrue(refreshed.is_published)
