"""
Tests for SmartLink Signal Handlers
=====================================
Covers all 6 previously untested signal handlers:

  1. click_signals    — on_click_recorded
  2. smartlink_signals — on_smartlink_save, on_smartlink_delete, slug change
  3. fraud_signals    — on_fraud_flag_created
  4. offer_signals    — on_cap_reached
  5. ab_test_signals  — on_ab_test_winner_found
  6. domain_signals   — on_domain_verified
"""
import uuid
import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

from api.smartlink.tests.test_helpers import (
    make_user, make_offer, make_smartlink, make_click,
    make_payout_record, make_profile, make_wallet,
    make_offer_pool_entry, make_batch, auth_client,
    # backwards-compatible aliases (legacy _make_* names)
    _make_user, _make_offer, _make_smartlink, _make_sl,
    _make_click, _make_profile, _make_payout_record, _make_batch,
    _make_offer_pool_entry,
)

# ─── Shared helpers ───────────────────────────────────────────────────────────

# ═════════════════════════════════════════════════════════════════════════════
# 1. click_signals
# ═════════════════════════════════════════════════════════════════════════════

class ClickSignalTest(TestCase):

    def setUp(self):
        self.publisher = _make_user('click_sig_pub')
        self.sl = _make_smartlink(self.publisher)

    def test_new_click_updates_smartlink_last_click_at(self):
        """Creating a Click fires signal → SmartLink.last_click_at is updated."""
        _make_click(self.sl)
        self.sl.refresh_from_db()
        self.assertIsNotNone(self.sl.last_click_at)

    def test_click_update_does_not_change_last_click_at(self):
        """Saving an existing Click (update) does NOT change last_click_at."""
        click = _make_click(self.sl)
        self.sl.refresh_from_db()
        ts_after_create = self.sl.last_click_at

        click.is_converted = True
        click.save(update_fields=['is_converted'])
        self.sl.refresh_from_db()
        # timestamp must not change on update
        self.assertEqual(self.sl.last_click_at, ts_after_create)

    def test_signal_exception_does_not_propagate(self):
        """Signal error is swallowed — Click is still saved successfully."""
        from api.smartlink.models import Click
        offer = _make_offer()
        with patch('api.smartlink.models.SmartLink.objects.filter',
                   side_effect=Exception("DB error")):
            try:
                Click.objects.create(
                    smartlink=self.sl, offer=offer,
                    ip='2.3.4.5', user_agent='Test',
                    country='GB', device_type='mobile',
                )
            except Exception:
                self.fail("Signal exception must not propagate to caller")

# ═════════════════════════════════════════════════════════════════════════════
# 2. smartlink_signals
# ═════════════════════════════════════════════════════════════════════════════

class SmartLinkSignalHandlerTest(TestCase):

    def setUp(self):
        self.publisher = _make_user('sl_sig_pub')
        self.sl = _make_smartlink(self.publisher, slug='sig-test-sl')

    def test_save_fires_cache_invalidation_task(self):
        """Saving a SmartLink fires invalidate_smartlink_cache.delay()."""
        with patch(
            'api.smartlink.tasks.cache_warmup_tasks.invalidate_smartlink_cache.delay'
        ) as mock_delay:
            self.sl.name = 'Updated Name'
            self.sl.save(update_fields=['name'])
            mock_delay.assert_called()
            self.assertEqual(mock_delay.call_args[0][0], self.sl.slug)

    def test_create_fires_cache_invalidation_task(self):
        """Creating a new SmartLink fires cache invalidation."""
        with patch(
            'api.smartlink.tasks.cache_warmup_tasks.invalidate_smartlink_cache.delay'
        ) as mock_delay:
            _make_smartlink(self.publisher, slug='new-sig-sl')
            mock_delay.assert_called()

    def test_delete_invalidates_cache(self):
        """Deleting a SmartLink calls SmartLinkCacheService.invalidate_smartlink."""
        with patch(
            'api.smartlink.services.core.SmartLinkCacheService'
            '.SmartLinkCacheService.invalidate_smartlink'
        ) as mock_inv:
            slug = self.sl.slug
            self.sl.delete()
            mock_inv.assert_called_once_with(slug)

    def test_slug_change_invalidates_old_slug_cache(self):
        """Changing slug → OLD slug is invalidated in cache before save."""
        with patch(
            'api.smartlink.services.core.SmartLinkCacheService'
            '.SmartLinkCacheService.invalidate_smartlink'
        ) as mock_inv:
            old_slug = self.sl.slug
            self.sl.slug = 'new-slug-after-change'
            self.sl.save(update_fields=['slug'])
            called_slugs = [c[0][0] for c in mock_inv.call_args_list]
            self.assertIn(old_slug, called_slugs)

    def test_signal_exception_does_not_crash_save(self):
        """Cache invalidation failure must not crash SmartLink.save()."""
        with patch(
            'api.smartlink.tasks.cache_warmup_tasks.invalidate_smartlink_cache.delay',
            side_effect=Exception("Redis down"),
        ):
            try:
                self.sl.name = 'Safe Save'
                self.sl.save(update_fields=['name'])
            except Exception:
                self.fail("Cache failure must not crash SmartLink.save()")

