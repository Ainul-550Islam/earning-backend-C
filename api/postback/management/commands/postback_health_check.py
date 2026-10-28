"""
management/commands/postback_health_check.py

Runs a comprehensive health check on the postback system and reports:
  • Database connectivity (PostbackLog, NetworkPostbackConfig tables)
  • Cache connectivity (nonce + rate limit keys)
  • Celery task queue reachability
  • Active network configs
  • Recent postback statistics (last 24h)
  • S2S callback URL reachability (HEAD request)
  • Pending/failed postbacks that need attention

Usage:
    python manage.py postback_health_check
    python manage.py postback_health_check --fix          # auto-requeue failed postbacks
    python manage.py postback_health_check --json         # machine-readable output
    python manage.py postback_health_check --network cpalead  # check specific network
"""
import json
import sys
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Comprehensive health check for the postback system."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Auto-requeue failed postbacks found during check.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Output results as JSON (for CI/monitoring integration).",
        )
        parser.add_argument(
            "--network",
            type=str,
            default=None,
            help="Check a specific network_key only.",
        )

    def handle(self, *args, **options):
        results = {}
        has_critical = False

        # ── 1. Database check ─────────────────────────────────────────────────
        db_ok, db_msg = self._check_db()
        results["database"] = {"ok": db_ok, "detail": db_msg}
        if not db_ok:
            has_critical = True

        # ── 2. Cache check ────────────────────────────────────────────────────
        cache_ok, cache_msg = self._check_cache()
        results["cache"] = {"ok": cache_ok, "detail": cache_msg}

        # ── 3. Celery check ───────────────────────────────────────────────────
        celery_ok, celery_msg = self._check_celery()
        results["celery"] = {"ok": celery_ok, "detail": celery_msg}
        if not celery_ok:
            has_critical = True

        # ── 4. Active networks ────────────────────────────────────────────────
        networks_info = self._check_networks(options.get("network"))
        results["networks"] = networks_info

        # ── 5. Recent stats (last 24h) ────────────────────────────────────────
        stats = self._get_recent_stats()
        results["stats_24h"] = stats

        # ── 6. S2S callback reachability ──────────────────────────────────────
        s2s_info = self._check_s2s_callbacks(options.get("network"))
        results["s2s_callbacks"] = s2s_info

        # ── 7. Pending attention ──────────────────────────────────────────────
        attention = self._check_needs_attention(fix=options.get("fix", False))
        results["needs_attention"] = attention

        # ── Output ────────────────────────────────────────────────────────────
        if options.get("json_output"):
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._print_human(results, has_critical)

        if has_critical:
            sys.exit(1)

    # ── Checks ────────────────────────────────────────────────────────────────

    def _check_db(self):
        try:
            from postback.models import PostbackLog, NetworkPostbackConfig
            log_count = PostbackLog.objects.count()
            net_count = NetworkPostbackConfig.objects.count()
            return True, f"PostbackLog={log_count} rows, NetworkConfigs={net_count} rows"
        except Exception as e:
            return False, f"DB ERROR: {e}"

    def _check_cache(self):
        try:
            from django.core.cache import cache
            test_key = "postback:healthcheck:test"
            cache.set(test_key, "ok", timeout=5)
            val = cache.get(test_key)
            cache.delete(test_key)
            if val == "ok":
                return True, "Cache read/write OK"
            return False, "Cache write succeeded but read returned wrong value"
        except Exception as e:
            return False, f"Cache ERROR: {e}"

    def _check_celery(self):
        try:
            from celery import current_app
            inspect = current_app.control.inspect(timeout=2.0)
            active = inspect.active()
            if active is not None:
                worker_count = len(active)
                return True, f"{worker_count} active Celery worker(s) responding"
            return False, "No Celery workers responded within timeout"
        except Exception as e:
            return False, f"Celery check ERROR: {e}"

    def _check_networks(self, network_key=None):
        try:
            from postback.models import NetworkPostbackConfig
            qs = NetworkPostbackConfig.objects.all()
            if network_key:
                qs = qs.filter(network_key=network_key)
            active = qs.filter(status="active").count()
            inactive = qs.filter(status="inactive").count()
            testing = qs.filter(status="testing").count()
            has_s2s = qs.exclude(callback_url="").count()
            return {
                "total": qs.count(),
                "active": active,
                "inactive": inactive,
                "testing": testing,
                "with_s2s_callback": has_s2s,
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_recent_stats(self):
        try:
            from postback.models import PostbackLog
            since = timezone.now() - timedelta(hours=24)
            qs = PostbackLog.objects.filter(received_at__gte=since)
            from django.db.models import Sum, Count
            stats = qs.aggregate(
                total=Count("id"),
                rewarded=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(status="rewarded")),
                rejected=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(status="rejected")),
                failed=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(status="failed")),
                reversals=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(is_reversal=True)),
                total_payout=Sum("payout"),
            )
            return {
                "period": "last_24h",
                "total": stats["total"] or 0,
                "rewarded": stats["rewarded"] or 0,
                "rejected": stats["rejected"] or 0,
                "failed": stats["failed"] or 0,
                "reversals": stats["reversals"] or 0,
                "total_payout": str(stats["total_payout"] or "0.00"),
            }
        except Exception as e:
            return {"error": str(e)}

    def _check_s2s_callbacks(self, network_key=None):
        try:
            from postback.models import NetworkPostbackConfig
            qs = NetworkPostbackConfig.objects.exclude(callback_url="").filter(status="active")
            if network_key:
                qs = qs.filter(network_key=network_key)
            results = []
            for net in qs[:10]:  # Check max 10
                url = net.callback_url.split("?")[0]  # Base URL only
                reachable = self._head_request(url)
                results.append({
                    "network_key": net.network_key,
                    "callback_base_url": url[:80],
                    "reachable": reachable,
                })
            return results
        except Exception as e:
            return {"error": str(e)}

    def _head_request(self, url: str) -> bool:
        try:
            if not url.startswith("https://"):
                return False
            import urllib.request
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status < 500
        except Exception:
            return False

    def _check_needs_attention(self, fix=False):
        try:
            from postback.models import PostbackLog
            from postback.choices import PostbackStatus
            attention = {}

            # Failed postbacks overdue for retry
            overdue = PostbackLog.objects.filter(
                status=PostbackStatus.FAILED,
                next_retry_at__lt=timezone.now(),
            ).count()
            attention["failed_overdue_for_retry"] = overdue

            if fix and overdue > 0:
                from postback.tasks import retry_failed_postbacks
                retry_failed_postbacks.delay()
                attention["auto_requeued"] = True
                self.stdout.write(self.style.SUCCESS(
                    f"  Auto-requeued {overdue} failed postback(s)."
                ))

            # Stuck in RECEIVED for >30 minutes
            stuck = PostbackLog.objects.filter(
                status=PostbackStatus.RECEIVED,
                received_at__lt=timezone.now() - timedelta(minutes=30),
            ).count()
            attention["stuck_in_received"] = stuck

            return attention
        except Exception as e:
            return {"error": str(e)}

    # ── Human-readable output ─────────────────────────────────────────────────

    def _print_human(self, results, has_critical):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("  POSTBACK SYSTEM HEALTH CHECK")
        self.stdout.write("=" * 60)

        status_map = {True: self.style.SUCCESS("✓ OK"), False: self.style.ERROR("✗ FAIL")}

        for key in ["database", "cache", "celery"]:
            r = results.get(key, {})
            ok = r.get("ok", False)
            detail = r.get("detail", "")
            self.stdout.write(f"  {key.upper():12} {status_map[ok]}  {detail}")

        self.stdout.write("\n  NETWORKS:")
        n = results.get("networks", {})
        for k, v in n.items():
            self.stdout.write(f"    {k}: {v}")

        self.stdout.write("\n  STATS (24h):")
        s = results.get("stats_24h", {})
        for k, v in s.items():
            if k != "period":
                self.stdout.write(f"    {k}: {v}")

        attention = results.get("needs_attention", {})
        if attention.get("failed_overdue_for_retry", 0) > 0:
            self.stdout.write(self.style.WARNING(
                f"\n  ⚠ {attention['failed_overdue_for_retry']} postback(s) overdue for retry"
            ))
        if attention.get("stuck_in_received", 0) > 0:
            self.stdout.write(self.style.WARNING(
                f"  ⚠ {attention['stuck_in_received']} postback(s) stuck in RECEIVED state"
            ))

        self.stdout.write("\n" + "=" * 60)
        if has_critical:
            self.stdout.write(self.style.ERROR("  STATUS: CRITICAL ISSUES FOUND"))
        else:
            self.stdout.write(self.style.SUCCESS("  STATUS: ALL CHECKS PASSED"))
        self.stdout.write("=" * 60 + "\n")
