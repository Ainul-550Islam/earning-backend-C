"""
tests/test_constants.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for constants.py and choices.py — value sanity,
type correctness, and cross-reference integrity.
"""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import constants as C


class TestRetentionConstants(unittest.TestCase):

    def test_postback_log_retention_positive(self):
        self.assertGreater(C.POSTBACK_LOG_RETENTION_DAYS, 0)

    def test_click_log_retention_positive(self):
        self.assertGreater(C.CLICK_LOG_RETENTION_DAYS, 0)

    def test_impression_retention_positive(self):
        self.assertGreater(C.IMPRESSION_RETENTION_DAYS, 0)

    def test_api_log_retention_positive(self):
        self.assertGreater(C.API_LOG_RETENTION_DAYS, 0)

    def test_performance_metric_retention_positive(self):
        self.assertGreater(C.PERFORMANCE_METRIC_RETENTION_DAYS, 0)

    def test_points_expiry_days_reasonable(self):
        self.assertGreater(C.POINTS_EXPIRY_DAYS, 0)
        self.assertLessEqual(C.POINTS_EXPIRY_DAYS, 3650)  # <= 10 years


class TestRetryConstants(unittest.TestCase):

    def test_max_postback_retries_positive(self):
        self.assertGreater(C.MAX_POSTBACK_RETRIES, 0)

    def test_postback_retry_delays_list(self):
        self.assertIsInstance(C.POSTBACK_RETRY_DELAYS, list)

    def test_postback_retry_delays_length_matches_max(self):
        self.assertEqual(len(C.POSTBACK_RETRY_DELAYS), C.MAX_POSTBACK_RETRIES)

    def test_postback_retry_delays_ascending(self):
        d = C.POSTBACK_RETRY_DELAYS
        self.assertEqual(d, sorted(d), 'Retry delays should be ascending')

    def test_max_payment_retry_positive(self):
        self.assertGreater(C.MAX_PAYMENT_RETRY_ATTEMPTS, 0)

    def test_payment_retry_intervals_list(self):
        self.assertIsInstance(C.PAYMENT_RETRY_INTERVALS_DAYS, list)

    def test_payment_retry_intervals_length_matches_max(self):
        self.assertEqual(
            len(C.PAYMENT_RETRY_INTERVALS_DAYS),
            C.MAX_PAYMENT_RETRY_ATTEMPTS,
        )

    def test_max_delivery_retry_positive(self):
        self.assertGreater(C.MAX_DELIVERY_RETRY_ATTEMPTS, 0)

    def test_max_bot_retries_positive(self):
        self.assertGreater(C.MAX_BOT_RETRIES, 0)