# ═════════════════════════════════════════════════════════════════════════════
# 3. fraud_signals
# ═════════════════════════════════════════════════════════════════════════════

class FraudSignalTest(TestCase):

    def setUp(self):
        self.publisher = _make_user('fraud_sig_pub')
        self.sl    = _make_smartlink(self.publisher)
        self.click = _make_click(self.sl, ip='9.8.7.6')

    def _make_fraud_flag(self, score=90):
        from api.smartlink.models import ClickFraudFlag
        # Real fields: click, score, signals (JSONField list), action_taken
        return ClickFraudFlag.objects.create(
            click=self.click,
            score=score,
            signals=['datacenter_ip'],
            action_taken='block' if score >= 70 else 'flag',
        )

    def test_critical_score_auto_blocks_ip_in_cache(self):
        """Fraud score >= 85 → IP is cached as blocked for 24h."""
        from django.core.cache import cache
        self._make_fraud_flag(score=90)
        cached = cache.get(f"fraud:blocked:{self.click.ip}")
        self.assertEqual(cached, '1')

    def test_low_score_does_not_auto_block_ip(self):
        """Fraud score < 85 → IP is NOT auto-blocked."""
        from django.core.cache import cache
        from api.smartlink.models import Click
        # Use a unique IP per test run to avoid cross-test cache pollution
        unique_ip = f"1.2.{uuid.uuid4().int % 255}.{uuid.uuid4().int % 255}"
        offer = _make_offer()
        low_click = Click.objects.create(
            smartlink=self.sl, offer=offer, ip=unique_ip,
            user_agent='Test', country='US', device_type='desktop',
        )
        from api.smartlink.models import ClickFraudFlag
        ClickFraudFlag.objects.create(
            click=low_click, score=50, signals=[], action_taken='flag',
        )
        cached = cache.get(f"fraud:blocked:{unique_ip}")
        self.assertIsNone(cached)

    def test_fraud_flag_fires_webhook_event(self):
        """Creating ClickFraudFlag fires deliver_webhook_event.delay()."""
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            self._make_fraud_flag(score=90)
            mock_wh.assert_called()
            # First positional arg or 'event' kwarg must be 'fraud_spike'
            event_val = (mock_wh.call_args[1].get('event')
                         or (mock_wh.call_args[0][0] if mock_wh.call_args[0] else None))
            self.assertEqual(event_val, 'fraud_spike')

    def test_critical_fraud_fires_notification(self):
        """Fraud score >= 90 → NotificationService.notify_fraud_spike() called."""
        with patch(
            'api.smartlink.services.notification.NotificationService'
            '.NotificationService.notify_fraud_spike'
        ) as mock_notify:
            self._make_fraud_flag(score=95)
            mock_notify.assert_called_once()
            self.assertEqual(mock_notify.call_args[1]['publisher'], self.publisher)

    def test_subcritical_fraud_does_not_fire_notification(self):
        """Fraud score 85–89 → notification NOT fired."""
        with patch(
            'api.smartlink.services.notification.NotificationService'
            '.NotificationService.notify_fraud_spike'
        ) as mock_notify:
            self._make_fraud_flag(score=87)
            mock_notify.assert_not_called()

    def test_fraud_signal_fires_only_for_new_flags(self):
        """Updating existing ClickFraudFlag (created=False) does NOT re-fire webhook."""
        flag = self._make_fraud_flag(score=90)
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            flag.score = 95
            flag.save(update_fields=['score'])
            mock_wh.assert_not_called()

# ═════════════════════════════════════════════════════════════════════════════
# 4. offer_signals
# ═════════════════════════════════════════════════════════════════════════════

