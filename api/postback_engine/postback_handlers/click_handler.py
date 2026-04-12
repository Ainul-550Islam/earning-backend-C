"""
postback_handlers/click_handler.py
────────────────────────────────────
Handles click tracking events:
  - Generate click ID when user clicks an offer
  - Validate incoming click_id during conversion attribution
  - Redirect user to offer URL with tracking macros embedded
  - Async: fraud scan + geo enrichment + device fingerprinting
"""
from __future__ import annotations
import hashlib
import logging
import secrets
from typing import Optional
from django.utils import timezone
from ..constants import CLICK_ID_LENGTH, CLICK_EXPIRY_HOURS
from ..enums import ClickStatus, DeviceType
from ..exceptions import ClickExpiredException, ClickNotFoundException, FraudDetectedException
from ..models import ClickLog, AdNetworkConfig
from ..signals import click_tracked, click_converted, click_expired, click_fraud

logger = logging.getLogger(__name__)


class ClickHandler:
    """
    Full click lifecycle management.
    """

    def generate(
        self,
        user,
        network: AdNetworkConfig,
        offer_id: str,
        offer_name: str = "",
        ip_address: str = "",
        user_agent: str = "",
        device_type: str = DeviceType.UNKNOWN,
        device_id: str = "",
        country: str = "",
        sub_id: str = "",
        sub_id2: str = "",
        referrer: str = "",
        utm_source: str = "",
        utm_medium: str = "",
        utm_campaign: str = "",
        campaign_id: str = "",
        metadata: dict = None,
    ) -> ClickLog:
        """
        Generate a new ClickLog. The click_id is embedded as {click_id} macro
        in the offer URL so the network returns it in the postback.
        """
        click_id = self._generate_click_id()
        expiry = timezone.now() + timezone.timedelta(hours=CLICK_EXPIRY_HOURS)
        fingerprint = self._compute_fingerprint(ip_address, user_agent, device_id)

        click_log = ClickLog.objects.create(
            tenant=network.tenant,
            click_id=click_id,
            user=user,
            network=network,
            offer_id=offer_id,
            offer_name=offer_name,
            campaign_id=campaign_id,
            ip_address=ip_address or None,
            user_agent=user_agent,
            device_type=device_type,
            device_id=device_id,
            device_fingerprint=fingerprint,
            country=country,
            sub_id=sub_id,
            sub_id2=sub_id2,
            referrer=referrer,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            expires_at=expiry,
            status=ClickStatus.VALID,
            metadata=metadata or {},
        )

        click_tracked.send(sender=ClickLog, click_log=click_log)

        # Async: fraud scan
        try:
            from ..tasks import process_click_task
            process_click_task.apply_async(args=[str(click_log.id)], countdown=1)
        except Exception as exc:
            logger.debug("click fraud scan dispatch failed (non-fatal): %s", exc)

        return click_log

    def validate(self, click_id: str) -> ClickLog:
        """
        Validate a click_id for conversion attribution.
        Raises ClickNotFoundException, ClickExpiredException, FraudDetectedException.
        """
        click_log = ClickLog.objects.get_by_click_id(click_id)
        if click_log is None:
            raise ClickNotFoundException(f"No click found: '{click_id}'")
        if click_log.status == ClickStatus.FRAUD:
            raise FraudDetectedException(
                f"Click '{click_id}' flagged as fraud.",
                fraud_type=click_log.fraud_type,
                fraud_score=click_log.fraud_score,
            )
        if click_log.is_expired:
            click_log.status = ClickStatus.EXPIRED
            click_log.save(update_fields=["status"])
            click_expired.send(sender=ClickLog, click_log=click_log)
            raise ClickExpiredException(f"Click '{click_id}' expired at {click_log.expires_at}")
        return click_log

    def build_offer_url(
        self,
        base_url: str,
        click_log: ClickLog,
        extra_params: dict = None,
    ) -> str:
        """Replace {macro} placeholders in offer URL with click tracking data."""
        from ..network_adapters.adapters import get_adapter
        adapter = get_adapter(click_log.network.network_key if click_log.network else "generic")
        context = {
            "click_id":    click_log.click_id,
            "sub_id":      click_log.sub_id or "",
            "user_id":     str(click_log.user_id) if click_log.user_id else "",
            "offer_id":    click_log.offer_id,
            "ip":          click_log.ip_address or "",
            "country":     click_log.country or "",
            **(extra_params or {}),
        }
        return adapter.expand_macros(base_url, context)

    def mark_converted(self, click_log: ClickLog, conversion) -> None:
        """Mark a click as converted and link to conversion."""
        click_log.mark_converted()
        click_converted.send(sender=ClickLog, click_log=click_log, conversion=conversion)

    def expire_stale(self) -> int:
        """Expire all clicks past their expiry time. Returns count expired."""
        count = ClickLog.objects.expired().update(status=ClickStatus.EXPIRED)
        logger.info("Expired %d stale clicks", count)
        return count

    @staticmethod
    def _generate_click_id() -> str:
        return secrets.token_urlsafe(CLICK_ID_LENGTH)

    @staticmethod
    def _compute_fingerprint(ip: str, user_agent: str, device_id: str) -> str:
        if not ip and not user_agent:
            return ""
        raw = f"{ip}:{user_agent}:{device_id}"
        return hashlib.sha256(raw.encode()).hexdigest()


# Module-level singleton
click_handler = ClickHandler()
