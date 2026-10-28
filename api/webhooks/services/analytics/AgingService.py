# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — WebhookAgingService

Evaluates every endpoint and delivery log, assigns age tiers,
schedules archive/purge, sends notifications, and writes audit events.

Public API:
    svc = AgingService()
    svc.run_full_sweep()                  → dict  (sweep summary)
    svc.evaluate_endpoint(endpoint)       → dict  (tier result)
    svc.evaluate_delivery_log(log)        → dict  (bucket result)
    svc.archive_due_records()             → dict  (archive summary)
    svc.purge_due_records(dry_run=False)  → dict  (purge summary)
    svc.get_aging_summary(owner=None)     → dict  (dashboard stats)
"""

import logging
from datetime import timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from ...models.aging import (
    AgeTier,
    AgingEventType,
    WebhookAgingEvent,
    WebhookAgingPolicy,
    WebhookDeliveryAging,
    WebhookEndpointAging,
)
from ...models.core import WebhookDeliveryLog, WebhookEndpoint
from ...exceptions import WebhookDispatchError

User = get_user_model()
logger = logging.getLogger("ainul.webhooks.aging")


class AgingService:
    """
    Ainul Enterprise Engine — Webhook lifecycle aging engine.

    Evaluates staleness of endpoints and delivery logs according to the
    owner's WebhookAgingPolicy (or the global default), assigns age tiers,
    schedules archival and purge timestamps, and records audit events.
    """

    # ── Init ─────────────────────────────────────────────────────────────────

    def __init__(self):
        self._policy_cache: dict = {}

    # ── Policy resolution ─────────────────────────────────────────────────────

    def _get_policy(self, owner) -> WebhookAgingPolicy:
        owner_id = getattr(owner, "pk", None)
        if owner_id not in self._policy_cache:
            policy = WebhookAgingPolicy.get_for_owner(owner)
            if policy is None:
                # Bootstrap a global default on first run
                policy, _ = WebhookAgingPolicy.objects.get_or_create(
                    owner=None,
                    defaults={
                        "log_warm_after_days":    7,
                        "log_cooling_after_days": 30,
                        "log_stale_after_days":   90,
                        "log_archive_after_days": 180,
                        "log_purge_after_days":   365,
                        "endpoint_warm_after_days":    7,
                        "endpoint_cooling_after_days": 30,
                        "endpoint_stale_after_days":   90,
                        "endpoint_dormant_after_days": 180,
                    },
                )
            self._policy_cache[owner_id] = policy
        return self._policy_cache[owner_id]

    # ── Full sweep ────────────────────────────────────────────────────────────

    def run_full_sweep(self) -> dict:
        """
        Ainul Enterprise Engine — Run a full aging sweep across all endpoints
        and delivery logs. Called by the Celery beat task.
        """
        logger.info("AgingService: starting full sweep")
        now = timezone.now()

        ep_results  = self._sweep_endpoints()
        log_results = self._sweep_delivery_logs()

        summary = {
            "swept_at":                now.isoformat(),
            "endpoints_evaluated":     ep_results["evaluated"],
            "endpoints_tier_changed":  ep_results["tier_changed"],
            "endpoints_archived":      ep_results["archived"],
            "endpoints_purge_warned":  ep_results["purge_warned"],
            "logs_evaluated":          log_results["evaluated"],
            "logs_tier_changed":       log_results["tier_changed"],
            "logs_archived":           log_results["archived"],
        }
        logger.info("AgingService sweep complete: %s", summary)
        return summary

    # ── Endpoint sweep ────────────────────────────────────────────────────────

    def _sweep_endpoints(self) -> dict:
        evaluated   = 0
        tier_changed = 0
        archived    = 0
        purge_warned = 0

        for endpoint in WebhookEndpoint.objects.select_related("owner").iterator():
            try:
                result = self.evaluate_endpoint(endpoint)
                evaluated += 1
                if result.get("tier_changed"):
                    tier_changed += 1
                if result.get("archived"):
                    archived += 1
                if result.get("purge_warned"):
                    purge_warned += 1
            except Exception as exc:
                logger.exception("AgingService: error evaluating endpoint %s: %s", endpoint.pk, exc)

        return {
            "evaluated":    evaluated,
            "tier_changed": tier_changed,
            "archived":     archived,
            "purge_warned": purge_warned,
        }

    def evaluate_endpoint(self, endpoint: WebhookEndpoint) -> dict:
        """
        Ainul Enterprise Engine — Compute and persist the age tier for one endpoint.
        Returns a result dict with keys: tier, tier_changed, archived, purge_warned.
        """
        policy = self._get_policy(endpoint.owner)
        now    = timezone.now()

        aging, _ = WebhookEndpointAging.objects.get_or_create(
            endpoint=endpoint,
            defaults={"last_delivery_at": endpoint.last_triggered_at},
        )

        # Update activity snapshot
        aging.last_delivery_at = endpoint.last_triggered_at
        aging.days_inactive    = aging.compute_days_inactive()
        aging.total_deliveries  = endpoint.total_deliveries
        aging.failed_deliveries = endpoint.failed_deliveries

        old_tier  = aging.tier
        new_tier  = aging.compute_tier(policy)
        tier_changed = old_tier != new_tier

        if tier_changed:
            aging.previous_tier = old_tier
            aging.tier          = new_tier
            self._record_event(
                event_type=AgingEventType.TIER_CHANGE,
                endpoint_aging=aging,
                from_tier=old_tier,
                to_tier=new_tier,
            )
            logger.debug("Endpoint %s: %s → %s", endpoint.label, old_tier, new_tier)

        # Schedule archive / purge timestamps
        if aging.archive_after is None and policy.endpoint_dormant_after_days:
            ref = aging.last_delivery_at or endpoint.created_at
            aging.archive_after = ref + timedelta(days=policy.endpoint_dormant_after_days + 90)
            aging.purge_after   = ref + timedelta(days=policy.endpoint_dormant_after_days + 180)

        # Send stale notification (once)
        stale_notified = False
        if (
            new_tier in (AgeTier.STALE, AgeTier.DORMANT)
            and policy.notify_on_stale
            and not aging.stale_notified_at
        ):
            self._send_stale_notification(endpoint, aging, new_tier)
            aging.stale_notified_at = now
            stale_notified = True

        # Purge warning
        purge_warned = False
        if aging.needs_purge_warning and policy.notify_before_purge:
            self._send_purge_warning(endpoint, aging)
            aging.purge_warned_at = now
            purge_warned = True

        # Archive if due
        archived = False
        if aging.archive_after and now >= aging.archive_after and not aging.is_archived:
            aging.is_archived  = True
            aging.archived_at  = now
            aging.tier         = AgeTier.ARCHIVED
            self._record_event(
                event_type=AgingEventType.ARCHIVED,
                endpoint_aging=aging,
                from_tier=new_tier,
                to_tier=AgeTier.ARCHIVED,
            )
            archived = True

        aging.last_evaluated_at = now
        aging.save()

        return {
            "tier":         aging.tier,
            "tier_changed": tier_changed,
            "archived":     archived,
            "purge_warned": purge_warned,
        }

    # ── Delivery log sweep ────────────────────────────────────────────────────

    def _sweep_delivery_logs(self) -> dict:
        evaluated   = 0
        tier_changed = 0
        archived    = 0

        qs = WebhookDeliveryLog.objects.select_related(
            "endpoint", "endpoint__owner"
        ).exclude(
            aging__is_purged=True
        ).iterator()

        for log in qs:
            try:
                result = self.evaluate_delivery_log(log)
                evaluated += 1
                if result.get("tier_changed"):
                    tier_changed += 1
                if result.get("archived"):
                    archived += 1
            except Exception as exc:
                logger.exception("AgingService: error evaluating log %s: %s", log.pk, exc)

        return {"evaluated": evaluated, "tier_changed": tier_changed, "archived": archived}

    def evaluate_delivery_log(self, log: WebhookDeliveryLog) -> dict:
        """
        Ainul Enterprise Engine — Compute and persist the age bucket for one delivery log.
        """
        policy = self._get_policy(log.endpoint.owner)
        now    = timezone.now()

        aging, _ = WebhookDeliveryAging.objects.get_or_create(delivery_log=log)

        age_days = (now - log.created_at).days
        aging.age_days = age_days

        old_bucket = aging.bucket
        new_bucket = self._compute_log_bucket(age_days, policy)
        tier_changed = old_bucket != new_bucket

        if tier_changed:
            aging.bucket = new_bucket

        # Set archive/purge timestamps if not already set
        if aging.archive_after is None:
            aging.archive_after = log.created_at + timedelta(days=policy.log_archive_after_days)
            aging.purge_after   = log.created_at + timedelta(days=policy.log_purge_after_days)

        # Archive if due
        archived = False
        if aging.archive_after and now >= aging.archive_after and not aging.is_archived:
            aging.is_archived = True
            aging.archived_at = now
            aging.bucket      = AgeTier.ARCHIVED
            archived = True

        aging.last_evaluated_at = now
        aging.save()

        return {"bucket": aging.bucket, "tier_changed": tier_changed, "archived": archived}

    @staticmethod
    def _compute_log_bucket(age_days: int, policy: WebhookAgingPolicy) -> str:
        if age_days >= policy.log_archive_after_days:
            return AgeTier.ARCHIVED
        if age_days >= policy.log_stale_after_days:
            return AgeTier.STALE
        if age_days >= policy.log_cooling_after_days:
            return AgeTier.COOLING
        if age_days >= policy.log_warm_after_days:
            return AgeTier.WARM
        return AgeTier.FRESH

    # ── Archive / Purge actions ───────────────────────────────────────────────

    def archive_due_records(self) -> dict:
        """
        Ainul Enterprise Engine — Archive all records where archive_after <= now.
        Does not delete; sets is_archived flag and records an audit event.
        """
        now = timezone.now()
        ep_count  = 0
        log_count = 0

        with transaction.atomic():
            due_eps = WebhookEndpointAging.objects.filter(
                archive_after__lte=now, is_archived=False
            )
            for aging in due_eps:
                old_tier = aging.tier
                aging.is_archived = True
                aging.archived_at = now
                aging.tier        = AgeTier.ARCHIVED
                aging.save()
                self._record_event(
                    AgingEventType.ARCHIVED, endpoint_aging=aging,
                    from_tier=old_tier, to_tier=AgeTier.ARCHIVED,
                )
                ep_count += 1

            due_logs = WebhookDeliveryAging.objects.filter(
                archive_after__lte=now, is_archived=False
            )
            for aging in due_logs:
                aging.is_archived = True
                aging.archived_at = now
                aging.bucket      = AgeTier.ARCHIVED
                aging.save()
                log_count += 1

        return {
            "archived_endpoints":     ep_count,
            "archived_delivery_logs": log_count,
            "archived_at":            now.isoformat(),
        }

    def purge_due_records(self, dry_run: bool = True) -> dict:
        """
        Ainul Enterprise Engine — Purge all records where purge_after <= now.

        Args:
            dry_run: If True (default), returns count without deleting.
                     Set to False only from the Celery purge task.
        """
        now = timezone.now()

        ep_qs  = WebhookEndpointAging.objects.filter(purge_after__lte=now, is_purged=False)
        log_qs = WebhookDeliveryAging.objects.filter(purge_after__lte=now, is_purged=False)

        ep_count  = ep_qs.count()
        log_count = log_qs.count()

        if dry_run:
            return {
                "dry_run":           True,
                "endpoints_to_purge":     ep_count,
                "delivery_logs_to_purge": log_count,
            }

        with transaction.atomic():
            for aging in ep_qs.select_related("endpoint"):
                old_tier = aging.tier
                aging.is_purged = True
                aging.purged_at = now
                aging.tier      = AgeTier.PURGED
                aging.save()
                self._record_event(
                    AgingEventType.PURGED, endpoint_aging=aging,
                    from_tier=old_tier, to_tier=AgeTier.PURGED,
                )

            for aging in log_qs:
                aging.is_purged = True
                aging.purged_at = now
                aging.bucket    = AgeTier.PURGED
                aging.save()
                WebhookDeliveryLog.objects.filter(pk=aging.delivery_log_id).delete()

        return {
            "dry_run":               False,
            "endpoints_purged":      ep_count,
            "delivery_logs_purged":  log_count,
            "purged_at":             now.isoformat(),
        }

    # ── Dashboard summary ─────────────────────────────────────────────────────

    def get_aging_summary(self, owner=None) -> dict:
        """
        Ainul Enterprise Engine — Return tier distribution stats for the dashboard.
        Pass owner to scope to a specific user, or None for platform-wide stats.
        """
        ep_qs  = WebhookEndpointAging.objects.all()
        log_qs = WebhookDeliveryAging.objects.all()

        if owner:
            ep_qs  = ep_qs.filter(endpoint__owner=owner)
            log_qs = log_qs.filter(delivery_log__endpoint__owner=owner)

        ep_by_tier = {
            row["tier"]: row["count"]
            for row in ep_qs.values("tier").annotate(count=Count("id"))
        }
        log_by_bucket = {
            row["bucket"]: row["count"]
            for row in log_qs.values("bucket").annotate(count=Count("id"))
        }

        return {
            "endpoints": {
                "total":    ep_qs.count(),
                "by_tier":  ep_by_tier,
                "archived": ep_qs.filter(is_archived=True).count(),
                "purged":   ep_qs.filter(is_purged=True).count(),
            },
            "delivery_logs": {
                "total":     log_qs.count(),
                "by_bucket": log_by_bucket,
                "archived":  log_qs.filter(is_archived=True).count(),
                "purged":    log_qs.filter(is_purged=True).count(),
            },
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _record_event(
        event_type: str,
        endpoint_aging: Optional[WebhookEndpointAging] = None,
        delivery_aging: Optional[WebhookDeliveryAging] = None,
        from_tier: str = "",
        to_tier:   str = "",
        detail:    dict = None,
    ):
        WebhookAgingEvent.objects.create(
            event_type     = event_type,
            endpoint_aging = endpoint_aging,
            delivery_aging = delivery_aging,
            from_tier      = from_tier,
            to_tier        = to_tier,
            detail         = detail or {},
        )

    @staticmethod
    def _send_stale_notification(endpoint, aging, tier):
        """Stub: hook into notification system (email / Slack / push)."""
        logger.info(
            "STALE NOTIFICATION: endpoint=%s label=%s tier=%s days_inactive=%d",
            endpoint.pk, endpoint.label, tier, aging.days_inactive,
        )

    @staticmethod
    def _send_purge_warning(endpoint, aging):
        """Stub: hook into notification system."""
        logger.warning(
            "PURGE WARNING: endpoint=%s label=%s purge_after=%s",
            endpoint.pk, endpoint.label, aging.purge_after,
        )
