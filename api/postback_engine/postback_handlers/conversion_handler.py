"""
postback_handlers/conversion_handler.py
─────────────────────────────────────────
Handles conversion events: create, approve, reject, reverse.
Business logic layer between the postback pipeline and the Conversion model.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Optional
from django.db import transaction
from django.utils import timezone
from ..models import Conversion, AdNetworkConfig, PostbackRawLog, ClickLog
from ..enums import ConversionStatus
from ..exceptions import (
    DuplicateConversionException,
    OfferInactiveException,
    PayoutLimitExceededException,
    RewardDispatchException,
)
from ..constants import MAX_PAYOUT_USD_PER_CONVERSION
from ..signals import conversion_created, conversion_approved, conversion_reversed

logger = logging.getLogger(__name__)


class ConversionHandler:
    """
    Handles the full lifecycle of a Conversion record:
      create() → approve() → dispatch_reward() → [reverse()]
    """

    @transaction.atomic
    def create(
        self,
        raw_log: PostbackRawLog,
        user,
        network: AdNetworkConfig,
        click_log: Optional[ClickLog] = None,
    ) -> Conversion:
        """
        Create a new approved Conversion from a validated PostbackRawLog.
        Raises DuplicateConversionException if transaction_id already exists.
        """
        from django.db import IntegrityError

        reward = network.get_reward_for_offer(raw_log.offer_id)
        points = reward.get("points", 0)
        reward_usd = Decimal(str(reward.get("usd", raw_log.payout)))

        # Calculate time-to-convert
        time_to_convert = None
        if click_log:
            delta = timezone.now() - click_log.clicked_at
            time_to_convert = int(delta.total_seconds())

        try:
            conv = Conversion.objects.create(
                tenant=network.tenant,
                raw_log=raw_log,
                click_log=click_log,
                network=network,
                user=user,
                lead_id=raw_log.lead_id,
                click_id=raw_log.click_id,
                offer_id=raw_log.offer_id,
                transaction_id=raw_log.transaction_id,
                network_payout=raw_log.payout,
                actual_payout=reward_usd,
                currency=raw_log.currency,
                points_awarded=points,
                time_to_convert_seconds=time_to_convert,
                source_ip=raw_log.source_ip,
                status=ConversionStatus.APPROVED,
                approved_at=timezone.now(),
            )
        except IntegrityError:
            raise DuplicateConversionException(
                f"Conversion for transaction_id={raw_log.transaction_id!r} already exists."
            )

        if click_log:
            click_log.mark_converted()

        conversion_created.send(sender=Conversion, conversion=conv)
        logger.info("Conversion created: %s user=%s offer=%s", conv.id, user.id, conv.offer_id)
        return conv

    def approve(self, conversion: Conversion) -> None:
        """Approve a pending conversion."""
        conversion.approve()
        conversion_approved.send(sender=Conversion, conversion=conversion)

    def reject(self, conversion: Conversion, reason: str = "") -> None:
        """Reject a conversion with a reason."""
        conversion.reject(reason=reason)
        logger.info("Conversion rejected: %s reason=%s", conversion.id, reason)

    @transaction.atomic
    def reverse(self, conversion: Conversion, reason: str = "") -> bool:
        """
        Reverse an approved/paid conversion and claw back from wallet.
        Returns True on success, False if already reversed.
        """
        if conversion.is_reversed:
            return False

        conversion.reverse(reason=reason)

        # Clawback from wallet
        try:
            from api.wallet.services import debit_for_reversal
            debit_for_reversal(
                user=conversion.user,
                amount=conversion.actual_payout,
                points=conversion.points_awarded,
                ref_id=str(conversion.id),
                description=f"Conversion reversal: {conversion.offer_id}",
            )
        except Exception as exc:
            logger.error("Wallet debit failed during reversal %s: %s", conversion.id, exc)

        conversion_reversed.send(
            sender=Conversion, conversion=conversion, reason=reason
        )
        logger.info("Conversion reversed: %s user=%s reason=%s", conversion.id, conversion.user_id, reason)
        return True

    def dispatch_reward(self, conversion: Conversion, network: AdNetworkConfig) -> None:
        """
        Credit the user's wallet for an approved conversion.
        Raises RewardDispatchException on failure (triggers retry).
        """
        if network.is_test_mode:
            logger.info("TEST MODE: skipping wallet credit for conversion=%s", conversion.id)
            return

        try:
            from api.wallet.services import credit_from_conversion
            wallet_tx = credit_from_conversion(
                user=conversion.user,
                amount=conversion.actual_payout,
                points=conversion.points_awarded,
                source="postback_engine",
                ref_id=str(conversion.id),
                description=f"CPA Reward: {conversion.offer_id} via {conversion.network.name}",
            )
            conversion.mark_wallet_credited(wallet_transaction_id=wallet_tx.id)
        except Exception as exc:
            from ..models import RetryLog
            RetryLog.objects.create(
                retry_type="reward",
                object_id=conversion.id,
                attempt_number=1,
                error_message=str(exc),
            )
            raise RewardDispatchException(f"Wallet credit failed: {exc}") from exc


# Module-level singleton
conversion_handler = ConversionHandler()
