import logging
from django.utils import timezone
from ...models import Click, UniqueClick
from django.db.models import F

logger = logging.getLogger('smartlink.attribution')


class ClickAttributionService:
    """
    Attribute a conversion (postback) back to the originating click.
    Supports last-click attribution model.
    """

    def attribute(self, offer_id: int, sub1: str = '', ip: str = '',
                  payout: float = 0.0, transaction_id: str = '') -> object:
        """
        Find the originating click for a conversion postback and mark it as converted.

        Attribution priority:
        1. sub1 match (most accurate — publisher sets sub1=click_id)
        2. IP + offer + recent click (fallback)

        Returns the attributed Click or None.
        """
        click = None

        # Strategy 1: sub1 contains click ID
        if sub1:
            click = self._find_by_sub1(sub1, offer_id)

        # Strategy 2: IP + offer ID match (last click in last 24h)
        if not click and ip:
            click = self._find_by_ip(ip, offer_id)

        if click:
            self._mark_converted(click, payout)
            logger.info(
                f"Conversion attributed: click#{click.pk} "
                f"offer#{offer_id} payout={payout} txn={transaction_id}"
            )
        else:
            logger.warning(
                f"Could not attribute conversion: "
                f"offer#{offer_id} sub1={sub1} ip={ip}"
            )

        return click

    def _find_by_sub1(self, sub1_value: str, offer_id: int) -> object:
        """Find click where metadata.sub1 matches the postback sub1 value."""
        try:
            # sub1 = click ID (publisher uses ?sub1={click_id} in smartlink URL)
            if sub1_value.isdigit():
                click = Click.objects.get(
                    pk=int(sub1_value),
                    offer_id=offer_id,
                    is_converted=False,
                )
                return click
        except Click.DoesNotExist:
            pass
        except (ValueError, TypeError):
            pass

        # sub1 may contain a custom value — match via metadata
        try:
            from ...models import ClickMetadata
            metadata = ClickMetadata.objects.select_related('click').get(
                sub1=sub1_value,
                click__offer_id=offer_id,
                click__is_converted=False,
                click__created_at__gte=timezone.now() - timezone.timedelta(days=30),
            )
            return metadata.click
        except Exception:
            return None

    def _find_by_ip(self, ip: str, offer_id: int) -> object:
        """Last-click attribution by IP (within 24 hours)."""
        cutoff = timezone.now() - timezone.timedelta(hours=24)
        return Click.objects.filter(
            ip=ip,
            offer_id=offer_id,
            is_converted=False,
            is_fraud=False,
            is_bot=False,
            created_at__gte=cutoff,
        ).order_by('-created_at').first()

    def _mark_converted(self, click: Click, payout: float):
        """Mark a click as converted and update payout."""
        Click.objects.filter(pk=click.pk).update(
            is_converted=True,
            payout=F('payout') + payout,
        )
        # Update SmartLink totals
        from ...models import SmartLink
        SmartLink.objects.filter(pk=click.smartlink_id).update(
            total_conversions=F('total_conversions') + 1,
            total_revenue=F('total_revenue') + payout,
        )