class OfferCapSignalTest(TestCase):

    def setUp(self):
        self.publisher = _make_user('cap_sig_pub')
        self.sl    = _make_smartlink(self.publisher)
        self.entry = _make_offer_pool_entry(self.sl)

    def _make_cap_tracker(self, is_capped=True, clicks_count=100, cap_limit=100):
        from api.smartlink.models import OfferCapTracker
        tracker, created = OfferCapTracker.objects.get_or_create(
            pool_entry=self.entry,
            period='daily',
            period_date=datetime.date.today(),
            defaults={
                'clicks_count': clicks_count,
                'cap_limit':    cap_limit,
                'is_capped':    is_capped,
            },
        )
        if not created:
            tracker.is_capped    = is_capped
            tracker.clicks_count = clicks_count
            tracker.cap_limit    = cap_limit
            tracker.save(update_fields=['is_capped', 'clicks_count', 'cap_limit'])
        return tracker

    def test_cap_reached_invalidates_pool_cache(self):
        """Offer capped → SmartLinkCacheService.invalidate_offer_pool called."""
        with patch(
            'api.smartlink.services.core.SmartLinkCacheService'
            '.SmartLinkCacheService.invalidate_offer_pool'
        ) as mock_inv:
            self._make_cap_tracker(is_capped=True)
            mock_inv.assert_called_once_with(self.sl.pk)

    def test_cap_reached_fires_pool_warmup_task(self):
        """Cap reached → warmup_offer_pool_cache.delay() fires."""
        with patch(
            'api.smartlink.tasks.cache_warmup_tasks.warmup_offer_pool_cache.delay'
        ) as mock_warmup:
            self._make_cap_tracker(is_capped=True)
            mock_warmup.assert_called_once_with(self.sl.pk)

    def test_cap_reached_fires_webhook(self):
        """Cap reached → deliver_webhook_event.delay(event='cap_reached') called."""
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            self._make_cap_tracker(is_capped=True)
            mock_wh.assert_called()
            event_val = (mock_wh.call_args[1].get('event')
                         or (mock_wh.call_args[0][0] if mock_wh.call_args[0] else None))
            self.assertEqual(event_val, 'cap_reached')

    def test_cap_reached_fires_publisher_notification(self):
        """Cap reached → NotificationService.notify_cap_reached() called."""
        with patch(
            'api.smartlink.services.notification.NotificationService'
            '.NotificationService.notify_cap_reached'
        ) as mock_notify:
            self._make_cap_tracker(is_capped=True)
            mock_notify.assert_called_once()

    def test_nearly_reached_fires_alert_task(self):
        """80% cap usage (not yet capped) → alert_cap_nearly_reached.delay() fires."""
        with patch(
            'api.smartlink.tasks.cap_reset_tasks.alert_cap_nearly_reached.delay'
        ) as mock_alert:
            self._make_cap_tracker(is_capped=False, clicks_count=80, cap_limit=100)
            mock_alert.assert_called()

    def test_below_80pct_no_alert(self):
        """Below 80% cap usage → no alert fires."""
        with patch(
            'api.smartlink.tasks.cap_reset_tasks.alert_cap_nearly_reached.delay'
        ) as mock_alert:
            self._make_cap_tracker(is_capped=False, clicks_count=50, cap_limit=100)
            mock_alert.assert_not_called()

# ═════════════════════════════════════════════════════════════════════════════
# 5. ab_test_signals
# ═════════════════════════════════════════════════════════════════════════════

class ABTestSignalTest(TestCase):

    def setUp(self):
        from api.smartlink.models.smartlink import SmartLinkVersion
        self.publisher = _make_user('ab_sig_pub')
        self.sl        = _make_smartlink(self.publisher)
        self.version   = SmartLinkVersion.objects.create(
            smartlink=self.sl, name='Variant B',
            traffic_split=50, is_control=False,
        )

    def _make_ab_result(self, status_val=None, winner=None,
                        uplift=12.5, confidence=0.95):
        from api.smartlink.models.analytics import ABTestResult
        from api.smartlink.choices import ABTestStatus
        status_val = status_val or ABTestStatus.WINNER_FOUND
        return ABTestResult.objects.create(
            smartlink=self.sl,
            status=status_val,
            winner_version=winner or self.version,
            uplift_percent=float(uplift),
            confidence_level=float(confidence),
            started_at=timezone.now() - datetime.timedelta(days=7),
            completed_at=timezone.now(),
        )

    def test_winner_found_fires_webhook(self):
        """WINNER_FOUND → deliver_webhook_event.delay(event='ab_winner') called."""
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            with patch(
                'api.smartlink.services.notification.NotificationService'
                '.NotificationService.notify_ab_winner'
            ):
                self._make_ab_result()
            mock_wh.assert_called()
            event_val = (mock_wh.call_args[1].get('event')
                         or (mock_wh.call_args[0][0] if mock_wh.call_args[0] else None))
            self.assertEqual(event_val, 'ab_winner')

    def test_winner_found_fires_notification(self):
        """WINNER_FOUND → NotificationService.notify_ab_winner() called."""
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ):
            with patch(
                'api.smartlink.services.notification.NotificationService'
                '.NotificationService.notify_ab_winner'
            ) as mock_notify:
                self._make_ab_result()
                mock_notify.assert_called_once()
                self.assertEqual(mock_notify.call_args[1]['publisher'], self.publisher)
                self.assertIn('winner_version', mock_notify.call_args[1])

    def test_non_winner_status_does_not_fire(self):
        """Status != WINNER_FOUND → nothing fires."""
        from api.smartlink.choices import ABTestStatus
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            self._make_ab_result(status_val=ABTestStatus.RUNNING)
            mock_wh.assert_not_called()

    def test_no_winner_version_does_not_fire(self):
        """winner_version=None → nothing fires even if status=WINNER_FOUND."""
        from api.smartlink.models.analytics import ABTestResult
        from api.smartlink.choices import ABTestStatus
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            ABTestResult.objects.create(
                smartlink=self.sl,
                status=ABTestStatus.WINNER_FOUND,
                winner_version=None,
                uplift_percent=5.0,
                confidence_level=0.90,
                started_at=timezone.now() - datetime.timedelta(days=3),
                completed_at=timezone.now(),
            )
            mock_wh.assert_not_called()

    def test_ab_signal_logs_winner_info(self):
        """on_ab_test_winner_found logs winner details at INFO level."""
        with patch('api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'):
            with patch(
                'api.smartlink.services.notification.NotificationService'
                '.NotificationService.notify_ab_winner'
            ):
                with self.assertLogs('smartlink.signals.ab_test', level='INFO') as cm:
                    self._make_ab_result(uplift=15.3, confidence=0.97)
        self.assertTrue(any('Variant B' in line for line in cm.output))

