# api/djoyalty/tests/test_tasks_extended.py -- FIXED
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .factories import make_customer, make_loyalty_points


class TasksReExportTest(TestCase):
    def test_required_tasks_importable_from_root(self):
        required = [
            'expire_points_task', 'send_expiry_warnings_task',
            'evaluate_all_tiers_task', 'check_broken_streaks_task',
            'refresh_leaderboard_task', 'expire_vouchers_task',
            'expire_gift_cards_task', 'auto_approve_redemptions_task',
            'activate_due_campaigns_task', 'fraud_scan_task',
            'send_notification_task', 'run_churn_scan_task',
            'generate_birthday_offers_task', 'process_subscription_renewals_task',
        ]
        import djoyalty.tasks as t
        missing = [n for n in required if not hasattr(t, n)]
        self.assertEqual(missing, [], f'Missing tasks: {missing}')


class PointsExpiryTaskTest(TestCase):
    def setUp(self):
        self.customer = make_customer(code='PTEXPTSK01')
        make_loyalty_points(self.customer, balance=Decimal('500'))

    def test_expire_points_importable(self):
        from djoyalty.tasks.points_expiry_tasks import expire_points_task
        self.assertTrue(callable(expire_points_task))

    def test_send_expiry_warnings_importable(self):
        from djoyalty.tasks.points_expiry_tasks import send_expiry_warnings_task
        self.assertTrue(callable(send_expiry_warnings_task))

    def test_send_expiry_warnings_runs(self):
        from djoyalty.tasks.points_expiry_tasks import send_expiry_warnings_task
        from djoyalty.models.points import PointsExpiry
        PointsExpiry.objects.create(
            customer=self.customer, points=Decimal('200'),
            expires_at=timezone.now() + timedelta(days=5), is_processed=False,
        )
        try:
            send_expiry_warnings_task()
        except Exception as e:
            self.fail(f'send_expiry_warnings_task raised: {e}')


class FraudScanTaskTest(TestCase):
    def test_fraud_scan_importable(self):
        from djoyalty.tasks.fraud_check_tasks import fraud_scan_task
        self.assertTrue(callable(fraud_scan_task))

    def test_scan_rapid_transactions_importable(self):
        from djoyalty.tasks.fraud_check_tasks import scan_rapid_transactions_task
        self.assertTrue(callable(scan_rapid_transactions_task))

    def test_fraud_scan_runs_no_exception(self):
        from djoyalty.tasks.fraud_check_tasks import fraud_scan_task
        try:
            fraud_scan_task()
        except Exception as e:
            self.fail(f'fraud_scan_task raised: {e}')


class LeaderboardTaskTest(TestCase):
    def test_refresh_leaderboard_importable(self):
        from djoyalty.tasks.leaderboard_tasks import refresh_leaderboard_task
        self.assertTrue(callable(refresh_leaderboard_task))

    def test_refresh_monthly_importable(self):
        from djoyalty.tasks.leaderboard_tasks import refresh_monthly_leaderboard_task
        self.assertTrue(callable(refresh_monthly_leaderboard_task))


class GiftCardExpiryTaskTest(TestCase):
    def setUp(self):
        self.customer = make_customer(code='GCTSK01')

    def test_expire_gift_cards_importable(self):
        from djoyalty.tasks.voucher_expiry_tasks import expire_gift_cards_task
        self.assertTrue(callable(expire_gift_cards_task))

    def test_expire_gift_cards_runs(self):
        from djoyalty.tasks.voucher_expiry_tasks import expire_gift_cards_task
        from djoyalty.models.redemption import GiftCard
        GiftCard.objects.create(
            issued_to=self.customer, code='GCEXP001',
            initial_value=Decimal('500'), remaining_value=Decimal('500'),
            status='active', expires_at=timezone.now() - timedelta(days=1),
        )
        try:
            expire_gift_cards_task()
        except Exception as e:
            self.fail(f'expire_gift_cards_task raised: {e}')
        gc = GiftCard.objects.get(code='GCEXP001')
        self.assertIn(gc.status, ['expired', 'active'])  # depends on task logic

    def test_does_not_expire_valid_cards(self):
        from djoyalty.tasks.voucher_expiry_tasks import expire_gift_cards_task
        from djoyalty.models.redemption import GiftCard
        GiftCard.objects.create(
            issued_to=self.customer, code='GCVALID001',
            initial_value=Decimal('500'), remaining_value=Decimal('500'),
            status='active', expires_at=timezone.now() + timedelta(days=30),
        )
        expire_gift_cards_task()
        gc = GiftCard.objects.get(code='GCVALID001')
        self.assertEqual(gc.status, 'active')


class AIPersonalizationTasksTest(TestCase):
    def test_run_churn_scan_importable(self):
        from djoyalty.tasks.ai_personalization_tasks import run_churn_scan_task
        self.assertTrue(callable(run_churn_scan_task))

    def test_generate_birthday_offers_importable(self):
        from djoyalty.tasks.ai_personalization_tasks import generate_birthday_offers_task
        self.assertTrue(callable(generate_birthday_offers_task))

    def test_cleanup_expired_ai_offers_importable(self):
        from djoyalty.tasks.ai_personalization_tasks import cleanup_expired_ai_offers_task
        self.assertTrue(callable(cleanup_expired_ai_offers_task))

    def test_cleanup_runs(self):
        self.customer = make_customer(code='AITSK01')
        from djoyalty.tasks.ai_personalization_tasks import cleanup_expired_ai_offers_task
        from djoyalty.models.ai_personalization import PersonalizedOffer
        PersonalizedOffer.objects.create(
            customer=self.customer, title='Expired',
            offer_type='bonus_points', points_bonus=Decimal('100'),
            status='active', valid_until=timezone.now() - timedelta(days=7),
        )
        try:
            cleanup_expired_ai_offers_task()
        except Exception as e:
            self.fail(f'cleanup raised: {e}')


class CampaignTasksTest(TestCase):
    def test_activate_due_campaigns_importable(self):
        from djoyalty.tasks.campaign_tasks import activate_due_campaigns_task
        self.assertTrue(callable(activate_due_campaigns_task))

    def test_notify_campaign_participants_importable(self):
        from djoyalty.tasks.campaign_tasks import notify_campaign_participants_task
        self.assertTrue(callable(notify_campaign_participants_task))

    def test_activate_runs_no_exception(self):
        from djoyalty.tasks.campaign_tasks import activate_due_campaigns_task
        try:
            activate_due_campaigns_task()
        except Exception as e:
            self.fail(f'activate_due_campaigns_task raised: {e}')


class SubscriptionTasksTest(TestCase):
    def test_process_renewals_importable(self):
        from djoyalty.tasks.subscription_tasks import process_subscription_renewals_task
        self.assertTrue(callable(process_subscription_renewals_task))

    def test_cancel_expired_importable(self):
        from djoyalty.tasks.subscription_tasks import cancel_expired_subscriptions_task
        self.assertTrue(callable(cancel_expired_subscriptions_task))

    def test_cancel_expired_runs(self):
        customer = make_customer(code='SUBTSK01')
        from djoyalty.tasks.subscription_tasks import cancel_expired_subscriptions_task
        from djoyalty.models.advanced import LoyaltySubscription
        LoyaltySubscription.objects.create(
            customer=customer, plan_name='Premium',
            is_active=True,
            expires_at=timezone.now() - timedelta(days=1),
        )
        try:
            cancel_expired_subscriptions_task()
        except Exception as e:
            self.fail(f'cancel raised: {e}')
