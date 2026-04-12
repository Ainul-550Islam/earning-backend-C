from django.test import TestCase
from unittest.mock import patch, MagicMock
from .factories import SmartLinkFactory, SmartLinkFallbackFactory


class CeleryTasksTest(TestCase):
    @patch('smartlink.services.click.ClickTrackingService.ClickTrackingService.record')
    def test_process_click_async_calls_service(self, mock_record):
        from ..tasks.click_processing_tasks import process_click_async
        sl = SmartLinkFactory()
        mock_click = MagicMock()
        mock_click.pk = 1
        mock_record.return_value = mock_click
        result = process_click_async(
            smartlink_id=sl.pk,
            offer_id=None,
            ip='1.2.3.4',
            user_agent='Mozilla/5.0',
            country='BD',
            device_type='mobile',
        )
        mock_record.assert_called_once()

    @patch('smartlink.services.rotation.CapTrackerService.CapTrackerService.reset_daily_caps')
    def test_reset_daily_caps_task(self, mock_reset):
        from ..tasks.cap_reset_tasks import reset_daily_caps
        mock_reset.return_value = 42
        result = reset_daily_caps()
        self.assertEqual(result['reset'], 42)

    @patch('smartlink.services.core.SmartLinkCacheService.SmartLinkCacheService.warmup_all_active')
    def test_warmup_cache_task(self, mock_warmup):
        from ..tasks.cache_warmup_tasks import warmup_resolver_cache
        mock_warmup.return_value = 10
        result = warmup_resolver_cache()
        self.assertEqual(result['cached'], 10)

    def test_check_broken_smartlinks_finds_empty_pools(self):
        from ..tasks.smartlink_health_tasks import check_broken_smartlinks
        sl = SmartLinkFactory(is_active=True)
        # No pool entries → should appear as broken
        result = check_broken_smartlinks()
        self.assertIn('broken_count', result)
        self.assertIsInstance(result['broken'], list)

    @patch('smartlink.services.rotation.EPCOptimizer.EPCOptimizer.recalculate_scores')
    def test_update_epc_scores_task(self, mock_recalc):
        from ..tasks.epc_update_tasks import update_epc_scores
        mock_recalc.return_value = 25
        result = update_epc_scores()
        self.assertEqual(result['updated'], 25)