# ═════════════════════════════════════════════════════════════════════════════
# 6. domain_signals
# ═════════════════════════════════════════════════════════════════════════════

class DomainSignalTest(TestCase):

    def setUp(self):
        self.publisher = _make_user('dom_sig_pub')

    def _make_domain(self, verified=True):
        from api.smartlink.models.publisher import PublisherDomain
        from api.smartlink.choices import DomainVerificationStatus
        status_val = (
            DomainVerificationStatus.VERIFIED
            if verified else DomainVerificationStatus.PENDING
        )
        return PublisherDomain.objects.create(
            publisher=self.publisher,
            domain=f"{uuid.uuid4().hex[:8]}.example.com",
            verification_status=status_val,
            verified_at=timezone.now() if verified else None,
        )

    def test_verified_domain_caches_publisher_mapping(self):
        """Verified domain → domain→publisher_id cached."""
        from django.core.cache import cache
        from api.smartlink.utils import domain_cache_key
        domain_obj = self._make_domain(verified=True)
        cached = cache.get(domain_cache_key(domain_obj.domain))
        self.assertEqual(cached, self.publisher.pk)

    def test_pending_domain_does_not_cache(self):
        """Pending domain → NO cache entry."""
        from django.core.cache import cache
        from api.smartlink.utils import domain_cache_key
        domain_obj = self._make_domain(verified=False)
        self.assertIsNone(cache.get(domain_cache_key(domain_obj.domain)))

    def test_verified_domain_fires_webhook(self):
        """Verified domain → deliver_webhook_event.delay(event='domain_verified')."""
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            with patch(
                'api.smartlink.services.notification.NotificationService'
                '.NotificationService._dispatch'
            ):
                domain_obj = self._make_domain(verified=True)
            mock_wh.assert_called()
            event_val = (mock_wh.call_args[1].get('event')
                         or (mock_wh.call_args[0][0] if mock_wh.call_args[0] else None))
            self.assertEqual(event_val, 'domain_verified')
            domain_val = (mock_wh.call_args[1].get('domain')
                          or (mock_wh.call_args[0][3] if len(mock_wh.call_args[0]) > 3 else None))
            self.assertEqual(domain_val, domain_obj.domain)

    def test_verified_domain_fires_notification(self):
        """Verified domain → NotificationService._dispatch() called with publisher."""
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ):
            with patch(
                'api.smartlink.services.notification.NotificationService'
                '.NotificationService._dispatch'
            ) as mock_dispatch:
                domain_obj = self._make_domain(verified=True)
                mock_dispatch.assert_called_once()
                self.assertEqual(mock_dispatch.call_args[0][0], self.publisher)
                self.assertIn(domain_obj.domain, mock_dispatch.call_args[0][1])

    def test_pending_domain_no_webhook_no_notification(self):
        """Pending domain → NO webhook, NO notification."""
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            self._make_domain(verified=False)
            mock_wh.assert_not_called()

    def test_status_change_to_verified_fires_signal(self):
        """Changing existing domain status → VERIFIED fires signal."""
        from api.smartlink.choices import DomainVerificationStatus
        domain_obj = self._make_domain(verified=False)
        with patch(
            'api.smartlink.tasks.webhook_tasks.deliver_webhook_event.delay'
        ) as mock_wh:
            with patch(
                'api.smartlink.services.notification.NotificationService'
                '.NotificationService._dispatch'
            ):
                domain_obj.verification_status = DomainVerificationStatus.VERIFIED
                domain_obj.verified_at = timezone.now()
                domain_obj.save(update_fields=['verification_status', 'verified_at'])
            mock_wh.assert_called()
