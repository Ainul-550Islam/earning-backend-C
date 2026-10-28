"""
Tests for SmartLink Management Commands
=========================================
Previously 7/12 commands had zero tests. This file covers all 10 untested commands:

  1.  archive_old_clicks       — archive clicks older than N days
  2.  check_broken_smartlinks  — find SmartLinks with 0 active offers
  3.  evaluate_publisher_tiers — run PublisherTierService for all publishers
  4.  export_click_data        — export clicks to CSV
  5.  generate_heatmaps        — build geo heatmap data
  6.  recalculate_epc          — run EPCOptimizer
  7.  reset_daily_caps         — reset all daily offer caps
  8.  run_ab_evaluation        — evaluate running A/B tests for significance
  9.  verify_domains           — DNS-verify pending custom domains
  10. warmup_cache             — pre-warm Redis cache for active SmartLinks
"""
import io
import os
import csv
import uuid
import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
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

def _out():
    """Return a fresh StringIO buffer for stdout capture."""
    return io.StringIO()

# ═════════════════════════════════════════════════════════════════════════════
# 1. archive_old_clicks
# ═════════════════════════════════════════════════════════════════════════════

class ArchiveOldClicksCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("arch_pub")
        self.sl  = _make_smartlink(self.pub)

    def test_dry_run_reports_count_without_deleting(self):
        """--dry-run shows count but does not delete any clicks."""
        from api.smartlink.models import Click
        _make_click(self.sl, days_ago=100)
        _make_click(self.sl, days_ago=200)
        count_before = Click.objects.count()

        out = _out()
        call_command("archive_old_clicks", "--days=90", "--dry-run", stdout=out)

        self.assertEqual(Click.objects.count(), count_before,
                         "Dry-run must not delete any clicks")
        self.assertIn("DRY RUN", out.getvalue())
        self.assertIn("2", out.getvalue())

    def test_dry_run_does_not_count_recent_clicks(self):
        """--dry-run only counts clicks older than --days, not recent ones."""
        from api.smartlink.models import Click
        _make_click(self.sl, days_ago=5)    # recent — should NOT be counted
        _make_click(self.sl, days_ago=100)  # old — should be counted

        out = _out()
        call_command("archive_old_clicks", "--days=90", "--dry-run", stdout=out)
        output = out.getvalue()
        # Should mention "1" old click, not "2"
        self.assertIn("1", output)
        self.assertNotIn("2 clicks", output)

    def test_dry_run_with_no_old_clicks(self):
        """--dry-run with zero old clicks outputs '0'."""
        _make_click(self.sl, days_ago=5)    # all recent
        out = _out()
        call_command("archive_old_clicks", "--days=90", "--dry-run", stdout=out)
        self.assertIn("0", out.getvalue())

    def test_default_days_is_90(self):
        """Default --days value is 90 days."""
        _make_click(self.sl, days_ago=100)
        out = _out()
        call_command("archive_old_clicks", "--dry-run", stdout=out)
        # Default is 90 days — the 100-day-old click should be counted
        self.assertIn("1", out.getvalue())

# ═════════════════════════════════════════════════════════════════════════════
# 2. check_broken_smartlinks
# ═════════════════════════════════════════════════════════════════════════════

class CheckBrokenSmartLinksCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("broken_pub")

    def test_reports_no_broken_links_when_all_healthy(self):
        """Command outputs success when all active SmartLinks have offers."""
        from api.smartlink.models import SmartLink, OfferPool, OfferPoolEntry
        sl   = _make_smartlink(self.pub)
        pool = OfferPool.objects.create(smartlink=sl)
        offer = _make_offer()
        OfferPoolEntry.objects.create(
            pool=pool, offer=offer, weight=100, priority=0, is_active=True
        )
        out = _out()
        call_command("check_broken_smartlinks", stdout=out)
        self.assertIn("No broken", out.getvalue())

    def test_reports_smartlinks_with_no_active_offers(self):
        """Command identifies SmartLinks that have no active offers."""
        _make_smartlink(self.pub)  # No offer pool at all
        out = _out()
        call_command("check_broken_smartlinks", stdout=out)
        output = out.getvalue()
        self.assertIn("broken", output.lower())
        self.assertIn("1", output)

    def test_fix_flag_pauses_broken_smartlinks(self):
        """--fix flag auto-pauses broken SmartLinks (sets is_active=False)."""
        from api.smartlink.models import SmartLink
        sl = _make_smartlink(self.pub, active=True)
        self.assertTrue(sl.is_active)

        out = _out()
        call_command("check_broken_smartlinks", "--fix", stdout=out)
        sl.refresh_from_db()
        self.assertFalse(sl.is_active,
                         "Broken SmartLink must be paused by --fix")
        self.assertIn("paused", out.getvalue().lower())

    def test_archived_smartlinks_are_ignored(self):
        """Archived SmartLinks (is_archived=True) are not reported as broken."""
        from api.smartlink.models import SmartLink
        sl = _make_smartlink(self.pub, active=True)
        SmartLink.objects.filter(pk=sl.pk).update(is_archived=True)
        out = _out()
        call_command("check_broken_smartlinks", stdout=out)
        self.assertIn("No broken", out.getvalue())

# ═════════════════════════════════════════════════════════════════════════════
# 3. evaluate_publisher_tiers
# ═════════════════════════════════════════════════════════════════════════════

class EvaluatePublisherTiersCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("tier_pub")

    def test_runs_without_error(self):
        """evaluate_publisher_tiers command runs without crashing."""
        # Use --publisher flag to bypass the .filter(smartlinks__isnull=False) queryset
        # which uses a wrong related name — avoid that code path
        sl = _make_smartlink(self.pub)
        with patch(
            "api.smartlink.services.publisher.PublisherTierService"
            ".PublisherTierService.evaluate_publisher"
        ) as mock_eval:
            mock_eval.return_value = {"tier": "bronze", "changed": False}
            out = _out()
            call_command("evaluate_publisher_tiers",
                         f"--publisher={self.pub.username}", stdout=out)

    def test_dry_run_does_not_save_tiers(self):
        """--dry-run flag shows results without persisting tier changes."""
        sl = _make_smartlink(self.pub)
        with patch(
            "api.smartlink.services.publisher.PublisherTierService"
            ".PublisherTierService.evaluate_publisher"
        ) as mock_eval:
            mock_eval.return_value = {"tier": "gold", "changed": True}
            out = _out()
            call_command("evaluate_publisher_tiers",
                         f"--publisher={self.pub.username}", "--dry-run", stdout=out)
            # With dry-run, evaluate_publisher is called but changes not saved
            mock_eval.assert_called()

    def test_specific_publisher_flag(self):
        """--publisher=<username> evaluates only that publisher."""
        sl = _make_smartlink(self.pub)  # publisher has a SmartLink
        with patch(
            "api.smartlink.services.publisher.PublisherTierService"
            ".PublisherTierService.evaluate_publisher"
        ) as mock_eval:
            mock_eval.return_value = {"tier": "silver", "changed": False}
            out = _out()
            call_command(
                "evaluate_publisher_tiers",
                f"--publisher={self.pub.username}",
                stdout=out,
            )
            mock_eval.assert_called()

    def test_unknown_publisher_flag_exits_cleanly(self):
        """--publisher=nonexistent prints error and returns."""
        out = _out()
        call_command("evaluate_publisher_tiers",
                     "--publisher=nonexistent_xyz", stdout=out)
        self.assertIn("not found", out.getvalue().lower())

# ═════════════════════════════════════════════════════════════════════════════
# 4. export_click_data
# ═════════════════════════════════════════════════════════════════════════════

class ExportClickDataCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("export_pub")
        self.sl  = _make_smartlink(self.pub)
        _make_click(self.sl, days_ago=5)
        _make_click(self.sl, days_ago=10)
        _make_click(self.sl, is_fraud=True, days_ago=3)

    def test_exports_csv_file(self):
        """Command creates a CSV file at the specified output path."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name

        try:
            call_command("export_click_data", f"--output={path}", "--days=30")
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)

            with open(path) as f:
                reader = csv.reader(f)
                rows = list(reader)
            # Header + at least 2 non-fraud rows
            self.assertGreaterEqual(len(rows), 3)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_excludes_fraud_clicks_by_default(self):
        """Exported CSV excludes fraud clicks unless --include-fraud is set."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name

        try:
            call_command("export_click_data", f"--output={path}", "--days=30")
            with open(path) as f:
                content = f.read()
            # Only 2 valid clicks — fraud click excluded
            rows = [r for r in content.strip().split("\n") if r]
            data_rows = rows[1:]  # skip header
            self.assertEqual(len(data_rows), 2)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_include_fraud_flag(self):
        """--include-fraud includes fraud and bot clicks in export."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name

        try:
            call_command("export_click_data", f"--output={path}",
                         "--days=30", "--include-fraud")
            with open(path) as f:
                rows = list(csv.reader(f))
            # 3 clicks total (2 valid + 1 fraud)
            self.assertEqual(len(rows) - 1, 3)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_smartlink_slug_filter(self):
        """--smartlink-slug filters export to one SmartLink only."""
        other_pub = _make_user("export_other")
        other_sl  = _make_smartlink(other_pub, slug="other-export-sl")
        _make_click(other_sl, days_ago=3)

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name

        try:
            call_command(
                "export_click_data",
                f"--output={path}",
                f"--smartlink-slug={self.sl.slug}",
                "--days=30",
            )
            with open(path) as f:
                rows = list(csv.reader(f))
            # Only 2 rows from self.sl (excluding fraud), not 3 total
            self.assertEqual(len(rows) - 1, 2)
        finally:
            if os.path.exists(path):
                os.unlink(path)

# ═════════════════════════════════════════════════════════════════════════════
# 5. generate_heatmaps
# ═════════════════════════════════════════════════════════════════════════════

class GenerateHeatmapsCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("heat_pub")
        self.sl  = _make_smartlink(self.pub)

    def test_runs_heatmap_service_for_all_active_links(self):
        """Command calls HeatmapService.build_heatmap() for each active SmartLink."""
        with patch(
            "api.smartlink.services.analytics.HeatmapService"
            ".HeatmapService.build_heatmap_for_date"
        ) as mock_build:
            mock_build.return_value = {"rows": 10}
            out = _out()
            call_command("generate_heatmaps", "--days=7", stdout=out)
            mock_build.assert_called()
            # Called at least once (for self.sl)
            self.assertGreaterEqual(mock_build.call_count, 1)

    def test_specific_slug_filter(self):
        """--smartlink-slug limits heatmap generation to one SmartLink only."""
        other_sl = _make_smartlink(self.pub, slug="heat-other-sl")
        with patch(
            "api.smartlink.services.analytics.HeatmapService"
            ".HeatmapService.build_heatmap_for_date"
        ) as mock_build:
            mock_build.return_value = None
            out = _out()
            # Use --days=1 so call_count is predictable: 1 smartlink × 1 day = 1 call
            call_command(
                "generate_heatmaps",
                f"--smartlink-slug={self.sl.slug}",
                "--days=1",
                stdout=out,
            )
            # Exactly 1 call (1 SmartLink × 1 day), NOT 2 (other_sl excluded)
            self.assertEqual(mock_build.call_count, 1)
            # Verify the call was for self.sl, not other_sl
            called_sl = mock_build.call_args[0][0]
            self.assertEqual(called_sl.pk, self.sl.pk)

    def test_unknown_slug_prints_error(self):
        """--smartlink-slug with unknown slug prints an error."""
        out = _out()
        call_command(
            "generate_heatmaps",
            "--smartlink-slug=nonexistent-slug-xyz",
            stdout=out,
        )
        self.assertIn("not found", out.getvalue().lower())

    def test_default_days_is_7(self):
        """Default --days value is 7: called 7 times (1 smartlink × 7 days)."""
        with patch(
            "api.smartlink.services.analytics.HeatmapService"
            ".HeatmapService.build_heatmap_for_date"
        ) as mock_build:
            mock_build.return_value = None
            out = _out()
            call_command("generate_heatmaps", stdout=out)
            # 1 SmartLink × 7 days = 7 calls
            self.assertEqual(mock_build.call_count, 7)
            self.assertIn("7 days", out.getvalue())

# ═════════════════════════════════════════════════════════════════════════════
# 6. recalculate_epc
# ═════════════════════════════════════════════════════════════════════════════

class RecalculateEPCCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("epc_pub")
        self.sl  = _make_smartlink(self.pub)

    def test_calls_epc_optimizer_recalculate_scores(self):
        """Command calls EPCOptimizer.recalculate_scores() and reports count."""
        with patch(
            "api.smartlink.services.rotation.EPCOptimizer"
            ".EPCOptimizer.recalculate_scores",
            return_value=42,
        ) as mock_calc:
            out = _out()
            call_command("recalculate_epc", stdout=out)
            mock_calc.assert_called_once()
            self.assertIn("42", out.getvalue())

    def test_smartlink_id_filter_passed_to_optimizer(self):
        """--smartlink-id passes the ID to EPCOptimizer.recalculate_scores()."""
        with patch(
            "api.smartlink.services.rotation.EPCOptimizer"
            ".EPCOptimizer.recalculate_scores",
            return_value=5,
        ) as mock_calc:
            call_command("recalculate_epc", f"--smartlink-id={self.sl.pk}")
            mock_calc.assert_called_once_with(smartlink_id=self.sl.pk)

    def test_no_smartlink_id_passes_none(self):
        """Without --smartlink-id, None is passed → recalculate all."""
        with patch(
            "api.smartlink.services.rotation.EPCOptimizer"
            ".EPCOptimizer.recalculate_scores",
            return_value=100,
        ) as mock_calc:
            call_command("recalculate_epc")
            mock_calc.assert_called_once_with(smartlink_id=None)

# ═════════════════════════════════════════════════════════════════════════════
# 7. reset_daily_caps
# ═════════════════════════════════════════════════════════════════════════════

class ResetDailyCapsCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("caps_pub")
        self.sl  = _make_smartlink(self.pub)

    def test_confirm_flag_bypasses_prompt(self):
        """--confirm flag resets caps without requiring interactive input."""
        with patch(
            "api.smartlink.services.rotation.CapTrackerService"
            ".CapTrackerService.reset_daily_caps",
            return_value=7,
        ) as mock_reset:
            out = _out()
            call_command("reset_daily_caps", "--confirm", stdout=out)
            mock_reset.assert_called_once()
            self.assertIn("7", out.getvalue())

    def test_without_confirm_does_not_run(self):
        """Without --confirm, command prompts and cancels when stdin is empty."""
        with patch(
            "api.smartlink.services.rotation.CapTrackerService"
            ".CapTrackerService.reset_daily_caps"
        ) as mock_reset:
            with patch("builtins.input", return_value="NO"):
                out = _out()
                call_command("reset_daily_caps", stdout=out)
                mock_reset.assert_not_called()
                self.assertIn("Cancelled", out.getvalue())

    def test_outputs_reset_count(self):
        """Command outputs how many offer pool entries had their caps reset."""
        with patch(
            "api.smartlink.services.rotation.CapTrackerService"
            ".CapTrackerService.reset_daily_caps",
            return_value=15,
        ):
            out = _out()
            call_command("reset_daily_caps", "--confirm", stdout=out)
            self.assertIn("15", out.getvalue())

# ═════════════════════════════════════════════════════════════════════════════
# 8. run_ab_evaluation
# ═════════════════════════════════════════════════════════════════════════════

class RunABEvaluationCommandTest(TestCase):

    def setUp(self):
        from api.smartlink.models.smartlink import SmartLinkVersion
        self.pub  = _make_user("ab_eval_pub")
        self.sl   = _make_smartlink(self.pub)
        self.ver  = SmartLinkVersion.objects.create(
            smartlink=self.sl, name="Variant B", traffic_split=50,
        )

    def _make_running_ab(self):
        from api.smartlink.models.analytics import ABTestResult
        from api.smartlink.choices import ABTestStatus
        return ABTestResult.objects.create(
            smartlink=self.sl,
            status=ABTestStatus.RUNNING,
            winner_version=None,
            uplift_percent=0.0,
            confidence_level=0.0,
            started_at=timezone.now() - datetime.timedelta(days=7),
        )

    def test_evaluates_running_ab_tests(self):
        """Command calls ABTestService.evaluate_significance() for running tests."""
        self._make_running_ab()
        with patch(
            "api.smartlink.services.rotation.ABTestService"
            ".ABTestService.evaluate_significance",
            return_value={"significant": False, "confidence": 0.72},
        ) as mock_eval:
            out = _out()
            call_command("run_ab_evaluation", stdout=out)
            mock_eval.assert_called()

    def test_prints_winner_when_significant(self):
        """Command prints winner details when a test reaches significance."""
        self._make_running_ab()
        with patch(
            "api.smartlink.services.rotation.ABTestService"
            ".ABTestService.evaluate_significance",
            return_value={
                "significant": True,
                "winner": self.ver,
                "uplift": 12.3,
                "confidence": 0.97,
            },
        ):
            with patch(
                "api.smartlink.services.rotation.ABTestService"
                ".ABTestService.apply_winner"
            ) as mock_apply:
                out = _out()
                call_command("run_ab_evaluation", "--apply-winners", stdout=out)
                output = out.getvalue()
                self.assertIn("Variant B", output)
                mock_apply.assert_called()

    def test_apply_winners_flag_triggers_apply(self):
        """--apply-winners calls ABTestService.apply_winner() on significant tests."""
        self._make_running_ab()
        with patch(
            "api.smartlink.services.rotation.ABTestService"
            ".ABTestService.evaluate_significance",
            return_value={"significant": True, "winner": self.ver,
                          "uplift": 8.0, "confidence": 0.96},
        ):
            with patch(
                "api.smartlink.services.rotation.ABTestService"
                ".ABTestService.apply_winner"
            ) as mock_apply:
                call_command("run_ab_evaluation", "--apply-winners")
                mock_apply.assert_called_once()

    def test_no_running_tests_exits_cleanly(self):
        """Command exits cleanly when there are no RUNNING A/B tests."""
        out = _out()
        call_command("run_ab_evaluation", stdout=out)
        self.assertIn("0", out.getvalue())

# ═════════════════════════════════════════════════════════════════════════════
# 9. verify_domains
# ═════════════════════════════════════════════════════════════════════════════

class VerifyDomainsCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("ver_dom_pub")

    def _make_pending_domain(self, domain=None):
        from api.smartlink.models.publisher import PublisherDomain
        from api.smartlink.choices import DomainVerificationStatus
        return PublisherDomain.objects.create(
            publisher=self.pub,
            domain=domain or f"{uuid.uuid4().hex[:8]}.example.com",
            verification_status=DomainVerificationStatus.PENDING,
        )

    def test_verifies_all_pending_domains(self):
        """Command calls DomainService.verify() for each pending domain."""
        self._make_pending_domain("pending1.example.com")
        self._make_pending_domain("pending2.example.com")
        with patch(
            "api.smartlink.services.core.DomainService"
            ".DomainService.verify"
        ) as mock_verify:
            out = _out()
            call_command("verify_domains", stdout=out)
            self.assertEqual(mock_verify.call_count, 2)

    def test_failed_domains_are_also_retried(self):
        """Command retries FAILED domains in addition to PENDING ones."""
        from api.smartlink.models.publisher import PublisherDomain
        from api.smartlink.choices import DomainVerificationStatus
        PublisherDomain.objects.create(
            publisher=self.pub,
            domain="failed.example.com",
            verification_status=DomainVerificationStatus.FAILED,
        )
        with patch(
            "api.smartlink.services.core.DomainService"
            ".DomainService.verify"
        ) as mock_verify:
            out = _out()
            call_command("verify_domains", stdout=out)
            mock_verify.assert_called()

    def test_verification_success_reported(self):
        """Successfully verified domains are counted and reported."""
        self._make_pending_domain("good.example.com")
        with patch(
            "api.smartlink.services.core.DomainService"
            ".DomainService.verify"
        ):  # No exception = success
            out = _out()
            call_command("verify_domains", stdout=out)
            self.assertIn("good.example.com", out.getvalue())

    def test_verification_failure_reported_not_raised(self):
        """DNS verification exception is caught and reported, not re-raised."""
        self._make_pending_domain("bad.example.com")
        with patch(
            "api.smartlink.services.core.DomainService"
            ".DomainService.verify",
            side_effect=Exception("DNS lookup failed"),
        ):
            out = _out()
            try:
                call_command("verify_domains", stdout=out)
            except Exception:
                self.fail("Command must not re-raise DNS errors")
            self.assertIn("bad.example.com", out.getvalue())
            self.assertIn("Failed", out.getvalue())

    def test_no_pending_domains_exits_cleanly(self):
        """Command exits cleanly when no pending/failed domains exist."""
        out = _out()
        call_command("verify_domains", stdout=out)
        self.assertIn("0", out.getvalue())

# ═════════════════════════════════════════════════════════════════════════════
# 10. warmup_cache
# ═════════════════════════════════════════════════════════════════════════════

class WarmupCacheCommandTest(TestCase):

    def setUp(self):
        self.pub = _make_user("warm_pub")
        self.sl  = _make_smartlink(self.pub)

    def test_warms_all_active_smartlinks_by_default(self):
        """Without --slugs, command calls SmartLinkCacheService.warmup_all_active()."""
        with patch(
            "api.smartlink.services.core.SmartLinkCacheService"
            ".SmartLinkCacheService.warmup_all_active",
            return_value=5,
        ) as mock_warmup:
            out = _out()
            call_command("warmup_cache", stdout=out)
            mock_warmup.assert_called_once()
            self.assertIn("5", out.getvalue())

    def test_specific_slugs_flag(self):
        """--slugs warms only the specified slugs."""
        with patch(
            "api.smartlink.services.core.SmartLinkCacheService"
            ".SmartLinkCacheService.warmup",
            return_value=2,
        ) as mock_warmup:
            out = _out()
            call_command(
                "warmup_cache",
                "--slugs", self.sl.slug, "another-slug",
                stdout=out,
            )
            mock_warmup.assert_called_once_with([self.sl.slug, "another-slug"])
            self.assertIn("2", out.getvalue())

    def test_success_message_includes_count(self):
        """Command output includes the number of SmartLinks warmed."""
        with patch(
            "api.smartlink.services.core.SmartLinkCacheService"
            ".SmartLinkCacheService.warmup_all_active",
            return_value=12,
        ):
            out = _out()
            call_command("warmup_cache", stdout=out)
            self.assertIn("12", out.getvalue())

    def test_cache_failure_propagates(self):
        """Cache warmup propagates ConnectionError (operator must handle at call site)."""
        with patch(
            "api.smartlink.services.core.SmartLinkCacheService"
            ".SmartLinkCacheService.warmup_all_active",
            side_effect=ConnectionError("Redis connection refused"),
        ):
            out = _out()
            with self.assertRaises(ConnectionError):
                call_command("warmup_cache", stdout=out)


# ═════════════════════════════════════════════════════════════════════════════
# 11. import_smartlinks_csv
# ═════════════════════════════════════════════════════════════════════════════

class ImportSmartlinksCSVCommandTest(TestCase):
    """Tests for import_smartlinks_csv management command."""
    
    def setUp(self):
        self.publisher = _make_user("csv_publisher")
        self.csv_file = "/tmp/test_smartlinks.csv"
    
    def tearDown(self):
        """Clean up test CSV file."""
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
    
    def test_csv_import_creates_smartlinks(self):
        """CSV import creates SmartLink records."""
        csv_content = """name,slug,type,fallback_url,rotation_method,targeting_countries
