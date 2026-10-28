"""Secret Rotation Service

This module provides webhook secret rotation functionality with grace
periods and invalidation.

FIX APPLIED:
    [ROT-01] rotate_secret() and rotate_inbound_secret() fetched the
             endpoint/inbound_webhook row inside an atomic block but did NOT
             lock it first.  Two concurrent rotation requests on the same
             endpoint could both read the current secret_key, each create an
             old-secret archive row, and each write a *different* new secret_key
             — the last writer wins and the first writer's rotation is silently
             lost.  The endpoint.secret_key and the archived row are then
             permanently out of sync.

             Fix: added select_for_update() so the first concurrent caller
             acquires a row-level lock.  The second caller blocks until the
             first transaction commits, then reads the already-rotated key and
             proceeds safely with a second rotation.
"""

import hashlib
import logging
import secrets
import string
from typing import Dict, Any, Optional, List
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ...models import WebhookEndpoint, WebhookSecret
from ...choices import WebhookStatus
from ...exceptions import WebhookSecurityError

logger = logging.getLogger(__name__)


class SecretRotationService:
    """Service for rotating webhook secrets with grace periods and invalidation."""

    def __init__(self):
        self.default_secret_length  = getattr(settings, "WEBHOOK_SECRET_LENGTH", 32)
        self.grace_period_hours     = getattr(settings, "WEBHOOK_SECRET_GRACE_PERIOD_HOURS", 24)
        self.max_old_secrets        = getattr(settings, "WEBHOOK_MAX_OLD_SECRETS", 3)

    # ─────────────────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────────────────────

    def rotate_secret(self, endpoint: WebhookEndpoint) -> str:
        """
        Rotate the signing secret for a webhook endpoint.

        FIX [ROT-01]: The endpoint row is now locked with select_for_update()
        inside the atomic block.  This serialises concurrent rotation requests
        so that only one new secret is produced per rotation call, preventing
        the race condition where two callers each read the same old secret,
        produce two different new ones, and the first writer's rotation is
        silently overwritten.

        Args:
            endpoint: The WebhookEndpoint to rotate.
        Returns:
            The newly generated secret_key string.
        Raises:
            WebhookSecurityError: on any unexpected failure.
        """
        try:
            with transaction.atomic():
                # FIX [ROT-01]: acquire a row-level lock so concurrent rotation
                # requests on the same endpoint are serialised, not lost.
                locked_endpoint = (
                    WebhookEndpoint.objects
                    .select_for_update()
                    .get(pk=endpoint.pk)
                )

                new_secret = self._generate_secret()

                # Archive the current secret inside the lock
                if locked_endpoint.secret_key:
                    WebhookSecret.objects.create(
                        endpoint=locked_endpoint,
                        secret_hash=hashlib.sha256(locked_endpoint.secret_key.encode()).hexdigest(),
                        is_active=False,
                        expires_at=timezone.now() + timedelta(hours=self.grace_period_hours),
                    )

                locked_endpoint.secret_key = new_secret
                locked_endpoint.save(update_fields=["secret_key", "updated_at"])

                # Keep endpoint object in sync with DB
                endpoint.secret_key = new_secret

                self._cleanup_old_secrets(locked_endpoint)

                logger.info("Secret rotated for endpoint %s", locked_endpoint.id)
                return new_secret

        except WebhookEndpoint.DoesNotExist:
            raise WebhookSecurityError(
                f"Endpoint {endpoint.pk} not found — cannot rotate secret."
            )
        except Exception as exc:
            logger.error("Error rotating secret for endpoint %s: %s", endpoint.pk, exc)
            raise

    def rotate_inbound_secret(self, inbound_webhook) -> str:
        """
        Rotate the secret for an inbound webhook.

        FIX [ROT-01]: Same select_for_update() pattern applied here so that
        concurrent rotation requests on the same inbound webhook are serialised.
        """
        try:
            with transaction.atomic():
                # FIX [ROT-01]: row-level lock prevents concurrent rotation
                # producing two different new secrets for the same row.
                from ...models import InboundWebhookSource   # local import avoids circulars
                locked_inbound = (
                    inbound_webhook.__class__.objects
                    .select_for_update()
                    .get(pk=inbound_webhook.pk)
                )

                new_secret = self._generate_secret()

                if locked_inbound.secret:
                    WebhookSecret.objects.create(
                        endpoint=None,
                        inbound_webhook=locked_inbound,
                        secret_key=locked_inbound.secret,
                        is_active=False,
                        expires_at=timezone.now() + timedelta(hours=self.grace_period_hours),
                        created_by=locked_inbound.created_by,
                    )

                locked_inbound.secret = new_secret
                locked_inbound.save(update_fields=["secret", "updated_at"])

                inbound_webhook.secret = new_secret

                self._cleanup_old_inbound_secrets(locked_inbound)

                logger.info("Secret rotated for inbound webhook %s", locked_inbound.id)
                return new_secret

        except Exception as exc:
            logger.error(
                "Error rotating secret for inbound webhook %s: %s",
                getattr(inbound_webhook, "pk", "?"), exc,
            )
            raise

    def is_rotation_needed(self, endpoint: WebhookEndpoint, grace_period_days: int = 7) -> bool:
        """
        Decide whether an endpoint's current secret is due for rotation.

        NEW METHOD (Session 9) - rotate_all_secrets.py has always called
        `rotation_service.is_rotation_needed(endpoint, grace_period)`, but
        this method never existed anywhere in the codebase (confirmed via
        a full-repo search). That meant every call raised AttributeError,
        caught by the command's own per-endpoint try/except - so running
        the command without --force failed on 100% of endpoints, every
        time; --force worked only because it skips this check entirely.

        This is genuinely new logic, not a restored pre-existing
        behavior, and involved a real judgment call worth flagging (see
        FIXES_APPLIED_SESSION9.md): no field anywhere in this codebase
        tracks "when should the current secret next rotate", or even
        "when was it last rotated", directly. endpoint.secret_key is a
        plain string with no expiry of its own - WebhookSecret.expires_at
        looks like it would answer this, but reading rotate_secret()
        confirms it's the grace-period end of an ARCHIVED (is_active=False)
        *retired* secret, unrelated to when the CURRENT one should next
        rotate.

        Implemented as: due if there's no secret at all, or if at least
        grace_period_days have passed since the last rotation - using the
        most recent archived WebhookSecret.created_at for this endpoint
        as "last rotated", or endpoint.created_at if it has never been
        rotated. This treats grace_period_days as a rotation interval
        (how often to rotate), not a lookahead-to-expiry window as
        rotate_all_secrets.py's own --grace-period help text suggests
        ("before old secret expires") - there is no expiry to look ahead
        to for the current secret, so a lookahead reading isn't
        implementable against real data. Flagged for confirmation rather
        than silently assumed correct.

        Args:
            endpoint: WebhookEndpoint instance
            grace_period_days: rotation interval in days

        Returns:
            True if the secret should be rotated now
        """
        if not endpoint.secret_key:
            return True

        last_rotated = (
            WebhookSecret.objects.filter(endpoint=endpoint)
            .order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        ) or endpoint.created_at

        if last_rotated is None:
            return True

        return (timezone.now() - last_rotated) >= timedelta(days=grace_period_days)

    def invalidate_secret(self, endpoint: WebhookEndpoint, reason: str = "Manual invalidation") -> bool:
        """Immediately invalidate the current secret and replace it."""
        try:
            with transaction.atomic():
                # FIX [ROT-01]: lock endpoint here too — invalidation has the
                # same race as rotation.
                locked_endpoint = (
                    WebhookEndpoint.objects
                    .select_for_update()
                    .get(pk=endpoint.pk)
                )

                if not locked_endpoint.secret_key:
                    return False

                WebhookSecret.objects.create(
                    endpoint=locked_endpoint,
                    secret_hash=hashlib.sha256(locked_endpoint.secret_key.encode()).hexdigest(),
                    is_active=False,
                    expires_at=timezone.now(),  # immediate expiry
                )

                new_secret               = self._generate_secret()
                locked_endpoint.secret_key = new_secret
                locked_endpoint.save(update_fields=["secret_key", "updated_at"])
                endpoint.secret_key = new_secret

                logger.info("Secret invalidated for endpoint %s: %s", locked_endpoint.id, reason)
                return True

        except Exception as exc:
            logger.error("Error invalidating secret for endpoint %s: %s", endpoint.pk, exc)
            return False

    def validate_secret(self, endpoint: WebhookEndpoint, provided_secret: str) -> bool:
        """
        Validate a provided secret against the current key and unexpired
        grace-period secrets.
        """
        try:
            if endpoint.secret_key == provided_secret:
                return True

            return WebhookSecret.objects.filter(
                endpoint=endpoint,
                secret_key=provided_secret,
                is_active=False,
                expires_at__gt=timezone.now(),
            ).exists()

        except Exception as exc:
            logger.error("Error validating secret for endpoint %s: %s", endpoint.pk, exc)
            return False

    def rotate_all_secrets(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Rotate secrets for all active endpoints (or those owned by user_id)."""
        try:
            endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE)
            if user_id:
                endpoints = endpoints.filter(owner_id=user_id)

            total         = endpoints.count()
            rotated_count = 0
            failed_count  = 0
            errors: List[str] = []

            for endpoint in endpoints:
                try:
                    self.rotate_secret(endpoint)
                    rotated_count += 1
                except Exception as exc:
                    failed_count += 1
                    errors.append(f"Endpoint {endpoint.id}: {exc}")

            return {
                "total_endpoints": total,
                "rotated_count":   rotated_count,
                "failed_count":    failed_count,
                "errors":          errors,
            }

        except Exception as exc:
            logger.error("Error rotating all secrets: %s", exc)
            return {
                "total_endpoints": 0,
                "rotated_count":   0,
                "failed_count":    0,
                "errors":          [str(exc)],
            }

    # ─────────────────────────────────────────────────────────────────────────
    #  HISTORY / STATS
    # ─────────────────────────────────────────────────────────────────────────

    def get_secret_history(self, endpoint: WebhookEndpoint) -> List[Dict[str, Any]]:
        """Return rotation history for an endpoint (newest first)."""
        try:
            archived = WebhookSecret.objects.filter(endpoint=endpoint).order_by("-created_at")

            history: List[Dict[str, Any]] = []
            for s in archived:
                history.append({
                    "secret_id":      str(s.id),
                    "secret_preview": (s.secret_key[:8] + "...") if s.secret_key else None,
                    "is_active":      s.is_active,
                    "expires_at":     s.expires_at.isoformat() if s.expires_at else None,
                    "created_at":     s.created_at.isoformat(),
                    "is_expired":     bool(s.expires_at and s.expires_at < timezone.now()),
                })

            if endpoint.secret_key:
                history.insert(0, {
                    "secret_id":      None,
                    "secret_preview": endpoint.secret_key[:8] + "...",
                    "is_active":      True,
                    "expires_at":     None,
                    "created_at":     endpoint.updated_at.isoformat(),
                    "is_expired":     False,
                })

            return history

        except Exception as exc:
            logger.error("Error getting secret history for endpoint %s: %s", endpoint.pk, exc)
            return []

    def get_expiring_secrets(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Return archived secrets expiring within the next `hours`."""
        try:
            cutoff = timezone.now() + timedelta(hours=hours)
            expiring = (
                WebhookSecret.objects
                .filter(expires_at__lte=cutoff, expires_at__gt=timezone.now(), is_active=False)
                .select_related("endpoint")
            )

            result: List[Dict[str, Any]] = []
            for s in expiring:
                entry: Dict[str, Any] = {
                    "secret_id":         str(s.id),
                    "expires_at":        s.expires_at.isoformat(),
                    "hours_until_expiry": (s.expires_at - timezone.now()).total_seconds() / 3600,
                }
                if s.endpoint:
                    entry.update({
                        "endpoint_id":    str(s.endpoint.id),
                        "endpoint_label": s.endpoint.label,
                        "endpoint_url":   s.endpoint.target_url,
                    })
                result.append(entry)

            return result

        except Exception as exc:
            logger.error("Error getting expiring secrets: %s", exc)
            return []

    def extend_grace_period(self, secret_id: str, additional_hours: int = 24) -> bool:
        """Extend the grace window of an archived (non-active) secret."""
        try:
            s = WebhookSecret.objects.get(id=secret_id)
            if s.is_active:
                return False
            s.expires_at = timezone.now() + timedelta(hours=additional_hours)
            s.save(update_fields=["expires_at"])
            logger.info("Extended grace period for secret %s by %d hours", secret_id, additional_hours)
            return True

        except WebhookSecret.DoesNotExist:
            logger.error("Secret %s not found", secret_id)
            return False
        except Exception as exc:
            logger.error("Error extending grace period for secret %s: %s", secret_id, exc)
            return False

    def get_rotation_statistics(self) -> Dict[str, Any]:
        """Return system-wide rotation statistics."""
        try:
            now = timezone.now()
            return {
                "total_endpoints":       WebhookEndpoint.objects.count(),
                "active_endpoints":      WebhookEndpoint.objects.filter(secret_key__isnull=False).count(),
                "total_secrets":         WebhookSecret.objects.count(),
                "grace_period_secrets":  WebhookSecret.objects.filter(is_active=False, expires_at__gt=now).count(),
                "expired_secrets":       WebhookSecret.objects.filter(is_active=False, expires_at__lt=now).count(),
                "recent_rotations_7d":   WebhookSecret.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
                "grace_period_hours":    self.grace_period_hours,
                "max_old_secrets":       self.max_old_secrets,
            }
        except Exception as exc:
            logger.error("Error getting rotation statistics: %s", exc)
            return {
                "total_endpoints": 0, "active_endpoints": 0, "total_secrets": 0,
                "grace_period_secrets": 0, "expired_secrets": 0, "recent_rotations_7d": 0,
                "grace_period_hours": self.grace_period_hours,
                "max_old_secrets": self.max_old_secrets,
                "error": str(exc),
            }

    # ─────────────────────────────────────────────────────────────────────────
    #  PRIVATE HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_secret(self, length: int = None) -> str:
        """Generate a cryptographically secure random secret string."""
        length = length or self.default_secret_length
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _cleanup_old_secrets(self, endpoint: WebhookEndpoint) -> int:
        """Delete expired / excess archived secrets for an endpoint."""
        try:
            qs = WebhookSecret.objects.filter(endpoint=endpoint).order_by("-created_at")
            total = qs.count()

            if total > self.max_old_secrets:
                to_delete = qs[self.max_old_secrets:]
                count     = to_delete.count()
                WebhookSecret.objects.filter(
                    pk__in=to_delete.values_list("pk", flat=True)
                ).delete()
            else:
                expired   = qs.filter(expires_at__lt=timezone.now())
                count     = expired.count()
                expired.delete()

            logger.info("Cleaned up %d old secrets for endpoint %s", count, endpoint.id)
            return count

        except Exception as exc:
            logger.error("Error cleaning up secrets for endpoint %s: %s", endpoint.id, exc)
            return 0

    def _cleanup_old_inbound_secrets(self, inbound_webhook) -> int:
        """Delete expired / excess archived secrets for an inbound webhook."""
        try:
            qs    = WebhookSecret.objects.filter(inbound_webhook=inbound_webhook).order_by("-created_at")
            total = qs.count()

            if total > self.max_old_secrets:
                to_delete = qs[self.max_old_secrets:]
                count     = to_delete.count()
                WebhookSecret.objects.filter(
                    pk__in=to_delete.values_list("pk", flat=True)
                ).delete()
            else:
                expired = qs.filter(expires_at__lt=timezone.now())
                count   = expired.count()
                expired.delete()

            logger.info(
                "Cleaned up %d old secrets for inbound webhook %s", count, inbound_webhook.id
            )
            return count

        except Exception as exc:
            logger.error(
                "Error cleaning up secrets for inbound webhook %s: %s",
                getattr(inbound_webhook, "id", "?"), exc,
            )
            return 0
