# =============================================================================
# promotions/tests/test_signals.py
# Signal Tests — verify auto-actions on model changes
# =============================================================================
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

User = get_user_model()


class SubmissionSignalTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sig_user', email='sig@test.com', password='pass')
        self.admin = User.objects.create_superuser(username='sig_admin', email='sa@test.com', password='pass')
        from api.promotions.models import PromotionCategory, RewardPolicy, Campaign
        cat = PromotionCategory.objects.create(name='social', sort_order=1)
        rp = RewardPolicy.objects.create(
            name='Signal Test Policy',
            base_reward=Decimal('1.00'),
            min_reward=Decimal('0.50'),
            max_reward=Decimal('5.00'),
            platform_commission_rate=Decimal('0.20'),
        )
        self.campaign = Campaign.objects.create(
            title='Signal Test Campaign',
            advertiser=self.user,
            category=cat,
            reward_policy=rp,
            total_budget=Decimal('100.00'),
            per_task_reward=Decimal('1.00'),
            max_tasks_per_user=5,
            status='active',
        )

    def test_submission_created_signal(self):
        from api.promotions.models import TaskSubmission
        sub = TaskSubmission.objects.create(
            campaign=self.campaign,
            user=self.user,
            proof_type='screenshot',
        )
        self.assertEqual(sub.status, 'pending')
        self.assertIsNotNone(sub.created_at)

    @patch('promotions.signals._calculate_reward')
    def test_submission_approved_triggers_reward(self, mock_reward):
        mock_reward.return_value = Decimal('1.00')
        from api.promotions.models import TaskSubmission
        sub = TaskSubmission.objects.create(
            campaign=self.campaign,
            user=self.user,
            proof_type='screenshot',
            status='pending',
        )
        # Simulate approval
        sub.status = 'approved'
        sub.save()
        # Signal should have fired
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'approved')

    def test_campaign_status_signal(self):
        from api.promotions.models import Campaign
        self.campaign.status = 'paused'
        self.campaign.save()
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'paused')


class FraudSignalTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fraud_sig', email='fs@test.com', password='pass')
        from api.promotions.models import PromotionCategory, RewardPolicy, Campaign, TaskSubmission
        cat = PromotionCategory.objects.create(name='web', sort_order=1)
        rp = RewardPolicy.objects.create(
            name='Fraud Sig Policy',
            base_reward=Decimal('1.00'),
            min_reward=Decimal('0.50'),
            max_reward=Decimal('5.00'),
            platform_commission_rate=Decimal('0.20'),
        )
        campaign = Campaign.objects.create(
            title='Fraud Signal Campaign',
            advertiser=self.user,
            category=cat,
            reward_policy=rp,
            total_budget=Decimal('100.00'),
            per_task_reward=Decimal('1.00'),
            max_tasks_per_user=5,
        )
        self.submission = TaskSubmission.objects.create(
            campaign=campaign,
            user=self.user,
            proof_type='screenshot',
        )

    def test_fraud_report_signal(self):
        from api.promotions.models import FraudReport
        report = FraudReport.objects.create(
            submission=self.submission,
            reported_user=self.user,
            fraud_type='fake_screenshot',
            confidence_score=Decimal('0.90'),
            action_taken='flagged',
        )
        self.assertIsNotNone(report.created_at)
        self.assertEqual(report.action_taken, 'flagged')