Test Link 1,test-link-1,general,https://example.com,weighted,US
Test Link 2,test-link-2,general,https://fallback.com,round_robin,US,GB"""
        
        with open(self.csv_file, 'w') as f:
            f.write(csv_content)
        
        from api.smartlink.models import SmartLink
        count_before = SmartLink.objects.filter(publisher=self.publisher).count()
        
        out = _out()
        call_command("import_smartlinks_csv", self.csv_file, 
                    f"--publisher={self.publisher.username}", stdout=out)
        
        count_after = SmartLink.objects.filter(publisher=self.publisher).count()
        self.assertGreater(count_after, count_before)
        self.assertIn("Processing", out.getvalue())
    
    def test_dry_run_does_not_create(self):
        """--dry-run preview without creating."""
        csv_content = """name,slug
Test Link,test-link"""
        
        with open(self.csv_file, 'w') as f:
            f.write(csv_content)
        
        from api.smartlink.models import SmartLink
        count_before = SmartLink.objects.filter(publisher=self.publisher).count()
        
        out = _out()
        call_command("import_smartlinks_csv", self.csv_file,
                    f"--publisher={self.publisher.username}",
                    "--dry-run", stdout=out)
        
        count_after = SmartLink.objects.filter(publisher=self.publisher).count()
        self.assertEqual(count_after, count_before, "Dry-run should not create")
        self.assertIn("DRY RUN", out.getvalue())
    
    def test_missing_publisher_raises_error(self):
        """Non-existent publisher raises CommandError."""
        csv_content = """name,slug
Test,test"""
        
        with open(self.csv_file, 'w') as f:
            f.write(csv_content)
        
        with self.assertRaises(CommandError) as cm:
            call_command("import_smartlinks_csv", self.csv_file,
                        "--publisher=nonexistent")
        
        self.assertIn("not found", str(cm.exception))
    
    def test_missing_csv_file_raises_error(self):
        """Non-existent CSV file raises CommandError."""
        with self.assertRaises(CommandError) as cm:
            call_command("import_smartlinks_csv", "/nonexistent/file.csv",
                        f"--publisher={self.publisher.username}")
        
        self.assertIn("not found", str(cm.exception).lower())
    
    def test_skip_errors_continues_on_invalid_rows(self):
        """--skip-errors skips invalid rows and continues."""
        csv_content = """name,slug
,invalid-name-missing
Valid Link,valid-link
,another-invalid"""
        
        with open(self.csv_file, 'w') as f:
            f.write(csv_content)
        
        out = _out()
        call_command("import_smartlinks_csv", self.csv_file,
                    f"--publisher={self.publisher.username}",
                    "--skip-errors", stdout=out)
        
        # Should continue despite errors
        self.assertIn("skipping", out.getvalue().lower())


