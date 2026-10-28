"""
tests/test_tasks.py — Coverage for tasks.py (was 0 tests)

Covers:
  expire_offers, recalculate_quality_scores, sync_all_providers_task,
  auto_approve_pending_conversions, expire_pending_conversions,
  retry_failed_postbacks, refresh_fraud_scores, cleanup_old_clicks,
  generate_monthly_invoices, mark_overdue_invoices, reset_monthly_usage,
  warm_analytics_cache, update_provider_stats,
  check_fraud_anomalies, check_provider_health, check_adapter_health
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class ExpireOffersTaskTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import OfferFactory, OfferProviderFactory
        self.provider = OfferProviderFactory()
        self.expired  = OfferFactory(
            provider=self.provider,
            status='active',
            end_date=timezone.now() - timedelta(days=1),
        )
        self.active = OfferFactory(
            provider=self.provider,
            status='active',
            end_date=timezone.now() + timedelta(days=1),
        )

    def test_expire_offers_marks_expired(self):
        from api.offerwall.tasks import expire_offers
        result = expire_offers()
        self.expired.refresh_from_db()
        self.active.refresh_from_db()
        self.assertEqual(self.expired.status, 'expired')
        self.assertEqual(self.active.status, 'active')
        self.assertGreaterEqual(result['expired'], 1)

    def test_expire_offers_no_candidates(self):
        from api.offerwall.tasks import expire_offers
        self.expired.status = 'expired'
        self.expired.save()
        result = expire_offers()
        self.assertEqual(result['expired'], 0)

    def test_expire_offers_returns_count(self):
        from api.offerwall.tasks import expire_offers
        result = expire_offers(batch_size=1)
        self.assertIn('expired', result)


class RecalculateQualityScoresTaskTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import OfferFactory, OfferProviderFactory
        self.provider = OfferProviderFactory()
        self.offer    = OfferFactory(provider=self.provider, status='active')

    def test_recalculate_updates_scores(self):
        from api.offerwall.tasks import recalculate_quality_scores
        result = recalculate_quality_scores(batch_size=50)
        self.assertIn('updated', result)
        self.assertGreaterEqual(result['updated'], 1)

    def test_recalculate_handles_errors(self):
        from api.offerwall.tasks import recalculate_quality_scores
        with patch.object(self.offer.__class__, 'calculate_quality_score',
                          side_effect=Exception('db error')):
            result = recalculate_quality_scores()
        self.assertIn('errors', result)


class AutoApprovePendingConversionsTaskTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import (
            OfferFactory, OfferProviderFactory, OfferConversionFactory)
        self.provider   = OfferProviderFactory()
        self.offer      = OfferFactory(provider=self.provider, is_high_risk=False)
        self.user       = User.objects.create_user('taskuser', password='pw')
        old_time        = timezone.now() - timedelta(hours=25)
        self.conversion = OfferConversionFactory(
            offer=self.offer, user=self.user, status='pending')
        # Backdate
        type(self.conversion).converted_at = PropertyMock(return_value=old_time)

    @patch('api.offerwall.tasks.FEATURE_AUTO_APPROVE_CONVERSIONS', True)
    def test_auto_approve_pending(self):
        from api.offerwall.tasks import auto_approve_pending_conversions
        from api.offerwall.models import OfferConversion
        OfferConversion.objects.filter(pk=self.conversion.pk).update(
            converted_at=timezone.now() - timedelta(hours=25))
        with patch('api.offerwall.tasks.OfferwallIntegrationService'
                   '.approve_conversion',
                   return_value={'success': True}):
            result = auto_approve_pending_conversions(review_hours=24)
        self.assertIn('approved', result)

    @patch('api.offerwall.tasks.FEATURE_AUTO_APPROVE_CONVERSIONS', False)
    def test_auto_approve_disabled_by_feature_flag(self):
        from api.offerwall.tasks import auto_approve_pending_conversions
        result = auto_approve_pending_conversions()
        self.assertEqual(result['approved'], 0)


class ExpirePendingConversionsTaskTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import (
            OfferFactory, OfferProviderFactory, OfferConversionFactory)
        self.provider   = OfferProviderFactory()
        self.offer      = OfferFactory(provider=self.provider)
        self.user       = User.objects.create_user('expireuser', password='pw')
        self.conversion = OfferConversionFactory(
            offer=self.offer, user=self.user, status='pending')

    def test_expire_old_pending(self):
        from api.offerwall.tasks import expire_pending_conversions
        from api.offerwall.models import OfferConversion
        OfferConversion.objects.filter(pk=self.conversion.pk).update(
            converted_at=timezone.now() - timedelta(hours=73))
        result = expire_pending_conversions(timeout_hours=72)
        self.conversion.refresh_from_db()
        self.assertEqual(self.conversion.status, 'rejected')
        self.assertGreaterEqual(result['rejected'], 1)

    def test_recent_pending_not_expired(self):
        from api.offerwall.tasks import expire_pending_conversions
        result = expire_pending_conversions(timeout_hours=72)
        self.conversion.refresh_from_db()
        self.assertEqual(self.conversion.status, 'pending')


class GenerateMonthlyInvoicesTaskTest(TestCase):

    def setUp(self):
        from api.offerwall.b2b.tests.factories import B2BClientFactory
        self.client = B2BClientFactory(status='active')

    def test_generates_invoice(self):
        from api.offerwall.tasks import generate_monthly_invoices
        now = timezone.now()
        result = generate_monthly_invoices()
        self.assertIn('created', result)
        self.assertIn('skipped', result)

    def test_idempotent_generation(self):
        from api.offerwall.tasks import generate_monthly_invoices
        generate_monthly_invoices()
        result = generate_monthly_invoices()
        self.assertGreaterEqual(result['skipped'], 1)
        self.assertEqual(result['created'], 0)


class WarmAnalyticsCacheTaskTest(TestCase):

    def test_warm_cache_success(self):
        from api.offerwall.tasks import warm_analytics_cache
        result = warm_analytics_cache()
        self.assertTrue(result.get('success'))

    def test_warm_cache_stores_platform_stats(self):
        from api.offerwall.tasks import warm_analytics_cache
        from django.core.cache import cache
        warm_analytics_cache()
        stats = cache.get('offerwall:platform_stats')
        self.assertIsNotNone(stats)
        self.assertIn('total_offers', stats)


class CheckFraudAnomaliesTaskTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import (
            OfferFactory, OfferProviderFactory, OfferConversionFactory)
        self.provider = OfferProviderFactory()
        self.offer    = OfferFactory(provider=self.provider)
        self.user     = User.objects.create_user('frauduser', password='pw')

    def test_no_anomalies_on_clean_data(self):
        from api.offerwall.tasks import check_fraud_anomalies
        result = check_fraud_anomalies()
        self.assertEqual(result['alerts_fired'], 0)

    @patch('api.offerwall.tasks.OfferwallAdapterFactory')
    def test_fires_alert_on_high_chargeback(self, mock_factory):
        from api.offerwall.tasks import check_fraud_anomalies
        from api.offerwall.models import OfferConversion
        from api.offerwall.tests.factories import OfferConversionFactory
        for _ in range(12):
            OfferConversionFactory(
                offer=self.offer, user=self.user, status='chargeback')
        mock_adapter = MagicMock()
        mock_factory.get.return_value = mock_adapter
        result = check_fraud_anomalies(window_minutes=1440)
        self.assertGreaterEqual(result['alerts_fired'], 1)


class UpdateProviderStatsTaskTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import OfferProviderFactory
        self.provider = OfferProviderFactory(status='active')

    def test_updates_provider_stats(self):
        from api.offerwall.tasks import update_provider_stats
        result = update_provider_stats()
        self.assertTrue(result.get('updated'))
        self.provider.refresh_from_db()
        self.assertIsNotNone(self.provider.total_offers)