class TestWebhookConstants(unittest.TestCase):

    def test_webhook_timeout_int_or_float(self):
        self.assertIsInstance(C.WEBHOOK_TIMEOUT_SECONDS, (int, float))

    def test_webhook_timeout_reasonable(self):
        self.assertGreater(C.WEBHOOK_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(C.WEBHOOK_TIMEOUT_SECONDS, 120)

    def test_webhook_signature_header_is_string(self):
        self.assertIsInstance(C.WEBHOOK_SIGNATURE_HEADER, str)
        self.assertTrue(C.WEBHOOK_SIGNATURE_HEADER.startswith('X-'),
                        'HTTP header should start with X-')


class TestIVTConstants(unittest.TestCase):

    def test_max_ivt_percentage_range(self):
        self.assertGreater(C.MAX_IVT_PERCENTAGE, 0)
        self.assertLessEqual(C.MAX_IVT_PERCENTAGE, 100)

    def test_critical_ivt_greater_than_max(self):
        self.assertGreater(C.CRITICAL_IVT_THRESHOLD, C.MAX_IVT_PERCENTAGE)

    def test_critical_ivt_not_over_100(self):
        self.assertLessEqual(C.CRITICAL_IVT_THRESHOLD, 100)


class TestCallConstants(unittest.TestCase):

    def test_call_ring_timeout_positive(self):
        self.assertGreater(C.CALL_RING_TIMEOUT_SECONDS, 0)

    def test_call_max_duration_positive(self):
        self.assertGreater(C.CALL_MAX_DURATION_SECONDS, 0)

    def test_call_max_duration_gt_ring_timeout(self):
        self.assertGreater(C.CALL_MAX_DURATION_SECONDS, C.CALL_RING_TIMEOUT_SECONDS)

    def test_presence_offline_threshold_positive(self):
        self.assertGreater(C.PRESENCE_OFFLINE_AFTER_SECONDS, 0)


class TestSubscriptionConstants(unittest.TestCase):

    def test_renewal_reminder_days_positive(self):
        self.assertGreater(C.RENEWAL_REMINDER_DAYS, 0)

    def test_trial_ending_reminder_days_positive(self):
        self.assertGreater(C.TRIAL_ENDING_REMINDER_DAYS, 0)

    def test_trial_ending_less_than_renewal(self):
        self.assertLessEqual(C.TRIAL_ENDING_REMINDER_DAYS, C.RENEWAL_REMINDER_DAYS)


class TestTaskStringConstants(unittest.TestCase):
    """Celery task path constants must be dotted strings."""

    TASK_CONSTANTS = [
        'TASK_BOT_PROCESS', 'TASK_EXPIRE_CODES', 'TASK_CHECK_LOW_STOCK',
        'TASK_SYNC_STOCK_COUNTS', 'TASK_RUN_IMAGE_SCAN', 'TASK_RUN_TEXT_ANALYSIS',
        'TASK_SCAN_SUBMISSION', 'TASK_RETRAIN_MODEL', 'TASK_RETRY_FAILED_DELIVERIES',
        'TASK_SCHEDULE_MAINTENANCE', 'TASK_END_MAINTENANCE',
        'TASK_CHECK_UPDATES', 'TASK_CLEANUP_OLD_POLICIES',
        'TASK_EVALUATE_RULES', 'TASK_CLEANUP_OLD_SUBMISSIONS',
    ]

    def test_task_constants_are_strings(self):
        for name in self.TASK_CONSTANTS:
            with self.subTest(const=name):
                val = getattr(C, name, None)
                self.assertIsNotNone(val, f'Missing constant: {name}')
                self.assertIsInstance(val, str, f'{name} should be str')

    def test_task_constants_are_dotted_paths(self):
        for name in self.TASK_CONSTANTS:
            val = getattr(C, name, '')
            with self.subTest(const=name):
                self.assertIn('.', val, f'{name}="{val}" should be a dotted module path')


class TestChoicesModule(unittest.TestCase):
    """choices.py — all added classes are iterable and have correct values."""

    def setUp(self):
        import choices as ch
        self.ch = ch

    @staticmethod
    def _vals(cls):
        result = []
        for v in cls:
            val = v.value
            result.append(val[0] if isinstance(val, tuple) else val)
        return result

    def test_subscription_status_has_active_and_cancelled(self):
        vals = self._vals(self.ch.SubscriptionStatus)
        self.assertIn('active', vals)
        self.assertIn('cancelled', vals)

    def test_subscription_status_has_past_due(self):
        self.assertIn('past_due', self._vals(self.ch.SubscriptionStatus))

    def test_payment_status_has_completed_failed(self):
        vals = self._vals(self.ch.PaymentStatus)
        self.assertIn('completed', vals)
        self.assertIn('failed', vals)

    def test_broadcast_status_has_draft_to_sent(self):
        vals = self._vals(self.ch.BroadcastStatus)
        for expected in ('draft', 'scheduled', 'sending', 'sent', 'failed'):
            self.assertIn(expected, vals)

    def test_call_status_has_ringing_ended(self):
        vals = self._vals(self.ch.CallStatus)
        self.assertIn('ringing', vals)
        self.assertIn('ended', vals)

    def test_bot_status_values(self):
        vals = self._vals(self.ch.BotStatus)
        for expected in ('idle', 'running', 'paused', 'stopped'):
            self.assertIn(expected, vals)

    def test_moderation_auto_values(self):
        vals = self._vals(self.ch.ModerationStatus)
        self.assertIn('auto_ok', vals)
        self.assertIn('auto_reject', vals)

    def test_inventory_status_out_of_stock(self):
        self.assertIn('out_of_stock', self._vals(self.ch.InventoryStatus))

    def test_code_status_has_redeemed(self):
        self.assertIn('redeemed', self._vals(self.ch.CodeStatus))

    def test_maintenance_status_values(self):
        vals = self._vals(self.ch.MaintenanceStatus)
        self.assertIn('scheduled', vals)
        self.assertIn('completed', vals)

    def test_policy_status_has_deprecated(self):
        self.assertIn('deprecated', self._vals(self.ch.PolicyStatus))

    def test_fraud_type_values(self):
        vals = self._vals(self.ch.FraudType)
        self.assertIn('click_fraud', vals)
        self.assertIn('bot_traffic', vals)

    def test_commission_status_has_paid(self):
        self.assertIn('paid', self._vals(self.ch.CommissionStatus))

    def test_rate_source_has_api_exchange(self):
        vals = self._vals(self.ch.RateSource)
        self.assertIn('api', vals)
        self.assertIn('exchange', vals)

    def test_choices_are_iterable(self):
        for attr in ['SubscriptionStatus', 'PaymentStatus', 'BroadcastStatus',
                     'CallStatus', 'BotStatus', 'ModerationStatus', 'InventoryStatus',
                     'CodeStatus', 'MaintenanceStatus', 'PolicyStatus',
                     'FraudType', 'FraudAction', 'CommissionStatus',
                     'TransactionType', 'RateSource']:
            with self.subTest(cls=attr):
                cls = getattr(self.ch, attr, None)
                self.assertIsNotNone(cls, f'choices.{attr} missing')
                vals = list(cls)
                self.assertGreater(len(vals), 0, f'choices.{attr} is empty')


if __name__ == '__main__':
    unittest.main()