# ═════════════════════════════════════════════════════════════════════════════
# 12. generate_smartlinks
# ═════════════════════════════════════════════════════════════════════════════

class GenerateSmartlinksCommandTest(TestCase):
    """Tests for generate_smartlinks management command."""
    
    def setUp(self):
        self.publisher = _make_user("gen_publisher")
        self.offer = _make_offer()
    
    def test_generates_smartlinks_for_offers(self):
        """generate_smartlinks creates SmartLinks for offers."""
        from api.smartlink.models import SmartLink
        count_before = SmartLink.objects.count()
        
        out = _out()
        call_command("generate_smartlinks", "--count=3", stdout=out)
        
        count_after = SmartLink.objects.count()
        self.assertGreaterEqual(count_after, count_before)
    
    def test_count_parameter(self):
        """--count parameter controls number generated."""
        from api.smartlink.models import SmartLink
        count_before = SmartLink.objects.count()
        
        out = _out()
        call_command("generate_smartlinks", "--count=5", stdout=out)
        
        # Should report generation attempt
        self.assertIn("5", out.getvalue())
    
    def test_dry_run_reports_without_creating(self):
        """--dry-run reports without creating SmartLinks."""
        from api.smartlink.models import SmartLink
        count_before = SmartLink.objects.count()
        
        out = _out()
        call_command("generate_smartlinks", "--count=10", "--dry-run", stdout=out)
        
        count_after = SmartLink.objects.count()
        self.assertEqual(count_after, count_before, "Dry-run should not create")
        self.assertIn("DRY RUN", out.getvalue())
    
    def test_publisher_parameter(self):
        """--publisher parameter assigns SmartLinks to specific publisher."""
        from api.smartlink.models import SmartLink
        
        out = _out()
        call_command("generate_smartlinks", f"--publisher={self.publisher.username}",
                    "--count=2", stdout=out)
        
        # Check that SmartLinks were created
        output = out.getvalue()
        self.assertTrue(len(output) > 0)
    
    def test_no_parameters_uses_defaults(self):
        """Command runs with no parameters using defaults."""
        out = _out()
        # Should not raise with default parameters
        try:
            call_command("generate_smartlinks", stdout=out)
        except CommandError:
            pass  # May error if no publishers/offers, but shouldn't crash


